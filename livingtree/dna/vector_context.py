"""Vector Context Bus — embedding-based inter-stage communication carrier.

Replaces text-based LifeContext as the communication medium between LifeEngine
pipeline stages. Instead of passing text strings that require repeated
encode→decode→encode round-trips through the LLM, a single 768-dim embedding
vector evolves through the pipeline, updated incrementally at each stage.

CORE INSIGHT: LLM inputs are token embeddings. Passing text between stages
forces unnecessary round-trips. A shared vector eliminates this overhead.

v2.4 — MoDA-Enhanced (arXiv:2603.15619):
    Added cross-depth attention, depth-aware embedding with positional encoding,
    preservation fidelity tracking, and skip-connection-style recovery.
    VectorContext now integrates with ModaCore for joint sequence+depth
    attention across pipeline stages.

Architecture:
    Text → [embed] → v0 → perceive → v1 → cognize → v2 → ... → v8 → [decode] → Text
                       ↑ 1 stage ↑       ↑ 1 stage ↑            ↑ 1 stage ↑
                      vector update     vector update          vector update

    NOW with MoDA: each stage attends to all prior stage vectors via
    joint softmax, recovering diluted information from early stages.

The vector IS the living context — it accumulates information from each stage
without ever being converted back to text.

Integration with LifeEngine:
    bridge = get_vector_bridge()
    pipeline = get_vector_pipeline()
    vctx = bridge.text_to_vector("设计一个高并发消息系统")

    ctx_before = vctx.snapshot()
    material_delta = vectorize_stage_output("perceive", materials_text, ctx_before.vector)
    vctx.update("perceive", material_delta)

    stage_context = bridge.extract_stage_context(vctx, pipeline.stage_map["cognize"])
    intent_delta = vectorize_stage_output("cognize", intent_text, vctx.vector)
    vctx.update("cognize", intent_delta)

    compact = bridge.vector_to_text(vctx)
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

# ═══ Constants ═══

DEFAULT_VECTOR_DIM: int = 768
VECTOR_CONTEXT_STAGE_ORDER: list[str] = [
    "perceive", "cognize", "ontogrow", "plan",
    "simulate", "execute", "reflect", "evolve",
]
STAGE_INDEX_MAP: dict[str, int] = {
    name: idx for idx, name in enumerate(VECTOR_CONTEXT_STAGE_ORDER)
}


# ═══ VectorContext ═══

@dataclass
class VectorContext:
    """A 768-dim L2-normalized embedding vector that evolves through the pipeline.

    The vector is the living context — each stage adds its contribution as
    a weighted delta, and the accumulator maintains L2 normalization so
    direction (not magnitude) encodes semantic information.

    Attributes:
        vector: L2-normalized 768-dim embedding.
        dimension: Embedding dimension (default 768).
        stage_weights: Per-stage contribution weights.
        updates: Log of {stage, magnitude, direction_cosine}.
        metadata: Optional text metadata for inspection/debug.
        created_at: Creation timestamp (time.time()).
        updated_at: Last update timestamp (time.time()).
    """
    vector: list[float]
    dimension: int = DEFAULT_VECTOR_DIM
    stage_weights: dict[str, float] = field(default_factory=dict)
    updates: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def update(
        self, stage_name: str, delta_vector: list[float], weight: float = 1.0
    ) -> float:
        """Add weighted delta to the current vector, L2-normalize, log the update.

        Args:
            stage_name: Name of the pipeline stage contributing this delta.
            delta_vector: The delta to add (should be same dimension).
            weight: Contribution weight (1.0 = full, 0.0 = ignored).

        Returns:
            Cosine similarity between previous vector and the new vector.
            1.0 = no change, 0.0 = completely different direction.
        """
        if len(delta_vector) != self.dimension:
            raise ValueError(
                f"delta_vector dim {len(delta_vector)} != {self.dimension}"
            )
        prev_vector = list(self.vector)
        clamped_weight = max(0.0, min(weight, 2.0))
        for i in range(self.dimension):
            self.vector[i] += delta_vector[i] * clamped_weight
        self._l2_normalize_inplace()
        delta_magnitude = _l2_norm(delta_vector)
        direction_cosine = _cosine_similarity(prev_vector, self.vector)
        self.stage_weights[stage_name] = (
            self.stage_weights.get(stage_name, 0.0) + clamped_weight
        )
        self.updates.append({
            "stage": stage_name,
            "magnitude": round(delta_magnitude, 6),
            "direction_cosine": round(direction_cosine, 6),
            "weight": clamped_weight,
        })
        self.metadata.setdefault("_stage_vectors", {})[stage_name] = list(
            self.vector
        )
        self.updated_at = time.time()
        logger.debug(
            "VectorContext: stage={} delta_mag={:.4f} cos={:.4f} updates={}",
            stage_name, delta_magnitude, direction_cosine, len(self.updates),
        )
        return direction_cosine

    def cosine_similarity(self, other: VectorContext) -> float:
        """Compute cosine similarity between this vector and another VectorContext."""
        return _cosine_similarity(self.vector, other.vector)

    def snapshot(self) -> VectorContext:
        """Return a deep copy of this VectorContext."""
        import copy
        return copy.deepcopy(self)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "vector": self.vector,
            "dimension": self.dimension,
            "stage_weights": dict(self.stage_weights),
            "updates": list(self.updates),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VectorContext:
        """Deserialize from a JSON-compatible dictionary."""
        return cls(
            vector=list(data.get("vector", [])),
            dimension=data.get("dimension", DEFAULT_VECTOR_DIM),
            stage_weights=dict(data.get("stage_weights", {})),
            updates=list(data.get("updates", [])),
            metadata=dict(data.get("metadata", {})),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )

    def attend_to_depth(
        self, query_vector: list[float] | None = None,
        stage_index: int | None = None,
    ) -> dict[str, Any]:
        """MoDA joint sequence+depth attention over all prior stage vectors.

        Computes joint softmax attention where the query (current stage's
        content or the current vector) attends to historical depth vectors
        stored in metadata['_stage_vectors'], recovering diluted information
        from early pipeline stages.

        Args:
            query_vector: Query to attend with (defaults to self.vector).
            stage_index: Current pipeline stage index for filtering prior stages.

        Returns:
            Dict with fused_vector, attention_weights, top_depth_stages,
            preservation_score, fidelity_delta.
        """
        q = query_vector if query_vector is not None else list(self.vector)
        stage_vecs = self.metadata.get("_stage_vectors", {})
        prior_stages = [
            s for s in VECTOR_CONTEXT_STAGE_ORDER
            if s in stage_vecs
            and (stage_index is None or STAGE_INDEX_MAP.get(s, 99) < stage_index)
        ]
        if not prior_stages:
            return {
                "fused_vector": list(q),
                "attention_weights": {"sequence": 1.0},
                "top_depth_stages": [],
                "preservation_score": 0.0,
                "fidelity_delta": 0.0,
            }
        depth_vecs = [stage_vecs[s] for s in prior_stages]
        seq_sim = 1.0
        depth_sims = [_cosine_similarity(q, dv) for dv in depth_vecs]
        all_logits = [seq_sim / 1.0] + [
            sim / 1.0 * (0.95 ** (len(prior_stages) - 1 - i))
            for i, sim in enumerate(depth_sims)
        ]
        max_logit = max(all_logits)
        exps = [math.exp(z - max_logit) for z in all_logits]
        total = sum(exps)
        weights = [e / total for e in exps] if total > 0 else [1.0 / len(all_logits)] * len(all_logits)
        seq_weight = weights[0]
        depth_weights = weights[1:]
        dim = len(q)
        fused = [0.0] * dim
        for j in range(dim):
            fused[j] += seq_weight * q[j]
            for k, dv in enumerate(depth_vecs):
                if k < len(depth_weights):
                    fused[j] += depth_weights[k] * dv[j]
        fused = _l2_normalize(fused)
        depth_sim_dict = dict(zip(prior_stages, depth_sims))
        attn_dict = {"sequence": seq_weight}
        attn_dict.update(dict(zip(prior_stages, depth_weights)))
        indexed = sorted(enumerate(depth_weights), key=lambda x: -x[1])
        top_depth = [prior_stages[i] for i, _ in indexed[:3]]
        pres = (
            sum(s * w for s, w in zip(depth_sims, depth_weights)) / max(sum(depth_weights), 1e-12)
            if depth_weights else 0.0
        )
        fid_delta = _cosine_similarity(q, fused) - 1.0
        return {
            "fused_vector": fused,
            "attention_weights": attn_dict,
            "top_depth_stages": top_depth,
            "preservation_score": pres,
            "fidelity_delta": fid_delta,
            "sequence_weight": seq_weight,
            "depth_total_weight": sum(depth_weights),
        }

    def update_with_moda(
        self, stage_name: str, delta_vector: list[float],
        weight: float = 1.0, stage_index: int | None = None,
    ) -> tuple[float, dict[str, Any]]:
        """Update with MoDA joint attention, recovering diluted info from prior stages.

        Unlike plain update(), this method computes joint attention over
        the new delta AND all prior stage vectors, producing a fused output
        that preserves information from early pipeline stages.

        Args:
            stage_name: Current pipeline stage name.
            delta_vector: New delta contributed by this stage.
            weight: Contribution weight (1.0 = full).
            stage_index: Optional stage index override.

        Returns:
            Tuple of (cosine_similarity, moda_attention_result_dict).
        """
        prev_snapshot = self.snapshot()
        plain_result = self.update(stage_name, delta_vector, weight)
        moda_result = self.attend_to_depth(
            query_vector=prev_snapshot.vector,
            stage_index=stage_index,
        )
        if moda_result.get("top_depth_stages"):
            combined = [0.7 * v + 0.3 * m for v, m in zip(
                self.vector, moda_result["fused_vector"])]
            self.vector = _l2_normalize(combined)
            self.metadata.setdefault("_moda_enhanced", []).append(stage_name)
        return plain_result, moda_result

    def preservation_fidelity(self) -> dict[str, Any]:
        """Compute information preservation metrics across all prior stages.

        Returns a dict with cumulative_degradation, degrading_stages,
        and per-stage preservation scores.
        """
        stage_vecs = self.metadata.get("_stage_vectors", {})
        if len(stage_vecs) < 2:
            return {"cumulative_degradation": 0.0, "degrading_stages": [], "scores": {}}
        stages_in_order = [s for s in VECTOR_CONTEXT_STAGE_ORDER if s in stage_vecs]
        scores: dict[str, float] = {}
        for i, stage in enumerate(stages_in_order):
            if i == 0:
                scores[stage] = 1.0
            else:
                scores[stage] = _cosine_similarity(
                    stage_vecs[stages_in_order[0]], stage_vecs[stage]
                )
        degrading = [s for s, v in scores.items() if v < 0.3] if scores else []
        cumulative = 1.0 - (sum(scores.values()) / max(len(scores), 1))
        return {
            "cumulative_degradation": cumulative,
            "degrading_stages": degrading,
            "scores": scores,
        }

    def _l2_normalize_inplace(self) -> None:
        norm = _l2_norm(self.vector)
        if norm < 1e-12:
            self.vector = [0.0] * self.dimension
            return
        self.vector = [v / norm for v in self.vector]

    def __repr__(self) -> str:
        n_updates = len(self.updates)
        dominant = self._dominant_stage() if self.stage_weights else "none"
        return (
            f"VectorContext(dim={self.dimension}, updates={n_updates}, "
            f"dominant={dominant})"
        )

    def _dominant_stage(self) -> str:
        if not self.stage_weights:
            return "none"
        return max(self.stage_weights, key=lambda k: self.stage_weights[k])


# ═══ VectorBridge — Text ↔ Vector Conversion ═══

class VectorBridge:
    """Bidirectional text ↔ vector conversion without LLM calls.

    Uses hash-based deterministic embedding — consistent with the project's
    EmbeddingScorer / text_to_embedding pattern. Tokenize → hash each token →
    accumulate at hash(token) % dim with weight = 1 + log(freq). L2 normalize.
    """

    def __init__(self, dim: int = DEFAULT_VECTOR_DIM) -> None:
        self.dim = dim

    def text_to_vector(self, text: str) -> VectorContext:
        """Convert arbitrary text into a VectorContext with hash-based embedding.

        Deterministic and fast — no LLM call. Same input always produces
        the same vector.

        Args:
            text: The raw text to embed.

        Returns:
            VectorContext with the L2-normalized embedding.
        """
        vec = self._hash_embed(text)
        return VectorContext(vector=vec, dimension=self.dim)

    def vector_to_text(
        self, vector_ctx: VectorContext, consciousness: Any = None
    ) -> str:
        """Decompose the vector into a structured natural language summary.

        The output contains:
        - Number of stages processed
        - Dominant stage (highest contribution weight)
        - Overall vector magnitude (processing depth)
        - Latest stage's direction cosine (how much it changed the vector)
        - Distribution of stage weights

        This compact form is suitable for LLM system prompt injection without
        requiring the LLM to decode the raw vector.

        Args:
            vector_ctx: The accumulated VectorContext.
            consciousness: Optional consciousness for enhanced summary (unused
                           in base implementation; reserved for subclass hooks).

        Returns:
            Compact natural language string describing the vector context.
        """
        vctx = vector_ctx
        n_stages = len(vctx.updates)
        dominant = vctx._dominant_stage()
        magnitude = _l2_norm(vctx.vector)
        total_weight = sum(vctx.stage_weights.values()) or 1.0
        weight_parts = []
        for stage_name in VECTOR_CONTEXT_STAGE_ORDER:
            if stage_name in vctx.stage_weights:
                pct = round(vctx.stage_weights[stage_name] / total_weight * 100)
                weight_parts.append(f"{stage_name}:{pct}%")
        weight_str = ", ".join(weight_parts[:5]) if weight_parts else "none"
        latest_dir = ""
        if vctx.updates:
            last = vctx.updates[-1]
            latest_dir = f"; trending toward: {last['stage']} (cos={last['direction_cosine']:.3f})"
        summary = (
            f"[[vector_ctx: stages={n_stages} depth={magnitude:.2f} "
            f"dominate={dominant}{latest_dir}]][[weights: {weight_str}]]"
        )
        return summary

    def extract_stage_context(
        self, vector_ctx: VectorContext, stage_index: int, consciousness: Any = None
    ) -> str:
        """Extract context from stages preceding the given stage_index.

        Builds a summary that answers: "what has the pipeline learned
        so far before stage {stage_index}?" Uses only the updates from
        stages with indices < stage_index.

        Args:
            vector_ctx: The accumulated VectorContext.
            stage_index: Index of the current stage (0-7).
            consciousness: Optional consciousness for enhanced extraction.

        Returns:
            A compact string describing the context accumulated so far,
            suitable for injection into the LLM system prompt.
        """
        idx_to_name = {v: k for k, v in STAGE_INDEX_MAP.items()}
        prior_stages = [
            update for update in vector_ctx.updates
            if update["stage"] in STAGE_INDEX_MAP
            and STAGE_INDEX_MAP[update["stage"]] < stage_index
        ]
        if not prior_stages:
            stage_name = idx_to_name.get(stage_index, f"stage_{stage_index}")
            return f"[[context: no prior stages before {stage_name}]]"
        prior_names = [u["stage"] for u in prior_stages]
        unique_priors = list(dict.fromkeys(prior_names))
        total_delta_mag = sum(
            vector_ctx.stage_weights.get(s, 0.0) for s in unique_priors
        )
        dominant_prior = max(
            unique_priors,
            key=lambda s: vector_ctx.stage_weights.get(s, 0.0),
        ) if unique_priors else "none"
        stage_name = idx_to_name.get(stage_index, f"stage_{stage_index}")
        return (
            f"[[stage_context: entering {stage_name}; prior stages={unique_priors}; "
            f"dominant={dominant_prior}; accumulated_weight={total_delta_mag:.2f}]]"
        )

    # ═══ Internal Helpers ═══

    def _hash_embed(self, text: str) -> list[float]:
        """Deterministic hash-based embedding consistent with EmbeddingScorer pattern.

        Tokenize on non-alphanumeric → hash each token → accumulate at
        hash(token) mod dim with weight = 1 + log(freq). L2 normalize.
        """
        tokens: list[str] = re.findall(r"[a-z0-9\u4e00-\u9fff]+", text.lower())
        vec = [0.0] * self.dim
        if not tokens:
            return vec
        freqs: dict[str, int] = {}
        for t in tokens:
            freqs[t] = freqs.get(t, 0) + 1
        for t, freq in freqs.items():
            idx = abs(hash(t)) % self.dim
            weight = 1.0 + math.log(float(freq))
            vec[idx] += weight
        return _l2_normalize(vec)


# ═══ VectorPipeline — Stage Execution on Vectors ═══

class VectorPipeline:
    """Manages the 8-stage vector pipeline and cumulative vector tracking.

    Provides utilities to:
    - Map stage names to pipeline indices
    - Extract the cumulative vector state as of any stage
    - Compute per-stage deltas
    - Compress the full vector into a compact text summary
    """

    stage_map: dict[str, int] = STAGE_INDEX_MAP

    def get_cumulative_vector(
        self, vctx: VectorContext, up_to_stage: str
    ) -> list[float]:
        """Return the vector state as it was after the specified stage.

        Uses snapshots stored in metadata['_stage_vectors'] (written by
        VectorContext.update()). If no snapshot exists for the stage, scans
        backwards through the update log to find the nearest saved snapshot.

        Args:
            vctx: The fully accumulated VectorContext.
            up_to_stage: Stage name to cumulate through (inclusive).

        Returns:
            L2-normalized vector snapshot as it was after the given stage,
            or a zero vector if no snapshot is available.
        """
        if up_to_stage not in self.stage_map:
            raise KeyError(
                f"Unknown stage '{up_to_stage}'. Valid: {list(self.stage_map)}"
            )
        stage_vectors = vctx.metadata.get("_stage_vectors", {})
        if up_to_stage in stage_vectors:
            return list(stage_vectors[up_to_stage])
        target_index = self.stage_map[up_to_stage]
        for idx in range(target_index, -1, -1):
            stage_name = None
            for k, v in self.stage_map.items():
                if v == idx:
                    stage_name = k
                    break
            if stage_name and stage_name in stage_vectors:
                return list(stage_vectors[stage_name])
        return [0.0] * vctx.dimension

    def compute_stage_delta(
        self, before_vec: list[float], after_vec: list[float]
    ) -> list[float]:
        """Compute the delta vector contributed by a stage.

        Args:
            before_vec: The vector before the stage executed.
            after_vec: The vector after the stage executed.

        Returns:
            Element-wise difference (after - before).
        """
        if len(before_vec) != len(after_vec):
            raise ValueError(
                f"Dimension mismatch: {len(before_vec)} vs {len(after_vec)}"
            )
        return [a - b for a, b in zip(after_vec, before_vec)]

    def compress_to_text(
        self, vctx: VectorContext, max_chars: int = 500
    ) -> str:
        """Compress the full 768-dim vector into a compact text summary.

        THE KEY METHOD for fitting vector state into LLM context windows.
        Uses:
        - Top-k dimension indices by magnitude → which semantic dimensions are "hot"
        - Stage weight proportions → "perceive:30%, cognize:25%, plan:45%"
        - Overall vector magnitude → "processing depth: 0.73"
        - Direction of last delta → "latest thinking shifted toward: execution"

        Args:
            vctx: The accumulated VectorContext.
            max_chars: Target maximum character count (approximate).

        Returns:
            Compact string like:
            "[[vector_ctx: stages=8 depth=0.73 dominate=plan; execute trending]]"
        """
        vec = vctx.vector
        top_k = 5
        indexed = sorted(
            enumerate(vec), key=lambda x: abs(x[1]), reverse=True
        )[:top_k]
        hot_dims = ",".join(f"d{i}" for i, _ in indexed)
        magnitude = _l2_norm(vec)
        dominant = vctx._dominant_stage()
        n_stages = len(vctx.updates)
        latest_trend = ""
        if vctx.updates:
            last = vctx.updates[-1]
            latest_trend = f"; {last['stage']} trending"

        fidelity = vctx.preservation_fidelity()
        fidelity_str = ""
        if fidelity["cumulative_degradation"] > 0.1:
            fidelity_str = f" degrade={fidelity['cumulative_degradation']:.2f}"

        total_weight = sum(vctx.stage_weights.values()) or 1.0
        weight_parts = []
        for s in VECTOR_CONTEXT_STAGE_ORDER:
            if s in vctx.stage_weights:
                pct = int(vctx.stage_weights[s] / total_weight * 100)
                weight_parts.append(f"{s[:3]}{pct}")
        weight_str = ",".join(weight_parts[:5])
        result = (
            f"[[vector_ctx: stages={n_stages} depth={magnitude:.2f} "
            f"dominate={dominant}{latest_trend}{fidelity_str}]][[hot:{hot_dims}]][[w:{weight_str}]]"
        )
        if len(result) > max_chars:
            return (
                f"[[vector_ctx: s={n_stages} d={magnitude:.2f} "
                f"dom={dominant}{latest_trend}{fidelity_str}]]"
            )
        return result

    def cross_depth_attend(
        self, vctx: VectorContext, target_stage: str | None = None,
    ) -> dict[str, Any]:
        """MoDA cross-depth attention: recover information from prior stages.

        Uses the current vector as query to attend to all prior stage
        snapshots, producing a fused vector that preserves diluted features.

        Args:
            vctx: The accumulated VectorContext.
            target_stage: Optional stage to recover from (if None, attends to all).

        Returns:
            MoDA attention result dict with fused_vector and diagnostics.
        """
        tgt_idx = STAGE_INDEX_MAP.get(target_stage, len(VECTOR_CONTEXT_STAGE_ORDER)) if target_stage else None
        return vctx.attend_to_depth(stage_index=tgt_idx)

# ═══ StageVectorizer — Stage Output to Vector Delta ═══

class StageVectorizer:
    """Converts each LifeEngine stage's text output into a vector delta.

    Each stage produces text output. This class hash-embeds that text
    and subtracts the input vector to produce a delta representing what
    the stage contributed.

    Usage:
        vectorizer = StageVectorizer()
        delta = vectorizer.vectorize_stage_output(
            "perceive", stage_text, input_vector
        )
        quality = vectorizer.compute_delta_quality(delta)
    """

    def __init__(self, dim: int = DEFAULT_VECTOR_DIM) -> None:
        self.dim = dim

    def vectorize_stage_output(
        self,
        stage_name: str,
        stage_output_text: str,
        input_vector: list[float],
    ) -> list[float]:
        """Convert a stage's text output into a vector delta.

        Algorithm: hash-embed the stage output text → subtract the
        input_vector (the state before this stage) → result is the delta
        contributed by this stage.

        Args:
            stage_name: Name of the pipeline stage (for logging).
            stage_output_text: The text output produced by the stage.
            input_vector: The vector state before this stage executed.

        Returns:
            Delta vector (stage_output_embedding - input_vector), representing
            what new information this stage contributed.
        """
        if not stage_output_text or not stage_output_text.strip():
            logger.debug(
                "StageVectorizer: stage={} empty output, returning zero delta",
                stage_name,
            )
            return [0.0] * self.dim
        output_vec = self._hash_embed(stage_output_text)
        if len(output_vec) != len(input_vector):
            raise ValueError(
                f"Dimension mismatch: output {len(output_vec)} vs input {len(input_vector)}"
            )
        delta = [o - i for o, i in zip(output_vec, input_vector)]
        quality = self.compute_delta_quality(delta)
        logger.debug(
            "StageVectorizer: stage={} delta_quality={:.4f} text_len={}",
            stage_name, quality, len(stage_output_text),
        )
        return delta

    def compute_delta_quality(self, delta: list[float]) -> float:
        """Measure how much information the delta adds (L2 norm of delta).

        High quality (> 0.3): stage contributed significant new information.
        Low quality (< 0.1): stage added little — may indicate redundancy
        or a stage that can be optimized/skipped.

        Args:
            delta: The delta vector to evaluate.

        Returns:
            L2 norm of the delta (0.0 = no contribution, higher = more info).
        """
        return _l2_norm(delta)

    def vectorize_stage_output_async(
        self,
        stage_name: str,
        stage_output_text: str,
        input_vector: list[float],
    ) -> list[float]:
        """Async-compatible wrapper (delegates to sync implementation).

        In a future version, this could use async LLM-based embedding.
        For now, hash-based embedding is instant and sync-only.
        """
        return self.vectorize_stage_output(stage_name, stage_output_text, input_vector)

    # ═══ Internal Helpers ═══

    def _hash_embed(self, text: str) -> list[float]:
        tokens: list[str] = re.findall(r"[a-z0-9\u4e00-\u9fff]+", text.lower())
        vec = [0.0] * self.dim
        if not tokens:
            return vec
        freqs: dict[str, int] = {}
        for t in tokens:
            freqs[t] = freqs.get(t, 0) + 1
        for t, freq in freqs.items():
            idx = abs(hash(t)) % self.dim
            weight = 1.0 + math.log(float(freq))
            vec[idx] += weight
        return _l2_normalize(vec)


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


# ═══ Singletons ═══

_pipeline: VectorPipeline | None = None
_bridge: VectorBridge | None = None
_vectorizer: StageVectorizer | None = None


def get_vector_pipeline() -> VectorPipeline:
    """Return the global singleton VectorPipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = VectorPipeline()
        logger.info("VectorPipeline singleton initialized")
    return _pipeline


