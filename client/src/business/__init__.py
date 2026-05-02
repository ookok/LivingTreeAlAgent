"""
LivingTree AI Agent - Business Layer

统一导出核心模块和工具函数
"""

from typing import Optional

# 统一层
from .unified_memory_layer import UnifiedMemoryLayer, get_unified_memory_layer, MemoryStoreType, MemoryRetrieverType
from .unified_search_engine import UnifiedSearchEngine, get_unified_search_engine, SearchSource
from .enhanced_event_bus import EnhancedEventBus, get_enhanced_event_bus
from .unified_integration_bootstrapper import UnifiedIntegrationBootstrapper, get_bootstrapper, initialize_all

# 任务链系统
from .multi_modal_intent_engine import MultiModalIntentEngine, get_multi_modal_intent_engine, InputData, InputType, Intent
from .adaptive_task_decomposer import AdaptiveTaskDecomposer, get_adaptive_task_decomposer, Task, Plan, TaskType
from .parallel_execution_scheduler import ParallelExecutionScheduler, get_parallel_execution_scheduler, ExecutionResult
from .multi_source_fusion_engine import MultiSourceFusionEngine, get_multi_source_fusion_engine, FusedResult, Conflict
from .unified_task_chain import UnifiedTaskChain, get_unified_task_chain, TaskChainResult, TaskChainContext, execute_task_chain

# 优化系统
from .intelligent_optimization_engine import IntelligentOptimizationEngine, get_intelligent_optimization_engine
from .token_optimizer import TokenOptimizer, get_token_optimizer
from .prompt_cache_manager import PromptCacheManager, get_prompt_cache_manager
from .token_compressor import TokenCompressor, get_token_compressor
from .cost_manager import CostManager, get_cost_manager

# 自我进化
from .self_evolution_engine import SelfEvolutionEngine, get_self_evolution_engine
from .open_ended_evolution import OpenEndedEvolution, create_open_ended_evolution
from .rl_driven_improvement import RLDrivenImprovement, create_rl_improvement, RLAlgorithm

# 技能发现
from .skill_integration_service import SkillIntegrationService, get_skill_integration_service
from .skill_discovery import SkillDiscovery, create_skill_discovery
from .skill_matcher import SkillMatcher, create_skill_matcher
from .skill_graph import SkillGraph, create_skill_graph

# LLM验证器
from .llm_verifier import LLMVerifier, create_llm_verifier
from .verifier_integration_service import VerifierIntegrationService, get_verifier_integration_service

# 智能搜索
from .intelligent_search_engine import IntelligentSearchEngine, get_intelligent_search_engine
from .web_scraper import WebScraper, create_web_scraper

# 消息工具
from .wecom_tool import WeComTool, get_wecom_tool
from .wechat_tool import WeChatTool, get_wechat_tool
from .message_sync_service import MessageSyncService, get_message_sync_service

# 配置引导
from .config_assistant import ConfigGuideAssistant, get_config_assistant, ConfigGap, GuideAction
from .config_scene_selector import ConfigSceneSelector, SceneConfig
from .smart_config_recommender import SmartConfigRecommender, get_smart_recommender, Recommendation
from .config_version_manager import ConfigVersionManager, get_version_manager, ConfigVersion
from .smart_config_detector import SmartConfigDetector, get_config_detector

# 稳定性与性能优化
from .circuit_breaker import LayeredCircuitBreaker, get_circuit_breaker, CircuitBreaker, BreakerState
from .health_monitor import HealthMonitor, get_health_monitor, HealthResult, Alert
from .graceful_degradation import GracefulDegradation, get_degradation_manager, DegradationLevel
from .priority_task_queue import PriorityTaskQueue, get_task_queue, TaskPriority
from .distributed_tracer import DistributedTracer, get_tracer, Trace, Span
from .smart_profiler import SmartProfiler, get_profiler, ProfileResult, OptimizationSuggestion
from .adaptive_resource_scheduler import AdaptiveResourceScheduler, get_resource_scheduler, LoadMonitor
from .stability_init import (
    StabilityManager,
    stability,
    with_circuit_breaker,
    with_profiling,
    with_tracing,
    cached,
    submit_task,
)

