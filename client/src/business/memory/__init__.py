"""
统一记忆层 (Unified Memory Layer)

提供统一的记忆访问接口，支持自适应路由到不同类型的记忆存储。

三层记忆模型：
- Short-term: 会话缓存、精确匹配 (< 1小时)
- Mid-term: 向量检索、数据库 (1小时~30天)
- Long-term: 知识图谱、Wiki (> 30天)

特殊记忆类型：
- Error Memory: 错误学习记忆
- Evolution Memory: 进化决策记忆
"""

from .router import AdaptiveMemoryRouter, get_memory_router
from .short_term import SessionMemory, ExactMemory, get_session_memory, get_exact_memory
from .mid_term import VectorMemory, DocumentMemory, DatabaseMemory, get_vector_memory, get_document_memory, get_database_memory
from .long_term import KnowledgeGraphMemory, get_knowledge_graph_memory
from .specialized import ErrorMemory, EvolutionMemory, get_error_memory, get_evolution_memory
from .knowledge_graph_service import UnifiedKnowledgeGraphService, get_knowledge_graph_service
from .rag_service import UnifiedRAGService, get_rag_service
from .intent_classifier import EnhancedIntentClassifier, get_intent_classifier
from .hybrid_intent_classifier import (
    HybridIntentClassifier, get_hybrid_intent_classifier,
    classify_intent, classify_intent_sync, train_intent_classifier, get_intent_classifier_stats
)
from .compat import KnowledgeBase, FusionRAG, VectorDBIntegration, search_knowledge, add_knowledge

__all__ = [
    # 路由器
    "AdaptiveMemoryRouter",
    "get_memory_router",
    
    # 短-term记忆
    "SessionMemory",
    "ExactMemory",
    "get_session_memory",
    "get_exact_memory",
    
    # 中-term记忆
    "VectorMemory",
    "DocumentMemory",
    "DatabaseMemory",
    "get_vector_memory",
    "get_document_memory",
    "get_database_memory",
    
    # 长-term记忆
    "KnowledgeGraphMemory",
    "get_knowledge_graph_memory",
    "UnifiedKnowledgeGraphService",
    "get_knowledge_graph_service",
    
    # RAG服务
    "UnifiedRAGService",
    "get_rag_service",
    
    # 意图分类器
    "EnhancedIntentClassifier",
    "get_intent_classifier",
    "HybridIntentClassifier",
    "get_hybrid_intent_classifier",
    "classify_intent",
    "classify_intent_sync",
    "train_intent_classifier",
    "get_intent_classifier_stats",
    
    # 特殊记忆
    "ErrorMemory",
    "EvolutionMemory",
    "get_error_memory",
    "get_evolution_memory",
    
    # 兼容性层（逐步淘汰）
    "KnowledgeBase",
    "FusionRAG",
    "VectorDBIntegration",
    "search_knowledge",
    "add_knowledge",
]


def query_memory(query: str, context: dict = None) -> dict:
    """
    统一记忆查询接口
    
    Args:
        query: 查询内容
        context: 上下文信息（可选）
    
    Returns:
        查询结果字典
    """
    router = get_memory_router()
    return router.query(query, context or {})


def store_memory(content: str, memory_type: str = "mid_term", **kwargs) -> str:
    """
    统一记忆存储接口
    
    Args:
        content: 要存储的内容
        memory_type: 记忆类型 (short_term/mid_term/long_term/error/evolution)
        **kwargs: 额外参数
    
    Returns:
        存储的ID
    """
    router = get_memory_router()
    return router.store(content, memory_type, **kwargs)