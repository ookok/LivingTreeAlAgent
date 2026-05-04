"""Execution layer — Task planning, orchestration, self-healing, and cognitive evolution.

Exports: TaskPlanner, Orchestrator, SelfHealer, ThinkingEvolution, MultiAgentQualityChecker
"""

from .task_planner import TaskPlanner, TaskSpec, SubTask
from .orchestrator import Orchestrator, AgentSpec, AgentRole
from .self_healer import SelfHealer, HealthCheck, RecoveryAction
from .thinking_evolution import ThinkingEvolution, EvolutionCandidate, ElitePool
from .quality_checker import MultiAgentQualityChecker, CheckResult, CheckStatus
from .hitl import HumanInTheLoop, ApprovalRequest
from .checkpoint import TaskCheckpoint, CheckpointState
from .cost_aware import CostAware, BudgetStatus
from .dag_executor import DAGExecutor, add_dependencies
from .rlm import RLMRunner, RLMSplitter, RLMTask, RLMResult, RLMAggregate
from .side_git import SideGit, TurnSnapshot
from .sub_agent_roles import SubAgentRoles, RoleTask, RoleDefinition, IMPLEMENTER_ROLE, VERIFIER_ROLE
from .session_manager import SessionManager, SessionState

__all__ = [
    "TaskPlanner", "TaskSpec", "SubTask",
    "Orchestrator", "AgentSpec", "AgentRole",
    "SelfHealer", "HealthCheck", "RecoveryAction",
    "ThinkingEvolution", "EvolutionCandidate", "ElitePool",
    "MultiAgentQualityChecker", "CheckResult", "CheckStatus",
    "HumanInTheLoop", "ApprovalRequest",
    "TaskCheckpoint", "CheckpointState",
    "CostAware", "BudgetStatus",
    "DAGExecutor", "add_dependencies",
    "RLMRunner", "RLMSplitter", "RLMTask", "RLMResult", "RLMAggregate",
    "SideGit", "TurnSnapshot",
    "SubAgentRoles", "RoleTask", "RoleDefinition", "IMPLEMENTER_ROLE", "VERIFIER_ROLE",
    "SessionManager", "SessionState",
]
