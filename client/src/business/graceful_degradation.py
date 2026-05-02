"""
Graceful Degradation — Compatibility Stub

Functionality integrated into livingtree.core.evolution.reflection (Repairer).
"""

from enum import Enum


class DegradationLevel(Enum):
    FULL = "full"
    REDUCED = "reduced"
    MINIMAL = "minimal"
    OFFLINE = "offline"


class GracefulDegradation:
    def __init__(self):
        self._level = DegradationLevel.FULL

    @property
    def level(self):
        return self._level

    def degrade(self, reason: str = ""):
        levels = list(DegradationLevel)
        idx = levels.index(self._level)
        if idx < len(levels) - 1:
            self._level = levels[idx + 1]


def get_degradation_manager():
    return GracefulDegradation()


__all__ = ["GracefulDegradation", "get_degradation_manager", "DegradationLevel"]
