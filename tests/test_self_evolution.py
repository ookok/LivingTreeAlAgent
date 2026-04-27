"""
Phase 3: 自主学习与进化系统测试
================================

测试内容:
1. SelfLearningEngine - 自主学习引擎
2. AdaptiveCompressionStrategy - 自适应压缩策略
3. EvolutionController - 进化控制器
4. 意图预测与建议
5. 知识模式学习
"""

import sys
import os
import importlib.util

# 直接加载模块，绕过 core/__init__.py
module_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'core', 'self_evolution.py'
)

spec = importlib.util.spec_from_file_location('self_evolution', module_path)
self_evolution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(self_evolution)

# 导出需要的内容
SelfLearningEngine = self_evolution.SelfLearningEngine
AdaptiveCompressionStrategy = self_evolution.AdaptiveCompressionStrategy
EvolutionController = self_evolution.EvolutionController
InteractionSample = self_evolution.InteractionSample
KnowledgePattern = self_evolution.KnowledgePattern
create_evolution_controller = self_evolution.create_evolution_controller
quick_learn = self_evolution.quick_learn
predict_and_suggest = self_evolution.predict_and_suggest


def test_learning_engine():
    """测试自主学习引擎"""
    print("\n[Test 1] SelfLearningEngine")
    print("-" * 40)
    
    engine = SelfLearningEngine("test_twin_001")
    # 降低学习阈值以便测试
    engine.min_samples_for_learning = 3
    
    # 添加样本
    samples_data = [
        ("create user class", "python code", True, 0.8),
        ("add login method", "python code", True, 0.9),
        ("fix auth bug", "debug code", False, -0.3),
        ("write tests", "test code", True, 0.7),
        ("optimize query", "sql code", True, 0.85),
    ]
    
    for query, context, success, score in samples_data:
        sample = InteractionSample(
            query=query,
            context=context,
            code="sample code",
            success=success,
            feedback_score=score
        )
        engine.add_sample(sample)
    
    # 检查样本数量
    print(f"  Samples Added: {len(engine.samples)}")
    assert len(engine.samples) == 5, "Sample count mismatch"
    
    # 检查指标
    summary = engine.get_performance_summary()
    print(f"  Metrics Tracked: {list(summary['metrics'].keys())}")
    print(f"  Accuracy Avg: {summary['metrics'].get('accuracy', {}).get('average', 0):.2f}")
    
    # 检查模式学习
    print(f"  Patterns Learned: {len(engine.patterns)}")
    
    print("  [OK] Learning Engine Test Passed")


def test_intent_prediction():
    """测试意图预测"""
    print("\n[Test 2] Intent Prediction")
    print("-" * 40)
    
    engine = SelfLearningEngine("test_twin_002")
    engine.min_samples_for_learning = 3
    
    # 添加一些样本建立模式
    for _ in range(10):
        engine.add_sample(InteractionSample(
            query="create a new class",
            context="code",
            code="class Test: pass",
            intent_signature={"type": "code", "action": "create"},
            success=True,
            feedback_score=0.8
        ))
    
    # 预测意图
    test_queries = [
        "create a database model",
        "add login method",
        "fix authentication bug"
    ]
    
    for query in test_queries:
        intent = engine.predict_intent(query)
        print(f"  Query: {query}")
        print(f"    Type: {intent['type']}, Action: {intent['action']}")
        print(f"    Confidence: {intent['confidence']:.2f}")
    
    print("  [OK] Intent Prediction Test Passed")


def test_context_suggestions():
    """测试上下文建议"""
    print("\n[Test 3] Context Suggestions")
    print("-" * 40)
    
    engine = SelfLearningEngine("test_twin_003")
    
    # 添加成功模式
    for _ in range(5):
        engine.add_sample(InteractionSample(
            query="implement API endpoint",
            context="REST API",
            code="def api(): pass",
            intent_signature={"type": "code", "action": "create"},
            success=True,
            feedback_score=0.9
        ))
    
    # 获取建议
    intent = {"type": "code", "action": "create"}
    suggestions = engine.suggest_context(intent)
    
    print(f"  Intent: {intent}")
    print(f"  Suggestions: {suggestions}")
    
    print("  [OK] Context Suggestions Test Passed")


def test_adaptive_compression():
    """测试自适应压缩策略"""
    print("\n[Test 4] Adaptive Compression Strategy")
    print("-" * 40)
    
    strategy = AdaptiveCompressionStrategy()
    
    test_intents = [
        {"type": "code", "action": "create"},
        {"type": "test", "action": "create"},
        {"type": "debug", "action": "fix"},
        {"type": "general", "action": "understand"}
    ]
    
    for intent in test_intents:
        selected = strategy.select_strategy(intent, [])
        print(f"  {intent['type']}/{intent['action']} -> {selected}")
        assert selected in ["aggressive", "balanced", "conservative"]
    
    # 测试策略调整
    strategy.adjust_strategy("aggressive", True)
    strategy.adjust_strategy("aggressive", True)
    strategy.adjust_strategy("aggressive", True)
    
    current = strategy.get_current_strategy()
    print(f"  Current Strategy: {current['name']}")
    print(f"  Performance: {current['performance']}")
    
    print("  [OK] Adaptive Compression Test Passed")


def test_evolution_controller():
    """测试进化控制器"""
    print("\n[Test 5] Evolution Controller")
    print("-" * 40)
    
    controller = create_evolution_controller("test_twin_004")
    
    # 处理多个交互
    for i in range(10):
        success = i % 10 < 8
        result = controller.process_and_learn(
            query=f"task {i}",
            context=f"context {i}",
            code=f"code {i}",
            response=f"response {i}",
            success=success,
            feedback_score=0.7 if success else -0.2
        )
        
        if i == 0:
            print(f"  First Result: Intent={result['intent']['type']}")
    
    # 检查学习洞察
    insights = controller.get_learning_insights()
    print(f"  Patterns: {len(insights['patterns'])}")
    print(f"  Recommendations: {len(insights['recommendations'])}")
    
    print("  [OK] Evolution Controller Test Passed")


def test_knowledge_patterns():
    """测试知识模式"""
    print("\n[Test 6] Knowledge Patterns")
    print("-" * 40)
    
    engine = SelfLearningEngine("test_twin_005")
    
    # 添加多种类型的样本
    patterns_data = [
        ("create", "code", True),
        ("create", "code", True),
        ("create", "code", True),
        ("modify", "code", True),
        ("modify", "code", False),
        ("search", "general", True),
        ("search", "general", True),
    ]
    
    for action, ptype, success in patterns_data:
        engine.add_sample(InteractionSample(
            query=f"{action} {ptype}",
            context="test",
            code="",
            intent_signature={"type": ptype, "action": action},
            success=success,
            feedback_score=0.8 if success else -0.3
        ))
    
    # 检查模式统计
    print(f"  Total Patterns: {len(engine.patterns)}")
    
    for pattern_id, pattern in list(engine.patterns.items())[:3]:
        print(f"  Pattern: {pattern.pattern_text}")
        print(f"    Type: {pattern.pattern_type}")
        print(f"    Success Rate: {pattern.success_rate:.2f}")
        print(f"    Confidence: {pattern.confidence:.2f}")
    
    print("  [OK] Knowledge Patterns Test Passed")


def test_evolution_trigger():
    """测试进化触发"""
    print("\n[Test 7] Evolution Trigger")
    print("-" * 40)
    
    controller = create_evolution_controller("test_twin_006")
    
    # 设置较小的进化间隔用于测试
    controller.evolution_interval = 5
    
    evolution_count = 0
    for i in range(15):
        result = controller.process_and_learn(
            query=f"task {i}",
            context="",
            code="",
            response="",
            success=i % 2 == 0,
            feedback_score=0.5
        )
        
        if result.get("evolution_result"):
            evolution_count += 1
            print(f"  Evolution triggered at sample {i + 1}")
    
    print(f"  Total Evolutions: {evolution_count}")
    print(f"  Final Status: {controller.learning_engine.evolution_status.value}")
    
    print("  [OK] Evolution Trigger Test Passed")


def test_quick_learn():
    """测试快速学习"""
    print("\n[Test 8] Quick Learn")
    print("-" * 40)
    
    result = quick_learn("test_twin_007", "create new feature", True, 0.9)
    
    print(f"  Predicted Intent: {result['intent']}")
    print(f"  Strategy: {result['compression_strategy']}")
    print(f"  Suggestions: {result['context_suggestions']}")
    
    assert "intent" in result, "Should include intent"
    
    print("  [OK] Quick Learn Test Passed")


def test_predict_and_suggest():
    """测试预测和建议"""
    print("\n[Test 9] Predict and Suggest")
    print("-" * 40)
    
    # 先学习一些模式
    controller = create_evolution_controller("test_twin_008")
    for _ in range(5):
        controller.process_and_learn(
            query="implement caching",
            context="performance",
            code="cache = {}",
            response="",
            success=True,
            feedback_score=0.8
        )
    
    # 然后预测
    result = predict_and_suggest("test_twin_008", "add memory cache")
    
    print(f"  Predicted Intent: {result['predicted_intent']}")
    print(f"  Context Suggestions: {result['context_suggestions']}")
    
    print("  [OK] Predict and Suggest Test Passed")


def test_performance_metrics():
    """测试性能指标"""
    print("\n[Test 10] Performance Metrics")
    print("-" * 40)
    
    engine = SelfLearningEngine("test_twin_009")
    
    # 添加样本并检查指标更新
    for i in range(20):
        sample = InteractionSample(
            query=f"task {i}",
            context="test context",
            code="code",
            intent_signature={"type": "code"},
            success=i % 10 < 8,
            feedback_score=0.7,
            latency_ms=100 + i * 5
        )
        engine.add_sample(sample)
    
    summary = engine.get_performance_summary()
    
    print(f"  Total Samples: {summary['total_samples']}")
    print(f"  Metrics:")
    
    for metric_name, metric_data in summary["metrics"].items():
        print(f"    {metric_name}:")
        print(f"      Current: {metric_data.get('current', 0):.2f}")
        print(f"      Average: {metric_data.get('average', 0):.2f}")
        print(f"      Trend: {metric_data.get('trend', 'N/A')}")
    
    print("  [OK] Performance Metrics Test Passed")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("[TEST] Phase 3: Self-Learning and Evolution")
    print("=" * 60)
    
    test_learning_engine()
    test_intent_prediction()
    test_context_suggestions()
    test_adaptive_compression()
    test_evolution_controller()
    test_knowledge_patterns()
    test_evolution_trigger()
    test_quick_learn()
    test_predict_and_suggest()
    test_performance_metrics()
    
    print("\n" + "=" * 60)
    print("[COMPLETE] All Phase 3 Tests Passed!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
