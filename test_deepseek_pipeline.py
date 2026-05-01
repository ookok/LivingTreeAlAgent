"""
使用 DeepSeek 的完整 AI 流水线测试脚本

测试内容：
1. 任务分解引擎 - 使用 DeepSeek 进行需求分析
2. 代码生成单元 - 使用 DeepSeek 生成代码
3. 质量评估 - 使用 DeepSeek 评估代码质量
4. 完整工作流 - 端到端测试
"""

import asyncio
import sys
import os
import json

# DeepSeek 配置
DEEPSEEK_API_KEY = "sk-f05ded8271b74091a499831999d34437"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


async def call_deepseek(model, messages, max_tokens=1024, thinking=False):
    """调用 DeepSeek API"""
    import httpx
    
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    
    data = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
    if thinking and "pro" in model.lower():
        data["thinking"] = {
            "type": "enabled",
            "thought": True,
            "thought_num": 5,
            "thought_max_token": 512
        }
    
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json=data
        )
        
        if response.status_code != 200:
            print(f"❌ API 调用失败: {response.text}")
            return None
        
        result = response.json()
        if result.get("choices"):
            return {
                "response": result["choices"][0]["message"]["content"],
                "usage": result.get("usage", {})
            }
    
    return None


async def test_task_decomposition():
    """测试任务分解引擎"""
    print("\n" + "="*60)
    print("🧪 测试任务分解引擎")
    print("="*60)
    
    requirement = "开发一个用户管理系统，支持用户注册、登录和权限管理功能"
    
    messages = [
        {
            "role": "system",
            "content": """你是一个资深产品经理，擅长将自然语言需求分解为结构化的任务列表。
            
            请按照以下格式输出：
            {
                "epic": "史诗级需求名称",
                "user_stories": [
                    {
                        "id": "US-001",
                        "title": "用户故事标题",
                        "description": "作为...，我希望...，以便...",
                        "priority": "高/中/低",
                        "tasks": [
                            {"id": "T-001", "title": "任务标题", "estimated_hours": 4}
                        ]
                    }
                ],
                "total_estimated_hours": 40
            }
            """
        },
        {"role": "user", "content": f"请分解以下需求：{requirement}"}
    ]
    
    result = await call_deepseek("deepseek-v4-pro", messages, max_tokens=2048, thinking=True)
    
    if result:
        print("✅ 任务分解成功")
        print(f"\n📋 分解结果:")
        
        try:
            parsed = json.loads(result["response"])
            print(f"   史诗: {parsed.get('epic', '未命名')}")
            print(f"   用户故事数: {len(parsed.get('user_stories', []))}")
            print(f"   预估工时: {parsed.get('total_estimated_hours', 0)} 小时")
            
            for us in parsed.get("user_stories", []):
                print(f"\n   📌 {us.get('id')}: {us.get('title')}")
                print(f"      优先级: {us.get('priority')}")
                print(f"      任务数: {len(us.get('tasks', []))}")
                
        except json.JSONDecodeError:
            print(f"响应内容:\n{result['response']}")
        
        print(f"\n📊 Token 使用: {result['usage']}")
        return result
    
    return None


async def test_code_generation():
    """测试代码生成单元"""
    print("\n" + "="*60)
    print("🧪 测试代码生成单元")
    print("="*60)
    
    requirement = "使用 Python FastAPI 编写一个用户登录 API，支持 JWT 认证"
    
    messages = [
        {
            "role": "system",
            "content": """你是一个资深 Python 开发者，擅长编写高质量的代码。
            
            请输出完整的代码实现，包括：
            1. 导入语句
            2. 函数定义
            3. 类型提示
            4. 注释
            5. 错误处理
            
            代码格式：
            ```python
            # 代码在这里
            ```
            """
        },
        {"role": "user", "content": f"请实现以下功能：{requirement}"}
    ]
    
    result = await call_deepseek("deepseek-v4-pro", messages, max_tokens=3072)
    
    if result:
        print("✅ 代码生成成功")
        print(f"\n💻 生成的代码:")
        
        # 提取代码块
        response = result["response"]
        if "```python" in response:
            code = response.split("```python")[1].split("```")[0].strip()
            print(f"```python\n{code}\n```")
        else:
            print(response)
        
        print(f"\n📊 Token 使用: {result['usage']}")
        return result
    
    return None


