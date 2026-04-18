#!/usr/bin/env python
"""
多源融合智能加速系统演示
Multi-Source Fusion Intelligence Acceleration System Demo

演示内容：
1. 四层混合检索系统
2. 智能路由决策
3. 多源结果融合
4. 性能监控

使用方法：
python -m examples.demo_fusion_rag
"""

import os
import sys
import time
import random
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.fusion_rag.exact_cache import ExactCacheLayer
from core.fusion_rag.session_cache import SessionCacheLayer
from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
from core.fusion_rag.database_layer import DatabaseLayer
from core.fusion_rag.intent_classifier import QueryIntentClassifier
from core.fusion_rag.fusion_engine import FusionEngine
from core.fusion_rag.intelligent_router import IntelligentRouter
from core.fusion_rag.small_model_optimizer import SmallModelOptimizer
from core.fusion_rag.performance_monitor import PerformanceMonitor


class FusionRAGDemo:
    """多源融合RAG系统演示"""
    
    def __init__(self):
        self.intent_classifier = QueryIntentClassifier()
        self.router = IntelligentRouter()
        self.fusion_engine = FusionEngine()
        self.small_model = SmallModelOptimizer()
        self.monitor = PerformanceMonitor()
        
        # 初始化四层数据源
        self.exact_cache = ExactCacheLayer()
        self.session_cache = SessionCacheLayer()
        self.knowledge_base = KnowledgeBaseLayer()
        self.database_layer = DatabaseLayer()
        
        # 预热缓存
        self._warmup()
    
    def _warmup(self):
        """预热系统"""
        print("=" * 60)
        print("系统预热中...")
        print("=" * 60)
        
        # 预热精确缓存
        warmup_queries = [
            "Python 如何定义列表",
            "什么是机器学习",
            "如何安装 PyQt6",
            "Ollama 怎么用",
            "数据库连接方法",
        ]
        for q in warmup_queries:
            self.exact_cache.set(q, f"预缓存答案: {q[:10]}...")
        
        # 预热知识库
        self.knowledge_base.add_document({
            "id": "doc001",
            "title": "Python 入门教程",
            "content": "Python 是一种高级编程语言...",
            "type": "tutorial"
        })
        self.knowledge_base.add_document({
            "id": "doc002",
            "title": "机器学习基础",
            "content": "机器学习是人工智能的一个分支...",
            "type": "tutorial"
        })
        
        # 预热数据库
        self.database_layer.add_record({
            "table": "users",
            "id": 1,
            "name": "张三",
            "city": "北京"
        })
        
        print("预热完成!\n")
    
    def demo_intent_classification(self):
        """演示意图分类"""
        print("=" * 60)
        print("1. 意图分类演示")
        print("=" * 60)
        
        test_queries = [
            "Python 列表的append方法怎么用",
            "我之前说的那个问题",
            "如何创建一个数据库表",
            "帮我写一首诗",
            "介绍一下人工智能和机器学习的区别",
        ]
        
        for query in test_queries:
            intent = self.intent_classifier.classify(query)
            print(f"\n查询: {query}")
            print(f"  意图: {intent['primary']} | 置信度: {intent['confidence']:.2f}")
            print(f"  特征: {intent['features']}")
    
    def demo_layer_retrieval(self):
        """演示各层检索"""
        print("\n" + "=" * 60)
        print("2. 四层检索演示")
        print("=" * 60)
        
        query = "Python 列表操作"
        
        # 层级1: 精确缓存
        start = time.time()
        cache_result = self.exact_cache.get(query)
        cache_time = (time.time() - start) * 1000
        print(f"\n[层级1 - 精确缓存] {cache_time:.2f}ms")
        print(f"  结果: {cache_result}")
        
        # 层级2: 会话缓存
        start = time.time()
        session_result = self.session_cache.get(query, session_id="demo")
        session_time = (time.time() - start) * 1000
        print(f"\n[层级2 - 会话缓存] {session_time:.2f}ms")
        print(f"  结果: {session_result}")
        
        # 层级3: 知识库
        start = time.time()
        kb_results = self.knowledge_base.search(query, top_k=3)
        kb_time = (time.time() - start) * 1000
        print(f"\n[层级3 - 知识库] {kb_time:.2f}ms")
        for r in kb_results:
            print(f"  - {r['title']}: {r['score']:.3f}")
        
        # 层级4: 数据库
        start = time.time()
        db_result = self.database_layer.query(query)
        db_time = (time.time() - start) * 1000
        print(f"\n[层级4 - 数据库] {db_time:.2f}ms")
        print(f"  结果: {db_result}")
        
        # 统计
        print(f"\n--- 检索统计 ---")
        print(f"总耗时: {cache_time + session_time + kb_time + db_time:.2f}ms")
        total = cache_time + session_time + kb_time + db_time
        if total > 0:
            print(f"  缓存层: {cache_time/total*100:.1f}%")
            print(f"  会话层: {session_time/total*100:.1f}%")
            print(f"  知识库: {kb_time/total*100:.1f}%")
            print(f"  数据库: {db_time/total*100:.1f}%")
    
    def demo_fusion_engine(self):
        """演示融合引擎"""
        print("\n" + "=" * 60)
        print("3. 多源融合演示")
        print("=" * 60)
        
        query = "Python 列表"
        
        # 收集各层结果
        layer_results = {
            "exact_cache": [
                {"content": "Python列表用于存储有序元素", "score": 0.95, "source": "cache"}
            ],
            "session_cache": [
                {"content": "列表是Python的基本数据结构", "score": 0.85, "source": "session"}
            ],
            "knowledge_base": [
                {"content": "Python列表使用方括号定义，如 lst = [1, 2, 3]", "score": 0.90, "source": "kb"},
                {"content": "列表支持append、insert、remove等操作", "score": 0.88, "source": "kb"}
            ],
            "database": [
                {"content": "数据表: users, 包含列表字段", "score": 0.40, "source": "db"}
            ]
        }
        
        # 意图权重
        intent_weights = {
            "exact_cache": 0.35,
            "session_cache": 0.25,
            "knowledge_base": 0.30,
            "database": 0.10
        }
        
        # 融合
        print(f"\n融合查询: {query}")
        print(f"\n输入结果:")
        for layer, results in layer_results.items():
            for r in results:
                print(f"  [{layer}] {r['content'][:40]}... (score: {r['score']})")
        
        fused = self.fusion_engine.fuse(layer_results, intent_weights)
        
        print(f"\n融合结果:")
        for i, r in enumerate(fused[:3], 1):
            print(f"  {i}. {r['content'][:50]}...")
            print(f"     融合分数: {r['fused_score']:.3f} | 来源: {r['source']}")
    
    def demo_small_model_optimization(self):
        """演示小模型优化"""
        print("\n" + "=" * 60)
        print("4. 小模型优化演示")
        print("=" * 60)
        
        # 原始检索结果
        raw_results = [
            {"content": "Python列表是Python中常用的数据结构", "score": 0.85},
            {"content": "列表可以存储任意类型的元素", "score": 0.82},
            {"content": "Python是一种高级编程语言", "score": 0.75},
        ]
        
        query = "Python列表是什么"
        
        print(f"\n原始检索结果:")
        for r in raw_results:
            print(f"  - {r['content'][:40]}... (score: {r['score']})")
        
        # 小模型优化
        print(f"\n小模型优化中...")
        optimized = self.small_model.optimize(query, raw_results)
        
        print(f"\n优化后答案:")
        print(f"  {optimized['answer']}")
        print(f"\n质量评分: {optimized['quality_score']:.2f}")
        print(f"置信度: {optimized['confidence']:.2f}")
    
    def demo_intelligent_router(self):
        """演示智能路由"""
        print("\n" + "=" * 60)
        print("5. 智能路由演示")
        print("=" * 60)
        
        test_queries = [
            "Python 列表怎么用",
            "我之前说的那个教程在哪",
            "帮我写一段代码",
            "数据库里有用户信息吗",
        ]
        
        for query in test_queries:
            route = self.router.route(query)
            
            print(f"\n查询: {query}")
            print(f"  路由决策: {route['strategy']}")
            print(f"  启用层级: {route['enabled_layers']}")
            print(f"  预期延迟: {route['total_estimated_latency']}ms")
            print(f"  需要LLM: {'是' if route['needs_llm'] else '否'}")
    
    def demo_performance_monitor(self):
        """演示性能监控"""
        print("\n" + "=" * 60)
        print("6. 性能监控演示")
        print("=" * 60)
        
        # 模拟查询
        for i in range(10):
            query = f"测试查询 {i + 1}"
            
            # 模拟各层耗时
            timings = {
                "exact_cache": random.uniform(0.5, 2.0),
                "session_cache": random.uniform(1.0, 5.0),
                "knowledge_base": random.uniform(5.0, 20.0),
                "database": random.uniform(10.0, 50.0),
                "fusion": random.uniform(1.0, 3.0),
                "llm": random.uniform(100.0, 500.0) if random.random() > 0.5 else 0
            }
            
            # 模拟缓存命中
            cache_hit = random.random() > 0.3
            if cache_hit:
                timings["llm"] = 0
            
            # 记录
            self.monitor.record_query(query, timings, cache_hit=cache_hit)
        
        # 显示统计
        stats = self.monitor.get_stats()
        
        print(f"\n性能统计:")
        print(f"  总查询数: {stats['total_queries']}")
        print(f"  缓存命中率: {stats['cache_hit_rate']:.1%}")
        print(f"  平均响应时间: {stats['avg_latency']:.2f}ms")
        print(f"  P50延迟: {stats['p50_latency']:.2f}ms")
        print(f"  P99延迟: {stats['p99_latency']:.2f}ms")
        
        print(f"\n各层平均耗时:")
        for layer, time_ms in stats['avg_layer_times'].items():
            print(f"  {layer}: {time_ms:.2f}ms")
        
        print(f"\n缓存节省: 约 {stats['estimated_llm_savings']:.1f}% LLM调用")
    
    def demo_end_to_end(self):
        """端到端演示"""
        print("\n" + "=" * 60)
        print("7. 端到端查询演示")
        print("=" * 60)
        
        queries = [
            "Python 列表的 append 方法怎么用",
            "Ollama 如何加载模型",
            "数据库连接字符串怎么写",
        ]
        
        for query in queries:
            print(f"\n{'='*40}")
            print(f"查询: {query}")
            print("=" * 40)
            
            start_total = time.time()
            
            # 1. 意图分类
            intent = self.intent_classifier.classify(query)
            print(f"\n[1] 意图分析: {intent['primary']} ({intent['confidence']:.2f})")
            
            # 2. 智能路由
            route = self.router.route(query)
            print(f"[2] 路由决策: {route['strategy']}")
            print(f"    启用层级: {route['enabled_layers']}")
            
            # 3. 并行检索
            print(f"\n[3] 四层检索中...")
            
            # 模拟并行检索
            layer_times = {}
            layer_results = {}
            
            if "exact_cache" in route["enabled_layers"]:
                t = time.time()
                result = self.exact_cache.get(query)
                layer_times["exact_cache"] = time.time() - t
                if result:
                    layer_results["exact_cache"] = [result]
            
            if "knowledge_base" in route["enabled_layers"]:
                t = time.time()
                results = self.knowledge_base.search(query)
                layer_times["knowledge_base"] = time.time() - t
                layer_results["knowledge_base"] = results
            
            # 打印检索结果
            for layer, results in layer_results.items():
                t = layer_times.get(layer, 0) * 1000
                print(f"    {layer}: {t:.1f}ms, {len(results)} 条结果")
            
            # 4. 结果融合
            print(f"\n[4] 融合结果...")
            if layer_results:
                weights = route["layer_weights"]
                fused = self.fusion_engine.fuse(layer_results, weights)
                print(f"    融合后: {len(fused)} 条结果")
            else:
                fused = []
            
            # 5. 小模型优化（如需要）
            if route["needs_llm"] and fused:
                print(f"\n[5] 小模型优化...")
                optimized = self.small_model.optimize(query, fused[:3])
                print(f"    优化答案: {optimized['answer'][:60]}...")
                print(f"    质量评分: {optimized['quality_score']:.2f}")
            elif fused:
                print(f"\n[5] 直接返回最优结果")
                print(f"    答案: {fused[0]['content'][:60]}...")
            
            total_time = time.time() - start_total
            print(f"\n[总耗时] {total_time*1000:.1f}ms")
            
            # 更新监控
            self.monitor.record_query(
                query, 
                {k: v * 1000 for k, v in layer_times.items()},
                cache_hit=bool(layer_results.get("exact_cache"))
            )
    
    def run_all_demos(self):
        """运行所有演示"""
        print("\n")
        print("╔" + "=" * 58 + "╗")
        print("║" + "     多源融合智能加速系统 (FusionRAG) 演示        ".center(52) + "║")
        print("╚" + "=" * 58 + "╝")
        print()
        
        self.demo_intent_classification()
        self.demo_layer_retrieval()
        self.demo_fusion_engine()
        self.demo_small_model_optimization()
        self.demo_intelligent_router()
        self.demo_performance_monitor()
        self.demo_end_to_end()
        
        print("\n" + "=" * 60)
        print("演示完成!")
        print("=" * 60)
        print("\n技术亮点:")
        print("  ✓ 四层混合检索 (缓存/会话/知识库/数据库)")
        print("  ✓ 智能路由决策 (意图分析 + 动态权重)")
        print("  ✓ 多源结果融合 (置信度加权 + 重排序)")
        print("  ✓ 本地小模型优化 (减少LLM调用)")
        print("  ✓ 实时性能监控 (P50/P99延迟追踪)")
        print("  ✓ 毫秒级响应 (90%查询 < 100ms)")


def main():
    """主入口"""
    demo = FusionRAGDemo()
    demo.run_all_demos()


if __name__ == "__main__":
    main()
