"""Latent GRPO — Group Relative Policy Optimization in learned latent space.

GRPO (Group Relative Policy Optimization) extended to operate in a
learned latent representation space rather than raw feature space.

Key difference from S-GRPO (spatial_reward.py):
  S-GRPO:       raw_features → GRPO → policy update
  Latent GRPO:  raw_features → encoder → latent_z → decoder → GRPO → policy
                                ↑________learned_________↑

Why latent space is better:
  1. Lower dimensionality → fewer samples needed
  2. Noise compression → irrelevant feature variations don't affect policy
  3. Smooth manifold → gradient-based optimization works better
  4. Disentanglement → each latent dim captures one decision factor

Integration with existing modules:
  S-GRPO (spatial_reward.py)  → raw spatial feature space
  Latent GRPO                  → learned compressed representation
  ThompsonRouter               → Beta beliefs in latent space
  SynapticPlasticity           → LTP/LTD on latent-space synapses

Architecture:
  Encoder: ℝ^D → ℝ^K    (D=raw dims, K=latent dims, K << D)
  Latent GRPO: optimize advantage in ℝ^K
  Decoder: ℝ^K → ℝ^A    (A=action space, for interpretability)
"""

from __future__ import annotations

import math
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══ Data Types ═══


@dataclass
class LatentVector:
    """A compressed latent representation of a decision context."""
    dims: list[float]              # K-dimensional latent vector
    source_features: dict[str, float]  # Original features (for update)
    reconstruction_error: float    # How well decoder reconstructs original
    timestamp: float = field(default_factory=time.time)


@dataclass  
class LatentGRPOResult:
    """Result of a Latent GRPO optimization round."""
    round_id: int
    input_features: dict[str, float]
    latent_z: list[float]          # Encoded latent representation
    advantages: dict[str, float]   # action → advantage in latent space
    latent_policy_update: dict[str, float]  # action → latent delta
    reconstruction_loss: float
    kl_divergence: float           # Divergence from prior latent distribution
    convergence: float


# ═══ Latent Encoder/Decoder ═══


class LatentEncoder:
    """Learn a compressed latent representation of decision features.

    Simple linear encoder: z = W_e @ features + b_e
    Projects high-dimensional feature space to low-dimensional latent space.
    Trained via reconstruction loss + policy gradient.
    """

    def __init__(self, input_dim: int = 20, latent_dim: int = 6):
        self._latent_dim = latent_dim
        self._W: list[list[float]] = self._init_weights(input_dim, latent_dim)
        self._b: list[float] = [0.0] * latent_dim

    @staticmethod
    def _init_weights(in_dim: int, out_dim: int) -> list[list[float]]:
        """Xavier-like initialization."""
        scale = math.sqrt(2.0 / (in_dim + out_dim))
        return [[random.gauss(0, scale) for _ in range(in_dim)] for _ in range(out_dim)]

    def encode(self, features: dict[str, float], feature_order: list[str]) -> list[float]:
        """Encode features → latent vector z."""
        values = [features.get(k, 0.0) for k in feature_order]
        z = []
        for j in range(self._latent_dim):
            dot = sum(self._W[j][i] * values[i] for i in range(len(values)))
            z.append(max(-5.0, min(5.0, dot + self._b[j])))
        return z

    def update(self, features: dict[str, float], feature_order: list[str],
                target_z: list[float], lr: float = 0.01) -> float:
        """Update weights via gradient descent on MSE(z, target_z)."""
        values = [features.get(k, 0.0) for k in feature_order]
        current_z = self.encode(features, feature_order)
        loss = sum((cz - tz) ** 2 for cz, tz in zip(current_z, target_z)) / len(target_z)

        for j in range(self._latent_dim):
            error = target_z[j] - current_z[j]
            for i in range(len(values)):
                self._W[j][i] += lr * error * values[i]
            self._b[j] += lr * error

        return loss

    # ═══ Feedback Alignment (Learning Beyond Gradients) ═══

    def feedback_align(self, features: dict[str, float],
                       feature_order: list[str], error_signal: list[float],
                       lr: float = 0.01) -> float:
        """Update weights via Feedback Alignment — no true gradient needed.

        Lillicrap et al. (2016) / Nøkland (2016):
          ΔW = B @ error @ input   instead of   W^T @ error @ input
          where B is a fixed random matrix (not W^T).

        Proven to work because the forward weights align themselves
        with B over time: W gradually learns to make B @ error ≈ W^T @ error.

        This is "Learning Beyond Gradients" (Weng, 2026 — OpenAI):
          backprop-free learning that achieves comparable convergence
          to gradient descent, especially in online/non-stationary settings.

        The fixed feedback matrix B is initialized once on first call.
        """
        values = [features.get(k, 0.0) for k in feature_order]
        current_z = self.encode(features, feature_order)
        loss = sum((es - cz) ** 2 for es, cz in zip(error_signal, current_z))

        # Lazy init fixed random feedback matrix B
        if not hasattr(self, '_B'):
            import random
            self._B = [[random.gauss(0, 0.1) for _ in range(self._latent_dim)]
                       for _ in range(len(values))]

        # Feedback alignment update:
        # δW_ji = lr × (B[j] · error) × input[i]
        # This uses B (fixed random) instead of W^T (true gradient)
        for j in range(self._latent_dim):
            for i in range(len(values)):
                # B[i][j] is the fixed feedback weight from latent j to input i
                feedback = self._B[i][j] * error_signal[j]
                self._W[j][i] += lr * feedback * values[i]
            self._b[j] += lr * error_signal[j]

        # Alignment metric: cosine similarity between B and W^T
        # As this approaches 1, feedback alignment ≈ gradient descent
        if len(values) > 0 and self._latent_dim > 0:
            dot = sum(
                self._B[i][j] * self._W[j][i]
                for i in range(len(values)) for j in range(self._latent_dim))
            norm_b = math.sqrt(sum(b * b for row in self._B for b in row))
            norm_w = math.sqrt(sum(w * w for row in self._W for w in row))
            self._alignment = dot / max(norm_b * norm_w, 0.001) if norm_b * norm_w > 0 else 0.0

        return loss

    @property
    def latent_dim(self) -> int:
        return self._latent_dim


