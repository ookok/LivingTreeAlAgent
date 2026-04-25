# -*- coding: utf-8 -*-
"""
长上下文处理模块测试
====================

测试自适应压缩、语义分块、分块分析功能。

Author: Hermes Desktop Team
Date: 2026-04-24
"""

import sys
import time
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent))

from client.src.business.long_context import (
    # 差异化压缩
    AdaptiveCompressor,
    compress_adaptive,
    SegmentType,
    Segment,
    CompressionResult,
    # 语义分块
    SemanticChunker,
    chunk_semantic,
    Chunk,
    ChunkType,
    # 分块分析
    ChunkAnalyzer,
    analyze_chunk,
    ChunkAnalysis,
    AnalysisResult,
    # 多轮分析
    MultiTurnAnalyzer,
    TurnResult,
)


def test_adaptive_compressor():
    """测试自适应压缩"""
    print("\n" + "=" * 60)
    print("测试1: 自适应差异化压缩")
    print("=" * 60)
    
    # 测试文本
    test_text = """
第一章：人工智能概述

人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，
旨在开发能够模拟、延伸和扩展人类智能的理论、方法、技术和应用系统。

人工智能的发展经历了多个阶段：
第一阶段是计算智能阶段，主要依赖于规则和算法；
第二阶段是感知智能阶段，主要依赖于机器学习和数据；
第三阶段是认知智能阶段，主要依赖于深度学习和神经网络。

例如，在图像识别领域，卷积神经网络（CNN）已经能够达到甚至超过人类的识别准确率。
在自然语言处理领域，Transformer架构更是带来了革命性的突破。

从市场规模来看，2024年全球AI市场规模达到5000亿美元，
同比增长25%。预计到2027年，市场规模将突破1万亿美元。

代码示例：
```python
def neural_network(data):
    # 简单的神经网络示例
    weights = initialize_weights()
    for epoch in range(100):
        output = forward_pass(data, weights)
        loss = calculate_loss(output, data.labels)
        weights = backward_pass(loss, weights)
    return weights
```

综上所述，人工智能已经成为推动社会进步的重要力量。
我们需要正确认识AI的潜力与局限，使其更好地服务于人类社会。
"""
    
    # 创建压缩器
    compressor = AdaptiveCompressor()
    
    # 执行压缩
    result = compressor.compress(test_text, target_ratio=0.5)
    
    # 输出结果
    print(f"\n📊 压缩统计:")
    print(f"   原始长度: {result.original_length} 字符")
    print(f"   压缩长度: {result.compressed_length} 字符")
    print(f"   压缩比: {result.compression_ratio:.2%}")
    print(f"   节省: {result.saved_tokens} 字符 ({result.saved_ratio:.2%})")
    print(f"   处理时间: {result.processing_time_ms:.2f}ms")
    
    # 输出分块信息
    print(f"\n📝 分块分析:")
    for i, seg in enumerate(result.segments[:8]):
        print(f"   [{i+1}] {seg.segment_type.value:12} | 重要度: {seg.importance:.1f} | 长度: {seg.length}")
    
    # 输出压缩后文本
    print(f"\n📄 压缩后文本预览:")
    preview = result.compressed_text[:500]
    print(f"   {preview}...")
    
    assert result.compression_ratio < 1.0, "压缩应该减少文本长度"
    print("\n✅ 自适应压缩测试通过!")
    
    return result