# 意图管理
from .intent_management import (
    # 统一意图定义中心
    UnifiedIntentHub,
    get_unified_intent_hub,
    IntentDefinition,
    IntentPriority,
    
    # 智能意图识别引擎
    SmartIntentRecognizer,
    get_smart_intent_recognizer,
    IntentResult,
    IntentCandidate,
    
    # 深度语义感知系统
    DeepSemanticAnalyzer,
    get_deep_semantic_analyzer,
    SemanticAnalysis,
    SemanticRole,
    SentimentType,
    DomainType,
    ComplexityLevel,
    
    # 自适应模型推理框架
    AdaptiveReasoningFramework,
    get_adaptive_reasoning_framework,
    ReasoningStrategyType,
    TaskType,
    ReasoningResult,
    
    # 智能缓存系统
    IntelligentCacheSystem,
    get_intelligent_cache_system,
    CacheLayer,
)

# 模型路由
from .model_routing import (
    SmartModelSelector,
    DynamicModelComposer,
    CostQualityRouter,
    get_smart_model_selector,
    get_dynamic_model_composer,
    get_cost_quality_router,
    ModelType,
    ModelDescriptor,
    RoutingDecision,
)

# 事件总线
from .shared.event_bus import EventBus, Event, EVENTS, get_event_bus, subscribe_event, publish_event

# 微内核
from .microkernel.kernel import Microkernel, get_kernel, init_kernel, shutdown_kernel
from .microkernel.lifecycle import LifecycleManager, LifecycleState, LifecycleEvent

# L0-L4 层架构
from .layered_architecture import (
    # L0 - 基础设施层
    DynamicResourceScheduler,
    SmartFailover,
    EdgeCloudSynergy,
    get_dynamic_resource_scheduler,
    get_smart_failover,
    get_edge_cloud_synergy,
    
    # L1 - 数据/存储层
    MultiModalStore,
    AdaptiveStorage,
    SmartDataLifecycle,
    get_multi_modal_store,
    get_adaptive_storage,
    get_smart_data_lifecycle,
    
    # L2 - 服务/逻辑层
    AdaptiveServiceComposition,
    SmartAPIGateway,
    get_adaptive_service_composition,
    get_smart_api_gateway,
    
    # L3 - 应用/业务层
    AdaptiveWorkflowEngine,
    SmartDecisionEngine,
    SelfEvolutionSystem,
    get_adaptive_workflow_engine,
    get_smart_decision_engine,
    get_self_evolution_system,
    
    # L4 - 表现/交互层
    MultiModalInteractionEngine,
    EmotionAwareUI,
    AdaptiveOutput,
    get_multi_modal_interaction_engine,
    get_emotion_aware_ui,
    get_adaptive_output,
    
    # 跨层组件
    VerticalOptimizer,
    SmartObservability,
    SecurityAsService,
    get_vertical_optimizer,
    get_smart_observability,
    get_security_as_service,
)