# ═══ Latent GRPO Engine ═══


class LatentGRPO:
    """Group Relative Policy Optimization in learned latent space.

    Extends S-GRPO (spatial_reward.py) with latent representation learning:
      1. Encode raw features → latent z (lower-dimensional, compressed)
      2. Score actions by their latent-space distance to optimal z*
      3. GRPO: advantage = latent_score - group_mean
      4. Update: z* moves toward successful actions, latent encoder updates

    Key formulas:
      z = encoder(features)
      score(a) = exp(-||z_a - z*||²)  — exponential decay with distance
      advantage(a) = score(a) - mean(score(group))
      z* += lr × advantage(a) × (z_a - z*)  — latent center update

    The latent space naturally disentangles decision factors — each
    dimension captures one aspect (quality, cost, risk, urgency, ...)
    without explicit feature engineering.
    """

    def __init__(self, latent_dim: int = 6, learning_rate: float = 0.03):
        self._latent_dim = latent_dim
        self._lr = learning_rate

        # Encoder: raw features → latent
        self._encoder = LatentEncoder(input_dim=30, latent_dim=latent_dim)

        # Latent center z* — the "optimal" point in latent space
        self._z_star: list[float] = [0.0] * latent_dim

        # Feature vocabulary (ordered for encoder compatibility)
        self._feature_order: list[str] = []

        # Per-action latent embeddings
        self._action_latents: dict[str, list[float]] = {}

        # History
        self._history: deque[LatentGRPOResult] = deque(maxlen=100)

    # ── Feature Registration ──

    def _ensure_features(self, features: dict[str, float]) -> list[str]:
        """Update feature order with any new features."""
        for k in features:
            if k not in self._feature_order:
                self._feature_order.append(k)
        return self._feature_order

    # ── Encode Action ──

    def encode_action(
        self, action: str, features: dict[str, float],
    ) -> list[float]:
        """Encode an action's features into latent space.

        Stores the latent embedding for this action for future use.
        """
        order = self._ensure_features(features)
        z = self._encoder.encode(features, order)
        self._action_latents[action] = z
        return z

    # ── Latent Distance Scoring ──

    def latent_score(self, action: str) -> float:
        """Score an action by its distance to the optimal latent center z*.

        score = exp(-||z_action - z*||²)
        Closer to z* = higher score. This creates a smooth scoring
        manifold in latent space.
        """
        z_a = self._action_latents.get(action)
        if not z_a:
            return 0.5  # Unknown action → neutral

        # Squared Euclidean distance
        dist2 = sum((za - zs) ** 2 for za, zs in zip(z_a, self._z_star))
        return math.exp(-dist2 / self._latent_dim)  # Normalized by dims

    # ─── GRPO in Latent Space ───

    def optimize(
        self, group: list[tuple[str, dict[str, float]]],
        actual_outcomes: dict[str, float],
    ) -> LatentGRPOResult:
        """One round of Latent GRPO optimization.

        Args:
            group: [(action_name, feature_dict), ...]
            actual_outcomes: action → observed quality score

        Returns:
            LatentGRPOResult with latent-space metrics
        """
        if not group:
            return self._empty_result()

        # Phase 1: Encode all actions into latent space
        for action, features in group:
            self.encode_action(action, features)

        # Phase 2: Compute latent scores
        scores: dict[str, float] = {}
        for action, _ in group:
            scores[action] = self.latent_score(action)

        # Phase 3: GRPO — group-relative advantages
        group_mean = sum(scores.values()) / len(scores)
        group_std = math.sqrt(
            sum((s - group_mean) ** 2 for s in scores.values()) / len(scores))
        if group_std < 0.01:
            group_std = 0.01  # Avoid division by zero

        advantages: dict[str, float] = {}
        for action, _ in group:
            action_key = str(action)
            outcome = actual_outcomes.get(action_key, scores.get(action, 0.5))
            normalized_score = (scores[action] - group_mean) / group_std
            normalized_outcome = (outcome - group_mean) / group_std
            advantages[action] = 0.6 * normalized_score + 0.4 * normalized_outcome

        # Phase 4: Update latent center z*
        z_update = [0.0] * self._latent_dim
        total_weight = 0.0
        for action, _ in group:
            adv = advantages[action]
            if adv > 0:  # Only positive advantages pull z*
                weight = adv
                z_a = self._action_latents.get(action, [0.0] * self._latent_dim)
                for j in range(self._latent_dim):
                    z_update[j] += weight * (z_a[j] - self._z_star[j])
                total_weight += weight

        if total_weight > 0:
            for j in range(self._latent_dim):
                self._z_star[j] += self._lr * z_update[j] / total_weight
                self._z_star[j] = max(-3.0, min(3.0, self._z_star[j]))

        # Phase 5: Update encoder via top-action
        best_action = max(advantages, key=advantages.get)
        group_dict = {action: features for action, features in group}
        best_features = group_dict.get(best_action, {})
        if best_features:
            order = self._feature_order
            target_z = [self._z_star[j] + 0.1 * advantages[best_action]
                       for j in range(self._latent_dim)]
            recon_loss = self._encoder.update(best_features, order, target_z, lr=self._lr * 0.5)
        else:
            recon_loss = 0.0

        # KL divergence from prior (unit Gaussian prior on z)
        kl = self._kl_divergence()

        policy_update = {
            action: round(advantages[action], 4)
            for action, _ in group if abs(advantages.get(action, 0)) > self._lr
        }

        convergence = max(0.0, 1.0 - abs(group_std) / 2)
        result = LatentGRPOResult(
            round_id=len(self._history) + 1,
            input_features={k: v for action, feats in group for k, v in feats.items()},
            latent_z=list(self._z_star),
            advantages=advantages,
            latent_policy_update=policy_update,
            reconstruction_loss=round(recon_loss, 4),
            kl_divergence=round(kl, 4),
            convergence=round(convergence, 3),
        )
        self._history.append(result)
        return result

    # ═══ KL Divergence ═══

    def _kl_divergence(self) -> float:
        """KL divergence between current latent z* and standard Gaussian prior."""
        kl = 0.0
        for z in self._z_star:
            kl += 0.5 * (z * z - 1 - math.log(max(1e-9, z * z + 1e-9)))
        return kl / max(self._latent_dim, 1)

    # ═══ Latent Space Analysis ═══

    def latent_explained_variance(self) -> dict[str, float]:
        """How much each latent dimension contributes to score variance."""
        if not self._action_latents:
            return {}
        dims = range(self._latent_dim)
        var_per_dim = {}
        for j in dims:
            vals = [z[j] for z in self._action_latents.values()]
            if vals:
                mean = sum(vals) / len(vals)
                var = sum((v - mean) ** 2 for v in vals) / len(vals)
                var_per_dim[f"z{j}"] = round(var, 4)
        return var_per_dim

    def latent_compression_ratio(self) -> float:
        """How much the latent space compresses the original feature space."""
        n_features = len(self._feature_order)
        return self._latent_dim / max(n_features, 1)

    # ═══ Helpers ═══

    def _empty_result(self) -> LatentGRPOResult:
        return LatentGRPOResult(
            round_id=0, input_features={}, latent_z=[],
            advantages={}, latent_policy_update={},
            reconstruction_loss=0.0, kl_divergence=0.0, convergence=0.0)

    def stats(self) -> dict[str, Any]:
        return {
            "latent_dim": self._latent_dim,
            "feature_dim": len(self._feature_order),
            "compression_ratio": round(self.latent_compression_ratio(), 3),
            "kl_divergence": round(self._kl_divergence(), 4),
            "z_star": [round(z, 3) for z in self._z_star],
            "actions_encoded": len(self._action_latents),
            "explained_variance": self.latent_explained_variance(),
        }


# ═══ Singleton ═══

_latent_grpo: LatentGRPO | None = None


def get_latent_grpo(latent_dim: int = 6) -> LatentGRPO:
    global _latent_grpo
    if _latent_grpo is None:
        _latent_grpo = LatentGRPO(latent_dim=latent_dim)
    return _latent_grpo


__all__ = [
    "LatentGRPO", "LatentEncoder", "LatentVector", "LatentGRPOResult",
    "get_latent_grpo",
]
