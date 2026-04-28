#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的深度搜索测试脚本
"""

import asyncio
import time
from core.ollama_client import OllamaClient, ChatMessage
from core.config import load_config


async def test_depth_search():
    """测试深度搜索"""
    print("🚀 开始测试深度搜索功能")
    print("=" * 60)
    
    # 加载配置
    config = load_config()
    
    # 创建 Ollama 客户端
    client = OllamaClient(config.ollama)
    
    # 测试查询
    query = "五一南京有哪些地方值得玩"
    
    # 连续测试5次，检查输出截断问题
    for i in range(5):
        print(f"\n第 {i+1} 次测试:")
        print(f"查询: {query}")
        
        start_time = time.time()
        try:
            # 构建消息
            messages = [
                ChatMessage(role="user", content=query)
            ]
            
            # 发送消息
            print("开始执行 Ollama 模型调用...")
            response = ""
            for chunk in client.chat(messages, model="qwen3.5:2b"):
                if chunk.error:
                    print(f"❌ 错误: {chunk.error}")
                    break
                if chunk.delta:
                    response += chunk.delta
                if chunk.done:
                    print("Ollama 模型调用完成")
                    break
            
            latency = (time.time() - start_time) * 1000
            
            print(f"智能执行结果:")
            print(f"内容长度: {len(response)} 字符")
            print(f"内容: {response}")
            print(f"延迟: {latency:.2f}ms")
            
        except Exception as e:
            print(f"❌ 智能执行失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 等待 2 秒避免请求过于频繁
        time.sleep(2)
    
    print("\n" + "=" * 60)
    print("📋 测试完成")


if __name__ == "__main__":
    asyncio.run(test_depth_search())
