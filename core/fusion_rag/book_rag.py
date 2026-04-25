"""
BookRAG - 统一入口模块
BookRAG Unified Entry Point

整合 IFT 分类器和检索管道，提供统一的 RAG 接口。
"""

from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field

from .ift_classifier import (
    IFTQueryClassifier,
    IFTQueryType,
    IFTClassificationResult,
    classify_ift_query,
)
from .retrieval_operators import (
    Chunk,
    RetrievalPipeline,
    RetrievalResult,
    RetrievalContext,
    Selector,
    Reasoner,
    Aggregator,
    Synthesizer,
    create_pipeline,
)


@dataclass
class BookRAGConfig:
    """BookRAG 配置"""
    # 选择器配置
    selector_top_k: int = 10
    selector_min_score: float = 0.1
    use_hybrid_similarity: bool = True
    
    # 推理器配置
    max_reasoning_hops: int = 3
    relation_threshold: float = 0.3
    
    # 聚合器配置
    aggregation_top_n: int = 20
    
    # 合成器配置
    max_context_length: int = 4000
    include_citations: bool = True
    
    # 默认管道
    default_pipeline: str = "auto"  # "auto" 会根据 IFT 类型自动选择
    
    # 管道映射
    pipeline_mapping: Dict[str, List[str]] = field(default_factory=lambda: {
        "single_hop": ["selector", "synthesizer"],
        "multi_hop": ["selector", "reasoner", "synthesizer"],
        "global_aggregation": ["selector", "aggregator", "synthesizer"],
    })


