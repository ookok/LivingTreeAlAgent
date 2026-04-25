# Evolution Engine - 智能IDE自我进化系统

"""
从"执行工具"进化为"设计伙伴"的关键跨越
构建"感知-诊断-规划-执行"闭环自治系统
"""

from .evolution_engine import EvolutionEngine, create_evolution_engine

# 传感器
from .sensors.base import BaseSensor, SensorType, EvolutionSignal
from .sensors.performance_sensor import PerformanceSensor
from .sensors.architecture_smell_sensor import ArchitectureSmellSensor

# 聚合器
from .aggregator.signal_aggregator import SignalAggregator

# 提案生成
from .proposal.structured_proposal import (
    StructuredProposal, ProposalType, ProposalPriority,
    ProposalStatus, RiskLevel, TriggerSignal, ProposalStep
)
from .proposal.proposal_generator import ProposalGenerator

# 安全围栏
from .safety.safety_fence import SafetyFence, SafetyRule, SafetyCategory

# Phase 3: 执行引擎
from .executor.git_sandbox import GitSandbox, SandboxSnapshot
from .executor.atomic_executor import AtomicExecutor, AtomicResult
from .executor.rollback_manager import RollbackManager, RollbackPoint, RollbackType
from .executor.step_executor import StepExecutor, StepExecutionResult, StepStatus

# 探索性执行引擎（新增）
from .exploratory_executor import (
    ExploratoryExecutor,
    CandidateSolution,
    CandidateStatus,
    ExplorationResult,
)

# Phase 4: 进化记忆
from .memory.evolution_log import (
    EvolutionLog, ScanRecord, ProposalRecord,
    ExecutionRecord, DecisionRecord, get_evolution_log
)
from .memory.learning_engine import (
    LearningEngine, ProposalMetrics, SignalPattern,
    LearningInsight, get_learning_engine
)
from .memory.pattern_miner import (
    PatternMiner, TemporalPattern, CoOccurrencePattern,
    CausalPattern, AnomalyPattern, get_pattern_miner
)
from .memory.decision_tracker import (
    DecisionTracker, DecisionType, DecisionOutcome,
    DecisionContext, DecisionFactor, DecisionNode,
    ExecutionChain, get_decision_tracker
)

# UI 集成
from .ui_integration import (
    init_evolution_engine,
    init_evolution_dashboard,
    connect_dashboard_to_engine,
    get_evolution_engine,
    create_evolution_snapshot,
    quick_start,
)

# Phase 5: 量化评估
from .evaluator import (
    EvolutionEvaluator,
    EvaluationMode,
    CapabilityDimension,
    CapabilityScore,
    EvolutionMetrics,
    BaseEvaluator,
    EvaluationResult,
    MetricScore,
    MetricType,
    DCLMEvaluator,
    DCLMScore,
    BPBEvaluator,
    BPBScore,
    BenchmarkEvaluator,
    BenchmarkScore,
    BenchmarkTask,
)

__all__ = [
    # 主控制器
    'EvolutionEngine',
    'create_evolution_engine',
    
    # 传感器
    'BaseSensor',
    'SensorType',
    'EvolutionSignal',
    'PerformanceSensor',
    'ArchitectureSmellSensor',
    
    # 聚合器
    'SignalAggregator',
    
    # 提案生成
    'StructuredProposal',
    'ProposalType',
    'ProposalPriority',
    'ProposalStatus',
    'RiskLevel',
    'TriggerSignal',
    'ProposalStep',
    'ProposalGenerator',
    
    # 安全围栏
    'SafetyFence',
    'SafetyRule',
    'SafetyCategory',
    
    # Phase 3: 执行引擎
    'GitSandbox',
    'SandboxSnapshot',
    'AtomicExecutor',
    'AtomicResult',
    'RollbackManager',
    'RollbackPoint',
    'RollbackType',
    'StepExecutor',
    'StepExecutionResult',
    'StepStatus',
    
    # Phase 4: 进化记忆
    'EvolutionLog',
    'ScanRecord',
    'ProposalRecord',
    'ExecutionRecord',
    'DecisionRecord',
    'get_evolution_log',
    'LearningEngine',
    'ProposalMetrics',
    'SignalPattern',
    'LearningInsight',
    'get_learning_engine',
    'PatternMiner',
    'TemporalPattern',
    'CoOccurrencePattern',
    'CausalPattern',
    'AnomalyPattern',
    'get_pattern_miner',
    'DecisionTracker',
    'DecisionType',
    'DecisionOutcome',
    'DecisionContext',
    'DecisionFactor',
    'DecisionNode',
    'ExecutionChain',
    'get_decision_tracker',
    
    # Phase 5: 量化评估
    'EvolutionEvaluator',
    'EvaluationMode',
    'CapabilityDimension',
    'CapabilityScore',
    'EvolutionMetrics',
    'BaseEvaluator',
    'EvaluationResult',
    'MetricScore',
    'MetricType',
    'DCLMEvaluator',
    'DCLMScore',
    'BPBEvaluator',
    'BPBScore',
    'BenchmarkEvaluator',
    'BenchmarkScore',
    'BenchmarkTask',

    # 探索性执行引擎（新增）
    'ExploratoryExecutor',
    'CandidateSolution',
    'CandidateStatus',
    'ExplorationResult',
]
