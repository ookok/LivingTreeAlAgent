# -*- coding: utf-8 -*-
"""
可视化智能进化引擎 - Visual Intelligent Evolution Engine
========================================================

核心理念：从"黑盒自动化"到"白盒可视化智能进化"

功能：
1. 环境感知可视化 - 系统资源、GPU、网络监控
2. 决策推演引擎 - 升级提案生成与决策树可视化
3. 实时进度可视化 - 进化过程完整展示
4. 模型管理器 - Ollama模型自动升级
5. 状态机可视化 - 进化状态实时展示

Author: Hermes Desktop Team
"""

from .system_monitor import (
    SystemMonitor,
    DashboardData,
    ResourceInfo,
    NetworkInfo,
    ModelInfo,
    get_system_monitor,
)

from .model_manager import (
    ModelManager,
    ModelUpgradeProposal,
    UpgradeDecision,
    UpgradeStage,
    get_model_manager,
)

from .decision_engine import (
    EvolutionDecisionEngine,
    DecisionTree,
    DecisionNode,
    get_decision_engine,
)

from .progress_tracker import (
    ProgressTracker,
    EvolutionProgress,
    StageProgress,
    get_progress_tracker,
)

from .dashboard import (
    EvolutionDashboard,
    DashboardConfig,
    get_evolution_dashboard,
)

__version__ = "1.0.0"

__all__ = [
    # 系统监控
    "SystemMonitor",
    "DashboardData",
    "ResourceInfo",
    "NetworkInfo",
    "ModelInfo",
    "get_system_monitor",
    # 模型管理
    "ModelManager",
    "ModelUpgradeProposal",
    "UpgradeDecision",
    "UpgradeStage",
    "get_model_manager",
    # 决策引擎
    "EvolutionDecisionEngine",
    "DecisionTree",
    "DecisionNode",
    "get_decision_engine",
    # 进度追踪
    "ProgressTracker",
    "EvolutionProgress",
    "StageProgress",
    "get_progress_tracker",
    # 仪表盘
    "EvolutionDashboard",
    "DashboardConfig",
    "get_evolution_dashboard",
]
