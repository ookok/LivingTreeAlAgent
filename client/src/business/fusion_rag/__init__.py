"""
多源融合智能加速系统 (FusionRAG)
Multi-Source Fusion Intelligence Acceleration System

架构升级 (2026-04-30):
- 引入共享基础设施层 (shared/)
- 依赖注入容器、统一术语模型、配置中心、事件总线、缓存层、统一异常体系

四层混合检索架构:
1. 精确缓存层 (毫秒级响应)
2. 会话缓存层 (上下文感知)
3. 知识库层 (深度文档检索)
4. 数据库层 (结构化数据查询)

L4 异构执行层:
- l4_executor: RelayFreeLLM 网关执行器
- write_back_cache: L4 结果回填缓存
- l4_aware_router: L4 感知智能路由

RAG 优化层 (2026-04-28):
- query_classifier: 判断查询是否需要检索
- query_transformer: 查询重写与分解
- reranker: 检索结果重新排序

行业知识治理体系 (2026-04-29):
- industry_governance: 源头治理（数据准入、元数据tagging、术语归一化）
- knowledge_tiering: 动态知识分层（L1/L2/L3三层架构）
- industry_filter: 行业过滤器（领域过滤、重排序、查询改写）
- relevance_scorer: 多维度相关性打分（领域匹配度、时效性、权威性、置信度）
- feedback_learner: 负反馈学习（持续进化机制）
- industry_dialect: 行业方言词典（本地术语管理）

核心原则：宁可召回不足，不可幻觉泛滥
"""

from typing import Dict, List, Optional, Any

# 共享基础设施层
from client.src.business.shared import (
    Container,
    Term,
    ConfigCenter,
    EventBus,
    CacheLayer,
    LTAException
)

# 基础缓存层
from .exact_cache import ExactCacheLayer
from .session_cache import SessionCacheLayer
from .knowledge_base import KnowledgeBaseLayer
from .database_layer import DatabaseLayer

# 路由与融合
from .intent_classifier import QueryIntentClassifier
from .intelligent_router import IntelligentRouter
from .fusion_engine import FusionEngine, FusionEngineError

# 优化与监控
from .small_model_optimizer import SmallModelOptimizer
from .performance_monitor import PerformanceMonitor

# L4 执行层
from .l4_executor import L4RelayExecutor, L4ExecutionError, get_l4_executor, execute_via_l4
from .write_back_cache import WriteBackCache, get_write_back_cache
from .l4_aware_router import L4AwareRouter, L4RouterError, get_l4_aware_router

# RAG 优化层（2026-04-28 新增）
from .query_classifier import QueryClassifier, ClassificationResult
from .query_transformer import QueryTransformer, TransformResult
from .reranker import Reranker, RerankItem

# 行业知识治理体系（2026-04-29 新增）
from .industry_governance import (
    IndustryGovernance,
    DocumentTag,
    DocumentFilter,
    DEFAULT_INDUSTRY_SYNONYMS,
    create_industry_governance
)
from .knowledge_tiering import (
    KnowledgeTierManager,
    TierConfig,
    TieredDocument,
    create_knowledge_tier_manager
)
from .industry_filter import (
    IndustryFilter,
    FilterResult,
    QueryRewriteResult,
    create_industry_filter
)
from .relevance_scorer import (
    RelevanceScorer,
    ScoreBreakdown,
    ScoringResult,
    ScoringConfig,
    create_relevance_scorer
)
from .feedback_learner import (
    FeedbackLearner,
    FeedbackRecord,
    LearningInsight,
    PinnedDocument,
    create_feedback_learner
)
from .industry_dialect import (
    IndustryDialectDict,
    DialectEntry,
    DialectStatistics,
    create_industry_dialect_dict,
    PRESET_DIALECTS
)

# 工业知识发现系统（2026-04-29 新增）
from .industrial_knowledge_discovery import (
    IndustrialKnowledgeDiscovery,
    DiscoveryResult,
    RetrievedDocument,
    GovernanceStats,
    create_industrial_knowledge_discovery,
    INDUSTRY_SOURCE_WHITELIST,
    INDUSTRY_SOURCE_BLACKLIST
)

# 三重链统一引擎（2026-04-30 新增）
from .triple_chain_engine import (
    TripleChainEngine,
    ReasoningStep,
    Evidence,
    TripleChainResult,
    create_triple_chain_engine
)


