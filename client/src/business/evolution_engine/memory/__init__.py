# memory 模块 - 进化记忆层

"""
Evolution Memory - Phase 4 进化记忆层

核心组件：
1. EvolutionLog - SQLite 进化日志持久化
2. LearningEngine - 强化学习引擎
3. PatternMiner - 模式挖掘器
4. DecisionTracker - 决策追踪器
"""

from .evolution_log import (
    EvolutionLog,
    ScanRecord,
    ProposalRecord,
    ExecutionRecord,
    DecisionRecord,
    get_evolution_log
)

from .learning_engine import (
    LearningEngine,
    ProposalMetrics,
    SignalPattern,
    LearningInsight,
    get_learning_engine
)

from .pattern_miner import (
    PatternMiner,
    TemporalPattern,
    CoOccurrencePattern,
    CausalPattern,
    AnomalyPattern,
    get_pattern_miner
)

from .decision_tracker import (
    DecisionTracker,
    DecisionType,
    DecisionOutcome,
    DecisionContext,
    DecisionFactor,
    DecisionNode,
    ExecutionChain,
    get_decision_tracker
)

__all__ = [
    # EvolutionLog
    'EvolutionLog',
    'ScanRecord',
    'ProposalRecord',
    'ExecutionRecord',
    'DecisionRecord',
    'get_evolution_log',
    
    # LearningEngine
    'LearningEngine',
    'ProposalMetrics',
    'SignalPattern',
    'LearningInsight',
    'get_learning_engine',
    
    # PatternMiner
    'PatternMiner',
    'TemporalPattern',
    'CoOccurrencePattern',
    'CausalPattern',
    'AnomalyPattern',
    'get_pattern_miner',
    
    # DecisionTracker
    'DecisionTracker',
    'DecisionType',
    'DecisionOutcome',
    'DecisionContext',
    'DecisionFactor',
    'DecisionNode',
    'ExecutionChain',
    'get_decision_tracker',
]
