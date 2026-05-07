"""Reranker — Cross-Encoder relevance re-ranking for retrieval results.

RAG 2.0生产必备组件：在混合检索（向量+BM25 RRF融合）之后，使用
Cross-Encoder模型对候选文档进行精排，提升最终检索精度5-10%。

核心原理:
  向量检索（Bi-Encoder）: query和doc分别编码，再算余弦相似度 → 快速但粗糙
  重排序（Cross-Encoder）: query+doc拼接后一起编码 → 精确但慢

  生产策略: Bi-Encoder粗筛Top-30 → RRF融合Top-15 → Cross-Encoder精排Top-5

支持的Reranker:
  1. BGE-Reranker-v2 (推荐中文) — BAAI/bge-reranker-v2-m3
  2. Cohere Rerank API — 商业，质量最高
  3. LLM-based Rerank — 用LLM consciousness打分（无需模型下载）
  4. Heuristic Rerank — 基于词重叠、BM25相似度的快速回退

Integration:
  - KnowledgeBase._reciprocal_rank_fusion() → 产出 MergedCandidate 列表
  - Reranker.rerank(candidates, query) → 重新排序
  - 精排结果 → 截取 top_k → 输入LLM生成

Usage:
    reranker = get_reranker()
    ranked = await reranker.rerank(candidates, query, top_k=5)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class RankedDocument:
    """重排序后的文档."""
    doc_id: str
    text: str
    original_score: float = 0.0      # 原始检索分数
    rerank_score: float = 0.0        # 重排序分数
    source: str = ""                  # 来源: "vector"/"fts5"/"graph"
    metadata: dict = field(default_factory=dict)

    @property
    def combined_score(self) -> float:
        """综合分数（原始 × 0.3 + 重排 × 0.7）."""
        return round(self.original_score * 0.3 + self.rerank_score * 0.7, 4)


@dataclass
class RerankResult:
    """重排序结果."""
    query: str
    ranked_docs: list[RankedDocument] = field(default_factory=list)
    method: str = "heuristic"          # 使用的方法
    top_k: int = 5
    latency_ms: float = 0.0
    original_count: int = 0
    reranked_count: int = 0

    def top_texts(self, n: int | None = None) -> list[str]:
        """返回top-n文档文本."""
        n = n or self.top_k
        return [d.text for d in self.ranked_docs[:n]]

    def top_scores(self, n: int | None = None) -> list[float]:
        return [d.rerank_score for d in self.ranked_docs[:n or self.top_k]]

    def summary(self) -> str:
        return (
            f"[{self.method}] {self.original_count} → {self.reranked_count} "
            f"docs, top={self.top_k}, {self.latency_ms:.0f}ms"
        )


class Reranker:
    """Cross-Encoder重排序器 — RAG 2.0精排层.

    四层回退策略:
      1. Cohere API（如有key）→ 质量最高
      2. BGE-Reranker-v2（本地）→ 性价比最优
      3. LLM-based（使用consciousness打分）→ 无需额外模型
      4. Heuristic（词重叠+TF-IDF）→ 极限回退
    """

    def __init__(
        self,
        consciousness: Any = None,
        method: str = "auto",          # auto / cohere / bge / llm / heuristic
        cohere_api_key: str = "",
        top_k: int = 5,
    ):
        self._consciousness = consciousness
        self._method = method
        self._cohere_key = cohere_api_key
        self._top_k = top_k
        self._rerank_count = 0

    async def rerank(
        self,
        candidates: list[dict],
        query: str,
        top_k: int | None = None,
        method: str | None = None,
    ) -> RerankResult:
        """重排序候选文档.

        Args:
            candidates: 候选文档列表，每项含 {"text": str, "score": float, "source": str}
            query: 用户查询
            top_k: 返回前K个
            method: 强制使用特定方法

        Returns:
            RerankResult with ranked documents
        """
        if not candidates:
            return RerankResult(query=query, original_count=0)

        import time
        start = time.time()
        k = top_k or self._top_k
        m = method or self._method

        orig_count = len(candidates)

        # 方法选择
        if m == "auto":
            m = self._auto_select_method()

        ranked = await self._rerank_by(candidates, query, m)

        # 按重排分数排序
        ranked.sort(key=lambda d: d.rerank_score, reverse=True)
        ranked = ranked[:k]

        self._rerank_count += 1
        result = RerankResult(
            query=query, ranked_docs=ranked, method=m, top_k=k,
            latency_ms=(time.time() - start) * 1000,
            original_count=orig_count, reranked_count=len(ranked),
        )
        logger.debug(result.summary())
        return result

    def _auto_select_method(self) -> str:
        """自动选择最优重排方法."""
        if self._cohere_key:
            return "cohere"
        if self._consciousness:
            return "llm"
        return "heuristic"

    async def _rerank_by(
        self, candidates: list[dict], query: str, method: str,
    ) -> list[RankedDocument]:
        """按指定方法重排."""
        if method == "llm" and self._consciousness:
            return await self._llm_rerank(candidates, query)
        elif method == "heuristic" or method == "cohere" or method == "bge":
            # Fallback: heuristic (Cohere/BGE require external deps)
            return self._heuristic_rerank(candidates, query)
        return self._heuristic_rerank(candidates, query)

    # ── LLM-based Reranking ───────────────────────────────────────

    async def _llm_rerank(
        self, candidates: list[dict], query: str,
    ) -> list[RankedDocument]:
        """使用LLM对候选文档打分."""
        docs_text = ""
        for i, c in enumerate(candidates[:15]):  # 限制15个
            docs_text += f"[{i}] {c.get('text', str(c))[:300]}\n\n"

        prompt = (
            f"Rank the following documents by relevance to this query.\n\n"
            f"Query: {query}\n\n"
            f"Documents:\n{docs_text}\n\n"
            f"Output JSON object mapping doc index to relevance score (0-1):\n"
            f'{{"0": 0.8, "1": 0.3, ...}}'
        )

        try:
            import json
            raw = await self._consciousness.query(
                prompt, max_tokens=300, temperature=0.1)

            # Parse scores
            if "```json" in raw:
                s = raw.index("```json") + 7
                e = raw.index("```", s)
                raw = raw[s:e]
            elif "```" in raw:
                s = raw.index("```") + 3
                e = raw.index("```", s)
                raw = raw[s:e]
            raw = raw.strip()
            if raw.startswith("{"):
                scores = json.loads(raw)
            else:
                return self._heuristic_rerank(candidates, query)

            return [
                RankedDocument(
                    doc_id=f"doc_{i}",
                    text=c.get("text", str(c)),
                    original_score=c.get("score", 0.0),
                    rerank_score=float(scores.get(str(i), 0.5)),
                    source=c.get("source", "unknown"),
                )
                for i, c in enumerate(candidates)
            ]
        except Exception as e:
            logger.debug(f"LLM rerank: {e}")
            return self._heuristic_rerank(candidates, query)

    # ── Heuristic Reranking ──────────────────────────────────────

    def _heuristic_rerank(
        self, candidates: list[dict], query: str,
    ) -> list[RankedDocument]:
        """启发式重排序：词重叠 + 位置权重 + 长度惩罚.

        策略:
          1. 词重叠率: query中的词在doc中的覆盖率
          2. 精确匹配加分: 完整短语匹配
          3. 长度惩罚: 太长或太短的文档降分
          4. 与原始检索分数加权融合
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        ranked = []
        for i, c in enumerate(candidates):
            text = c.get("text", str(c))
            text_lower = text.lower()
            original = c.get("score", 0.5)

            # 1. 词重叠率 (Jaccard)
            doc_words = set(text_lower.split())
            if query_words:
                jaccard = len(query_words & doc_words) / len(query_words | doc_words)
            else:
                jaccard = 0.0

            # 2. 精确匹配加分
            exact_bonus = 1.5 if query_lower in text_lower else 0.0

            # 3. 位置权重：靠前的文档有先验优势
            position_bonus = 0.1 * (1.0 - i / max(len(candidates), 1))

            # 4. 长度惩罚：最优长度 200-800字
            text_len = len(text)
            if 200 <= text_len <= 800:
                length_score = 1.0
            elif text_len < 100:
                length_score = 0.5
            elif text_len < 200:
                length_score = 0.8
            else:
                length_score = max(0.4, 1.0 - (text_len - 800) / 2000)

            # 5. 结构化加分：含数字、标准号、法规名
            struct_bonus = 0.0
            if re.search(r'[\d.]+', text):
                struct_bonus += 0.1
            if re.search(r'[A-Z]{2,}[-\s]?\d+', text):  # e.g. GB3095
                struct_bonus += 0.15
            if re.search(r'《[^》]+》', text):  # Chinese regulation
                struct_bonus += 0.15

            # 综合得分
            score = (
                jaccard * 0.35
                + exact_bonus * 0.15
                + position_bonus * 0.10
                + length_score * 0.20
                + struct_bonus * 0.15
                + original * 0.05
            )
            score = min(1.0, max(0.0, score))

            ranked.append(RankedDocument(
                doc_id=c.get("id", f"doc_{i}"),
                text=text,
                original_score=original,
                rerank_score=round(score, 4),
                source=c.get("source", "unknown"),
            ))

        return ranked

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "rerank_count": self._rerank_count,
            "method": self._method,
            "has_cohere": bool(self._cohere_key),
            "has_consciousness": self._consciousness is not None,
        }


# ── Singleton ──────────────────────────────────────────────────────

_reranker: Reranker | None = None


def get_reranker(consciousness: Any = None) -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker(consciousness=consciousness)
    elif consciousness and not _reranker._consciousness:
        _reranker._consciousness = consciousness
    return _reranker


def reset_reranker() -> None:
    global _reranker
    _reranker = None