class BookRAG:
    """
    BookRAG 统一检索接口
    
    Example:
        >>> rag = BookRAG()
        >>> result = rag.retrieve("Python 和 Java 有什么区别？", chunks)
        >>> print(result.answer)
    """
    
    def __init__(
        self,
        config: Optional[BookRAGConfig] = None,
        knowledge_base: Optional[Any] = None,
    ):
        """
        初始化 BookRAG
        
        Args:
            config: BookRAG 配置
            knowledge_base: 关联的知识库（可选）
        """
        self.config = config or BookRAGConfig()
        self.knowledge_base = knowledge_base
        
        # 初始化组件
        self.classifier = IFTQueryClassifier()
        
        # 初始化管道
        self._init_pipeline()
    
    def _init_pipeline(self):
        """初始化检索管道"""
        # 创建操作符
        operators = {
            "selector": Selector(
                top_k=self.config.selector_top_k,
                min_score=self.config.selector_min_score,
                use_hybrid=self.config.use_hybrid_similarity,
            ),
            "reasoner": Reasoner(
                max_hops=self.config.max_reasoning_hops,
                relation_threshold=self.config.relation_threshold,
            ),
            "aggregator": Aggregator(
                top_n=self.config.aggregation_top_n,
            ),
            "synthesizer": Synthesizer(
                max_context_length=self.config.max_context_length,
                include_citations=self.config.include_citations,
            ),
        }
        
        self.pipeline = RetrievalPipeline(
            operators=operators,
            default_pipeline="simple",
        )
    
    def retrieve(
        self,
        query: str,
        chunks: Optional[List[Chunk]] = None,
        knowledge_base: Optional[Any] = None,
        return_classification: bool = False,
    ) -> Union[RetrievalResult, tuple]:
        """
        执行检索
        
        Args:
            query: 用户查询
            chunks: 文档块列表
            knowledge_base: 知识库（如果初始化时未提供）
            return_classification: 是否返回 IFT 分类结果
        
        Returns:
            RetrievalResult 或 (RetrievalResult, IFTClassificationResult)
        """
        # 获取块
        if chunks is None:
            if self.knowledge_base:
                chunks = self._fetch_chunks(self.knowledge_base, query)
            elif knowledge_base:
                chunks = self._fetch_chunks(knowledge_base, query)
            else:
                raise ValueError("必须提供 chunks 或 knowledge_base")
        
        if not chunks:
            result = RetrievalResult(
                answer="未找到相关文档块。",
                sources=[],
                confidence=0.0,
                pipeline_used=[],
            )
            return (result, None) if return_classification else result
        
        # 1. IFT 分类
        classification = self.classifier.classify(query)
        
        # 2. 确定管道
        if self.config.default_pipeline == "auto":
            pipeline = self.config.pipeline_mapping.get(
                classification.query_type.value,
                self.config.pipeline_mapping["single_hop"]
            )
        else:
            pipeline = self.config.default_pipeline
        
        # 3. 执行检索
        result = self.pipeline.run(query, chunks, pipeline=pipeline)
        
        # 4. 更新结果元数据
        result.metadata["ift_classification"] = {
            "query_type": classification.query_type.value,
            "confidence": classification.confidence,
            "reasoning": classification.reasoning,
        }
        
        if return_classification:
            return result, classification
        else:
            return result
    
    def _fetch_chunks(
        self, 
        knowledge_base: Any, 
        query: str
    ) -> List[Chunk]:
        """
        从知识库获取块（可被子类重写）
        
        Args:
            knowledge_base: 知识库对象
            query: 查询文本
            
        Returns:
            文档块列表
        """
        # 默认实现：检查知识库接口
        if hasattr(knowledge_base, 'search'):
            raw_chunks = knowledge_base.search(query)
        elif hasattr(knowledge_base, 'retrieve'):
            raw_chunks = knowledge_base.retrieve(query)
        elif hasattr(knowledge_base, 'get_chunks'):
            raw_chunks = knowledge_base.get_chunks(query)
        else:
            # 尝试通用接口
            raw_chunks = knowledge_base.get(query, [])
        
        # 转换为 Chunk 对象
        chunks = []
        for i, chunk in enumerate(raw_chunks):
            if isinstance(chunk, Chunk):
                chunks.append(chunk)
            elif isinstance(chunk, dict):
                chunks.append(Chunk(
                    id=chunk.get("id", f"chunk_{i}"),
                    content=chunk.get("content", str(chunk)),
                    metadata=chunk.get("metadata", {}),
                ))
            else:
                chunks.append(Chunk(
                    id=f"chunk_{i}",
                    content=str(chunk),
                ))
        
        return chunks
    
    def classify(self, query: str) -> IFTClassificationResult:
        """
        单独进行 IFT 分类
        
        Args:
            query: 查询文本
            
        Returns:
            IFTClassificationResult
        """
        return self.classifier.classify(query)
    
    def get_pipeline_for_query(self, query: str) -> List[str]:
        """
        获取适合查询的管道配置
        
        Args:
            query: 查询文本
            
        Returns:
            管道配置列表
        """
        classification = self.classifier.classify(query)
        return self.config.pipeline_mapping.get(
            classification.query_type.value,
            self.config.pipeline_mapping["single_hop"]
        )


# ============== 快捷函数 ==============

def bookrag_retrieve(
    query: str,
    chunks: List[Chunk],
) -> RetrievalResult:
    """
    BookRAG 快捷检索函数
    
    Example:
        >>> chunks = [Chunk(id="1", content="...")]
        >>> result = bookrag_retrieve("Python 是什么？", chunks)
    """
    rag = BookRAG()
    return rag.retrieve(query, chunks)


def bookrag_classify(query: str) -> IFTClassificationResult:
    """
    BookRAG 快捷分类函数
    
    Example:
        >>> result = bookrag_classify("Python 和 Java 区别")
        >>> print(result.query_type)  # MULTI_HOP
    """
    return classify_ift_query(query)


# ============== 工厂函数 ==============

def create_bookrag(
    pipeline_type: str = "auto",
    **kwargs,
) -> BookRAG:
    """
    创建 BookRAG 实例的工厂函数
    
    Args:
        pipeline_type: 管道类型 ("auto", "simple", "reasoning", "aggregation", "full")
        **kwargs: 其他配置参数
    
    Returns:
        BookRAG 实例
    """
    config = BookRAGConfig()
    
    if pipeline_type != "auto":
        config.default_pipeline = pipeline_type
    
    # 应用其他配置
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    return BookRAG(config=config)