def test_semantic_chunker():
    """测试语义分块"""
    print("\n" + "=" * 60)
    print("测试2: 语义分块")
    print("=" * 60)
    
    # 测试文本
    test_text = """
机器学习是人工智能的核心技术之一。

它通过让计算机从数据中学习，自动提取特征和模式，
从而实现预测和决策。根据学习方式的不同，机器学习可以分为三类：
监督学习、无监督学习和强化学习。

监督学习需要标注数据。例如，图像分类任务中，每张图片都需要标注其类别。
常见的监督学习算法包括决策树、支持向量机、神经网络等。

无监督学习不需要标注数据。它通过发现数据内部的隐藏结构来学习。
聚类和降维是无监督学习的两个主要任务。K-means是一种经典的聚类算法。

强化学习则是通过与环境交互来学习最优策略。
智能体根据环境的奖励信号不断调整行为，以最大化累积奖励。
AlphaGo就是强化学习的典型应用。

在实际应用中，我们需要根据具体问题选择合适的算法。
数据质量、特征工程、模型调参等都会影响最终效果。
"""
    
    # 创建分块器
    chunker = SemanticChunker(
        chunk_size=500,
        overlap=50,
        min_chunk_size=100,
    )
    
    # 执行分块
    chunks = chunker.chunk(test_text, strategy="auto")
    
    # 输出结果
    print(f"\n📊 分块统计:")
    stats = chunker.get_stats(chunks)
    print(f"   总分块数: {stats['total_chunks']}")
    print(f"   总长度: {stats['total_length']} 字符")
    print(f"   平均块大小: {stats['avg_chunk_size']:.0f} 字符")
    
    # 输出每个块
    print(f"\n📝 分块详情:")
    for chunk in chunks:
        print(f"\n   块 {chunk.index} [{chunk.chunk_type.value}]")
        print(f"   位置: {chunk.start_pos} - {chunk.end_pos}")
        print(f"   长度: {chunk.length} 字符")
        print(f"   关键词: {', '.join(chunk.keywords[:3])}")
        print(f"   内容预览: {chunk.content[:80]}...")
    
    assert len(chunks) > 0, "应该产生至少一个分块"
    assert all(c.length > 0 for c in chunks), "每个分块应该有内容"
    print("\n✅ 语义分块测试通过!")
    
    return chunks


def test_chunk_analyzer():
    """测试分块分析"""
    print("\n" + "=" * 60)
    print("测试3: 分块分析")
    print("=" * 60)
    
    # 测试文本
    test_text = """
深度学习框架PyTorch由Facebook开发，于2016年发布。

PyTorch的主要特点包括动态计算图、Python优先设计、强大的GPU加速支持。
它使用tensor作为基本数据结构，类似于NumPy数组但可以在GPU上运行。

代码示例：
```python
import torch

# 创建张量
x = torch.randn(3, 4)
y = torch.randn(3, 4)

# 计算
z = x + y
print(z.shape)  # torch.Size([3, 4])
```

PyTorch广泛应用于计算机视觉、自然语言处理等领域。
2024年，PyTorch 2.0引入了编译功能，大幅提升了训练效率。
"""
    
    # 分块
    chunker = SemanticChunker(chunk_size=300)
    chunks = chunker.chunk(test_text, strategy="paragraph")
    
    # 分析
    analyzer = ChunkAnalyzer()
    result = analyzer.analyze_chunks(chunks)
    
    # 输出结果
    print(f"\n📊 分析统计:")
    print(f"   总实体数: {result.total_entities}")
    print(f"   总关系数: {result.total_relations}")
    print(f"   覆盖率: {result.coverage:.2%}")
    
    # 输出实体
    print(f"\n👤 实体列表:")
    for entity in result.global_entities[:10]:
        print(f"   - {entity.entity_type.value}: {entity.text}")
    
    # 输出主题
    print(f"\n📌 核心主题:")
    for theme in result.key_themes[:5]:
        print(f"   - {theme}")
    
    # 输出洞察
    print(f"\n💡 洞察:")
    for insight in result.insights:
        print(f"   - {insight}")
    
    # 输出推荐问题
    print(f"\n❓ 推荐追问:")
    for q in result.recommended_questions[:3]:
        print(f"   - {q}")
    
    assert result.total_entities > 0, "应该识别到实体"
    print("\n✅ 分块分析测试通过!")
    
    return result


