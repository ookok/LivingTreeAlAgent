#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
控制台会话程序，用于测试深度搜索功能
"""

import asyncio
import time
from core.smolllm2.l0_integration import smart_execute, preview_route


async def console_session():
    """控制台会话"""
    print("开始控制台会话")
    print("=" * 60)
    print("输入 'exit' 退出会话")
    print("输入 'clear' 清空缓存")
    print("输入 'stats' 查看统计信息")
    print("=" * 60)
    
    while True:
        # 获取用户输入
        prompt = input("\n请输入您的问题: ")
        
        # 处理特殊命令
        if prompt.lower() == 'exit':
            print("退出会话")
            break
        elif prompt.lower() == 'clear':
            # 清空缓存
            from core.smolllm2.l0_integration import get_l0l4_executor
            executor = await get_l0l4_executor()
            router = await executor._get_l0_router()
            router.clear_cache()
            print("缓存已清空")
            continue
        elif prompt.lower() == 'stats':
            # 查看统计信息
            from core.smolllm2.l0_integration import get_l0l4_executor
            executor = await get_l0l4_executor()
            stats = executor.get_stats()
            print("统计信息:")
            print(f"总请求数: {stats.get('total', 0)}")
            print(f"缓存命中: {stats.get('cache', 0)}")
            print(f"本地执行: {stats.get('local', 0)}")
            print(f"搜索请求: {stats.get('search', 0)}")
            print(f"大模型推理: {stats.get('heavy', 0)}")
            print(f"转人工: {stats.get('human', 0)}")
            print(f"平均延迟: {stats.get('avg_latency_ms', 0):.2f}ms")
            print(f"快反率: {stats.get('fast_response_rate', 0):.2f}")
            continue
        
        # 测试 L0 路由
        print("\n分析意图和路由...")
        try:
            decision = await preview_route(prompt)
            print(f"L0 路由决策: {decision.route.value}")
            print(f"意图: {decision.intent.value}")
            print(f"原因: {decision.reason}")
            print(f"置信度: {decision.confidence:.2f}")
            print(f"延迟: {decision.latency_ms:.2f}ms")
            print(f"模型: {decision.model_used}")
            print(f"是否备用: {decision.fallback}")
        except Exception as e:
            print(f"L0 路由测试失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 测试智能执行
        print("\n执行深度搜索...")
        start_time = time.time()
        try:
            result = await smart_execute(prompt)
            latency = (time.time() - start_time) * 1000
            
            print(f"\n执行结果:")
            print(f"内容长度: {len(result.get('content', ''))} 字符")
            print(f"内容: {result.get('content', '')}")
            print(f"延迟: {latency:.2f}ms")
            
            if "cache_hit" in result and result["cache_hit"]:
                print("缓存命中")
            elif "escalate_to_human" in result and result["escalate_to_human"]:
                print("转人工")
            
            if "l0_decision" in result:
                l0_decision = result["l0_decision"]
                print(f"L0 决策: {l0_decision['route']}, 意图: {l0_decision['intent']}")
                print(f"原因: {l0_decision['reason']}")
        except Exception as e:
            print(f"智能执行失败: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(console_session())
