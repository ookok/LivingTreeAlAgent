#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 L0 路由功能
"""

import asyncio
from core.smolllm2.l0_integration import preview_route


async def test_l0_route():
    """测试 L0 路由"""
    print("🚀 开始测试 L0 路由功能")
    print("=" * 60)
    
    # 测试查询
    queries = [
        "五一南京周边哪些地方适合玩",
        "请分析以下内容: " + "a" * 1000  # 1000字超长上下文
    ]
    
    for i, query in enumerate(queries):
        print(f"\n测试 {i+1}: {query[:50]}...")
        
        try:
            decision = await preview_route(query)
            print(f"L0 路由决策: {decision.route.value}")
            print(f"意图: {decision.intent.value}")
            print(f"原因: {decision.reason}")
            print(f"置信度: {decision.confidence:.2f}")
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("📋 测试完成")


if __name__ == "__main__":
    asyncio.run(test_l0_route())
