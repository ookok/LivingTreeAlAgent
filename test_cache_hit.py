#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试缓存命中情况
"""

import asyncio
import time
from core.smolllm2.l0_integration import smart_execute, get_l0l4_executor


async def test_cache_hit():
    """测试缓存命中"""
    print("=== 测试缓存命中 ===")
    
    # 测试查询
    query = "南京溧水养猪场环评报告"
    
    # 先测试 L0 路由
    print("\n测试 L0 路由:")
    from core.smolllm2.l0_integration import preview_route
    try:
        decision = await preview_route(query)
        print(f"L0 路由决策: {decision.route.value}, 意图: {decision.intent.value}")
        print(f"原因: {decision.reason}, 置信度: {decision.confidence:.2f}")
    except Exception as e:
        print(f"❌ L0 路由测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 连续测试3次，查看缓存命中情况
    for i in range(3):
        print(f"\n第 {i+1} 次测试:")
        print(f"查询: {query}")
        
        start_time = time.time()
        try:
            print("开始执行 smart_execute...")
            result = await smart_execute(query)
            print("smart_execute 执行完成")
            latency = (time.time() - start_time) * 1000
            
            print(f"智能执行结果:")
            print(f"内容: {result['content'][:100]}...")  # 只显示前100个字符
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
        
        # 等待 2 秒避免请求过于频繁
        time.sleep(2)
    
    # 获取统计信息
    executor = await get_l0l4_executor()
    stats = executor.get_stats()
    print(f"\n统计信息: {stats}")
    print(f"总请求数: {stats.get('total', 0)}")
    print(f"缓存命中: {stats.get('cache', 0)}")
    print(f"本地执行: {stats.get('local', 0)}")
    print(f"大模型推理: {stats.get('heavy', 0)}")


async def main():
    """主测试函数"""
    print("🚀 开始测试缓存命中功能")
    print("=" * 60)
    
    # 测试缓存命中
    await test_cache_hit()
    
    print("\n" + "=" * 60)
    print("📋 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
