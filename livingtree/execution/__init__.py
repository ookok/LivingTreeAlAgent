"""Execution layer — Task planning, orchestration, self-healing, and cognitive evolution.

Exports: TaskPlanner, Orchestrator, SelfHealer, ThinkingEvolution, MultiAgentQualityChecker,
PlanValidator, FitnessLandscape, DiffusionPlanner, PipelineOptimizer
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
from .batch_executor import BatchExecutor, BatchMode, BatchTask, create_batch_executor
from .continuation import ContinuationEngine, ExecutionSnapshot, LLMContextSnapshot, CONTINUATION_ENGINE, get_continuation_engine
from .react_executor import ReactExecutor, ReactConfig, ReactTrajectory, ReactStep, ReactAction, ExecutionMode, route_execution, get_react_executor
from .plan_validator import PlanValidator, ValidationResult, PlanStep, get_plan_validator
from .fitness_landscape import FitnessLandscape, FitnessVector, TrajectoryScore, get_fitness_landscape
from .diffusion_planner import DiffusionPlanner, DiffusionStep, RefinedPlan, get_diffusion_planner
from .real_pipeline import PipelineOptimizer, get_pipeline_optimizer

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
    "BatchExecutor", "BatchMode", "BatchTask", "create_batch_executor",
    "ContinuationEngine", "ExecutionSnapshot", "LLMContextSnapshot", "CONTINUATION_ENGINE", "get_continuation_engine",
    "ReactExecutor", "ReactConfig", "ReactTrajectory", "ReactStep", "ReactAction",
    "ExecutionMode", "route_execution", "get_react_executor",
    "PlanValidator", "ValidationResult", "PlanStep", "get_plan_validator",
    "FitnessLandscape", "FitnessVector", "TrajectoryScore", "get_fitness_landscape",
    "DiffusionPlanner", "DiffusionStep", "RefinedPlan", "get_diffusion_planner",
    "PipelineOptimizer", "get_pipeline_optimizer",
]
