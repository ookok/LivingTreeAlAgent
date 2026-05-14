"""LPO — Listwise Policy Optimization (arXiv:2605.06139).

Group-based RLVR as target-projection on the LLM response simplex.

Core innovation (Tsinghua × Tencent, 2026-05-07):
  All group-based policy gradient methods share a common geometric structure:
  each IMPLICITLY defines a target distribution π* on the response simplex and
  projects toward it via first-order approximation.
  LPO makes this EXPLICIT — construct π*, project π_θ → π* via exact divergence
  minimization ∇D(π* || π_θ), yielding:
    (i)  Monotonic improvement with bounded, zero-sum, self-correcting gradients
    (ii) Divergence flexibility through decoupled projection step

LivingTree integration points:
  - SynapseLPO: replace SynapseAggregator._compute_contributions() additive weights
  - ProviderLPO: replace HolisticElection score.total with simplex projection
  - TrajectoryLPO: transform JointEvolution rewards into π* target distribution

Usage:
  from livingtree.optimization import SynapseLPO, ProviderLPO
  sto = SynapseLPO(divergence="kl")
  contribs = sto.project_contributions(rewards)  # replaces _compute_contributions
"""

from __future__ import annotations

import math
from typing import Callable

from loguru import logger

# ── Supported divergences ─────────────────────────────────────────

DIVERGENCES: set[str] = {
    "kl",             # D_KL(π* || π_θ) — forward KL, mode-seeking
    "reverse_kl",     # D_KL(π_θ || π*) — reverse KL, mass-covering
    "jsd",            # Jensen-Shannon — symmetric, bounded in [0, ln2]
    "squared_hellinger",  # H² — sqrt-geometric, bounds TV
    "chi_squared",    # χ²(π* || π_θ) — strongly mode-seeking
}

# ── Divergence gradient functions ─────────────────────────────────

LPO_DIVERGENCE_GRADIENTS: dict[str, Callable[[float, float], float]] = {
    "kl": lambda p_star, p_theta: -p_star / max(p_theta, 1e-12),
    "reverse_kl": lambda p_star, p_theta: math.log(p_theta / max(p_star, 1e-12)) + 1,
    "jsd": lambda p_star, p_theta: 0.5 * (
        math.log(p_theta / max((p_star + p_theta) / 2, 1e-12)) -
        math.log(p_star / max((p_star + p_theta) / 2, 1e-12))
    ),
    "squared_hellinger": lambda p_star, p_theta: (
        0.5 * (1.0 - math.sqrt(p_star / max(p_theta, 1e-12)))
    ),
    "chi_squared": lambda p_star, p_theta: (
        1.0 - p_star / max(p_theta, 1e-12)
    ),
}


