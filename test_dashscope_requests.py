#!/usr/bin/env python3
"""
测试远程 API 调用（阿里云 DashScope - 使用requests）
"""

import json
import requests


def test_dashscope_api():
    """测试阿里云 DashScope API"""
    print("=== 测试阿里云 DashScope API (requests) ===")

    # 设置 API Key
    api_key = "sk-59dcddeff7694360a43d427d9ae80d23"
    model = "qwen3.5-plus"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    print(f"API Key: {api_key[:10]}...")
    print(f"模型: {model}")
    print(f"Base URL: {base_url}")

    # 构造请求
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "你好，请介绍一下你自己"}
        ],
        "max_tokens": 500,
        "temperature": 0.7,
        "top_p": 0.9
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print("\n发送请求...")

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=30
        )

        print(f"\n响应状态: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"响应内容: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}")
        else:
            print(f"错误响应: {response.text[:500]}")

    except requests.Timeout:
        print("\n错误: 请求超时")
    except requests.ConnectionError as e:
        print(f"\n连接错误: {e}")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_dashscope_api()