__all__ = [
    # 基础缓存层
    "ExactCacheLayer",
    "SessionCacheLayer",
    "KnowledgeBaseLayer",
    "DatabaseLayer",

    # 路由与融合
    "QueryIntentClassifier",
    "IntelligentRouter",
    "FusionEngine",
    "FusionEngineError",

    # 优化与监控
    "SmallModelOptimizer",
    "PerformanceMonitor",

    # L4 执行层
    "L4RelayExecutor",
    "L4ExecutionError",
    "L4AwareRouter",
    "L4RouterError",

    # RAG 优化层
    "QueryClassifier",
    "ClassificationResult",
    "QueryTransformer",
    "TransformResult",
    "Reranker",
    "RerankItem",

    # 行业知识治理体系
    "IndustryGovernance",
    "DocumentTag",
    "DocumentFilter",
    "DEFAULT_INDUSTRY_SYNONYMS",
    "KnowledgeTierManager",
    "TierConfig",
    "TieredDocument",
    "IndustryFilter",
    "FilterResult",
    "QueryRewriteResult",
    "RelevanceScorer",
    "ScoreBreakdown",
    "ScoringResult",
    "ScoringConfig",
    "FeedbackLearner",
    "FeedbackRecord",
    "LearningInsight",
    "PinnedDocument",
    "IndustryDialectDict",
    "DialectEntry",
    "DialectStatistics",
    "PRESET_DIALECTS",
    
    # 工业知识发现系统
    "IndustrialKnowledgeDiscovery",
    "DiscoveryResult",
    "RetrievedDocument",
    "GovernanceStats",
    "INDUSTRY_SOURCE_WHITELIST",
    "INDUSTRY_SOURCE_BLACKLIST",
    
    # 三重链统一引擎
    "TripleChainEngine",
    "ReasoningStep",
    "Evidence",
    "TripleChainResult",

    # 工具函数
    "get_l4_executor",
    "execute_via_l4",
    "get_write_back_cache",
    "get_l4_aware_router",
    "create_industry_governance",
    "create_knowledge_tier_manager",
    "create_industry_filter",
    "create_relevance_scorer",
    "create_feedback_learner",
    "create_industry_dialect_dict",
    "create_industrial_knowledge_discovery",
    "create_triple_chain_engine"
]

__version__ = "2.2.0"
__author__ = "LivingTree AI Team"
__description__ = "Multi-Source Fusion Intelligence Acceleration System with Industry Governance"


