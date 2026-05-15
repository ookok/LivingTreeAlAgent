"""Dialectical Logic — 辩证逻辑：矛盾运动 + 量变质变."""
from .reasoning_hub import (
    ContradictionTracker, Contradiction, ContradictionPole, ContradictionState,
    PhaseTransitionMonitor, PhaseTransition, Phase,
    get_contradiction_tracker, get_phase_transition_monitor,
)

__all__ = [
    "ContradictionTracker", "Contradiction", "ContradictionPole", "ContradictionState",
    "PhaseTransitionMonitor", "PhaseTransition", "Phase",
    "get_contradiction_tracker", "get_phase_transition_monitor",
]
