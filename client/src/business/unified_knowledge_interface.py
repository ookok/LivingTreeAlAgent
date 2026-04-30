"""
统一知识检索接口 (Unified Knowledge Interface)

提供 FusionRAG 和 LLM Wiki 的统一访问接口，确保两者功能对等。

设计理念：
1. 抽象层：定义统一的接口规范
2. 适配器模式：让 FusionRAG 和 LLM Wiki 都实现同一接口
3. 策略模式：支持运行时切换实现
4. 功能对等：确保两者提供相同的 API

核心功能：
- 知识检索（支持行业过滤、分层检索）
- 三重链验证（思维链、因果链、证据链）
- 行业治理（术语归一化、行业过滤）
- 负反馈学习
- DeepKE-LLM 术语抽取
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


class KnowledgeProvider(Enum):
    """知识提供者枚举"""
    FUSION_RAG = "fusion_rag"
    LLM_WIKI = "llm_wiki"


@dataclass
class SearchResult:
    """搜索结果"""
    content: str
    score: float
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    citations: List[str] = field(default_factory=list)


@dataclass
class TripleChainResult:
    """三重链验证结果"""
    thought_chain: str
    causal_chain: str
    evidence_chain: str
    is_valid: bool
    confidence: float


@dataclass
class TermInfo:
    """术语信息"""
    term: str
    category: str
    synonyms: List[str] = field(default_factory=list)
    definition: str = ""
    confidence: float = 0.0


@dataclass
class QueryResult:
    """查询结果"""
    answer: str
    sources: List[str]
    confidence: float
    triple_chain: Optional[TripleChainResult] = None
    related_topics: List[str] = field(default_factory=list)


class IKnowledgeRetriever(ABC):
    """
    知识检索器接口
    
    FusionRAG 和 LLM Wiki 都需要实现此接口，确保功能对等。
    """
    
    @abstractmethod
    async def search(self, query: str, **kwargs) -> List[SearchResult]:
        """
        基础搜索
        
        Args:
            query: 查询字符串
            **kwargs: 额外参数（如 top_k, industry 等）
        
        Returns:
            搜索结果列表
        """
        pass
    
    @abstractmethod
    async def search_with_governance(self, query: str, industry: str = "", **kwargs) -> List[SearchResult]:
        """
        带行业治理的搜索
        
        Args:
            query: 查询字符串
            industry: 目标行业
            **kwargs: 额外参数
        
        Returns:
            搜索结果列表（已应用行业过滤）
        """
        pass
    
    @abstractmethod
    async def search_with_triple_chain(self, query: str) -> QueryResult:
        """
        带三重链验证的搜索
        
        Args:
            query: 查询字符串
        
        Returns:
            查询结果（包含三重链验证）
        """
        pass
    
    @abstractmethod
    async def add_document(self, content: str, metadata: Dict[str, Any] = None):
        """
        添加文档
        
        Args:
            content: 文档内容
            metadata: 文档元数据
        """
        pass
    
    @abstractmethod
    async def add_term(self, term: str, category: str, synonyms: List[str] = None):
        """
        添加术语
        
        Args:
            term: 术语名称
            category: 术语类别
            synonyms: 同义词列表
        """
        pass
    
    @abstractmethod
    async def extract_terms(self, text: str) -> List[TermInfo]:
        """
        从文本中抽取术语（使用 DeepKE-LLM）
        
        Args:
            text: 输入文本
        
        Returns:
            抽取的术语列表
        """
        pass
    
    @abstractmethod
    async def set_target_industry(self, industry: str):
        """
        设置目标行业
        
        Args:
            industry: 行业名称
        """
        pass
    
    @abstractmethod
    async def record_feedback(self, query: str, answer: str, rating: int, comment: str = ""):
        """
        记录反馈
        
        Args:
            query: 查询内容
            answer: 回答内容
            rating: 评分（1-5）
            comment: 评论
        """
        pass
    
    @abstractmethod
    async def build_industry_dictionary(self, documents: List[str], industry: str) -> Dict[str, TermInfo]:
        """
        构建行业词典
        
        Args:
            documents: 文档列表
            industry: 行业名称
        
        Returns:
            行业词典
        """
        pass


class UnifiedKnowledgeManager:
    """
    统一知识管理器
    
    提供 FusionRAG 和 LLM Wiki 的统一访问入口，支持运行时切换。
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        # 当前活跃的知识提供者
        self._current_provider = KnowledgeProvider.FUSION_RAG
        
        # 注册的提供者实例
        self._providers: Dict[KnowledgeProvider, IKnowledgeRetriever] = {}
        
        # 初始化时尝试加载默认提供者
        self._init_default_providers()
        
        print("[UnifiedKnowledgeManager] 初始化完成")
        self._initialized = True
    
    def _init_default_providers(self):
        """初始化默认知识提供者（使用适配器）"""
        # 尝试注册 FusionRAG 适配器
        try:
            from client.src.business.fusion_rag.adapter import create_fusion_rag_adapter
            fusion_rag_adapter = create_fusion_rag_adapter()
            self.register_provider(KnowledgeProvider.FUSION_RAG, fusion_rag_adapter)
            print("[UnifiedKnowledgeManager] 已注册 FusionRAG 适配器")
        except Exception as e:
            print(f"[UnifiedKnowledgeManager] FusionRAG 适配器注册失败: {e}")
        
        # 尝试注册 LLM Wiki 适配器
        try:
            from client.src.business.llm_wiki.adapter import create_llm_wiki_adapter
            llm_wiki_adapter = create_llm_wiki_adapter()
            self.register_provider(KnowledgeProvider.LLM_WIKI, llm_wiki_adapter)
            print("[UnifiedKnowledgeManager] 已注册 LLM Wiki 适配器")
        except Exception as e:
            print(f"[UnifiedKnowledgeManager] LLM Wiki 适配器注册失败: {e}")
    
    def register_provider(self, provider: KnowledgeProvider, instance: IKnowledgeRetriever):
        """
        注册知识提供者
        
        Args:
            provider: 提供者类型
            instance: 提供者实例
        """
        self._providers[provider] = instance
    
    def set_provider(self, provider: KnowledgeProvider):
        """
        设置当前活跃的知识提供者
        
        Args:
            provider: 提供者类型
        """
        if provider in self._providers:
            self._current_provider = provider
            print(f"[UnifiedKnowledgeManager] 当前提供者已切换为: {provider.value}")
        else:
            raise ValueError(f"未注册的知识提供者: {provider}")
    
    def get_current_provider(self) -> KnowledgeProvider:
        """获取当前活跃的知识提供者"""
        return self._current_provider
    
    def get_available_providers(self) -> List[KnowledgeProvider]:
        """获取所有可用的知识提供者"""
        return list(self._providers.keys())
    
    def _get_provider(self) -> IKnowledgeRetriever:
        """获取当前提供者实例"""
        if self._current_provider in self._providers:
            return self._providers[self._current_provider]
        raise RuntimeError("当前没有可用的知识提供者")
    
    # ============ 统一 API 方法 ============
    
    async def search(self, query: str, **kwargs) -> List[SearchResult]:
        """基础搜索"""
        return await self._get_provider().search(query, **kwargs)
    
    async def search_with_governance(self, query: str, industry: str = "", **kwargs) -> List[SearchResult]:
        """带行业治理的搜索"""
        return await self._get_provider().search_with_governance(query, industry, **kwargs)
    
    async def search_with_triple_chain(self, query: str) -> QueryResult:
        """带三重链验证的搜索"""
        return await self._get_provider().search_with_triple_chain(query)
    
    async def add_document(self, content: str, metadata: Dict[str, Any] = None):
        """添加文档"""
        await self._get_provider().add_document(content, metadata)
    
    async def add_term(self, term: str, category: str, synonyms: List[str] = None):
        """添加术语"""
        await self._get_provider().add_term(term, category, synonyms)
    
    async def extract_terms(self, text: str) -> List[TermInfo]:
        """从文本中抽取术语"""
        return await self._get_provider().extract_terms(text)
    
    async def set_target_industry(self, industry: str):
        """设置目标行业"""
        await self._get_provider().set_target_industry(industry)
    
    async def record_feedback(self, query: str, answer: str, rating: int, comment: str = ""):
        """记录反馈"""
        await self._get_provider().record_feedback(query, answer, rating, comment)
    
    async def build_industry_dictionary(self, documents: List[str], industry: str) -> Dict[str, TermInfo]:
        """构建行业词典"""
        return await self._get_provider().build_industry_dictionary(documents, industry)
    
    # ============ 跨提供者操作 ============
    
    async def sync_between_providers(self, source: KnowledgeProvider, target: KnowledgeProvider):
        """
        在两个提供者之间同步数据
        
        Args:
            source: 源提供者
            target: 目标提供者
        """
        if source not in self._providers or target not in self._providers:
            raise ValueError("无效的提供者")
        
        source_provider = self._providers[source]
        target_provider = self._providers[target]
        
        # 同步术语（简化实现）
        print(f"[UnifiedKnowledgeManager] 正在从 {source.value} 同步到 {target.value}")
        
        # 实际同步逻辑需要根据具体实现来写
        # 这里只是一个示例框架
    
    async def compare_results(self, query: str) -> Dict[str, QueryResult]:
        """
        比较不同提供者的查询结果
        
        Args:
            query: 查询字符串
        
        Returns:
            各提供者的查询结果对比
        """
        results = {}
        
        for provider, instance in self._providers.items():
            try:
                result = await instance.search_with_triple_chain(query)
                results[provider.value] = result
            except Exception as e:
                results[provider.value] = None
                print(f"[UnifiedKnowledgeManager] {provider.value} 查询失败: {e}")
        
        return results


