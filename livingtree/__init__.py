"""LivingTree AI Agent — Digital Lifeform Platform v2.0.0

A self-learning, self-evolving, self-healing digital life form for:
- Autonomous chat and task execution
- Industrial report generation (EIA, emergency plans, etc.)
- AI cell training and knowledge distillation
- P2P network discovery and collaboration
- Multi-agent task orchestration

Uses litellm with local DeepSeek pricing (no remote fetch).
"""

import os
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

__version__ = "2.0.0"
__author__ = "LivingTree Team"

from .dna import LifeEngine, Genome, Consciousness, DefaultConsciousness, DualModelConsciousness, SafetyGuard
from .cell import CellAI, CellRegistry, CellTrainer, Mitosis, Phage, Regen, Distillation
from .knowledge import KnowledgeBase, VectorStore, KnowledgeGraph, FormatDiscovery, GapDetector
from .capability import SkillFactory, ToolMarket, DocEngine, CodeEngine, MaterialCollector
from .network import Node, Discovery, NATTraverser, Reputation
from .execution import TaskPlanner, Orchestrator, SelfHealer
from .integration import IntegrationHub, launch, LaunchMode
from .config import LTAIConfig, get_config, reload_config
from .observability import setup_observability, get_logger
from .tui import LivingTreeTuiApp, ChatScreen, CodeScreen, DocsScreen, SettingsScreen

__all__ = [
    # Version
    "__version__",
    # DNA
    "LifeEngine", "Genome", "Consciousness", "DefaultConsciousness", "DualModelConsciousness", "SafetyGuard",
    # Cell
    "CellAI", "CellRegistry", "CellTrainer", "Mitosis", "Phage", "Regen", "Distillation",
    # Knowledge
    "KnowledgeBase", "VectorStore", "KnowledgeGraph", "FormatDiscovery", "GapDetector",
    # Capability
    "SkillFactory", "ToolMarket", "DocEngine", "CodeEngine", "MaterialCollector",
    # Network
    "Node", "Discovery", "NATTraverser", "Reputation",
    # Execution
    "TaskPlanner", "Orchestrator", "SelfHealer",
    # Integration
    "IntegrationHub", "launch", "LaunchMode",
    # Config
    "LTAIConfig", "get_config", "reload_config",
    "setup_observability", "get_logger",
    "LivingTreeTuiApp", "ChatScreen", "CodeScreen", "DocsScreen", "SettingsScreen",
]
