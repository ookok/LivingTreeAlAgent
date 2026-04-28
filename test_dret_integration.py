"""
DRET 系统完整测试 - 集成知识库和深度搜索
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.skill_evolution.dret_system import (
    create_dret_system,
    GapDetector,
    ConflictFinder,
    MultiDebater,
    RecursiveLearner,
    KnowledgeGraphBuilder,
    RecursionLevel,
    GapType,
    ConflictLevel,
)

# 测试文档
SAMPLE_DOC = """
OpenCode AI 助手完整指南

## 安装步骤

1. 安装 Node.js 环境（必需）
2. 安装 OpenCode: npm install -g opencode-ai
3. 验证安装: opencode --version
4. 配置 oh-my-opencode: bunx oh-my-opencode install

## 核心功能

- **ultrawork 模式**: 全自动执行任务
- **search 模式**: 智能搜索和调研
- **多 Agent 协同**: 支持多个 AI 协作
- **Tab 切换**: plan(规划)/build(编码) 模式

## 使用技巧

- 使用 /init 初始化项目配置
- 使用 /add 文件名 添加文件到上下文
- 使用 ultrawork 可以完全自动化复杂任务

## 高级特性

支持 Python、JavaScript、Bash 多种代码执行环境。
内置代码解释器可以实时执行和验证代码。

## 与传统 Agent 对比

OpenCode 声称比传统 Agent 效率更高，
但实际测试显示效率提升因场景而异。
"""


def test_gap_detector():
    """测试空白检测"""
    print("\n" + "="*60)
    print("  Test 1: Gap Detector")
    print("="*60)

    detector = GapDetector()
    gaps = detector.detect_gaps(SAMPLE_DOC)

    print(f"\nDetected {len(gaps)} gaps:")
    for gap in gaps:
        print(f"  [{gap.gap_id}] {gap.gap_type.value:12s} - {gap.description}")

    return gaps


def test_conflict_finder():
    """测试矛盾检测"""
    print("\n" + "="*60)
    print("  Test 2: Conflict Finder")
    print("="*60)

    finder = ConflictFinder()
    conflicts = finder.find_conflicts(SAMPLE_DOC)

    print(f"\nFound {len(conflicts)} conflicts:")
    for conflict in conflicts:
        print(f"  [{conflict.conflict_id}] {conflict.level.value:8s}")
        print(f"    A: {conflict.statement_a}")
        print(f"    B: {conflict.statement_b}")
        if conflict.evidence_a:
            print(f"    Evidence A: {conflict.evidence_a[0]}")

    return conflicts


def test_multi_debater():
    """测试多专家辩论"""
    print("\n" + "="*60)
    print("  Test 3: Multi-Expert Debate")
    print("="*60)

    debater = MultiDebater()
    result = debater.debate(
        topic="OpenCode 的 ultrawork 模式是否优于传统 Agent?",
        context="用户关心自动化程度和执行效率"
    )

    print(f"\nTopic: {result.topic}")
    print(f"\nPerspectives:")
    for role, perspective in result.perspectives.items():
        print(f"  [{role.value:12s}] {perspective[:60]}...")

    print(f"\nConsensus: {result.consensus}")
    print(f"Confidence: {result.confidence:.0%}")
    print(f"Key Points: {result.key_points}")

    return result


def test_knowledge_graph():
    """测试知识图谱构建"""
    print("\n" + "="*60)
    print("  Test 4: Knowledge Graph Builder")
    print("="*60)

    builder = KnowledgeGraphBuilder()
    graph = builder.build_from_text(SAMPLE_DOC)

    print(f"\nKnowledge Graph:")
    print(f"  Nodes: {len(graph['nodes'])}")
    print(f"  Edges: {len(graph['edges'])}")

    print("\nEntities:")
    for node in graph['nodes'][:5]:
        print(f"  - {node['label']}")

    print("\nRelations:")
    for edge in graph['edges'][:5]:
        print(f"  - {edge['from']} --[{edge['type']}]--> {edge['to']}")

    return graph


def test_recursive_learner():
    """测试递归学习器"""
    print("\n" + "="*60)
    print("  Test 5: Recursive Learner (Full Integration)")
    print("="*60)

    # 创建系统（带知识库 mock）
    class MockKB:
        def search(self, query, top_k=3):
            # 模拟知识库搜索
            results = [
                {"content": f"知识库中关于 '{query}' 的说明...", "source": "mock_kb"},
            ]
            return results

    class MockDeepSearch:
        def search(self, query):
            # 模拟深度搜索
            results = [
                {"content": f"深度搜索发现: {query}", "url": "https://example.com"},
            ]
            return results

    learner = create_dret_system(
        max_recursion_depth=2,
        kb_layer=MockKB(),
        deep_search=MockDeepSearch()
    )

    report = learner.learn_from_document(SAMPLE_DOC, doc_id="opencode_guide_full")

    print(f"\nLearning Report:")
    print(f"  Gaps Found: {report.gaps_found}")
    print(f"  Gaps Filled: {report.gaps_filled}")
    print(f"  Conflicts Found: {report.conflicts_found}")
    print(f"  Conflicts Resolved: {report.conflicts_resolved}")
    print(f"  Debate Rounds: {report.debate_rounds}")
    print(f"  KG Nodes: {report.knowledge_graph_nodes}")
    print(f"  KG Edges: {report.knowledge_graph_edges}")
    print(f"  Total Time: {report.total_time:.2f}s")
    print(f"  Recursion Levels: {report.recursion_levels_used}")

    return report


def test_recursion_levels():
    """测试不同递归层级"""
    print("\n" + "="*60)
    print("  Test 6: Recursion Levels Comparison")
    print("="*60)

    class MockKB:
        def search(self, query, top_k=3):
            return [{"content": f"KB: {query}", "source": "mock"}]

    class MockDeepSearch:
        def search(self, query):
            return [{"content": f"DS: {query}", "url": "mock"}]

    print("\n| Depth | Gaps Found | Gaps Filled | Time |")
    print("|-------|------------|-------------|------|")

    for depth in [1, 2, 3]:
        learner = create_dret_system(
            max_recursion_depth=depth,
            kb_layer=MockKB(),
            deep_search=MockDeepSearch()
        )
        report = learner.learn_from_document(SAMPLE_DOC, doc_id=f"depth_{depth}")

        print(f"|   {depth}   |     {report.gaps_found:2d}     |     {report.gaps_filled:2d}      | {report.total_time:.2f}s |")


def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║   Document-Driven Recursive Expert Training (DRET) Test   ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    test_gap_detector()
    test_conflict_finder()
    test_multi_debater()
    test_knowledge_graph()
    test_recursive_learner()
    test_recursion_levels()

    print("\n" + "="*60)
    print("  All Tests Completed!")
    print("="*60)


if __name__ == "__main__":
    main()
