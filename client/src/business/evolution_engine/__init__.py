"""
Evolution Engine - 智能IDE自我进化系统 (向后兼容层)

⚠️ 已迁移至 livingtree.core.evolution
本模块保留为兼容层，所有导入将自动重定向到新位置。
"""

from livingtree.core.evolution.evolution_engine import EvolutionEngine, create_evolution_engine
from livingtree.core.evolution.sensors.base import BaseSensor, SensorType, EvolutionSignal
from livingtree.core.evolution.sensors.performance_sensor import PerformanceSensor
from livingtree.core.evolution.sensors.architecture_smell_sensor import ArchitectureSmellSensor
from livingtree.core.evolution.aggregator.signal_aggregator import SignalAggregator
from livingtree.core.evolution.proposal.structured_proposal import (
    StructuredProposal, ProposalType, ProposalPriority,
    ProposalStatus, RiskLevel, TriggerSignal, ProposalStep,
)
from livingtree.core.evolution.proposal.proposal_generator import ProposalGenerator
from livingtree.core.evolution.safety.safety_fence import SafetyFence, SafetyRule, SafetyCategory
from livingtree.core.evolution.executor.git_sandbox import GitSandbox, SandboxSnapshot
from livingtree.core.evolution.executor.atomic_executor import AtomicExecutor, AtomicResult
from livingtree.core.evolution.executor.rollback_manager import RollbackManager, RollbackPoint, RollbackType
from livingtree.core.evolution.executor.step_executor import StepExecutor, StepExecutionResult, StepStatus
from livingtree.core.evolution.exploratory_executor import (
    ExploratoryExecutor, CandidateSolution, CandidateStatus, ExplorationResult,
)
from livingtree.core.evolution.memory.evolution_log import (
    EvolutionLog, ScanRecord, ProposalRecord, ExecutionRecord, DecisionRecord, get_evolution_log,
)
from livingtree.core.evolution.memory.learning_engine import (
    LearningEngine, ProposalMetrics, SignalPattern, LearningInsight, get_learning_engine,
)
from livingtree.core.evolution.memory.pattern_miner import (
    PatternMiner, TemporalPattern, CoOccurrencePattern,
    CausalPattern, AnomalyPattern, get_pattern_miner,
)
from livingtree.core.evolution.memory.decision_tracker import (
    DecisionTracker, DecisionType, DecisionOutcome,
    DecisionContext, DecisionFactor, DecisionNode, ExecutionChain, get_decision_tracker,
)
from livingtree.core.evolution.ui_integration import (
    init_evolution_engine, init_evolution_dashboard,
    connect_dashboard_to_engine, get_evolution_engine,
    create_evolution_snapshot, quick_start,
)
from livingtree.core.evolution.evaluator.evolution_evaluator import (
    EvolutionEvaluator, EvaluationMode, CapabilityDimension,
    CapabilityScore, EvolutionMetrics,
)
from livingtree.core.evolution.evaluator.base_evaluator import (
    BaseEvaluator, EvaluationResult, MetricScore,
)

__all__ = [
    'EvolutionEngine', 'create_evolution_engine',
    'BaseSensor', 'SensorType', 'EvolutionSignal', 'PerformanceSensor', 'ArchitectureSmellSensor',
    'SignalAggregator',
    'StructuredProposal', 'ProposalType', 'ProposalPriority', 'ProposalStatus', 'RiskLevel',
    'TriggerSignal', 'ProposalStep', 'ProposalGenerator',
    'SafetyFence', 'SafetyRule', 'SafetyCategory',
    'GitSandbox', 'SandboxSnapshot', 'AtomicExecutor', 'AtomicResult',
    'RollbackManager', 'RollbackPoint', 'RollbackType',
    'StepExecutor', 'StepExecutionResult', 'StepStatus',
    'ExploratoryExecutor', 'CandidateSolution', 'CandidateStatus', 'ExplorationResult',
    'EvolutionLog', 'ScanRecord', 'ProposalRecord', 'ExecutionRecord', 'DecisionRecord',
    'get_evolution_log', 'LearningEngine', 'ProposalMetrics', 'SignalPattern',
    'LearningInsight', 'get_learning_engine',
    'PatternMiner', 'TemporalPattern', 'CoOccurrencePattern',
    'CausalPattern', 'AnomalyPattern', 'get_pattern_miner',
    'DecisionTracker', 'DecisionType', 'DecisionOutcome',
    'DecisionContext', 'DecisionFactor', 'DecisionNode', 'ExecutionChain', 'get_decision_tracker',
    'init_evolution_engine', 'init_evolution_dashboard',
    'connect_dashboard_to_engine', 'get_evolution_engine',
    'create_evolution_snapshot', 'quick_start',
    'EvolutionEvaluator', 'EvaluationMode', 'CapabilityDimension',
    'CapabilityScore', 'EvolutionMetrics', 'BaseEvaluator', 'EvaluationResult', 'MetricScore',
]
