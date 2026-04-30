"""
FusionRAG 适配器

实现统一知识检索接口，使 FusionRAG 与 LLM Wiki 功能对等。
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# 导入统一接口
from client.src.business.unified_knowledge_interface import (
    IKnowledgeRetriever,
    SearchResult,
    TripleChainResult,
    TermInfo,
    QueryResult
)

# 导入 FusionRAG 核心组件
from . import (
    FusionRAG,
    DeepKETermExtractor,
    get_term_extractor,
    get_dict_builder
)


class FusionRAGAdapter(IKnowledgeRetriever):
    """
    FusionRAG 适配器，实现统一知识检索接口
    """
    
    def __init__(self, fusion_rag: Optional[FusionRAG] = None):
        """
        初始化适配器
        
        Args:
            fusion_rag: FusionRAG 实例（可选，自动创建）
        """
        if fusion_rag:
            self.fusion_rag = fusion_rag
        else:
            self.fusion_rag = FusionRAG()
        
        # 初始化术语抽取器
        try:
            self.term_extractor = get_term_extractor()
            print("[FusionRAGAdapter] 已初始化术语抽取器")
        except Exception as e:
            self.term_extractor = None
            print(f"[FusionRAGAdapter] 术语抽取器初始化失败: {e}")
        
        print("[FusionRAGAdapter] 初始化完成")
    
    async def search(self, query: str, **kwargs) -> List[SearchResult]:
        """基础搜索"""
        top_k = kwargs.get("top_k", 10)
        results = self.fusion_rag.search(query, top_k=top_k)
        
        return [
            SearchResult(
                content=r.get("content", ""),
                score=r.get("score", 0.0),
                source=r.get("source_type", "unknown"),
                metadata={
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "tier": r.get("tier"),
                    "source_attribution": r.get("source_attribution")
                },
                citations=[]
            )
            for r in results
        ]
    
    async def search_with_governance(self, query: str, industry: str = "", **kwargs) -> List[SearchResult]:
        """带行业治理的搜索"""
        # 设置目标行业
        if industry:
            original_industry = self.fusion_rag.target_industry
            self.fusion_rag.target_industry = industry
        
        try:
            top_k = kwargs.get("top_k", 10)
            results = self.fusion_rag.search(query, top_k=top_k)
            
            return [
                SearchResult(
                    content=r.get("content", ""),
                    score=r.get("score", 0.0),
                    source=r.get("source_type", "unknown"),
                    metadata={
                        "id": r.get("id"),
                        "title": r.get("title"),
                        "tier": r.get("tier"),
                        "source_attribution": r.get("source_attribution")
                    },
                    citations=[]
                )
                for r in results
            ]
        finally:
            if industry:
                self.fusion_rag.target_industry = original_industry
    
    async def search_with_triple_chain(self, query: str) -> QueryResult:
        """带三重链验证的搜索"""
        result = self.fusion_rag.search_with_triple_chain(query)
        
        # 构建三重链结果
        triple_chain = TripleChainResult(
            thought_chain=str(result.get("reasoning", "")),
            causal_chain="",  # FusionRAG 当前不直接返回因果链
            evidence_chain=str([e.get("content_snippet", "") for e in result.get("evidence", [])]),
            is_valid=result.get("validation_passed", False),
            confidence=result.get("overall_confidence", 0.0)
        )
        
        # 提取来源
        sources = [e.get("title", "") for e in result.get("evidence", [])]
        
        return QueryResult(
            answer=result.get("answer", ""),
            sources=sources,
            confidence=result.get("overall_confidence", 0.0),
            triple_chain=triple_chain,
            related_topics=[]
        )
    
    async def add_document(self, content: str, metadata: Dict[str, Any] = None):
        """添加文档"""
        # FusionRAG 的文档添加通过治理模块进行
        if metadata is None:
            metadata = {}
        
        # 使用行业治理模块添加文档
        self.fusion_rag.governance.add_document(
            content=content,
            title=metadata.get("title", ""),
            source_type=metadata.get("source_type", "unknown"),
            industry=metadata.get("industry", self.fusion_rag.target_industry)
        )
    
    async def add_term(self, term: str, category: str, synonyms: List[str] = None):
        """添加术语"""
        if synonyms is None:
            synonyms = []
        
        # 使用行业治理模块添加术语
        self.fusion_rag.governance.add_term(term, category, synonyms)
        
        # 同时添加到方言词典
        for synonym in synonyms:
            self.fusion_rag.dialect.add_entry(
                term=term,
                alias=synonym,
                industry=self.fusion_rag.target_industry
            )
    
    async def extract_terms(self, text: str) -> List[TermInfo]:
        """从文本中抽取术语"""
        if not self.term_extractor:
            return []
        
        # 使用 DeepKE-LLM 抽取术语
        terms = self.term_extractor.extract_terms_from_text(text, self.fusion_rag.target_industry)
        
        return [
            TermInfo(
                term=t.get("term", ""),
                category=t.get("category", ""),
                synonyms=[],
                confidence=t.get("confidence", 0.0)
            )
            for t in terms
        ]
    
    async def set_target_industry(self, industry: str):
        """设置目标行业"""
        self.fusion_rag.target_industry = industry
        print(f"[FusionRAGAdapter] 目标行业已设置为: {industry}")
    
    async def record_feedback(self, query: str, answer: str, rating: int, comment: str = ""):
        """记录反馈"""
        # 将评分转换为反馈类型
        feedback_type = "positive" if rating >= 4 else "negative" if rating <= 2 else "neutral"
        
        # 生成唯一结果ID
        result_id = f"result_{hash(answer) % 1000000}"
        
        # 记录反馈
        self.fusion_rag.record_feedback(
            query=query,
            result_id=result_id,
            result_content=answer,
            feedback_type=feedback_type,
            reason=comment
        )
    
    async def build_industry_dictionary(self, documents: List[str], industry: str) -> Dict[str, TermInfo]:
        """构建行业词典"""
        if not self.term_extractor:
            return {}
        
        # 使用行业词典构建器
        from . import get_dict_builder
        dict_builder = get_dict_builder()
        
        # 构建词典
        dictionary = dict_builder.build_industry_dictionary(documents, industry)
        
        # 转换为统一格式
        result = {}
        for term, info in dictionary.items():
            result[term] = TermInfo(
                term=term,
                category=info.get("category", ""),
                synonyms=info.get("synonyms", []),
                definition=info.get("definition", ""),
                confidence=info.get("confidence", 0.0)
            )
        
        return result


def create_fusion_rag_adapter() -> FusionRAGAdapter:
    """创建 FusionRAG 适配器实例"""
    return FusionRAGAdapter()


__all__ = [
    "FusionRAGAdapter",
    "create_fusion_rag_adapter"
]