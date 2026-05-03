"""Execution layer — Task planning, orchestration, self-healing, and cognitive evolution.

Exports: TaskPlanner, Orchestrator, SelfHealer, ThinkingEvolution, MultiAgentQualityChecker
"""

from .task_planner import TaskPlanner, TaskSpec, SubTask
from .orchestrator import Orchestrator, AgentSpec, AgentRole
from .self_healer import SelfHealer, HealthCheck, RecoveryAction
from .thinking_evolution import ThinkingEvolution, EvolutionCandidate, ElitePool, EvolutionResult
from .quality_checker import MultiAgentQualityChecker, CheckResult, CheckStatus, QualityReport

__all__ = [
    "TaskPlanner", "TaskSpec", "SubTask",
    "Orchestrator", "AgentSpec", "AgentRole",
    "SelfHealer", "HealthCheck", "RecoveryAction",
    "ThinkingEvolution", "EvolutionCandidate", "ElitePool", "EvolutionResult",
    "MultiAgentQualityChecker", "CheckResult", "CheckStatus", "QualityReport",
]
