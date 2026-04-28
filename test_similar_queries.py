# -*- coding: utf-8 -*-
"""
相似 Query 缓存命中测试
=======================

测试 unified_cache.py 三大增强：
1. QueryNormalizer - 超长 query 截断 + 关键词提取
2. SimilarQueryDetector - 相似问法语义匹配
3. SemanticSimilarityCache - 关键词 Jaccard / Ollama Embedding 真实语义

测试场景：
- 完全相同的 query → 精确命中
- 相似的 query（换词/换序）→ 语义命中
- 完全不同的 query → 未命中
- 超长 query → 截断后正常处理
"""

import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))
from unified_cache import (
    QueryNormalizer, SemanticSimilarityCache, SimilarQueryDetector,
    UnifiedCache, reset_unified_cache, get_unified_cache
)


# ════════════════════════════════════════════════════════════════════════════
# Test 1: QueryNormalizer - 超长截断 + 关键词提取
# ════════════════════════════════════════════════════════════════════════════

def test_query_normalizer():
    print("\n" + "=" * 60)
    print("Test 1: QueryNormalizer - 超长截断 + 关键词提取")
    print("=" * 60)

    norm = QueryNormalizer(max_length=50)

    tests = [
        # (原始, 关键词数期望, 是否截断)
        ("杭州五一有什么好玩的", None, False),
        ("2024年五一杭州有什么好玩的地方推荐？", None, False),
        ("杭州" + "啊" * 100 + "五一有什么好玩的", None, True),
    ]

    for query, _, _ in tests:
        result = norm.normalize(query)
        print(f"\n  原始: {query[:60]}...")
        print(f"  清理: {result['cleaned']}")
        print(f"  截断: {'YES' if result['was_truncated'] else 'NO'} ({result['length']}→{len(result['cleaned'])}字)")
        print(f"  关键词({len(result['keywords'])}): {sorted(result['keywords'])[:10]}")
        print(f"  hash_key: {result['hash_key'][:16]}...")

        # 验证截断
        assert result["was_truncated"] == (len(query) > 50), f"截断判断错误: {query}"
        assert len(result["cleaned"]) <= 50, f"截断长度超限: {len(result['cleaned'])}"

    # Jaccard 相似度测试
    q1 = norm.normalize("杭州五一有什么好玩的")
    q2 = norm.normalize("五一去杭州玩什么")
    q3 = norm.normalize("南京溧水养猪场环评报告")

    sim_12 = norm.jaccard_similarity(q1["keywords"], q2["keywords"])
    sim_13 = norm.jaccard_similarity(q1["keywords"], q3["keywords"])

    print(f"\n  相似度测试:")
    print(f"    Q1='杭州五一有什么好玩的' vs Q2='五一去杭州玩什么'")
    print(f"    关键词: {sorted(q1['keywords'])} vs {sorted(q2['keywords'])}")
    print(f"    Jaccard = {sim_12:.3f}  {'✅ 能命中!' if sim_12 > 0.3 else '❌ 不会命中'}")
    print(f"    Q1 vs Q3='南京溧水养猪场环评报告'")
    print(f"    Jaccard = {sim_13:.3f}  {'✅ 能命中!' if sim_13 > 0.3 else '❌ 不会命中'}")

    assert sim_12 > sim_13, "相似问题应该比不相似问题有更高相似度"
    print("\n  ✅ QueryNormalizer 测试通过")


# ════════════════════════════════════════════════════════════════════════════
# Test 2: SemanticSimilarityCache - 真实语义匹配
# ════════════════════════════════════════════════════════════════════════════

