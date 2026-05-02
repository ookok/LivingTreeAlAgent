"""
LivingTree AI Agent - Business Layer

统一导出核心模块和工具函数。
使用延迟/防御式导入，已迁移模块通过 livingtree/ 核心包提供。
"""

from typing import Optional


def _safe_import(import_path: str, names: list, globals_dict: dict = None) -> dict:
    result = {}
    try:
        parts = import_path.split(".")
        module_name = parts[0]
        from_name = parts[-1] if len(parts) > 1 else module_name
        mod = __import__(import_path, fromlist=[from_name])
        for name in names:
            try:
                result[name] = getattr(mod, name)
            except AttributeError:
                pass
    except (ImportError, ModuleNotFoundError):
        pass
    return result


# ── 统一层 ─────────────────────────────────────────────────

_imports = _safe_import("business.unified_memory_layer",
    ["UnifiedMemoryLayer", "get_unified_memory_layer", "MemoryStoreType", "MemoryRetrieverType"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.unified_search_engine",
    ["UnifiedSearchEngine", "get_unified_search_engine", "SearchSource"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.enhanced_event_bus",
    ["EnhancedEventBus", "get_enhanced_event_bus"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.unified_integration_bootstrapper",
    ["UnifiedIntegrationBootstrapper", "get_bootstrapper", "initialize_all"])
for k, v in _imports.items(): globals()[k] = v


# ── 任务链系统 ─────────────────────────────────────────────

_imports = _safe_import("business.multi_modal_intent_engine",
    ["MultiModalIntentEngine", "get_multi_modal_intent_engine", "InputData", "InputType", "Intent"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.adaptive_task_decomposer",
    ["AdaptiveTaskDecomposer", "get_adaptive_task_decomposer", "Task", "Plan", "TaskType"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.parallel_execution_scheduler",
    ["ParallelExecutionScheduler", "get_parallel_execution_scheduler", "ExecutionResult"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.multi_source_fusion_engine",
    ["MultiSourceFusionEngine", "get_multi_source_fusion_engine", "FusedResult", "Conflict"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.unified_task_chain",
    ["UnifiedTaskChain", "get_unified_task_chain", "TaskChainResult", "TaskChainContext", "execute_task_chain"])
for k, v in _imports.items(): globals()[k] = v


# ── 优化系统 ──────────────────────────────────────────────

_imports = _safe_import("business.intelligent_optimization_engine",
    ["IntelligentOptimizationEngine", "get_intelligent_optimization_engine"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.token_optimizer",
    ["TokenOptimizer", "get_token_optimizer"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.prompt_cache_manager",
    ["PromptCacheManager", "get_prompt_cache_manager"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.token_compressor",
    ["TokenCompressor", "get_token_compressor"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.cost_manager",
    ["CostManager", "get_cost_manager"])
for k, v in _imports.items(): globals()[k] = v


# ── 自我进化 ──────────────────────────────────────────────

_imports = _safe_import("business.self_evolution_engine",
    ["SelfEvolutionEngine", "get_self_evolution_engine"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.open_ended_evolution",
    ["OpenEndedEvolution", "create_open_ended_evolution"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.rl_driven_improvement",
    ["RLDrivenImprovement", "create_rl_improvement", "RLAlgorithm"])
for k, v in _imports.items(): globals()[k] = v


# ── 技能发现 ──────────────────────────────────────────────

_imports = _safe_import("business.skill_integration_service",
    ["SkillIntegrationService", "get_skill_integration_service"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.skill_discovery",
    ["SkillDiscovery", "create_skill_discovery"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.skill_matcher",
    ["SkillMatcher", "create_skill_matcher"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.skill_graph",
    ["SkillGraph", "create_skill_graph"])
for k, v in _imports.items(): globals()[k] = v


# ── LLM验证器 ─────────────────────────────────────────────

_imports = _safe_import("business.llm_verifier",
    ["LLMVerifier", "create_llm_verifier"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.verifier_integration_service",
    ["VerifierIntegrationService", "get_verifier_integration_service"])
for k, v in _imports.items(): globals()[k] = v


# ── 智能搜索 ──────────────────────────────────────────────

_imports = _safe_import("business.intelligent_search_engine",
    ["IntelligentSearchEngine", "get_intelligent_search_engine"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.web_scraper",
    ["WebScraper", "create_web_scraper"])
for k, v in _imports.items(): globals()[k] = v


# ── 消息工具 ──────────────────────────────────────────────

_imports = _safe_import("business.wecom_tool", ["WeComTool", "get_wecom_tool"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.wechat_tool", ["WeChatTool", "get_wechat_tool"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.message_sync_service",
    ["MessageSyncService", "get_message_sync_service"])
for k, v in _imports.items(): globals()[k] = v


# ── 配置引导 ──────────────────────────────────────────────

_imports = _safe_import("business.config_assistant",
    ["ConfigGuideAssistant", "get_config_assistant", "ConfigGap", "GuideAction"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.config_scene_selector",
    ["ConfigSceneSelector", "SceneConfig"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.smart_config_recommender",
    ["SmartConfigRecommender", "get_smart_recommender", "Recommendation"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.config_version_manager",
    ["ConfigVersionManager", "get_version_manager", "ConfigVersion"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.smart_config_detector",
    ["SmartConfigDetector", "get_config_detector"])
for k, v in _imports.items(): globals()[k] = v


# ── 稳定性与性能优化 ──────────────────────────────────────

_imports = _safe_import("business.circuit_breaker",
    ["LayeredCircuitBreaker", "get_circuit_breaker", "CircuitBreaker", "BreakerState"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.health_monitor",
    ["HealthMonitor", "get_health_monitor", "HealthResult", "Alert"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.graceful_degradation",
    ["GracefulDegradation", "get_degradation_manager", "DegradationLevel"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.priority_task_queue",
    ["PriorityTaskQueue", "get_task_queue", "TaskPriority"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.distributed_tracer",
    ["DistributedTracer", "get_tracer", "Trace", "Span"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.smart_profiler",
    ["SmartProfiler", "get_profiler", "ProfileResult", "OptimizationSuggestion"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.adaptive_resource_scheduler",
    ["AdaptiveResourceScheduler", "get_resource_scheduler", "LoadMonitor"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.stability_init",
    ["StabilityManager", "stability", "with_circuit_breaker",
     "with_profiling", "with_tracing", "cached", "submit_task"])
for k, v in _imports.items(): globals()[k] = v


# ── 意图管理 ──────────────────────────────────────────────

_imports = _safe_import("business.intent_management",
    ["UnifiedIntentHub", "get_unified_intent_hub", "IntentDefinition", "IntentPriority",
     "SmartIntentRecognizer", "get_smart_intent_recognizer", "IntentResult", "IntentCandidate",
     "DeepSemanticAnalyzer", "get_deep_semantic_analyzer", "SemanticAnalysis",
     "SemanticRole", "SentimentType", "DomainType", "ComplexityLevel",
     "AdaptiveReasoningFramework", "get_adaptive_reasoning_framework",
     "ReasoningStrategyType", "TaskType", "ReasoningResult",
     "IntelligentCacheSystem", "get_intelligent_cache_system", "CacheLayer"])
for k, v in _imports.items(): globals()[k] = v


# ── 事件总线 ──────────────────────────────────────────────

_imports = _safe_import("business.shared.event_bus",
    ["EventBus", "Event", "EVENTS", "get_event_bus", "subscribe_event", "publish_event"])
for k, v in _imports.items(): globals()[k] = v


# ── 微内核 ────────────────────────────────────────────────

_imports = _safe_import("business.microkernel.kernel",
    ["Microkernel", "get_kernel", "init_kernel", "shutdown_kernel"])
for k, v in _imports.items(): globals()[k] = v

_imports = _safe_import("business.microkernel.lifecycle",
    ["LifecycleManager", "LifecycleState", "LifecycleEvent"])
for k, v in _imports.items(): globals()[k] = v
