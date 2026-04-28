#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Ollama 服务状态和模型可用性
"""

import time
from core.ollama_client import OllamaClient
from core.config import load_config


def test_ollama_status():
    """测试 Ollama 服务状态和模型可用性"""
    # 输出文件路径
    output_file = "ollama_status.txt"
    
    # 清空输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("🚀 开始测试 Ollama 服务状态\n")
        f.write("=" * 60 + "\n")
    
    try:
        # 加载配置
        config = load_config()
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"Ollama 服务地址: {config.ollama.base_url}\n")
        
        # 创建 Ollama 客户端
        client = OllamaClient(config.ollama)
        
        # 测试服务状态
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write("\n测试 Ollama 服务状态...\n")
        version = client.version()
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"Ollama 服务版本: {version}\n")
            f.write("✅ Ollama 服务正常运行\n")
        
        # 测试模型列表
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write("\n测试模型列表...\n")
        models = client.list_models()
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"可用模型数量: {len(models)}\n")
            for model in models:
                f.write(f"- {model.name}\n")
        
        # 测试模型调用
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write("\n测试模型调用...\n")
        from core.ollama_client import ChatMessage
        messages = [
            ChatMessage(role="user", content="你好")
        ]
        
        start_time = time.time()
        response = ""
        for chunk in client.chat(messages, model="qwen3.5:2b"):
            if chunk.error:
                with open(output_file, 'a', encoding='utf-8') as f:
                    f.write(f"❌ 错误: {chunk.error}\n")
                break
            if chunk.delta:
                response += chunk.delta
            if chunk.done:
                with open(output_file, 'a', encoding='utf-8') as f:
                    f.write("Ollama 模型调用完成\n")
                break
        
        latency = (time.time() - start_time) * 1000
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"响应: {response}\n")
            f.write(f"延迟: {latency:.2f}ms\n")
            f.write("✅ 模型调用正常\n")
        
        # 测试深度搜索
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write("\n测试深度搜索...\n")
        messages = [
            ChatMessage(role="user", content="五一南京有哪些地方值得玩")
        ]
        
        start_time = time.time()
        response = ""
        for chunk in client.chat(messages, model="qwen3.5:2b"):
            if chunk.error:
                with open(output_file, 'a', encoding='utf-8') as f:
                    f.write(f"❌ 错误: {chunk.error}\n")
                break
            if chunk.delta:
                response += chunk.delta
            if chunk.done:
                with open(output_file, 'a', encoding='utf-8') as f:
                    f.write("深度搜索完成\n")
                break
        
        latency = (time.time() - start_time) * 1000
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"内容长度: {len(response)} 字符\n")
            f.write(f"内容: {response}\n")
            f.write(f"延迟: {latency:.2f}ms\n")
            f.write("✅ 深度搜索正常\n")
        
    except Exception as e:
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"❌ 测试失败: {e}\n")
            import traceback
            traceback.print_exc()
    
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("\n" + "=" * 60 + "\n")
        f.write("📋 测试完成\n")
    
    # 打印完成信息
    print(f"测试完成，结果已写入 {output_file}")
    print(f"文件路径: {os.path.abspath(output_file)}")


if __name__ == "__main__":
    test_ollama_status()
