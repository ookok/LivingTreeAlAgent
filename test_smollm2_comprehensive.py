#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合测试 SmolLM2 初始化、路由和备用分类功能
"""

import asyncio
import time
from core.smolllm2.ollama_runner import get_runner_manager
from core.smolllm2.router import L0Router


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


async def test_long_text_route():
    """测试长文本路由"""
    print("\n=== 测试长文本路由 ===")
    
    # 创建 L0 路由器
    router = L0Router()
    
    # 测试短文本
    short_text = "你好"
    print(f"短文本输入: {short_text}")
    decision = await router.route(short_text)
    print(f"路由决策: {decision.route.value}, 意图: {decision.intent.value}")
    print(f"原因: {decision.reason}, 置信度: {decision.confidence:.2f}")
    
    # 测试长文本（超过1000字符）
    long_text = "a" * 1100
    print(f"\n长文本输入: {long_text[:50]}... (共{len(long_text)}字符)")
    decision = await router.route(long_text)
    print(f"路由决策: {decision.route.value}, 意图: {decision.intent.value}")
    print(f"原因: {decision.reason}, 置信度: {decision.confidence:.2f}")
    
    # 测试中型文本（接近阈值）
    medium_text = "a" * 900
    print(f"\n中型文本输入: {medium_text[:50]}... (共{len(medium_text)}字符)")
    decision = await router.route(medium_text)
    print(f"路由决策: {decision.route.value}, 意图: {decision.intent.value}")
    print(f"原因: {decision.reason}, 置信度: {decision.confidence:.2f}")


async def test_fallback_classification():
    """测试备用分类方法"""
    print("\n=== 测试备用分类方法 ===")
    
    # 创建 L0 路由器
    router = L0Router()
    
    # 测试问候语
    greeting = "你好"
    print(f"问候语输入: {greeting}")
    decision = await router.route(greeting)
    print(f"路由决策: {decision.route.value}, 意图: {decision.intent.value}")
    print(f"原因: {decision.reason}, 置信度: {decision.confidence:.2f}")
    
    # 测试搜索意图
    search = "查一下今天的股票行情"
    print(f"\n搜索意图输入: {search}")
    decision = await router.route(search)
    print(f"路由决策: {decision.route.value}, 意图: {decision.intent.value}")
    print(f"原因: {decision.reason}, 置信度: {decision.confidence:.2f}")
    
    # 测试重型任务
    heavy = "写一篇关于人工智能发展趋势的文章，不少于1000字"
    print(f"\n重型任务输入: {heavy}")
    decision = await router.route(heavy)
    print(f"路由决策: {decision.route.value}, 意图: {decision.intent.value}")
    print(f"原因: {decision.reason}, 置信度: {decision.confidence:.2f}")


async def test_stats():
    """测试统计功能"""
    print("\n=== 测试统计功能 ===")
    
    # 创建 L0 路由器
    router = L0Router()
    
    # 执行几个测试
    test_prompts = [
        "你好",
        "今天天气怎么样？",
        "帮我查一下最新的新闻",
        "写一篇关于人工智能的文章",
        "a" * 1100,  # 长文本
    ]
    
    for prompt in test_prompts:
        await router.route(prompt)
    
    # 获取统计信息
    stats = router.get_stats()
    print(f"统计信息: {stats}")
    print(f"总请求数: {stats.get('total', 0)}")
    print(f"快反率: {stats.get('fast_response_rate', 0.0)}")
    print(f"缓存命中: {stats.get('cache', 0)}")
    print(f"本地执行: {stats.get('local', 0)}")
    print(f"搜索请求: {stats.get('search', 0)}")
    print(f"大模型推理: {stats.get('heavy', 0)}")


async def main():
    """主测试函数"""
    print("🚀 开始综合测试 SmolLM2 功能")
    print("=" * 60)
    
    # 测试 SmolLM2 初始化
    init_success = await test_smollm2_initialization()
    
    if init_success:
        # 测试长文本路由
        await test_long_text_route()
        
        # 测试备用分类方法
        await test_fallback_classification()
        
        # 测试统计功能
        await test_stats()
    else:
        print("\n❌ SmolLM2 初始化失败，无法测试其他功能")
    
    print("\n" + "=" * 60)
    print("📋 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
