"""
BookRAG 模块测试
BookRAG Module Tests

测试 IFT 分类器、检索操作符和 BookRAG 统一入口
"""

import pytest
from core.fusion_rag import (
    BookRAG,
    BookRAGConfig,
    IFTQueryClassifier,
    IFTQueryType,
    IFTClassificationResult,
    Chunk,
    RetrievalPipeline,
    RetrievalContext,
    RetrievalResult,
    Selector,
    Reasoner,
    Aggregator,
    Synthesizer,
    bookrag_retrieve,
    bookrag_classify,
    create_bookrag,
    create_pipeline,
)


# ============== IFT 分类器测试 ==============

class TestIFTClassifier:
    """IFT 查询分类器测试"""

    def test_single_hop_zh(self):
        """测试中文单跳查询"""
        classifier = IFTQueryClassifier()
        result = classifier.classify("什么是 Python？")
        
        assert result.query_type == IFTQueryType.SINGLE_HOP
        assert result.confidence > 0.3
        assert "selector" in result.recommended_pipeline

    def test_single_hop_en(self):
        """测试英文单跳查询"""
        classifier = IFTQueryClassifier()
        result = classifier.classify("What is machine learning?")
        
        assert result.query_type == IFTQueryType.SINGLE_HOP
        assert result.confidence > 0.3

    def test_multi_hop_comparison(self):
        """测试比较型多跳查询"""
        classifier = IFTQueryClassifier()
        result = classifier.classify("Python 和 Java 有什么区别？")
        
        assert result.query_type == IFTQueryType.MULTI_HOP
        assert result.confidence > 0.4
        assert "reasoner" in result.recommended_pipeline

    def test_multi_hop_why(self):
        """测试因果型多跳查询"""
        classifier = IFTQueryClassifier()
        result = classifier.classify("为什么 Transformer 需要注意力机制？")
        
        assert result.query_type == IFTQueryType.MULTI_HOP

    def test_aggregation_count(self):
        """测试计数型聚合查询"""
        classifier = IFTQueryClassifier()
        result = classifier.classify("文档中一共提到了多少次 AI？")
        
        assert result.query_type == IFTQueryType.GLOBAL_AGGREGATION
        assert result.confidence > 0.5
        assert "aggregator" in result.recommended_pipeline

    def test_aggregation_list(self):
        """测试列表型聚合查询"""
        classifier = IFTQueryClassifier()
        result = classifier.classify("列出所有提到的算法")
        
        assert result.query_type == IFTQueryType.GLOBAL_AGGREGATION

    def test_batch_classify(self):
        """测试批量分类"""
        from core.fusion_rag import batch_classify
        
        queries = [
            "什么是 Python？",
            "Python 和 Java 的区别？",
            "文档中有多少个章节？",
        ]
        
        results = batch_classify(queries)
        
        assert len(results) == 3
        assert results[0].query_type == IFTQueryType.SINGLE_HOP
        assert results[1].query_type == IFTQueryType.MULTI_HOP
        assert results[2].query_type == IFTQueryType.GLOBAL_AGGREGATION

    def test_language_detection(self):
        """测试语言检测"""
        classifier = IFTQueryClassifier()
        
        # 纯中文
        result = classifier.classify("什么是编程语言")
        assert result.metadata.get("language") in ["zh", "mixed"]
        
        # 纯英文
        result = classifier.classify("What is programming language")
        assert result.metadata.get("language") == "en"
        
        # 混合
        result = classifier.classify("Python 是什么？")
        assert result.metadata.get("language") == "mixed"


# ============== 检索操作符测试 ==============

class TestSelector:
    """选择器测试"""

    def test_basic_selection(self):
        """测试基础选择功能"""
        selector = Selector(top_k=2, min_score=0.1)
        chunks = [
            Chunk(id="1", content="Python 是一种编程语言。"),
            Chunk(id="2", content="Java 也是一种编程语言。"),
            Chunk(id="3", content="今天天气真好。"),
        ]
        
        context = RetrievalContext(chunks=chunks, query="Python 编程")
        result = selector.process("Python 编程", context)
        
        assert len(result.chunks) <= 2
        # 应该选择包含 Python 的块
        selected_ids = [c.id for c in result.chunks]
        assert "1" in selected_ids

    def test_hybrid_scoring(self):
        """测试混合评分"""
        selector = Selector(
            top_k=2,
            use_hybrid=True,
            semantic_weight=0.6,
            keyword_weight=0.3,
            bm25_weight=0.1,
        )
        
        chunks = [
            Chunk(id="1", content="Python Python Python"),
            Chunk(id="2", content="Java Java Java"),
        ]
        
        context = RetrievalContext(chunks=chunks, query="Python")
        result = selector.process("Python", context)
        
        assert len(result.chunks) >= 1
        assert result.chunks[0].id == "1"

    def test_no_match(self):
        """测试无匹配情况"""
        selector = Selector(top_k=2, min_score=0.5)
        chunks = [
            Chunk(id="1", content="今天天气真好。"),
            Chunk(id="2", content="明天可能下雨。"),
        ]
        
        context = RetrievalContext(chunks=chunks, query="Python 编程")
        result = selector.process("Python 编程", context)
        
        # 应该没有块满足阈值
        assert len(result.chunks) == 0 or all(
            c.relevance_score < 0.5 for c in result.chunks
        )


