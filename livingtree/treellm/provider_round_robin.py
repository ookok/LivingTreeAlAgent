"""ProviderRoundRobin — Prevents single-provider overheating via cooldown.

When the same provider is used consecutively, a cooldown factor is applied
to its election score, encouraging diversity and preventing rate-limit storms.

Integration:
    rr = get_provider_round_robin()
    factor = rr.cooldown_factor(provider_name)
    score.scores["sticky"] *= factor    # in holistic_election scoring
    rr.mark_used(provider_name)         # after successful call
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional


class ProviderRoundRobin:
    """Cooldown-based provider rotation to prevent overheating."""

    _instance: Optional["ProviderRoundRobin"] = None

    @classmethod
    def instance(cls) -> "ProviderRoundRobin":
        if cls._instance is None:
            cls._instance = ProviderRoundRobin()
        return cls._instance

    def __init__(self):
        self._consecutive: dict[str, int] = defaultdict(int)
        self._last_used: str = ""
        self._total_switches = 0

    def cooldown_factor(self, provider: str) -> float:
        """Return 0.0-1.0 multiplier. Lower = more cooldown needed."""
        streak = self._consecutive.get(provider, 0)
        if streak >= 5:
            return 0.5
        if streak >= 3:
            return 0.7
        if streak >= 1:
            return 0.85
        return 1.0

    def mark_used(self, provider: str) -> None:
        """Record that this provider was used for the current request."""
        if provider != self._last_used:
            self._total_switches += 1
            self._consecutive[self._last_used] = 0
        self._consecutive[provider] += 1
        self._last_used = provider

    def should_rotate(self, provider: str) -> bool:
        """Return True if we should force-rotate away from this provider."""
        return self._consecutive.get(provider, 0) >= 5

    def stats(self) -> dict:
        return {
            "last_used": self._last_used,
            "switches": self._total_switches,
            "streaks": {k: v for k, v in self._consecutive.items() if v > 1},
        }


_round_robin: Optional[ProviderRoundRobin] = None


def get_provider_round_robin() -> ProviderRoundRobin:
    global _round_robin
    if _round_robin is None:
        _round_robin = ProviderRoundRobin()
    return _round_robin


__all__ = ["ProviderRoundRobin", "get_provider_round_robin"]
