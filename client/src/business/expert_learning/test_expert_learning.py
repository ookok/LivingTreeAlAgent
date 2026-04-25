# -*- coding: utf-8 -*-
"""
专家指导学习系统测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from expert_learning import (
    ExpertGuidedLearningSystem,
    create_expert_learning_system,
    LearningPhase,
    CorrectionLevel,
)


def test_system_creation():
    """Test system creation"""
    print("\n=== Test 1: System Creation ===")

    system = create_expert_learning_system({
        "ollama_url": "http://localhost:11434",
        "expert_model": "qwen3.5:9b",
    })

    print(f"[OK] System created")
    print(f"   - Cache: {'Enabled' if system.cache else 'Disabled'}")
    print(f"   - Knowledge Graph: {'Enabled' if system.knowledge_graph else 'Disabled'}")
    print(f"   - Distiller: {'Enabled' if system.distiller else 'Disabled'}")
    return system


def test_response_comparator():
    """Test response comparator"""
    print("\n=== Test 2: Response Comparator ===")

    from expert_learning import ResponseComparator

    comparator = ResponseComparator()

    # 测试用例
    test_cases = [
        {
            "query": "Python 怎么定义函数?",
            "local": "用 def 关键词定义函数。",
            "expert": "在 Python 中，使用 def 关键字来定义函数，语法为：\ndef 函数名(参数):\n    函数体\n    return 返回值\n\n示例：\ndef add(a, b):\n    return a + b",
            "expected_correction": True,
        },
        {
            "query": "你好",
            "local": "你好！有什么可以帮助你的吗？",
            "expert": "你好呀！很高兴见到你！有什么想问的吗？",
            "expected_correction": False,
        },
    ]

    for i, case in enumerate(test_cases):
        result = comparator.compare(
            case["query"],
            case["local"],
            case["expert"]
        )
        print(f"\n  测试 {i+1}: {case['query'][:20]}...")
        print(f"    需要纠正: {result['needs_correction']} (期望: {case['expected_correction']})")
        print(f"    纠正层级: {result['correction_level'].name}")
        print(f"    相似度: {result['similarity']:.2%}")


def test_learning_phases():
    """Test learning phase enum"""
    print("\n=== Test 3: Learning Phases ===")

    phases = [
        LearningPhase.CACHE_HIT,
        LearningPhase.LOCAL_ONLY,
        LearningPhase.LOCAL_THEN_EXPERT,
        LearningPhase.EXPERT_GUIDED,
        LearningPhase.CONSOLIDATING,
    ]

    for phase in phases:
        print(f"  {phase.value}: {phase.name}")


def test_stats():
    """Test statistics"""
    print("\n=== Test 4: Statistics ===")

    system = create_expert_learning_system()
    stats = system.get_stats()

    print(f"  总查询数: {stats['total_queries']}")
    print(f"  缓存命中: {stats['cache_hits']}")
    print(f"  本地生成: {stats['local_only']}")
    print(f"  专家指导: {stats['expert_guided']}")
    print(f"  纠正次数: {stats['corrections']}")


def main():
    print("=" * 60)
    print("Expert-Guided Learning System Test")
    print("=" * 60)

    # 测试系统创建
    system = test_system_creation()

    # 测试响应对比器
    test_response_comparator()

    # 测试学习阶段
    test_learning_phases()

    # 测试统计
    test_stats()

    print("\n" + "=" * 60)
    print("[OK] All tests completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
