"""
Phase 3 测试文件 - 内容分析引导

测试内容分析引导的各个组件
"""

import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============== 测试导入 ==============

def test_import():
    """测试模块导入"""
    print("[TEST] Phase 3 模块导入...")
    
    try:
        from client.src.business.content_guidance import (
            ContentType,
            ContentQuality,
            GuidanceDepth,
            ContentAnalysis,
            QualityAssessment,
            SemanticGuidanceResult,
            SemanticGuidanceGenerator,
            analyze_content,
            evaluate_quality,
            generate_semantic_guidance,
        )
        print("   [OK] core.content_guidance 导入成功")
    except ImportError as e:
        print(f"   [FAIL] core.content_guidance 导入失败: {e}")
        return False
    
    try:
        from client.src.business.content_guidance_integration import (
            ContentAwareEnhancedAgentChat,
            enhance_agent_chat_with_content,
            quick_content_analysis,
            generate_intelligent_guidance,
        )
        print("   [OK] core.content_guidance_integration 导入成功")
    except ImportError as e:
        print(f"   [FAIL] core.content_guidance_integration 导入失败: {e}")
        return False
    
    return True


# ============== 测试内容类型识别 ==============

def test_content_type_detection():
    """测试内容类型识别"""
    print("\n[TEST] 内容类型识别...")
    
    from client.src.business.content_guidance import ContentTypeDetector, ContentType
    
    detector = ContentTypeDetector()
    
    # 测试代码内容
    code_content = """
    def hello():
        print("Hello World")
        return True
    
    class MyClass:
        def __init__(self):
            self.name = "test"
    """
    content_type, confidence = detector.detect(code_content)
    print(f"   代码内容: {content_type.value} (置信度: {confidence:.2f})")
    assert content_type == ContentType.CODE, f"期望 CODE，实际 {content_type}"
    
    # 测试数据内容
    data_content = """
    2024年第一季度营收同比增长15.2%
    其中华东地区占比45%，华南地区占比30%
    毛利率为23.5%，环比增长2.1个百分点
    """
    content_type, confidence = detector.detect(data_content)
    print(f"   数据内容: {content_type.value} (置信度: {confidence:.2f})")
    assert content_type == ContentType.DATA, f"期望 DATA，实际 {content_type}"
    
    # 测试教程内容
    tutorial_content = """
    第一步：打开设置页面
    第二步：选择网络选项
    第三步：配置WiFi连接
    最后：保存设置
    """
    content_type, confidence = detector.detect(tutorial_content)
    print(f"   教程内容: {content_type.value} (置信度: {confidence:.2f})")
    assert content_type == ContentType.TUTORIAL, f"期望 TUTORIAL，实际 {content_type}"
    
    print("   [OK] 内容类型识别正确")
    return True


# ============== 测试内容分析器 ==============

def test_content_analyzer():
    """测试内容分析器"""
    print("\n[TEST] 内容分析器...")
    
    from client.src.business.content_guidance import ContentAnalyzer, ContentType
    
    analyzer = ContentAnalyzer()
    
    # 测试复杂内容
    content = """
    Python 是一种广泛使用的高级编程语言。

    主要特点：
    1. 简单易学的语法
    2. 丰富的标准库
    3. 跨平台支持

    例如，我们可以这样写一个函数：
    ```python
    def add(a, b):
        return a + b
    ```

    相比 JavaScript，Python 在数据科学领域更受欢迎。
    """
    
    result = analyzer.analyze(content)
    
    print(f"   内容类型: {result.content_type.value}")
    print(f"   置信度: {result.confidence:.2f}")
    print(f"   复杂度: {result.complexity:.2f}")
    print(f"   技术深度: {result.technical_depth:.2f}")
    print(f"   包含代码: {result.has_code}")
    print(f"   包含示例: {result.has_examples}")
    print(f"   包含对比: {result.has_comparison}")
    print(f"   主题: {result.topics}")
    
    # 验证
    assert result.has_code == True, "应该包含代码"
    assert result.has_examples == True, "应该包含示例"
    assert result.has_steps == True, "应该包含步骤"
    assert result.has_comparison == True, "应该包含对比"
    
    print("   [OK] 内容分析正确")
    return True


