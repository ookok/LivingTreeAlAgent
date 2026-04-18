"""
演示程序：智能AI缓存与四级模型调度系统
"""

import asyncio
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tier_model import (
    CacheManager, Tier1Cache, Tier2Lightweight, Tier3Standard, Tier4Enhanced,
    TierDispatcher, IntelligentRouter, PerformanceMonitor,
    RouteDecision, QueryComplexity
)


class DemoScheduler:
    """演示调度器"""
    
    def __init__(self):
        self.cache_manager = CacheManager()
        self.tier1 = Tier1Cache()
        self.tier2 = Tier2Lightweight()
        self.tier3 = Tier3Standard()
        self.tier4 = Tier4Enhanced()
        self.router = IntelligentRouter()
        self.monitor = PerformanceMonitor()
        self.dispatcher = TierDispatcher(self.cache_manager)
        self.monitor.start()
    
    async def process_query(self, query: str, context: str = None):
        """处理查询"""
        print(f"\n{'='*60}")
        print(f"Query: {query[:80]}{'...' if len(query) > 80 else ''}")
        
        route_result = self.router.route(query)
        print(f"\nRoute: {route_result.decision.value} (confidence: {route_result.confidence:.2%})")
        
        cache_result = self.cache_manager.get(query, context)
        if cache_result:
            print(f"Cache hit: {cache_result['tier']}")
            self.monitor.record(cache_result['tier'], 0, True)
            return cache_result['response']
        
        start_time = time.perf_counter()
        
        if route_result.decision == RouteDecision.L1_CACHE:
            result = "Cached result"
        elif route_result.decision == RouteDecision.L2_LIGHTWEIGHT:
            r = await self.tier2.process(query, context)
            result = r.response
        elif route_result.decision == RouteDecision.L3_STANDARD:
            r = await self.tier3.process(query, context)
            result = r.response
        else:
            r = await self.tier4.process(query, context)
            result = r.response
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        if result:
            self.cache_manager.set(query, result, context)
        
        self.monitor.record(route_result.decision.value, latency_ms, False)
        
        print(f"Latency: {latency_ms:.1f}ms")
        return result
    
    def show_stats(self):
        """显示统计"""
        print(f"\n{'='*60}")
        print("Statistics")
        print(f"{'='*60}")
        
        cache_stats = self.cache_manager.get_combined_stats()
        print(f"Combined hit rate: {cache_stats['combined_hit_rate']:.2%}")
        print(f"L1: {cache_stats['L1_memory']['size']}/{cache_stats['L1_memory']['max_size']}")
        print(f"L2: {cache_stats['L2_local']['size']}/{cache_stats['L2_local']['max_size']}")
        
        status = self.monitor.get_status()
        print(f"\nAvg latency: {status['metrics']['latency_avg']:.1f}ms")
        print(f"P95 latency: {status['metrics']['latency_p95']:.1f}ms")


async def run_demo():
    """运行演示"""
    print("\n" + "="*60)
    print("Intelligent Cache & Four-Tier Model Scheduling System Demo")
    print("="*60)
    
    scheduler = DemoScheduler()
    
    test_queries = [
        "Hello, how are you?",
        "Hello, how are you?",
        "What is Python?",
        "Translate to English: Hello World",
        "Analyze the trends in artificial intelligence",
        "Write a Python quicksort implementation",
        "Deep analysis: opportunities and challenges of LLM in enterprise",
    ]
    
    for i, query in enumerate(test_queries):
        print(f"\n[{i+1}/{len(test_queries)}]")
        await scheduler.process_query(query)
        await asyncio.sleep(0.1)
    
    scheduler.show_stats()
    await scheduler.monitor.stop()
    
    print(f"\n{'='*60}")
    print("Demo Complete")
    print("="*60)


async def main():
    await run_demo()


if __name__ == "__main__":
    asyncio.run(main())
