"""
BookRAG 测试脚本

用法:
    # 方式1: 在项目根目录运行
    python -m core.fusion_rag.test_bookrag
    
    # 方式2: 设置 PYTHONPATH
    PYTHONPATH=. python core/fusion_rag/test_bookrag.py
"""

import sys
from pathlib import Path

# 添加模块路径
_module_dir = Path(__file__).parent
_project_root = _module_dir.parent.parent
sys.path.insert(0, str(_project_root))

from core.fusion_rag import (
    BookRAG,
    BookRAGConfig,
    IFTQueryClassifier,
    IFTQueryType,
    IFTClassificationResult,
    Chunk,
    RetrievalPipeline,
    create_pipeline,
    bookrag_retrieve,
    bookrag_classify,
)


def test_ift_classifier():
    """测试 IFT 分类器"""
    print("=" * 60)
    print("测试 IFT 分类器")
    print("=" * 60)
    
    classifier = IFTQueryClassifier()
    
    test_queries = [
        # 单跳查询
        ("什么是机器学习？", IFTQueryType.SINGLE_HOP),
        ("Python 的创始人是谁？", IFTQueryType.SINGLE_HOP),
        ("What is Python?", IFTQueryType.SINGLE_HOP),
        
        # 多跳查询
        ("Python 和 Java 有什么区别？", IFTQueryType.MULTI_HOP),
        ("为什么 Transformer 需要注意力机制？", IFTQueryType.MULTI_HOP),
        ("Compare Python and Java", IFTQueryType.MULTI_HOP),
        
        # 全局聚合查询
        ("文档中一共提到了多少个人名？", IFTQueryType.GLOBAL_AGGREGATION),
        ("列出所有提到的算法", IFTQueryType.GLOBAL_AGGREGATION),
        ("How many times is AI mentioned?", IFTQueryType.GLOBAL_AGGREGATION),
    ]
    
    passed = 0
    for query, expected_type in test_queries:
        result = classifier.classify(query)
        status = "✓" if result.query_type == expected_type else "✗"
        
        if result.query_type == expected_type:
            passed += 1
        
        print(f"{status} 查询: {query}")
        print(f"  预期: {expected_type.value}")
        print(f"  实际: {result.query_type.value} (置信度: {result.confidence:.2f})")
        print(f"  管道: {result.recommended_pipeline}")
        print()
    
    print(f"通过率: {passed}/{len(test_queries)}")
    return passed == len(test_queries)


def test_retrieval_operators():
    """测试检索操作符"""
    print("=" * 60)
    print("测试检索操作符")
    print("=" * 60)
    
    # 创建测试块
    chunks = [
        Chunk(
            id="chunk_1",
            content="Python 是一种高级编程语言，由 Guido van Rossum 于 1991 年创建。",
            metadata={"source": "Python 介绍"},
        ),
        Chunk(
            id="chunk_2",
            content="Java 是一种面向对象的编程语言，由 Sun Microsystems 于 1995 年发布。",
            metadata={"source": "Java 介绍"},
        ),
        Chunk(
            id="chunk_3",
            content="Python 和 Java 都需要编译或解释执行。Python 使用缩进来定义代码块。",
            metadata={"source": "对比分析"},
        ),
        Chunk(
            id="chunk_4",
            content="机器学习是人工智能的一个分支，研究如何让计算机从数据中学习。",
            metadata={"source": "ML 介绍"},
        ),
        Chunk(
            id="chunk_5",
            content="深度学习是机器学习的子集，使用神经网络模型。",
            metadata={"source": "DL 介绍"},
        ),
    ]
    
    # 测试简单管道
    print("\n1. 测试简单管道 (Selector + Synthesizer):")
    pipeline = create_pipeline("simple")
    result = pipeline.run("Python 是什么？", chunks)
    
    print(f"  答案: {result.answer[:100]}...")
    print(f"  置信度: {result.confidence:.2f}")
    print(f"  来源数: {len(result.sources)}")
    print(f"  管道: {result.pipeline_used}")
    
    # 测试推理管道
    print("\n2. 测试推理管道 (Selector + Reasoner + Synthesizer):")
    pipeline = create_pipeline("reasoning")
    result = pipeline.run("Python 和 Java 有什么区别？", chunks)
    
    print(f"  答案: {result.answer[:100]}...")
    print(f"  置信度: {result.confidence:.2f}")
    print(f"  来源数: {len(result.sources)}")
    print(f"  管道: {result.pipeline_used}")
    
    # 测试聚合管道
    print("\n3. 测试聚合管道 (Selector + Aggregator + Synthesizer):")
    pipeline = create_pipeline("aggregation")
    result = pipeline.run("文档中提到了哪些编程语言？", chunks)
    
    print(f"  答案: {result.answer[:200]}...")
    print(f"  置信度: {result.confidence:.2f}")
    print(f"  来源数: {len(result.sources)}")
    print(f"  管道: {result.pipeline_used}")
    
    return True


def test_bookrag():
    """测试 BookRAG 统一接口"""
    print("=" * 60)
    print("测试 BookRAG 统一接口")
    print("=" * 60)
    
    # 创建块
    chunks = [
        Chunk(
            id="chunk_1",
            content="Python 是一种高级编程语言。",
            metadata={"source": "来源1"},
        ),
        Chunk(
            id="chunk_2",
            content="Java 是一种面向对象编程语言。",
            metadata={"source": "来源2"},
        ),
        Chunk(
            id="chunk_3",
            content="深度学习是机器学习的子集，使用神经网络。",
            metadata={"source": "来源3"},
        ),
    ]
    
    # 测试自动管道选择
    print("\n1. 测试自动管道选择:")
    rag = BookRAG()
    
    queries = [
        "Python 是什么？",
        "Python 和 Java 的区别是什么？",
        "文档中提到了哪些编程语言？",
    ]
    
    for query in queries:
        result, classification = rag.retrieve(query, chunks, return_classification=True)
        
        print(f"\n查询: {query}")
        print(f"  IFT 类型: {classification.query_type.value}")
        print(f"  置信度: {classification.confidence:.2f}")
        print(f"  管道: {result.pipeline_used}")
        print(f"  置信度: {result.confidence:.2f}")
    
    return True


def test_custom_config():
    """测试自定义配置"""
    print("=" * 60)
    print("测试自定义配置")
    print("=" * 60)
    
    config = BookRAGConfig(
        selector_top_k=5,
        max_context_length=2000,
        include_citations=True,
        default_pipeline="reasoning",
    )
    
    rag = BookRAG(config=config)
    
    chunks = [
        Chunk(id="1", content="测试内容 " * 50),
    ]
    
    result = rag.retrieve("测试查询", chunks)
    
    print(f"自定义配置测试:")
    print(f"  管道: {result.pipeline_used}")
    print(f"  置信度: {result.confidence:.2f}")
    
    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("BookRAG 模块测试")
    print("=" * 60 + "\n")
    
    all_passed = True
    
    # 运行所有测试
    tests = [
        ("IFT 分类器", test_ift_classifier),
        ("检索操作符", test_retrieval_operators),
        ("BookRAG 统一接口", test_bookrag),
        ("自定义配置", test_custom_config),
    ]
    
    for name, test_func in tests:
        try:
            passed = test_func()
            if not passed:
                all_passed = False
                print(f"\n✗ {name} 测试失败")
        except Exception as e:
            all_passed = False
            print(f"\n✗ {name} 测试出错: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ 所有测试通过！")
    else:
        print("✗ 部分测试失败")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    main()
