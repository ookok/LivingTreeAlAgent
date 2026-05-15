"""LivingTree Reasoning Layer — 四大逻辑统一推理引擎.

形式逻辑:   思维确定性 — 规则推理 + 三段论验证
数理逻辑:   形式化 — FOL知识表示 + 贝叶斯概率推理
辩证逻辑:   矛盾运动 — 矛盾追踪 + 量变质变监控
历史逻辑:   实践检验 — 归因迭代 + 层累演进 + A/B评估

四大逻辑共同构成人类从抽象推理到具体实践、
从静态分析到动态把握、从形式规范到内容本质的完整认知链条。
"""

from .formal import (
    RuleEngine, Rule, Fact, FactStatus,
    SyllogismVerifier, CategoricalProposition, Quantifier, SyllogismFigure, SyllogismResult,
)
from .mathematical import (
    KnowledgeRepresentation, Predicate, Individual, Axiom,
    BayesianReasoner, Hypothesis, Evidence,
    get_knowledge_representation, get_bayesian_reasoner,
)
from .dialectical import (
    ContradictionTracker, Contradiction, ContradictionPole, ContradictionState,
    PhaseTransitionMonitor, PhaseTransition, Phase,
    get_contradiction_tracker, get_phase_transition_monitor,
)
from .historical import (
    AttributionLoop, Attribution,
    LayeringTracker, Layer, EmergentCapability,
    ConsensusMeasure, ABComparison, TrialResult, DecisionOutcome,
    get_layering_tracker, get_consensus_measure,
)

__all__ = [
    # Formal Logic
    "RuleEngine", "Rule", "Fact", "FactStatus",
    "SyllogismVerifier", "CategoricalProposition", "Quantifier", "SyllogismFigure", "SyllogismResult",
    # Mathematical Logic
    "KnowledgeRepresentation", "Predicate", "Individual", "Axiom",
    "BayesianReasoner", "Hypothesis", "Evidence",
    # Dialectical Logic
    "ContradictionTracker", "Contradiction", "ContradictionPole", "ContradictionState",
    "PhaseTransitionMonitor", "PhaseTransition", "Phase",
    "get_contradiction_tracker", "get_phase_transition_monitor",
    # Historical Logic
    "AttributionLoop", "Attribution",
    "LayeringTracker", "Layer", "EmergentCapability",
    "ConsensusMeasure", "ABComparison", "TrialResult", "DecisionOutcome",
    "get_layering_tracker", "get_consensus_measure",
]
