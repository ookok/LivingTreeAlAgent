"""
认知框架协作者测试
"""

import sys
sys.path.insert(0, '.')

from core.cognitive_framework import (
    CognitiveFrameworkCollaborator,
    collaborate,
    CognitiveFrameworkAnalyzer,
    QuestionType,
    DomainCategory
)


def test_analyzer():
    """测试分析器"""
    print("=" * 60)
    print("测试 1: 问题分析器")
    print("=" * 60)
    
    analyzer = CognitiveFrameworkAnalyzer()
    
    test_cases = [
        ("什么是深度学习？", "概念理解型问题"),
        ("Python和Java有什么区别？", "比较分析型问题"),
        ("人工智能的历史演变是怎样的？", "历史演变型问题"),
        ("如何用Python实现快速排序？", "流程操作型问题"),
        ("为什么股票会涨跌？", "因果关系型问题"),
        ("比特币和以太坊哪个更有投资价值？", "评价判断型问题"),
    ]
    
    for question, expected in test_cases:
        result = analyzer.analyze(question)
        print(f"\n问题: {question}")
        print(f"  类型: {result.question_type.value} (期望: {expected})")
        print(f"  领域: {result.domain.value}")
        print(f"  关键概念: {result.key_concepts[:3]}")
        print(f"  深度需求: {result.implied_depth}, 广度需求: {result.implied_breadth}")
        print(f"  需要时间轴: {result.implied_history}, 需要比较轴: {result.implied_comparison}")


def test_collaborator():
    """测试协作者"""
    print("\n" + "=" * 60)
    print("测试 2: 认知框架协作者")
    print("=" * 60)
    
    collaborator = CognitiveFrameworkCollaborator()
    
    test_cases = [
        ("深度学习是什么？", None),
        ("Python和Java有什么区别？", ("Python", "Java")),
        ("人工智能的发展历程是怎样的？", None),
        ("比特币和以太坊各有什么特点？", ("比特币", "以太坊")),
    ]
    
    for question, comparison in test_cases:
        print(f"\n{'='*60}")
        print(f"问题: {question}")
        print("=" * 60)
        
        result = collaborator.collaborate(question, comparison)
        print(result)
        print()


def test_quick_api():
    """测试快捷API"""
    print("\n" + "=" * 60)
    print("测试 3: 快捷API")
    print("=" * 60)
    
    result = collaborate("机器学习和深度学习有什么区别？", ("机器学习", "深度学习"))
    print(result[:2000] + "\n... (输出已截断)")


def test_framework_structure():
    """测试框架结构"""
    print("\n" + "=" * 60)
    print("测试 4: 框架结构详情")
    print("=" * 60)
    
    collaborator = CognitiveFrameworkCollaborator()
    framework, _ = collaborator.collaborate(
        "区块链技术是什么？",
        return_framework=True
    )
    
    print(f"\n框架ID: {framework.id}")
    print(f"问题类型: {framework.question_type}")
    print(f"所属领域: {framework.domain}")
    print(f"整体置信度: {framework.confidence_overall:.2%}")
    
    print(f"\n时间轴节点数: {len(framework.time_axis)}")
    for i, node in enumerate(framework.time_axis):
        print(f"  [{i+1}] {node.period}: {node.significance[:30]}...")
    
    print(f"\n比较轴节点数: {len(framework.comparison_axis)}")
    for i, node in enumerate(framework.comparison_axis):
        print(f"  [{i+1}] {node.dimension}")
    
    print(f"\n认知地图节点数: {len(framework.cognitive_map)}")
    for node_id, node in framework.cognitive_map.items():
        print(f"  [{node_id}] {node.title} ({node.node_type}, 优先级: {node.priority})")
    
    print(f"\n关键洞察: {framework.key_insights}")
    print(f"风险区域: {framework.risk_areas}")


def main():
    """主测试函数"""
    # 设置UTF-8输出
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("[Brain] Cognitive Framework Collaborator Test")
    print("=" * 60)
    
    try:
        test_analyzer()
        test_collaborator()
        test_quick_api()
        test_framework_structure()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
