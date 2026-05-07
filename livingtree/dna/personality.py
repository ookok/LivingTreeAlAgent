"""Personality — Unified personality and behavior modules.

Consolidates three thin DNA-layer behavior modules:
  - anticipatory.py:  predictive task suggestions (Anticipatory)
  - adaptive_ui.py:   UI adaptation based on context (AdaptiveUI, AdaptiveTheme)
  - biorhythm.py:     agent activity cycle management (Biorhythm, BioMetrics, LifeState)

Usage:
    from livingtree.dna.personality import Anticipatory, AdaptiveUI, Biorhythm
"""

from .anticipatory import Anticipatory
from .adaptive_ui import AdaptiveUI, AdaptiveTheme
from .biorhythm import Biorhythm, BioMetrics, LifeState

__all__ = [
    "Anticipatory", "AdaptiveUI", "AdaptiveTheme",
    "Biorhythm", "BioMetrics", "LifeState",
]
