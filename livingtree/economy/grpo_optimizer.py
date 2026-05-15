"""GRPO Optimizer — Group Relative Policy Optimization (3-in-1 merged module).

Merges three GRPO variants into a single composite optimizer:
  - LatentGRPO: GRPO in learned latent representation space
  - SpatialGRPO (S-GRPO): Spatial-aware reward attribution for routing
  - TDM-R1: Non-differentiable reward RL for pipeline optimization

Papers referenced:
  - Ni et al. (ACL 2026), arXiv:2601.03248 — STReasoner / S-GRPO
  - Luo et al. (2026), arXiv:2603.07700 — TDM-R1
  - Sharifnassab et al., arXiv:2604.19033 — NLMS diagonal scaling
  - OpenAI (2026) — Heuristic Learning / Feedback Alignment
  - v2.6 LPO, arXiv:2605.06139 — Latent Policy Optimization
"""

from __future__ import annotations

import math
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


# ═══════════════════════════════════════════════════════════════════
# Shared Utilities
# ═══════════════════════════════════════════════════════════════════


def _apply_nlms(gradient: list[float], g2_ema: list[float],
                lr: float, eps: float, g2_decay: float) -> list[float]:
    """NLMS diagonal scaling: update squared gradient EMA, return per-dim step sizes.

    For each dimension j:
        1. g2_ema[j] = g2_decay * g2_ema[j] + (1 - g2_decay) * gradient[j]^2
        2. eta_j = lr / (eps + g2_ema[j])

    High-variance dimensions auto-dampen; low-variance dimensions auto-amplify.
    Based on Sharifnassab et al. (arXiv:2604.19033).
    """
    for j in range(len(gradient)):
        gj = gradient[j]
        g2_ema[j] = (g2_decay * g2_ema[j] + (1 - g2_decay) * gj * gj)
    return [lr / (eps + g2_ema[j]) for j in range(len(gradient))]


def _compute_convergence(values: list[float], multiplier: float = 1.0,
                         min_count: int = 10) -> float:
    """Convergence score: 1.0 - sqrt(variance) * multiplier over recent history.

    Returns 0.0..1.0 where 1.0 = fully converged (low variance).
    """
    if len(values) < min_count:
        return 0.0
    recent = values[-min_count:]
    mean = sum(recent) / len(recent)
    var = sum((v - mean) ** 2 for v in recent) / len(recent)
    return max(0.0, min(1.0, 1.0 - math.sqrt(var) * multiplier))


# ═══════════════════════════════════════════════════════════════════
# Section 1: LatentGRPO Variant
# — GRPO in learned latent representation space
# ═══════════════════════════════════════════════════════════════════


@dataclass
class LatentVector:
    """A compressed latent representation of a decision context."""
    dims: list[float]
    source_features: dict[str, float]
    reconstruction_error: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class LatentGRPOResult:
    """Result of a Latent GRPO optimization round."""
    round_id: int
    input_features: dict[str, float]
    latent_z: list[float]
    advantages: dict[str, float]
    latent_policy_update: dict[str, float]
    reconstruction_loss: float
    kl_divergence: float
    convergence: float


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
        self._fb: list[list[float]] | None = None
        self._alignment: float = 0.0

    @staticmethod
    def _init_weights(in_dim: int, out_dim: int) -> list[list[float]]:
        scale = math.sqrt(2.0 / (in_dim + out_dim))
        return [[random.gauss(0, scale) for _ in range(in_dim)] for _ in range(out_dim)]

    def encode(self, features: dict[str, float], feature_order: list[str]) -> list[float]:
        values = [features.get(k, 0.0) for k in feature_order]
        z = []
        for j in range(self._latent_dim):
            dot = sum(self._W[j][i] * values[i] for i in range(len(values)))
            z.append(max(-5.0, min(5.0, dot + self._b[j])))
        return z

    def update(self, features: dict[str, float], feature_order: list[str],
               target_z: list[float], lr: float = 0.01) -> float:
        values = [features.get(k, 0.0) for k in feature_order]
        current_z = self.encode(features, feature_order)
        loss = sum((cz - tz) ** 2 for cz, tz in zip(current_z, target_z)) / len(target_z)
        for j in range(self._latent_dim):
            error = target_z[j] - current_z[j]
            for i in range(len(values)):
                self._W[j][i] += lr * error * values[i]
            self._b[j] += lr * error
        return loss

    def feedback_align(self, features: dict[str, float],
                       feature_order: list[str], error_signal: list[float],
                       lr: float = 0.01) -> float:
        """Update weights via Feedback Alignment — no true gradient needed."""
        values = [features.get(k, 0.0) for k in feature_order]
        current_z = self.encode(features, feature_order)
        loss = sum((es - cz) ** 2 for es, cz in zip(error_signal, current_z))
        if self._fb is None:
            self._fb = [[random.gauss(0, 0.1) for _ in range(self._latent_dim)]
                        for _ in range(len(values))]
        for j in range(self._latent_dim):
            for i in range(len(values)):
                feedback = self._fb[i][j] * error_signal[j]
                self._W[j][i] += lr * feedback * values[i]
            self._b[j] += lr * error_signal[j]
        if len(values) > 0 and self._latent_dim > 0:
            dot = sum(
                self._fb[i][j] * self._W[j][i]
                for i in range(len(values)) for j in range(self._latent_dim))
            norm_b = math.sqrt(sum(b * b for row in self._fb for b in row))
            norm_w = math.sqrt(sum(w * w for row in self._W for w in row))
            self._alignment = dot / max(norm_b * norm_w, 0.001) if norm_b * norm_w > 0 else 0.0
        return loss

    @property
    def latent_dim(self) -> int:
        return self._latent_dim


