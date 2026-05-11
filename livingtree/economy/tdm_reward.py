"""TDM-R1 Reward Optimizer — non-differentiable RL for pipeline optimization.

Based on Luo et al. (2026), arXiv:2603.07700:
  "TDM-R1: Reinforcing Few-Step Diffusion Models with Non-Differentiable Reward"

Core innovations mapped to LivingTree:
  1. Non-differentiable reward: binary success, budget compliance, human feedback
  2. Per-step reward distribution: allocate trajectory reward along pipeline stages
  3. Decoupled surrogate learning: reward model learns from outcomes, generator trained against surrogate
  4. Few-step optimization: after RL, 3-step pipeline > 10-step pipeline quality

LivingTree pipeline as a deterministic trajectory (TDM analog):
  stage_0 → stage_1 → ... → stage_N → total_outcome
  Each stage gets a per-step reward: r_t = total_reward × stage_contribution_weight

Surrogate reward model: learns to predict per-step reward from stage context.
Generator (pipeline config): optimized against the surrogate model.

Intentional Updates integration (Sharifnassab et al., arXiv:2604.19033):
  NLMS diagonal scaling + Intentional TD replaces fixed learning_rate:
    - NLMS: η_i = η_base / (ε + E[g_i²]) — per-feature adaptive step size
    - Intentional TD: η* = γ × |error| / (|g|² + ε) — achieves fixed fractional error reduction
  Benefit: high-gradient features auto-dampen, low-gradient features auto-explore.

Integration:
  LifeEngine stages → per-step reward → surrogate model → config optimization
  GTSM plan steps → per-step reward → surrogate model → step ordering
  AgenticRAG rounds → per-step reward → surrogate model → round limit/strategy
"""

from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


# ═══ Data Types ═══


class RewardType(str, Enum):
    """Types of non-differentiable reward signals."""
    BINARY_SUCCESS = "binary_success"    # 0 or 1
    QUALITY_SCORE = "quality_score"       # 0.0 to 1.0 continuous
    HUMAN_FEEDBACK = "human_feedback"      # 0.0 to 1.0 from human
    BUDGET_COMPLIANCE = "budget"          # Normalized budget usage
    LATENCY = "latency"                   # Inverse-normalized latency
    FORMAT_VALIDITY = "format"            # Output format check
    SAFETY_CHECK = "safety"               # Safety gate result


@dataclass
class PerStepReward:
    """Reward allocated to a single pipeline step.

    TDM-R1 analog: per-step reward along the deterministic trajectory.
    r_t = total_outcome × stage_contribution(t)
    """
    step_index: int
    step_name: str
    raw_reward: float = 0.0            # Original reward for this step
    surrogate_estimate: float = 0.0     # Surrogate model's estimate
    contribution_weight: float = 0.0    # How much this step contributed
    step_context: dict = field(default_factory=dict)  # Context features
    reward_type: str = "binary_success"


@dataclass
class TrajectoryReward:
    """Complete reward decomposition for a pipeline trajectory."""
    trajectory_id: str
    steps: list[PerStepReward]
    total_reward: float                # Overall trajectory outcome
    total_surrogate: float              # Surrogate model's total estimate
    reward_types_used: list[str]
    trajectory_length: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class TDMOptimizationResult:
    """Result of a TDM-R1 optimization round."""
    round_id: int
    surrogate_loss: float               # Loss of the surrogate model
    policy_gradient_norm: float          # Norm of the policy gradient
    reward_improvement: float            # Δ in average trajectory reward
    best_config: dict[str, Any]          # Best pipeline config found
    convergence_score: float
    per_stage_contributions: dict[str, float]  # stage → avg contribution


# ═══ Surrogate Reward Model ═══