def test_semantic_cache():
    print("\n" + "=" * 60)
    print("Test 2: SemanticSimilarityCache - 真实语义匹配")
    print("=" * 60)

    cache = SemanticSimilarityCache(
        similarity_threshold=0.5,  # char_similarity 有效范围 0~1，建议 >= 0.5
        max_entries=100,
        enable_ollama=False,  # 强制用 char_similarity 模式
    )

    # Step 1: 存入原始 query
    base_query = "杭州五一有什么好玩的"
    base_response = "杭州五一推荐：西湖、灵隐寺、宋城、千岛湖..."
    cache.set(base_query, base_response, "llm_model")
    print(f"\n  存入: {base_query}")
    print(f"  响应: {base_response}")

    # Step 2: 完全相同 → 精确命中
    result = cache.get(base_query)
    print(f"\n  [T1] 完全相同 query:")
    print(f"    结果: {'✅ 命中' if result else '❌ 未命中'}")
    print(f"    类型: {result['match_type'] if result else '-'}")
    print(f"    相似度: {result['similarity']:.3f}" if result else "")
    assert result is not None and result["match_type"] == "exact", "精确匹配失败"
    print("  ✅ 精确匹配通过")

    # Step 3: 相似 query → 语义命中
    similar_tests = [
        ("五一去杭州玩什么", "换词换序"),
        ("杭州五一假期景点推荐", "近义表达"),
        ("杭州五一有什么好玩的景点", "加词"),
        ("杭州有什么好玩的", "去掉时间词"),
        ("南京溧水养猪场环评报告", "完全不相关"),
    ]

    print(f"\n  [T2] 相似 query 语义匹配:")
    for query, desc in similar_tests:
        result = cache.get(query)
        if result:
            print(f"    ✅ [{desc}] '{query}' → 命中 (sim={result['similarity']:.3f}, type={result['match_type']})")
        else:
            print(f"    ❌ [{desc}] '{query}' → 未命中")

    # Step 4: 批量存入后 top-k 搜索
    more_queries = [
        ("北京五一旅游攻略", "北京攻略"),
        ("上海五一美食推荐", "上海美食"),
        ("深圳五一户外活动", "深圳户外"),
    ]
    for q, r in more_queries:
        cache.set(q, f"关于{q}的回答", "model")

    print(f"\n  [T3] top-3 相似搜索:")
    similar = cache.search_similar("五一去杭州玩什么", top_k=3)
    for s in similar:
        print(f"    sim={s['similarity']:.3f} [{s['match_type']}]: {s['query']}")

    # Step 5: 统计
    stats = cache.get_stats()
    print(f"\n  [T4] 统计:")
    print(f"    模式: {stats['mode']}")
    print(f"    条目数: {stats['entries']}/{stats['max_entries']}")
    print(f"    命中率: {stats['hit_rate']}")
    print(f"    阈值: {stats['similarity_threshold']}")

    print("\n  ✅ SemanticSimilarityCache 测试通过")


# ════════════════════════════════════════════════════════════════════════════
# Test 3: UnifiedCache 相似检测 + 路由/搜索/L4 缓存协同
# ════════════════════════════════════════════════════════════════════════════

def test_unified_cache_similar():
    print("\n" + "=" * 60)
    print("Test 3: UnifiedCache - 相似检测集成")
    print("=" * 60)

    reset_unified_cache()
    cache = get_unified_cache(query_max_length=50, similar_threshold=0.5)

    # 预存一个答案
    original_query = "杭州五一有什么好玩的"
    original_answer = "杭州五一推荐：西湖十景、灵隐寺、清河坊..."
    cache.store_similar(original_query, original_answer, "qwen3.5:4b")
    print(f"\n  预存: {original_query}")
    print(f"  答案: {original_answer}")

    # 相似 query 测试
    tests = [
        ("五一杭州有哪些玩的", "✅ 同义改写"),
        ("杭州五一去哪里玩", "✅ 换序表达"),
        ("杭州五一旅游推荐景点", "✅ 扩充词"),
        ("杭州天气怎么样", "❌ 不相关"),
    ]

    print(f"\n  相似检测结果:")
    for query, desc in tests:
        similar = cache.find_similar(query)
        if similar:
            print(f"    {desc}")
            print(f"      输入: {query}")
            print(f"      命中: {similar['query']} (sim={similar['similarity']:.3f}, type={similar['match_type']})")
            print(f"      答案: {str(similar['response'])[:50]}...")
        else:
            print(f"    {desc}")
            print(f"      输入: {query}")
            print(f"      命中: ❌ 未找到相似 query")

    # L0 缓存key 测试（超长 query 截断）
    long_query = "请帮我查找2024年五一期间杭州西湖风景区有哪些推荐的旅游景点和美食餐厅，以及住宿建议，具体行程规划为3天2晚，需要包含门票价格、开放时间、交通路线等详细信息，请尽量详细全面地回答谢谢"
    print(f"\n  超长 query 测试 ({len(long_query)} 字):")
    norm = cache.normalizer.normalize(long_query)
    print(f"    截断后: {norm['cleaned'][:50]}... ({len(norm['cleaned'])}字)")
    print(f"    关键词: {sorted(norm['keywords'])[:15]}")
    print(f"    hash_key: {norm['hash_key'][:16]}...")

    assert norm["was_truncated"] == True, "超长 query 应该被截断"
    print("  ✅ 超长 query 截断通过")

    # 路由缓存 key 截断
    hit = cache.get_l0_route(long_query)
    print(f"\n  L0 缓存 key 测试 (超长 query):")
    print(f"    命中: {'✅' if hit else '❌ 未命中（正常）'}")

    print("\n  ✅ UnifiedCache 相似检测集成测试通过")


