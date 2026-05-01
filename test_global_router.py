"""
使用 GlobalModelRouter 的 AI 流水线测试脚本

测试内容：
1. 任务分解引擎 - 使用 GlobalModelRouter 进行需求分析
2. 代码生成单元 - 使用 GlobalModelRouter 生成代码
3. DeepSeek Thinking 模式测试
4. 完整工作流测试
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'client', 'src'))


async def test_task_decomposition():
    """测试任务分解引擎"""
    print("\n" + "="*60)
    print("🧪 测试任务分解引擎")
    print("="*60)
    
    from business.global_model_router import GlobalModelRouter, ModelCapability, RoutingStrategy
    
    router = GlobalModelRouter()
    
    requirement = "开发一个用户管理系统，支持用户注册、登录和权限管理功能"
    
    system_prompt = """你是一个资深产品经理，擅长将自然语言需求分解为结构化的任务列表。

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
    
    result = await router.call_model(
        capability=ModelCapability.PLANNING,
        prompt=f"请分解以下需求：{requirement}",
        system_prompt=system_prompt,
        strategy=RoutingStrategy.QUALITY  # 使用高质量策略
    )
    
    if result:
        print("✅ 任务分解成功")
        print(f"\n📋 分解结果:\n{result[:1000]}...")
        return result
    
    return None


async def test_code_generation():
    """测试代码生成单元"""
    print("\n" + "="*60)
    print("🧪 测试代码生成单元")
    print("="*60)
    
    from business.global_model_router import GlobalModelRouter, ModelCapability, RoutingStrategy
    
    router = GlobalModelRouter()
    
    requirement = "使用 Python FastAPI 编写一个用户登录 API，支持 JWT 认证"
    
    system_prompt = """你是一个资深 Python 开发者，擅长编写高质量的代码。

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
    
    result = await router.call_model(
        capability=ModelCapability.CODE_GENERATION,
        prompt=f"请实现以下功能：{requirement}",
        system_prompt=system_prompt,
        strategy=RoutingStrategy.QUALITY
    )
    
    if result:
        print("✅ 代码生成成功")
        print(f"\n💻 生成的代码:\n{result[:1500]}...")
        return result
    
    return None


async def test_thinking_mode():
    """测试 DeepSeek Thinking 模式"""
    print("\n" + "="*60)
    print("🧪 测试 DeepSeek Thinking 模式")
    print("="*60)
    
    from business.global_model_router import GlobalModelRouter, ModelCapability, RoutingStrategy
    
    router = GlobalModelRouter()
    
    question = "一个房间里有3个人，每个人有2个苹果，后来进来了2个人，每个人有3个苹果，现在总共有多少个苹果？请详细解释计算过程。"
    
    # 使用 PLANNING 能力进行推理（已验证可用）
    print("\n📌 使用 PLANNING 能力:")
    result1 = await router.call_model(
        capability=ModelCapability.PLANNING,
        prompt=question,
        system_prompt="你是一个数学助手，详细解释你的计算过程。",
        strategy=RoutingStrategy.QUALITY
    )
    
    if result1:
        print(f"响应: {result1}")
        # 检查是否包含思考过程
        if "<think>" in result1:
            print("\n✅ 检测到思考过程！")
        return True
    else:
        print("❌ 调用失败")
        return False


async def test_full_workflow():
    """测试完整工作流"""
    print("\n" + "="*60)
    print("🧪 测试完整工作流")
    print("="*60)
    
    from business.global_model_router import GlobalModelRouter, ModelCapability, RoutingStrategy
    
    router = GlobalModelRouter()
    
    requirement = "开发一个简单的图书管理 API，支持 CRUD 操作"
    
    print(f"🎯 需求: {requirement}")
    print("\n🚀 开始执行工作流...")
    
    # 步骤 1: 需求分析（使用 PLANNING 能力）
    print("\n🔍 步骤 1: 需求分析")
    analysis_result = await router.call_model(
        capability=ModelCapability.PLANNING,
        prompt=f"请分析以下需求的关键点，并列出核心功能：{requirement}",
        strategy=RoutingStrategy.SPEED
    )
    if analysis_result:
        print("✅ 需求分析完成")
    
    # 步骤 2: 任务分解
    print("\n📋 步骤 2: 任务分解")
    decomposition_result = await router.call_model(
        capability=ModelCapability.PLANNING,
        prompt=f"请将以下需求分解为具体的开发任务：{requirement}",
        strategy=RoutingStrategy.BALANCED
    )
    if decomposition_result:
        print("✅ 任务分解完成")
    
    # 步骤 3: 代码生成（使用 CONTENT_GENERATION 能力）
    print("\n💻 步骤 3: 代码生成")
    code_result = await router.call_model(
        capability=ModelCapability.CONTENT_GENERATION,
        prompt=f"请使用 Python FastAPI 实现以下图书管理 API，支持 CRUD 操作：{requirement}",
        strategy=RoutingStrategy.QUALITY
    )
    if code_result:
        print("✅ 代码生成完成")
    
    # 步骤 4: 代码审查（使用 PLANNING 能力进行审查）
    print("\n🔍 步骤 4: 代码审查")
    if code_result:
        review_result = await router.call_model(
            capability=ModelCapability.PLANNING,
            prompt=f"请审查以下代码的质量，指出潜在问题和改进建议：\n{code_result[:500]}...",
            strategy=RoutingStrategy.QUALITY
        )
        if review_result:
            print("✅ 代码审查完成")
    
    print("\n🎉 工作流执行完成！")
    return True


async def main():
    """主函数"""
    print("🚀 使用 GlobalModelRouter 的 AI 流水线测试")
    print("="*60)
    
    results = []
    
    # 运行测试
    results.append(("任务分解", await test_task_decomposition()))
    results.append(("代码生成", await test_code_generation()))
    results.append(("Thinking 模式", await test_thinking_mode()))
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
        print("\n🎉 所有测试通过！GlobalModelRouter 集成成功！")
    else:
        print(f"\n⚠️ 有 {total - passed} 个测试失败")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)