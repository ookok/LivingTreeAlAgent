"""
Skill 自进化系统 - 统一入口

借鉴 GenericAgent 的设计思想，实现 Hermes Desktop 的 Skill 自主进化功能。

核心架构：
┌─────────────────────────────────────────────────────────────┐
│                    分层记忆系统 (L0-L4)                       │
├─────────────────────────────────────────────────────────────┤
│  L0: Meta Rules（元规则）    - Agent 基础行为约束              │
│  L1: Insight Index（索引）  - 记忆索引，快速路由与召回          │
│  L2: Global Facts（事实）   - 长期积累的稳定知识                │
│  L3: Task Skills/SOPs      - 可复用工作流程（技能核心）         │
│  L4: Session Archive       - 已完成任务的提炼归档              │
└─────────────────────────────────────────────────────────────┘

技能进化流程：
[遇到新任务] → [自主摸索] → [将执行路径固化为 Skill] → [写入 L3] → [下次直接调用]

使用示例：
    from client.src.business.skill_evolution import create_agent

    agent = create_agent(
        db_path="~/.hermes-desktop/evolution/evolution.db",
        workspace_root="d:/mhzyapp/hermes-desktop",
    )

    result = agent.execute_task("帮我读取 config.py 文件")
"""

from pathlib import Path

# 数据目录
_DATA_DIR = Path.home() / ".hermes-desktop" / "evolution"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

from .models import (
    # 枚举
    MemoryLayer,
    SkillEvolutionStatus,
    TaskStatus,
    ExecutionPhase,
    # 数据类
    MetaRule,
    InsightIndex,
    GlobalFact,
    TaskSkill,
    SessionArchive,
    TaskContext,
    ExecutionRecord,
    # 工具函数
    generate_id,
    generate_skill_id,
)

from .database import EvolutionDatabase
from .engine import EvolutionEngine, ConsolidationResult, MergeSuggestion
from .atom_tools import (
    UnifiedToolHandler,
    ToolResult,
    FileTools,
    CodeTools,
    WebTools,
    DialogTools,
    get_default_tools,
    get_tool_schemas,
)
from .agent_loop import (
    SkillEvolutionAgent,
    SimpleLLMClient,
    create_agent,
)

# A-EVOLVE 集成
from .evolution_strategy import (
    EvolutionStrategyType,
    EvolutionGoal,
    EvolutionStrategy,
    TargetedEvolutionStrategy,
    ScalingEvolutionStrategy,
    OpenEndedEvolutionStrategy,
    EvolutionStrategyManager,
    EvolutionMonitor,
)

from .a_evolve_integration import (
    AEvolveConfig,
    AEvolveIntegrator,
    integrate_a_evolve,
    get_a_evolve_integrator,
    evolve_skill_with_feedback,
    get_skill_health,
)

# 实验循环集成
from ..experiment_loop import (
    OptimizationGoal,
    MetricType,
    ExperimentResult,
    ExperimentSummary,
    ExperimentLoop,
    CodeOptimizationExperiment,
    SystemResourceExperiment,
    CustomExperiment,
    ExperimentManager,
    ExperimentDrivenEvolution,
    ExperimentDashboard,
    create_experiment_driven_evolution,
    create_experiment_dashboard,
)

__all__ = [
    # 枚举
    "MemoryLayer",
    "SkillEvolutionStatus",
    "TaskStatus",
    "ExecutionPhase",
    # 数据类
    "MetaRule",
    "InsightIndex",
    "GlobalFact",
    "TaskSkill",
    "SessionArchive",
    "TaskContext",
    "ExecutionRecord",
    # 工具函数
    "generate_id",
    "generate_skill_id",
    # 核心组件
    "EvolutionDatabase",
    "EvolutionEngine",
    "ConsolidationResult",
    "MergeSuggestion",
    "UnifiedToolHandler",
    "ToolResult",
    "FileTools",
    "CodeTools",
    "WebTools",
    "DialogTools",
    "get_default_tools",
    "get_tool_schemas",
    "SkillEvolutionAgent",
    "SimpleLLMClient",
    "create_agent",
    # A-EVOLVE 集成
    "EvolutionStrategyType",
    "EvolutionGoal",
    "EvolutionStrategy",
    "TargetedEvolutionStrategy",
    "ScalingEvolutionStrategy",
    "OpenEndedEvolutionStrategy",
    "EvolutionStrategyManager",
    "EvolutionMonitor",
    "AEvolveConfig",
    "AEvolveIntegrator",
    "integrate_a_evolve",
    "get_a_evolve_integrator",
    "evolve_skill_with_feedback",
    "get_skill_health",
    # 实验循环集成
    "OptimizationGoal",
    "MetricType",
    "ExperimentResult",
    "ExperimentSummary",
    "ExperimentLoop",
    "CodeOptimizationExperiment",
    "SystemResourceExperiment",
    "CustomExperiment",
    "ExperimentManager",
    "ExperimentDrivenEvolution",
    "ExperimentDashboard",
    "create_experiment_driven_evolution",
    "create_experiment_dashboard",
]

# 默认数据库路径
DEFAULT_DB_PATH = str(_DATA_DIR / "evolution.db")
