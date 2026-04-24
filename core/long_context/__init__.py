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

设计原则:
1. 复用现有组件 (ContentAnalyzer, QueryNormalizer, UnifiedContext)
2. 与 TierModel 架构兼容
3. 支持流式输出和渐进式分析

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

# 便捷函数
from .adaptive_compressor import compress_adaptive
from .semantic_chunker import chunk_semantic
from .chunk_analyzer import analyze_chunk

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
]
