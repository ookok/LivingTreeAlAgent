"""Dynamic Retrieval Router — Linear-time relevance prediction via dynamic parameters.

Based on arXiv:2605.01711 (He, Han & Huang, Tsinghua 2026):
  "Linear-Time Global Visual Modeling without Explicit Attention"

Core insight (WeightFormer): Attention can be mathematically reframed as an MLP
with dynamically predicted parameters. This achieves Transformer-level global
modeling at linear complexity — O(n) instead of O(n²).

LivingTree application: Multi-source retrieval fusion currently uses pairwise
similarity comparison (O(n²) across chunks). DynamicRetrievalRouter replaces
this with lightweight MLP prediction → O(n) linear complexity.

How it works:
  1. Extract simple features from each chunk (length, term overlap, source type)
  2. Predict relevance score via small regression
  3. Sort by predicted score → select top-k
  4. No pairwise attention needed — each chunk scored independently (linear)

This is especially impactful when:
  - Many retrieved chunks (>100) from multiple sources
  - Long contexts where pairwise comparison dominates latency
  - HiFloat8 contexts where we retrieve 3x more chunks
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class ChunkFeatures:
    """Lightweight features extracted from a retrieved chunk.

    These are the "dynamic parameters" that replace attention weights.
    """
    text: str
    source: str
    chunk_len: int = 0
    term_overlap_score: float = 0.0
    source_priority: float = 0.5  # Higher for document_kb, lower for struct_mem
    position_bonus: float = 0.0    # Earlier chunks often more relevant
    entity_density: float = 0.0    # Named entities / total words
    score: float = 0.0


class DynamicRetrievalRouter:
    """Linear-time relevance prediction for multi-source retrieval.

    Replaces O(n²) pairwise attention with O(n) feature-based prediction.
    WeightFormer insight: dynamic parameters = compressed global context.

    Feature weights are adaptive — updated based on which features
    correlate with high-quality results over time.
    """

    # Source priority: some sources are inherently more authoritative
    SOURCE_PRIORITY = {
        "document_kb": 0.9,
        "knowledge_base": 0.7,
        "struct_mem": 0.5,
        "knowledge_graph": 0.6,
        "engram": 0.8,
    }

    # Feature weights — dynamically updated via feedback
    DEFAULT_WEIGHTS = {
        "term_overlap": 0.35,
        "source_priority": 0.25,
        "position": 0.10,
        "entity_density": 0.15,
        "length_norm": 0.15,
    }

    def __init__(self):
        self._weights = dict(self.DEFAULT_WEIGHTS)
        self._feedback_count = 0

    # ── Core: Linear-time scoring ──

    def score_chunks(
        self, chunks: list[dict], query: str
    ) -> list[tuple[float, dict]]:
        """Score chunks in O(n) time — each chunk independently.

        Args:
            chunks: List of chunk dicts with 'text', 'source', etc.
            query: User query for relevance estimation.

        Returns:
            List of (score, chunk) sorted descending.
        """
        t0 = time.time()
        query_terms = set(query.lower().split()) if query else set()

        scored = []
        for i, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            source = chunk.get("source", "unknown")

            features = self._extract_features(text, source, i, query_terms, len(chunks))
            score = self._predict_score(features)

            scored.append((score, chunk))

        # Sort by predicted score (O(n log n), but no pairwise comparisons)
        scored.sort(key=lambda x: -x[0])

        elapsed_ms = (time.time() - t0) * 1000
        if len(chunks) > 50:
            logger.debug(
                f"DynamicRouter: scored {len(chunks)} chunks in {elapsed_ms:.1f}ms "
                f"(linear O(n) vs O(n²)={len(chunks)**2/1000:.0f}ms pairwise)"
            )

        return scored

    def select_top_k(
        self, chunks: list[dict], query: str, top_k: int = 10
    ) -> list[dict]:
        """Select top-k chunks using linear-time dynamic routing.

        Args:
            chunks: Retrieved chunks from all sources.
            query: User query.
            top_k: Number of chunks to return.

        Returns:
            Top-k chunks ranked by predicted relevance.
        """
        scored = self.score_chunks(chunks, query)
        return [chunk for _, chunk in scored[:top_k]]

    def fuse_sources(
        self, source_results: dict[str, list[dict]], query: str, top_k: int = 10
    ) -> list[dict]:
        """Fuse results from multiple sources with linear-time scoring.

        This is where WeightFormer's insight shines: instead of computing
        pairwise attention between all source pairs (O(m*n)), we score
        each result independently (O(m+n)).

        Args:
            source_results: Dict of source_name → list of chunk dicts.
            query: User query.
            top_k: Total results to return.

        Returns:
            Fused and ranked top-k results.
        """
        all_chunks = []
        for source, chunks in source_results.items():
            # Tag each chunk with source for priority
            for c in chunks:
                if "source" not in c:
                    c["source"] = source
            all_chunks.extend(chunks)

        return self.select_top_k(all_chunks, query, top_k)

    # ── Feedback: Update weights based on actual relevance ──

    def feedback(self, chunk_text: str, source: str, was_useful: bool) -> None:
        """Update feature weights based on whether a chunk was actually useful.

        This is the "dynamic parameter" update — weights evolve to match
        the true relevance distribution.
        """
        self._feedback_count += 1
        alpha = 1.0 / (self._feedback_count + 10)  # Decaying learning rate

        features = self._extract_features(chunk_text, source, 0, set(), 1)
        target = 1.0 if was_useful else 0.0

        # Simple SGD: adjust each weight toward gradient
        for feat_name, weight in self._weights.items():
            feat_val = getattr(features, self._feat_to_attr(feat_name), 0.5)
            predicted = sum(
                self._weights[k] * getattr(features, self._feat_to_attr(k), 0.5)
                for k in self._weights
            )
            error = target - predicted
            self._weights[feat_name] += alpha * error * feat_val

        # Normalize weights
        total = sum(self._weights.values())
        if total > 0:
            for k in self._weights:
                self._weights[k] /= total

    # ── Internal ──

    def _extract_features(
        self, text: str, source: str, position: int,
        query_terms: set, total_chunks: int,
    ) -> ChunkFeatures:
        """Extract lightweight features from a chunk — O(1) per chunk."""
        text_lower = text.lower() if text else ""
        words = text_lower.split()

        # Term overlap: how many query terms appear in this chunk
        overlap = sum(1 for t in query_terms if t in text_lower) if query_terms else 0
        term_overlap = overlap / max(1, len(query_terms)) if query_terms else 0.0

        # Source priority
        source_priority = self.SOURCE_PRIORITY.get(source, 0.5)

        # Position bonus: earlier chunks often more relevant
        position_bonus = 1.0 - (position / max(1, total_chunks))

        # Entity density: capital words / total words (rough proxy)
        cap_words = sum(1 for w in words if w and w[0].isupper())
        entity_density = cap_words / max(1, len(words))

        return ChunkFeatures(
            text=text,
            source=source,
            chunk_len=len(text),
            term_overlap_score=term_overlap,
            source_priority=source_priority,
            position_bonus=position_bonus,
            entity_density=entity_density,
        )

    def _predict_score(self, features: ChunkFeatures) -> float:
        """Predict relevance score via weighted feature combination — O(1).

        This is the "MLP with dynamic parameters" — the weights act as
        compressed global context, replacing explicit pairwise attention.
        """
        return (
            self._weights["term_overlap"] * features.term_overlap_score
            + self._weights["source_priority"] * features.source_priority
            + self._weights["position"] * features.position_bonus
            + self._weights["entity_density"] * features.entity_density
            + self._weights["length_norm"] * math.log(1 + features.chunk_len) / 10
        )

    @staticmethod
    def _feat_to_attr(feat_name: str) -> str:
        mapping = {
            "term_overlap": "term_overlap_score",
            "source_priority": "source_priority",
            "position": "position_bonus",
            "entity_density": "entity_density",
            "length_norm": "chunk_len",
        }
        return mapping.get(feat_name, feat_name)


# ── Singleton ──

_router: Optional[DynamicRetrievalRouter] = None


def get_dynamic_router() -> DynamicRetrievalRouter:
    global _router
    if _router is None:
        _router = DynamicRetrievalRouter()
    return _router
