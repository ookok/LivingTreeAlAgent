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
]
