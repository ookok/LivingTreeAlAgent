# -*- coding: utf-8 -*-
"""
分层混合分析器测试 - Layered Hybrid Analyzer Test
=================================================

测试分层分析器的各个功能：
1. Layer 1: 超级摘要提取
2. Layer 2: 分块深度分析
3. Layer 3: 关系网络构建
4. Layer 4: 综合分析

Author: Hermes Desktop Team
Date: 2026-04-24
"""

import sys
import time
sys.stdout.reconfigure(encoding='utf-8')

from client.src.business.long_context import (
    LayeredHybridAnalyzer,
    AnalysisDepth,
    analyze_layered,
)


# ============================================================================
# 测试数据
# ============================================================================

SAMPLE_TEXT = """
人工智能概述

第一章：人工智能简介

人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，致力于开发能够模拟、延伸和扩展人类智能的理论、方法和技术。

人工智能的研究始于20世纪50年代，经过几十年的发展，已经取得了显著的进展。

第二章：机器学习基础

机器学习是人工智能的一个重要分支，它使计算机能够从数据中学习并改进性能。

监督学习、无监督学习和强化学习是机器学习的三种主要类型。

监督学习需要标注数据来训练模型。常见的算法包括决策树、支持向量机和神经网络。

第三章：深度学习

深度学习是机器学习的一个子领域，使用多层神经网络来学习数据的表征。

卷积神经网络（CNN）主要用于图像处理任务，而循环神经网络（RNN）则适用于序列数据处理。

第四章：应用领域

人工智能在各个领域都有广泛的应用：

1. 计算机视觉：图像识别、目标检测、人脸识别
2. 自然语言处理：机器翻译、情感分析、问答系统
3. 自动驾驶：环境感知、路径规划、决策控制
4. 医疗诊断：疾病预测、影像分析、药物研发

第五章：未来展望

人工智能的发展前景广阔，但也面临诸多挑战：

首先，数据隐私和安全问题是重要考量。其次，算法透明性和可解释性需要进一步研究。最后，人工智能伦理问题日益受到关注。

总结来说，人工智能将继续深刻改变我们的生活和工作方式。
"""


def test_layer1_super_summary():
    """测试 Layer 1: 超级摘要"""
    print("\n" + "=" * 60)
    print("测试 Layer 1: 超级摘要")
    print("=" * 60)
    
    analyzer = LayeredHybridAnalyzer()
    result = analyzer.analyze(
        SAMPLE_TEXT, 
        task="总结要点",
        depth=AnalysisDepth.QUICK,
    )
    
    print(f"\n核心摘要: {result.layer1_summary.core_summary}")
    print(f"结构: {result.layer1_summary.structure}")
    print(f"文档类型: {result.layer1_summary.doc_type}")
    print(f"关键观点数: {len(result.layer1_summary.key_points)}")
    
    for i, point in enumerate(result.layer1_summary.key_points[:3], 1):
        print(f"  {i}. {point}")
    
    print("\n✅ Layer 1 测试通过")
    return True


def test_layer2_deep_analysis():
    """测试 Layer 2: 分块深度分析"""
    print("\n" + "=" * 60)
    print("测试 Layer 2: 分块深度分析")
    print("=" * 60)
    
    analyzer = LayeredHybridAnalyzer()
    result = analyzer.analyze(
        SAMPLE_TEXT, 
        task="分析各章节内容",
        depth=AnalysisDepth.STANDARD,
    )
    
    print(f"\n总分块数: {result.total_chunks}")
    print(f"分析深度: {result.layer2_analyses[0].chunk.chunk_type.value if result.layer2_analyses else 'N/A'}")
    
    for chunk_analysis in result.layer2_analyses[:3]:
        print(f"\n分块 {chunk_analysis.chunk_index + 1}:")
        print(f"  相关度: {chunk_analysis.relevance_to_task:.2%}")
        print(f"  实体数: {len(chunk_analysis.analysis.entities)}")
        print(f"  关键点: {len(chunk_analysis.analysis.key_points)}")
        print(f"  洞察: {len(chunk_analysis.insights)}")
        
        if chunk_analysis.insights:
            print(f"  示例洞察: {chunk_analysis.insights[0][:50]}...")
    
    print("\n✅ Layer 2 测试通过")
    return True


def test_layer3_relation_network():
    """测试 Layer 3: 关系网络"""
    print("\n" + "=" * 60)
    print("测试 Layer 3: 关系网络")
    print("=" * 60)
    
    analyzer = LayeredHybridAnalyzer()
    result = analyzer.analyze(
        SAMPLE_TEXT, 
        task="分析章节关系",
        depth=AnalysisDepth.DEEP,
    )
    
    if not result.layer3_network:
        print("⚠️ 关系网络为空")
        return False
    
    print(f"\n总关系数: {result.layer3_network.total_relations}")
    print(f"强关系数: {len(result.layer3_network.strong_relations)}")
    
    print("\n关系统计:")
    for rel_type, count in result.layer3_network.relation_stats.items():
        print(f"  {rel_type}: {count}")
    
    print(f"\n聚类数: {len(result.layer3_network.clusters)}")
    for i, cluster in enumerate(result.layer3_network.clusters[:3], 1):
        print(f"  聚类 {i}: 分块 {cluster}")
    
    if result.layer3_network.relations:
        print("\n关系示例:")
        for rel in result.layer3_network.relations[:3]:
            print(f"  分块{rel.from_chunk} -> 分块{rel.to_chunk}: {rel.relation_type.value} ({rel.strength:.2f})")
    
    print("\n✅ Layer 3 测试通过")
    return True


