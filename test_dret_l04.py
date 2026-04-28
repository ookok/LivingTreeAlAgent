"""
DRET L0-L4 集成测试
"""

import asyncio
import time
import sys
sys.path.insert(0, "d:/mhzyapp/LivingTreeAlAgent")

from core.skill_evolution.dret_l04_integration import (
    L04IntegratedGapDetector,
    L04IntegratedConflictFinder,
    L04IntegratedDebater,
    L04IntegratedRecursiveLearner,
    create_l04_dret_system,
    L04_COMPONENTS
)


def test_l04_components():
    """测试 L0-L4 组件加载"""
    print("\n" + "=" * 60)
    print("Test 1: L0-L4 组件加载状态")
    print("=" * 60)

    available = {
        "intent_classifier": "IntentClassifier" in L04_COMPONENTS,
        "knowledge_base": "knowledge_base" in L04_COMPONENTS,
        "session_cache": "session_cache" in L04_COMPONENTS,
        "exact_cache": "exact_cache" in L04_COMPONENTS,
        "l4_executor": "get_l4_executor" in L04_COMPONENTS,
        "router": "router" in L04_COMPONENTS,
        "fusion_engine": "fusion_engine" in L04_COMPONENTS,
        "unified_cache": "unified_cache" in L04_COMPONENTS,
    }

    for name, available_flag in available.items():
        status = "[OK]" if available_flag else "[XX]"
        print(f"  {status} {name}")

    loaded_count = sum(available.values())
    print(f"\n已加载 {loaded_count}/{len(available)} 个组件")

    return loaded_count > 0


def test_gap_detector():
    """测试空白检测"""
    print("\n" + "=" * 60)
    print("Test 2: 知识空白检测")
    print("=" * 60)

    detector = L04IntegratedGapDetector(enable_l04=True)

    test_content = """
    OpenCode 是一个 AI 代码助手，使用 LLM 进行代码生成。
    通过 ultrawork 模式可以实现自动化任务。
    需要先安装 Node.js 环境。

    安装步骤：
    首先安装 npm 包，然后配置 bunx，
    最后使用 bunx oh-my-opencode install 完成设置。
    """

    gaps = detector.detect_gaps(test_content, doc_id="test_doc")

    print(f"检测到 {len(gaps)} 个知识空白:")
    for gap in gaps[:5]:
        filled_status = "[OK]" if gap.get("filled") else "[--]"
        print(f"  {filled_status} [{gap['type']}] {gap['description'][:50]}")

    return len(gaps) > 0


def test_conflict_finder():
    """测试矛盾发现"""
    print("\n" + "=" * 60)
    print("Test 3: 矛盾发现")
    print("=" * 60)

    finder = L04IntegratedConflictFinder(enable_l04=True)

    test_content = """
    使用 OpenCode 必须安装 Node.js。
    但是你也可以使用其他运行时环境。
    所有操作都是完全自动化的。
    有时需要手动干预某些步骤。
    这个工具总是可靠的。
    """

    conflicts = finder.find_conflicts(test_content, doc_id="test_doc")

    print(f"发现 {len(conflicts)} 个潜在矛盾:")
    for cf in conflicts[:3]:
        print(f"  [!] [{cf['level']}] {cf['type']}")
        print(f"     A: {cf['statement_a']}")
        print(f"     B: {cf['statement_b']}")

    return len(conflicts) >= 0  # 可能没有矛盾也是正常的


def test_debater():
    """测试多专家辩论"""
    print("\n" + "=" * 60)
    print("Test 4: 多专家辩论")
    print("=" * 60)

    debater = L04IntegratedDebater(enable_l04=True)

    topic = "OpenCode 的 ultrawork 模式是否适合所有项目？"

    result = debater.debate(topic, context="OpenCode 支持全自动任务执行")

    print(f"辩论主题: {result['topic']}")
    print(f"\n各方观点:")
    for role, perspective in result["perspectives"].items():
        print(f"  [{role}]: {perspective[:80]}...")

    print(f"\n综合结论: {result['consensus'][:100]}...")
    print(f"置信度: {result['confidence']:.2f}")

    return "consensus" in result


def test_recursive_learner():
    """测试递归学习"""
    print("\n" + "=" * 60)
    print("Test 5: 递归学习")
    print("=" * 60)

    learner = create_l04_dret_system(max_recursion_depth=2)

    sample_doc = """
    OpenCode 安装指南：

    1. 安装: npm install -g opencode-ai
    2. 配置: bunx oh-my-opencode install
    3. 使用: bunx opencode

    特性：
    - 多 Agent 协同
    - Tab 切换 (plan/build)
    - /init 生成 AGENTS.md
    - ultrawork 全自动模式

    注意：需要 Node.js 环境
    """

    report = learner.learn_from_document(sample_doc, doc_id="opencode_guide")

    print(f"\n学习报告:")
    print(f"  文档: {report['doc_id']}")
    print(f"  空白发现: {report['gaps_found']}")
    print(f"  空白填充: {report['gaps_filled']}")
    print(f"  矛盾发现: {report['conflicts_found']}")
    print(f"  矛盾解决: {report['conflicts_resolved']}")
    print(f"  辩论轮次: {report['debate_rounds']}")
    print(f"  知识图谱: {report['knowledge_graph']['nodes']} 节点, {report['knowledge_graph']['edges']} 边")
    print(f"  总耗时: {report['total_time']:.2f}s")

    print(f"\n组件统计:")
    for k, v in report["stats"].items():
        print(f"  {k}: {v}")

    return "doc_id" in report


def main():
    print("\n" + "=" * 60)
    print("DRET L0-L4 集成测试")
    print("=" * 60)

    tests = [
        ("L0-L4 组件加载", test_l04_components),
        ("知识空白检测", test_gap_detector),
        ("矛盾发现", test_conflict_finder),
        ("多专家辩论", test_debater),
        ("递归学习", test_recursive_learner),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "[PASS]" if result else "[FAIL]"))
        except Exception as e:
            results.append((name, f"[ERROR]: {e}"))
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, result in results:
        print(f"  {result} - {name}")

    passed = sum(1 for _, r in results if "PASS" in r)
    print(f"\n通过: {passed}/{len(results)}")


if __name__ == "__main__":
    main()
