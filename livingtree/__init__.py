"""LivingTree AI Agent — Digital Lifeform Platform v2.1.0

A self-learning, self-evolving, self-healing digital life form for:
- Autonomous chat and task execution
- Industrial report generation (EIA, emergency plans, etc.)
- AI cell training and knowledge distillation
- P2P network discovery and collaboration
- Multi-agent task orchestration

TreeLLM-powered multi-provider routing (DeepSeek, LongCat, Xiaomi, Aliyun, etc.)
"""

import os

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

__version__ = "2.0.0"
__author__ = "LivingTree Team"

# Lightweight imports — always available immediately
from .config import LTAIConfig, get_config, reload_config
from .observability import setup_observability, get_logger

__all__ = [
    "__version__",
    "LifeEngine", "Genome", "Consciousness", "DefaultConsciousness",
    "DualModelConsciousness", "SafetyGuard",
    "CellAI", "CellRegistry", "CellTrainer", "Mitosis", "Phage", "Regen",
    "Distillation", "SwiftDrillTrainer",
    "KnowledgeBase", "VectorStore", "KnowledgeGraph", "FormatDiscovery",
    "GapDetector",
    "SkillFactory", "ToolMarket", "DocEngine", "CodeEngine", "MaterialCollector",
    "Node", "Discovery", "NATTraverser", "Reputation",
    "TaskPlanner", "Orchestrator", "SelfHealer",
    "IntegrationHub", "launch", "LaunchMode",
    "LTAIConfig", "get_config", "reload_config",
    "setup_observability", "get_logger",
    "LivingTreeTuiApp", "ChatScreen", "CodeScreen", "KnowledgeScreen",
    "SettingsScreen",
    "CacheOptimizer", "ToolCallRepair", "ThoughtHarvester",
    "RLMRunner", "SideGit", "SubAgentRoles", "SessionManager",
    "LSPManager", "SSEAgentServer", "SkillDiscoveryManager",
    "StructMemory",
    # Economy
    "EconomicOrchestrator", "EconomicPolicy", "ROIModel", "ComplianceGate",
    # RAG 2.0
    "AgenticRAG", "Reranker",
    # Execution (new)
    "PlanValidator", "FitnessLandscape", "DiffusionPlanner", "PipelineOptimizer",
]


# Lazy imports map — modules only loaded on first access
_LAZY = {
    # DNA
    "LifeEngine": ".dna",
    "Genome": ".dna",
    "Consciousness": ".dna",
    "DefaultConsciousness": ".dna",
    "DualModelConsciousness": ".dna",
    "SafetyGuard": ".dna",
    # Cell
    "CellAI": ".cell",
    "CellRegistry": ".cell",
    "CellTrainer": ".cell",
    "Mitosis": ".cell",
    "Phage": ".cell",
    "Regen": ".cell",
    "Distillation": ".cell",
    "SwiftDrillTrainer": ".cell",
    # Knowledge
    "KnowledgeBase": ".knowledge",
    "VectorStore": ".knowledge",
    "KnowledgeGraph": ".knowledge",
    "FormatDiscovery": ".knowledge",
    "GapDetector": ".knowledge",
    # Capability
    "SkillFactory": ".capability",
    "ToolMarket": ".capability",
    "DocEngine": ".capability",
    "CodeEngine": ".capability",
    "MaterialCollector": ".capability",
    # Network
    "Node": ".network",
    "Discovery": ".network",
    "NATTraverser": ".network",
    "Reputation": ".network",
    # Execution
    "TaskPlanner": ".execution",
    "Orchestrator": ".execution",
    "SelfHealer": ".execution",
    # Integration
    "IntegrationHub": ".integration",
    "launch": ".integration",
    "LaunchMode": ".integration",
    # TUI
    "LivingTreeTuiApp": ".tui",
    "ChatScreen": ".tui",
    "CodeScreen": ".tui",
    "KnowledgeScreen": ".tui",
    "SettingsScreen": ".tui",
    # Economy
    "EconomicOrchestrator": ".economy",
    "EconomicPolicy": ".economy",
    "ROIModel": ".economy",
    "ComplianceGate": ".economy",
    # RAG 2.0
    "AgenticRAG": ".knowledge",
    "Reranker": ".knowledge",
    # Execution (new modules)
    "PlanValidator": ".execution",
    "FitnessLandscape": ".execution",
    "DiffusionPlanner": ".execution",
    "PipelineOptimizer": ".execution",
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib
        mod = importlib.import_module(_LAZY[name], __package__)
        attr = getattr(mod, name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