class LPOOptimizer:
    """Listwise Policy Optimization — core engine.

    Given a set of N items (provider responses, models, trajectories) each
    with a reward signal, LPO:
      1. constructs explicit target distribution π* = softmax(rewards / T)
      2. computes current policy π_θ from current scores
      3. projects π_θ toward π* by minimizing chosen divergence D(π* || π_θ)
      4. returns updated contributions with monotonic improvement guarantee
    """

    def __init__(self, divergence: str = "kl", temperature: float = 1.0):
        if divergence not in DIVERGENCES:
            raise ValueError(f"Unknown divergence '{divergence}' — choose from {DIVERGENCES}")
        self._divergence = divergence
        self._temperature = temperature
        self._divergence_history: list[float] = []

    @property
    def divergence(self) -> str:
        return self._divergence

    @property
    def temperature(self) -> float:
        return self._temperature

    # ── Step 1: Construct target distribution ──────────────────────

    def construct_target(self, rewards: dict[str, float]) -> dict[str, float]:
        """π* = softmax(rewards / T) — the explicit target distribution.

        Args:
            rewards: dict of {entity_name: reward_score} where higher is better

        Returns:
            dict of {entity_name: target_probability} summing to 1.0
        """
        if not rewards:
            return {}
        t = max(self._temperature, 1e-6)
        exp_values: dict[str, float] = {}
        for name, r in rewards.items():
            exp_values[name] = math.exp(r / t)
        total = sum(exp_values.values())
        if total <= 0:
            n = len(rewards)
            return {k: round(1.0 / n, 6) for k in rewards}
        return {k: round(v / total, 6) for k, v in exp_values.items()}

    # ── Step 2: Project current policy toward target ──────────────

    def project(
        self, current: dict[str, float], target: dict[str, float],
    ) -> dict[str, float]:
        """Project current π_θ toward target π* by minimizing D(π* || π_θ).

        Uses the selected divergence. Gradient is bounded, zero-sum, and
        self-correcting (monotonic improvement guaranteed — D always decreases).

        Returns updated π_θ with learning rate adapted to gradient scale.
        """
        if not current or not target:
            return dict(current)
        keys = list(target.keys())
        n = max(len(keys), 1)
        c_sum = sum(current.get(k, 0.0) for k in keys) or 1.0
        pi_theta = {k: current.get(k, 0.0) / c_sum for k in keys}
        pi_star = target
        grad_fn = LPO_DIVERGENCE_GRADIENTS[self._divergence]
        gradient: dict[str, float] = {}
        for k in keys:
            p_star = pi_star.get(k, 0.0)
            p_theta = max(pi_theta.get(k, 1e-12), 1e-12)
            gradient[k] = grad_fn(p_star, p_theta)
        g_mean = sum(gradient.values()) / n
        zero_sum_grad = {k: g - g_mean for k, g in gradient.items()}
        # Adaptive step: cap gradient magnitude per element
        max_g = max(max(abs(v) for v in zero_sum_grad.values()), 1.0)
        step_size = min(1.0 / n, 0.25 / max_g)
        updated: dict[str, float] = {}
        for k in keys:
            updated[k] = max(0.0, pi_theta[k] - step_size * zero_sum_grad[k])
        u_sum = sum(updated.values()) or 1.0
        result = {k: round(v / u_sum, 6) for k, v in updated.items()}
        d_before = self._compute_divergence(pi_theta, pi_star)
        d_after = self._compute_divergence(result, pi_star)
        self._divergence_history.append(d_after)
        if d_after > d_before + 1e-8:
            logger.debug(
                f"LPO: divergence increased ({d_before:.6f}→{d_after:.6f}), "
                f"clamping to π* (target distribution)"
            )
            result = dict(pi_star)
        else:
            logger.debug(
                f"LPO: monotonic divergence: {d_before:.6f}→{d_after:.6f} "
                f"(Δ={d_before - d_after:.6f})"
            )
        return result

    # ── Step 3: Full optimize — construct + project ───────────────

    def optimize(
        self, current: dict[str, float], rewards: dict[str, float],
    ) -> dict[str, float]:
        """Full LPO pipeline: rewards → π* → project π_θ → updated π_θ."""
        target = self.construct_target(rewards)
        return self.project(current, target)

    # ── Divergence computation ─────────────────────────────────────

    def _compute_divergence(
        self, pi_theta: dict[str, float], pi_star: dict[str, float],
    ) -> float:
        keys = list(pi_star.keys())
        if self._divergence == "kl":
            return sum(
                pi_star[k] * math.log(pi_star[k] / max(pi_theta.get(k, 1e-12), 1e-12))
                for k in keys if pi_star[k] > 0
            )
        elif self._divergence == "reverse_kl":
            return sum(
                pi_theta.get(k, 0.0) * math.log(max(pi_theta.get(k, 1e-12), 1e-12)
                                                 / max(pi_star[k], 1e-12))
                for k in keys if pi_theta.get(k, 0.0) > 0
            )
        elif self._divergence == "jsd":
            m = {k: 0.5 * (pi_star[k] + pi_theta.get(k, 0.0)) for k in keys}
            return 0.5 * (
                sum(pi_star[k] * math.log(pi_star[k] / max(m[k], 1e-12))
                    for k in keys if pi_star[k] > 0) +
                sum(pi_theta[k] * math.log(pi_theta[k] / max(m[k], 1e-12))
                    for k in keys if pi_theta.get(k, 0.0) > 0)
            )
        elif self._divergence == "squared_hellinger":
            return 0.5 * sum(
                (math.sqrt(pi_star[k]) - math.sqrt(max(pi_theta.get(k, 0.0), 0.0))) ** 2
                for k in keys
            )
        elif self._divergence == "chi_squared":
            return sum(
                (pi_star[k] - pi_theta.get(k, 0.0)) ** 2 / max(pi_theta.get(k, 1e-12), 1e-12)
                for k in keys if pi_star[k] > 0
            )
        return 0.0

    # ── Utilities ──────────────────────────────────────────────────

    def set_temperature(self, t: float) -> None:
        self._temperature = max(t, 0.01)

    def set_divergence(self, name: str) -> None:
        if name not in DIVERGENCES:
            raise ValueError(f"Unknown divergence '{name}'")
        self._divergence = name

    def is_monotonic(self) -> bool:
        """Check if optimization has been monotonically improving."""
        if len(self._divergence_history) < 2:
            return True
        return all(
            self._divergence_history[i] >= self._divergence_history[i + 1] - 1e-8
            for i in range(len(self._divergence_history) - 1)
        )

    def reset_history(self) -> None:
        self._divergence_history.clear()


