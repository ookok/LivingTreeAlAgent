"""Spatial-Aware Reward Optimizer — S-GRPO for multi-model routing.

Based on Ni et al. (ACL 2026), arXiv:2601.03248:
  "STReasoner: Spatio-Temporal Reasoning via Spatial-Aware RL"

Core innovation adapted to LivingTree:
  S-GRPO = Group Relative Policy Optimization where the reward is
  specifically attributable to SPATIAL information (graph/hypergraph
  topology, precedence structure, knowledge gravity field).

Key formula:
  R_spatial = R_total - R_without_spatial
  → rewards only the marginal contribution of spatial/graph features

Applied to three decision layers:
  1. Provider Routing: which provider benefits most from spatial context?
  2. Plan Validation: which plan step ordering is best supported by topology?
  3. Knowledge Retrieval: which retrieval path maximizes spatial coherence?

Three-stage optimization (mapped from STReasoner's training pipeline):
  Stage 1: Baseline scoring (no spatial) — establish baseline
  Stage 2: Spatial injection — add graph/hypergraph features  
  Stage 3: S-GRPO — reinforce decisions that leverage spatial info well
"""

from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══ Data Types ═══


@dataclass
class SpatialContext:
    """Spatial/graph context extracted from the knowledge hypergraph."""
    entity_count: int = 0
    hyperedge_count: int = 0
    avg_centrality: float = 0.0      # Average node centrality in relevant subgraph
    graph_density: float = 0.0       # Edge-to-node ratio
    precedence_depth: float = 0.0    # Max precedence chain length
    gravity_field_entropy: float = 0.5  # From knowledge gravity model
    boundary_distance: float = 0.5   # Distance to nearest decision boundary
    has_cycles: bool = False         # Whether the relevant subgraph has cycles


@dataclass
class SpatialReward:
    """A reward specifically attributable to spatial/graph information.

    S-GRPO core: R_spatial(i) = R_total(i) - R_baseline(i)
    where R_total includes graph features and R_baseline is without.
    """
    step_id: str
    total_reward: float = 0.0        # R_total — with spatial context
    baseline_reward: float = 0.0     # R_baseline — without spatial context
    spatial_delta: float = 0.0       # ΔR = R_total - R_baseline
    providers_involved: list[str] = field(default_factory=list)
    spatial_features_used: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def spatial_efficiency(self) -> float:
        """How much the spatial info contributed (0=useless, 1=critical)."""
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
    spatial_policy_update: dict[str, float]  # action → weight adjustment
    convergence_score: float


# ═══ Spatial Context Extractor ═══


class SpatialContextExtractor:
    """Extract spatial/graph context from knowledge hypergraph for a query.

    STReasoner analog: the time series encoder that captures spatial
    dependencies. Here we capture hypergraph topology dependencies.
    """

    def extract(
        self, query_entities: list[str],
        hypergraph_store=None,
        precedence_model=None,
    ) -> SpatialContext:
        """Extract spatial context from the knowledge topology."""
        ctx = SpatialContext()

        if not hypergraph_store:
            return ctx

        ctx.entity_count = len(query_entities)

        # Count relevant hyperedges
        relevant_edges = hypergraph_store.query_by_entities(
            query_entities, max_edges=50)
        ctx.hyperedge_count = len(relevant_edges)

        # Centrality: average degree of query entities in hypergraph
        centrality_sum = 0.0
        for eid in query_entities:
            if eid in hypergraph_store._graph:
                degree = hypergraph_store._graph.degree(eid)
                max_deg = max(
                    (d for _, d in hypergraph_store._graph.degree()),
                    default=1)
                centrality_sum += degree / max(max_deg, 1)
        ctx.avg_centrality = centrality_sum / max(len(query_entities), 1)

        # Graph density
        node_count = len(hypergraph_store._entities)
        edge_count = hypergraph_store._graph.number_of_edges()
        max_edges = node_count * (node_count - 1) / 2
        ctx.graph_density = edge_count / max(max_edges, 1)

        # Precedence depth
        if precedence_model:
            all_types = []
            for he in relevant_edges[:10]:
                all_types.append(he.relation)
            if all_types:
                result = precedence_model.order_facts(all_types)
                ctx.precedence_depth = result.total_score

        # Cycle detection
        import networkx as nx
        try:
            # Check if the relevant subgraph has cycles
            sub_nodes = set()
            for he in relevant_edges:
                sub_nodes.update(he.entities)
            sub = hypergraph_store._graph.subgraph(sub_nodes)
            ctx.has_cycles = not nx.is_forest(sub)
        except Exception:
            pass

        return ctx


