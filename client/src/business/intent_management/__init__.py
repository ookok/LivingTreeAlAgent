"""
Intent Management Package

意图管理包，包含统一意图定义中心、智能意图识别引擎、深度语义感知系统、自适应模型推理框架和智能缓存系统。

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

from .intent_hub import (
    UnifiedIntentHub,
    IntentDefinition,
    IntentPattern,
    IntentPriority,
    IntentVersion,
    IntentEvolution,
    get_unified_intent_hub,
)

from .intent_recognizer import (
    SmartIntentRecognizer,
    RecognitionLevel,
    DialogContext,
    IntentCandidate,
    IntentResult,
    get_smart_intent_recognizer,
)

from .semantic_analyzer import (
    DeepSemanticAnalyzer,
    SemanticRole,
    SentimentType,
    DomainType,
    ComplexityLevel,
    SemanticRoleLabel,
    SemanticAnalysis,
    LogicalForm,
    ContextModel,
    get_deep_semantic_analyzer,
)

from .reasoning_framework import (
    AdaptiveReasoningFramework,
    ReasoningStrategyType,
    TaskType,
    ReasoningStep,
    ReasoningResult,
    CompositeReasoning,
    get_adaptive_reasoning_framework,
)

from .intelligent_cache import (
    IntelligentCacheSystem,
    CacheLayer,
    EvictionPolicy,
    CacheEntry,
    CacheStats,
    get_intelligent_cache_system,
)

__all__ = [
    # Intent Hub
    "UnifiedIntentHub",
    "IntentDefinition",
    "IntentPattern",
    "IntentPriority",
    "IntentVersion",
    "IntentEvolution",
    "get_unified_intent_hub",
    
    # Intent Recognizer
    "SmartIntentRecognizer",
    "RecognitionLevel",
    "DialogContext",
    "IntentCandidate",
    "IntentResult",
    "get_smart_intent_recognizer",
    
    # Semantic Analyzer
    "DeepSemanticAnalyzer",
    "SemanticRole",
    "SentimentType",
    "DomainType",
    "ComplexityLevel",
    "SemanticRoleLabel",
    "SemanticAnalysis",
    "LogicalForm",
    "ContextModel",
    "get_deep_semantic_analyzer",
    
    # Reasoning Framework
    "AdaptiveReasoningFramework",
    "ReasoningStrategyType",
    "TaskType",
    "ReasoningStep",
    "ReasoningResult",
    "CompositeReasoning",
    "get_adaptive_reasoning_framework",
    
    # Intelligent Cache
    "IntelligentCacheSystem",
    "CacheLayer",
    "EvictionPolicy",
    "CacheEntry",
    "CacheStats",
    "get_intelligent_cache_system",
]

__version__ = "1.0.0"