class LatentGRPO:
    """Group Relative Policy Optimization in learned latent space.

    Extends S-GRPO with latent representation learning:
      1. Encode raw features → latent z (lower-dimensional, compressed)
      2. Score actions by their latent-space distance to optimal z*
      3. GRPO: advantage = latent_score - group_mean
      4. Update: z* moves toward successful actions, latent encoder updates

    Key formulas:
      z = encoder(features)
      score(a) = exp(-||z_a - z*||^2)
      advantage(a) = score(a) - mean(score(group))
      z* += lr * advantage(a) * (z_a - z*)
    """

    def __init__(self, latent_dim: int = 6, learning_rate: float = 0.03,
                 gamma: float = 0.3, epsilon: float = 1e-6):
        self._latent_dim = latent_dim
        self._lr = learning_rate
        self._gamma = gamma
        self._epsilon = epsilon

        self._encoder = LatentEncoder(input_dim=30, latent_dim=latent_dim)

        self._z_star: list[float] = [0.0] * latent_dim

        self._g2_dim: list[float] = [1e-3] * latent_dim
        self._g2_decay: float = 0.95

        self._feature_order: list[str] = []

        self._action_latents: dict[str, list[float]] = {}

        self._history: deque[LatentGRPOResult] = deque(maxlen=100)

        self._feedback_matrix: list[list[float]] = [
            [random.gauss(0, 1.0 / math.sqrt(latent_dim)) for _ in range(latent_dim)]
            for _ in range(latent_dim)
        ]

    def _ensure_features(self, features: dict[str, float]) -> list[str]:
        for k in features:
            if k not in self._feature_order:
                self._feature_order.append(k)
        return self._feature_order

    def encode_action(
        self, action: str, features: dict[str, float],
    ) -> list[float]:
        order = self._ensure_features(features)
        z = self._encoder.encode(features, order)
        self._action_latents[action] = z
        return z

    def latent_score(self, action: str) -> float:
        z_a = self._action_latents.get(action)
        if not z_a:
            return 0.5
        dist2 = sum((za - zs) ** 2 for za, zs in zip(z_a, self._z_star))
        return math.exp(-dist2 / self._latent_dim)

    def optimize(
        self, group: list[tuple[str, dict[str, float]]],
        actual_outcomes: dict[str, float],
    ) -> LatentGRPOResult:
        if not group:
            return self._empty_result()

        for action, features in group:
            self.encode_action(action, features)

        scores: dict[str, float] = {}
        for action, _ in group:
            scores[action] = self.latent_score(action)

        group_mean = sum(scores.values()) / len(scores)
        group_std = math.sqrt(
            sum((s - group_mean) ** 2 for s in scores.values()) / len(scores))
        if group_std < 0.01:
            group_std = 0.01

        advantages: dict[str, float] = {}
        for action, _ in group:
            action_key = str(action)
            outcome = actual_outcomes.get(action_key)
            if outcome is None:
                outcome = scores.get(action, group_mean)  # Use group mean as neutral fallback
            normalized_score = (scores[action] - group_mean) / group_std
            normalized_outcome = (outcome - group_mean) / group_std
            advantages[action] = 0.6 * normalized_score + 0.4 * normalized_outcome

        z_update = [0.0] * self._latent_dim
        total_weight = 0.0
        for action, _ in group:
            adv = advantages[action]
            if adv > 0:
                weight = adv
                z_a = self._action_latents.get(action, [0.0] * self._latent_dim)
                for j in range(self._latent_dim):
                    z_update[j] += weight * (z_a[j] - self._z_star[j])
                total_weight += weight

        if total_weight > 0:
            for j in range(self._latent_dim):
                z_update[j] /= total_weight

            # NLMS: update per-dimension squared gradient EMA (shared utility)
            _apply_nlms(z_update, self._g2_dim, self._lr, self._epsilon, self._g2_decay)

            # Intentional TD: compute effective step size
            if self._gamma > 0:
                effective_g2 = sum(
                    (z_update[j] / (self._epsilon + self._g2_dim[j])) ** 2
                    for j in range(self._latent_dim))
                eta_star = self._gamma / (effective_g2 + self._epsilon) if effective_g2 > 0 else self._lr
            else:
                eta_star = self._lr

            for j in range(self._latent_dim):
                eta_j = eta_star / (self._epsilon + self._g2_dim[j])
                self._z_star[j] += eta_j * z_update[j]
                self._z_star[j] = max(-3.0, min(3.0, self._z_star[j]))

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

    def _kl_divergence(self, divergence_type: str = "forward") -> float:
        kl = 0.0
        for z in self._z_star:
            mu_prior = 0.0
            sigma_prior = 1.0
            z2 = z * z
            if divergence_type == "forward":
                kl += 0.5 * (z2 - 1 - math.log(max(1e-9, z2 + 1e-9)))
            elif divergence_type == "reverse":
                kl += 0.5 * (-z2 - 1 + math.log(max(1e-9, z2 + 1e-9)))
            elif divergence_type == "jsd":
                m = 0.5 * z2 + 0.5
                kl_fwd = 0.5 * (-math.log(max(1e-9, z2 + 1e-9)) - 1 + z2) if z2 > 1e-9 else 0
                kl_rev = 0.5 * (z2 - 1 - math.log(max(1e-9, z2 + 1e-9)))
                kl += 0.5 * (kl_fwd + kl_rev)
            elif divergence_type == "squared_hellinger":
                kl += 0.5 * (math.sqrt(z2) - 1) ** 2 / max(z2 + 1, 1)
            elif divergence_type == "chi_squared":
                kl += (z2 - 1) ** 2 / max(z2 + 1, 1)
        return kl / max(self._latent_dim, 1)

    def optimize_lpo(
        self, group: list[tuple[Any, dict[str, float]]],
        actual_outcomes: dict[str, float] | None = None,
        divergence: str = "kl",
    ) -> LatentGRPOResult:
        """v2.6 LPO (arXiv:2605.06139): Optimize latent policy via explicit target-projection."""
        if not group:
            return self._empty_result()
        from livingtree.optimization.lpo_optimizer import LPOOptimizer

        lpo = LPOOptimizer(divergence=divergence, temperature=1.0)
        for action, features in group:
            self.encode_action(action, features)
        rewards: dict[str, float] = {}
        for action, _ in group:
            rewards[action] = self.latent_score(action)
        target = lpo.construct_target(rewards)
        projected = lpo.project(rewards, target)
        z_update = [0.0] * self._latent_dim
        total_weight = 0.0
        for action, _ in group:
            delta = projected.get(action, 0.0) - rewards.get(action, 0.0)
            if delta > 0:
                weight = delta
                z_a = self._action_latents.get(action, [0.0] * self._latent_dim)
                for j in range(self._latent_dim):
                    z_update[j] += weight * (z_a[j] - self._z_star[j])
                total_weight += weight
        if total_weight > 0:
            for j in range(self._latent_dim):
                z_update[j] /= total_weight
            for j in range(self._latent_dim):
                self._z_star[j] += self._lr * z_update[j]
                self._z_star[j] = max(-3.0, min(3.0, self._z_star[j]))
        advantages = {action: projected.get(action, rewards.get(action, 0.0))
                      for action, _ in group}
        kl = self._kl_divergence("forward")
        result = LatentGRPOResult(
            round_id=len(self._history) + 1,
            input_features={k: v for action, feats in group for k, v in feats.items()},
            latent_z=list(self._z_star),
            advantages=advantages,
            latent_policy_update={a: round(v, 4) for a, v in advantages.items()},
            reconstruction_loss=0.0,
            kl_divergence=round(kl, 4),
            convergence=round(lpo.is_monotonic(), 3),
        )
        self._history.append(result)
        return result

    def latent_explained_variance(self) -> dict[str, float]:
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
        n_features = len(self._feature_order)
        return self._latent_dim / max(n_features, 1)

    def heuristic_gradient_approximation(self, error_signal: list[float]) -> list[float]:
        """Compute policy gradients using feedback alignment (no backprop)."""
        if len(error_signal) != self._latent_dim:
            error_signal = error_signal[:self._latent_dim]
            while len(error_signal) < self._latent_dim:
                error_signal.append(0.0)

        grad = [0.0] * self._latent_dim
        for i in range(self._latent_dim):
            row = self._feedback_matrix[i]
            grad[i] = sum(row[j] * error_signal[j] for j in range(self._latent_dim))
            grad[i] /= max(self._latent_dim, 1)

        return grad

    def feedback_alignment_score(self) -> float:
        test_error = [1.0 / math.sqrt(self._latent_dim)] * self._latent_dim
        grad = self.heuristic_gradient_approximation(test_error)
        grad_norm = math.sqrt(sum(g * g for g in grad))
        error_norm = math.sqrt(sum(e * e for e in test_error))
        if error_norm < 1e-6:
            return 0.0
        return min(1.0, grad_norm / error_norm)

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
            "feedback_alignment": round(self.feedback_alignment_score(), 4),
        }


