"""KnowledgeRouter — SSA-inspired content-dependent knowledge source routing.

SSA core idea: instead of computing all pairwise attention (O(n²)), select
which positions to attend to before computing. Similarly, instead of running
all 5 retrieval layers for every query, classify the query and route to the
optimal 1-2 sources.

Routing decisions:
  regulation/standard  → Engram O(1) only
  semantic/similar     → Vector only
  relationship/graph   → Graph only
  lookup/fact          → FTS5 only
  complex/multi-hop    → Engram + Vector (two source RRF fusion)
  deep research        → full pipeline (rare, explicit)

This reduces average retrieval cost from O(5 layers) to O(1-2 layers),
following the SSA principle of "only compute what matters."

Usage:
    router = get_knowledge_router()
    route = router.classify(query)
    source = route.primary_source  # "engram" | "fts5" | "vector" | "graph" | "fusion"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RouteTarget:
    source: str
    weight: float = 1.0
    max_results: int = 5

@dataclass
class RouteDecision:
    query: str
    query_type: str
    primary_source: str
    secondary_sources: list[str] = field(default_factory=list)
    confidence: float = 0.8
    reason: str = ""


class KnowledgeRouter:
    """SSA-style content-dependent knowledge source router.

    Classifies query type via keyword analysis and routes to optimal
    knowledge source(s), skipping irrelevant retrieval layers.
    """

    REGULATION_KEYWORDS = [
        "GB", "HJ", "标准", "限值", "排放", "浓度", "噪声", "dB",
        "SO2", "NO2", "PM2.5", "PM10", "CO2", "COD", "BOD",
        "环境空气", "地表水", "声环境", "环评", "EIA", "AERSCREEN",
        "大气扩散", "高斯", "烟羽", "烟团", "标准限值",
    ]
    SEMANTIC_KEYWORDS = [
        "类似", "相似", "相近", "推荐", "建议", "最佳实践",
        "best practice", "similar", "analogous", "comparable",
    ]
    GRAPH_KEYWORDS = [
        "关系", "依赖", "关联", "属于", "继承", "调用", "引用",
        "前置", "后置", "上游", "下游", "关联方",
    ]
    LOOKUP_KEYWORDS = [
        "定义", "什么是", "是多少", "查找", "查询", "定位",
        "哪个文件", "在哪", "define", "locate",
    ]
    COMPLEX_KEYWORDS = [
        "分析", "评估", "对比", "综合", "汇总", "生成报告",
        "多维度", "全面", "透彻", "深入",
    ]

    def __init__(self):
        self._route_stats: dict[str, int] = {}

    def classify(self, query: str) -> RouteDecision:
        """Classify query type and determine optimal knowledge route.

        The key SSA insight: don't compute all retrievals — route to what matters.
        """
        q = query.lower()

        regulation_score = sum(1 for kw in self.REGULATION_KEYWORDS if kw.lower() in q)
        semantic_score = sum(1 for kw in self.SEMANTIC_KEYWORDS if kw.lower() in q)
        graph_score = sum(1 for kw in self.GRAPH_KEYWORDS if kw.lower() in q)
        lookup_score = sum(1 for kw in self.LOOKUP_KEYWORDS if kw.lower() in q)
        complex_score = sum(1 for kw in self.COMPLEX_KEYWORDS if kw.lower() in q)

        is_code = bool(re.search(r'[A-Z][a-z]+\.[a-z]+\(', query))
        is_number = bool(re.search(r'\d+(\.\d+)?\s*(dB|mg|μg|km|m³|%|万元|吨)', query))
        is_formula = bool(re.search(r'[a-zA-Z]\([^)]*\)\s*=', query))

        if regulation_score >= 2 or is_number:
            route = RouteDecision(query=query, query_type="regulation",
                                   primary_source="engram",
                                   secondary_sources=["fts5"],
                                   confidence=0.9,
                                   reason="regulatory standard or numeric value query")
            self._track("engram")
        elif is_formula:
            route = RouteDecision(query=query, query_type="formula",
                                   primary_source="engram",
                                   secondary_sources=["fts5"],
                                   confidence=0.85,
                                   reason="mathematical formula lookup")
            self._track("engram")
        elif lookup_score >= 2:
            route = RouteDecision(query=query, query_type="lookup",
                                   primary_source="fts5",
                                   secondary_sources=[],
                                   confidence=0.8,
                                   reason="direct fact lookup")
            self._track("fts5")
        elif graph_score >= 2:
            route = RouteDecision(query=query, query_type="graph",
                                   primary_source="graph",
                                   secondary_sources=["fts5"],
                                   confidence=0.85,
                                   reason="relationship knowledge needed")
            self._track("graph")
        elif semantic_score >= 2:
            route = RouteDecision(query=query, query_type="semantic",
                                   primary_source="vector",
                                   secondary_sources=[],
                                   confidence=0.8,
                                   reason="semantic similarity search")
            self._track("vector")
        elif complex_score >= 3:
            route = RouteDecision(query=query, query_type="complex",
                                   primary_source="engram",
                                   secondary_sources=["vector", "fts5", "graph"],
                                   confidence=0.6,
                                   reason="complex multi-hop query — parallel fusion")
            self._track("fusion")
        else:
            route = RouteDecision(query=query, query_type="general",
                                   primary_source="engram",
                                   secondary_sources=["fts5"],
                                   confidence=0.5,
                                   reason="general query — fast lookup + text search")
            self._track("engram")

        return route

    def route(self, query: str) -> list[RouteTarget]:
        """Return ordered list of retrieval targets with weights.

        The weight determines how many results to pull from each source.
        Higher weight = more results from that source.
        """
        decision = self.classify(query)
        targets = []

        primary_weight = 0.6
        targets.append(RouteTarget(source=decision.primary_source,
                                    weight=primary_weight, max_results=5))

        total_secondary_weight = 0.4
        if decision.secondary_sources:
            per_src_weight = total_secondary_weight / len(decision.secondary_sources)
            for src in decision.secondary_sources:
                targets.append(RouteTarget(source=src, weight=per_src_weight,
                                            max_results=3))

        return targets

    def should_skip_fusion(self, query: str) -> bool:
        """SSA principle: skip fusion for simple queries. Only run fusion when needed."""
        decision = self.classify(query)
        return decision.query_type in ("regulation", "formula", "lookup")

    def _track(self, source: str):
        self._route_stats[source] = self._route_stats.get(source, 0) + 1

    def stats(self) -> dict[str, Any]:
        total = sum(self._route_stats.values())
        return {
            "total_classifications": total,
            "by_source": {k: {"count": v, "pct": round(v / max(total, 1) * 100, 1)}
                          for k, v in self._route_stats.items()},
            "active_layers": sum(1 for v in self._route_stats.values() if v > 0),
        }


_knowledge_router: KnowledgeRouter | None = None


def get_knowledge_router() -> KnowledgeRouter:
    global _knowledge_router
    if _knowledge_router is None:
        _knowledge_router = KnowledgeRouter()
    return _knowledge_router


# ═══════════════════════════════════════════════════════════════════════
# Merged from dynamic_router.py — Linear-time retrieval routing
# ═══════════════════════════════════════════════════════════════════════

import math
import time
from collections import defaultdict

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
    source_priority: float = 0.5
    position_bonus: float = 0.0
    entity_density: float = 0.0
    score: float = 0.0


class DynamicRetrievalRouter:
    """Linear-time relevance prediction for multi-source retrieval.

    Replaces O(n²) pairwise attention with O(n) feature-based prediction.
    WeightFormer insight: dynamic parameters = compressed global context.
    """

    SOURCE_PRIORITY = {
        "document_kb": 0.9,
        "knowledge_base": 0.7,
        "struct_mem": 0.5,
        "knowledge_graph": 0.6,
        "engram": 0.8,
    }

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

    def score_chunks(
        self, chunks: list[dict], query: str
    ) -> list[tuple[float, dict]]:
        t0 = time.time()
        query_terms = set(query.lower().split()) if query else set()

        scored = []
        for i, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            source = chunk.get("source", "unknown")

            features = self._extract_features(text, source, i, query_terms, len(chunks))
            score = self._predict_score(features)

            scored.append((score, chunk))

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
        scored = self.score_chunks(chunks, query)
        return [chunk for _, chunk in scored[:top_k]]

    def fuse_sources(
        self, source_results: dict[str, list[dict]], query: str, top_k: int = 10
    ) -> list[dict]:
        all_chunks = []
        for source, chunks in source_results.items():
            for c in chunks:
                if "source" not in c:
                    c["source"] = source
            all_chunks.extend(chunks)

        return self.select_top_k(all_chunks, query, top_k)

    def feedback(self, chunk_text: str, source: str, was_useful: bool) -> None:
        self._feedback_count += 1
        alpha = 1.0 / (self._feedback_count + 10)

        features = self._extract_features(chunk_text, source, 0, set(), 1)
        target = 1.0 if was_useful else 0.0

        for feat_name, weight in self._weights.items():
            feat_val = getattr(features, self._feat_to_attr(feat_name), 0.5)
            predicted = sum(
                self._weights[k] * getattr(features, self._feat_to_attr(k), 0.5)
                for k in self._weights
            )
            error = target - predicted
            self._weights[feat_name] += alpha * error * feat_val

        total = sum(self._weights.values())
        if total > 0:
            for k in self._weights:
                self._weights[k] /= total

    def _extract_features(
        self, text: str, source: str, position: int,
        query_terms: set, total_chunks: int,
    ) -> ChunkFeatures:
        text_lower = text.lower() if text else ""
        words = text_lower.split()

        overlap = sum(1 for t in query_terms if t in text_lower) if query_terms else 0
        term_overlap = overlap / max(1, len(query_terms)) if query_terms else 0.0

        source_priority = self.SOURCE_PRIORITY.get(source, 0.5)

        position_bonus = 1.0 - (position / max(1, total_chunks))

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


_dynamic_router: DynamicRetrievalRouter | None = None


def get_dynamic_router() -> DynamicRetrievalRouter:
    global _dynamic_router
    if _dynamic_router is None:
        _dynamic_router = DynamicRetrievalRouter()
    return _dynamic_router


__all__ = [
    "ChunkFeatures",
    "DynamicRetrievalRouter",
    "KnowledgeRouter",
    "RouteDecision",
    "RouteTarget",
    "get_dynamic_router",
    "get_knowledge_router",
]
