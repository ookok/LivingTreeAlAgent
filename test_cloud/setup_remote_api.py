#!/usr/bin/env python3
"""
配置远程API和本地模型优先级
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
_root = Path(__file__).parent
sys.path.insert(0, str(_root))

from core.config import load_config, save_config, AppConfig


def configure_alibaba_api():
    """配置阿里云 DashScope API"""
    print("=== 配置阿里云 DashScope API ===")

    # 读取现有配置
    cfg = load_config()

    # 设置 API Key
    api_key = "sk-59dcddeff7694360a43d427d9ae80d23"
    os.environ["DASHSCOPE_API_KEY"] = api_key

    print(f"API Key: {api_key[:10]}...")
    print("已设置环境变量 DASHSCOPE_API_KEY")

    # 保存配置
    save_config(cfg)
    print("配置已保存")


def configure_model_priority():
    """配置本地模型优先级"""
    print("\n=== 配置本地模型优先级 ===")

    print("本地模型优先级顺序：")
    print("1. Unsloth (最高优先级)")
    print("2. vLLM")
    print("3. llama-cpp")
    print("4. nano-vllm")
    print("5. Ollama (最低优先级)")

    print("\n注意：Unsloth 需要单独安装和配置")
    print("安装方法：pip install unsloth")


def test_remote_api():
    """测试远程 API 调用"""
    print("\n=== 测试远程 API 调用 ===")

    api_key = "sk-59dcddeff7694360a43d427d9ae80d23"
    model = "qwen3.5-plus"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    print(f"API Key: {api_key[:10]}...")
    print(f"模型: {model}")
    print(f"Base URL: {base_url}")

    # 测试 API 连接
    try:
        import httpx

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "你好"}
            ],
            "max_tokens": 100,
            "temperature": 0.7
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        print("\n发送测试请求...")

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                result = response.json()
                print(f"成功! 响应: {result.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')[:200]}")
            else:
                print(f"错误: {response.status_code} - {response.text[:200]}")

    except Exception as e:
        print(f"请求失败: {e}")
        print("请确保网络可以访问 https://dashscope.aliyuncs.com")


if __name__ == "__main__":
    configure_alibaba_api()
    configure_model_priority()
    test_remote_api()