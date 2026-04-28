#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试深度搜索功能，将结果写入文件以避免输出被截断
"""

import asyncio
import time
import os
from core.ollama_client import OllamaClient, ChatMessage
from core.config import load_config


async def test_depth_search(output_file):
    """测试深度搜索"""
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("=== 测试深度搜索 ===\n\n")
    
    # 加载配置
    config = load_config()
    
    # 创建 Ollama 客户端
    client = OllamaClient(config.ollama)
    
    # 测试查询
    query = "五一南京有哪些地方值得玩"
    
    # 连续测试5次，检查输出截断问题
    for i in range(5):
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"\n第 {i+1} 次测试:\n")
            f.write(f"查询: {query}\n")
        
        start_time = time.time()
        try:
            # 构建消息
            messages = [
                ChatMessage(role="user", content=query)
            ]
            
            # 发送消息
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write("开始执行 Ollama 模型调用...\n")
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
                f.write("智能执行结果:\n")
                f.write(f"内容长度: {len(response)} 字符\n")
                f.write(f"内容: {response}\n")
                f.write(f"延迟: {latency:.2f}ms\n")
            
        except Exception as e:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"❌ 智能执行失败: {e}\n")
                import traceback
                traceback.print_exc()
        
        # 等待 2 秒避免请求过于频繁
        time.sleep(2)


async def main():
    """主测试函数"""
    # 输出文件路径
    output_file = "depth_search_output.txt"
    
    # 清空输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("🚀 开始测试深度搜索功能\n")
        f.write("=" * 60 + "\n")
    
    # 测试深度搜索
    await test_depth_search(output_file)
    
    # 完成测试
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("\n" + "=" * 60 + "\n")
        f.write("📋 测试完成\n")
    
    # 打印完成信息
    print(f"测试完成，结果已写入 {output_file}")
    print(f"文件路径: {os.path.abspath(output_file)}")


if __name__ == "__main__":
    asyncio.run(main())
