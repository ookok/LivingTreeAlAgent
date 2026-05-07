"""Evolution — Unified self-evolution engine for code + compression rules.

This module consolidates the DNA layer's two evolution systems:
  - SelfEvolvingEngine (code evolution, DGM-H pattern)
  - SelfEvolvingRules (compression rule evolution, TACO-inspired)

Both follow the observe→generate→test→deploy lifecycle. This module provides
a unified import path while keeping the original implementations intact.

Usage:
    from livingtree.dna.evolution import (
        SelfEvolvingEngine, ProcessMetrics,
        SelfEvolvingRules, RuleCandidate, EvolutionStats,
        get_self_evolving_rules,
    )
"""

from .self_evolving import SelfEvolvingEngine, ProcessMetrics
from .self_evolving_rules import (
    SelfEvolvingRules, RuleCandidate, EvolutionStats,
    get_self_evolving_rules, reset_self_evolving_rules,
)

__all__ = [
    "SelfEvolvingEngine", "ProcessMetrics",
    "SelfEvolvingRules", "RuleCandidate", "EvolutionStats",
    "get_self_evolving_rules", "reset_self_evolving_rules",
]