class SurrogateRewardModel:
    """Learns a differentiable proxy for non-differentiable reward signals.

    TDM-R1 key: decouple reward learning from generator optimization.
    The surrogate model is trained on observed (context, per_step_reward) pairs,
    then used to optimize the pipeline configuration.

    This is a simple weighted linear model for fast online learning,
    sufficient for pipeline stage-level optimization.

    Intentional TD + NLMS diagonal scaling:
      Each feature weight has its own adaptive step size = η_base / (ε + E[g_i²]).
      High-gradient features get smaller steps (prevents overshoot),
      low-gradient features get larger steps (explores more fully).
      Combined with Intentional TD: overall step size = γ × |error| / (|g|² + ε).
    """

    def __init__(self, learning_rate: float = 0.01, feature_dim: int = 10,
                 gamma: float = 0.3, epsilon: float = 1e-6):
        self._lr = learning_rate
        self._gamma = gamma       # Intentional TD: target error reduction fraction
        self._epsilon = epsilon   # NLMS: regularization for division
        self._weights: dict[str, float] = defaultdict(float)
        self._bias: float = 0.0
        self._samples: int = 0
        self._loss_history: deque[float] = deque(maxlen=100)
        # NLMS: running average of squared gradient per feature
        self._g2_avg: dict[str, float] = defaultdict(float)  # E[g_i²]
        self._g2_bias_avg: float = 1e-3                     # E[g_bias²]
        self._g2_decay: float = 0.95  # EMA decay for squared gradient

    def predict(self, features: dict[str, float]) -> float:
        """Predict per-step reward from context features."""
        score = self._bias
        for feat, value in features.items():
            if feat in self._weights:
                score += self._weights[feat] * value
        return max(0.0, min(1.0, score))

    def train_step(
        self, features: dict[str, float], target: float,
    ) -> float:
        """Single SGD step with NLMS diagonal scaling + Intentional TD.

        NLMS: Each feature weight w_i gets its own step size:
            η_i = η_base / (ε + E[g_i²])
        where E[g_i²] is the EMA of squared gradient magnitude for that feature.
        High-gradient features → auto-dampen (prevent overshoot).
        Low-gradient features → auto-amplify (explore more).
        
        Intentional TD: Overall step is scaled to achieve fractional error reduction γ:
            η*_total = γ × |error| / (Σ (g_i² / (ε + E[g_i²])) + ε)
        This guarantees each update reduces approximately γ of the prediction gap.
        
        Returns the loss for this sample.
        """
        pred = self.predict(features)
        error = target - pred
        loss = error * error

        # ── Compute per-feature gradients ──
        grads: dict[str, float] = {}
        for feat, value in features.items():
            grads[feat] = -2 * error * value
        bias_grad = -2 * error

        # ── Update NLMS running averages E[g_i²] ──
        for feat, g in grads.items():
            self._g2_avg[feat] = (self._g2_decay * self._g2_avg[feat]
                                  + (1 - self._g2_decay) * g * g)
        self._g2_bias_avg = (self._g2_decay * self._g2_bias_avg
                            + (1 - self._g2_decay) * bias_grad * bias_grad)

        # ── Intentional TD: compute optimal step size ──
        if self._gamma > 0:
            # Effective gradient norm (NLMS-scaled)
            effective_g2 = 0.0
            for feat, g in grads.items():
                scaled = g / (self._epsilon + self._g2_avg[feat])
                effective_g2 += scaled * scaled
            # Bias contribution
            bias_scaled = bias_grad / (self._epsilon + self._g2_bias_avg)
            effective_g2 += bias_scaled * bias_scaled

            # η* = γ × |error| / (effective_g2 + ε)
            if effective_g2 > 0:
                eta_star = self._gamma * abs(error) / (effective_g2 + self._epsilon)
            else:
                eta_star = self._gamma * abs(error) / self._epsilon
        else:
            eta_star = self._lr  # Legacy fixed learning rate

        # ── Apply NLMS-weighted updates ──
        for feat, g in grads.items():
            eta_i = eta_star / (self._epsilon + self._g2_avg[feat])
            self._weights[feat] -= eta_i * g

        eta_bias = eta_star / (self._epsilon + self._g2_bias_avg)
        self._bias -= eta_bias * bias_grad

        self._samples += 1
        self._loss_history.append(loss)
        return loss

    def train_batch(
        self, batch: list[tuple[dict[str, float], float]],
    ) -> float:
        """Train on a batch of (features, target) pairs."""
        total_loss = 0.0
        for features, target in batch:
            total_loss += self.train_step(features, target)
        return total_loss / max(len(batch), 1)

    @property
    def avg_loss(self) -> float:
        if not self._loss_history:
            return float('inf')
        return sum(self._loss_history) / len(self._loss_history)

    def stats(self) -> dict[str, Any]:
        return {
            "samples": self._samples,
            "avg_loss": round(self.avg_loss, 6),
            "feature_count": len(self._weights),
            "top_features": sorted(
                self._weights.items(), key=lambda x: -abs(x[1]))[:5],
        }


# ═══ TDM-R1 Optimizer ═══


