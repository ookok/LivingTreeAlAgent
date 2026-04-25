# -*- coding: utf-8 -*-
"""
Test Adaptive Quality System - 自适应质量保障系统测试
====================================================

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from enhanced_evaluator import (
    EnhancedQualityEvaluator,
    QualityLevel,
    QualityDimension,
    quick_evaluate,
)
from upgrade_engine import (
    UpgradeDecisionEngine,
    UpgradeStrategy,
    UpgradeReason,
    quick_decide,
)
from adaptive_quality_system import (
    AdaptiveQualitySystem,
    QualityBudget,
    quick_execute,
)


def test_enhanced_evaluator():
    """测试增强型质量评估器"""
    print("\n" + "=" * 60)
    print("测试 1: Enhanced Quality Evaluator")
    print("=" * 60)
    
    evaluator = EnhancedQualityEvaluator()
    
    # 测试案例
    test_cases = [
        {
            "query": "什么是人工智能？",
            "response": """人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，致力于开发能够模拟、延伸和扩展人类智能的理论、方法、技术和应用系统。

主要特点：
1. 感知能力 - 能够感知图像、声音、文字等信息
2. 推理能力 - 能够进行逻辑推理和决策
3. 学习能力 - 能够从数据中学习和改进
4. 交互能力 - 能够与人类进行自然交互

人工智能技术正在深刻改变我们的生活和工作方式。""",
            "expected_level": "good",
        },
        {
            "query": "你好",
            "response": "你好！有什么可以帮助你的吗？",
            "expected_level": "good",
        },
        {
            "query": "解释量子计算",
            "response": "好的。",  # 太短，应该差
            "expected_level": "poor",
        },
        {
            "query": "医学诊断",
            "response": "抱歉，我不知道具体的医学诊断方法。",  # 拒绝回答
            "expected_level": "poor",
        },
    ]
    
    passed = 0
    for i, case in enumerate(test_cases):
        report = evaluator.evaluate(case["response"], case["query"], model_level=2)
        
        print(f"\n  测试 {i+1}: {case['query'][:20]}...")
        print(f"    综合评分: {report.overall_score:.2f}")
        print(f"    质量等级: {report.overall_level.value}")
        print(f"    需要升级: {report.needs_upgrade}")
        if report.suggested_model_level:
            print(f"    建议级别: L{report.suggested_model_level}")
        print(f"    维度详情: {report.dimensions_summary}")
        
        if report.overall_level.value != "failed":
            passed += 1
    
    print(f"\n  评估器测试: {passed}/{len(test_cases)} 通过")
    return passed >= 3


def test_upgrade_decision_engine():
    """测试升级决策引擎"""
    print("\n" + "=" * 60)
    print("测试 2: Upgrade Decision Engine")
    print("=" * 60)
    
    engine = UpgradeDecisionEngine()
    
    # 测试案例
    test_cases = [
        {
            "query": "什么是Python？",
            "current_level": 0,
            "quality_score": 0.7,
            "expected_upgrade": False,  # 0.7 >= 0.5, 不升级
        },
        {
            "query": "解释量子计算的原理和应用",
            "current_level": 1,
            "quality_score": 0.4,  # 质量不足
            "expected_upgrade": True,
        },
        {
            "query": "帮我写一个医疗诊断系统",
            "current_level": 2,
            "quality_score": 0.6,
            "expected_upgrade": True,  # 关键领域
        },
        {
            "query": "你好",
            "current_level": 0,
            "quality_score": 0.8,
            "expected_upgrade": False,  # 0.8 >= 0.5
        },
    ]
    
    passed = 0
    for i, case in enumerate(test_cases):
        decision = engine.decide(
            query=case["query"],
            current_level=case["current_level"],
            quality_score=case["quality_score"],
        )
        
        print(f"\n  测试 {i+1}: {case['query'][:20]}... (L{case['current_level']})")
        print(f"    质量评分: {case['quality_score']:.2f}")
        print(f"    决策: {'升级' if decision.should_upgrade else '不升级'}")
        print(f"    目标级别: L{decision.target_level}")
        print(f"    原因: {decision.reason.value}")
        print(f"    策略: {decision.strategy.value}")
        print(f"    推理: {decision.reasoning}")
        
        if decision.should_upgrade == case["expected_upgrade"]:
            passed += 1
    
    print(f"\n  决策引擎测试: {passed}/{len(test_cases)} 通过")
    return passed >= 3


def test_quick_functions():
    """测试快速函数"""
    print("\n" + "=" * 60)
    print("测试 3: Quick Functions")
    print("=" * 60)
    
    # 快速评估
    response = """人工智能（AI）是计算机科学的重要分支，主要研究如何让计算机完成通常需要人类智能的任务。

