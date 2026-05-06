"""Dialectical Logic — 辩证逻辑：矛盾运动 + 量变质变."""
from .contradiction_tracker import ContradictionTracker, Contradiction, ContradictionPole, ContradictionState
from .phase_transition import PhaseTransitionMonitor, PhaseTransition, Phase

__all__ = [
    "ContradictionTracker", "Contradiction", "ContradictionPole", "ContradictionState",
    "PhaseTransitionMonitor", "PhaseTransition", "Phase",
]
