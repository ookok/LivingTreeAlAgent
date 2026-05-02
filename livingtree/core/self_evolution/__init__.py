"""
自我进化引擎 (Self-Evolution Engine) - 延迟导入

⚠️ 许多子模块依赖尚未迁移的 business/ 模块。
直接导入子模块以获完整功能:
    from livingtree.core.self_evolution.code_tool import CodeTool
"""

__all__ = [
    'SelfEvolutionOrchestrator', 'CodeEvolutionPlanner', 'CodeEvolutionExecutor',
    'CodeTool',
    'ToolMissingDetector', 'AutonomousToolCreator', 'ActiveLearningLoop',
    'SelfReflectionEngine', 'UserClarificationRequester',
    'SafeAutonomousToolCreator', 'ProxySourceManager', 'CLIToolDiscoverer',
    'ModelAutoDetectorAndUpgrader', 'DeterministicExecutor',
    'ModelNativeDSL', 'AntiRationalizationTable',
    'SerenaAdapter', 'KnowledgeIngestionPipeline',
]


def __getattr__(name):
    _lazy_imports = {
        'ToolMissingDetector': 'livingtree.core.self_evolution.tool_missing_detector',
        'AutonomousToolCreator': 'livingtree.core.self_evolution.autonomous_tool_creator',
        'ActiveLearningLoop': 'livingtree.core.self_evolution.active_learning_loop',
        'SelfReflectionEngine': 'livingtree.core.self_evolution.self_reflection_engine',
        'UserClarificationRequester': 'livingtree.core.self_evolution.user_clarification_requester',
        'SafeAutonomousToolCreator': 'livingtree.core.self_evolution.safe_autonomous_tool_creator',
        'ProxySourceManager': 'livingtree.core.self_evolution.proxy_source_manager',
        'CLIToolDiscoverer': 'livingtree.core.self_evolution.cli_tool_discoverer',
        'ModelAutoDetectorAndUpgrader': 'livingtree.core.self_evolution.model_auto_detector_and_upgrader',
        'DeterministicExecutor': 'livingtree.core.self_evolution.deterministic_executor',
        'ModelNativeDSL': 'livingtree.core.self_evolution.model_native_dsl',
        'AntiRationalizationTable': 'livingtree.core.self_evolution.anti_rationalization_table',
        'ProjectStructureScanner': 'livingtree.core.self_evolution.project_structure_scanner',
        'KnowledgeIngestionPipeline': 'livingtree.core.self_evolution.knowledge_ingestion_pipeline',
        'CodeEvolutionPlanner': 'livingtree.core.self_evolution.code_evolution_planner',
        'CodeEvolutionExecutor': 'livingtree.core.self_evolution.code_evolution_executor',
        'SelfEvolutionOrchestrator': 'livingtree.core.self_evolution.self_evolution_orchestrator',
        'SerenaAdapter': 'livingtree.core.self_evolution.serena_adapter',
        'CodeTool': 'livingtree.core.self_evolution.code_tool',
    }
    if name in _lazy_imports:
        import importlib
        module = importlib.import_module(_lazy_imports[name])
        cls = getattr(module, name)
        globals()[name] = cls
        return cls
    raise AttributeError(f"module 'livingtree.core.self_evolution' has no attribute '{name}'")