def test_layer4_synthesis():
    """测试 Layer 4: 综合分析"""
    print("\n" + "=" * 60)
    print("测试 Layer 4: 综合分析")
    print("=" * 60)
    
    analyzer = LayeredHybridAnalyzer()
    result = analyzer.analyze(
        SAMPLE_TEXT, 
        task="总结人工智能要点",
        depth=AnalysisDepth.COMPREHENSIVE,
    )
    
    if not result.layer4_synthesis:
        print("⚠️ 综合分析为空")
        return False
    
    print(f"\n置信度: {result.layer4_synthesis.confidence:.2%}")
    print(f"处理时间: {result.layer4_synthesis.processing_time:.2f}秒")
    print(f"结论数: {len(result.layer4_synthesis.conclusions)}")
    print(f"建议数: {len(result.layer4_synthesis.recommendations)}")
    
    print("\n结论:")
    for i, conclusion in enumerate(result.layer4_synthesis.conclusions[:3], 1):
        print(f"  {i}. {conclusion[:60]}...")
    
    print("\n建议:")
    for i, rec in enumerate(result.layer4_synthesis.recommendations, 1):
        print(f"  {i}. {rec}")
    
    print("\n最终报告预览:")
    report_lines = result.layer4_synthesis.report.split('\n')
    for line in report_lines[:15]:
        print(f"  {line}")
    if len(report_lines) > 15:
        print("  ...")
    
    print("\n✅ Layer 4 测试通过")
    return True


def test_convenience_function():
    """测试便捷函数"""
    print("\n" + "=" * 60)
    print("测试便捷函数 analyze_layered()")
    print("=" * 60)
    
    result = analyze_layered(
        SAMPLE_TEXT[:500],  # 使用部分文本
        task="快速总结",
        depth="standard",
    )
    
    print(f"\n分析完成: {result.is_complete}")
    print(f"分块数: {result.total_chunks}")
    print(f"Layer 1 摘要: {result.layer1_summary.core_summary[:50]}...")
    
    print("\n✅ 便捷函数测试通过")
    return True


def test_streaming():
    """测试流式分析"""
    print("\n" + "=" * 60)
    print("测试流式分析")
    print("=" * 60)
    
    analyzer = LayeredHybridAnalyzer()
    
    print("\n流式输出:")
    for layer_name, layer_result, progress in analyzer.analyze_streaming(
        SAMPLE_TEXT[:800],
        task="分析",
        depth=AnalysisDepth.DEEP,
    ):
        if layer_name == "layer2_progress":
            print(f"  [Layer 2] 分块 {layer_result.chunk_index + 1} 完成 (进度: {progress:.1%})")
        else:
            print(f"  [Layer {layer_name.replace('layer', '')}] 完成 (进度: {progress:.1%})")
    
    print("\n✅ 流式分析测试通过")
    return True


def test_performance():
    """性能测试"""
    print("\n" + "=" * 60)
    print("性能测试")
    print("=" * 60)
    
    analyzer = LayeredHybridAnalyzer()
    
    # 测试不同深度
    depths = [
        AnalysisDepth.QUICK,
        AnalysisDepth.STANDARD,
        AnalysisDepth.DEEP,
        AnalysisDepth.COMPREHENSIVE,
    ]
    
    for depth in depths:
        start = time.time()
        result = analyzer.analyze(SAMPLE_TEXT, task="总结", depth=depth)
        elapsed = time.time() - start
        
        print(f"\n{depth.value}:")
        print(f"  耗时: {elapsed:.3f}秒")
        print(f"  分块: {result.total_chunks}")
        print(f"  完整: {result.is_complete}")
    
    print("\n✅ 性能测试通过")
    return True


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("分层混合分析器测试套件")
    print("=" * 60)
    
    tests = [
        ("Layer 1: 超级摘要", test_layer1_super_summary),
        ("Layer 2: 分块深度分析", test_layer2_deep_analysis),
        ("Layer 3: 关系网络", test_layer3_relation_network),
        ("Layer 4: 综合分析", test_layer4_synthesis),
        ("便捷函数", test_convenience_function),
        ("流式分析", test_streaming),
        ("性能测试", test_performance),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ {name} 失败: {e}")
            results.append((name, False))
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n总计: {passed_count}/{total_count} 通过")
    
    return passed_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
