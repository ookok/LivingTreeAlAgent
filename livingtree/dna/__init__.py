"""
DNA Layer — The life blueprint of the digital organism.
Exports: LifeEngine, Consciousness, Genome, SafetyGuard, SandboxedExecutor
"""
from .life_engine import LifeEngine
from .consciousness import Consciousness, DefaultConsciousness
from .llm_consciousness import LLMConsciousness
from .dual_consciousness import DualModelConsciousness
from .living_world import LivingWorld
from .genome import Genome
from .safety import SafetyGuard, SandboxedExecutor, ActionPolicy, AuditTrail, KillSwitch

__all__ = [
    "LifeEngine",
    "Consciousness", "DefaultConsciousness", "LLMConsciousness", "DualModelConsciousness",
    "LivingWorld",
    "Genome",
    "SafetyGuard", "SandboxedExecutor", "ActionPolicy", "AuditTrail", "KillSwitch",
]
