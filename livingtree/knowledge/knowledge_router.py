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
            "avg_sources_per_query": round(
                sum(self._route_stats.values()) / max(total, 1), 1),
        }


_knowledge_router: KnowledgeRouter | None = None


def get_knowledge_router() -> KnowledgeRouter:
    global _knowledge_router
    if _knowledge_router is None:
        _knowledge_router = KnowledgeRouter()
    return _knowledge_router
