#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 L0-L4 调用和智能路由
"""

import asyncio
import time
from core.smolllm2.l0_integration import smart_execute, get_l0l4_executor
from core.smolllm2.router import L0Router
from core.smolllm2.models import RouteType, IntentType


async def test_route_decision():
    """测试路由决策"""
    print("=== 测试 L0 路由决策 ===")
    
    # 创建 L0 路由器
    router = L0Router()
    
    # 测试用例
    test_cases = [
        # 问候语（应该走本地）
        ("你好", RouteType.LOCAL, IntentType.GREETING),
        ("Hello", RouteType.LOCAL, IntentType.GREETING),
        ("早上好", RouteType.LOCAL, IntentType.GREETING),
        
        # 简单问题（应该走本地）
        ("今天天气怎么样？", RouteType.LOCAL, IntentType.SIMPLE_QUESTION),
        ("你是谁？", RouteType.LOCAL, IntentType.SIMPLE_QUESTION),
        
        # 格式化请求（应该走本地）
        ("帮我格式化这段文本", RouteType.LOCAL, IntentType.FORMAT_CLEAN),
        ("整理一下这个内容", RouteType.LOCAL, IntentType.FORMAT_CLEAN),
        
        # JSON 提取（应该走本地）
        ("提取JSON数据", RouteType.LOCAL, IntentType.JSON_EXTRACT),
        ("把这个转成JSON", RouteType.LOCAL, IntentType.JSON_EXTRACT),
        
        # 简单代码（应该走本地）
        ("帮我修复这个代码", RouteType.LOCAL, IntentType.CODE_SIMPLE),
        ("给这段代码加注释", RouteType.LOCAL, IntentType.CODE_SIMPLE),
        
        # 搜索意图（应该走搜索）
        ("查一下今天的股票行情", RouteType.SEARCH, IntentType.SEARCH_QUERY),
        ("帮我查一下最新的新闻", RouteType.SEARCH, IntentType.SEARCH_QUERY),
        
        # 重型任务（应该走大模型）
        ("写一篇关于人工智能发展趋势的文章，不少于1000字", RouteType.HEAVY, IntentType.LONG_WRITING),
        ("分析一下当前市场的投资机会", RouteType.HEAVY, IntentType.ANALYSIS),
        ("设计一个复杂的系统架构", RouteType.HEAVY, IntentType.CODE_COMPLEX),
        
        # 长文本（应该走大模型）
        ("a" * 1000, RouteType.HEAVY, IntentType.UNKNOWN),
    ]
    
    for prompt, expected_route, expected_intent in test_cases:
        print(f"\n测试输入: {prompt}")
        print(f"期望路由: {expected_route.value}, 期望意图: {expected_intent.value}")
        
        start_time = time.time()
        decision = await router.route(prompt)
        latency = (time.time() - start_time) * 1000
        
        print(f"实际路由: {decision.route.value}, 实际意图: {decision.intent.value}")
        print(f"置信度: {decision.confidence:.2f}, 延迟: {latency:.2f}ms")
        print(f"原因: {decision.reason}")
        
        # 验证路由类型
        if decision.route == expected_route:
            print("✅ 路由类型正确")
        else:
            print(f"❌ 路由类型错误，期望 {expected_route.value}，实际 {decision.route.value}")
        
        # 验证意图类型（如果不是UNKNOWN）
        if expected_intent != IntentType.UNKNOWN and decision.intent == expected_intent:
            print("✅ 意图类型正确")
        elif expected_intent == IntentType.UNKNOWN:
            print("⚠️  意图类型为UNKNOWN，跳过验证")
        else:
            print(f"❌ 意图类型错误，期望 {expected_intent.value}，实际 {decision.intent.value}")


async def test_smart_execute():
    """测试智能执行"""
    print("\n=== 测试 L0-L4 智能执行 ===")
    
    # 测试用例
    test_cases = [
        # 简单问候（应该走本地）
        "你好，我是测试用户",
        
        # 简单问题（应该走本地）
        "今天是星期几？",
    ]
    
    for prompt in test_cases:
        print(f"\n测试输入: {prompt}")
        
        try:
            start_time = time.time()
            result = await smart_execute(prompt)
            latency = (time.time() - start_time) * 1000
            
            print(f"执行结果: {result['content']}")
            print(f"延迟: {latency:.2f}ms")
            
            if "l0_decision" in result:
                l0_decision = result["l0_decision"]
                print(f"L0 决策: {l0_decision['route']}, 意图: {l0_decision['intent']}")
                print(f"置信度: {l0_decision['confidence']:.2f}")
            
            if "cache_hit" in result and result["cache_hit"]:
                print("✅ 缓存命中")
            elif "escalate_to_human" in result and result["escalate_to_human"]:
                print("⚠️  转人工")
        except Exception as e:
            print(f"❌ 执行失败: {e}")
            import traceback
            traceback.print_exc()


async def test_cache_functionality():
    """测试缓存功能"""
    print("\n=== 测试缓存功能 ===")
    
    # 获取执行器
    executor = await get_l0l4_executor()
    
    # 测试相同的输入两次，第二次应该命中缓存
    test_prompt = "你好，测试缓存功能"
    
    print(f"第一次执行: {test_prompt}")
    start_time = time.time()
    result1 = await executor.execute(test_prompt)
    latency1 = (time.time() - start_time) * 1000
    print(f"结果: {result1['content']}")
    print(f"延迟: {latency1:.2f}ms")
    
    print(f"\n第二次执行: {test_prompt}")
    start_time = time.time()
    result2 = await executor.execute(test_prompt)
    latency2 = (time.time() - start_time) * 1000
    print(f"结果: {result2['content']}")
    print(f"延迟: {latency2:.2f}ms")
    
    if "cache_hit" in result2 and result2["cache_hit"]:
        print("✅ 缓存命中成功")
        print(f"缓存加速: {latency1 - latency2:.2f}ms")
    else:
        print("❌ 缓存未命中")


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
    print("🚀 开始测试 L0-L4 调用和智能路由")
    print("=" * 60)
    
    # 测试路由决策
    await test_route_decision()
    
    # 测试统计功能
    await test_stats()
    
    print("\n" + "=" * 60)
    print("📋 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
