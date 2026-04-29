"""
消息模式系统测试脚本
"""

import sys
import os

# 设置 UTF-8 编码
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.message_patterns import (
    MessagePattern, PatternManager, get_pattern_manager,
    VariableResolver, ResolverContext, ContextBuilder, get_variable_resolver,
    PatternMatcher, IntentClassifier, get_pattern_matcher, get_intent_classifier,
    PromptGenerator, get_prompt_generator,
    EffectivenessEvaluator, get_effectiveness_evaluator,
    PatternCategory, TriggerType, ThinkingStyle, BuiltInPatterns
)


def test_models():
    """测试数据模型"""
    print("\n=== 测试数据模型 ===")

    # 测试创建模式
    pattern = MessagePattern()
    pattern.name = "测试模式"
    pattern.description = "这是一个测试模式"
    pattern.category = PatternCategory.ANALYSIS
    pattern.tags = ["测试", "示例"]
    pattern.template.content = "请分析 {requirement}，使用 {framework} 框架"

    print(f"✅ 创建模式: {pattern.name}")
    print(f"   ID: {pattern.id}")
    print(f"   分类: {pattern.category.value}")
    print(f"   标签: {pattern.tags}")

    # 测试序列化
    pattern_dict = pattern.to_dict()
    print(f"   序列化: ✓")

    # 测试反序列化
    pattern2 = MessagePattern.from_dict(pattern_dict)
    print(f"   反序列化: ✓")
    print(f"   名称匹配: {pattern.name == pattern2.name}")

    return True


def test_builtin_patterns():
    """测试内置模式"""
    print("\n=== 测试内置模式 ===")

    patterns = BuiltInPatterns.get_all_builtin_patterns()
    print(f"✅ 内置模式数量: {len(patterns)}")

    for pattern in patterns:
        print(f"   - {pattern.icon} {pattern.name}: {pattern.description}")

    return True


def test_pattern_manager():
    """测试模式管理器"""
    print("\n=== 测试模式管理器 ===")

    manager = get_pattern_manager()

    # 获取所有模式
    patterns = manager.get_all_patterns()
    print(f"✅ 总模式数: {len(patterns)}")

    # 获取统计
    stats = manager.get_statistics()
    print(f"   使用次数: {stats['total_usage']}")
    print(f"   平均评分: {stats['avg_quality_score']:.2f}")

    return True


def test_variable_resolver():
    """测试变量解析器"""
    print("\n=== 测试变量解析器 ===")

    resolver = get_variable_resolver()

    # 测试模板
    template = "你好 {username}，今天是 {current_date}，当前时间是 {current_time}"

    # 构建上下文
    context = ResolverContext(
        user_input="测试输入",
        user_profile={"name": "测试用户", "role": "管理员"},
        session_id="test-session-001"
    )

    # 解析
    result = resolver.resolve(template, {}, context)
    print(f"✅ 解析模板: {template[:30]}...")
    print(f"   结果: {result[:50]}...")

    # 测试变量提取
    undefined = resolver.get_undefined_variables("这是一个 {content} 的 {topic}")
    print(f"   未定义变量: {undefined}")

    return True


def test_intent_classifier():
    """测试意图分类器"""
    print("\n=== 测试意图分类器 ===")

    classifier = get_intent_classifier()

    test_cases = [
        "帮我分析一下这个需求",
        "请帮我写一篇文章",
        "帮我写一个Python函数",
        "这两个方案哪个更好？",
        "介绍一下机器学习"
    ]

    for text in test_cases:
        result = classifier.classify(text)
        print(f"✅ 输入: {text}")
        print(f"   意图: {result.primary_intent} (置信度: {result.confidence:.2f})")
        print(f"   次意图: {result.secondary_intents}")
        print()


def test_pattern_matcher():
    """测试模式匹配器"""
    print("\n=== 测试模式匹配器 ===")

    manager = get_pattern_manager()
    matcher = get_pattern_matcher()

    # 获取模式
    patterns = manager.get_all_patterns()

    # 测试输入
    test_inputs = [
        "请分析一下这个需求",
        "帮我写一个代码审查",
        "这两个方案怎么选择"
    ]

    for user_input in test_inputs:
        context = ResolverContext(
            user_input=user_input,
            conversation_history=[],
            user_profile={}
        )

        matches = matcher.match(patterns, context, threshold=0.3)
        print(f"✅ 输入: {user_input}")
        if matches:
            print(f"   最佳匹配: {matches[0].pattern.name} (置信度: {matches[0].confidence:.2f})")
            print(f"   匹配类型: {matches[0].match_type}")
        else:
            print(f"   无匹配")
        print()


def test_prompt_generator():
    """测试提示词生成器"""
    print("\n=== 测试提示词生成器 ===")

    manager = get_pattern_manager()
    generator = get_prompt_generator()

    # 获取第一个模式
    patterns = manager.get_all_patterns()
    if not patterns:
        print("⚠️ 没有可用模式")
        return False

    pattern = patterns[0]
    print(f"✅ 使用模式: {pattern.icon} {pattern.name}")

    # 构建上下文
    context = ResolverContext(
        user_input="这是一个测试需求",
        conversation_history=[],
        user_profile={"name": "测试用户"},
        session_id="test-session"
    )

    # 生成
    prompt = generator.generate(pattern, context)
    print(f"   生成成功: ✓")
    print(f"   置信度: {prompt.confidence:.2f}")
    print(f"   警告: {len(prompt.warnings)}")
    print(f"   内容预览: {prompt.content[:100]}...")

    return True


def test_effectiveness_evaluator():
    """测试效果评估器"""
    print("\n=== 测试效果评估器 ===")

    evaluator = get_effectiveness_evaluator()

    # 创建模拟评估
    from core.message_patterns import PatternUsageRecord

    test_output = """## 分析结果

### 问题识别
1. 性能问题
2. 安全隐患

### 建议
- 优化代码结构
- 增加安全验证

### 总结
整体方案可行"""

    # 分析质量
    analyzer = evaluator._analyzer
    quality = analyzer.analyze_quality(test_output)
    print(f"✅ 质量分析:")
    for metric, score in quality.items():
        print(f"   {metric}: {score:.2f}")

    return True


def main():
    """主函数"""
    print("=" * 60)
    print("消息模式与智能提示词系统 - 功能测试")
    print("=" * 60)

    tests = [
        ("数据模型", test_models),
        ("内置模式", test_builtin_patterns),
        ("模式管理器", test_pattern_manager),
        ("变量解析器", test_variable_resolver),
        ("意图分类器", test_intent_classifier),
        ("模式匹配器", test_pattern_matcher),
        ("提示词生成器", test_prompt_generator),
        ("效果评估器", test_effectiveness_evaluator)
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} 失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {name}: {status}")

    passed = sum(1 for _, r in results if r)
    print(f"\n总计: {passed}/{len(results)} 通过")


if __name__ == "__main__":
    main()
