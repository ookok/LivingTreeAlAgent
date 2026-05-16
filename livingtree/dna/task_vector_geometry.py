"""Task Vector Geometry — dual-mode (ID/OOD) routing for TreeLLM layered election.

Based on: "Task Vector Geometry Underlies Dual Modes of Task Inference in Transformers"
(Yan et al., arXiv:2605.03780, 2026)

Core insight: Task vectors form a convex geometric structure in embedding space:
  - ID (In-Distribution): Query lies inside the convex hull of known task vectors →
    task is similar to previously seen types → cache best provider, skip expensive routing.
  - OOD (Out-of-Distribution): Query lies outside the convex hull →
    task is novel → explore new providers via orthogonal subspace direction.

Integration:
    geometry = get_task_geometry()
    decision = geometry.classify(query_embedding, "code")     # Route decision
    if decision.mode == "id":
        provider = decision.recommended_provider               # Fast path
    else:
        explore_dir = decision.exploration_direction            # OOD exploration
    # After response:
    geometry.add_vector(query_embedding, task_type, provider, success_rate)
"""

from __future__ import annotations

import json
import math
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══ Constants ═══

ID_SIMILARITY_THRESHOLD: float = 0.75         # Cosine similarity threshold for ID classification
CONVEX_HULL_RADIUS_FACTOR: float = 1.2        # Multiplier on avg hull radius for ID boundary
DEFAULT_DIM: int = 128                         # Task vector embedding dimension
DEFAULT_MAX_VECTORS: int = 1000                # LRU eviction cap
TOP_K_NEAREST: int = 5                         # Number of nearest neighbors for hull check
DEFAULT_TOPK: int = 3                          # Default top-k for find_nearest
VECTORS_FILE: str = ".livingtree/task_vectors.json"


# ═══ Data Types ═══


@dataclass
class TaskVector:
    """A 128-dim task type embedding with cached routing outcome.

    Each successfully routed query produces a TaskVector that captures
    the geometric relationship between the query type and the best provider.
    Together, all vectors form a convex polytope in embedding space.
    """
    id: str
    embedding: list[float]
    task_type: str             # code / reasoning / chat / search / general
    best_provider: str          # Provider that performed best for this task
    success_rate: float = 1.0   # 0-1, updated via moving average
    call_count: int = 1
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)


@dataclass
class DualModeDecision:
    """The routing decision produced by TaskVectorGeometry.classify().

    Answers two questions:
      (1) Is this query in-distribution or out-of-distribution?
      (2) What provider should we use / what direction should we explore?
    """
    mode: str                                  # "id" | "ood"
    confidence: float                          # 0-1
    nearest_vector_id: str | None = None       # Closest match (for ID)
    similarity_score: float = 0.0              # Cosine similarity to nearest vector
    convex_hull_distance: float = 0.0          # Negative = inside hull, positive = outside
    recommended_provider: str | None = None    # Cached best provider (ID only)
    exploration_direction: list[float] | None = None  # Orthogonal direction (OOD only)


# ═══ Task Vector Geometry Engine ═══