# ═══════════════════════════════════════════════════════════════════
# Section 2: SpatialGRPO Variant
# — Spatial-aware reward attribution for multi-model routing
# ═══════════════════════════════════════════════════════════════════


@dataclass
class SpatialContext:
    """Spatial/graph context extracted from the knowledge hypergraph."""
    entity_count: int = 0
    hyperedge_count: int = 0
    avg_centrality: float = 0.0
    graph_density: float = 0.0
    precedence_depth: float = 0.0
    gravity_field_entropy: float = 0.5
    boundary_distance: float = 0.5
    has_cycles: bool = False


@dataclass
class SpatialReward:
    """A reward specifically attributable to spatial/graph information.

    S-GRPO core: R_spatial(i) = R_total(i) - R_baseline(i)
    """
    step_id: str
    total_reward: float = 0.0
    baseline_reward: float = 0.0
    spatial_delta: float = 0.0
    providers_involved: list[str] = field(default_factory=list)
    spatial_features_used: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def spatial_efficiency(self) -> float:
        if self.total_reward <= 0:
            return 0.0
        return self.spatial_delta / self.total_reward


@dataclass
class SGRPOResult:
    """Result of an S-GRPO optimization round."""
    round_id: int
    decisions: list[SpatialReward]
    avg_spatial_delta: float
    best_decision_id: str
    spatial_policy_update: dict[str, float]
    convergence_score: float


