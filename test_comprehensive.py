#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合测试脚本，测试深度搜索和超长上下文处理
"""

import asyncio
import time
from core.smolllm2.l0_integration import smart_execute, preview_route


async def test_deep_search():
    """测试深度搜索"""
    print("=== 测试深度搜索 ===")
    
    # 测试查询
    query = "五一南京周边哪些地方适合玩"
    
    # 测试 L0 路由
    print("\n测试 L0 路由:")
    try:
        decision = await preview_route(query)
        print(f"L0 路由决策: {decision.route.value}, 意图: {decision.intent.value}")
        print(f"原因: {decision.reason}, 置信度: {decision.confidence:.2f}")
    except Exception as e:
        print(f"❌ L0 路由测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试智能执行
    print("\n测试智能执行:")
    start_time = time.time()
    try:
        print("开始执行 smart_execute...")
        result = await smart_execute(query)
        print("smart_execute 执行完成")
        latency = (time.time() - start_time) * 1000
        
        print(f"智能执行结果:")
        print(f"内容长度: {len(result['content'])} 字符")
        print(f"内容: {result['content'][:300]}...")  # 只显示前300个字符
        print(f"延迟: {latency:.2f}ms")
        
        if "cache_hit" in result and result["cache_hit"]:
            print("✅ 缓存命中")
        elif "escalate_to_human" in result and result["escalate_to_human"]:
            print("⚠️  转人工")
        
        if "l0_decision" in result:
            l0_decision = result["l0_decision"]
            print(f"L0 决策: {l0_decision['route']}, 意图: {l0_decision['intent']}")
            print(f"原因: {l0_decision['reason']}")
    except Exception as e:
        print(f"❌ 智能执行失败: {e}")
        import traceback
        traceback.print_exc()


async def test_long_context():
    """测试超长上下文处理"""
    print("\n=== 测试超长上下文处理 ===")
    
    # 创建1000字的超长上下文
    long_context = "a" * 1000
    query = f"请分析以下内容: {long_context}"
    
    print(f"超长上下文长度: {len(long_context)} 字符")
    
    # 测试 L0 路由
    print("\n测试 L0 路由:")
    try:
        decision = await preview_route(query)
        print(f"L0 路由决策: {decision.route.value}, 意图: {decision.intent.value}")
        print(f"原因: {decision.reason}, 置信度: {decision.confidence:.2f}")
    except Exception as e:
        print(f"❌ L0 路由测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试智能执行
    print("\n测试智能执行:")
    start_time = time.time()
    try:
        result = await smart_execute(query)
        latency = (time.time() - start_time) * 1000
        
        print(f"智能执行结果:")
        print(f"内容: {result['content'][:200]}...")  # 只显示前200个字符
        print(f"延迟: {latency:.2f}ms")
        
        if "cache_hit" in result and result["cache_hit"]:
            print("✅ 缓存命中")
        elif "escalate_to_human" in result and result["escalate_to_human"]:
            print("⚠️  转人工")
        
        if "l0_decision" in result:
            l0_decision = result["l0_decision"]
            print(f"L0 决策: {l0_decision['route']}, 意图: {l0_decision['intent']}")
            print(f"原因: {l0_decision['reason']}")
    except Exception as e:
        print(f"❌ 智能执行失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主测试函数"""
    print("🚀 开始综合测试")
    print("=" * 60)
    
    # 测试深度搜索
    await test_deep_search()
    
    # 测试超长上下文处理
    await test_long_context()
    
    print("\n" + "=" * 60)
    print("📋 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
