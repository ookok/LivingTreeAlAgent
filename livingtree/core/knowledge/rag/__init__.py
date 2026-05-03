"""
FusionRAG 统一模块

合并增强自（~45,000 LOC → ~800 LOC，~98% 代码减少）:
- client/src/business/fusion_rag/ (61 files: engine, fusion, query, retrieval, reasoning, vector store, etc.)

架构:
    types.py    — 统一类型（RAGResult, SearchHit, IngestResult, embedding/generator工具）
    pipeline.py — 统一RAGPipeline（组合检索+融合+推理，替代5个独立引擎）
    
核心增强:
    - 统一结果类型（7个重复类型 → 4个清晰类型）
    - 共享嵌入工具（消除 engine.py 和 query_engine.py 的 DRY 违规）
    - 依赖注入架构（KG/VectorStore 共享实例）
    - 策略模式（5种检索策略：速度优先/精度优先/平衡/仅缓存/LLM优先）
    - 统一流水线: Ingest → Embed → Retrieve → Fuse → Reason → Answer
"""

from .types import (
    RAGResult,
    SearchHit,
    IngestResult,
    generate_embedding,
    generate_content_hash,
    extract_entities,
)

from .pipeline import (
    RAGPipeline,
    create_rag_pipeline,
    RetrieveStrategy,
    SpeedFirstStrategy,
    AccuracyFirstStrategy,
    BalancedStrategy,
    CacheOnlyStrategy,
    LLMFirstStrategy,
    STRATEGIES,
)

__all__ = [
    # Types
    "RAGResult",
    "SearchHit",
    "IngestResult",
    # Utils
    "generate_embedding",
    "generate_content_hash",
    "extract_entities",
    # Pipeline
    "RAGPipeline",
    "create_rag_pipeline",
    # Strategies
    "RetrieveStrategy",
    "SpeedFirstStrategy",
    "AccuracyFirstStrategy",
    "BalancedStrategy",
    "CacheOnlyStrategy",
    "LLMFirstStrategy",
    "STRATEGIES",
]