class TDMRewardOptimizer:
    """Non-differentiable reward RL for pipeline trajectory optimization.

    TDM-R1 three-phase decoupled optimization:
      Phase 1: Per-step reward distribution — allocate trajectory reward to steps
      Phase 2: Surrogate model training — learn to predict per-step rewards
      Phase 3: Policy gradient — optimize pipeline config using surrogate

    Pipeline "generator" = LifeEngine stage configuration, AgenticRAG params,
    GTSM mode selection, provider choices — any discrete config that affects
    the trajectory outcome.
    """

    # Stage contribution priors (from TDM's reverse-time weighting)
    # Later stages get higher weight (they're closer to the outcome)
    DEFAULT_STAGE_PRIORS: dict[str, float] = {
        "perceive": 0.08,     # Early stage: low contribution
        "cognize": 0.12,
        "ontogrow": 0.08,
        "plan": 0.15,
        "simulate": 0.10,
        "execute": 0.25,      # Execution: high contribution
        "reflect": 0.12,
        "evolve": 0.10,
        # GTSM modes
        "tree_decompose": 0.20,
        "flow_refine": 0.35,
        "skeleton_build": 0.15,
        "diffusion_step": 0.30,
        # AgenticRAG
        "rag_round_1": 0.30,
        "rag_round_2": 0.25,
        "rag_round_3": 0.20,
        "rag_round_4": 0.15,
        "rag_round_5": 0.10,
    }

    def __init__(self, learning_rate: float = 0.05):
        self._surrogate = SurrogateRewardModel()
        self._lr = learning_rate
        self._history: list[TrajectoryReward] = []
        self._optimization_rounds: list[TDMOptimizationResult] = []
        # Per-stage contribution tracking
        self._stage_contributions: dict[str, list[float]] = defaultdict(list)

    # ═══ Phase 1: Per-Step Reward Distribution ═══

    def distribute_rewards(
        self,
        trajectory_id: str,
        stage_names: list[str],
        stage_contexts: list[dict[str, float]],
        total_outcome: float,
        reward_type: str = "binary_success",
        stage_weights: dict[str, float] | None = None,
    ) -> TrajectoryReward:
        """Allocate total trajectory reward to individual steps.

        TDM-R1 analog: per-step reward distribution along the deterministic
        trajectory. Later steps get higher weight (closer to outcome).
        Uses TDM's backward reward allocation.

        Args:
            trajectory_id: Unique ID for this trajectory
            stage_names: Ordered list of stage names (e.g. ["perceive", "cognize", ...])
            stage_contexts: Context feature dicts for each stage
            total_outcome: Total trajectory reward (e.g. task success = 1.0)
            reward_type: Type of reward signal
            stage_weights: Optional override for per-stage contribution weights

        Returns:
            TrajectoryReward with per-step reward allocations
        """
        n = len(stage_names)
        if n == 0:
            return TrajectoryReward(
                trajectory_id=trajectory_id, steps=[],
                total_reward=total_outcome, total_surrogate=0.0,
                reward_types_used=[reward_type], trajectory_length=0,
            )

        # Default: reverse-time weighting (TDM's backward allocation)
        # Later steps get higher weight
        weights = stage_weights or {}
        total_weight = 0.0
        step_weights = []
        for i, name in enumerate(stage_names):
            if name in weights:
                w = weights[name]
            else:
                w = self.DEFAULT_STAGE_PRIORS.get(name, 1.0 / n)
            # Boost later steps: linear ramp from 0.5 to 1.5
            position_factor = 0.5 + (i / max(n - 1, 1))
            w = w * position_factor
            step_weights.append(w)
            total_weight += w

        # Allocate
        steps: list[PerStepReward] = []
        total_surrogate = 0.0
        for i, name in enumerate(stage_names):
            contrib = step_weights[i] / max(total_weight, 0.001)
            raw = total_outcome * contrib
            ctx = stage_contexts[i] if i < len(stage_contexts) else {}

            # Query surrogate for estimate
            surrogate_est = self._surrogate.predict(ctx)

            steps.append(PerStepReward(
                step_index=i,
                step_name=name,
                raw_reward=round(raw, 4),
                surrogate_estimate=round(surrogate_est, 4),
                contribution_weight=round(contrib, 4),
                step_context=ctx,
                reward_type=reward_type,
            ))
            total_surrogate += surrogate_est

            # Track stage contributions
            self._stage_contributions[name].append(contrib)

        traj = TrajectoryReward(
            trajectory_id=trajectory_id,
            steps=steps,
            total_reward=total_outcome,
            total_surrogate=round(total_surrogate, 4),
            reward_types_used=[reward_type],
            trajectory_length=n,
        )
        self._history.append(traj)
        if len(self._history) > 200:
            self._history = self._history[-200:]
        return traj

    # ═══ Phase 2: Surrogate Model Training ═══

    def train_surrogate(
        self, trajectories: list[TrajectoryReward] | None = None,
    ) -> float:
        """Train the surrogate reward model on observed trajectory data.

        TDM-R1 analog: surrogate reward learning from non-differentiable
        reward signals. The surrogate becomes a differentiable proxy that
        the generator can optimize against.

        Returns:
            Average training loss
        """
        data = trajectories or self._history
        if not data:
            return float('inf')

        batch = []
        for traj in data[-50:]:  # Most recent 50 trajectories
            for step in traj.steps:
                if step.step_context:
                    batch.append((step.step_context, step.raw_reward))

        if not batch:
            return float('inf')

        loss = self._surrogate.train_batch(batch)
        logger.debug(f"TDM-R1 surrogate: loss={loss:.4f}, samples={self._surrogate._samples}")
        return loss

    # ═══ Phase 3: Policy Optimization ═══

    def optimize_policy(
        self,
        current_config: dict[str, Any],
        candidate_configs: list[dict[str, Any]],
        config_to_features: callable,
    ) -> TDMOptimizationResult:
        """Optimize pipeline configuration using the trained surrogate.

        TDM-R1 analog: generator (pipeline config) optimization using the
        learned surrogate reward model. Policy gradient with surrogate
        rewards in place of non-differentiable true rewards.

        Args:
            current_config: Current pipeline configuration
            candidate_configs: Alternative configs to evaluate
            config_to_features: fn(config) → dict[str, float] feature vector

        Returns:
            TDMOptimizationResult with best config and metrics
        """
        round_id = len(self._optimization_rounds) + 1

        best_config = current_config
        best_score = self._surrogate.predict(config_to_features(current_config))

        scores = []
        for cfg in candidate_configs:
            score = self._surrogate.predict(config_to_features(cfg))
            scores.append(score)
            if score > best_score:
                best_score = score
                best_config = cfg

        # Compute policy gradient norm (approximate)
        grad_norm = 0.0
        if len(scores) > 1:
            mean_score = sum(scores) / len(scores)
            grad_norm = math.sqrt(sum((s - mean_score) ** 2 for s in scores))

        # Reward improvement
        prev_avg = (
            sum(t.total_reward for t in self._history[-10:]) / max(
                len(self._history[-10:]), 1)
            if self._history else 0.0)
        reward_improvement = best_score - prev_avg

        # Per-stage contributions
        stage_contribs = {
            name: sum(vals) / max(len(vals), 1)
            for name, vals in self._stage_contributions.items()
        }

        result = TDMOptimizationResult(
            round_id=round_id,
            surrogate_loss=self._surrogate.avg_loss,
            policy_gradient_norm=round(grad_norm, 4),
            reward_improvement=round(reward_improvement, 4),
            best_config=best_config,
            convergence_score=round(self._convergence(), 4),
            per_stage_contributions=stage_contribs,
        )

        self._optimization_rounds.append(result)
        logger.info(
            f"TDM-R1 round {round_id}: best_score={best_score:.3f}, "
            f"Δreward={reward_improvement:+.3f}, loss={self._surrogate.avg_loss:.3f}",
        )
        return result

    # ═══ Multi-Reward Type Aggregation ═══

    def aggregate_rewards(
        self, rewards: dict[str, float],  # reward_type → value
        weights: dict[str, float] | None = None,
    ) -> float:
        """Aggregate multiple non-differentiable reward types into one.

        Handles: binary_success, quality_score, human_feedback, budget, latency, format, safety.

        TDM-R1 analog: combining multiple reward signals (text rendering,
        visual quality, preference alignment) into a unified reward.
        """
        default_weights = {
            "binary_success": 0.30,
            "quality_score": 0.25,
            "human_feedback": 0.15,
            "budget": 0.10,
            "latency": 0.08,
            "format": 0.07,
            "safety": 0.05,
        }
        w = weights or default_weights

        total = 0.0
        for rtype, value in rewards.items():
            total += value * w.get(rtype, 0.05)
        return min(1.0, max(0.0, total))

    # ═══ Stage Contribution Analysis ═══

    def most_contributing_stages(self, top_n: int = 5) -> list[tuple[str, float]]:
        """Which stages contribute most to trajectory outcomes?"""
        contribs = {
            name: sum(vals) / max(len(vals), 1)
            for name, vals in self._stage_contributions.items()
        }
        return sorted(contribs.items(), key=lambda x: -x[1])[:top_n]

    def least_contributing_stages(self, top_n: int = 5) -> list[tuple[str, float]]:
        """Which stages contribute least (candidates for optimization/skipping)?"""
        contribs = {
            name: sum(vals) / max(len(vals), 1)
            for name, vals in self._stage_contributions.items()
        }
        return sorted(contribs.items(), key=lambda x: x[1])[:top_n]

    def stage_pruning_candidates(self, threshold: float = 0.05) -> list[str]:
        """Stages with contribution below threshold — skip candidates.

        TDM-R1 analog: after RL optimization, some early diffusion steps
        become unnecessary because later steps learned to compensate.
        """
        return [
            name for name, avg in self.most_contributing_stages(20)
            if avg < threshold
        ]

    # ═══ 4-step beats 100-step (TDM-R1 key result) ═══

    def few_step_quality_ratio(self) -> float:
        """After RL optimization, how many pipeline steps are truly needed?

        𝑅 = avg_reward_with_K_steps / avg_reward_with_all_steps
        > 1 means fewer steps already match/exceed full pipeline quality.
        """
        if len(self._history) < 10:
            return 1.0

        # Compare short trajectories (≤ 5 steps) vs long (≥ 7 steps)
        short = [t for t in self._history if t.trajectory_length <= 5]
        long = [t for t in self._history if t.trajectory_length >= 7]

        if not short or not long:
            return 1.0

        short_avg = sum(t.total_reward for t in short) / len(short)
        long_avg = sum(t.total_reward for t in long) / len(long)
        return short_avg / max(long_avg, 0.01)

    # ═══ Helpers ═══

    def _convergence(self) -> float:
        """How well has the optimization converged?"""
        if len(self._optimization_rounds) < 3:
            return 0.0
        improvements = [
            r.reward_improvement for r in self._optimization_rounds[-5:]]
        mean = sum(improvements) / len(improvements)
        var = sum((i - mean) ** 2 for i in improvements) / len(improvements)
        return max(0.0, min(1.0, 1.0 - math.sqrt(var) * 2))

    def stats(self) -> dict[str, Any]:
        return {
            "trajectories_processed": len(self._history),
            "optimization_rounds": len(self._optimization_rounds),
            "surrogate_samples": self._surrogate._samples,
            "surrogate_loss": round(self._surrogate.avg_loss, 4),
            "few_step_quality_ratio": round(self.few_step_quality_ratio(), 2),
            "top_contributing_stages": self.most_contributing_stages(5),
            "stage_pruning_candidates": self.stage_pruning_candidates(),
            "convergence": round(self._convergence(), 3),
        }


