"""
GSD (Get Shit Done) 集成模块

规格驱动开发系统，专注于上下文工程和多代理协作
解决 context rot 问题，提高 AI 代码生成质量

参考 https://github.com/gsd-build/get-shit-done
"""

from .gsd_engine import (
    GSDEngine,
    GSDConfig,
    GSDPhase,
    GSDPlan,
    GSDTask,
    GSDWorkspace,
    ProjectMetadata,
    get_gsd_engine,
)

from .context_engineering import (
    ContextManager,
    ContextScope,
    get_context_manager,
)

from .planning import (
    Planner,
    ResearchAgent,
    Executor,
    Verifier,
    WaveExecutor,
    get_planner,
)

from .state_manager import (
    StateManager,
    ProjectState,
    PhaseState,
    get_state_manager,
)

from .commands import (
    GSDCommands,
    get_gsd_commands,
)

__all__ = [
    "GSDEngine",
    "GSDConfig",
    "GSDPhase",
    "GSDPlan",
    "GSDTask",
    "GSDWorkspace",
    "ProjectMetadata",
    "get_gsd_engine",
    "ContextManager",
    "ContextScope",
    "get_context_manager",
    "Planner",
    "ResearchAgent",
    "Executor",
    "Verifier",
    "WaveExecutor",
    "get_planner",
    "StateManager",
    "ProjectState",
    "PhaseState",
    "get_state_manager",
    "GSDCommands",
    "get_gsd_commands",
]