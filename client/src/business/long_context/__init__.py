# -*- coding: utf-8 -*-
"""
长上下文处理器 - Long Context Processor
======================================

为长文本提供智能分块、差异压缩和多轮分析能力。

核心组件:
- AdaptiveCompressor: 自适应差异化压缩
- SemanticChunker: LLM驱动的语义分块
- ChunkAnalyzer: 分块分析器
- MultiTurnAnalyzer: 多轮对话分析器
- CodeSigner: 代码签名化（Phase 2 P1 新增）
- LayeredContextPyramid: 分层上下文金字塔（Phase 2 P1 新增）

设计原则:
1. 复用现有组件 (ContentAnalyzer, QueryNormalizer, UnifiedContext)
2. 与 TierModel 架构兼容
3. 支持流式输出和渐进式分析
4. 代码签名化：1% Token 传递 99% 意图

Author: Hermes Desktop Team
Date: 2026-04-24
"""

from __future__ import annotations

# 版本信息
__version__ = "1.0.0"

# 公开 API
from .adaptive_compressor import (
    AdaptiveCompressor,
    CompressionResult,
    SegmentType,
    Segment,
)

from .semantic_chunker import (
    SemanticChunker,
    Chunk,
    ChunkType,
)

from .chunk_analyzer import (
    ChunkAnalyzer,
    ChunkAnalysis,
    AnalysisResult,
)

from .multi_turn_analyzer import (
    MultiTurnAnalyzer,
    TurnResult,
    ExplorationPath,
)

from .layered_analyzer import (
    LayeredHybridAnalyzer,
    AnalysisDepth,
    RelationType,
    ChunkRelation,
    Layer1Summary,
    Layer2ChunkAnalysis,
    Layer3RelationNetwork,
    Layer4Synthesis,
    LayeredAnalysisResult,
    analyze_layered,
)

from .multi_agent_analyzer import (
    AgentType,
    AgentStatus,
    MessageType,
    AgentMessage,
    AgentConfig,
    AgentResult,
    MessageBus,
    MultiAgentCoordinator,
    SummaryAgent,
    EntityAgent,
    RelationAgent,
    InsightAgent,
    SynthesisAgent,
    analyze_multi_agent,
    quick_analyze,
)

# Phase 4: 渐进式理解
from .progressive_understanding_impl import (
    ProgressiveUnderstanding,
    ProgressiveResult,
    UnderstandingConfig,
    UnderstandingDepth,
    UnderstandingSession,
    UnderstandingContext,
    KnowledgeAccumulator,
    KnowledgeItem,
    ProgressTracker,
    ComprehensionProgress,
    ComprehensionPhase,
    ComprehensionState,
    SessionManager,
    create_progressive_understander,
    quick_understand,
)

# 集成模块
from .integrations import (
    IntegrationMode,
    IntegrationConfig,
    IntegratedResult,
    UnifiedAgent,
    create_unified_agent,
)

# 便捷函数
from .adaptive_compressor import compress_adaptive
from .semantic_chunker import chunk_semantic
from .chunk_analyzer import analyze_chunk

# Phase 2 P1: 代码签名化
from .code_signer import (
    CodeSigner,
    SignatureResult,
    CodeElement,
    CodeElementType,
    PythonSignatureExtractor,
    signaturize_code,
)

# Phase 2 P1: 分层上下文金字塔
from .layered_context_pyramid import (
    ContextLevel,
    TokenBudget,
    LEVEL_BUDGETS,
    Symbol,
    FileIndex,
    ProjectIndex,
    SymbolIndex,
    LayeredContextBuilder,
    IncrementalContextManager,
)

__all__ = [
    # 版本
    "__version__",
    # 差异化压缩
    "AdaptiveCompressor",
    "CompressionResult",
    "SegmentType",
    "Segment",
    "compress_adaptive",
    # 语义分块
    "SemanticChunker",
    "Chunk",
    "ChunkType",
    "chunk_semantic",
    # 分块分析
    "ChunkAnalyzer",
    "ChunkAnalysis",
    "AnalysisResult",
    "analyze_chunk",
    # 多轮分析
    "MultiTurnAnalyzer",
    "TurnResult",
    "ExplorationPath",
    # 分层分析
    "LayeredHybridAnalyzer",
    "AnalysisDepth",
    "RelationType",
    "ChunkRelation",
    "Layer1Summary",
    "Layer2ChunkAnalysis",
    "Layer3RelationNetwork",
    "Layer4Synthesis",
    "LayeredAnalysisResult",
    "analyze_layered",
    # 多智能体协同
    "AgentType",
    "AgentStatus",
    "MessageType",
    "AgentMessage",
    "AgentConfig",
    "AgentResult",
    "MessageBus",
    "MultiAgentCoordinator",
    "SummaryAgent",
    "EntityAgent",
    "RelationAgent",
    "InsightAgent",
    "SynthesisAgent",
    "analyze_multi_agent",
    "quick_analyze",
    # 渐进式理解 (Phase 4)
    "ProgressiveUnderstanding",
    "ProgressiveResult",
    "UnderstandingConfig",
    "UnderstandingDepth",
    "UnderstandingSession",
    "UnderstandingContext",
    "KnowledgeAccumulator",
    "KnowledgeItem",
    "ProgressTracker",
    "ComprehensionProgress",
    "ComprehensionPhase",
    "ComprehensionState",
    "SessionManager",
    "create_progressive_understander",
    "quick_understand",
    # 集成模块
    "IntegrationMode",
    "IntegrationConfig",
    "IntegratedResult",
    "UnifiedAgent",
    "create_unified_agent",
    # Phase 2 P1: 代码签名化
    "CodeSigner",
    "SignatureResult",
    "CodeElement",
    "CodeElementType",
    "PythonSignatureExtractor",
    "signaturize_code",
    # Phase 2 P1: 分层上下文金字塔
    "ContextLevel",
    "TokenBudget",
    "LEVEL_BUDGETS",
    "Symbol",
    "FileIndex",
    "ProjectIndex",
    "SymbolIndex",
    "LayeredContextBuilder",
    "IncrementalContextManager",
]
