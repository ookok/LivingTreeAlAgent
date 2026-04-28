"""
测试 DeepSeek LLM（OpenAI 兼容格式）

配置信息：
- base_url: https://api.deepseek.com
- api_key: sk-f05ded8271b74091a499831999d34437
- models: DeepSeek-V4-Flash, DeepSeek-V4-Pro
"""

import requests
import json
import time

# DeepSeek 配置（OpenAI 兼容格式）
DEEPSEEK_CONFIG = {
    "base_url": "https://api.deepseek.com",
    "api_key": "sk-f05ded8271b74091a499831999d34437",
    "models": {
        "flash": "deepseek-v4-flash",  # 注意：小写
        "pro": "deepseek-v4-pro"        # 注意：小写
    }
}


def test_deepseek_chat(model: str, messages: list, temperature: float = 0.7):
    """
    测试 DeepSeek 对话接口（OpenAI 格式）
    
    Args:
        model: 模型名称（DeepSeek-V4-Flash / DeepSeek-V4-Pro）
        messages: 对话历史 [{"role": "user", "content": "..."}]
        temperature: 温度参数
        
    Returns:
        response_text: 模型回复文本
    """
    url = f"{DEEPSEEK_CONFIG['base_url']}/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_CONFIG['api_key']}"
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False
    }
    
    print(f"\n{'='*60}")
    print(f"📊 测试模型: {model}")
    print(f"📝 提示: {messages[-1]['content']}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        elapsed = time.time() - start_time
        
        result = response.json()
        
        # 提取回复文本
        if "choices" in result and len(result["choices"]) > 0:
            response_text = result["choices"][0]["message"]["content"]
            
            print(f"✅ 调用成功！耗时: {elapsed:.2f}秒")
            print(f"📊 使用情况:")
            if "usage" in result:
                usage = result["usage"]
                print(f"   - 提示 tokens: {usage.get('prompt_tokens', 'N/A')}")
                print(f"   - 完成 tokens: {usage.get('completion_tokens', 'N/A')}")
                print(f"   - 总 tokens: {usage.get('total_tokens', 'N/A')}")
            
            print(f"\n📄 模型回复:\n{response_text}\n")
            
            return response_text
        else:
            print(f"❌ 响应格式错误: {result}")
            return None
            
    except requests.exceptions.RequestException as e:
        elapsed = time.time() - start_time
        print(f"❌ 调用失败！耗时: {elapsed:.2f}秒")
        print(f"错误: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"响应内容: {e.response.text}")
        return None


def test_deepseek_models():
    """测试获取模型列表"""
    url = f"{DEEPSEEK_CONFIG['base_url']}/v1/models"
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_CONFIG['api_key']}"
    }
    
    print(f"\n{'='*60}")
    print(f"📊 测试获取模型列表")
    print(f"{'='*60}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        
        print(f"✅ 获取模型列表成功！")
        print(f"可用模型:")
        if "data" in result:
            for model in result["data"]:
                print(f"   - {model.get('id', 'N/A')}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 获取模型列表失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"响应内容: {e.response.text}")
        return None


def main():
    """主测试函数"""
    print("🚀 开始测试 DeepSeek LLM")
    print(f"Base URL: {DEEPSEEK_CONFIG['base_url']}")
    print(f"可用模型: {list(DEEPSEEK_CONFIG['models'].values())}")
    
    # 1. 测试获取模型列表
    test_deepseek_models()
    
    # 2. 测试 DeepSeek-V4-Flash（快速模型）
    flash_model = DEEPSEEK_CONFIG['models']['flash']
    test_deepseek_chat(
        model=flash_model,
        messages=[
            {"role": "user", "content": "请用一句话介绍什么是环境影响评价（EIA）？"}
        ],
        temperature=0.7
    )
    
    # 3. 测试 DeepSeek-V4-Pro（高级模型）
    pro_model = DEEPSEEK_CONFIG['models']['pro']
    test_deepseek_chat(
        model=pro_model,
        messages=[
            {"role": "user", "content": "环评报告包含哪些主要章节？请列出并简要说明。"}
        ],
        temperature=0.3
    )
    
    # 4. 测试中文能力
    test_deepseek_chat(
        model=flash_model,
        messages=[
            {"role": "user", "content": "解释一下「环境敏感点」在环评中的含义。"}
        ],
        temperature=0.5
    )
    
    print(f"\n{'='*60}")
    print("✅ 测试完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