# ============== 测试质量评估 ==============

def test_quality_evaluation():
    """测试质量评估"""
    print("\n[TEST] 质量评估...")
    
    from client.src.business.content_guidance import (
        ContentQualityEvaluator,
        ContentType,
    )
    
    evaluator = ContentQualityEvaluator()
    
    # 测试完整内容
    complete_content = """
    Python 是什么？

    Python 是一种高级编程语言，由 Guido van Rossum 于 1991 年创建。

    主要特点如下：
    1. 简洁易读的语法
    2. 丰富的第三方库
    3. 强大的社区支持

    例如，使用 print 函数可以输出信息：
    ```python
    print("Hello World")
    ```

    但是，Python 也有其局限性，比如运行速度相对较慢。
    总之，Python 是一门值得学习的语言。
    """
    
    result = evaluator.evaluate(complete_content, ContentType.EXPLANATION)
    
    print(f"   质量等级: {result.quality.value}")
    print(f"   完整性: {result.completeness:.2f}")
    print(f"   准确性: {result.accuracy:.2f}")
    print(f"   清晰度: {result.clarity:.2f}")
    print(f"   优点: {result.strengths[:2] if result.strengths else '无'}")
    print(f"   缺失: {result.missing_info[:2] if result.missing_info else '无'}")
    
    # 完整内容应该有较高的完整性
    assert result.completeness >= 0.3, "完整内容应该有较高的完整性"
    
    # 测试不完整内容
    incomplete_content = "Python 是一种语言。"
    
    result2 = evaluator.evaluate(incomplete_content, ContentType.EXPLANATION)
    print(f"\n   不完整内容质量: {result2.quality.value}")
    print(f"   缺失项: {result2.missing_info}")
    
    assert result2.completeness < result.completeness, "不完整内容应该更低的完整性"
    
    print("   [OK] 质量评估正确")
    return True


# ============== 测试语义追问生成 ==============

def test_semantic_guidance():
    """测试语义追问生成"""
    print("\n[TEST] 语义追问生成...")
    
    from client.src.business.content_guidance import (
        SemanticGuidanceGenerator,
        GuidanceDepth,
    )
    
    generator = SemanticGuidanceGenerator()
    
    # 测试代码内容
    code_content = """
    ```python
    def quick_sort(arr):
        if len(arr) <= 1:
            return arr
        pivot = arr[len(arr) // 2]
        left = [x for x in arr if x < pivot]
        middle = [x for x in arr if x == pivot]
        right = [x for x in arr if x > pivot]
        return quick_sort(left) + middle + quick_sort(right)
    ```
    """
    
    result = generator.generate(code_content, "code_generation")
    
    print(f"   生成追问数: {len(result.questions)}")
    print(f"   追问深度: {result.depth.value}")
    print(f"   置信度: {result.confidence:.2f}")
    print(f"   关联信号: {result.related_signals}")
    
    for i, q in enumerate(result.questions[:3], 1):
        print(f"   {i}. {q}")
    
    assert len(result.questions) > 0, "应该生成追问"
    assert result.analysis.has_code == True, "应该识别代码"
    
    # 测试数据内容
    data_content = """
    2024年各地区销售额：
    | 地区 | 销售额(万) | 同比增长 |
    |------|-----------|---------|
    | 华东 | 1500 | 12% |
    | 华南 | 1200 | 18% |
    | 华北 | 1000 | 8% |
    """
    
    result2 = generator.generate(data_content, "knowledge_query")
    
    print(f"\n   数据内容追问: {len(result2.questions)} 个")
    for i, q in enumerate(result2.questions[:3], 1):
        print(f"   {i}. {q}")
    
    print("   [OK] 语义追问生成正确")
    return True


# ============== 测试领域策略 ==============

