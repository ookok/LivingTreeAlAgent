"""
DNA Layer — The life blueprint of the digital organism.
Exports: LifeEngine, Consciousness, Genome, SafetyGuard, SandboxedExecutor
"""
from .life_engine import LifeEngine
from .consciousness import Consciousness, DefaultConsciousness
from .dual_consciousness import DualModelConsciousness
from .living_world import LivingWorld
from .genome import Genome
from .safety import (
    SafetyGuard, SandboxedExecutor, ActionPolicy,
    MerkleAuditChain, MerkleEntry, PathGuard, SSRFGuard, PromptInjectionScanner, KillSwitch,
)
from .cache_optimizer import CacheOptimizer, PrefixCacheTracker
from .tool_repair import ToolCallRepair, repair_tool_call, normalize_command
from .thought_harvest import ThoughtHarvester, HarvestResult, scavenge_thinking
from .conversation_dna import ConversationDNA, SessionGene
from .hitl import HITLManager, HITLConfig, InterventionMode, HITL_MANAGER, get_hitl_manager
from .evolution_store import EvolutionStore, EvolutionLesson, OntologyAuditor, EVOLUTION_STORE, get_evolution_store
from .agent_roles import RoleTriad, AgentRole, RoleAction, TriadSession, ROLE_TRIAD, get_triad
from .security_context import SecurityContext, Capability, SandboxExecutor, SEC_CTX, get_security_context, get_sandbox
from .meta_memory import MetaMemory, StrategyRecord, GatingRecord, ToolEvent, get_meta_memory
from .meta_strategy import (
    MetaStrategy, MetaStrategyEngine, MetaStrategyVersion,
    ObservationStrategy, GenerationStrategy, DeploymentStrategy,
    get_meta_strategy_engine,
)
from .model_spec import AgentSpec, SpecPrinciple, get_agent_spec
from .output_compressor import compress_output, CompressResult, compress_conversation
from .self_evolving import SelfEvolvingEngine, ProcessMetrics
from .self_evolving_rules import SelfEvolvingRules, RuleCandidate, EvolutionStats, get_self_evolving_rules
from .gradual_agent import GradualAgent, GradualResult, EscalationTier, get_gradual_agent
from .reasoning_chain import ReasoningChain, DecisionNode, ChainSummary, get_reasoning_chain
from .skill_progression import SkillProgression, SkillMetric, ProgressReport, Milestone, get_skill_progression
from .autonomous_core import AutonomousCore, DiscoveredWork, ActionPlan, AuditFinding, CycleResult, IntentType, get_autonomous_core
from .local_intelligence import LocalIntelligence, IntelligenceTier, TierResponse, LocalIQ, get_local_intelligence
from .autonomous_goals import (
    AutonomousGoal, GoalStatus, PatternCategory, ObservedPattern, GoalStats,
    PatternObserver, AutonomousGoalEngine, get_autonomous_goals,
)
from .gep_protocol import GEPProtocol, EvolutionEvent, get_gep_protocol

__all__ = [
    "LifeEngine",
    "Consciousness", "DefaultConsciousness", "DualModelConsciousness",
    "LivingWorld", "Genome",
    "SafetyGuard", "SandboxedExecutor", "ActionPolicy",
    "MerkleAuditChain", "MerkleEntry", "PathGuard", "SSRFGuard", "PromptInjectionScanner", "KillSwitch",
    "CacheOptimizer", "PrefixCacheTracker",
    "ToolCallRepair", "repair_tool_call", "normalize_command",
    "ThoughtHarvester", "HarvestResult", "scavenge_thinking",
    "ConversationDNA", "SessionGene",
    "HITLManager", "HITLConfig", "InterventionMode", "HITL_MANAGER", "get_hitl_manager",
    "EvolutionStore", "EvolutionLesson", "OntologyAuditor", "EVOLUTION_STORE", "get_evolution_store",
    "RoleTriad", "AgentRole", "RoleAction", "TriadSession", "ROLE_TRIAD", "get_triad",
    "SecurityContext", "Capability", "SandboxExecutor", "SEC_CTX", "get_security_context", "get_sandbox",
    "MetaMemory", "StrategyRecord", "GatingRecord", "ToolEvent", "get_meta_memory",
    "MetaStrategy", "MetaStrategyEngine", "MetaStrategyVersion",
    "ObservationStrategy", "GenerationStrategy", "DeploymentStrategy",
    "get_meta_strategy_engine",
    "AgentSpec", "SpecPrinciple", "get_agent_spec",
    "compress_output", "CompressResult", "compress_conversation",
    "SelfEvolvingEngine", "ProcessMetrics",
    "GradualAgent", "GradualResult", "EscalationTier", "get_gradual_agent",
    "ReasoningChain", "DecisionNode", "ChainSummary", "get_reasoning_chain",
    "SkillProgression", "SkillMetric", "ProgressReport", "Milestone", "get_skill_progression",
    "AutonomousCore", "DiscoveredWork", "ActionPlan", "AuditFinding", "CycleResult", "IntentType",
    "get_autonomous_core",
    "LocalIntelligence", "IntelligenceTier", "TierResponse", "LocalIQ", "get_local_intelligence",
    "AutonomousGoal", "GoalStatus", "PatternCategory", "ObservedPattern", "GoalStats",
    "PatternObserver", "AutonomousGoalEngine", "get_autonomous_goals",
    "GEPProtocol", "EvolutionEvent", "get_gep_protocol",
]