class TaskVectorGeometry:
    """Manages the convex geometric structure of task vectors for dual-mode routing.

    ID (fast path): Inside convex hull → use cached best provider → skip Layers 2-3.
    OOD (full route): Outside convex hull → explore orthogonal subspace → full layered routing.

    The convex hull is approximated via centroid + average radius of top-k nearest
    neighbors, avoiding the heavy computation of an exact N-d convex hull.
    """

    def __init__(self, dim: int = DEFAULT_DIM, max_vectors: int = DEFAULT_MAX_VECTORS) -> None:
        self.dim = dim
        self._max_vectors = max_vectors
        self._vectors: dict[str, TaskVector] = {}
        self._id_decisions: int = 0
        self._ood_decisions: int = 0
        self._load()

    # ═══ Vector CRUD ═══

    def add_vector(
        self, embedding: list[float], task_type: str,
        best_provider: str, success_rate: float = 1.0,
    ) -> TaskVector:
        """Store a new task vector and return it. LRU eviction if over capacity."""
        self._evict_if_needed()
        normalized = self._l2_normalize(embedding)
        vec_id = uuid.uuid4().hex[:12]
        tv = TaskVector(
            id=vec_id,
            embedding=normalized,
            task_type=task_type,
            best_provider=best_provider,
            success_rate=success_rate,
        )
        self._vectors[vec_id] = tv
        logger.debug("task_vector: added {} type={} provider={}", vec_id, task_type, best_provider)
        self._save()
        return tv

    def update_vector(
        self, vector_id: str, best_provider: str = "", success_rate: float = 0.0,
    ) -> TaskVector | None:
        """Update an existing task vector's stats via exponential moving average."""
        tv = self._vectors.get(vector_id)
        if tv is None:
            return None
        tv.last_seen = time.time()
        tv.call_count += 1
        if best_provider:
            tv.best_provider = best_provider
        if success_rate > 0:
            alpha = 0.2
            tv.success_rate = tv.success_rate * (1 - alpha) + success_rate * alpha
        self._save()
        return tv

    def get_vector(self, vector_id: str) -> TaskVector | None:
        """Look up a task vector by id."""
        return self._vectors.get(vector_id)

    def find_nearest(
        self, query_embedding: list[float], task_type: str = "", top_k: int = DEFAULT_TOPK,
    ) -> list[tuple[TaskVector, float]]:
        """Return top-k nearest TaskVectors by cosine similarity, sorted descending."""
        normalized = self._l2_normalize(query_embedding)
        candidates = list(self._vectors.values())
        if task_type:
            candidates = [v for v in candidates if v.task_type == task_type]
        if not candidates:
            return []
        scored = [(v, self._cosine_sim(normalized, v.embedding)) for v in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # ═══ Convex Hull Geometry ═══

    def compute_convex_hull_dist(
        self, embedding: list[float], nearest_vectors: list[TaskVector],
    ) -> float:
        """Compute normalized distance from query to the convex hull approximated by nearest vectors.

        Returns a normalized score:
          - Negative: inside hull (ID zone)
          - Zero: on hull boundary
          - Positive: outside hull (OOD zone)
        """
        if not nearest_vectors:
            return float("inf")
        normalized = self._l2_normalize(embedding)
        embeddings = [v.embedding for v in nearest_vectors]
        centroid = self._centroid(embeddings)
        avg_radius = self._avg_distance(centroid, embeddings)
        if avg_radius < 1e-12:
            query_dist = self._l2_dist(normalized, centroid)
            return query_dist if query_dist > 1e-12 else 0.0
        query_dist = self._l2_dist(normalized, centroid)
        return (query_dist - avg_radius) / avg_radius

    def is_in_distribution(
        self, query_embedding: list[float], task_type: str = "",
    ) -> DualModeDecision:
        """Determine whether a query embedding lies in-distribution (ID) or out-of-distribution (OOD).

        Algorithm:
          1. Find top-5 nearest task vectors (same task_type if specified).
          2. If max similarity >= 0.75 → ID (convex combination zone).
          3. Otherwise, compute convex hull distance:
             - distance <= 1.2 * avg_radius → ID (inside hull)
             - distance > 1.2 * avg_radius → OOD (outside hull, novel task)
        """
        nearest = self.find_nearest(query_embedding, task_type=task_type, top_k=TOP_K_NEAREST)

        if not nearest:
            self._ood_decisions += 1
            return DualModeDecision(
                mode="ood",
                confidence=1.0,
                similarity_score=0.0,
                convex_hull_distance=float("inf"),
                exploration_direction=[],
            )

        best_vec, best_sim = nearest[0]
        nearest_vectors = [v for v, _ in nearest]
        hull_dist = self.compute_convex_hull_dist(query_embedding, nearest_vectors)

        if best_sim >= ID_SIMILARITY_THRESHOLD:
            self._id_decisions += 1
            return DualModeDecision(
                mode="id",
                confidence=best_sim,
                nearest_vector_id=best_vec.id,
                similarity_score=best_sim,
                convex_hull_distance=hull_dist,
                recommended_provider=best_vec.best_provider,
            )

        if hull_dist <= CONVEX_HULL_RADIUS_FACTOR:
            self._id_decisions += 1
            return DualModeDecision(
                mode="id",
                confidence=0.5 + 0.5 * best_sim,
                nearest_vector_id=best_vec.id,
                similarity_score=best_sim,
                convex_hull_distance=hull_dist,
                recommended_provider=best_vec.best_provider,
            )

        self._ood_decisions += 1
        exploration_dir = self.get_ood_direction(query_embedding, nearest_vectors)
        return DualModeDecision(
            mode="ood",
            confidence=1.0 - best_sim,
            nearest_vector_id=best_vec.id,
            similarity_score=best_sim,
            convex_hull_distance=hull_dist,
            exploration_direction=exploration_dir,
        )

    def classify(
        self, query_embedding: list[float], task_type: str = "general",
    ) -> DualModeDecision:
        """Primary routing entry point. Short alias for is_in_distribution()."""
        return self.is_in_distribution(query_embedding, task_type=task_type)

    # ═══ OOD Exploration ═══

    def get_ood_direction(
        self, query_embedding: list[float], nearest_vectors: list[TaskVector],
    ) -> list[float]:
        """Compute the orthogonal exploration direction pointing into novel task space.

        Uses Gram-Schmidt orthogonalization: project the query onto the subspace
        spanned by the nearest vectors, then return the residual component.
        This residual points into unexplored regions — where novel providers may excel.

        Args:
            query_embedding: The normalized query embedding.
            nearest_vectors: Top-k nearest task vectors for subspace basis.

        Returns:
            A 128-dim direction vector (L2 normalized) pointing orthogonally away
            from the known task subspace. Empty list if no valid direction exists.
        """
        normalized = self._l2_normalize(query_embedding)
        if not nearest_vectors:
            return list(normalized)

        basis = [list(v.embedding) for v in nearest_vectors]
        projection = [0.0] * self.dim

        for basis_vec in basis:
            dot = self._dot(normalized, basis_vec)
            for i in range(self.dim):
                projection[i] += dot * basis_vec[i]

        residual = [normalized[i] - projection[i] for i in range(self.dim)]
        residual = self._l2_normalize(residual)
        return residual

    # ═══ Stats & Persistence ═══

    def stats(self) -> dict[str, Any]:
        """Return summary statistics for monitoring and dashboards."""
        total = self._id_decisions + self._ood_decisions
        id_ratio = self._id_decisions / max(total, 1)
        task_types: dict[str, int] = {}
        providers: dict[str, int] = {}
        avg_success = 0.0
        if self._vectors:
            for v in self._vectors.values():
                task_types[v.task_type] = task_types.get(v.task_type, 0) + 1
                providers[v.best_provider] = providers.get(v.best_provider, 0) + 1
                avg_success += v.success_rate
            avg_success /= len(self._vectors)
        return {
            "total_vectors": len(self._vectors),
            "id_decisions": self._id_decisions,
            "ood_decisions": self._ood_decisions,
            "total_decisions": total,
            "id_ratio": round(id_ratio, 4),
            "avg_success_rate": round(avg_success, 4),
            "task_type_distribution": task_types,
            "top_providers": dict(sorted(providers.items(), key=lambda x: -x[1])[:5]),
            "max_vectors": self._max_vectors,
            "dim": self.dim,
            "id_threshold": ID_SIMILARITY_THRESHOLD,
            "hull_radius_factor": CONVEX_HULL_RADIUS_FACTOR,
        }

    def save(self) -> None:
        """Persist task vectors to disk as JSON."""
        self._save()

    def _save(self) -> None:
        """Write vectors to .livingtree/task_vectors.json."""
        try:
            os.makedirs(os.path.dirname(VECTORS_FILE), exist_ok=True)
            data: list[dict[str, Any]] = []
            for v in self._vectors.values():
                data.append({
                    "id": v.id,
                    "embedding": v.embedding,
                    "task_type": v.task_type,
                    "best_provider": v.best_provider,
                    "success_rate": v.success_rate,
                    "call_count": v.call_count,
                    "created_at": v.created_at,
                    "last_seen": v.last_seen,
                })
            payload = {
                "dim": self.dim,
                "max_vectors": self._max_vectors,
                "id_decisions": self._id_decisions,
                "ood_decisions": self._ood_decisions,
                "vectors": data,
            }
            with open(VECTORS_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("task_vector: save failed: {}", e)

    def _load(self) -> None:
        """Load persisted task vectors from disk."""
        if not os.path.exists(VECTORS_FILE):
            return
        try:
            with open(VECTORS_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.dim = payload.get("dim", self.dim)
            self._max_vectors = payload.get("max_vectors", self._max_vectors)
            self._id_decisions = payload.get("id_decisions", 0)
            self._ood_decisions = payload.get("ood_decisions", 0)
            for item in payload.get("vectors", []):
                tv = TaskVector(
                    id=item["id"],
                    embedding=item["embedding"],
                    task_type=item["task_type"],
                    best_provider=item["best_provider"],
                    success_rate=item.get("success_rate", 1.0),
                    call_count=item.get("call_count", 1),
                    created_at=item.get("created_at", time.time()),
                    last_seen=item.get("last_seen", time.time()),
                )
                self._vectors[tv.id] = tv
            logger.debug("task_vector: loaded {} vectors from {}", len(self._vectors), VECTORS_FILE)
        except Exception as e:
            logger.warning("task_vector: load failed: {}", e)

    def _evict_if_needed(self) -> None:
        """Evict the least recently seen vector if over capacity."""
        if len(self._vectors) >= self._max_vectors:
            oldest = min(self._vectors.values(), key=lambda v: v.last_seen)
            del self._vectors[oldest.id]

    # ═══ Math Utilities ═══

    @staticmethod
    def _dot(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    def _l2_norm(self, vec: list[float]) -> float:
        return math.sqrt(sum(v * v for v in vec))

    def _l2_normalize(self, vec: list[float]) -> list[float]:
        norm = self._l2_norm(vec)
        if norm < 1e-12:
            return [0.0] * len(vec)
        return [v / norm for v in vec]

    def _cosine_sim(self, a: list[float], b: list[float]) -> float:
        return self._dot(a, b)

    def _l2_dist(self, a: list[float], b: list[float]) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    def _centroid(self, vectors: list[list[float]]) -> list[float]:
        if not vectors:
            return [0.0] * self.dim
        n = len(vectors)
        result = [0.0] * self.dim
        for vec in vectors:
            for i in range(self.dim):
                result[i] += vec[i]
        return [v / n for v in result]

    def _avg_distance(self, centroid: list[float], vectors: list[list[float]]) -> float:
        if not vectors:
            return 0.0
        total = sum(self._l2_dist(centroid, v) for v in vectors)
        return total / len(vectors)


# ═══ Text to Embedding (standalone, consistent with EmbeddingScorer) ═══

def text_to_embedding(text: str, dim: int = DEFAULT_DIM) -> list[float]:
    """Convert arbitrary text to a fixed-dim hash-based embedding.

    Uses the same reproducible hash-based TF weighting as EmbeddingScorer._encode(),
    but as a standalone function with no class dependency.

    Algorithm:
      - Tokenize on non-alphanumeric boundaries after lowercasing.
      - Each token contributes to dimension index = hash(token) mod dim.
      - Weight = 1 + log(freq).
      - Result is L2 normalized.

    Args:
        text: Input text to embed.
        dim: Embedding dimension (default 128).

    Returns:
        L2-normalized embedding vector of length dim.
    """
    import re
    # Match English words AND Chinese characters/sequences
    tokens: list[str] = re.findall(r"[a-z0-9]{2,}|[\u4e00-\u9fff]{1,}", text.lower())
    if not tokens:
        return [0.0] * dim
    # Add bigrams for semantic context
    bigrams = [tokens[i] + "_" + tokens[i+1] for i in range(len(tokens) - 1)]
    all_terms = tokens + bigrams
    freqs: dict[str, int] = {}
    for t in all_terms:
        freqs[t] = freqs.get(t, 0) + 1
    for t, freq in freqs.items():
        idx = abs(hash(t)) % dim
        weight = 1.0 + math.log(float(freq))
        vec[idx] += weight
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


# ═══ Singleton ═══

_geometry: TaskVectorGeometry | None = None


def get_task_geometry(dim: int = DEFAULT_DIM, max_vectors: int = DEFAULT_MAX_VECTORS) -> TaskVectorGeometry:
    """Return the global singleton TaskVectorGeometry instance.

    The first call creates the instance with the given dim and max_vectors.
    Subsequent calls return the same instance, ignoring any new parameters.
    """
    global _geometry
    if _geometry is None:
        _geometry = TaskVectorGeometry(dim=dim, max_vectors=max_vectors)
    return _geometry


__all__ = [
    "TaskVector",
    "DualModeDecision",
    "TaskVectorGeometry",
    "text_to_embedding",
    "get_task_geometry",
    "ID_SIMILARITY_THRESHOLD",
    "CONVEX_HULL_RADIUS_FACTOR",
    "DEFAULT_DIM",
    "DEFAULT_MAX_VECTORS",
]