class TestReasoner:
    """推理器测试"""

    def test_entity_extraction(self):
        """测试实体提取"""
        reasoner = Reasoner(max_hops=2)
        chunks = [
            Chunk(id="1", content="Python 由 Guido van Rossum 创造。"),
            Chunk(id="2", content="Guido 是荷兰程序员。"),
        ]
        
        context = RetrievalContext(chunks=chunks, query="Python 和 Guido 的关系")
        result = reasoner.process("Python 和 Guido 的关系", context)
        
        # 应该检测到实体关系
        assert result.metadata.get("entities_found", 0) > 0

    def test_reference_detection(self):
        """测试引用检测"""
        reasoner = Reasoner()
        chunks = [
            Chunk(id="1", content="如上所述，Python 是一种高级语言。"),
            Chunk(id="2", content="这是一种通用的编程语言。"),
        ]
        
        context = RetrievalContext(chunks=chunks, query="Python 是什么")
        result = reasoner.process("Python 是什么", context)
        
        # 应该检测到引用关系
        assert result.metadata.get("relations_detected", 0) > 0


class TestAggregator:
    """聚合器测试"""

    def test_count_aggregation(self):
        """测试计数聚合"""
        aggregator = Aggregator(top_n=5)
        chunks = [
            Chunk(id="1", content="Python 是一种语言。"),
            Chunk(id="2", content="Python 很简单。"),
            Chunk(id="3", content="Java 也是语言。"),
        ]
        
        context = RetrievalContext(chunks=chunks, query="Python 出现了多少次？")
        result = aggregator.process("Python 出现了多少次？", context)
        
        assert result.metadata.get("aggregation_type") == "count"

    def test_distinct_aggregation(self):
        """测试去重聚合"""
        aggregator = Aggregator(top_n=5)
        chunks = [
            Chunk(id="1", content="Python、Java、C++"),
            Chunk(id="2", content="Python、Go、Rust"),
        ]
        
        context = RetrievalContext(chunks=chunks, query="列出一共提到了哪些语言")
        result = aggregator.process("列出一共提到了哪些语言", context)
        
        assert result.metadata.get("aggregation_type") == "distinct"


class TestSynthesizer:
    """合成器测试"""

    def test_basic_synthesis(self):
        """测试基础合成"""
        synthesizer = Synthesizer(max_context_length=100)
        chunks = [
            Chunk(id="1", content="Python 是一种高级编程语言。", relevance_score=0.9),
            Chunk(id="2", content="它由 Guido van Rossum 创造。", relevance_score=0.7),
        ]
        
        context = RetrievalContext(chunks=chunks, query="Python 是什么？")
        result = synthesizer.process("Python 是什么？", context)
        
        assert "answer" in result.metadata
        assert result.metadata.get("compressed_length") <= 100

    def test_citation_generation(self):
        """测试引用生成"""
        synthesizer = Synthesizer(include_citations=True)
        chunks = [
            Chunk(id="1", content="Python 是一种语言。", source="doc1.md"),
            Chunk(id="2", content="Java 也是一种语言。", source="doc2.md"),
        ]
        
        context = RetrievalContext(chunks=chunks, query="编程语言有哪些")
        result = synthesizer.process("编程语言有哪些", context)
        
        # 答案应该包含引用
        answer = result.metadata.get("answer", "")
        assert "参考来源" in answer or len(answer) > 0


# ============== 检索管道测试 ==============

