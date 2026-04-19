#!/usr/bin/env python3
"""
测试系统深度搜索功能
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
_root = Path(__file__).parent
sys.path.insert(0, str(_root))

from core.fusion_rag.fusion_engine import FusionEngine


def test_deep_search():
    """测试深度搜索功能"""
    print("=== 测试深度搜索功能 ===")

    # 初始化融合引擎
    fusion_engine = FusionEngine(top_k=5)

    # 模拟各层检索结果
    layer_results = {
        "exact_cache": [
            {"content": "Python 是一种高级编程语言，易学易用", "score": 0.95},
            {"content": "Python 支持面向对象编程", "score": 0.85}
        ],
        "session_cache": [
            {"content": "Python 有丰富的标准库", "score": 0.90},
            {"content": "Python 适用于数据分析", "score": 0.80}
        ],
        "knowledge_base": [
            {"content": "Python 是一种解释型语言", "score": 0.85},
            {"content": "Python 由 Guido van Rossum 创造", "score": 0.75}
        ],
        "database": [
            {"content": "Python 支持多种编程范式", "score": 0.80},
            {"content": "Python 在人工智能领域广泛应用", "score": 0.92}
        ]
    }

    print("\n1. 测试加权求和融合")
    weighted_results = fusion_engine.fuse(layer_results, algorithm="weighted_sum")
    for i, result in enumerate(weighted_results, 1):
        print(f"  {i}. {result['content']} (分数: {result['score']:.3f}, 来源: {result['source']})")

    print("\n2. 测试 RRF 融合")
    rrf_results = fusion_engine.fuse(layer_results, algorithm="rrf")
    for i, result in enumerate(rrf_results, 1):
        print(f"  {i}. {result['content']} (RRF分数: {result['rrf_score']:.3f}, 来源: {result['source']})")

    print("\n3. 测试混合融合")
    hybrid_results = fusion_engine.fuse(layer_results, algorithm="hybrid")
    for i, result in enumerate(hybrid_results, 1):
        print(f"  {i}. {result['content']} (融合分数: {result['fused_score']:.3f}, 来源: {result['source']})")

    print("\n4. 测试答案生成")
    query = "Python 是什么"
    answer = fusion_engine.generate_answer(query, hybrid_results)
    print(f"  查询: {query}")
    print(f"  答案: {answer['answer']}")
    print(f"  置信度: {answer['confidence']:.3f}")
    print(f"  来源: {len(answer['sources'])} 个")

    print("\n5. 测试统计信息")
    stats = fusion_engine.get_stats()
    print(f"  融合次数: {stats['fusion_count']}")
    print(f"  平均结果数: {stats['avg_results_count']:.1f}")
    print(f"  可用算法: {', '.join(stats['available_algorithms'])}")
    print(f"  默认算法: {stats['default_algorithm']}")

    print("\n深度搜索功能测试完成！")


if __name__ == "__main__":
    test_deep_search()