class SpatialContextExtractor:
    """Extract spatial/graph context from knowledge hypergraph for a query."""

    def extract(
        self, query_entities: list[str],
        hypergraph_store=None,
        precedence_model=None,
    ) -> SpatialContext:
        ctx = SpatialContext()

        if not hypergraph_store:
            return ctx

        ctx.entity_count = len(query_entities)

        relevant_edges = hypergraph_store.query_by_entities(
            query_entities, max_edges=50)
        ctx.hyperedge_count = len(relevant_edges)

        centrality_sum = 0.0
        for eid in query_entities:
            if eid in hypergraph_store._graph:
                degree = hypergraph_store._graph.degree(eid)
                max_deg = max(
                    (d for _, d in hypergraph_store._graph.degree()),
                    default=1)
                centrality_sum += degree / max(max_deg, 1)
        ctx.avg_centrality = centrality_sum / max(len(query_entities), 1)

        node_count = len(hypergraph_store._entities)
        edge_count = hypergraph_store._graph.number_of_edges()
        max_edges = node_count * (node_count - 1) / 2
        ctx.graph_density = edge_count / max(max_edges, 1)

        if precedence_model:
            all_types = []
            for he in relevant_edges[:10]:
                all_types.append(he.relation)
            if all_types:
                result = precedence_model.order_facts(all_types)
                ctx.precedence_depth = result.total_score

        import networkx as nx
        try:
            sub_nodes = set()
            for he in relevant_edges:
                sub_nodes.update(he.entities)
            sub = hypergraph_store._graph.subgraph(sub_nodes)
            ctx.has_cycles = not nx.is_forest(sub)
        except Exception:
            pass

        return ctx


