"""
LLM Wiki 适配器

实现统一知识检索接口，使 LLM Wiki 与 FusionRAG 功能对等。
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

# 导入 LLM Wiki 核心组件
from .integration import LLMWikiIntegration


class LLVWikiAdapter(IKnowledgeRetriever):
    """
    LLM Wiki 适配器，实现统一知识检索接口
    """
    
    def __init__(self, llm_wiki: Optional[LLMWikiIntegration] = None):
        """
        初始化适配器
        
        Args:
            llm_wiki: LLM Wiki 集成实例（可选，自动创建）
        """
        if llm_wiki:
            self.llm_wiki = llm_wiki
        else:
            self.llm_wiki = LLMWikiIntegration()
        
        # 目标行业
        self.target_industry = "通用"
        
        print("[LLMWikiAdapter] 初始化完成")
    
    async def search(self, query: str, **kwargs) -> List[SearchResult]:
        """基础搜索"""
        top_k = kwargs.get("top_k", 10)
        
        # 使用 LLM Wiki 的搜索功能
        results = await self.llm_wiki.search(query, top_k=top_k)
        
        return [
            SearchResult(
                content=r.get("content", ""),
                score=r.get("score", 0.0),
                source=r.get("source", "llm_wiki"),
                metadata={
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "path": r.get("path")
                },
                citations=r.get("citations", [])
            )
            for r in results
        ]
    
    async def search_with_governance(self, query: str, industry: str = "", **kwargs) -> List[SearchResult]:
        """带行业治理的搜索"""
        top_k = kwargs.get("top_k", 10)
        
        # 使用 LLM Wiki 的行业治理搜索
        results = await self.llm_wiki.search_with_governance(query, industry, top_k=top_k)
        
        return [
            SearchResult(
                content=r.get("content", ""),
                score=r.get("score", 0.0),
                source=r.get("source", "llm_wiki"),
                metadata={
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "path": r.get("path"),
                    "industry": r.get("industry")
                },
                citations=r.get("citations", [])
            )
            for r in results
        ]
    
    async def search_with_triple_chain(self, query: str) -> QueryResult:
        """带三重链验证的搜索"""
        result = await self.llm_wiki.search_with_triple_chain(query)
        
        # 构建三重链结果
        triple_chain = TripleChainResult(
            thought_chain=result.get("thought_chain", ""),
            causal_chain=result.get("causal_chain", ""),
            evidence_chain=result.get("evidence_chain", ""),
            is_valid=result.get("is_valid", False),
            confidence=result.get("confidence", 0.0)
        )
        
        return QueryResult(
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            confidence=result.get("confidence", 0.0),
            triple_chain=triple_chain,
            related_topics=result.get("related_topics", [])
        )
    
    async def add_document(self, content: str, metadata: Dict[str, Any] = None):
        """添加文档"""
        if metadata is None:
            metadata = {}
        
        # 使用 LLM Wiki 的添加文档功能
        await self.llm_wiki.add_document(
            content=content,
            title=metadata.get("title", ""),
            industry=metadata.get("industry", self.target_industry)
        )
    
    async def add_term(self, term: str, category: str, synonyms: List[str] = None):
        """添加术语"""
        if synonyms is None:
            synonyms = []
        
        # 使用 LLM Wiki 的添加术语功能
        await self.llm_wiki.add_synonym(term, synonyms)
    
    async def extract_terms(self, text: str) -> List[TermInfo]:
        """从文本中抽取术语"""
        # 使用 LLM Wiki 的术语抽取功能
        terms = await self.llm_wiki.extract_terms_from_text(text, self.target_industry)
        
        return [
            TermInfo(
                term=t.get("term", ""),
                category=t.get("category", ""),
                synonyms=t.get("synonyms", []),
                confidence=t.get("confidence", 0.0)
            )
            for t in terms
        ]
    
    async def set_target_industry(self, industry: str):
        """设置目标行业"""
        self.target_industry = industry
        # 同步到 LLM Wiki
        await self.llm_wiki.set_target_industry(industry)
        print(f"[LLMWikiAdapter] 目标行业已设置为: {industry}")
    
    async def record_feedback(self, query: str, answer: str, rating: int, comment: str = ""):
        """记录反馈"""
        # 使用 LLM Wiki 的反馈记录功能
        await self.llm_wiki.record_feedback(query, answer, rating, comment)
    
    async def build_industry_dictionary(self, documents: List[str], industry: str) -> Dict[str, TermInfo]:
        """构建行业词典"""
        # 使用 LLM Wiki 的词典构建功能
        dictionary = await self.llm_wiki.build_industry_dictionary(documents, industry)
        
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


def create_llm_wiki_adapter() -> LLVWikiAdapter:
    """创建 LLM Wiki 适配器实例"""
    return LLVWikiAdapter()


__all__ = [
    "LLVWikiAdapter",
    "create_llm_wiki_adapter"
]