"""Thompson Sampling Router — Bayesian adaptive model selection.

Based on Dirac (1928) quantum superposition analogy:
  - Each provider exists in a superposition of quality states
  - Each call = a "measurement" that collapses a sample
  - Thompson Sampling = the optimal Bayesian strategy for exploration/exploitation

Based on Vaswani et al. (2017) attention + Schaeffer et al. (2023):
  - Not "magic emergence" — it's learned from observed data
  - Attention weights = posterior belief distributions over provider quality

Fully replaces static weights in HolisticElection with adaptive Beta-distribution sampling.

Integration:
    router = ThompsonRouter(election_engine)
    provider = router.select(candidates, task_type)  # replaces get_best()
    router.record(provider, success, latency, cost)   # update posteriors
"""

from __future__ import annotations

import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══ Bayesian State ═══


@dataclass
class BetaBelief:
    """Beta-distribution belief about a single metric dimension.

    Beta(α, β) where:
      α = successes + prior_α  (effective positive evidence)
      β = failures + prior_β   (effective negative evidence)
    Mean = α / (α + β), Variance = αβ / ((α+β)²(α+β+1))
    """
    alpha: float = 1.0     # Prior: uniform Beta(1,1)
    beta: float = 1.0
    prior_alpha: float = 1.0
    prior_beta: float = 1.0

    @property
    def mean(self) -> float:
        denom = self.alpha + self.beta
        return self.alpha / denom if denom > 0 else 0.5

    @property
    def variance(self) -> float:
        denom = (self.alpha + self.beta) ** 2 * (self.alpha + self.beta + 1)
        return (self.alpha * self.beta) / denom if denom > 0 else 0.25

    @property
    def uncertainty(self) -> float:
        """Higher = more exploration needed."""
        return math.sqrt(self.variance)

    def observe_success(self, weight: float = 1.0) -> None:
        self.alpha += weight

    def observe_failure(self, weight: float = 1.0) -> None:
        self.beta += weight

    def sample(self) -> float:
        """Thompson sample from Beta(α, β)."""
        return random.betavariate(self.alpha, self.beta)

    def decay(self, rate: float = 0.001) -> None:
        """Gradually decay toward prior (forgets old data)."""
        self.alpha = self.prior_alpha + (self.alpha - self.prior_alpha) * (1 - rate)
        self.beta = self.prior_beta + (self.beta - self.prior_beta) * (1 - rate)


@dataclass
class ProviderBandit:
    """Multi-dimensional bandit arm for a single provider.

    Tracks Beta beliefs for each scoring dimension:
      - quality: success/failure rate of outputs
      - latency: fast/slow response (fast = success)
      - cost: below/above expected cost (below = success)
    """
    provider_name: str
    quality: BetaBelief = field(default_factory=BetaBelief)
    latency: BetaBelief = field(default_factory=BetaBelief)
    cost_belief: BetaBelief = field(default_factory=BetaBelief)
    total_calls: int = 0
    last_sample_time: float = 0.0
    composite_samples: list[float] = field(default_factory=list)  # Recent Thompson samples

    def sample_composite(self, weights: dict[str, float] | None = None) -> float:
        """Thompson sample from all dimensions, weighted."""
        w = weights or {"quality": 0.5, "latency": 0.25, "cost_belief": 0.25}
        score = (
            w.get("quality", 0.5) * self.quality.sample()
            + w.get("latency", 0.25) * self.latency.sample()
            + w.get("cost_belief", 0.25) * self.cost_belief.sample()
        )
        self.last_sample_time = time.time()
        self.composite_samples.append(score)
        if len(self.composite_samples) > 100:
            self.composite_samples = self.composite_samples[-100:]
        return score

    @property
    def expected_value(self) -> float:
        """Posterior mean — best estimate without exploration."""
        return (
            0.5 * self.quality.mean
            + 0.25 * self.latency.mean
            + 0.25 * self.cost_belief.mean
        )

    @property
    def exploration_bonus(self) -> float:
        """Uncertainty — how much we should explore this arm."""
        return (
            0.5 * self.quality.uncertainty
            + 0.25 * self.latency.uncertainty
            + 0.25 * self.cost_belief.uncertainty
        )

    def stats(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "quality_mean": round(self.quality.mean, 3),
            "quality_uncertainty": round(self.quality.uncertainty, 3),
            "latency_mean": round(self.latency.mean, 3),
            "cost_mean": round(self.cost_belief.mean, 3),
            "expected_value": round(self.expected_value, 3),
            "total_calls": self.total_calls,
        }


# ═══ Thompson Sampling Router ═══


