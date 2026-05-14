"""HealthPredictor — Pre-failure provider health prediction.

Monitors latency trends and error patterns to predict provider degradation
BEFORE the circuit breaker trips. Proactively down-weights unhealthy providers
so users never experience the failure.

Features:
  - Latency trend: rising latency → degradation signal
  - Error rate: recent error spikes → pre-failure
  - Recovery detection: latencies stabilizing → restore weight

Integration:
    hp = get_health_predictor()
    factor = hp.health_factor(provider_name)      # 1.0=healthy, 0.3=pre-failure
    score.total *= factor                          # applied in holistic_election
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional

from loguru import logger

WINDOW_SECONDS = 600  # 10-minute sliding window


class HealthPredictor:
    """Predicts provider health degradation before circuit breaker trips."""

    _instance: Optional["HealthPredictor"] = None

    @classmethod
    def instance(cls) -> "HealthPredictor":
        if cls._instance is None:
            cls._instance = HealthPredictor()
        return cls._instance

    def __init__(self, window_seconds: int = WINDOW_SECONDS):
        self._window = window_seconds
        self._latencies: dict[str, list[tuple[float, float]]] = defaultdict(list)  # (ts, ms)
        self._errors: dict[str, list[tuple[float, bool]]] = defaultdict(list)       # (ts, is_error)
        self._predictions = 0

    def record(self, provider: str, latency_ms: float, is_error: bool) -> None:
        """Record a provider call outcome."""
        now = time.time()
        self._latencies[provider].append((now, latency_ms))
        self._errors[provider].append((now, is_error))
        self._prune(provider)

    def health_factor(self, provider: str) -> float:
        """Return 0.0-1.0 health factor for election scoring.

        1.0 = healthy, 0.6 = warning, 0.3 = pre-failure, 0.0 = predicted failure.
        """
        self._prune(provider)
        lats = self._latencies.get(provider, [])
        errs = self._errors.get(provider, [])

        if len(lats) < 5:
            return 1.0  # Not enough data → assume healthy

        # Latency trend
        lats_sorted = sorted(lats, key=lambda x: x[0])
        first_half = [l for _, l in lats_sorted[:len(lats_sorted)//2]]
        second_half = [l for _, l in lats_sorted[len(lats_sorted)//2:]]
        avg_first = sum(first_half) / max(len(first_half), 1)
        avg_second = sum(second_half) / max(len(second_half), 1)
        latency_ratio = avg_second / max(avg_first, 1.0)

        # Error rate
        recent_errs = [e for _, e in errs[-10:]]
        error_rate = sum(recent_errs) / max(len(recent_errs), 1) if recent_errs else 0.0

        self._predictions += 1

        # Decision logic
        if error_rate > 0.5 or latency_ratio > 2.0:
            return 0.0   # Predicted failure — exclude
        if error_rate > 0.3 or latency_ratio > 1.5:
            return 0.3   # Pre-failure — heavy penalty
        if error_rate > 0.15 or latency_ratio > 1.2:
            return 0.6   # Warning — moderate penalty
        return 1.0

    def _prune(self, provider: str) -> None:
        """Remove entries older than the sliding window."""
        now = time.time()
        cutoff = now - self._window
        self._latencies[provider] = [(t, l) for t, l in self._latencies[provider] if t > cutoff]
        self._errors[provider] = [(t, e) for t, e in self._errors[provider] if t > cutoff]

    def stats(self) -> dict:
        return {
            "providers_tracked": len(self._latencies),
            "predictions": self._predictions,
        }

    def first_person_health_narrative(self, provider: str) -> str:
        factor = self.health_factor(provider)
        lats = self._latencies.get(provider, [])
        recent_lats = [(t, l) for t, l in lats if t > time.time() - 300]
        avg_latency = sum(l for _, l in recent_lats) / max(len(recent_lats), 1)
        if factor >= 0.9:
            return f"I sense {provider} is healthy — responding in {avg_latency:.0f}ms. I trust it."
        elif factor >= 0.6:
            return f"I notice {provider} has been slowing slightly ({avg_latency:.0f}ms avg). I am watching it."
        elif factor >= 0.3:
            return f"I feel {provider} is degrading — {avg_latency:.0f}ms avg. I am reducing my reliance on it."
        elif factor > 0.0:
            recent_errs = [e for _, e in lats[-5:] if len(lats) >= 5]
            return f"I sense {provider} may fail soon — {avg_latency:.0f}ms. I am avoiding it for now."
        else:
            return f"I have stopped trusting {provider} — it has failed. I will re-evaluate when it stabilizes."

    def introspective_provider_assessment(self) -> dict:
        assessments = {}
        for provider in self._latencies:
            if self.health_factor(provider) < 0.6:
                assessments[provider] = self.first_person_health_narrative(provider)
        return {
            "healthy_count": sum(1 for p in self._latencies if self.health_factor(p) >= 0.6),
            "unhealthy_count": sum(1 for p in self._latencies if self.health_factor(p) < 0.6),
            "narratives": assessments,
            "self_awareness": bool(assessments),
        }


_predictor: Optional[HealthPredictor] = None


def get_health_predictor() -> HealthPredictor:
    global _predictor
    if _predictor is None:
        _predictor = HealthPredictor()
    return _predictor


__all__ = ["HealthPredictor", "get_health_predictor"]