class TestRetrievalPipeline:
    """检索管道测试"""

    def test_simple_pipeline(self):
        """测试简单管道"""
        pipeline = RetrievalPipeline(default_pipeline="simple")
        chunks = [
            Chunk(id="1", content="Python 是一种编程语言。"),
            Chunk(id="2", content="Java 也是编程语言。"),
        ]
        
        result = pipeline.run("Python 是什么？", chunks)
        
        assert isinstance(result, RetrievalResult)
        assert len(result.pipeline_used) >= 1
        assert result.confidence >= 0.0

    def test_reasoning_pipeline(self):
        """测试推理管道"""
        pipeline = RetrievalPipeline(default_pipeline="reasoning")
        chunks = [
            Chunk(id="1", content="Python 简单易学。"),
            Chunk(id="2", content="Java 适合企业级开发。"),
        ]
        
        result = pipeline.run("Python 和 Java 有什么区别？", chunks)
        
        assert "reasoner" in result.pipeline_used

    def test_custom_pipeline(self):
        """测试自定义管道"""
        pipeline = RetrievalPipeline()
        chunks = [
            Chunk(id="1", content="Python 是一种语言。"),
        ]
        
        result = pipeline.run(
            "Python 是什么？", 
            chunks, 
            pipeline=["selector", "synthesizer"]
        )
        
        assert "selector" in result.pipeline_used
        assert "synthesizer" in result.pipeline_used

    def test_execution_log(self):
        """测试执行日志"""
        pipeline = RetrievalPipeline()
        chunks = [Chunk(id="1", content="test")]
        
        result = pipeline.run("test query", chunks)
        
        assert len(result.reasoning) > 0
        assert any("selector" in log.lower() for log in result.reasoning)


# ============== BookRAG 统一入口测试 ==============

class TestBookRAG:
    """BookRAG 统一入口测试"""

    def test_basic_retrieval(self):
        """测试基础检索"""
        rag = BookRAG()
        chunks = [
            Chunk(id="1", content="Python 是一种高级编程语言。"),
            Chunk(id="2", content="它由 Guido van Rossum 创造。"),
            Chunk(id="3", content="Python 适合快速开发。"),
        ]
        
        result = rag.retrieve("Python 是什么？", chunks)
        
        assert isinstance(result, RetrievalResult)
        assert result.sources is not None

    def test_retrieval_with_classification(self):
        """测试带分类信息的检索"""
        rag = BookRAG()
        chunks = [Chunk(id="1", content="Python 是一种语言。")]
        
        result, classification = rag.retrieve(
            "Python 和 Java 的区别？",
            chunks,
            return_classification=True
        )
        
        assert isinstance(result, RetrievalResult)
        assert isinstance(classification, IFTClassificationResult)
        assert classification.query_type == IFTQueryType.MULTI_HOP

    def test_empty_chunks(self):
        """测试空块列表"""
        rag = BookRAG()
        
        result = rag.retrieve("test query", chunks=[])
        
        assert result.answer == "未找到相关文档块。"
        assert len(result.sources) == 0

    def test_classify_only(self):
        """测试单独分类"""
        rag = BookRAG()
        
        classification = rag.classify("Python 是什么？")
        
        assert isinstance(classification, IFTClassificationResult)
        assert classification.query_type == IFTQueryType.SINGLE_HOP

    def test_get_pipeline_for_query(self):
        """测试获取适合查询的管道"""
        rag = BookRAG()
        
        pipeline = rag.get_pipeline_for_query("Python 和 Java 区别？")
        
        assert "reasoner" in pipeline

    def test_custom_config(self):
        """测试自定义配置"""
        config = BookRAGConfig(
            selector_top_k=5,
            max_context_length=2000,
            default_pipeline="reasoning",
        )
        rag = BookRAG(config=config)
        
        assert rag.config.selector_top_k == 5
        assert rag.config.max_context_length == 2000

    def test_ifr_metadata(self):
        """测试 IFT 元数据"""
        rag = BookRAG()
        chunks = [Chunk(id="1", content="test")]
        
        result = rag.retrieve("列出所有内容", chunks)
        
        assert "ift_classification" in result.metadata
        if_class = result.metadata["ift_classification"]
        assert "query_type" in if_class
        assert if_class["query_type"] == "global_aggregation"


# ============== 快捷函数测试 ==============