class SpatialGRPOOptimizer:
    """Spatial-aware Group Relative Policy Optimization.

    Three decision layers optimized:
      L1: Provider Routing — which model best leverages spatial context?
      L2: Plan Ordering — which plan step order maximizes graph coherence?
      L3: Retrieval Path — which retrieval trajectory has best spatial alignment?
    """

    def __init__(self, learning_rate: float = 0.05, group_size: int = 8):
        self._lr = learning_rate
        self._group_size = group_size
        self._context_extractor = SpatialContextExtractor()

        self._spatial_weights: dict[str, float] = defaultdict(lambda: 0.0)
        self._reward_history: deque[float] = deque(maxlen=100)
        self._spatial_deltas: deque[float] = deque(maxlen=100)

    def score_baseline(
        self, action: str, features: dict[str, float],
    ) -> float:
        score = (
            features.get("capability", 0.5) * 0.4
            + features.get("latency_norm", 0.5) * 0.2
            + features.get("cost_norm", 0.5) * 0.2
            + features.get("reliability", 0.5) * 0.2
        )
        return min(1.0, max(0.0, score))

    def score_total(
        self, action: str, features: dict[str, float],
        spatial: SpatialContext,
    ) -> float:
        base = self.score_baseline(action, features)
        spatial_contrib = (
            spatial.avg_centrality * 0.2
            + spatial.graph_density * 0.1
            + spatial.precedence_depth * 0.2
            + spatial.boundary_distance * 0.1
            + (0.1 if spatial.has_cycles else 0.0)
            + spatial.gravity_field_entropy * 0.1
        )
        total = base * 0.6 + min(0.4, spatial_contrib) * 0.4
        return min(1.0, max(0.0, total))

    def optimize(
        self,
        group: list[tuple[str, dict[str, float]]],
        spatial: SpatialContext,
        actual_outcomes: dict[str, float],
    ) -> SGRPOResult:
        if not group:
            return self._empty_result()

        decisions: list[SpatialReward] = []

        for action, features in group:
            R_baseline = self.score_baseline(action, features)
            R_total = self.score_total(action, features, spatial)
            delta = R_total - R_baseline

            reward = SpatialReward(
                step_id=action,
                total_reward=R_total,
                baseline_reward=R_baseline,
                spatial_delta=delta,
                spatial_features_used=self._active_spatial(spatial),
            )
            decisions.append(reward)
            self._spatial_deltas.append(delta)

        total_scores = [
            actual_outcomes.get(d.step_id, d.total_reward)
            for d in decisions
        ]
        group_mean = sum(total_scores) / len(total_scores) if total_scores else 0.0

        policy_update: dict[str, float] = {}
        for d, outcome in zip(decisions, total_scores):
            advantage = outcome - group_mean
            if d.spatial_delta > 0.01 and advantage > 0:
                update = self._lr * advantage * d.spatial_delta
                self._spatial_weights[d.step_id] += update
                policy_update[d.step_id] = update
            elif d.spatial_delta < -0.01:
                update = -self._lr * abs(d.spatial_delta) * 0.5
                self._spatial_weights[d.step_id] = max(
                    -1.0, self._spatial_weights.get(d.step_id, 0) + update)
                policy_update[d.step_id] = update

        for k in self._spatial_weights:
            self._spatial_weights[k] = max(-1.0, min(1.0, self._spatial_weights[k]))

        self._reward_history.append(group_mean)

        avg_delta = (
            sum(d.spatial_delta for d in decisions) / len(decisions)
            if decisions else 0.0)

        best = max(decisions, key=lambda d: d.spatial_efficiency) if decisions else None

        conv_score = self._compute_convergence()

        result = SGRPOResult(
            round_id=len(self._reward_history),
            decisions=decisions,
            avg_spatial_delta=round(avg_delta, 4),
            best_decision_id=best.step_id if best else "",
            spatial_policy_update=policy_update,
            convergence_score=round(conv_score, 4),
        )

        logger.debug(
            f"S-GRPO: {len(decisions)} actions, avg_ΔR={avg_delta:.3f}, "
            f"best={result.best_decision_id}, conv={conv_score:.3f}",
        )
        return result

    def optimize_providers(
        self,
        providers: list[str],
        provider_features: dict[str, dict[str, float]],
        spatial: SpatialContext,
        actual_quality: dict[str, float],
    ) -> SGRPOResult:
        group = [(p, provider_features.get(p, {})) for p in providers]
        return self.optimize(group, spatial, actual_quality)

    def optimize_plan_steps(
        self,
        steps: list[str],
        step_features: dict[str, dict[str, float]],
        spatial: SpatialContext,
        step_outcomes: dict[str, float],
    ) -> SGRPOResult:
        group = [(s, step_features.get(s, {})) for s in steps]
        return self.optimize(group, spatial, step_outcomes)

    def optimize_retrieval_paths(
        self,
        paths: list[str],
        path_features: dict[str, dict[str, float]],
        spatial: SpatialContext,
        path_quality: dict[str, float],
    ) -> SGRPOResult:
        group = [(p, path_features.get(p, {})) for p in paths]
        return self.optimize(group, spatial, path_quality)

    def spatial_weight(self, action: str) -> float:
        return self._spatial_weights.get(action, 0.0)

    def is_spatially_preferred(self, action: str) -> bool:
        return self._spatial_weights.get(action, 0.0) > 0.1

    def closed_loop_validation(
        self, actions: list[str],
        baseline_quality: dict[str, float],
        with_spatial_quality: dict[str, float],
    ) -> dict[str, Any]:
        deltas = {}
        improved = []
        degraded = []
        unchanged = []

        for action in actions:
            baseline = baseline_quality.get(action, 0.0)
            spatial = with_spatial_quality.get(action, 0.0)
            delta = spatial - baseline
            deltas[action] = delta

            if delta > 0.01:
                improved.append((action, delta))
            elif delta < -0.01:
                degraded.append((action, abs(delta)))
            else:
                unchanged.append(action)

        total = len(actions)
        improved_count = len(improved)
        degraded_count = len(degraded)
        avg_delta = sum(deltas.values()) / max(total, 1)
        closure_rate = improved_count / max(total, 1)

        loop_closed = closure_rate > 0.5 and avg_delta > 0

        total_improvement = sum(d for _, d in improved)
        total_degradation = sum(d for _, d in degraded)
        spatial_efficiency = (
            total_improvement / max(total_degradation, 0.001)
            if total_degradation > 0 else float('inf')
        )

        if loop_closed:
            status = "closed"
            recommendation = (
                f"Spatial injection validated: {closure_rate:.0%} actions "
                f"improved (avg +{avg_delta:.4f}). Continue with spatial GRPO."
            )
        elif closure_rate > 0.3:
            status = "partial"
            recommendation = (
                f"Spatial injection partially effective: {closure_rate:.0%} "
                f"improved. Increase spatial feature depth or recalibrate "
                f"graph topology before next GRPO round."
            )
        else:
            status = "open"
            recommendation = (
                f"Spatial injection NOT validated: only {closure_rate:.0%} "
                f"improved (avg Δ={avg_delta:.4f}). Revert to baseline "
                f"policy and investigate graph topology mismatch."
            )

        return {
            "loop_status": status,
            "loop_closed": loop_closed,
            "closure_rate": round(closure_rate, 4),
            "avg_delta": round(avg_delta, 4),
            "improved_count": improved_count,
            "degraded_count": degraded_count,
            "unchanged_count": len(unchanged),
            "spatial_efficiency": round(spatial_efficiency, 4),
            "best_improvement": max(deltas.values()) if deltas else 0.0,
            "worst_degradation": min(deltas.values()) if deltas else 0.0,
            "recommendation": recommendation,
        }

    def spatial_significance(self) -> float:
        if len(self._spatial_deltas) < 5:
            return 1.0
        mean = sum(self._spatial_deltas) / len(self._spatial_deltas)
        var = sum(
            (d - mean) ** 2 for d in self._spatial_deltas) / len(self._spatial_deltas)
        if var < 0.0001:
            return 0.0 if mean > 0 else 1.0
        t_stat = mean / math.sqrt(var / len(self._spatial_deltas))
        df = len(self._spatial_deltas) - 1
        p = 2 * (1 - self._norm_cdf(abs(t_stat)))
        return min(1.0, max(0.0, p))

    @staticmethod
    def _norm_cdf(x: float) -> float:
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _active_spatial(self, spatial: SpatialContext) -> list[str]:
        active = []
        if spatial.avg_centrality > 0.1:
            active.append("centrality")
        if spatial.graph_density > 0.01:
            active.append("density")
        if spatial.precedence_depth > 0.1:
            active.append("precedence")
        if spatial.boundary_distance < 0.5:
            active.append("boundary")
        if spatial.has_cycles:
            active.append("cycles")
        if spatial.gravity_field_entropy > 0.1:
            active.append("gravity_entropy")
        return active

    def _compute_convergence(self) -> float:
        return _compute_convergence(list(self._reward_history), multiplier=3, min_count=10)

    def _empty_result(self) -> SGRPOResult:
        return SGRPOResult(
            round_id=0, decisions=[], avg_spatial_delta=0.0,
            best_decision_id="", spatial_policy_update={},
            convergence_score=0.0,
        )

    def stats(self) -> dict[str, Any]:
        return {
            "learned_weights_count": len(self._spatial_weights),
            "avg_spatial_delta": round(
                sum(self._spatial_deltas) / max(len(self._spatial_deltas), 1), 4),
            "convergence_score": self._compute_convergence(),
            "spatial_significance_p_value": round(self.spatial_significance(), 4),
            "reward_history_mean": round(
                sum(self._reward_history) / max(len(self._reward_history), 1), 3),
            "top_spatial_actions": sorted(
                self._spatial_weights.items(),
                key=lambda x: -x[1],
            )[:5],
        }


