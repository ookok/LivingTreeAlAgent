"""AdaptiveWeights — Real-time load-adaptive election weight adjustment.

Dynamically modifies election weights based on:
  - Time of day (peak hours prioritize latency)
  - Global latency health (all providers slow → prioritize speed)
  - Provider count (few providers → prioritize quality over cost)
  - Failure rate (high errors → boost exploration weight)

Integration:
    aw = get_adaptive_weights()
    weights = aw.adjust(base_weights, providers_stats, hour, failures)
"""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger

PEAK_HOURS = {9, 10, 11, 14, 15, 16, 17, 20, 21, 22}


class AdaptiveWeights:
    """Real-time load-adaptive weight adjustment."""

    _instance: Optional["AdaptiveWeights"] = None

    @classmethod
    def instance(cls) -> "AdaptiveWeights":
        if cls._instance is None:
            cls._instance = AdaptiveWeights()
        return cls._instance

    def __init__(self):
        self._adjustment_count = 0

    def adjust(
        self, base: dict[str, float], providers_stats: dict[str, Any],
        hour: int = -1, failure_count: int = 0, provider_count: int = 18,
    ) -> dict[str, float]:
        """Return adjusted weights based on current load conditions."""
        import time as _time
        w = dict(base)
        self._adjustment_count += 1

        if hour < 0:
            hour = _time.localtime().tm_hour

        # Peak hours: prioritize latency
        if hour in PEAK_HOURS:
            w["latency"] = w.get("latency", 0.18) * 1.35
            w["quality"] = w.get("quality", 0.23) * 0.75
            w["cost"] = w.get("cost", 0.15) * 0.85

        # Night hours (0-6): quality over speed
        if 0 <= hour <= 6:
            w["quality"] = w.get("quality", 0.23) * 1.2
            w["latency"] = w.get("latency", 0.18) * 0.7
            w["cost"] = w.get("cost", 0.15) * 0.9

        # Global latency check: all providers slow → prioritize speed
        if providers_stats:
            latencies = [
                s.get("avg_latency_ms", 200) for s in providers_stats.values()
                if s.get("calls", 0) > 0
            ]
            if latencies:
                avg_lat = sum(latencies) / len(latencies)
                if avg_lat > 3000:
                    w["latency"] = w.get("latency", 0.18) * 1.5
                    w["cost"] = w.get("cost", 0.15) * 0.5
                elif avg_lat > 1500:
                    w["latency"] = w.get("latency", 0.18) * 1.2
                    w["cost"] = w.get("cost", 0.15) * 0.7

        # Few providers available → prioritize quality over cost
        if provider_count < 5:
            w["quality"] = w.get("quality", 0.23) * 1.3
            w["cost"] = w.get("cost", 0.15) * 0.6

        # High failure rate → boost exploration
        if failure_count > provider_count * 0.3:
            w["exploration"] = w.get("exploration", 0.04) * 2.0
            w["elo"] = w.get("elo", 0.08) * 0.5

        # Normalize to sum ~1.0
        total = sum(w.values())
        if total > 0:
            target = 1.0
            ratio = target / total
            w = {k: round(v * ratio, 4) for k, v in w.items()}

        return w

    def stats(self) -> dict:
        return {"adjustments": self._adjustment_count}


_adaptive: Optional[AdaptiveWeights] = None


def get_adaptive_weights() -> AdaptiveWeights:
    global _adaptive
    if _adaptive is None:
        _adaptive = AdaptiveWeights()
    return _adaptive


__all__ = ["AdaptiveWeights", "get_adaptive_weights"]