# ═══ S-GRPO Optimizer ═══


class SpatialGRPOOptimizer:
    """Spatial-aware Group Relative Policy Optimization.

    STReasoner's S-GRPO algorithm adapted to LivingTree's decision layers:
      - Group: a batch of N decision alternatives (N providers, N plans, etc.)
      - Relative: score each alternative relative to the group mean
      - Policy Optimization: reinforce decisions with positive spatial delta
      - Spatial-Aware: reward ONLY the spatial contribution (R_total - R_baseline)

    Three decision layers optimized:
      L1: Provider Routing — which model best leverages spatial context?
      L2: Plan Ordering — which plan step order maximizes graph coherence?
      L3: Retrieval Path — which retrieval trajectory has best spatial alignment?
    """

    def __init__(self, learning_rate: float = 0.05, group_size: int = 8):
        self._lr = learning_rate
        self._group_size = group_size
        self._context_extractor = SpatialContextExtractor()

        # Policy weights per action (learned via S-GRPO)
        self._spatial_weights: dict[str, float] = defaultdict(lambda: 0.0)
        # Historical rewards for convergence tracking
        self._reward_history: deque[float] = deque(maxlen=100)
        # Spatial deltas for analysis
        self._spatial_deltas: deque[float] = deque(maxlen=100)

    # ── Baseline: Score WITHOUT Spatial Context ──

    def score_baseline(
        self, action: str, features: dict[str, float],
    ) -> float:
        """Score without spatial information (R_baseline).

        Uses only non-spatial features: capability scores, latencies, cost.
        This is the counterfactual: "how good would this decision be
        if we didn't have the knowledge graph?"
        """
        # Non-spatial features only
        score = (
            features.get("capability", 0.5) * 0.4
            + features.get("latency_norm", 0.5) * 0.2
            + features.get("cost_norm", 0.5) * 0.2
            + features.get("reliability", 0.5) * 0.2
        )
        return min(1.0, max(0.0, score))

    # ── Total: Score WITH Spatial Context ──

    def score_total(
        self, action: str, features: dict[str, float],
        spatial: SpatialContext,
    ) -> float:
        """Score with spatial information (R_total).

        Includes spatial features: centrality, density, precedence, cycles.
        """
        base = self.score_baseline(action, features)

        # Spatial feature contributions
        spatial_contrib = (
            spatial.avg_centrality * 0.2
            + spatial.graph_density * 0.1
            + spatial.precedence_depth * 0.2
            + spatial.boundary_distance * 0.1
            + (0.1 if spatial.has_cycles else 0.0)
            + spatial.gravity_field_entropy * 0.1
        )

        # Blend: baseline + spatial contribution
        total = base * 0.6 + min(0.4, spatial_contrib) * 0.4
        return min(1.0, max(0.0, total))

    # ── S-GRPO Step ──

    def optimize(
        self,
        group: list[tuple[str, dict[str, float]]],  # [(action, features)]
        spatial: SpatialContext,
        actual_outcomes: dict[str, float],  # action → observed quality
    ) -> SGRPOResult:
        """One S-GRPO optimization round over a group of decisions.

        Algorithm:
          1. For each action in group:
             a. Compute R_baseline (no spatial)
             b. Compute R_total (with spatial)
             c. spatial_delta = R_total - R_baseline
          2. Compute group mean of spatial_deltas
          3. For each action:
             - advantage = actual_outcome - group_mean
             - If spatial_delta > 0 AND advantage > 0 → reinforce
             - If spatial_delta < 0 → penalize
          4. Update policy weights: w_i += lr × advantage × sign(delta)

        Args:
            group: List of (action_name, feature_dict) tuples
            spatial: Extracted spatial context for this batch
            actual_outcomes: Observed quality scores for each action

        Returns:
            SGRPOResult with updated policy weights
        """
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

        # Group relative scoring
        total_scores = [
            actual_outcomes.get(d.step_id, d.total_reward)
            for d in decisions
        ]
        group_mean = sum(total_scores) / len(total_scores) if total_scores else 0.0

        # Policy update: reinforce actions where spatial info helped
        policy_update: dict[str, float] = {}
        for d, outcome in zip(decisions, total_scores):
            advantage = outcome - group_mean
            if d.spatial_delta > 0.01 and advantage > 0:
                # Positive spatial contribution + above average → reinforce
                update = self._lr * advantage * d.spatial_delta
                self._spatial_weights[d.step_id] += update
                policy_update[d.step_id] = update
            elif d.spatial_delta < -0.01:
                # Negative spatial contribution → penalize
                update = -self._lr * abs(d.spatial_delta) * 0.5
                self._spatial_weights[d.step_id] = max(
                    -1.0, self._spatial_weights.get(d.step_id, 0) + update)
                policy_update[d.step_id] = update

        # Normalize weights to [-1, 1]
        for k in self._spatial_weights:
            self._spatial_weights[k] = max(-1.0, min(1.0, self._spatial_weights[k]))

        self._reward_history.append(group_mean)

        avg_delta = (
            sum(d.spatial_delta for d in decisions) / len(decisions)
            if decisions else 0.0)

        # Best decision: highest spatial efficiency
        best = max(decisions, key=lambda d: d.spatial_efficiency) if decisions else None

        # Convergence: reward history variance (low = converged)
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

    # ── Layer-Specific Optimization ──

    def optimize_providers(
        self,
        providers: list[str],
        provider_features: dict[str, dict[str, float]],
        spatial: SpatialContext,
        actual_quality: dict[str, float],
    ) -> SGRPOResult:
        """L1: Optimize provider routing with spatial reward."""
        group = [(p, provider_features.get(p, {})) for p in providers]
        return self.optimize(group, spatial, actual_quality)

    def optimize_plan_steps(
        self,
        steps: list[str],
        step_features: dict[str, dict[str, float]],
        spatial: SpatialContext,
        step_outcomes: dict[str, float],
    ) -> SGRPOResult:
        """L2: Optimize plan step ordering with spatial reward."""
        group = [(s, step_features.get(s, {})) for s in steps]
        return self.optimize(group, spatial, step_outcomes)

    def optimize_retrieval_paths(
        self,
        paths: list[str],
        path_features: dict[str, dict[str, float]],
        spatial: SpatialContext,
        path_quality: dict[str, float],
    ) -> SGRPOResult:
        """L3: Optimize retrieval trajectory with spatial reward."""
        group = [(p, path_features.get(p, {})) for p in paths]
        return self.optimize(group, spatial, path_quality)

    # ── Policy Query ──

    def spatial_weight(self, action: str) -> float:
        """Get the learned spatial weight for an action (-1 to 1)."""
        return self._spatial_weights.get(action, 0.0)

    def is_spatially_preferred(self, action: str) -> bool:
        """Whether spatial info positively contributes for this action."""
        return self._spatial_weights.get(action, 0.0) > 0.1

    # ── Statistical Tests ──

    def spatial_significance(self) -> float:
        """Statistical significance of spatial contribution.

        One-sample t-test: is the mean spatial delta significantly > 0?
        Returns p-value approximation.
        """
        if len(self._spatial_deltas) < 5:
            return 1.0
        mean = sum(self._spatial_deltas) / len(self._spatial_deltas)
        var = sum(
            (d - mean) ** 2 for d in self._spatial_deltas) / len(self._spatial_deltas)
        if var < 0.0001:
            return 0.0 if mean > 0 else 1.0
        t_stat = mean / math.sqrt(var / len(self._spatial_deltas))
        # Approximate p-value from t-distribution
        df = len(self._spatial_deltas) - 1
        # Welch-Satterthwaite approximation
        p = 2 * (1 - self._norm_cdf(abs(t_stat)))
        return min(1.0, max(0.0, p))

    @staticmethod
    def _norm_cdf(x: float) -> float:
        """Standard normal CDF approximation."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    # ── Helpers ──

    def _active_spatial(self, spatial: SpatialContext) -> list[str]:
        """List which spatial features are active (non-zero)."""
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
        """How well the policy has converged (1 = fully converged)."""
        if len(self._reward_history) < 10:
            return 0.0
        recent = list(self._reward_history)[-10:]
        mean = sum(recent) / len(recent)
        var = sum((r - mean) ** 2 for r in recent) / len(recent)
        return max(0.0, min(1.0, 1.0 - math.sqrt(var) * 3))

    def _empty_result(self) -> SGRPOResult:
        return SGRPOResult(
            round_id=0, decisions=[], avg_spatial_delta=0.0,
            best_decision_id="", spatial_policy_update={},
            convergence_score=0.0,
        )

    # ── Stats ──

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


# ═══ Singleton ═══

_sgrpo: SpatialGRPOOptimizer | None = None


def get_sgrpo() -> SpatialGRPOOptimizer:
    global _sgrpo
    if _sgrpo is None:
        _sgrpo = SpatialGRPOOptimizer()
    return _sgrpo


__all__ = [
    "SpatialGRPOOptimizer", "SpatialContext", "SpatialReward",
    "SGRPOResult", "SpatialContextExtractor", "get_sgrpo",
]