class FusionRAG:
    """
    FusionRAG 主入口类
    
    整合所有模块，提供统一的检索接口
    
    行业知识治理闭环：
    1. 输入控制 → IndustryGovernance (数据准入、术语归一化)
    2. 检索对齐 → KnowledgeTierManager + IndustryFilter (分层检索、行业过滤)
    3. 输出验证 → RelevanceScorer + TripleChainEngine (多维度打分、三重链验证)
    4. 持续进化 → FeedbackLearner + IndustryDialectDict (负反馈学习、方言扩展)
    
    三重链统一机制：
    - 思维链：显式推理步骤
    - 因果链：步骤间逻辑关系
    - 证据链：可追溯的来源支持
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化 FusionRAG
        
        Args:
            config: 配置字典
        """
        # 初始化治理模块
        self.governance = create_industry_governance()
        self.tier_manager = create_knowledge_tier_manager()
        self.filter = create_industry_filter()
        self.scorer = create_relevance_scorer()
        self.learner = create_feedback_learner()
        self.dialect = create_industry_dialect_dict()
        
        # 初始化三重链引擎
        self.triple_chain_engine = create_triple_chain_engine()
        
        # 配置
        self.config = config or {}
        self.target_industry = self.config.get("target_industry", "通用")
        self.min_relevance_threshold = self.config.get("min_relevance_threshold", 0.6)
        
        print(f"[FusionRAG] 初始化完成，目标行业: {self.target_industry}")
    
    def normalize_query(self, query: str) -> str:
        """
        查询预处理：方言转换 + 术语归一化
        
        Args:
            query: 原始查询
            
        Returns:
            预处理后的查询
        """
        # 1. 方言转换
        expanded_queries = self.dialect.expand_query(query, self.target_industry)
        
        # 2. 术语归一化
        normalized = []
        for q in expanded_queries:
            normalized.append(self.governance.normalize_query(q, self.target_industry))
        
        return normalized[0] if normalized else query
    
    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        完整检索流程
        
        Args:
            query: 用户查询
            top_k: 返回数量
            
        Returns:
            检索结果列表（已排序和过滤）
        """
        # 1. 查询预处理
        normalized_query = self.normalize_query(query)
        
        # 2. 查询改写（行业化）
        rewrite_result = self.filter.rewrite_query(normalized_query, self.target_industry)
        
        # 3. 跨层级检索
        tier_results = self.tier_manager.multi_tier_search(
            rewrite_result.rewritten_query,
            top_k_per_tier=top_k
        )
        
        # 4. 转换为统一格式
        items = []
        for score, doc in tier_results:
            items.append({
                "id": doc.doc_id,
                "title": doc.title,
                "content": doc.content,
                "source_type": doc.source_type,
                "tier": doc.tier,
                "score": score
            })
        
        # 5. 行业过滤
        filtered_items = []
        for item in items:
            filter_result = self.filter.filter_by_industry(
                item["content"],
                item["title"],
                self.target_industry
            )
            if filter_result.passed:
                filtered_items.append(item)
        
        # 6. 行业感知重排序
        reranked = self.filter.rerank_by_industry(
            query,
            filtered_items,
            self.target_industry
        )
        
        # 7. 多维度相关性打分与过滤
        scored = self.scorer.filter_by_score(
            reranked,
            self.target_industry,
            self.min_relevance_threshold
        )
        
        # 8. 添加来源归因
        for item in scored:
            item["source_attribution"] = self.scorer.generate_source_attribution(
                item.get("title", ""),
                item.get("source_type", "unknown")
            )
        
        return scored[:top_k]
    
    def search_with_triple_chain(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        带三重链验证的检索流程
        
        Args:
            query: 用户查询
            top_k: 返回数量
            
        Returns:
            包含三重链信息的检索结果
        """
        # 1. 查询预处理
        normalized_query = self.normalize_query(query)
        
        # 2. 查询改写（行业化）
        rewrite_result = self.filter.rewrite_query(normalized_query, self.target_industry)
        
        # 3. 跨层级检索
        tier_results = self.tier_manager.multi_tier_search(
            rewrite_result.rewritten_query,
            top_k_per_tier=top_k
        )
        
        # 4. 转换为统一格式
        items = []
        for score, doc in tier_results:
            items.append({
                "id": doc.doc_id,
                "title": doc.title,
                "content": doc.content,
                "source_type": doc.source_type,
                "tier": doc.tier,
                "score": score,
                "confidence": score,
                "authority_level": 3
            })
        
        # 5. 行业过滤
        filtered_items = []
        for item in items:
            filter_result = self.filter.filter_by_industry(
                item["content"],
                item["title"],
                self.target_industry
            )
            if filter_result.passed:
                filtered_items.append(item)
        
        # 6. 确定任务类型
        task_type = self._determine_task_type(query)
        
        # 7. 构建三重链
        triple_chain_result = self.triple_chain_engine.build_triple_chain(
            query=query,
            task_type=task_type,
            retrieved_docs=filtered_items[:5]
        )
        
        # 8. 构建返回结果
        return {
            "answer": triple_chain_result.answer,
            "reasoning": [{"step_id": s.step_id, "content": s.content, "confidence": s.confidence} 
                         for s in triple_chain_result.reasoning_steps],
            "evidence": [{
                "doc_id": e.doc_id,
                "title": e.title,
                "content_snippet": e.content_snippet,
                "source_type": e.source_type,
                "confidence": e.confidence
            } for e in triple_chain_result.evidences],
            "overall_confidence": triple_chain_result.overall_confidence,
            "uncertainty_note": triple_chain_result.uncertainty_note,
            "validation_passed": triple_chain_result.validation_passed,
            "task_type": task_type,
            "query": query,
            "normalized_query": normalized_query
        }
    
    def _determine_task_type(self, query: str) -> str:
        """确定任务类型"""
        query_lower = query.lower()
        if "选择" in query or "选型" in query or "推荐" in query:
            return "selection"
        elif "故障" in query or "诊断" in query or "原因" in query or "解决" in query:
            return "diagnosis"
        elif "计算" in query or "多少" in query or "数值" in query or "计算" in query_lower:
            return "calculation"
        elif "符合" in query or "验证" in query or "检查" in query or "是否" in query:
            return "validation"
        else:
            return "selection"
    
    def record_feedback(self, query: str, result_id: str, result_content: str,
                       feedback_type: str, reason: str = ""):
        """
        记录用户反馈
        
        Args:
            query: 用户查询
            result_id: 结果ID
            result_content: 结果内容
            feedback_type: 反馈类型
            reason: 反馈原因
        """
        self.learner.record_feedback(query, result_id, result_content, feedback_type, reason)
        
        # 如果是不相关反馈，尝试学习新的同义词
        if feedback_type == "irrelevant":
            suggestions = self.dialect.suggest_aliases(query, self.target_industry)
            if suggestions:
                print(f"[FusionRAG] 建议添加方言条目: {suggestions}")
    
    def pin_document(self, doc_id: str, title: str, scenarios: List[str], priority: int = 3):
        """
        钉选文档（专家知识注入）
        
        Args:
            doc_id: 文档ID
            title: 文档标题
            scenarios: 适用场景
            priority: 优先级
        """
        self.learner.pin_document(doc_id, title, scenarios, priority)
    
    def add_synonym(self, alias: str, standard_term: str, industry: str = None):
        """
        添加同义词
        
        Args:
            alias: 别名
            standard_term: 标准术语
            industry: 行业
        """
        target_industry = industry or self.target_industry
        self.governance.load_synonym_table(target_industry, {alias: standard_term})
        self.dialect.add_entry(alias, standard_term, target_industry)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        return {
            "governance": self.governance.get_stats(),
            "tier_manager": self.tier_manager.get_tier_stats(),
            "filter": self.filter.get_stats(),
            "scorer": self.scorer.get_stats(),
            "learner": self.learner.get_learning_insights(),
            "dialect": self.dialect.get_stats()
        }
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "target_industry": self.target_industry,
            "min_relevance_threshold": self.min_relevance_threshold,
            "version": __version__
        }


def create_fusion_rag(config: Optional[Dict[str, Any]] = None) -> FusionRAG:
    """创建 FusionRAG 实例"""
    return FusionRAG(config)


# 添加到导出列表
__all__.append("FusionRAG")
__all__.append("create_fusion_rag")