# ── Specializations for LivingTree Integration ────────────────────


class SynapseLPO(LPOOptimizer):
    """LPO for response-level group aggregation.

    Replaces SynapseAggregator._compute_contributions() additive weights.
    Models → explicit π* from quality rewards → project contributions.

    Usage:
        sto = get_synapse_lpo()
        contribs = sto.aggregate_contributions(model_outputs, rewards)
    """

    def __init__(self, divergence: str = "kl", temperature: float = 1.0):
        super().__init__(divergence=divergence, temperature=temperature)

    def aggregate_contributions(
        self,
        outputs: list,
        validations: list | None = None,
        consensus: float = 0.5,
    ) -> dict[str, float]:
        """Compute per-model contribution weight via LPO target-projection.

        This replaces the linear weighted-sum formula with principled
        geometric projection onto the response simplex.

        Args:
            outputs: list of ModelOutput with provider/election_score etc.
            validations: CrossValidation list (unused in LPO, kept for API compat)
            consensus: overall consensus level

        Returns:
            dict of {provider_name: contribution_weight} summing to 1.0
        """
        if not outputs:
            return {}
        # Build reward signals for each model
        rewards: dict[str, float] = {}
        current: dict[str, float] = {}
        for o in outputs:
            r = (o.election_score * 0.25 + o.self_assessment * 0.12
                 + o.depth_score * 0.12 + o.self_verify_score * 0.12)
            rewards[o.provider] = r
            current[o.provider] = r  # initial π_θ = rewards themselves
        if not rewards:
            return {}
        # LPO: construct π* from rewards, project current toward it
        return self.optimize(current, rewards)

    def aggregate_with_consensus(
        self,
        outputs: list,
        validations: list | None = None,
        consensus: float = 0.5,
    ) -> dict[str, float]:
        """Extended aggregation factoring consensus into temperature.

        Higher consensus → lower temperature (sharper π*) → clearer weighting.
        Lower consensus → higher temperature (flatter π*) → more egalitarian.
        """
        t = max(0.1, 1.0 - consensus * 0.9)  # T ∈ [0.1, 1.0]
        self.set_temperature(t)
        return self.aggregate_contributions(outputs, validations, consensus)


