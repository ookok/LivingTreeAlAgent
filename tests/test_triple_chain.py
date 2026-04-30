"""
三重链统一引擎测试脚本（集成 LLM Wiki）
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from client.src.business.fusion_rag import (
    FusionRAG,
    create_triple_chain_engine,
    TripleChainEngine
)

# 测试 LLM Wiki 集成
try:
    from client.src.business.llm_wiki import search_llm_wiki, HybridRetriever
    print("✓ LLM Wiki 模块导入成功")
except ImportError as e:
    print(f"✗ LLM Wiki 模块导入失败: {e}")


def test_triple_chain_engine():
    """测试三重链引擎"""
    print("=" * 60)
    print("测试三重链统一引擎")
    print("=" * 60)
    
    # 创建引擎
    engine = create_triple_chain_engine()
    print("✓ 三重链引擎初始化成功")
    
    # 模拟检索文档
    mock_docs = [
        {
            "id": "doc001",
            "title": "GB/T 18254-2016 高碳铬轴承钢",
            "content": "高碳铬轴承钢用于制造轴承套圈和滚动体，硬度要求HRC60-64...",
            "source_type": "gb/t",
            "confidence": 0.95,
            "authority_level": 5
        },
        {
            "id": "doc002",
            "title": "机械设计手册-轴承选型篇",
            "content": "轴承选型需考虑载荷、转速、精度等级等因素...",
            "source_type": "技术手册",
            "confidence": 0.88,
            "authority_level": 4
        },
        {
            "id": "doc003",
            "title": "轴承失效分析报告",
            "content": "常见失效模式包括疲劳剥落、磨损、腐蚀等...",
            "source_type": "内部文档",
            "confidence": 0.75,
            "authority_level": 3
        }
    ]
    
    # 构建三重链
    result = engine.build_triple_chain(
        query="为高速旋转设备选择轴承",
        task_type="selection",
        retrieved_docs=mock_docs
    )
    
    print(f"\n✓ 三重链构建成功")
    print(f"  验证状态: {'通过' if result.validation_passed else '未通过'}")
    print(f"  总体置信度: {result.overall_confidence:.2f}")
    print(f"  不确定性提示: {result.uncertainty_note}")
    
    # 输出推理步骤
    print("\n推理步骤:")
    for step in result.reasoning_steps:
        print(f"  {step.step_id}. {step.content} (置信度: {step.confidence:.2f})")
    
    # 输出证据
    print("\n证据来源:")
    for evidence in result.evidences:
        print(f"  - {evidence.title} (来源类型: {evidence.source_type}, 置信度: {evidence.confidence:.2f})")
    
    print("\n" + "=" * 60)


def test_fusion_rag_with_triple_chain():
    """测试FusionRAG的三重链检索"""
    print("\n" + "=" * 60)
    print("测试FusionRAG三重链检索")
    print("=" * 60)
    
    # 创建FusionRAG实例
    rag = FusionRAG({"target_industry": "机械制造"})
    print("✓ FusionRAG初始化成功")
    
    # 执行三重链检索
    result = rag.search_with_triple_chain("为高速旋转设备选择轴承")
    
    print(f"\n✓ 检索完成")
    print(f"  查询: {result['query']}")
    print(f"  任务类型: {result['task_type']}")
    print(f"  验证通过: {result['validation_passed']}")
    print(f"  总体置信度: {result['overall_confidence']:.2f}")
    
    print("\n回答:")
    print(f"  {result['answer']}")
    
    print("\n推理步骤:")
    for step in result['reasoning']:
        print(f"  {step['step_id']}. {step['content']}")
    
    print("\n证据来源:")
    for evidence in result['evidence']:
        print(f"  - {evidence['title']}")
    
    if result['uncertainty_note']:
        print(f"\n提示: {result['uncertainty_note']}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_triple_chain_engine()
    test_fusion_rag_with_triple_chain()
    print("\n✅ 所有测试完成！")