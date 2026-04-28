"""
测试 DeepSeek-V4-Pro thinking 字段处理 + Ollama FRP 地址迁移
"""
import asyncio
import sys
import os

# 强制 UTF-8 编码（Windows 终端兼容）
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from client.src.business.global_model_router import GlobalModelRouter, ModelTier, ModelCapability
from client.src.business.encrypted_config import setup_default_configs, load_model_config


async def test_ollama_frp_address():
    """测试 Ollama FRP 地址迁移"""
    print("=" * 60)
    print("Test 1: Ollama FRP Address Migration")
    print("=" * 60)
    
    # 查看当前加密配置中的 Ollama 地址
    config = load_model_config("ollama")
    if config:
        print(f"Encrypted config Ollama URL: {config.get('base_url')}")
    else:
        print("Ollama config not found, please run setup_default_configs() first")
        return
    
    # 初始化路由器，触发自动迁移
    router = GlobalModelRouter()
    router._load_models_from_encrypted_config()
    
    # 检查 Ollama 模型的 config 中的 url
    for model_id, model_info in router.models.items():
        if model_info.backend.value == "ollama":
            url = model_info.config.get("url", "")
            print(f"Model {model_id} using URL: {url}")
            
            if "mogoo.com.cn" in url:
                print(">>> FRP address migration SUCCESS!")
            elif "localhost" in url:
                print(">>> WARNING: Still using localhost (auto-migration not working)")
    
    print()


async def test_deepseek_thinking_non_stream():
    """测试 DeepSeek 非流式 thinking 处理"""
    print("=" * 60)
    print("Test 2: DeepSeek Non-Stream Thinking Handling")
    print("=" * 60)
    
    router = GlobalModelRouter()
    router._load_models_from_encrypted_config()
    
    # 检查 deepseek_v4_pro 模型是否存在
    if "deepseek_v4_pro" not in router.models:
        print("deepseek_v4_pro model not found, skipping test")
        return
    
    print("Calling DeepSeek-V4-Pro (non-stream)...")
    print("-" * 60)
    
    try:
        response = await router.call_model(
            capability=ModelCapability.REASONING,
            prompt="Please answer in thinking mode: What is 1+1? Show your thinking process.",
            system_prompt="You are a helpful assistant with thinking capability.",
            model_id="deepseek_v4_pro",
            use_cache=False
        )
        
        print("Model response:")
        print(response)
        print("-" * 60)
        
        if "<think>" in response and "</think>" in response:
            print(">>> thinking content correctly wrapped with <think> tags!")
            
            # 提取 thinking 内容
            start = response.find("<think>")
            end = response.find("</think>")
            thinking = response[start+7:end].strip()
            print(f"Thinking content (first 100 chars): {thinking[:100]}...")
        else:
            print(">>> WARNING: No <think> tags found (model may not return thinking content)")
        
    except Exception as e:
        print(f"Call failed: {e}")
    
    print()


async def test_deepseek_thinking_stream():
    """测试 DeepSeek 流式 thinking 处理"""
    print("=" * 60)
    print("Test 3: DeepSeek Stream Thinking Handling")
    print("=" * 60)
    
    router = GlobalModelRouter()
    router._load_models_from_encrypted_config()
    
    if "deepseek_v4_pro" not in router.models:
        print("deepseek_v4_pro model not found, skipping test")
        return
    
    print("Calling DeepSeek-V4-Pro (stream)...")
    print("-" * 60)
    print("Stream output:")
    
    try:
        chunks = []
        in_thinking = False
        
        async for chunk in router.call_model_stream(
            capability=ModelCapability.REASONING,
            prompt="Please answer in thinking mode: What is the capital of China?",
            system_prompt="You are a helpful assistant with thinking capability.",
            model_id="deepseek_v4_pro",
            use_cache=False
        ):
            chunks.append(chunk)
            
            # 检测 thinking 标签
            if "<think>" in chunk:
                in_thinking = True
                print(f"\n[Thinking starts]")
            elif "</think>" in chunk:
                in_thinking = False
                print(f"\n[Thinking ends, formal reply starts]")
            
            # 打印块（用标签区分）
            if in_thinking:
                print(f"[T] {chunk}", end="", flush=True)
            else:
                print(chunk, end="", flush=True)
        
        print("\n" + "-" * 60)
        
        full_response = "".join(chunks)
        if "<think>" in full_response and "</think>" in full_response:
            print(">>> Stream response thinking content correctly tagged!")
        else:
            print(">>> WARNING: No <think> tags found in stream response")
        
    except Exception as e:
        print(f"\nCall failed: {e}")
    
    print()


async def main():
    print("\n=== Testing DeepSeek-V4-Pro thinking field handling ===\n")
    
    # 可以先运行 setup_default_configs() 确保配置正确
    # print("Initializing default configs...")
    # setup_default_configs()
    
    await test_ollama_frp_address()
    await test_deepseek_thinking_non_stream()
    await test_deepseek_thinking_stream()
    
    print("\n=== All tests completed! ===\n")


if __name__ == "__main__":
    asyncio.run(main())
