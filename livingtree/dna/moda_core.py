"""ModaCore — Mixture-of-Depths Attention for cognitive pipelines.

Inspired by Zhu et al. "Mixture-of-Depths Attention" (arXiv:2603.15619, 2026).
The paper addresses signal degradation in deep Transformers where informative
features from shallow layers are diluted by repeated residual updates.

ADAPTATION TO LIVINGTREE:
LivingTree's LifeEngine pipeline (perceive→cognize→...→evolve) suffers from
the same pathology. Instead of actual transformer K/V matrices, we use per-stage
content vectors and compute similarity-based joint attention across:
  1. Current stage content (analogous to sequence attention)
  2. Historical depth content from all preceding stages (depth attention)

CORE COMPONENTS:
  ModaDepthCache    — stores per-stage content vectors as "depth KV"
  ModaJointScorer   — computes joint similarity (sequence + depth)
  ModaPreservationGate — learnable gate controlling depth information retention
  ModaFidelityMonitor — tracks information preservation quality over time
  ModaCore          — unified pipeline orchestrator

ARCHITECTURE:
  ┌─────────────────────────────────────────────────────────┐
  │  Stage N                                                  │
  │  Q (current) ──┬── attend to Sequence KV (this stage)     │
  │                └── attend to Depth KV (stages 0..N-1)    │
  │                                                           │
  │  Joint Softmax combines both → output O                   │
  │  O is stored in DepthCache for stages N+1.. to use         │
  └─────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

DEFAULT_DIM: int = 768
DEFAULT_TEMPERATURE: float = 1.0
DEFAULT_DEPTH_DECAY: float = 0.95  # exponential decay for older depth layers


# ═══ Math Utilities ═══

def _l2_norm(vec: list[float]) -> float:
    return math.sqrt(sum(v * v for v in vec))


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = _l2_norm(vec)
    if norm < 1e-12:
        return [0.0] * len(vec)
    return [v / norm for v in vec]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    norm_a = _l2_norm(a)
    norm_b = _l2_norm(b)
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0.0
    raw = _dot(a, b) / (norm_a * norm_b)
    return max(-1.0, min(1.0, raw))


# ═══ Data Types ═══


@dataclass
class DepthEntry:
    """A single entry in the depth K/V cache.

    Each pipeline stage stores one entry after execution, recording
    the content vector that was produced at that stage.
    """

    stage_name: str
    stage_index: int
    content_vector: list[float]
    quality_score: float = 1.0
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DepthAttentionResult:
    """Output of a MoDA joint attention computation.

    Contains both the fused output vector and diagnostics about
    how much each source contributed.
    """

    fused_vector: list[float]
    sequence_similarity: float
    depth_similarities: dict[str, float]
    attention_weights: dict[str, float]
    sequence_weight: float
    depth_total_weight: float
    top_depth_stages: list[str]
    preservation_score: float
    fidelity_delta: float


@dataclass
class GateState:
    """State of a single preservation gate controlling one depth layer.

    Each gate learns over time how much to trust its associated depth
    stage based on observed outcomes.
    """

    stage_name: str
    weight: float = 1.0
    bias: float = 0.0
    hit_count: int = 0
    miss_count: int = 0

    @property
    def success_rate(self) -> float:
        total = self.hit_count + self.miss_count
        return self.hit_count / max(total, 1)


# ═══ ModaDepthCache ═══


class ModaDepthCache:
    """Stores per-stage content vectors as historical depth KV.

    In MoDA terms, each DepthEntry is the "depth KV pair" for a stage.
    Current stages attend to these historical entries to recover
    information that might have been diluted by intermediate processing.

    Depth decay: older entries are weighted less by default (exponential
    decay factor), simulating the natural degradation of information
    over depth, while MoDA's attention mechanism selectively recovers
    those that remain relevant.
    """

    def __init__(self, depth_decay: float = DEFAULT_DEPTH_DECAY) -> None:
        self._entries: list[DepthEntry] = []
        self.depth_decay = depth_decay

    def store(self, entry: DepthEntry) -> None:
        existing = [i for i, e in enumerate(self._entries) if e.stage_name == entry.stage_name]
        if existing:
            self._entries[existing[0]] = entry
        else:
            self._entries.append(entry)
            self._entries.sort(key=lambda e: e.stage_index)

    def get_depth_vectors(self) -> list[list[float]]:
        return [e.content_vector for e in self._entries]

    def get_depth_stages(self) -> list[str]:
        return [e.stage_name for e in self._entries]

    def get_entry(self, stage_name: str) -> DepthEntry | None:
        for e in self._entries:
            if e.stage_name == stage_name:
                return e
        return None

    def get_entries_before(self, stage_index: int) -> list[DepthEntry]:
        return [e for e in self._entries if e.stage_index < stage_index]

    def get_decayed_weights(self) -> list[float]:
        n = len(self._entries)
        if n == 0:
            return []
        return [self.depth_decay ** (n - 1 - i) for i in range(n)]

    @property
    def depth_count(self) -> int:
        return len(self._entries)

    @property
    def max_depth_index(self) -> int:
        return max((e.stage_index for e in self._entries), default=-1)

    def reset(self) -> None:
        self._entries.clear()

    def __repr__(self) -> str:
        names = [e.stage_name for e in self._entries]
        return f"ModaDepthCache(depth={len(self._entries)}, stages={names})"


# ═══ ModaJointScorer ═══


class ModaJointScorer:
    """Joint sequence + depth similarity scoring under a unified softmax.

    This is the core MoDA operation: given a query vector (current stage's
    content), compute similarity to:
      1. The current stage's own content (sequence attention)
      2. All preceding stages' content vectors in the depth cache (depth attention)

    All similarities are combined under one softmax with configurable
    sequence/depth temperature and depth decay.

    THE KEY INSIGHT from MoDA:
    Instead of treating sequence and depth as separate passes (which loses
    relative importance information), combine them in one softmax so the
    model can learn to allocate attention between current and historical
    information adaptively.
    """

    def __init__(
        self,
        sequence_temperature: float = DEFAULT_TEMPERATURE,
        depth_temperature: float = DEFAULT_TEMPERATURE,
        depth_decay: float = DEFAULT_DEPTH_DECAY,
    ) -> None:
        self.seq_temp = max(sequence_temperature, 0.01)
        self.depth_temp = max(depth_temperature, 0.01)
        self.depth_decay = depth_decay

    def score(
        self,
        query_vector: list[float],
        sequence_vector: list[float],
        depth_vectors: list[list[float]],
        depth_stages: list[str],
        quality_scores: list[float] | None = None,
    ) -> DepthAttentionResult:
        """Compute joint MoDA attention and return fused output.

        Algorithm:
          1. Compute cosine similarity: query vs sequence
          2. Compute cosine similarities: query vs each depth entry
          3. Apply temperature scaling and depth decay to all similarities
          4. Join all logits in one softmax
          5. Compute weighted average of all vectors = fused output
          6. Compute preservation and fidelity metrics

        Args:
            query_vector: Current stage's content vector (the "Q" in attention)
            sequence_vector: Current stage's output vector (the "V" for sequence)
            depth_vectors: All preceding stage content vectors (the "V" for depth)
            depth_stages: Stage names for depth vectors
            quality_scores: Per-depth quality scores (optional, for weighted gating)

        Returns:
            DepthAttentionResult with fused vector and diagnostics
        """
        seq_sim = _cosine_similarity(query_vector, sequence_vector)
        seq_logit = seq_sim / self.seq_temp

        n_depth = len(depth_vectors)
        depth_logits: list[float] = []
        depth_sims: list[float] = []
        depth_names: list[str] = []

        for i, (dv, ds) in enumerate(zip(depth_vectors, depth_stages)):
            if i >= len(depth_stages):
                break
            sim = _cosine_similarity(query_vector, dv)
            depth_sims.append(sim)

            decay = self.depth_decay ** (n_depth - 1 - i)
            quality = quality_scores[i] if quality_scores and i < len(quality_scores) else 1.0
            logit = (sim / self.depth_temp) * decay * quality
            depth_logits.append(logit)
            depth_names.append(ds)

        all_logits = [seq_logit] + depth_logits
        all_names = ["sequence"] + depth_names
        max_logit = max(all_logits)
        exps = [math.exp(z - max_logit) for z in all_logits]
        total = sum(exps)
        weights = [e / total for e in exps] if total > 0 else [1.0 / len(exps)] * len(exps)

        seq_weight = weights[0]
        depth_weights = weights[1:]

        dim = len(query_vector)
        fused = [0.0] * dim

        for j in range(dim):
            fused[j] += seq_weight * sequence_vector[j]
            for k, dv in enumerate(depth_vectors):
                if k < len(depth_weights):
                    fused[j] += depth_weights[k] * dv[j]

        fused = _l2_normalize(fused)

        depth_total_weight = sum(depth_weights)
        depth_sim_dict = dict(zip(depth_names, depth_sims))
        attn_dict = dict(zip(all_names, weights))

        indexed_weights = list(enumerate(depth_weights))
        indexed_weights.sort(key=lambda x: -x[1])
        top_depth = [depth_names[i] for i, _ in indexed_weights[:3]]

        preservation_score = self._compute_preservation(depth_sims, depth_weights)
        fidelity_delta = _cosine_similarity(query_vector, fused) - _cosine_similarity(
            query_vector, sequence_vector
        )

        return DepthAttentionResult(
            fused_vector=fused,
            sequence_similarity=seq_sim,
            depth_similarities=depth_sim_dict,
            attention_weights=attn_dict,
            sequence_weight=seq_weight,
            depth_total_weight=depth_total_weight,
            top_depth_stages=top_depth,
            preservation_score=preservation_score,
            fidelity_delta=fidelity_delta,
        )

    @staticmethod
    def _compute_preservation(
        depth_sims: list[float], depth_weights: list[float]
    ) -> float:
        if not depth_sims or not depth_weights:
            return 0.0
        weighted_sum = sum(s * w for s, w in zip(depth_sims, depth_weights))
        total_w = sum(depth_weights)
        return weighted_sum / max(total_w, 1e-12)


# ═══ ModaPreservationGate ═══


class ModaPreservationGate:
    """Learnable gates controlling how much each depth layer's information is retained.

    Each depth layer (pipeline stage) gets a gate that learns from observed
    outcomes: when the system correctly uses information from a stage, that
    stage's gate opens wider; when it's misleading, the gate closes.

    This replaces the simple uniform accumulation in VectorContext with
    learned, outcome-driven weighting from MoDA.
    """

    def __init__(self, stage_names: list[str]) -> None:
        self._gates: dict[str, GateState] = {s: GateState(stage_name=s) for s in stage_names}
        self._stage_names = list(stage_names)
        n = len(stage_names)
        if n > 0:
            for i, name in enumerate(stage_names):
                alibi_slope = 1.0 / (2.0 ** (i + 1))
                self._gates[name].bias = -alibi_slope
                self._gates[name].weight = max(0.3, 1.0 - alibi_slope * 0.5)

    def get_gate_weight(self, stage_name: str) -> float:
        gate = self._gates.get(stage_name)
        if gate is None:
            return 1.0
        return max(0.0, min(1.0, gate.weight + gate.bias))

    def get_all_weights(self) -> dict[str, float]:
        return {s: self.get_gate_weight(s) for s in self._stage_names}

    def record_success(self, stage_name: str, bonus: float = 0.1) -> None:
        gate = self._gates.get(stage_name)
        if gate is None:
            return
        gate.hit_count += 1
        gate.bias = min(1.0, gate.bias + bonus)

    def record_failure(self, stage_name: str, penalty: float = 0.1) -> None:
        gate = self._gates.get(stage_name)
        if gate is None:
            return
        gate.miss_count += 1
        gate.bias = max(-1.0, gate.bias - penalty)

    def update_from_outcome(
        self, attention_result: DepthAttentionResult, success: bool
    ) -> None:
        top_stages = attention_result.top_depth_stages
        reward = 0.05 if success else -0.08
        for stage_name in top_stages:
            self._gates[stage_name].bias = max(
                -1.0, min(1.0, self._gates[stage_name].bias + reward)
            )
            if success:
                self._gates[stage_name].hit_count += 1
            else:
                self._gates[stage_name].miss_count += 1

    def stats(self) -> dict[str, dict[str, Any]]:
        return {
            s: {
                "weight": g.weight,
                "bias": g.bias,
                "effective": self.get_gate_weight(s),
                "success_rate": g.success_rate,
                "hit_count": g.hit_count,
                "miss_count": g.miss_count,
            }
            for s, g in self._gates.items()
        }

    def reset(self) -> None:
        for gate in self._gates.values():
            gate.bias = 0.0
            gate.hit_count = 0
            gate.miss_count = 0


# ═══ ModaFidelityMonitor ═══


@dataclass
class FidelitySnapshot:
    """A single fidelity measurement at a point in the pipeline."""

    stage_name: str
    stage_index: int
    preservation_score: float
    fidelity_delta: float
    depth_attention_ratio: float
    top_depth_stages: list[str]
    timestamp: float


class ModaFidelityMonitor:
    """Tracks information preservation fidelity across the cognitive pipeline.

    The MoDA paper's core motivation is signal degradation — features from
    early layers are "diluted" by later residual updates. This monitor
    tracks cumulative degradation and provides early warning when key
    features are being lost.

    Metrics tracked:
      - preservation_score: how well depth information is retained at each stage
      - fidelity_delta: change in direction between raw and fused output
      - depth_attention_ratio: proportion of attention allocated to depth vs sequence
      - cumulative_degradation: running average of (1 - preservation_score)
    """

    def __init__(self, warning_threshold: float = 0.3) -> None:
        self._snapshots: list[FidelitySnapshot] = []
        self.warning_threshold = warning_threshold

    def record(self, stage_name: str, stage_index: int, result: DepthAttentionResult) -> None:
        snap = FidelitySnapshot(
            stage_name=stage_name,
            stage_index=stage_index,
            preservation_score=result.preservation_score,
            fidelity_delta=result.fidelity_delta,
            depth_attention_ratio=result.depth_total_weight,
            top_depth_stages=list(result.top_depth_stages),
            timestamp=time.time(),
        )
        self._snapshots.append(snap)

    @property
    def cumulative_degradation(self) -> float:
        if not self._snapshots:
            return 0.0
        total = sum(1.0 - s.preservation_score for s in self._snapshots)
        return total / len(self._snapshots)

    @property
    def is_degrading(self) -> bool:
        return self.cumulative_degradation > self.warning_threshold

    def get_degrading_stages(self) -> list[str]:
        return [
            s.stage_name
            for s in self._snapshots
            if (1.0 - s.preservation_score) > self.warning_threshold
        ]

    def need_early_recovery(self) -> bool:
        if len(self._snapshots) < 2:
            return False
        recent = [s.preservation_score for s in self._snapshots[-3:]]
        if len(recent) < 2:
            return False
        return all(a > b for a, b in zip(recent, recent[1:]))

    def stats(self) -> dict[str, Any]:
        return {
            "total_stages": len(self._snapshots),
            "cumulative_degradation": round(self.cumulative_degradation, 4),
            "is_degrading": self.is_degrading,
            "degrading_stages": self.get_degrading_stages(),
            "need_early_recovery": self.need_early_recovery(),
            "latest_preservation": (
                self._snapshots[-1].preservation_score if self._snapshots else 0.0
            ),
        }

    def reset(self) -> None:
        self._snapshots.clear()


# ═══ ModaCore ═══


class ModaCore:
    """Unified MoDA pipeline orchestrator for LivingTree.

    Wraps all MoDA components into a single, easy-to-use interface.
    Drop-in enhancement for LifeEngine's existing pipeline:
      before: stage output → VectorContext.update
      after:  stage output → ModaCore.attend → VectorContext.update (depth-aware)

    Usage:
        core = get_moda_core()
        core.store_depth("perceive", 0, perceive_vector)

        result = core.attend(
            query=cognize_query_vec,
            current=cognize_output_vec,
            current_stage="cognize",
            stage_index=1,
        )
        # result.fused_vector → use this as the enhanced cognize output
        # core.monitor stats → check if information is degrading
    """

    def __init__(self) -> None:
        self.cache = ModaDepthCache()
        self.scorer = ModaJointScorer()
        self.gate = ModaPreservationGate(
            ["perceive", "cognize", "ontogrow", "plan", "simulate", "execute", "reflect", "evolve"]
        )
        self.monitor = ModaFidelityMonitor()

    def store_depth(
        self, stage_name: str, stage_index: int, content_vector: list[float],
        quality_score: float = 1.0, metadata: dict[str, Any] | None = None,
    ) -> None:
        entry = DepthEntry(
            stage_name=stage_name,
            stage_index=stage_index,
            content_vector=content_vector,
            quality_score=quality_score,
            metadata=metadata or {},
        )
        self.cache.store(entry)

    def attend(
        self,
        query: list[float],
        current: list[float],
        current_stage: str,
        stage_index: int,
    ) -> DepthAttentionResult:
        prior = self.cache.get_entries_before(stage_index)
        depth_vecs = [e.content_vector for e in prior]
        depth_stages = [e.stage_name for e in prior]

        gate_qualities = [self.gate.get_gate_weight(s) for s in depth_stages]

        result = self.scorer.score(
            query_vector=query,
            sequence_vector=current,
            depth_vectors=depth_vecs,
            depth_stages=depth_stages,
            quality_scores=gate_qualities,
        )

        self.monitor.record(current_stage, stage_index, result)

        logger.debug(
            "ModaCore: stage={} seq_weight={:.3f} depth_weight={:.3f} "
            "preservation={:.3f} fidelity_delta={:.3f} top_depth={}",
            current_stage, result.sequence_weight, result.depth_total_weight,
            result.preservation_score, result.fidelity_delta,
            result.top_depth_stages,
        )

        return result

    def record_outcome(self, stage_name: str, success: bool) -> None:
        self.gate.record_success(stage_name) if success else self.gate.record_failure(stage_name)

    def get_depth_weights(self) -> dict[str, float]:
        return self.gate.get_all_weights()

    def fidelity_stats(self) -> dict[str, Any]:
        return self.monitor.stats()

    def reset(self) -> None:
        self.cache.reset()
        self.gate.reset()
        self.monitor.reset()

    def __repr__(self) -> str:
        return (
            f"ModaCore(depth={self.cache.depth_count}, "
            f"degradation={self.monitor.cumulative_degradation:.3f}, "
            f"is_degrading={self.monitor.is_degrading})"
        )


# ═══ Singleton ═══

_core: ModaCore | None = None


def get_moda_core() -> ModaCore:
    global _core
    if _core is None:
        _core = ModaCore()
        logger.info("ModaCore singleton initialized")
    return _core


__all__ = [
    "ModaCore",
    "ModaDepthCache",
    "ModaJointScorer",
    "ModaPreservationGate",
    "ModaFidelityMonitor",
    "DepthEntry",
    "DepthAttentionResult",
    "GateState",
    "FidelitySnapshot",
    "get_moda_core",
]