# ═══════════════════════════════════════════════════════════════════
# Section 3: TDM-R1 Variant
# — Non-differentiable reward RL for pipeline optimization
# ═══════════════════════════════════════════════════════════════════


class RewardType(str, Enum):
    """Types of non-differentiable reward signals."""
    BINARY_SUCCESS = "binary_success"
    QUALITY_SCORE = "quality_score"
    HUMAN_FEEDBACK = "human_feedback"
    BUDGET_COMPLIANCE = "budget"
    LATENCY = "latency"
    FORMAT_VALIDITY = "format"
    SAFETY_CHECK = "safety"


@dataclass
class PerStepReward:
    """Reward allocated to a single pipeline step."""
    step_index: int
    step_name: str
    raw_reward: float = 0.0
    surrogate_estimate: float = 0.0
    contribution_weight: float = 0.0
    step_context: dict = field(default_factory=dict)
    reward_type: str = "binary_success"


@dataclass
class TrajectoryReward:
    """Complete reward decomposition for a pipeline trajectory."""
    trajectory_id: str
    steps: list[PerStepReward]
    total_reward: float
    total_surrogate: float
    reward_types_used: list[str]
    trajectory_length: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class TDMOptimizationResult:
    """Result of a TDM-R1 optimization round."""
    round_id: int
    surrogate_loss: float
    policy_gradient_norm: float
    reward_improvement: float
    best_config: dict[str, Any]
    convergence_score: float
    per_stage_contributions: dict[str, float]


class SurrogateRewardModel:
    """Learns a differentiable proxy for non-differentiable reward signals.

    Intentional TD + NLMS diagonal scaling:
      Each feature weight has its own adaptive step size = η_base / (ε + E[g_i^2]).
      High-gradient features get smaller steps (prevents overshoot),
      low-gradient features get larger steps (explores more fully).
    """

    def __init__(self, learning_rate: float = 0.01, feature_dim: int = 10,
                 gamma: float = 0.3, epsilon: float = 1e-6):
        self._lr = learning_rate
        self._gamma = gamma
        self._epsilon = epsilon
        self._weights: dict[str, float] = defaultdict(float)
        self._bias: float = 0.0
        self._samples: int = 0
        self._loss_history: deque[float] = deque(maxlen=100)
        self._g2_avg: dict[str, float] = defaultdict(float)
        self._g2_bias_avg: float = 1e-3
        self._g2_decay: float = 0.95

    def predict(self, features: dict[str, float]) -> float:
        score = self._bias
        for feat, value in features.items():
            if feat in self._weights:
                score += self._weights[feat] * value
        return max(0.0, min(1.0, score))

    def train_step(
        self, features: dict[str, float], target: float,
    ) -> float:
        """Single SGD step with NLMS diagonal scaling + Intentional TD."""
        pred = self.predict(features)
        error = target - pred
        loss = error * error

        grads: dict[str, float] = {}
        for feat, value in features.items():
            grads[feat] = -2 * error * value
        bias_grad = -2 * error

        # Update NLMS running averages E[g_i^2]
        for feat, g in grads.items():
            self._g2_avg[feat] = (self._g2_decay * self._g2_avg[feat]
                                  + (1 - self._g2_decay) * g * g)
        self._g2_bias_avg = (self._g2_decay * self._g2_bias_avg
                            + (1 - self._g2_decay) * bias_grad * bias_grad)

        # Intentional TD: compute optimal step size
        if self._gamma > 0:
            effective_g2 = 0.0
            for feat, g in grads.items():
                scaled = g / (self._epsilon + self._g2_avg[feat])
                effective_g2 += scaled * scaled
            bias_scaled = bias_grad / (self._epsilon + self._g2_bias_avg)
            effective_g2 += bias_scaled * bias_scaled

            if effective_g2 > 0:
                eta_star = self._gamma * abs(error) / (effective_g2 + self._epsilon)
            else:
                eta_star = self._gamma * abs(error) / self._epsilon
        else:
            eta_star = self._lr

        # Apply NLMS-weighted updates
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


