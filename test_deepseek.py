"""
DeepSeek API 真实测试脚本

使用系统统一的加密配置文件进行测试：
1. 从加密配置加载 DeepSeek API 配置
2. 测试 DeepSeek-V4-Flash 模型
3. 测试 DeepSeek-V4-Pro 模型（支持 thinking 模式）
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_deepseek_api():
    """测试 DeepSeek API"""
    print("🚀 DeepSeek API 真实测试")
    print("="*60)
    
    # 1. 加载加密配置
    from client.src.business.encrypted_config import get_config_manager
    
    manager = get_config_manager()
    deepseek_config = manager.load_config("deepseek")
    
    if not deepseek_config:
        print("❌ 无法加载 DeepSeek 配置")
        return False
    
    api_key = deepseek_config.get("api_key")
    base_url = deepseek_config.get("base_url")
    models = deepseek_config.get("models", {})
    
    print(f"📋 配置信息:")
    print(f"   - API Key: {api_key[:10]}...（已隐藏）")
    print(f"   - Base URL: {base_url}")
    print(f"   - 可用模型: {list(models.keys())}")
    print()
    
    # 2. 测试 DeepSeek-V4-Flash
    print("🧪 测试 DeepSeek-V4-Flash 模型")
    print("-"*60)
    
    flash_config = models.get("flash")
    if flash_config:
        flash_result = await call_deepseek_api(
            api_key=api_key,
            base_url=base_url,
            model_name=flash_config.get("model_name"),
            prompt="请用一句话介绍你自己",
            max_tokens=512
        )
        
        if flash_result.get("success"):
            print(f"✅ Flash 模型测试成功")
            print(f"   响应: {flash_result['response'][:100]}...")
        else:
            print(f"❌ Flash 模型测试失败: {flash_result.get('error')}")
    else:
        print("⚠️ Flash 模型配置不存在")
    
    print()
    
    # 3. 测试 DeepSeek-V4-Pro（支持 thinking 模式）
    print("🧪 测试 DeepSeek-V4-Pro 模型（支持 thinking 模式）")
    print("-"*60)
    
    pro_config = models.get("pro")
    if pro_config:
        # 测试普通模式
        pro_result = await call_deepseek_api(
            api_key=api_key,
            base_url=base_url,
            model_name=pro_config.get("model_name"),
            prompt="一个房间里有3个人，每个人有2个苹果，总共有多少个苹果？请详细解释计算过程。",
            max_tokens=1024
        )
        
        if pro_result.get("success"):
            print(f"✅ Pro 模型测试成功")
            print(f"   响应: {pro_result['response'][:150]}...")
        else:
            print(f"❌ Pro 模型测试失败: {pro_result.get('error')}")
        
        # 测试 thinking 模式
        print("\n🧠 测试 Pro 模型 Thinking 模式")
        thinking_result = await call_deepseek_api(
            api_key=api_key,
            base_url=base_url,
            model_name=pro_config.get("model_name"),
            prompt="一个房间里有3个人，每个人有2个苹果，后来进来了2个人，每个人有3个苹果，现在总共有多少个苹果？请详细解释计算过程。",
            max_tokens=1024,
            thinking=True  # 启用 thinking 模式
        )
        
        if thinking_result.get("success"):
            print(f"✅ Thinking 模式测试成功")
            print(f"   响应: {thinking_result['response'][:200]}...")
        else:
            print(f"❌ Thinking 模式测试失败: {thinking_result.get('error')}")
    else:
        print("⚠️ Pro 模型配置不存在")
    
    print()
    print("="*60)
    print("📊 测试完成")
    
    return True


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
            data["thinking_options"] = {
                "enable": True,
                "max_thinking_steps": 10
            }
        
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
            
            response.raise_for_status()
            
            result = response.json()
            
            # 解析响应
            if result.get("choices"):
                return {
                    "success": True,
                    "response": result["choices"][0]["message"]["content"],
                    "model": model_name,
                    "usage": result.get("usage", {})
                }
            else:
                return {"success": False, "error": "无响应内容"}
        
    except httpx.HTTPError as e:
        return {"success": False, "error": f"HTTP 错误: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"未知错误: {str(e)}"}


async def main():
    """主函数"""
    print("🧪 DeepSeek API 真实测试脚本")
    print("="*60)
    
    # 先检查加密配置
    from client.src.business.encrypted_config import get_config_manager, setup_default_configs
    
    manager = get_config_manager()
    
    # 如果配置不存在，设置默认配置
    if "deepseek" not in manager.list_configs():
        print("⚠️ DeepSeek 配置不存在，正在设置默认配置...")
        setup_default_configs()
    
    # 运行测试
    await test_deepseek_api()


if __name__ == "__main__":
    asyncio.run(main())