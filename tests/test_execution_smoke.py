"""Smoke tests for execution/ module — verify imports and basic instantiation.

Tests 35-file execution layer: TaskPlanner, Orchestrator, SelfHealer,
HumanInTheLoop, TaskCheckpoint, CostAware, DAGExecutor, ReactExecutor,
PlanValidator, FitnessLandscape, DiffusionPlanner, and more.
"""

import pytest


class TestExecutionImports:
    """Verify all key execution classes import without error."""

    def test_import_task_planner(self):
        from livingtree.execution import TaskPlanner, TaskSpec, SubTask
        assert TaskPlanner is not None
        assert TaskSpec is not None
        assert SubTask is not None

    def test_import_orchestrator(self):
        from livingtree.execution import Orchestrator, AgentSpec, AgentRole
        assert Orchestrator is not None
        assert AgentSpec is not None
        assert AgentRole is not None

    def test_import_self_healer(self):
        from livingtree.execution import SelfHealer, HealthCheck, RecoveryAction
        assert SelfHealer is not None
        assert HealthCheck is not None
        assert RecoveryAction is not None

    def test_import_thinking_evolution(self):
        from livingtree.execution import ThinkingEvolution, EvolutionCandidate, ElitePool
        assert ThinkingEvolution is not None
        assert EvolutionCandidate is not None
        assert ElitePool is not None

    def test_import_quality_checker(self):
        from livingtree.execution import MultiAgentQualityChecker, CheckResult, CheckStatus
        assert MultiAgentQualityChecker is not None
        assert CheckResult is not None
        assert CheckStatus is not None

    def test_import_hitl(self):
        from livingtree.execution import HumanInTheLoop, ApprovalRequest
        assert HumanInTheLoop is not None
        assert ApprovalRequest is not None

    def test_import_checkpoint(self):
        from livingtree.execution import TaskCheckpoint, CheckpointState
        assert TaskCheckpoint is not None
        assert CheckpointState is not None

    def test_import_cost_aware(self):
        from livingtree.execution import CostAware, BudgetStatus
        assert CostAware is not None
        assert BudgetStatus is not None

    def test_import_dag_executor(self):
        from livingtree.execution import DAGExecutor, add_dependencies
        assert DAGExecutor is not None
        assert add_dependencies is not None

    def test_import_react_executor(self):
        from livingtree.execution import (
            ReactExecutor, ReactConfig, ReactTrajectory, ReactStep,
            ReactAction, ExecutionMode, route_execution, get_react_executor,
        )
        assert ReactExecutor is not None
        assert ReactConfig is not None
        assert ReactTrajectory is not None
        assert ReactStep is not None
        assert ReactAction is not None
        assert ExecutionMode is not None

    def test_import_plan_validator(self):
        from livingtree.execution import PlanValidator, ValidationResult, PlanStep
        assert PlanValidator is not None
        assert ValidationResult is not None
        assert PlanStep is not None

    def test_import_fitness_landscape(self):
        from livingtree.execution import FitnessLandscape, FitnessVector, TrajectoryScore
        assert FitnessLandscape is not None
        assert FitnessVector is not None
        assert TrajectoryScore is not None

    def test_import_diffusion_planner(self):
        from livingtree.execution import DiffusionPlanner, DiffusionStep, RefinedPlan
        assert DiffusionPlanner is not None
        assert DiffusionStep is not None
        assert RefinedPlan is not None

    def test_import_rlm(self):
        from livingtree.execution import RLMRunner, RLMSplitter, RLMTask, RLMResult, RLMAggregate
        assert RLMRunner is not None
        assert RLMSplitter is not None
        assert RLMTask is not None

    def test_import_sub_agent_roles(self):
        from livingtree.execution import SubAgentRoles, RoleTask, RoleDefinition
        from livingtree.execution import IMPLEMENTER_ROLE, VERIFIER_ROLE
        assert SubAgentRoles is not None
        assert RoleTask is not None
        assert RoleDefinition is not None
        assert IMPLEMENTER_ROLE is not None
        assert VERIFIER_ROLE is not None

    def test_import_session_manager(self):
        from livingtree.execution import SessionManager, SessionState
        assert SessionManager is not None
        assert SessionState is not None

    def test_import_batch_executor(self):
        from livingtree.execution import BatchExecutor, BatchMode, BatchTask
        assert BatchExecutor is not None
        assert BatchMode is not None
        assert BatchTask is not None

    def test_import_continuation(self):
        from livingtree.execution import ContinuationEngine, ExecutionSnapshot, LLMContextSnapshot
        from livingtree.execution import CONTINUATION_ENGINE
        assert ContinuationEngine is not None
        assert ExecutionSnapshot is not None
        assert LLMContextSnapshot is not None

    def test_no_import_crash_execution_all(self):
        """Import all 25+ execution exports — verify no crash."""
        from livingtree.execution import (
            TaskPlanner, Orchestrator, SelfHealer,
            ThinkingEvolution, MultiAgentQualityChecker,
            HumanInTheLoop, TaskCheckpoint, CostAware,
            DAGExecutor, ReactExecutor, PlanValidator,
            FitnessLandscape, DiffusionPlanner,
            RLMRunner, SubAgentRoles, SessionManager,
            BatchExecutor, ContinuationEngine,
            SideGit, PipelineOptimizer,
        )
        assert all([
            TaskPlanner, Orchestrator, SelfHealer,
            ThinkingEvolution, MultiAgentQualityChecker,
            HumanInTheLoop, TaskCheckpoint, CostAware,
            DAGExecutor, ReactExecutor, PlanValidator,
            FitnessLandscape, DiffusionPlanner,
            RLMRunner, SubAgentRoles, SessionManager,
            BatchExecutor, ContinuationEngine,
        ])


class TestTaskPlannerBasic:
    """Test TaskPlanner basic instantiation."""

    def test_task_planner_instantiate(self):
        from livingtree.execution import TaskPlanner
        planner = TaskPlanner(max_depth=3)
        assert planner is not None
        assert hasattr(planner, "max_depth")
        assert planner.max_depth == 3


class TestOrchestratorBasic:
    """Test Orchestrator basic instantiation."""

    def test_orchestrator_instantiate(self):
        from livingtree.execution import Orchestrator
        orch = Orchestrator(max_agents=5, max_parallel=3)
        assert orch is not None
        assert hasattr(orch, "max_agents")
        assert orch.max_agents == 5
        assert orch.max_parallel == 3


class TestSelfHealerBasic:
    """Test SelfHealer basic instantiation."""

    def test_self_healer_instantiate(self):
        from livingtree.execution import SelfHealer
        healer = SelfHealer(check_interval=30.0)
        assert healer is not None
        assert hasattr(healer, "check_interval")
        assert healer.check_interval == 30.0


class TestCostAwareBasic:
    """Test CostAware budget tracking."""

    def test_cost_aware_instantiate(self):
        from livingtree.execution import CostAware
        ca = CostAware(daily_budget_tokens=500000)
        assert ca is not None
        assert hasattr(ca, "daily_budget")  # Check budget-related attrs exist


class TestHumanInTheLoopBasic:
    """Test HITL basic instantiation."""

    def test_hitl_instantiate(self):
        from livingtree.execution import HumanInTheLoop
        hitl = HumanInTheLoop(default_timeout=120.0)
        assert hitl is not None


class TestTaskCheckpointBasic:
    """Test TaskCheckpoint basic instantiation."""

    def test_checkpoint_instantiate(self):
        from livingtree.execution import TaskCheckpoint
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as td:
            cp = TaskCheckpoint(store_path=os.path.join(td, "checkpoints"))
            assert cp is not None
