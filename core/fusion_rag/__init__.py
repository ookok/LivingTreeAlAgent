"""
多源融合智能加速系统 (FusionRAG)
Multi-Source Fusion Intelligence Acceleration System

四层混合检索架构:
1. 精确缓存层 (毫秒级响应)
2. 会话缓存层 (上下文感知)
3. 知识库层 (深度文档检索)
4. 数据库层 (结构化数据查询)

L4 异构执行层:
- l4_executor: RelayFreeLLM 网关执行器
- write_back_cache: L4 结果回填缓存
- l4_aware_router: L4 感知智能路由

KV Cache 推理优化:
- kv_cache_optimizer: 三层 KV 缓存管理器

核心模块:
- exact_cache: 精确缓存层
- session_cache: 会话缓存层
- knowledge_base: 知识库检索层
- database_layer: 数据库查询层
- intent_classifier: 查询意图分类器
- intelligent_router: 智能路由引擎
- fusion_engine: 多源融合引擎
- small_model_optimizer: 本地小模型优化器
- performance_monitor: 性能监控系统
- l4_executor: L4 Relay 执行器
- write_back_cache: L4 回填缓存
- l4_aware_router: L4 感知路由
- kv_cache_optimizer: KV Cache 推理优化
"""

from .exact_cache import ExactCacheLayer
from .session_cache import SessionCacheLayer
from .knowledge_base import KnowledgeBaseLayer
from .database_layer import DatabaseLayer
from .intent_classifier import QueryIntentClassifier
from .intelligent_router import IntelligentRouter
from .fusion_engine import FusionEngine, FusionEngineError
from .small_model_optimizer import SmallModelOptimizer
from .performance_monitor import PerformanceMonitor
from .l4_executor import L4RelayExecutor, L4ExecutionError, get_l4_executor, execute_via_l4
from .write_back_cache import WriteBackCache, get_write_back_cache
from .l4_aware_router import L4AwareRouter, L4RouterError, get_l4_aware_router

# KV Cache 优化器
from .kv_cache_optimizer import (
    FusionKVCacheManager,
    SemanticQueryCache,
    RetrievalResultCache,
    LLMResponseCache,
    CachePreheater,
    LRUCache,
    get_kv_cache_manager,
    clear_kv_cache,
    KV_CACHE_CONFIG,
)

# BookRAG 模块
from .ift_classifier import (
    IFTQueryClassifier,
    IFTQueryType,
    IFTClassificationResult,
    classify_ift_query,
    batch_classify,
)
from .retrieval_operators import (
    Chunk,
    RetrievalContext,
    RetrievalResult,
    RetrievalOperator,
    Selector,
    Reasoner,
    Aggregator,
    Synthesizer,
    RetrievalPipeline,
    create_pipeline,
)
from .book_rag import (
    BookRAG,
    BookRAGConfig,
    bookrag_retrieve,
    bookrag_classify,
    create_bookrag,
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

    # 工具函数
    "get_l4_executor",
    "execute_via_l4",
    "get_write_back_cache",
    "get_l4_aware_router",

    # KV Cache 优化
    "FusionKVCacheManager",
    "SemanticQueryCache",
    "RetrievalResultCache",
    "LLMResponseCache",
    "CachePreheater",
    "LRUCache",
    "get_kv_cache_manager",
    "clear_kv_cache",
    "KV_CACHE_CONFIG",

    # BookRAG - IFT 分类
    "IFTQueryClassifier",
    "IFTQueryType",
    "IFTClassificationResult",
    "classify_ift_query",
    "batch_classify",

    # BookRAG - 检索操作符
    "Chunk",
    "RetrievalContext",
    "RetrievalResult",
    "RetrievalOperator",
    "Selector",
    "Reasoner",
    "Aggregator",
    "Synthesizer",
    "RetrievalPipeline",
    "create_pipeline",

    # BookRAG - 统一入口
    "BookRAG",
    "BookRAGConfig",
    "bookrag_retrieve",
    "bookrag_classify",
    "create_bookrag",
]

__version__ = "2.2.0"