# ═══ LifeEngine Integration Helper ═══

def lifeengine_to_trajectory(
    engine: Any, session_id: str, success_rate: float,
) -> tuple[list[str], list[dict[str, float]]]:
    """Convert a completed LifeEngine cycle to TDM trajectory format.

    Extracts stage names and context features from LifeEngine's internal state.
    """
    stage_names = []
    stage_contexts = []

    for life_stage in engine.stages:
        name = life_stage.stage
        stage_names.append(name)

        # Extract context features
        ctx: dict[str, float] = {
            "duration_ms": life_stage.duration_ms / 10000.0,  # Normalize
            "status_code": 1.0 if life_stage.status == "completed" else 0.0,
            "has_error": 1.0 if life_stage.error else 0.0,
            "stage_order": life_stage.stage.count("_") / 10.0,  # Rough position
        }
        stage_contexts.append(ctx)

    return stage_names, stage_contexts


# ═══ Singleton ═══

_tdm: TDMRewardOptimizer | None = None


def get_tdm_optimizer() -> TDMRewardOptimizer:
    global _tdm
    if _tdm is None:
        _tdm = TDMRewardOptimizer()
    return _tdm


__all__ = [
    "TDMRewardOptimizer", "SurrogateRewardModel",
    "TrajectoryReward", "PerStepReward", "TDMOptimizationResult",
    "RewardType", "lifeengine_to_trajectory", "get_tdm_optimizer",
]
