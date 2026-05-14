"""Order-Aware Reranker — re-rank RRF-fused candidates by sequential coherence.

OKH-RAG (arXiv:2604.12185) integration layer:
  - Takes RRF-merged candidates (unordered set of facts)
  - Uses PrecedenceModel to score candidates by their expected position
    in the reasoning trajectory
  - Blends order score with content relevance for final ranking

Integration point: KnowledgeBase.multi_source_retrieve() → after RRF fusion,
before returning to caller. This adds order-awareness as a post-fusion
reranking step without changing the existing fusion logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from .precedence_model import PrecedenceModel, PrecedenceResult, get_precedence_model


@dataclass
class OrderAwareScore:
    """Per-document order-aware scoring result."""
    doc_id: str
    content_relevance: float       # Original RRF/reranker score (0-1)
    order_score: float             # How well this doc fits its expected position (0-1)
    position_penalty: float        # Penalty for being out of expected order (0-1, 0=best)
    combined: float                # Final blended score
    expected_position: int         # Where in the reasoning chain this should appear
    doc_type: str                  # Inferred document/fact type


@dataclass 
class OrderAwareRerankResult:
    """Complete order-aware reranking result."""
    query: str
    query_types: list[str]         # Decomposed query types for sequence inference
    inferred_order: PrecedenceResult | None  # Inferred optimal ordering
    scored_docs: list[OrderAwareScore]       # Scored documents
    reranked_docs: list[Any]                 # Reranked documents (same type as input)
    order_confidence: float                  # Confidence in the inferred order (0-1)


class OrderAwareReranker:
    """Re-rank candidates by sequential coherence using OKH-RAG approach.

    Two-phase processing:
      1. Type Inference: Map each document to a fact type (e.g., "definition",
         "threshold", "procedure") based on content patterns
      2. Order Scoring: Use PrecedenceModel to score documents by how well they
         fit their expected position in the reasoning chain

    Integration:
      order_reranker = OrderAwareReranker()
      scored_docs = order_reranker.rerank(candidates, query)
      # scored_docs are re-sorted by (relevance × 0.7 + order × 0.3)
    """

    # Fact type patterns: content regex → inferred type
    FACT_TYPE_PATTERNS: dict[str, list[str]] = {
        "definition": ["定义", "是指", "是指", "definition", "概念", "concept"],
        "threshold": ["限值", "阈值", "标准值", "threshold", "limit", "≤", "≥", "mg/m³", "μg/m³"],
        "procedure": ["步骤", "流程", "方法", "procedure", "method", "操作", "protocol"],
        "regulation": ["标准", "法规", "规范", "regulation", "standard", "GB", "HJ", "条例"],
        "data_observation": ["监测", "检测", "数据", "measurement", "observation", "实测"],
        "analysis_result": ["分析", "结果", "结论", "analysis", "result", "finding", "显示"],
        "requirement": ["要求", "应当", "必须", "shall", "must", "require", "需要"],
        "background": ["背景", "概述", "简介", "background", "introduction", "overview"],
        "mitigation": ["措施", "减缓", "治理", "mitigation", "control", "对策", "削减"],
        "conclusion": ["总结", "结论", "建议", "conclusion", "summary", "recommendation"],
    }

    ALIBI_SLOPES: dict[str, float] = {
        "definition": 0.5,
        "background": 0.25,
        "threshold": 0.125,
        "requirement": 0.125,
        "procedure": 0.0625,
        "mitigation": 0.0625,
        "regulation": 0.03125,
        "data_observation": 0.015625,
        "analysis_result": 0.015625,
        "conclusion": 0.0078125,
        "general": 0.0625,
    }

    def __init__(self, model: PrecedenceModel | None = None):
        self._model = model or get_precedence_model()

    # ── Type Inference ──

    def infer_doc_type(self, content: str) -> str:
        """Infer the fact type of a document by content pattern matching.

        Falls back to "general" if no strong match.
        """
        content_lower = content.lower()
        scores: dict[str, int] = {}
        for doc_type, patterns in self.FACT_TYPE_PATTERNS.items():
            score = sum(1 for p in patterns if p.lower() in content_lower)
            if score > 0:
                scores[doc_type] = score
        if scores:
            return max(scores, key=scores.get)
        return "general"

    def infer_query_types(self, query: str) -> list[str]:
        """Decompose query into expected fact type sequence.

        Uses heuristic: extract key intent words and map to types.
        """
        query_lower = query.lower()
        types_found = []

        # Order-sensitive type detection
        detection_order = [
            ("背景", "background"), ("概述", "background"),
            ("标准", "regulation"), ("法规", "regulation"),
            ("限值", "threshold"), ("阈值", "threshold"),
            ("监测", "data_observation"), ("检测", "data_observation"),
            ("分析", "analysis_result"), ("评估", "analysis_result"),
            ("措施", "mitigation"), ("减缓", "mitigation"),
            ("步骤", "procedure"), ("流程", "procedure"), ("方法", "procedure"),
            ("要求", "requirement"),
            ("结论", "conclusion"), ("总结", "conclusion"),
        ]
        for keyword, doc_type in detection_order:
            if keyword in query_lower and doc_type not in types_found:
                types_found.append(doc_type)

        return types_found if types_found else ["general"]

    # ── Reranking ──

    def rerank(
        self,
        candidates: list[Any],
        query: str,
        blend_weight: float = 0.3,      # Weight for order score vs relevance
        min_order_confidence: float = 0.3,
    ) -> OrderAwareRerankResult:
        """Rerank candidates by sequential coherence.

        Args:
            candidates: Documents/ScoredResult objects with .content and .final_score
            query: Original user query
            blend_weight: How much to weight order score (0 = pure relevance)
            min_order_confidence: Minimum order inference confidence to apply rerank

        Returns:
            OrderAwareRerankResult with reranked docs and scoring details
        """
        if not candidates:
            return OrderAwareRerankResult(
                query=query, query_types=[], inferred_order=None,
                scored_docs=[], reranked_docs=[], order_confidence=0.0,
            )

        # Phase 1: Infer expected order from query
        query_types = self.infer_query_types(query)
        inferred_order = None
        order_mapping: dict[str, int] = {}  # type → expected position

        if len(query_types) >= 2:
            inferred_order = self._model.order_facts(query_types)
            for i, t in enumerate(inferred_order.ordered_types):
                order_mapping[t] = i

        order_confidence = inferred_order.total_score if inferred_order else 0.0

        # Phase 2: Score each document
        scored_docs: list[OrderAwareScore] = []
        for i, doc in enumerate(candidates):
            # Extract content and relevance score
            content = getattr(doc, "content", "") or getattr(doc, "document", "") or ""
            if hasattr(content, "content"):
                content = content.content
            content_str = str(content) if content else ""

            relevance = getattr(doc, "final_score", None)
            if relevance is None:
                relevance = getattr(doc, "score", 0.5)
            if relevance is None:
                relevance = 0.5

            # Infer document type
            doc_type = self.infer_doc_type(content_str)

            # Compute order score
            if order_confidence >= min_order_confidence and doc_type in order_mapping:
                expected_pos = order_mapping[doc_type]
                actual_pos = i
                # Position penalty: penalty grows with distance from expected
                max_pos = max(len(candidates), 1)
                pos_dist = abs(actual_pos - expected_pos) / max_pos
                slope = self.ALIBI_SLOPES.get(doc_type, 0.125)
                position_penalty = pos_dist * slope * 4.0
                order_score = 1.0 - position_penalty
            else:
                expected_pos = i
                position_penalty = 0.0
                order_score = 0.5  # Neutral

            # Blend
            relevance_weight = 1.0 - blend_weight
            combined = relevance * relevance_weight + order_score * blend_weight

            scored_docs.append(OrderAwareScore(
                doc_id=getattr(doc, "doc_id", f"doc_{i}"),
                content_relevance=round(relevance, 3),
                order_score=round(order_score, 3),
                position_penalty=round(position_penalty, 3),
                combined=round(combined, 4),
                expected_position=expected_pos,
                doc_type=doc_type,
            ))

        # Phase 3: Re-sort by combined score
        scored_pairs = list(zip(scored_docs, candidates))
        scored_pairs.sort(key=lambda x: -x[0].combined)
        scored_docs_sorted = [s for s, _ in scored_pairs]
        reranked = [d for _, d in scored_pairs]

        logger.info(
            f"OrderAwareReranker: {len(candidates)} docs → reranked "
            f"(order_confidence={order_confidence:.2f}, "
            f"types={query_types[:5]})",
        )

        return OrderAwareRerankResult(
            query=query,
            query_types=query_types,
            inferred_order=inferred_order,
            scored_docs=scored_docs_sorted,
            reranked_docs=reranked,
            order_confidence=order_confidence,
        )

    # ── Learn from sequences ──

    def learn_from_retrieved(self, docs: list[Any], query: str) -> None:
        """Learn transition probabilities from observed retrieval sequences.

        Call this after successful retrievals to improve the model over time.
        """
        types = []
        for doc in docs[:10]:
            content = getattr(doc, "content", "") or str(doc)
            doc_type = self.infer_doc_type(str(content))
            types.append(doc_type)
        if len(types) >= 2:
            self._model.observe_sequence(types)

    @property
    def model(self) -> PrecedenceModel:
        return self._model


# ═══ Singleton ═══

_order_reranker: OrderAwareReranker | None = None


def get_order_aware_reranker() -> OrderAwareReranker:
    global _order_reranker
    if _order_reranker is None:
        _order_reranker = OrderAwareReranker()
    return _order_reranker


__all__ = [
    "OrderAwareReranker", "OrderAwareScore", "OrderAwareRerankResult",
    "get_order_aware_reranker",
]