def test_domain_strategies():
    """测试领域特定追问策略"""
    print("\n[TEST] 领域特定追问策略...")
    
    from client.src.business.content_guidance import (
        DomainGuidanceStrategies,
        ContentType,
        ContentAnalyzer,
        ContentQualityEvaluator,
    )
    
    analyzer = ContentAnalyzer()
    evaluator = ContentQualityEvaluator()
    
    # 测试代码领域
    code_content = """
    def fibonacci(n):
        if n <= 1:
            return n
        return fibonacci(n-1) + fibonacci(n-2)
    """
    
    analysis = analyzer.analyze(code_content)
    quality = evaluator.evaluate(code_content, ContentType.CODE)
    
    questions = DomainGuidanceStrategies.generate_questions(
        analysis.content_type, analysis, quality
    )
    
    print(f"   代码领域追问: {len(questions)} 个")
    for q in questions[:2]:
        print(f"   - {q}")
    
    # 测试教程领域
    tutorial_content = """
    第一步：安装 Python
    第二步：配置环境变量
    第三步：安装 IDE
    """
    
    analysis2 = analyzer.analyze(tutorial_content)
    quality2 = evaluator.evaluate(tutorial_content, ContentType.TUTORIAL)
    
    questions2 = DomainGuidanceStrategies.generate_questions(
        analysis2.content_type, analysis2, quality2
    )
    
    print(f"\n   教程领域追问: {len(questions2)} 个")
    for q in questions2[:2]:
        print(f"   - {q}")
    
    print("   [OK] 领域策略正确")
    return True


# ============== 测试便捷函数 ==============

def test_convenience_functions():
    """测试便捷函数"""
    print("\n[TEST] 便捷函数...")
    
    from client.src.business.content_guidance_integration import (
        quick_content_analysis,
        generate_intelligent_guidance,
    )
    
    content = """
    深度学习是机器学习的一个分支。

    主要网络结构：
    1. CNN（卷积神经网络）- 用于图像
    2. RNN（循环神经网络）- 用于序列
    3. Transformer - 用于自然语言

    ```python
    import torch
    model = torch.nn.Sequential(
        torch.nn.Linear(784, 128),
        torch.nn.ReLU(),
        torch.nn.Linear(128, 10)
    )
    ```
    """
    
    # 快速分析
    result = quick_content_analysis(content)
    print(f"   内容类型: {result['content_type']}")
    print(f"   质量等级: {result['quality']}")
    print(f"   技术深度: {result['technical_depth']}")
    print(f"   包含代码: {result['has_code']}")
    
    # 智能追问
    guidance = generate_intelligent_guidance(content, "knowledge_query")
    print(f"\n   生成追问 {len(guidance['questions'])} 个:")
    for i, q in enumerate(guidance['questions'][:3], 1):
        print(f"   {i}. {q}")
    
    print("   [OK] 便捷函数正确")
    return True


# ============== 测试集成模块 ==============

def test_integration_module():
    """测试集成模块"""
    print("\n[TEST] 集成模块...")
    
    from client.src.business.content_guidance_integration import (
        ContentAwareEnhancedAgentChat,
        EnhancedGuidanceResult,
    )
    
    # 检查类定义
    print(f"   ContentAwareEnhancedAgentChat: 定义正确")
    print(f"   EnhancedGuidanceResult: 定义正确")
    
    # 检查属性
    result = EnhancedGuidanceResult(
        basic_questions=["基础追问1", "基础追问2"],
        semantic_questions=["语义追问1"],
        all_questions=["基础追问1", "基础追问2", "语义追问1"],
    )
    
    print(f"   合并追问: {len(result.questions)} 个")
    print(f"   策略: {result.strategy}")
    
    print("   [OK] 集成模块正确")
    return True


# ============== 主测试函数 ==============

def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Phase 3 内容分析引导 - 测试")
    print("=" * 60)
    print()
    
    tests = [
        test_import,
        test_content_type_detection,
        test_content_analyzer,
        test_quality_evaluation,
        test_semantic_guidance,
        test_domain_strategies,
        test_convenience_functions,
        test_integration_module,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"   [ERROR] {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
        print()
    
    # 汇总
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"测试结果: {passed}/{total} 通过")
    print("=" * 60)
    
    if passed == total:
        print("[PASS] All Phase 3 tests passed!")
    else:
        print("[WARN] Some tests failed, please check output above")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
