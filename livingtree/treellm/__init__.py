"""TreeLLM — Lightweight multi-provider LLM routing.

Usage:
    from livingtree.treellm import TreeLLM, create_deepseek_provider, create_longcat_provider

    llm = TreeLLM()
    llm.add_provider(create_deepsek_provider("sk-xxx"))
    llm.add_provider(create_longcat_provider("ak-xxx"))

    result = await llm.chat([{"role": "user", "content": "Hello"}])
    async for token in llm.stream([...]):
        print(token, end="")
"""

from .core import TreeLLM, RouterStats
from .providers import (
    Provider, ProviderResult,
    DeepSeekProvider, LongCatProvider, NvidiaProvider, OpenAILikeProvider,
    create_deepseek_provider, create_longcat_provider, create_nvidia_provider,
)
from .classifier import (
    TinyClassifier,
    QueryClassifier, get_query_classifier,
    AdaptiveClassifier, get_adaptive_classifier,
    AutoClassifier, get_auto_classifier, ClassificationResult,
)
from .prompt_versioning import PromptVersionManager, PromptTemplate, PROMPT_VERSION_MANAGER
from .embedding_scorer import EmbeddingScorer, ModelProfile, get_embedding_scorer
from .foresight_gate import ForesightGate, ForesightDecision, get_foresight_gate
from .onto_prompt_builder import OntoPromptBuilder, get_onto_prompt_builder
from .holistic_election import HolisticElection, ProviderScore, PROVIDER_CAPABILITIES, get_election
from .holistic_election import CausalEffectTracker, CausalEffect, ABTestManager, get_causal_tracker, get_ab_manager
from .router import (
    UnifiedRouter, get_router, RoutingCandidate, RoutingDecision,
    RouteLearner, LearnedProfile, RoutingWeight, get_route_learner,
    ThompsonStrategy, BudgetStrategy, FitnessStrategy,
    PredictiveStrategy, ScoreMatchStrategy,
)
from .synapse_aggregator import SynapseAggregator, SynapseResult, ModelOutput, CrossValidation, get_synapse_aggregator
from .synapse_aggregator import ParliamentSession, Verdict, ParliamentRole, get_parliament
from .competitive_eliminator import CompetitiveEliminator, ModelRanking, get_eliminator
from .strategic_orchestrator import StrategicOrchestrator, OrchestrationPlan, TaskStep, get_orchestrator
from .deep_probe import DeepProbe, ProbeStrategy, ProbeContext, ProbeResult, get_deep_probe
from .adversarial_selfplay import AdversarialSelfPlay, SelfPlayResult, RebuttalRound, PlayStatus, get_selfplay
from .depth_grading import DepthGrader, DepthGrade, DepthDimension, get_depth_grader
from .joint_evolution import JointEvolutionCoordinator, EvolutionTrajectory, JointHealth, get_joint_evolution
from .concurrent_stream import ConcurrentStream, StreamEvent, ConcurrentResult, get_concurrent_stream
from .micro_turn_aware import MicroTurnAware, MicroTurnState, MicroTurnContext, get_micro_turn_aware
from .proactive_interject import ProactiveInterject, InterjectDecision, InterjectTrigger, get_proactive_interject
from .reasoning_budget import ReasoningBudgetEngine, ReasoningBudget, ReasoningTier, get_reasoning_budget
from .fluid_collective import FluidCollective, StigmergicTrace, TransientFormation, MobilityBudget, get_fluid_collective
from .reasoning_dependency_graph import ReasoningDependencyGraph, ReasoningGraph, StepNode, OptimalSchedule, get_reasoning_graph
from .vital_signs import VitalSigns, VitalReport, OrganReport, get_vital_signs

from .providers import (
    create_modelscope_provider, create_bailing_provider,
    create_stepfun_provider, create_internlm_provider,
    create_sensetime_provider,
)

__all__ = [
    "TreeLLM", "RouterStats",
    "Provider", "ProviderResult",
    "DeepSeekProvider", "LongCatProvider", "NvidiaProvider", "OpenAILikeProvider",
    "create_deepseek_provider", "create_longcat_provider", "create_nvidia_provider",
    "TinyClassifier",
    "QueryClassifier", "get_query_classifier",
    "AdaptiveClassifier", "get_adaptive_classifier",
    "AutoClassifier", "get_auto_classifier", "ClassificationResult",
    "PromptVersionManager", "PromptTemplate", "PROMPT_VERSION_MANAGER",
    "EmbeddingScorer", "ModelProfile", "get_embedding_scorer",
    "ForesightGate", "ForesightDecision", "get_foresight_gate",
    "OntoPromptBuilder", "get_onto_prompt_builder",
    "HolisticElection", "ProviderScore", "PROVIDER_CAPABILITIES", "get_election",
    "CausalEffectTracker", "CausalEffect", "ABTestManager", "get_causal_tracker", "get_ab_manager",
    "RouteLearner", "LearnedProfile", "RoutingWeight", "get_route_learner",
    "UnifiedRouter", "get_router", "RoutingCandidate", "RoutingDecision",
    "ThompsonStrategy", "BudgetStrategy", "FitnessStrategy",
    "PredictiveStrategy", "ScoreMatchStrategy",
    "SynapseAggregator", "SynapseResult", "ModelOutput", "CrossValidation", "get_synapse_aggregator",
    "ParliamentSession", "Verdict", "ParliamentRole", "get_parliament",
    "CompetitiveEliminator", "ModelRanking", "get_eliminator",
    "StrategicOrchestrator", "OrchestrationPlan", "TaskStep", "get_orchestrator",
    "DeepProbe", "ProbeStrategy", "ProbeContext", "ProbeResult", "get_deep_probe",
    "AdversarialSelfPlay", "SelfPlayResult", "RebuttalRound", "PlayStatus", "get_selfplay",
    "DepthGrader", "DepthGrade", "DepthDimension", "get_depth_grader",
    "JointEvolutionCoordinator", "EvolutionTrajectory", "JointHealth", "get_joint_evolution",
    "ConcurrentStream", "StreamEvent", "ConcurrentResult", "get_concurrent_stream",
    "MicroTurnAware", "MicroTurnState", "MicroTurnContext", "get_micro_turn_aware",
    "ProactiveInterject", "InterjectDecision", "InterjectTrigger", "get_proactive_interject",
    "ReasoningBudgetEngine", "ReasoningBudget", "ReasoningTier", "get_reasoning_budget",
    "FluidCollective", "StigmergicTrace", "TransientFormation", "MobilityBudget", "get_fluid_collective",
    "ReasoningDependencyGraph", "ReasoningGraph", "StepNode", "OptimalSchedule", "get_reasoning_graph",
    "VitalSigns", "VitalReport", "OrganReport", "get_vital_signs",
    "create_modelscope_provider", "create_bailing_provider",
    "create_stepfun_provider", "create_internlm_provider",
    "create_sensetime_provider",
]