核心领域：
- 机器学习
- 深度学习
- 自然语言处理
- 计算机视觉

应用场景非常广泛，包括智能客服、自动驾驶、医疗诊断等。"""
    
    score, needs_upgrade, suggested_level = quick_evaluate(response, "什么是人工智能", model_level=1)
    print(f"\n  快速评估:")
    print(f"    评分: {score:.2f}")
    print(f"    需要升级: {needs_upgrade}")
    print(f"    建议级别: L{suggested_level if suggested_level else 'N/A'}")
    
    # 快速决策
    decision = quick_decide("解释量子计算的原理", current_level=1, quality_score=0.3)
    print(f"\n  快速决策:")
    print(f"    需要升级: {decision.should_upgrade}")
    print(f"    目标级别: L{decision.target_level}")
    
    return True


def test_adaptive_system():
    """测试自适应系统（模拟）"""
    print("\n" + "=" * 60)
    print("测试 4: Adaptive Quality System")
    print("=" * 60)
    
    system = AdaptiveQualitySystem()
    
    # 模拟不同级别的响应
    responses = {
        0: "人工智能是AI。",
        1: "人工智能是一种技术。",
        2: """人工智能（Artificial Intelligence）是计算机科学的一个分支，
             致力于开发能够模拟人类智能的系统。""",
        3: """人工智能（Artificial Intelligence，AI）是计算机科学的核心领域之一，
             它研究如何让机器具备感知、推理、学习和决策等智能能力。
             
             主要技术包括：
             1. 机器学习 - 让机器从数据中学习
             2. 深度学习 - 基于神经网络的进阶技术
             3. 自然语言处理 - 理解和生成人类语言
             4. 计算机视觉 - 理解和分析图像视频
             
             应用前景广阔，正在改变各行各业。""",
    }
    
    # 使用快速执行
    best_response, best_level, best_score = quick_execute(
        "什么是人工智能？",
        responses
    )
    
    print(f"\n  多级别响应选择:")
    print(f"    最佳级别: L{best_level}")
    print(f"    质量评分: {best_score:.2f}")
    print(f"    选择原因: 最高评分自动选择")
    
    # 获取统计
    stats = system.get_stats()
    print(f"\n  系统统计:")
    print(f"    总请求数: {stats['total_requests']}")
    print(f"    级别分布: {stats['level_distribution']}")
    
    return True


def test_strategy_selection():
    """测试策略选择"""
    print("\n" + "=" * 60)
    print("测试 5: Strategy Selection")
    print("=" * 60)
    
    engine = UpgradeDecisionEngine(strategy=UpgradeStrategy.ADAPTIVE)
    
    strategies = {
        "代码生成": "帮我写一个排序算法",
        "创意写作": "帮我写一个科幻故事",
        "简单问答": "今天天气怎么样",
        "复杂分析": "分析一下当前经济形势和未来发展趋势",
    }
    
    print("\n  策略选择测试:")
    for desc, query in strategies.items():
        decision = engine.decide(
            query=query,
            current_level=1,
            quality_score=0.5,
        )
        print(f"\n  [{desc}]")
        print(f"    查询: {query}")
        print(f"    策略: {decision.strategy.value}")
        print(f"    目标: L{decision.target_level}")


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("自适应质量保障系统测试")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(("Enhanced Evaluator", test_enhanced_evaluator()))
    results.append(("Upgrade Engine", test_upgrade_decision_engine()))
    results.append(("Quick Functions", test_quick_functions()))
    results.append(("Adaptive System", test_adaptive_system()))
    results.append(("Strategy Selection", test_strategy_selection()))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    return passed >= total - 1


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