__all__ = [
    # 统一层
    "UnifiedMemoryLayer",
    "get_unified_memory_layer",
    "MemoryStoreType",
    "MemoryRetrieverType",
    "UnifiedSearchEngine",
    "get_unified_search_engine",
    "SearchSource",
    "EnhancedEventBus",
    "get_enhanced_event_bus",
    "UnifiedIntegrationBootstrapper",
    "get_bootstrapper",
    "initialize_all",
    
    # 任务链系统
    "MultiModalIntentEngine",
    "get_multi_modal_intent_engine",
    "InputData",
    "InputType",
    "Intent",
    "AdaptiveTaskDecomposer",
    "get_adaptive_task_decomposer",
    "Task",
    "Plan",
    "TaskType",
    "ParallelExecutionScheduler",
    "get_parallel_execution_scheduler",
    "ExecutionResult",
    "MultiSourceFusionEngine",
    "get_multi_source_fusion_engine",
    "FusedResult",
    "Conflict",
    "UnifiedTaskChain",
    "get_unified_task_chain",
    "TaskChainResult",
    "TaskChainContext",
    "execute_task_chain",
    
    # 优化系统
    "IntelligentOptimizationEngine",
    "get_intelligent_optimization_engine",
    "TokenOptimizer",
    "get_token_optimizer",
    "PromptCacheManager",
    "get_prompt_cache_manager",
    "TokenCompressor",
    "get_token_compressor",
    "CostManager",
    "get_cost_manager",
    
    # 自我进化
    "SelfEvolutionEngine",
    "get_self_evolution_engine",
    "OpenEndedEvolution",
    "create_open_ended_evolution",
    "RLDrivenImprovement",
    "create_rl_improvement",
    "RLAlgorithm",
    
    # 技能发现
    "SkillIntegrationService",
    "get_skill_integration_service",
    "SkillDiscovery",
    "create_skill_discovery",
    "SkillMatcher",
    "create_skill_matcher",
    "SkillGraph",
    "create_skill_graph",
    
    # LLM验证器
    "LLMVerifier",
    "create_llm_verifier",
    "VerifierIntegrationService",
    "get_verifier_integration_service",
    
    # 智能搜索
    "IntelligentSearchEngine",
    "get_intelligent_search_engine",
    "WebScraper",
    "create_web_scraper",
    
    # 消息工具
    "WeComTool",
    "get_wecom_tool",
    "WeChatTool",
    "get_wechat_tool",
    "MessageSyncService",
    "get_message_sync_service",
    
    # 配置引导
    "ConfigGuideAssistant",
    "get_config_assistant",
    "ConfigGap",
    "GuideAction",
    "ConfigSceneSelector",
    "SceneConfig",
    "SmartConfigRecommender",
    "get_smart_recommender",
    "Recommendation",
    "ConfigVersionManager",
    "get_version_manager",
    "ConfigVersion",
    "SmartConfigDetector",
    "get_config_detector",
    
    # 稳定性与性能优化
    "LayeredCircuitBreaker",
    "get_circuit_breaker",
    "CircuitBreaker",
    "BreakerState",
    "HealthMonitor",
    "get_health_monitor",
    "HealthResult",
    "Alert",
    "GracefulDegradation",
    "get_degradation_manager",
    "DegradationLevel",
    "PriorityTaskQueue",
    "get_task_queue",
    "TaskPriority",
    "DistributedTracer",
    "get_tracer",
    "Trace",
    "Span",
    "SmartProfiler",
    "get_profiler",
    "ProfileResult",
    "OptimizationSuggestion",
    "AdaptiveResourceScheduler",
    "get_resource_scheduler",
    "LoadMonitor",
    "StabilityManager",
    "stability",
    "with_circuit_breaker",
    "with_profiling",
    "with_tracing",
    "cached",
    "submit_task",
    
    # 意图管理
    "UnifiedIntentHub",
    "get_unified_intent_hub",
    "IntentDefinition",
    "IntentPriority",
    "SmartIntentRecognizer",
    "get_smart_intent_recognizer",
    "IntentResult",
    "IntentCandidate",
    "DeepSemanticAnalyzer",
    "get_deep_semantic_analyzer",
    "SemanticAnalysis",
    "SemanticRole",
    "SentimentType",
    "DomainType",
    "ComplexityLevel",
    "AdaptiveReasoningFramework",
    "get_adaptive_reasoning_framework",
    "ReasoningStrategyType",
    "TaskType",
    "ReasoningResult",
    "IntelligentCacheSystem",
    "get_intelligent_cache_system",
    "CacheLayer",
    
    # 模型路由
    "SmartModelSelector",
    "DynamicModelComposer",
    "CostQualityRouter",
    "get_smart_model_selector",
    "get_dynamic_model_composer",
    "get_cost_quality_router",
    "ModelType",
    "ModelDescriptor",
    "RoutingDecision",
    
    # 事件总线
    "EventBus",
    "Event",
    "EVENTS",
    "get_event_bus",
    "subscribe_event",
    "publish_event",
    
    # 微内核
    "Microkernel",
    "get_kernel",
    "init_kernel",
    "shutdown_kernel",
    "LifecycleManager",
    "LifecycleState",
    "LifecycleEvent",
    
    # L0 - 基础设施层
    "DynamicResourceScheduler",
    "SmartFailover",
    "EdgeCloudSynergy",
    "get_dynamic_resource_scheduler",
    "get_smart_failover",
    "get_edge_cloud_synergy",
    
    # L1 - 数据/存储层
    "MultiModalStore",
    "AdaptiveStorage",
    "SmartDataLifecycle",
    "get_multi_modal_store",
    "get_adaptive_storage",
    "get_smart_data_lifecycle",
    
    # L2 - 服务/逻辑层
    "AdaptiveServiceComposition",
    "SmartAPIGateway",
    "get_adaptive_service_composition",
    "get_smart_api_gateway",
    
    # L3 - 应用/业务层
    "AdaptiveWorkflowEngine",
    "SmartDecisionEngine",
    "SelfEvolutionSystem",
    "get_adaptive_workflow_engine",
    "get_smart_decision_engine",
    "get_self_evolution_system",
    
    # L4 - 表现/交互层
    "MultiModalInteractionEngine",
    "EmotionAwareUI",
    "AdaptiveOutput",
    "get_multi_modal_interaction_engine",
    "get_emotion_aware_ui",
    "get_adaptive_output",
    
    # 跨层组件
    "VerticalOptimizer",
    "SmartObservability",
    "SecurityAsService",
    "get_vertical_optimizer",
    "get_smart_observability",
    "get_security_as_service",
]