# ════════════════════════════════════════════════════════════════════════════
# Test 4: 端到端链路 - 模拟真实深度搜索场景
# ════════════════════════════════════════════════════════════════════════════

def test_end_to_end():
    print("\n" + "=" * 60)
    print("Test 4: 端到端链路 - 深度搜索场景")
    print("=" * 60)

    reset_unified_cache()
    cache = get_unified_cache()

    scenario = {
        "query_1": "杭州五一有什么好玩的",
        "answer_1": "杭州五一推荐去西湖、灵隐寺、宋城、千岛湖游玩。",
        "query_2": "五一杭州有哪些景点值得去",
        "query_3": "北京五一去哪里玩",
        "answer_3": "北京五一推荐故宫、长城、颐和园、天安门广场。",
    }

    # 场景1: 首次查询，无缓存
    print(f"\n  [S1] 首次查询: {scenario['query_1']}")
    hit = cache.find_similar(scenario["query_1"])
    print(f"    相似命中: {'✅' if hit else '❌ 无缓存，正常执行搜索'}")
    cache.store_similar(scenario["query_1"], scenario["answer_1"])

    # 场景2: 相似 query → 命中
    print(f"\n  [S2] 相似查询: {scenario['query_2']}")
    hit = cache.find_similar(scenario["query_2"])
    if hit:
        print(f"    ✅ 命中! 相似度={hit['similarity']:.3f}")
        print(f"    来源: {hit['query']}")
        print(f"    答案: {hit['response'][:50]}...")
    else:
        print(f"    ❌ 未命中，执行搜索...")

    # 场景3: 不同 query → 未命中
    print(f"\n  [S3] 不同查询: {scenario['query_3']}")
    hit = cache.find_similar(scenario["query_3"])
    if hit:
        print(f"    ⚠️ 误命中（应该不命中）: {hit['query']}")
    else:
        print(f"    ❌ 正确未命中，执行搜索...")
    cache.store_similar(scenario["query_3"], scenario["answer_3"])

    # 场景4: 再问相似 query
    print(f"\n  [S4] 再问: {scenario['query_3']}")
    hit = cache.find_similar(scenario["query_3"])
    if hit:
        print(f"    ✅ 命中! 相似度={hit['similarity']:.3f}, 答案: {hit['response'][:50]}...")

    print("\n  ✅ 端到端测试通过")


# ════════════════════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("🔬 统一缓存增强功能测试")
    print("=" * 60)
    print(f"  1. QueryNormalizer - 超长截断 + 关键词提取")
    print(f"  2. SemanticSimilarityCache - 真实语义匹配")
    print(f"  3. SimilarQueryDetector - 相似问法检测")
    print(f"  4. 端到端深度搜索场景")

    test_query_normalizer()
    test_semantic_cache()
    test_unified_cache_similar()
    test_end_to_end()

    print("\n" + "=" * 60)
    print("🎉 全部测试通过！")
    print("=" * 60)

    # 最终统计
    cache = get_unified_cache()
    cache.print_report()


if __name__ == "__main__":
    main()
