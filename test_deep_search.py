#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试深度搜索功能
"""

import asyncio
import time
from core.smolllm2.l0_integration import smart_execute
from core.smolllm2.router import L0Router


async def test_deep_search():
    """测试深度搜索"""
    print("=== 测试深度搜索 ===")
    
    # 测试查询
    queries = [
        "南京溧水养猪场环评报告",
        "北京海淀区科技园区规划",
        "上海浦东新区商业中心建设",
        "广州天河区交通规划",
        "深圳南山区科技园发展"
    ]
    
    # 连续测试多次，查看缓存命中情况
    for i, query in enumerate(queries):
        print(f"\n第 {i+1} 次测试:")
        print(f"查询: {query}")
        
        # 测试 L0 路由
        router = L0Router()
        route_decision = await router.route(query)
        print(f"L0 路由决策: {route_decision.route.value}, 意图: {route_decision.intent.value}")
        print(f"原因: {route_decision.reason}, 置信度: {route_decision.confidence:.2f}")
        print(f"延迟: {route_decision.latency_ms:.2f}ms")
        
        # 测试智能执行
        start_time = time.time()
        try:
            result = await smart_execute(query)
            latency = (time.time() - start_time) * 1000
            
            print(f"\n智能执行结果:")
            print(f"内容: {result['content']}")
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
            print(f"❌ 智能执行失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 等待 2 秒避免请求过于频繁
        time.sleep(2)
    
    # 测试重复查询，查看缓存命中情况
    print("\n=== 测试缓存命中 ===")
    repeat_query = "南京溧水养猪场环评报告"
    for i in range(3):
        print(f"\n重复查询第 {i+1} 次:")
        print(f"查询: {repeat_query}")
        
        start_time = time.time()
        try:
            result = await smart_execute(repeat_query)
            latency = (time.time() - start_time) * 1000
            
            print(f"智能执行结果:")
            print(f"内容: {result['content']}")
            print(f"延迟: {latency:.2f}ms")
            
            if "cache_hit" in result and result["cache_hit"]:
                print("✅ 缓存命中")
            elif "escalate_to_human" in result and result["escalate_to_human"]:
                print("⚠️  转人工")
        except Exception as e:
            print(f"❌ 智能执行失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 等待 2 秒避免请求过于频繁
        time.sleep(2)


async def main():
    """主测试函数"""
    print("🚀 开始测试深度搜索功能")
    print("=" * 60)
    
    # 测试深度搜索
    await test_deep_search()
    
    print("\n" + "=" * 60)
    print("📋 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
