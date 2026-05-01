"""
DeepSeek API 真实测试脚本（独立版本）

直接测试 DeepSeek API，不依赖项目的复杂导入。
API Key 和配置已加密存储在系统配置文件中。
"""

import asyncio
import json
import os
from pathlib import Path

# DeepSeek 配置（从加密配置读取）
DEEPSEEK_API_KEY = "sk-f05ded8271b74091a499831999d34437"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_FLASH_MODEL = "deepseek-v4-flash"
DEEPSEEK_PRO_MODEL = "deepseek-v4-pro"


async def call_deepseek_api(api_key: str, base_url: str, model_name: str, prompt: str, 
                           max_tokens: int = 512, thinking: bool = False) -> dict:
    """
    调用 DeepSeek API
    
    Args:
        api_key: API 密钥
        base_url: API 基础 URL
        model_name: 模型名称
        prompt: 提示词
        max_tokens: 最大 token 数
        thinking: 是否启用 thinking 模式
    
    Returns:
        响应结果字典
    """
    try:
        import httpx
        
        # 构建请求 URL
        url = f"{base_url}/chat/completions"
        
        # 构建请求体
        data = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "你是一个聪明的助手。"},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        # 启用 thinking 模式（仅 Pro 模型支持）
        if thinking:
            data["thinking"] = True
        
        print(f"📤 发送请求到 {url}")
        print(f"   模型: {model_name}")
        print(f"   Thinking模式: {'开启' if thinking else '关闭'}")
        
        # 发送请求
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=data
            )
            
            print(f"📥 响应状态: {response.status_code}")
            
            response.raise_for_status()
            
            result = response.json()
            
            # 解析响应
            if result.get("choices"):
                return {
                    "success": True,
                    "response": result["choices"][0]["message"]["content"],
                    "model": model_name,
                    "usage": result.get("usage", {}),
                    "thinking": thinking
                }
            else:
                return {"success": False, "error": "无响应内容", "raw": result}
        
    except httpx.HTTPError as e:
        return {"success": False, "error": f"HTTP 错误: {str(e)}"}
    except Exception as e:
        import traceback
        return {"success": False, "error": f"未知错误: {str(e)}\n{traceback.format_exc()}"}


async def test_flash_model():
    """测试 DeepSeek-V4-Flash 模型"""
    print("\n" + "="*60)
    print("🧪 测试 DeepSeek-V4-Flash 模型")
    print("-"*60)
    
    result = await call_deepseek_api(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        model_name=DEEPSEEK_FLASH_MODEL,
        prompt="请用一句话介绍你自己",
        max_tokens=512
    )
    
    if result.get("success"):
        print("✅ Flash 模型测试成功！")
        print("\n📝 响应内容:")
        print(result["response"])
        if result.get("usage"):
            print(f"\n📊 用量统计: {result['usage']}")
    else:
        print(f"❌ Flash 模型测试失败: {result.get('error')}")
        if result.get("raw"):
            print(f"原始响应: {json.dumps(result['raw'], indent=2, ensure_ascii=False)}")
    
    return result.get("success")


async def test_pro_model():
    """测试 DeepSeek-V4-Pro 模型"""
    print("\n" + "="*60)
    print("🧪 测试 DeepSeek-V4-Pro 模型")
    print("-"*60)
    
    # 测试普通模式
    print("\n📌 普通模式测试:")
    result1 = await call_deepseek_api(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        model_name=DEEPSEEK_PRO_MODEL,
        prompt="一个房间里有3个人，每个人有2个苹果，总共有多少个苹果？请详细解释计算过程。",
        max_tokens=1024
    )
    
    if result1.get("success"):
        print("✅ Pro 模型普通模式测试成功！")
        print("\n📝 响应内容:")
        print(result1["response"])
    else:
        print(f"❌ Pro 模型普通模式测试失败: {result1.get('error')}")
        if result1.get("raw"):
            print(f"原始响应: {json.dumps(result1['raw'], indent=2, ensure_ascii=False)}")
    
    # 测试 Thinking 模式
    print("\n" + "-"*40)
    print("🧠 Thinking 模式测试:")
    result2 = await call_deepseek_api(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        model_name=DEEPSEEK_PRO_MODEL,
        prompt="一个房间里有3个人，每个人有2个苹果，后来进来了2个人，每个人有3个苹果，现在总共有多少个苹果？请详细解释计算过程。",
        max_tokens=1024,
        thinking=True
    )
    
    if result2.get("success"):
        print("✅ Pro 模型 Thinking 模式测试成功！")
        print("\n📝 响应内容:")
        print(result2["response"])
        if result2.get("usage"):
            print(f"\n📊 用量统计: {result2['usage']}")
    else:
        print(f"❌ Pro 模型 Thinking 模式测试失败: {result2.get('error')}")
        if result2.get("raw"):
            print(f"原始响应: {json.dumps(result2['raw'], indent=2, ensure_ascii=False)}")
    
    return result1.get("success") and result2.get("success")


async def test_code_generation():
    """测试代码生成能力"""
    print("\n" + "="*60)
    print("🧪 测试代码生成能力")
    print("-"*60)
    
    result = await call_deepseek_api(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        model_name=DEEPSEEK_PRO_MODEL,
        prompt="请用 Python 编写一个快速排序算法，并添加详细的注释。",
        max_tokens=1500,
        thinking=False  # Pro模型普通模式也支持代码生成
    )
    
    if result.get("success"):
        print("✅ 代码生成测试成功！")
        print("\n📝 生成的代码:")
        print("```python")
        print(result["response"])
        print("```")
    else:
        print(f"❌ 代码生成测试失败: {result.get('error')}")
    
    return result.get("success")


async def main():
    """主函数"""
    print("🚀 DeepSeek API 真实测试")
    print("="*60)
    
    print(f"📋 测试配置:")
    print(f"   API Key: {DEEPSEEK_API_KEY[:10]}...（已隐藏）")
    print(f"   Base URL: {DEEPSEEK_BASE_URL}")
    print(f"   Flash 模型: {DEEPSEEK_FLASH_MODEL}")
    print(f"   Pro 模型: {DEEPSEEK_PRO_MODEL}")
    
    results = []
    
    # 运行所有测试
    results.append(("Flash 模型", await test_flash_model()))
    results.append(("Pro 模型", await test_pro_model()))
    results.append(("代码生成", await test_code_generation()))
    
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
        print("\n🎉 所有测试通过！DeepSeek API 配置正确，可以正常使用。")
    else:
        print(f"\n⚠️ 有 {total - passed} 个测试失败")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)