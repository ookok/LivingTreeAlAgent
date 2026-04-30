"""
Karpathy Skills 模块测试
"""

import sys
import os

# 添加项目根目录到 path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def log(msg, ok=True):
    prefix = "[OK]" if ok else "[FAIL]"
    try:
        print(f"{prefix} {msg}")
    except UnicodeEncodeError:
        safe_msg = msg.replace("\u2713", "OK").replace("\u2717", "X")
        print(f"{prefix} {safe_msg}")


def test_imports():
    """测试模块导入"""
    print("\n" + "=" * 60)
    print("Module Import Test")
    print("=" * 60)

    try:
        from business.karpathy_skills import (
            KARPATHY_RULES_TEXT,
            AmbiguitySignal,
            AmbiguityDetector,
            AgentPromptBuilder,
            build_karpathy_agent_prompt,
            get_code_architect_prompt,
        )
        log("All imports successful")
        return True
    except ImportError as e:
        log(f"Import failed: {e}", ok=False)
        return False


def test_rules_text():
    """测试规则文本"""
    print("\n" + "=" * 60)
    print("Rules Text Test")
    print("=" * 60)

    from business.karpathy_skills import KARPATHY_RULES_TEXT

    # 检查五项准则
    required = ["不隐藏困惑", "极简实现", "最小接触", "目标驱动", "主动权衡"]
    found = sum(1 for r in required if r in KARPATHY_RULES_TEXT)

    log(f"Found {found}/5 required rules")
    print(f"\nRules preview:\n{KARPATHY_RULES_TEXT[:200]}...")

    return found == 5


def test_ambiguity_detector():
    """测试歧义检测器"""
    print("\n" + "=" * 60)
    print("Ambiguity Detector Test")
    print("=" * 60)

    from business.karpathy_skills import AmbiguityDetector, get_detector

    detector = get_detector()

    # 测试用例
    test_cases = [
        {
            "input": "帮我优化一下这个函数，可能需要添加缓存",
            "expect_ambiguity": True,
            "reason": "包含模糊词'可能'"
        },
        {
            "input": "写一个函数计算两个数的和",
            "expect_ambiguity": False,
            "reason": "明确的需求"
        },
        {
            "input": "实现一个数据处理模块，大概需要支持CSV和JSON格式",
            "expect_ambiguity": True,
            "reason": "包含'大概'和模糊的'支持'"
        },
    ]

    all_passed = True
    for case in test_cases:
        signals = detector.detect(case["input"])
        has_ambiguity = len(signals) > 0

        if has_ambiguity == case["expect_ambiguity"]:
            log(f"✓ '{case['reason']}' - {'检测到' if has_ambiguity else '未检测到'}歧义")
        else:
            log(f"✗ '{case['reason']}' - 预期{'检测到' if case['expect_ambiguity'] else '未检测到'}，实际{'检测到' if has_ambiguity else '未检测到'}", ok=False)
            all_passed = False

    return all_passed


def test_code_complexity():
    """测试代码复杂度检查"""
    print("\n" + "=" * 60)
    print("Code Complexity Test")
    print("=" * 60)

    from business.karpathy_skills import get_detector

    detector = get_detector()

    # 过度设计的代码
    over_engineered = """
class AbstractFactoryBuilder:
    def __init__(self):
        self._strategy = None
        self._observer = None

    def create_strategy(self):
        return StrategyInterface()

    def add_observer(self, observer):
        self._observer = Observer()

    def execute(self):
        self._strategy.execute()

class StrategyInterface:
    def execute(self):
        pass

def func1(): pass
def func2(): pass
def func3(): pass
def func4(): pass
def func5(): pass
def func6(): pass
"""

    # 简洁的代码
    simple_code = """
def add(a, b):
    return a + b
"""

    result1 = detector.check_code_complexity(over_engineered)
    result2 = detector.check_code_complexity(simple_code)

    log(f"Over-engineered code: is_over={result1['is_over_engineered']}")
    log(f"Simple code: is_over={result2['is_over_engineered']}")

    return result1["is_over_engineered"] and not result2["is_over_engineered"]


def test_prompt_builder():
    """测试 Prompt 构建器"""
    print("\n" + "=" * 60)
    print("Prompt Builder Test")
    print("=" * 60)

    from business.karpathy_skills import (
        AgentPromptBuilder,
        build_karpathy_agent_prompt,
        get_code_architect_prompt,
        get_code_generator_prompt,
        AgentType,
    )

    builder = AgentPromptBuilder()

    # 测试基础构建
    prompt1 = builder.build(agent_type=AgentType.CODE_ARCHITECT, include_karpathy=True)
    has_rules1 = "不隐藏困惑" in prompt1
    log(f"Code Architect prompt has rules: {has_rules1}")

    # 测试快捷函数
    prompt2 = get_code_generator_prompt()
    has_rules2 = "极简实现" in prompt2
    log(f"Code Generator prompt has rules: {has_rules2}")

    # 测试上下文注入
    prompt3 = builder.build(
        agent_type=AgentType.GENERAL,
        include_karpathy=True,
        extra_context="当前项目: TestProject\n语言: Python"
    )
    has_context = "TestProject" in prompt3
    log(f"Extra context injected: {has_context}")

    return has_rules1 and has_rules2 and has_context


def test_interaction_module():
    """测试交互模块"""
    print("\n" + "=" * 60)
    print("Interaction Module Test")
    print("=" * 60)

    try:
        from business.karpathy_skills import (
            AmbiguityResolver,
            AmbiguityDialog,
            get_resolver_context,
        )

        resolver = AmbiguityResolver()
        context = get_resolver_context()

        log("AmbiguityResolver created")
        log("ResolverContext singleton works")

        return True
    except ImportError as e:
        log(f"Interaction module import failed: {e}", ok=False)
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Karpathy Skills Module Test Suite")
    print("=" * 60)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Rules Text", test_rules_text()))
    results.append(("Ambiguity Detector", test_ambiguity_detector()))
    results.append(("Code Complexity", test_code_complexity()))
    results.append(("Prompt Builder", test_prompt_builder()))
    results.append(("Interaction Module", test_interaction_module()))

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    for name, ok in results:
        status = "OK" if ok else "X"
        print(f"  [{status}] {name}")

    print(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed")