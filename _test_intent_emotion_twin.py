# -*- coding: utf-8 -*-
"""测试 L0 意图分类器 + 情绪感知 + 数字分身"""
import sys
sys.path.insert(0, ".")

def test_l0_classifier():
    """测试 L0 意图分类器"""
    from core.agent import L0IntentClassifier

    classifier = L0IntentClassifier()

    test_cases = [
        # (query, expected)
        ("今天好累啊", "emotion_aware"),      # 情感词
        ("你好", "dialogue"),                  # 寒暄
        ("你好啊", "dialogue"),                # 寒暄
        ("帮我写一个排序算法", "task"),         # 行动动词
        ("什么是大模型", "search"),             # 疑问词开头
        ("Python怎么安装", "search"),           # 疑问词开头
        ("帮我查一下天气", "task"),             # 行动动词
        ("今天心情不错", "emotion_aware"),       # 情感词
        ("累死了", "emotion_aware"),            # 情感词
        ("谢谢", "dialogue"),                  # 寒暄
        ("hi", "dialogue"),                   # 英文寒暄
        ("配置一下Redis缓存", "task"),          # 技术词
        ("打开浏览器", "task"),                 # 行动动词
        ("AI Agent的原理是什么", "task"),       # 疑问词+技术词
        ("GPU能跑多少模型", "search"),          # 疑问词
    ]

    print("\n" + "="*60)
    print("  L0 意图分类器测试")
    print("="*60)

    passed = 0
    failed = 0
    for query, expected in test_cases:
        result = classifier.classify(query, use_llm_fallback=False)  # 先测规则
        status = "PASS" if result["type"] == expected else "FAIL"
        if result["type"] == expected:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] [{result['method']:>6}] \"{query}\" -> {result['type']} (expected: {expected})")

    print(f"\n  规则命中率: {classifier._stats['rule_hits']}/{len(test_cases)} ({100*passed/len(test_cases):.0f}%)")
    print(f"  LLM 兜底调用: {classifier._stats['model_calls']} 次")

    return passed, failed


def test_emotion_vector():
    """测试情绪向量"""
    # 直接导入避免 living_tree_ai.__init__ 的循环依赖
    import sys
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "emotional",
        "core/living_tree_ai/neural_layer/emotional.py"
    )
    em_module = importlib.util.module_from_spec(spec)
    sys.modules["emotional"] = em_module
    spec.loader.exec_module(em_module)
    EmotionVector = em_module.EmotionVector
    EmotionType = em_module.EmotionType

    print("\n" + "="*60)
    print("  情绪感知测试")
    print("="*60)

    test_cases = [
        "今天好累啊",
        "太棒了！我非常开心",
        "心情很差，有点郁闷",
        "工作压力好大",
        "学习Python好难",
        "你好",
        "这个很简单",
    ]

    for text in test_cases:
        vec = EmotionVector.from_text_analysis(text)
        dominant = vec.dominant_emotion()
        print(f"  \"{text}\"")
        print(f"    → 主导情感: {dominant.value}")
        print(f"      效价valence={vec.valence:+.1f}, 唤醒度arousal={vec.arousal:.1f}, 强度={vec.intensity:.1f}")

    # 测试共振计算
    print("\n  情感共振测试:")
    vec1 = EmotionVector.from_text_analysis("今天好开心！")
    vec2 = EmotionVector.from_text_analysis("太棒了！")

    # 手动计算情感共振
    import math
    v1_list = vec1.to_list()
    v2_list = vec2.to_list()
    dot = sum(a * b for a, b in zip(v1_list, v2_list))
    mag1 = math.sqrt(sum(a * a for a in v1_list))
    mag2 = math.sqrt(sum(b * b for b in v2_list))
    resonance = (dot / (mag1 * mag2) + 1) / 2 if mag1 > 0 and mag2 > 0 else 0
    print(f'    "今天好开心" <-> "太棒了" 共振强度: {resonance:.2f}')


def test_digital_twin():
    """测试用户数字分身"""
    from core.agent import get_user_digital_twin, UserDigitalTwin

    # 使用和 test_emotion_vector 同样的方式加载 EmotionVector
    import sys, importlib.util
    spec = importlib.util.spec_from_file_location(
        "emotional_test", "core/living_tree_ai/neural_layer/emotional.py"
    )
    em_module = importlib.util.module_from_spec(spec)
    sys.modules["emotional_test"] = em_module
    spec.loader.exec_module(em_module)
    EmotionVector = em_module.EmotionVector

    print("\n" + "="*60)
    print("  数字分身测试")
    print("="*60)

    twin = get_user_digital_twin("test_user")

    # 模拟多次交互
    interactions = [
        ("今天好累啊", "emotion_aware"),
        ("帮我写一个排序算法", "task"),
        ("什么是大模型", "search"),
        ("你好", "dialogue"),
        ("Python怎么安装", "search"),
        ("工作压力好大", "emotion_aware"),
        ("帮我查一下天气", "task"),
        ("心情很差", "emotion_aware"),
        ("你好啊", "dialogue"),
        ("累死了", "emotion_aware"),
    ]

    for query, intent in interactions:
        emotion = EmotionVector.from_text_analysis(query)
        twin.record_interaction(query, intent, emotion)
        print(f"  记录: \"{query}\" [{intent}] → 等级={twin.level}, 经验={twin.experience}")

    # 测试高频话题
    print(f"\n  高频意图: {twin.get_top_intents(3)}")
    print(f"  高频话题: {twin.get_top_topics(3)}")

    # 测试情感趋势
    trend = twin.get_recent_emotion_trend()
    print(f"  近期情感趋势: {trend}")

    # 测试关心判断
    should_care = twin.should_express_care()
    print(f"  是否应表达关心: {should_care}")
    if should_care:
        print(f"  关心语句: {twin.get_care_response()}")

    # 测试数字分身上下文生成
    print(f"\n  数字分身提示上下文:")
    ctx = twin.get_context_for_prompt()
    for line in ctx.split("\n"):
        print(f"    {line}")

    # 测试序列化
    data = twin.to_dict()
    print(f"\n  序列化: {data['level']}级, {data['experience']}经验, "
          f"意图类型={len(data['intent_history'])}, "
          f"情感记录={len(data['emotion_timeline'])}条")

    # 测试反序列化
    twin2 = UserDigitalTwin.from_dict(data)
    print(f"  反序列化: {twin2.level}级, 经验={twin2.experience}")


def test_model_election_cache():
    """测试模型选举缓存"""
    from core.model_election import get_elected_models, _election_cache

    print("\n" + "="*60)
    print("  模型选举缓存测试")
    print("="*60)

    # 第一次调用
    result1 = get_elected_models()
    print(f"  L0: {result1.l0_model}, L3: {result1.l3_model}, L4: {result1.l4_model}")

    # 第二次调用（应该命中缓存）
    result2 = get_elected_models()
    print(f"  缓存命中: {'是 ✓' if result1 is result2 else '否 ✗'}")

    # 强制刷新
    result3 = get_elected_models(force_refresh=True)
    print(f"  强制刷新后: {'新对象 ✓' if result1 is not result3 else '相同对象 ✗'}")

    # 打印完整报告
    from core.model_election import print_election_report
    print_election_report(result1)


if __name__ == "__main__":
    p, f = test_l0_classifier()
    test_emotion_vector()
    test_digital_twin()
    test_model_election_cache()

    print("\n" + "="*60)
    print(f"  测试完成: {p+f} 个测试用例，{p} 通过，{f} 失败")
    print("="*60)