# 创建全局实例
_knowledge_manager = None


def get_unified_knowledge_manager() -> UnifiedKnowledgeManager:
    """获取统一知识管理器实例"""
    global _knowledge_manager
    if _knowledge_manager is None:
        _knowledge_manager = UnifiedKnowledgeManager()
    return _knowledge_manager


# 便捷函数
async def search_knowledge(query: str, provider: KnowledgeProvider = None, **kwargs) -> List[SearchResult]:
    """
    便捷搜索函数
    
    Args:
        query: 查询字符串
        provider: 指定知识提供者（可选，默认为当前活跃提供者）
        **kwargs: 额外参数
    
    Returns:
        搜索结果列表
    """
    manager = get_unified_knowledge_manager()
    
    if provider:
        original_provider = manager.get_current_provider()
        manager.set_provider(provider)
        try:
            return await manager.search(query, **kwargs)
        finally:
            manager.set_provider(original_provider)
    
    return await manager.search(query, **kwargs)


async def query_with_triple_chain(query: str, provider: KnowledgeProvider = None) -> QueryResult:
    """
    便捷查询函数（带三重链验证）
    
    Args:
        query: 查询字符串
        provider: 指定知识提供者（可选）
    
    Returns:
        查询结果
    """
    manager = get_unified_knowledge_manager()
    
    if provider:
        original_provider = manager.get_current_provider()
        manager.set_provider(provider)
        try:
            return await manager.search_with_triple_chain(query)
        finally:
            manager.set_provider(original_provider)
    
    return await manager.search_with_triple_chain(query)


__all__ = [
    "KnowledgeProvider",
    "SearchResult",
    "TripleChainResult",
    "TermInfo",
    "QueryResult",
    "IKnowledgeRetriever",
    "UnifiedKnowledgeManager",
    "get_unified_knowledge_manager",
    "search_knowledge",
    "query_with_triple_chain"
]