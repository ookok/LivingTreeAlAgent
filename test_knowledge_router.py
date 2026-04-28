#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库智能路由器测试
验证增强版路由器的完整链路
"""

import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.fusion_rag.knowledge_router import (
    KnowledgeRouter,
    IntentClassifier,
    QueryAnalyzer,
    smart_search,
    QueryIntent,
)


def test_intent_classifier():
    """测试意图分类器"""
    print("\n" + "=" * 60)
    print("[TEST 1] Intent Classifier")
    print("=" * 60)

    classifier = IntentClassifier()

    test_queries = [
        ("什么是微服务架构", QueryIntent.RETRIEVAL),
        ("找一下Ollama的安装文档", QueryIntent.RETRIEVAL),
        ("帮我分析微服务的发展趋势", QueryIntent.GENERATE),
        ("对比一下Spring Cloud和Dubbo", QueryIntent.GENERATE),
        ("打开第3章的Ollama部署指南", QueryIntent.LOCATE),
        ("什么是微服务+怎么部署", QueryIntent.HYBRID),
    ]

    all_passed = True
    for query, expected in test_queries:
        result = classifier.classify(query)
        status = "PASS" if result == expected else "FAIL"
        if result != expected:
            all_passed = False
        print(f"  [{status}] '{query}'")
        print(f"         Expected: {expected.value}, Got: {result.value}")

    print(f"\n  Stats: {classifier.get_stats()}")
    return all_passed


def test_query_analyzer():
    """测试查询分析器"""
    print("\n" + "=" * 60)
    print("[TEST 2] Query Analyzer")
    print("=" * 60)

    analyzer = QueryAnalyzer()

    test_queries = [
        "什么是微服务架构",
        "帮我分析一下Kubernetes和Docker的区别以及优缺点",
        "python def function example",
    ]

    for query in test_queries:
        result = analyzer.analyze(query)
        print(f"\n  Query: '{query}'")
        print(f"    Keywords: {result.keywords}")
        print(f"    Complexity: {result.complexity}")
        print(f"    Length: {result.length}")
        print(f"    Is Chinese: {result.is_chinese}")
        print(f"    Has Code: {result.has_code}")
        print(f"    Recommended: {result.recommended_sources}")

    return True


def test_router_integration():
    """测试路由器集成"""
    print("\n" + "=" * 60)
    print("[TEST 3] Router Integration")
    print("=" * 60)

    # 添加测试文档到知识库
    from core.fusion_rag.knowledge_base import KnowledgeBaseLayer

    kb = KnowledgeBaseLayer()
    kb.add_document({
        "id": "ollama_doc",
        "title": "Ollama Deployment Guide",
        "content": """
Ollama is a local LLM runtime. Install: curl -fsSL https://ollama.com/install.sh | sh
Run: ollama run llama2, ollama list, ollama pull <model>
API: http://localhost:11434/api/generate
GPU: Supports NVIDIA CUDA acceleration.
        """.strip(),
        "type": "md",
        "metadata": {"source": "test"}
    })

    kb.add_document({
        "id": "microservice_doc",
        "title": "Microservice Architecture",
        "content": """
Microservice architecture splits applications into small services.
Each service runs independently and communicates via APIs.
Benefits: scalability, maintainability, technology flexibility.
Challenges: complexity, data consistency, monitoring.
        """.strip(),
        "type": "md",
        "metadata": {"source": "test"}
    })

    print(f"  [KB] Added 2 documents, {kb.get_stats()['chunk_count']} chunks")

    # 初始化路由器
    router = KnowledgeRouter()

    # 测试查询
    test_cases = [
        {
            "query": "什么是微服务",
            "description": "简单检索型查询"
        },
        {
            "query": "帮我分析微服务架构的优缺点",
            "description": "生成型查询"
        },
        {
            "query": "ollama怎么安装",
            "description": "简单事实检索"
        },
    ]

    async def run_tests():
        for tc in test_cases:
            print(f"\n  Query: '{tc['query']}' ({tc['description']})")

            response = await router.route(tc["query"])

            print(f"    Intent: {response.intent.value}")
            print(f"    Analysis: {response.analysis.complexity}")
            print(f"    Sources used: {response.sources_used}")
            print(f"    Results: {len(response.results)}")
            print(f"    Time: {response.total_time_ms:.1f}ms")

            for i, r in enumerate(response.results[:3], 1):
                print(f"    [{i}] [{r.source}] Score: {r.score:.3f}")
                print(f"        {r.title or r.content[:60]}...")

    asyncio.run(run_tests())

    # 打印统计
    stats = router.get_stats()
    print(f"\n  Router Stats: {stats}")

    return True


def test_smart_search():
    """测试便捷搜索接口"""
    print("\n" + "=" * 60)
    print("[TEST 4] Smart Search API")
    print("=" * 60)

    async def run():
        response = await smart_search("微服务架构设计原则")

        print(f"  Query: {response.query}")
        print(f"  Intent: {response.intent.value}")
        print(f"  Complexity: {response.analysis.complexity}")
        print(f"  Time: {response.total_time_ms:.1f}ms")
        print(f"  Results: {len(response.results)}")

        for i, r in enumerate(response.results[:5], 1):
            print(f"    [{i}] {r.source} | Score: {r.score:.3f} | {r.title or r.content[:50]}...")

    asyncio.run(run())
    return True


def benchmark():
    """性能基准测试"""
    print("\n" + "=" * 60)
    print("[BENCHMARK] Performance Test")
    print("=" * 60)

    from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
    import time

    # 添加测试数据
    kb = KnowledgeBaseLayer()
    for i in range(10):
        kb.add_document({
            "id": f"doc_{i}",
            "title": f"Test Document {i}",
            "content": f"This is test document {i} with content about microservices, Kubernetes, and Docker deployment.",
            "type": "md",
            "metadata": {"index": i}
        })

    router = KnowledgeRouter()

    queries = [
        "微服务架构",
        "Kubernetes deployment",
        "Docker container",
        "什么是微服务",
        "怎么部署应用",
    ]

    times = []

    async def run():
        for query in queries:
            t0 = time.time()
            response = await router.route(query)
            elapsed = (time.time() - t0) * 1000
            times.append(elapsed)
            print(f"  '{query}' -> {elapsed:.1f}ms ({len(response.results)} results)")

    asyncio.run(run())

    avg = sum(times) / len(times)
    print(f"\n  Average latency: {avg:.1f}ms")
    print(f"  Min: {min(times):.1f}ms, Max: {max(times):.1f}ms")


def main():
    print("=" * 60)
    print("KNOWLEDGE ROUTER TEST SUITE")
    print("=" * 60)

    results = []

    # Test 1: Intent Classifier
    results.append(("Intent Classifier", test_intent_classifier()))

    # Test 2: Query Analyzer
    results.append(("Query Analyzer", test_query_analyzer()))

    # Test 3: Router Integration
    results.append(("Router Integration", test_router_integration()))

    # Test 4: Smart Search API
    results.append(("Smart Search API", test_smart_search()))

    # Benchmark
    benchmark()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    all_passed = all(r[1] for r in results)
    print(f"\n  Overall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")


if __name__ == "__main__":
    main()