def test_multi_turn_analyzer():
    """测试多轮分析"""
    print("\n" + "=" * 60)
    print("测试4: 多轮对话分析")
    print("=" * 60)
    
    # 测试文本
    test_text = """
人工智能（AI）是当前科技发展的热点领域。

机器学习是AI的核心技术。它使计算机能够从数据中学习，而无需明确编程。
监督学习是最常见的学习方式，需要大量标注数据。

深度学习是机器学习的一个分支，使用多层神经网络。
卷积神经网络（CNN）在图像识别领域取得突破，
ResNet等架构达到了甚至超过人类的识别准确率。

Transformer架构改变了自然语言处理领域。
BERT和GPT等预训练模型展现了强大的语言理解能力。
大语言模型（LLM）如ChatGPT更是引发了AI革命。

在实际应用中，需要考虑数据质量、计算资源、伦理问题等因素。
AI的可解释性和安全性也是重要研究方向。
"""
    
    # 创建分析器
    analyzer = MultiTurnAnalyzer(
        max_turns_per_chunk=2,
        enable_synthesis=True,
    )
    
    # 进度回调
    def progress(msg, p):
        print(f"   [{p*100:3.0f}%] {msg}")
    
    # 执行分析
    result = analyzer.analyze(
        test_text,
        task="总结AI技术的发展",
        progress_callback=progress
    )
    
    # 输出结果
    print(f"\n📊 分析统计:")
    print(f"   分块数: {len(result.chunks)}")
    print(f"   分析覆盖率: {result.analysis.coverage:.2%}")
    print(f"   探索路径数: {len(result.exploration_paths)}")
    print(f"   总轮次数: {result.total_turns}")
    print(f"   总耗时: {result.duration_seconds:.2f}秒")
    
    # 输出探索路径
    print(f"\n🔍 探索路径:")
    for path in result.exploration_paths:
        print(f"\n   路径 {path.path_id}:")
        print(f"   - 探索深度: {path.depth} 轮")
        print(f"   - 探索块: {path.chunks}")
        for turn in path.turns:
            print(f"   - 轮次 {turn.turn_id}:")
            print(f"     Q: {turn.question[:50]}...")
            print(f"     A: {turn.answer[:50]}...")
    
    # 输出综合结果
    print(f"\n📝 综合结果:")
    print(f"   {result.synthesized_result}")
    
    assert len(result.chunks) > 0, "应该产生分块"
    assert result.total_turns > 0, "应该产生轮次"
    print("\n✅ 多轮分析测试通过!")
    
    return result


def test_integration():
    """测试集成流程"""
    print("\n" + "=" * 60)
    print("测试5: 集成流程")
    print("=" * 60)
    
    # 完整流程
    test_text = """
区块链技术是一种去中心化的分布式账本技术。

比特币是最早的区块链应用，由中本聪于2009年创建。
以太坊则引入了智能合约，将区块链应用扩展到更广领域。

区块链的核心特性包括：
1. 去中心化：无须第三方信任机构
2. 不可篡改：数据一旦写入难以修改
3. 可追溯：所有交易记录可查
4. 透明公开：账本对所有参与者可见

然而，区块链也面临挑战：
- 性能问题：TPS（每秒交易数）受限
- 能源消耗：特别是PoW共识机制
- 监管合规：如何与现有法律兼容

未来，区块链将与AI、物联网等技术深度融合，
在供应链金融、政务服务、医疗健康等领域发挥更大作用。
"""
    
    print("\n📋 完整流程测试:")
    
    # 1. 语义分块
    print("\n[1/3] 语义分块...")
    chunks = chunk_semantic(test_text, strategy="auto")
    print(f"    产生 {len(chunks)} 个分块")
    
    # 2. 分块分析
    print("\n[2/3] 分块分析...")
    analyzer = ChunkAnalyzer()
    analysis = analyzer.analyze_chunks(chunks)
    print(f"    识别 {analysis.total_entities} 个实体")
    print(f"    发现 {len(analysis.global_relations)} 个关系")
    
    # 3. 差异化压缩
    print("\n[3/3] 差异化压缩...")
    compressor = AdaptiveCompressor()
    result = compressor.compress(test_text, target_ratio=0.5)
    print(f"    压缩比: {result.compression_ratio:.2%}")
    print(f"    节省: {result.saved_ratio:.2%}")
    
    print("\n✅ 集成流程测试通过!")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🚀 长上下文处理模块测试")
    print("=" * 60)
    
    tests = [
        ("自适应压缩", test_adaptive_compressor),
        ("语义分块", test_semantic_chunker),
        ("分块分析", test_chunk_analyzer),
        ("多轮分析", test_multi_turn_analyzer),
        ("集成流程", test_integration),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, "PASS"))
        except Exception as e:
            print(f"\n❌ {name} 测试失败: {e}")
            results.append((name, f"FAIL: {e}"))
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)
    
    for name, result in results:
        status = "✅" if result == "PASS" else "❌"
        print(f"   {status} {name}: {result}")
    
    passed = sum(1 for _, r in results if r == "PASS")
    print(f"\n通过: {passed}/{len(results)}")


if __name__ == "__main__":
    run_all_tests()