class ProviderLPO(LPOOptimizer):
    """LPO for provider selection routing.

    Replaces HolisticElection's additive score.total with simplex projection.
    Providers → explicit π* from capability/reward profile → project scores.

    Usage:
        pto = get_provider_lpo()
        scores = pto.rank_providers(provider_metrics)
    """

    def __init__(self, divergence: str = "kl", temperature: float = 0.5):
        super().__init__(divergence=divergence, temperature=temperature)

    def rank_providers(
        self, metrics: dict[str, dict[str, float]],
        weights: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """Rank providers via LPO target-projection on the provider simplex.

        Args:
            metrics: {provider: {dimension: score (0-1)}}
            weights: {dimension: weight} — if None, equal weight

        Returns:
            dict of {provider: lpo_score} (not necessarily summing to 1)
        """
        if not metrics:
            return {}
        w = weights or {}
        all_dims = set()
        for m in metrics.values():
            all_dims.update(m.keys())
        dims = list(all_dims)
        if not w:
            w = {d: 1.0 / len(dims) for d in dims} if dims else {}
        # Compute weighted rewards
        rewards: dict[str, float] = {}
        for name, m in metrics.items():
            rewards[name] = sum(w.get(d, 0.0) * m.get(d, 0.0) for d in dims)
        # LPO projection
        current = dict(rewards)
        projected = self.optimize(current, rewards)
        # Scale back to original reward range while preserving LPO ordering
        max_r = max(rewards.values()) if rewards else 1.0
        return {k: round(v * max_r / max(projected.values(), 1e-12), 4)
                for k, v in projected.items()}


class TrajectoryLPO(LPOOptimizer):
    """LPO for trajectory-level provider optimization.

    Transforms JointEvolution's independent EMA rewards into a simplex
    target distribution. Providers with high trajectory success get
    heavier π* mass; underperformers get proportionally less.

    Usage:
        tto = TrajectoryLPO()
        target = tto.build_trajectory_target(long_term_rewards)
    """

    def __init__(self, divergence: str = "reverse_kl", temperature: float = 0.8):
        super().__init__(divergence=divergence, temperature=temperature)

    def build_trajectory_target(
        self, long_term_rewards: dict[str, float],
    ) -> dict[str, float]:
        """Build explicit π* target from trajectory-level rewards.

        Uses reverse-KL by default (mass-covering) to keep all viable
        providers in the distribution rather than collapsing to a single mode.
        """
        if not long_term_rewards:
            return {}
        # Shift rewards to be non-negative (LPO requires positive softmax)
        min_r = min(long_term_rewards.values())
        shifted = {k: v - min_r + 0.01 for k, v in long_term_rewards.items()}
        return self.construct_target(shifted)

    def inject_to_election(
        self, long_term_rewards: dict[str, float],
    ) -> dict[str, float]:
        """Produce LPO-based election modifiers from trajectory rewards.

        Returns: {provider: modifier} where values are zero-sum
        (some positive + others negative → total ≈ 0).

        This replaces JointEvolution.inject_rewards_to_election()'s
        simple reward * 0.3 scaling with LPO's principled projection.
        """
        target = self.build_trajectory_target(long_term_rewards)
        if not target:
            return {}
        # Uniform current → project toward target
        n = len(target)
        uniform = {k: 1.0 / n for k in target}
        projected = self.project(uniform, target)
        # Convert to zero-sum modifiers: deviation from uniform
        return {k: round(v - 1.0 / n, 4) for k, v in projected.items()}


# ── Singletons ────────────────────────────────────────────────────


_lpo_optimizer: LPOOptimizer | None = None
_synapse_lpo: SynapseLPO | None = None
_provider_lpo: ProviderLPO | None = None


def get_lpo_optimizer(
    divergence: str = "kl", temperature: float = 1.0,
) -> LPOOptimizer:
    global _lpo_optimizer
    if _lpo_optimizer is None:
        _lpo_optimizer = LPOOptimizer(divergence=divergence, temperature=temperature)
    return _lpo_optimizer


def get_synapse_lpo(
    divergence: str = "kl", temperature: float = 1.0,
) -> SynapseLPO:
    global _synapse_lpo
    if _synapse_lpo is None:
        _synapse_lpo = SynapseLPO(divergence=divergence, temperature=temperature)
    return _synapse_lpo


def get_provider_lpo(
    divergence: str = "kl", temperature: float = 0.5,
) -> ProviderLPO:
    global _provider_lpo
    if _provider_lpo is None:
        _provider_lpo = ProviderLPO(divergence=divergence, temperature=temperature)
    return _provider_lpo