def get_vector_bridge(dim: int = DEFAULT_VECTOR_DIM) -> VectorBridge:
    """Return the global singleton VectorBridge instance.

    The first call creates the instance with the given dim.
    Subsequent calls return the same instance, ignoring any new parameters.
    """
    global _bridge
    if _bridge is None:
        _bridge = VectorBridge(dim=dim)
        logger.info("VectorBridge singleton initialized (dim={})", dim)
    return _bridge


def get_stage_vectorizer(dim: int = DEFAULT_VECTOR_DIM) -> StageVectorizer:
    """Return the global singleton StageVectorizer instance."""
    global _vectorizer
    if _vectorizer is None:
        _vectorizer = StageVectorizer(dim=dim)
        logger.info("StageVectorizer singleton initialized (dim={})", dim)
    return _vectorizer


# ═══ Convenience: Standalone hash embed (consistent with task_vector_geometry) ═══

def text_to_vector(text: str, dim: int = DEFAULT_VECTOR_DIM) -> list[float]:
    """Convert arbitrary text to a fixed-dim hash-based embedding vector.

    Uses the same reproducible hash-based TF weighting as VectorBridge._hash_embed,
    but as a standalone function with no class dependency.

    Args:
        text: Input text to embed.
        dim: Embedding dimension (default 768).

    Returns:
        L2-normalized embedding vector of length dim.
    """
    tokens: list[str] = re.findall(r"[a-z0-9\u4e00-\u9fff]+", text.lower())
    vec = [0.0] * dim
    if not tokens:
        return vec
    freqs: dict[str, int] = {}
    for t in tokens:
        freqs[t] = freqs.get(t, 0) + 1
    for t, freq in freqs.items():
        idx = abs(hash(t)) % dim
        weight = 1.0 + math.log(float(freq))
        vec[idx] += weight
    return _l2_normalize(vec)


# ═══ Convenience: vectorize_stage_output standalone ═══

def vectorize_stage_output(
    stage_name: str,
    stage_output_text: str,
    input_vector: list[float],
    dim: int = DEFAULT_VECTOR_DIM,
) -> list[float]:
    """Standalone function to convert a stage's text output into a vector delta.

    Equivalent to get_stage_vectorizer().vectorize_stage_output(...).
    """
    return get_stage_vectorizer(dim).vectorize_stage_output(
        stage_name, stage_output_text, input_vector,
    )


def compute_delta_quality(delta: list[float]) -> float:
    """Standalone function: measure how much information a delta adds.

    Equivalent to get_stage_vectorizer().compute_delta_quality(delta).
    """
    return _l2_norm(delta)


__all__ = [
    "VectorContext",
    "VectorBridge",
    "VectorPipeline",
    "StageVectorizer",
    "get_vector_pipeline",
    "get_vector_bridge",
    "get_stage_vectorizer",
    "text_to_vector",
    "vectorize_stage_output",
    "compute_delta_quality",
    "DEFAULT_VECTOR_DIM",
    "VECTOR_CONTEXT_STAGE_ORDER",
    "STAGE_INDEX_MAP",
]