async def test_code_review():
    """测试代码审查（质量评估）"""
    print("\n" + "="*60)
    print("🧪 测试代码审查（质量评估）")
    print("="*60)
    
    code = """
async def login(username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if user and verify_password(password, user.hashed_password):
        token = create_access_token(data={"sub": user.username})
        return {"access_token": token, "token_type": "bearer"}
    return {"error": "Invalid credentials"}
    """
    
    messages = [
        {
            "role": "system",
            "content": """你是一个资深代码审查专家。请从以下维度评估代码质量：
            
            1. 安全性：是否有安全漏洞？
            2. 可读性：代码是否清晰易懂？
            3. 健壮性：是否有适当的错误处理？
            4. 最佳实践：是否遵循行业最佳实践？
            
            请输出详细的审查报告。
            """
        },
        {"role": "user", "content": f"请审查以下代码：\n```python\n{code}\n```"}
    ]
    
    result = await call_deepseek("deepseek-v4-pro", messages, max_tokens=1024)
    
    if result:
        print("✅ 代码审查完成")
        print(f"\n📝 审查报告:\n{result['response']}")
        print(f"\n📊 Token 使用: {result['usage']}")
        return result
    
    return None


async def test_document_generation():
    """测试需求文档生成"""
    print("\n" + "="*60)
    print("🧪 测试需求文档生成")
    print("="*60)
    
    requirement = "开发一个待办事项应用，支持任务创建、编辑、删除和状态管理"
    
    messages = [
        {
            "role": "system",
            "content": """你是一个专业的技术文档编写者。请根据需求生成结构化的需求文档，包括：
            
            1. 需求概述
            2. 功能需求
            3. 非功能需求
            4. 用户故事
            5. 验收标准
            
            使用 Markdown 格式输出。
            """
        },
        {"role": "user", "content": f"请为以下需求生成需求文档：{requirement}"}
    ]
    
    result = await call_deepseek("deepseek-v4-pro", messages, max_tokens=2048, thinking=True)
    
    if result:
        print("✅ 文档生成成功")
        print(f"\n📄 需求文档:\n{result['response'][:1000]}...")
        print(f"\n📊 Token 使用: {result['usage']}")
        return result
    
    return None


async def test_full_workflow():
    """测试完整工作流"""
    print("\n" + "="*60)
    print("🧪 测试完整工作流")
    print("="*60)
    
    requirement = "开发一个简单的图书管理 API，支持 CRUD 操作"
    
    print(f"🎯 需求: {requirement}")
    print("\n🚀 开始执行工作流...")
    
    # 步骤 1: 需求分析
    print("\n🔍 步骤 1: 需求分析")
    analysis_result = await call_deepseek(
        "deepseek-v4-flash",
        [
            {"role": "system", "content": "请分析以下需求的关键点："},
            {"role": "user", "content": requirement}
        ],
        max_tokens=512
    )
    
    if analysis_result:
        print("✅ 需求分析完成")
    
    # 步骤 2: 任务分解
    print("\n📋 步骤 2: 任务分解")
    decomposition_result = await call_deepseek(
        "deepseek-v4-pro",
        [
            {"role": "system", "content": "请将以下需求分解为具体任务："},
            {"role": "user", "content": requirement}
        ],
        max_tokens=1024
    )
    
    if decomposition_result:
        print("✅ 任务分解完成")
    
    # 步骤 3: 代码生成
    print("\n💻 步骤 3: 代码生成")
    code_result = await call_deepseek(
        "deepseek-v4-pro",
        [
            {"role": "system", "content": "请使用 Python FastAPI 实现以下 API："},
            {"role": "user", "content": requirement}
        ],
        max_tokens=2048
    )
    
    if code_result:
        print("✅ 代码生成完成")
    
    # 步骤 4: 测试用例生成
    print("\n🧪 步骤 4: 测试用例生成")
    test_result = await call_deepseek(
        "deepseek-v4-flash",
        [
            {"role": "system", "content": "请为以下 API 生成单元测试用例："},
            {"role": "user", "content": requirement}
        ],
        max_tokens=1024
    )
    
    if test_result:
        print("✅ 测试用例生成完成")
    
    print("\n🎉 工作流执行完成！")
    
    return True


async def main():
    """主函数"""
    print("🚀 DeepSeek AI 流水线完整测试")
    print("="*60)
    print(f"📊 使用模型: DeepSeek-V4-Pro (支持 Thinking 模式)")
    print(f"🔑 API Key: {DEEPSEEK_API_KEY[:10]}...")
    print()
    
    results = []
    
    # 运行测试
    results.append(("任务分解", await test_task_decomposition()))
    results.append(("代码生成", await test_code_generation()))
    results.append(("代码审查", await test_code_review()))
    results.append(("文档生成", await test_document_generation()))
    results.append(("完整工作流", await test_full_workflow()))
    
    # 输出总结
    print("\n" + "="*60)
    print("📊 测试结果总结")
    print("="*60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"   {status} {name}")
    
    print(f"\n   总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！DeepSeek 集成成功！")
    else:
        print(f"\n⚠️ 有 {total - passed} 个测试失败")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)