class ThompsonRouter:
    """Bayesian multi-armed bandit router for LLM provider selection.

    Dirac (1928) analog:
      - Providers are quantum states: |provider_i⟩ = α_i|success⟩ + β_i|failure⟩
      - Routing = measurement that collapses the superposition
      - Thompson Sampling = the optimal measurement strategy

    Schaeffer et al. (2023) lesson:
      - No magic: gains come from systematic exploration, not emergent miracles
      - Track all dimensions: rein in overconfidence with uncertainty estimates
    """

    def __init__(
        self,
        decay_rate: float = 0.0001,        # Per-call belief decay toward prior
        exploration_weight: float = 0.15,   # UCB exploration bonus weight
        min_calls_for_exploit: int = 10,    # Minimum data before exploitation mode
    ):
        self._arms: dict[str, ProviderBandit] = {}
        self._decay_rate = decay_rate
        self._exploration_weight = exploration_weight
        self._min_calls_for_exploit = min_calls_for_exploit
        self._total_selections = 0

    # ── Arm Management ──

    def get_arm(self, provider_name: str) -> ProviderBandit:
        if provider_name not in self._arms:
            self._arms[provider_name] = ProviderBandit(provider_name=provider_name)
        return self._arms[provider_name]

    def register_provider(
        self, name: str, quality_prior: tuple[float, float] = (1, 1),
        latency_prior: tuple[float, float] = (2, 1),
        cost_prior: tuple[float, float] = (1, 1),
    ) -> ProviderBandit:
        arm = self.get_arm(name)
        arm.quality.prior_alpha, arm.quality.prior_beta = quality_prior
        arm.quality.alpha, arm.quality.beta = quality_prior
        arm.latency.prior_alpha, arm.latency.prior_beta = latency_prior
        arm.latency.alpha, arm.latency.beta = latency_prior
        arm.cost_belief.prior_alpha, arm.cost_belief.prior_beta = cost_prior
        arm.cost_belief.alpha, arm.cost_belief.beta = cost_prior
        return arm

    # ── Selection ──

    def select(
        self,
        candidates: list[str],
        task_type: str = "general",
        top_n: int = 3,
    ) -> list[tuple[str, float]]:
        """Thompson-sample the best N providers.

        Uses UCB-style bonus: score = expected_value + exploration_bonus × weight
        This balances exploitation (high expected value) with exploration (high uncertainty).

        Returns:
            List of (provider_name, thompson_score) sorted descending
        """
        arms = [self.get_arm(c) for c in candidates]
        weights = self._dimension_weights(task_type)

        scored: list[tuple[str, float]] = []
        for arm in arms:
            # Thompson sample: draw from posterior
            ts = arm.sample_composite(weights)
            # UCB bonus: encourage exploring uncertain arms
            ucb = arm.exploration_bonus * self._exploration_weight
            # Cold start boost: new providers get temporary exploration bonus
            cold_boost = 0.0
            if arm.total_calls < self._min_calls_for_exploit:
                cold_boost = 0.3 * (1 - arm.total_calls / self._min_calls_for_exploit)

            score = ts + ucb + cold_boost
            scored.append((arm.provider_name, round(score, 4)))

        scored.sort(key=lambda x: -x[1])
        self._total_selections += 1

        # Periodic decay
        if self._total_selections % 100 == 0:
            self._decay_all()

        return scored[:top_n]

    def select_best(self, candidates: list[str], task_type: str = "general") -> str:
        """Select the single best provider (most common use case)."""
        result = self.select(candidates, task_type, top_n=1)
        return result[0][0] if result else (candidates[0] if candidates else "")

    def select_explore(self, candidates: list[str], top_n: int = 2) -> list[str]:
        """Pure exploration: select providers with highest uncertainty."""
        arms = [(self.get_arm(c), c) for c in candidates]
        arms.sort(key=lambda x: -x[0].exploration_bonus)
        return [name for _, name in arms[:top_n]]

    # ── Feedback (Observer Collapse) ──

    def record_success(
        self, provider_name: str, latency_ms: float, cost_yuan: float,
    ) -> None:
        """Record a successful call — collapses toward |success⟩."""
        arm = self.get_arm(provider_name)
        arm.total_calls += 1
        arm.quality.observe_success(weight=1.0)

        # ── Synaptic LTP: strengthen provider as synapse ──
        try:
            from ..core.synaptic_plasticity import get_plasticity
            get_plasticity().strengthen(f"provider:{provider_name}", boost=0.8)
        except ImportError:
            pass

        # Latency: fast is good (inverse scoring)
        latency_fast = max(0.0, min(1.0, 1.0 - latency_ms / 10000.0))
        if latency_fast > 0.5:
            arm.latency.observe_success(weight=latency_fast)
        else:
            arm.latency.observe_failure(weight=1.0 - latency_fast)

        # Cost: cheap is good
        cost_good = max(0.0, min(1.0, 1.0 - cost_yuan / 0.1))
        if cost_good > 0.5:
            arm.cost_belief.observe_success(weight=cost_good)
        else:
            arm.cost_belief.observe_failure(weight=1.0 - cost_good)

    def record_failure(self, provider_name: str) -> None:
        """Record a failed call — collapses toward |failure⟩."""
        arm = self.get_arm(provider_name)
        arm.total_calls += 1
        arm.quality.observe_failure(weight=1.0)
        arm.latency.observe_failure(weight=0.5)
        arm.cost_belief.observe_failure(weight=0.3)

        # ── Synaptic LTD: weaken provider synapse ──
        try:
            from ..core.synaptic_plasticity import get_plasticity
            get_plasticity().weaken(f"provider:{provider_name}", penalty=1.0)
        except ImportError:
            pass

    def record_rate_limit(self, provider_name: str) -> None:
        """Record a rate limit — strong failure signal."""
        arm = self.get_arm(provider_name)
        arm.quality.observe_failure(weight=2.0)  # Double penalty
        arm.latency.observe_failure(weight=1.0)

    # ── Analysis ──

    def _dimension_weights(self, task_type: str) -> dict[str, float]:
        """Dimension weight schedule per task type."""
        schedules = {
            "code": {"quality": 0.5, "latency": 0.2, "cost_belief": 0.3},
            "reasoning": {"quality": 0.6, "latency": 0.1, "cost_belief": 0.3},
            "chat": {"quality": 0.3, "latency": 0.5, "cost_belief": 0.2},
            "search": {"quality": 0.3, "latency": 0.3, "cost_belief": 0.4},
            "multimodal": {"quality": 0.5, "latency": 0.2, "cost_belief": 0.3},
            "general": {"quality": 0.4, "latency": 0.3, "cost_belief": 0.3},
        }
        return schedules.get(task_type, schedules["general"])

    def _decay_all(self) -> None:
        """Apply decay to all arms — forgets stale evidence."""
        for arm in self._arms.values():
            arm.quality.decay(self._decay_rate)
            arm.latency.decay(self._decay_rate)
            arm.cost_belief.decay(self._decay_rate)

    def all_stats(self) -> list[dict[str, Any]]:
        """Return stats for all tracked providers."""
        return [arm.stats() for arm in self._arms.values()]

    def best_provider(self) -> str:
        """Provider with highest expected value (no exploration)."""
        if not self._arms:
            return ""
        return max(self._arms.values(), key=lambda a: a.expected_value).provider_name

    def most_explored(self) -> str:
        """Provider with most calls."""
        if not self._arms:
            return ""
        return max(self._arms.values(), key=lambda a: a.total_calls).provider_name

    def least_certain(self) -> str:
        """Provider with highest uncertainty — needs more exploration."""
        if not self._arms:
            return ""
        return max(self._arms.values(), key=lambda a: a.exploration_bonus).provider_name

    # ── Initialization from existing stats ──

    def warm_start(self, election_engine=None) -> None:
        """Initialize priors from existing HolisticElection RouterStats."""
        if election_engine is None:
            return
        try:
            stats = election_engine.get_all_stats()
            for name, s in stats.items():
                arm = self.get_arm(name)
                calls = s.get("calls", 0)
                successes = s.get("successes", 0)
                failures = s.get("failures", 0)
                if calls > 0:
                    arm.total_calls = calls
                    arm.quality.alpha = successes + 1
                    arm.quality.beta = failures + 1
                    arm.latency_mean = s.get("avg_latency_ms", 500)
                    # Quality-rate informed latency prior
                    rate = s.get("success_rate", 0.5)
                    arm.latency.alpha = rate * calls + 1
                    arm.latency.beta = (1 - rate) * calls + 1
                    arm.cost_belief.alpha = rate * calls * 0.5 + 1
                    arm.cost_belief.beta = (1 - rate) * calls * 0.5 + 1
        except Exception:
            pass


# ═══ Singleton ═══

_bandit_router: ThompsonRouter | None = None


def get_bandit_router() -> ThompsonRouter:
    global _bandit_router
    if _bandit_router is None:
        _bandit_router = ThompsonRouter()
    return _bandit_router


def initialize_from_election(election_engine=None) -> ThompsonRouter:
    """Initialize the bandit router from an existing HolisticElection engine."""
    router = get_bandit_router()
    router.warm_start(election_engine)
    return router


__all__ = [
    "ThompsonRouter", "ProviderBandit", "BetaBelief",
    "get_bandit_router", "initialize_from_election",
]