class TDMRewardOptimizer:
    """Non-differentiable reward RL for pipeline trajectory optimization.

    TDM-R1 three-phase decoupled optimization:
      Phase 1: Per-step reward distribution — allocate trajectory reward to steps
      Phase 2: Surrogate model training — learn to predict per-step rewards
      Phase 3: Policy gradient — optimize pipeline config using surrogate
    """

    DEFAULT_STAGE_PRIORS: dict[str, float] = {
        "perceive": 0.08,
        "cognize": 0.12,
        "ontogrow": 0.08,
        "plan": 0.15,
        "simulate": 0.10,
        "execute": 0.25,
        "reflect": 0.12,
        "evolve": 0.10,
        "tree_decompose": 0.20,
        "flow_refine": 0.35,
        "skeleton_build": 0.15,
        "diffusion_step": 0.30,
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
        self._stage_contributions: dict[str, list[float]] = defaultdict(list)

    def distribute_rewards(
        self,
        trajectory_id: str,
        stage_names: list[str],
        stage_contexts: list[dict[str, float]],
        total_outcome: float,
        reward_type: str = "binary_success",
        stage_weights: dict[str, float] | None = None,
    ) -> TrajectoryReward:
        n = len(stage_names)
        if n == 0:
            return TrajectoryReward(
                trajectory_id=trajectory_id, steps=[],
                total_reward=total_outcome, total_surrogate=0.0,
                reward_types_used=[reward_type], trajectory_length=0,
            )

        weights = stage_weights or {}
        total_weight = 0.0
        step_weights = []
        for i, name in enumerate(stage_names):
            if name in weights:
                w = weights[name]
            else:
                w = self.DEFAULT_STAGE_PRIORS.get(name, 1.0 / n)
            position_factor = 0.5 + (i / max(n - 1, 1))
            w = w * position_factor
            step_weights.append(w)
            total_weight += w

        steps: list[PerStepReward] = []
        total_surrogate = 0.0
        for i, name in enumerate(stage_names):
            contrib = step_weights[i] / max(total_weight, 0.001)
            raw = total_outcome * contrib
            ctx = stage_contexts[i] if i < len(stage_contexts) else {}

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

    def train_surrogate(
        self, trajectories: list[TrajectoryReward] | None = None,
    ) -> float:
        data = trajectories or self._history
        if not data:
            return float('inf')

        batch = []
        for traj in data[-50:]:
            for step in traj.steps:
                if step.step_context:
                    batch.append((step.step_context, step.raw_reward))

        if not batch:
            return float('inf')

        loss = self._surrogate.train_batch(batch)
        logger.debug(f"TDM-R1 surrogate: loss={loss:.4f}, samples={self._surrogate._samples}")
        return loss

    def optimize_policy(
        self,
        current_config: dict[str, Any],
        candidate_configs: list[dict[str, Any]],
        config_to_features: callable,
    ) -> TDMOptimizationResult:
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

        grad_norm = 0.0
        if len(scores) > 1:
            mean_score = sum(scores) / len(scores)
            grad_norm = math.sqrt(sum((s - mean_score) ** 2 for s in scores))

        prev_avg = (
            sum(t.total_reward for t in self._history[-10:]) / max(
                len(self._history[-10:]), 1)
            if self._history else 0.0)
        reward_improvement = best_score - prev_avg

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

    def aggregate_rewards(
        self, rewards: dict[str, float],
        weights: dict[str, float] | None = None,
    ) -> float:
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

    def most_contributing_stages(self, top_n: int = 5) -> list[tuple[str, float]]:
        contribs = {
            name: sum(vals) / max(len(vals), 1)
            for name, vals in self._stage_contributions.items()
        }
        return sorted(contribs.items(), key=lambda x: -x[1])[:top_n]

    def least_contributing_stages(self, top_n: int = 5) -> list[tuple[str, float]]:
        contribs = {
            name: sum(vals) / max(len(vals), 1)
            for name, vals in self._stage_contributions.items()
        }
        return sorted(contribs.items(), key=lambda x: x[1])[:top_n]

    def stage_pruning_candidates(self, threshold: float = 0.05) -> list[str]:
        return [
            name for name, avg in self.most_contributing_stages(20)
            if avg < threshold
        ]

    def few_step_quality_ratio(self) -> float:
        if len(self._history) < 10:
            return 1.0

        short = [t for t in self._history if t.trajectory_length <= 5]
        long = [t for t in self._history if t.trajectory_length >= 7]

        if not short or not long:
            return 1.0

        short_avg = sum(t.total_reward for t in short) / len(short)
        long_avg = sum(t.total_reward for t in long) / len(long)
        return short_avg / max(long_avg, 0.01)

    def _convergence(self) -> float:
        improvements = [r.reward_improvement for r in self._optimization_rounds[-5:]]
        return _compute_convergence(improvements, multiplier=2, min_count=3)

    def surrogate_annealing(
        self, current_config: dict[str, Any],
        candidate_configs: list[dict[str, Any]],
        config_to_features: callable,
        temperature: float = 1.0,
        cooling_steps: int = 100,
    ) -> dict[str, Any]:
        best_config = current_config
        best_score = self._surrogate.predict(config_to_features(current_config))
        stagnation = 0

        for step in range(1, cooling_steps + 1):
            T = temperature / math.log(math.e + step)

            if candidate_configs:
                for cfg in candidate_configs:
                    score = self._surrogate.predict(config_to_features(cfg))
                    dE = best_score - score
                    if dE < 0 or (T > 0.001 and random.random() < math.exp(-abs(dE) / max(T, 0.001))):
                        best_score = score
                        best_config = cfg
                        stagnation = 0
                    else:
                        stagnation += 1

                if stagnation >= 15 and T > 0.01:
                    tunnel_cfg = random.choice(candidate_configs)
                    tunnel_score = self._surrogate.predict(config_to_features(tunnel_cfg))
                    dE_tunnel = best_score - tunnel_score
                    if random.random() < math.exp(-abs(dE_tunnel) / T * 0.5):
                        best_score = tunnel_score
                        best_config = tunnel_cfg
                        stagnation = 0
                        logger.debug(
                            f"TDM F-N tunnel: step={step}, T={T:.4f}, "
                            f"best_score={best_score:.4f}"
                        )

        return {
            "best_config": best_config,
            "best_score": round(best_score, 4),
            "steps": cooling_steps,
            "final_temperature": round(temperature / math.log(math.e + cooling_steps), 4),
            "converged": stagnation >= 30,
        }

    def energy_landscape_pipeline(self) -> dict[str, Any]:
        stages = list(self._stage_contributions.keys())
        if len(stages) < 2:
            return {"energy": 0.0, "stages": stages, "optimal_config": []}

        h = {}
        for name, vals in self._stage_contributions.items():
            avg = sum(vals) / max(len(vals), 1)
            h[name] = math.tanh(avg)

        H = -sum(h.values())
        on_stages = [name for name, field in h.items() if field > 0]

        return {
            "energy": round(H, 4),
            "num_spins": len(stages),
            "external_fields": h,
            "on_stages": on_stages,
            "off_stages": [s for s in stages if s not in on_stages],
            "magnetization": round(sum(1 if v > 0 else -1 for v in h.values()) / len(stages), 3),
        }

    def convergence_certificate(self) -> dict[str, float | bool]:
        loss_ok = self._surrogate.avg_loss < 0.05
        conv_ok = self._convergence() > 0.95
        grad_ok = (
            len(self._optimization_rounds) >= 3 and
            all(r.policy_gradient_norm < 0.01 for r in self._optimization_rounds[-3:])
        )

        return {
            "surrogate_loss_low": loss_ok,
            "convergence_high": conv_ok,
            "gradient_small": grad_ok,
            "converged": loss_ok and conv_ok and grad_ok,
            "surrogate_loss": round(self._surrogate.avg_loss, 4),
            "convergence_score": round(self._convergence(), 4),
        }

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


def lifeengine_to_trajectory(
    engine: Any, session_id: str, success_rate: float,
) -> tuple[list[str], list[dict[str, float]]]:
    """Convert a completed LifeEngine cycle to TDM trajectory format."""
    stage_names = []
    stage_contexts = []

    for life_stage in engine.stages:
        name = life_stage.stage
        stage_names.append(name)

        ctx: dict[str, float] = {
            "duration_ms": life_stage.duration_ms / 10000.0,
            "status_code": 1.0 if life_stage.status == "completed" else 0.0,
            "has_error": 1.0 if life_stage.error else 0.0,
            "stage_order": life_stage.stage.count("_") / 10.0,
        }
        stage_contexts.append(ctx)

    return stage_names, stage_contexts


# ═══════════════════════════════════════════════════════════════════
# Section 4: Composite Optimizer + Singletons
# ═══════════════════════════════════════════════════════════════════


class GRPOOptimizer:
    """Composite GRPO optimizer holding all three variants.

    Provides unified access to LatentGRPO, SpatialGRPOOptimizer, and
    TDMRewardOptimizer, with aggregate stats() across all three.
    """

    def __init__(self, latent_dim: int = 6):
        self.latent = LatentGRPO(latent_dim=latent_dim)
        self.spatial = SpatialGRPOOptimizer()
        self.tdm = TDMRewardOptimizer()

    def stats(self) -> dict[str, Any]:
        return {
            "latent": self.latent.stats(),
            "spatial": self.spatial.stats(),
            "tdm": self.tdm.stats(),
        }


_grpo_composite: GRPOOptimizer | None = None


def get_grpo_optimizer(latent_dim: int = 6) -> GRPOOptimizer:
    """Get or create the composite GRPO optimizer singleton."""
    global _grpo_composite
    if _grpo_composite is None:
        _grpo_composite = GRPOOptimizer(latent_dim=latent_dim)
    return _grpo_composite


def get_latent_grpo(latent_dim: int = 6) -> LatentGRPO:
    """Backward-compatible: get LatentGRPO from composite."""
    return get_grpo_optimizer(latent_dim).latent


def get_sgrpo() -> SpatialGRPOOptimizer:
    """Backward-compatible: get SpatialGRPOOptimizer from composite."""
    return get_grpo_optimizer().spatial


def get_tdm_optimizer() -> TDMRewardOptimizer:
    """Backward-compatible: get TDMRewardOptimizer from composite."""
    return get_grpo_optimizer().tdm


__all__ = [
    # Shared utilities
    "_apply_nlms",
    "_compute_convergence",
    # LatentGRPO
    "LatentGRPO", "LatentEncoder", "LatentVector", "LatentGRPOResult",
    "get_latent_grpo",
    # SpatialGRPO
    "SpatialGRPOOptimizer", "SpatialContextExtractor", "SpatialContext",
    "SpatialReward", "SGRPOResult", "get_sgrpo",
    # TDM
    "TDMRewardOptimizer", "SurrogateRewardModel", "PerStepReward",
    "TrajectoryReward", "TDMOptimizationResult", "RewardType",
    "lifeengine_to_trajectory", "get_tdm_optimizer",
    # Composite
    "GRPOOptimizer", "get_grpo_optimizer",
]