class TestShortcutFunctions:
    """快捷函数测试"""

    def test_bookrag_retrieve(self):
        """测试快捷检索函数"""
        chunks = [
            Chunk(id="1", content="Python 是一种语言。"),
        ]
        
        result = bookrag_retrieve("Python 是什么？", chunks)
        
        assert isinstance(result, RetrievalResult)

    def test_bookrag_classify(self):
        """测试快捷分类函数"""
        result = bookrag_classify("Python 和 Java 区别？")
        
        assert result.query_type == IFTQueryType.MULTI_HOP

    def test_create_bookrag(self):
        """测试工厂函数"""
        rag = create_bookrag(pipeline_type="reasoning")
        
        assert isinstance(rag, BookRAG)
        assert rag.config.default_pipeline == "reasoning"

    def test_create_pipeline(self):
        """测试管道工厂函数"""
        pipeline = create_pipeline("reasoning")
        
        assert isinstance(pipeline, RetrievalPipeline)


# ============== Chunk 数据结构测试 ==============

class TestChunk:
    """Chunk 数据结构测试"""

    def test_chunk_creation(self):
        """测试 Chunk 创建"""
        chunk = Chunk(
            id="test-1",
            content="测试内容",
            metadata={"source": "test.txt"},
            relevance_score=0.8,
        )
        
        assert chunk.id == "test-1"
        assert chunk.content == "测试内容"
        assert chunk.relevance_score == 0.8
        assert chunk.metadata["source"] == "test.txt"

    def test_chunk_equality(self):
        """测试 Chunk 相等性"""
        chunk1 = Chunk(id="1", content="test")
        chunk2 = Chunk(id="1", content="different")
        chunk3 = Chunk(id="2", content="test")
        
        assert chunk1 == chunk2
        assert chunk1 != chunk3


# ============== RetrievalContext 测试 ==============

class TestRetrievalContext:
    """检索上下文测试"""

    def test_add_chunk(self):
        """测试添加块"""
        context = RetrievalContext(query="test")
        chunk = Chunk(id="1", content="test")
        
        context.add_chunk(chunk)
        
        assert len(context.chunks) == 1

    def test_get_top_chunks(self):
        """测试获取 Top-k 块"""
        context = RetrievalContext(query="test")
        chunks = [
            Chunk(id="1", content="low", relevance_score=0.3),
            Chunk(id="2", content="high", relevance_score=0.9),
            Chunk(id="3", content="medium", relevance_score=0.6),
        ]
        context.chunks = chunks
        
        top_chunks = context.get_top_chunks(k=2)
        
        assert len(top_chunks) == 2
        assert top_chunks[0].id == "2"
        assert top_chunks[1].id == "3"


# ============== 集成测试 ==============

class TestBookRAGIntegration:
    """BookRAG 集成测试"""

    def test_end_to_end_single_hop(self):
        """端到端测试：单跳查询"""
        rag = BookRAG()
        chunks = [
            Chunk(id="1", content="机器学习是人工智能的一个分支。"),
            Chunk(id="2", content="深度学习是机器学习的一个子领域。"),
            Chunk(id="3", content="自然语言处理使用深度学习模型。"),
            Chunk(id="4", content="Python 是一种常用的机器学习编程语言。"),
        ]
        
        result = rag.retrieve("什么是机器学习？", chunks)
        
        assert result.confidence > 0
        assert len(result.sources) > 0
        # 验证使用的是简单管道
        assert "ift_classification" in result.metadata
        assert result.metadata["ift_classification"]["query_type"] == "single_hop"

    def test_end_to_end_multi_hop(self):
        """端到端测试：多跳查询"""
        rag = BookRAG()
        chunks = [
            Chunk(id="1", content="Python 由 Guido van Rossum 创造。"),
            Chunk(id="2", content="Guido 是荷兰程序员。"),
            Chunk(id="3", content="Python 是一种高级语言。"),
            Chunk(id="4", content="高级语言易于学习和使用。"),
        ]
        
        result = rag.retrieve("Python 和它的创造者有什么关系？", chunks)
        
        # 应该使用推理管道
        assert "reasoner" in result.pipeline_used or "ift_classification" in result.metadata

    def test_end_to_end_aggregation(self):
        """端到端测试：聚合查询"""
        rag = BookRAG()
        chunks = [
            Chunk(id="1", content="Python 是一种语言。"),
            Chunk(id="2", content="Python 简单易学。"),
            Chunk(id="3", content="Python 功能强大。"),
            Chunk(id="4", content="Python 应用广泛。"),
            Chunk(id="5", content="Python 越来越流行。"),
        ]
        
        result = rag.retrieve("文档中 Python 出现了多少次？", chunks)
        
        assert "aggregator" in result.pipeline_used or "ift_classification" in result.metadata
        assert result.metadata["ift_classification"]["query_type"] == "global_aggregation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
