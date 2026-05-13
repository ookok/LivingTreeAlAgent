"""LatencyOracle — Predict per-provider latency and determine optimal timeout.

Uses historical latency EMA × query complexity × time-of-day factor to predict
how long each provider will take. Providers predicted to exceed timeout are
skipped early, saving wait time. Also recommends per-provider adaptive timeouts.

Integration:
    oracle = get_latency_oracle()
    predicted, viable = oracle.predict(provider, complexity, hour)
    if not viable: continue  # skip this provider
    timeout = oracle.smart_timeout(provider, complexity)
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional

from loguru import logger

PEAK_HOURS = {9, 10, 11, 14, 15, 16, 17, 20, 21}


class LatencyOracle:
    """Predicts provider latency and determines optimal timeouts."""

    _instance: Optional["LatencyOracle"] = None

    @classmethod
    def instance(cls) -> "LatencyOracle":
        if cls._instance is None:
            cls._instance = LatencyOracle()
        return cls._instance

    def __init__(self):
        self._ema_latency: dict[str, float] = defaultdict(lambda: 2000.0)  # ms
        self._ema_alpha = 0.2
        self._predictions = 0

    def record(self, provider: str, latency_ms: float) -> None:
        """Update EMA latency for a provider after each call."""
        old = self._ema_latency[provider]
        self._ema_latency[provider] = old * (1 - self._ema_alpha) + latency_ms * self._ema_alpha

    def predict(self, provider: str, complexity: float = 0.5,
                hour: int = -1, timeout_ms: int = 120000) -> tuple[float, bool]:
        """Predict latency and whether provider will complete within timeout.

        Returns (predicted_ms, viable).
        """
        if hour < 0:
            hour = time.localtime().tm_hour

        base = self._ema_latency.get(provider, 2000.0)
        complexity_factor = 0.4 + complexity * 1.6
        hour_factor = 1.35 if hour in PEAK_HOURS else 1.0

        predicted = base * complexity_factor * hour_factor
        self._predictions += 1

        viable = predicted < timeout_ms * 0.9  # 10% safety margin
        return round(predicted, 0), viable

    def smart_timeout(self, provider: str, complexity: float = 0.5,
                      min_ms: int = 5000, max_ms: int = 120000) -> int:
        """Return adaptive timeout for this provider.

        Predicted latency × 1.5 safety margin, clamped to [min_ms, max_ms].
        """
        predicted, _ = self.predict(provider, complexity)
        return int(min(max(predicted * 1.5, min_ms), max_ms))

    def should_retry(self, provider: str, elapsed_ms: float) -> bool:
        """Return True if a timed-out call should be retried."""
        ema = self._ema_latency.get(provider, 2000.0)
        return elapsed_ms < ema * 0.5  # Only retry if we quit very early

    def stats(self) -> dict:
        return {
            "providers": len(self._ema_latency),
            "predictions": self._predictions,
            "avg_latency_ms": round(
                sum(self._ema_latency.values()) / max(len(self._ema_latency), 1), 0
            ),
        }


_oracle: Optional[LatencyOracle] = None


def get_latency_oracle() -> LatencyOracle:
    global _oracle
    if _oracle is None:
        _oracle = LatencyOracle()
    return _oracle


__all__ = ["LatencyOracle", "get_latency_oracle"]
