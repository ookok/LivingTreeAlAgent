#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 SmolLM2 模型的初始化、下载和加载功能
"""

import asyncio
import time
from core.smolllm2.ollama_runner import get_runner_manager
from core.smolllm2.l0_integration import smart_execute


async def test_smollm2_initialization():
    """测试 SmolLM2 初始化"""
    print("=== 测试 SmolLM2 初始化 ===")
    
    # 获取 Runner 管理器
    manager = await get_runner_manager()
    
    # 确保 Runner 就绪
    start_time = time.time()
    ready = await manager.ensure_ready()
    latency = (time.time() - start_time) * 1000
    
    print(f"初始化状态: {'成功' if ready else '失败'}")
    print(f"初始化延迟: {latency:.2f}ms")
    
    return ready


async def test_smart_execute():
    """测试智能执行"""
    print("\n=== 测试智能执行 ===")
    
    # 测试用例
    test_cases = [
        "你好",
        "今天天气怎么样？",
        "帮我查一下最新的新闻",
    ]
    
    for prompt in test_cases:
        print(f"\n测试输入: {prompt}")
        
        start_time = time.time()
        try:
            result = await smart_execute(prompt)
            latency = (time.time() - start_time) * 1000
            
            print(f"执行结果: {result['content']}")
            print(f"延迟: {latency:.2f}ms")
            
            if "l0_decision" in result:
                l0_decision = result["l0_decision"]
                print(f"L0 决策: {l0_decision['route']}, 意图: {l0_decision['intent']}")
                print(f"置信度: {l0_decision['confidence']:.2f}")
        except Exception as e:
            print(f"执行失败: {e}")


async def main():
    """主测试函数"""
    print("🚀 开始测试 SmolLM2 初始化和智能路由功能")
    print("=" * 60)
    
    # 测试 SmolLM2 初始化
    init_success = await test_smollm2_initialization()
    
    if init_success:
        # 测试智能执行
        await test_smart_execute()
    else:
        print("\n❌ SmolLM2 初始化失败，无法测试智能执行")
    
    print("\n" + "=" * 60)
    print("📋 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
