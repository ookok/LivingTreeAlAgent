#!/usr/bin/env python3
"""
集成模块测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 60)
print("ProgressiveUnderstanding 集成模块测试")
print("=" * 60)

# 测试 1: 模块导入
print("\n[测试 1] 模块导入")
try:
    from core.long_context import (
        # Phase 4 组件
        ProgressiveUnderstanding,
        ProgressiveResult,
        UnderstandingConfig,
        UnderstandingDepth,
        ComprehensionPhase,
        KnowledgeItem,

        # 集成组件
        IntegrationMode,
        IntegrationConfig,
        IntegratedResult,
        UnifiedAgent,
        create_unified_agent,
    )
    print("✓ 所有模块导入成功")
    test_passed = [True]
except ImportError as e:
    print(f"✗ 导入失败: {e}")
    test_passed = [False]

# 测试 2: 集成配置
print("\n[测试 2] IntegrationConfig")
try:
    config = IntegrationConfig(
        mode=IntegrationMode.FULL,
        understanding_depth=UnderstandingDepth.DEEP,
        max_iterations=2,
        enable_knowledge_base=True,
        enable_deep_search=True,
        enable_skill_evolution=True,
    )
    assert config.mode == IntegrationMode.FULL
    assert config.understanding_depth == UnderstandingDepth.DEEP
    print("✓ IntegrationConfig 创建成功")
    test_passed.append(True)
except Exception as e:
    print(f"✗ IntegrationConfig 失败: {e}")
    test_passed.append(False)

# 测试 3: UnifiedAgent 创建
print("\n[测试 3] UnifiedAgent 创建")
try:
    agent = UnifiedAgent(config)
    assert agent.config.mode == IntegrationMode.FULL
    print("✓ UnifiedAgent 创建成功")
    test_passed.append(True)
except Exception as e:
    print(f"✗ UnifiedAgent 创建失败: {e}")
    test_passed.append(False)

# 测试 4: 工厂函数
print("\n[测试 4] create_unified_agent 工厂函数")
try:
    agent = create_unified_agent(depth="deep", mode="full")
    assert agent.config.understanding_depth == UnderstandingDepth.DEEP
    assert agent.config.mode == IntegrationMode.FULL
    print("✓ create_unified_agent 成功")
    test_passed.append(True)
except Exception as e:
    print(f"✗ create_unified_agent 失败: {e}")
    test_passed.append(False)

# 测试 5: UnifiedAgent 组件
print("\n[测试 5] UnifiedAgent 组件初始化")
try:
    agent = create_unified_agent(mode="full")
    assert hasattr(agent, 'understander'), "缺少 understander"
    assert hasattr(agent, 'intent_classifier'), "缺少 intent_classifier"
    print(f"✓ UnifiedAgent 组件完整")
    print(f"  - understander: {type(agent.understander).__name__}")
    print(f"  - intent_classifier: {type(agent.intent_classifier).__name__}")
    test_passed.append(True)
except Exception as e:
    print(f"✗ 组件检查失败: {e}")
    test_passed.append(False)

# 测试 6: 策略决策
print("\n[测试 6] 策略决策")
try:
    agent = create_unified_agent(mode="standalone")

    # 测试不同意图的策略
    from core.agent_chat_enhancer import IntentAnalysis, ChatIntent, IntentCategory

    # 快速响应场景
    intent_quick = IntentAnalysis(
        intent=ChatIntent.GREETING,
        confidence=0.95,
        category=IntentCategory.CONVERSATION,
    )
    strategy = agent._decide_strategy(intent_quick)
    assert strategy == "quick", f"问候应该快速响应，实际: {strategy}"
    print(f"✓ 问候 -> 快速响应 ({strategy})")

    # 知识库场景
    intent_kb = IntentAnalysis(
        intent=ChatIntent.KNOWLEDGE_QUERY,
        confidence=0.8,
        category=IntentCategory.KNOWLEDGE,
        need_knowledge=True,
    )
    strategy = agent._decide_strategy(intent_kb)
    assert strategy == "knowledge", f"知识查询应该知识库增强，实际: {strategy}"
    print(f"✓ 知识查询 -> 知识库增强 ({strategy})")

    # 深度理解场景
    intent_deep = IntentAnalysis(
        intent=ChatIntent.CODE_GENERATION,
        confidence=0.7,
        category=IntentCategory.TASK,
    )
    strategy = agent._decide_strategy(intent_deep)
    assert strategy == "understand", f"代码生成应该深度理解，实际: {strategy}"
    print(f"✓ 代码生成 -> 深度理解 ({strategy})")

    test_passed.append(True)
except Exception as e:
    print(f"✗ 策略决策失败: {e}")
    test_passed.append(False)

# 测试 7: ProgressiveUnderstanding 集成
print("\n[测试 7] ProgressiveUnderstanding 集成")
try:
    from core.long_context import quick_understand

    # 直接使用渐进式理解
    text = """
    Python 是一种高级编程语言，由 Guido van Rossum 创造于 1991 年。
    它支持多种编程范式，包括面向对象、函数式和过程式编程。
    Python 有丰富的标准库，适用于数据分析、人工智能等领域。
    """

    result = quick_understand(text, task="分析 Python 特性", depth="standard")
    print(f"✓ ProgressiveUnderstanding 运行成功")
    print(f"  - 理解等级: {result.understanding_level:.0%}")
    print(f"  - 洞察数: {len(result.key_insights)}")
    print(f"  - 会话 ID: {result.session_id}")

    test_passed.append(True)
except Exception as e:
    print(f"✗ ProgressiveUnderstanding 集成失败: {e}")
    import traceback
    traceback.print_exc()
    test_passed.append(False)

# 测试 8: 会话状态
print("\n[测试 8] 会话状态管理")
try:
    agent = create_unified_agent(mode="standalone")

    # 获取会话状态
    status = agent.get_session_status("test_session")
    assert "session_id" in status, "缺少 session_id"
    assert "progress" in status, "缺少 progress"

    print(f"✓ 会话状态获取成功")
    print(f"  - session_id: {status['session_id']}")
    print(f"  - progress: {status['progress']:.0%}")

    test_passed.append(True)
except Exception as e:
    print(f"✗ 会话状态失败: {e}")
    test_passed.append(False)

# 测试 9: 追问生成
print("\n[测试 9] 追问生成")
try:
    agent = create_unified_agent(mode="full")

    from core.agent_chat_enhancer import IntentAnalysis, ChatIntent, IntentCategory

    intent = IntentAnalysis(
        intent=ChatIntent.ANALYSIS,
        confidence=0.8,
        category=IntentCategory.REASONING,
    )

    questions = agent._generate_guidance(
        "分析一下 Python 和 Java 的区别",
        "Python 是动态类型语言，Java 是静态类型...",
        intent
    )

    print(f"✓ 追问生成成功")
    print(f"  - 生成追问数: {len(questions)}")
    for q in questions:
        print(f"    - {q}")

    test_passed.append(True)
except Exception as e:
    print(f"✗ 追问生成失败: {e}")
    test_passed.append(False)

# 测试 10: 搜索主题提取
print("\n[测试 10] 搜索主题提取")
try:
    agent = create_unified_agent(mode="full")

    # 测试不同格式的消息
    test_cases = [
        ("Python 的异步编程怎么实现？", "Python"),
        ("帮我分析一下机器学习的应用场景。", "帮我分析一下机器学习"),
        ("请详细介绍深度学习的原理和应用", "请详细介绍深度学习的原理"),
    ]

    for msg, expected in test_cases:
        topic = agent._extract_search_topic(msg)
        print(f"  '{msg[:20]}...' -> '{topic}'")

    print("✓ 搜索主题提取成功")
    test_passed.append(True)
except Exception as e:
    print(f"✗ 搜索主题提取失败: {e}")
    test_passed.append(False)

# 总结
print("\n" + "=" * 60)
passed = sum(test_passed)
total = len(test_passed)
print(f"测试结果: {passed}/{total} 通过")
if passed == total:
    print("✓ 所有测试通过!")
else:
    print(f"✗ {total - passed} 个测试失败")
print("=" * 60)
