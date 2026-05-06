"""Query Decomposer — complex query splitting + HyDE hypothesis generation.

P0 准确率提升模块：将复杂查询拆解为子查询链，生成假设文档增强检索。

Core techniques:
  Decomposition:      复杂查询 → 原子子查询 → 并行检索 → 结果合并
  HyDE:               query → LLM生成假设文档 → 用假设文档向量检索 → 真实文档
  Query2Doc:          query → few-shot生成伪文档 → 用伪文档增强稀疏检索
  Iterative retrieval: 检索 → 结果不足 → 重新分解 → 再检索

集成现有:
  - expand_query() 中文扩展 → 作为分解的输入
  - unified_retrieve() 多路召回 → 每个子查询的结果合并
  - hierarchical_retrieve() 层次检索 → HyDE 结果附带章节上下文
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class SubQuery:
    """分解后的原子子查询。"""
    query: str
    weight: float = 1.0
    intent: str = ""         # "factual", "procedural", "comparative", "definitional"
    dependencies: list[str] = field(default_factory=list)  # 依赖的前序子查询ID


@dataclass
class DecomposedQuery:
    """完整的查询分解结果。"""
    original: str
    sub_queries: list[SubQuery] = field(default_factory=list)
    hyde_document: str = ""      # HyDE 生成的假设文档
    strategy: str = "direct"     # "direct", "decompose", "hyde", "iterative"


@dataclass
class DecomposedResult:
    """分解查询的合并结果。"""
    original_query: str
    sub_results: dict[str, list[Any]] = field(default_factory=dict)
    merged_text: str = ""
    strategy_used: str = ""


class QueryDecomposer:
    """查询分解器 + HyDE 生成器。

    Usage:
        qd = QueryDecomposer()
        decomposed = qd.decompose("环评中大气扩散模型参数如何设置，与噪声模型有何区别？")
        # → 3 sub-queries + 1 HyDE document

        for sq in decomposed.sub_queries:
            results = await unified_retrieve(sq.query, top_k=5, hub=hub)
    """

    def __init__(self):
        self._decomposition_patterns = [
            (r'(.+?)与(.+?)有何区别', self._split_comparison),
            (r'(.+?)如何(.+?)(?:以及|和)(.+)', self._split_compound),
            (r'(.+?)(?:的|中)(.+?)(?:以及|还有|和)(.+?)的(.+)', self._split_multi_aspect),
            (r'(.+?)，(.+?)。', self._split_semicolons),
        ]

    def decompose(self, query: str, hub: Any = None, max_sub: int = 5) -> DecomposedQuery:
        """分解复杂查询 + 生成 HyDE 假设文档。

        Strategy selection:
          query长度 < 20 → direct (无需分解)
          query含 "与" "以及" "和" → decompose (拆分对比/复合)
          其他 → hyde (生成假设文档增强检索)
        """
        result = DecomposedQuery(original=query)

        # Strategy 1: Direct (short/simple queries)
        if len(query) < 20 and not any(kw in query for kw in ("与", "以及", "和", "对比", "比较")):
            result.strategy = "direct"
            result.sub_queries = [SubQuery(query=query, weight=1.0, intent="factual")]
            return result

        # Strategy 2: Decompose (multi-part questions)
        sub_queries = self._rule_decompose(query)[:max_sub]
        if len(sub_queries) >= 2:
            result.strategy = "decompose"
            result.sub_queries = [
                SubQuery(query=q, weight=1.0 / len(sub_queries),
                        intent=self._detect_intent(q))
                for q in sub_queries
            ]
        else:
            result.strategy = "direct"
            result.sub_queries = [SubQuery(query=query, weight=1.0, intent=self._detect_intent(query))]

        # Strategy 3: HyDE (always generate for complex queries)
        if len(query) > 20 and hub:
            result.hyde_document = self._generate_hyde(query, hub)
            if result.hyde_document:
                result.sub_queries.append(SubQuery(
                    query=result.hyde_document[:500],
                    weight=0.3,
                    intent="hyde",
                ))

        return result

    def decompose_with_hub(self, query: str, hub: Any) -> DecomposedQuery:
        """LLM 增强的查询分解（最佳质量）。"""
        result = self.decompose(query, hub)

        if result.strategy == "decompose" and hub:
            try:
                result = self._llm_decompose(query, hub, result)
            except Exception as e:
                logger.warning("LLM decomposition failed, using rule-based: %s", e)

        return result

    def _rule_decompose(self, query: str) -> list[str]:
        """规则化查询分解。"""
        for pattern, handler in self._decomposition_patterns:
            match = re.search(pattern, query)
            if match:
                return handler(match)
        return [query]

    @staticmethod
    def _split_comparison(match) -> list[str]:
        a, b = match.group(1).strip(), match.group(2).strip()
        return [a, b, f"{a} 与 {b} 对比"]

    @staticmethod
    def _split_compound(match) -> list[str]:
        topic, action, extra = match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
        return [f"{topic}如何{action}", f"{topic}如何{extra}"]

    @staticmethod
    def _split_multi_aspect(match) -> list[str]:
        domain, aspect1, aspect2, attr = [g.strip() for g in match.groups()]
        return [f"{domain}的{aspect1}{attr}", f"{domain}的{aspect2}{attr}"]

    @staticmethod
    def _split_semicolons(match) -> list[str]:
        parts = match.group(0).replace("，", "|").replace("。", "|").split("|")
        return [p.strip() for p in parts if len(p.strip()) > 5]

    @staticmethod
    def _detect_intent(query: str) -> str:
        if any(kw in query for kw in ("如何", "怎样", "步骤", "方法")):
            return "procedural"
        if any(kw in query for kw in ("对比", "区别", "比较", "vs")):
            return "comparative"
        if any(kw in query for kw in ("定义", "什么是", "概念")):
            return "definitional"
        return "factual"

    def _llm_decompose(self, query: str, hub: Any, existing: DecomposedQuery) -> DecomposedQuery:
        prompt = f"""Break down this complex query into 2-4 simpler sub-queries:

Query: {query}

Rules:
- Each sub-query should be independently answerable
- Preserve key entities and constraints
- For comparisons, generate one sub-query per entity
- Output as JSON list of strings

Example:
"环评中大气扩散模型参数与噪声衰减模型参数有何区别" →
["大气扩散模型参数设置", "噪声衰减模型参数设置", "大气扩散与噪声衰减模型对比"]"""

        try:
            response = hub.chat(prompt)
            import json
            if "[" in response:
                response = response[response.index("["):response.rindex("]")+1]
            sub_list = json.loads(response)
            if isinstance(sub_list, list) and len(sub_list) >= 2:
                existing.sub_queries = [
                    SubQuery(query=q, weight=1.0/len(sub_list), intent=self._detect_intent(q))
                    for q in sub_list[:5]
                ]
                existing.strategy = "decompose"
        except Exception:
            pass

        return existing

    def _generate_hyde(self, query: str, hub: Any) -> str:
        """HyDE: 生成假设文档作为检索桥梁。

        原理: LLM生成一个"理想答案文档"，用其向量检索真实知识库。
              假设文档与真实文档在语义空间近邻，但包含更丰富的术语。
        """
        prompt = f"""Write a brief technical document section that answers this question:

Question: {query}

Write 3-5 sentences as if you're writing a reference manual entry.
Use specific terminology, numbers where appropriate, and factual tone.
Do NOT say "I don't know" — write a plausible technical answer."""

        try:
            response = hub.chat(prompt)
            if response and len(response) > 20:
                logger.debug("HyDE generated %d chars for query: %s", len(response), query[:50])
                return response
        except Exception as e:
            logger.debug("HyDE generation failed: %s", e)

        return ""

    def iterative_decompose(self, query: str, hub: Any,
                           retriever_fn: callable,
                           min_results: int = 3,
                           max_iterations: int = 3) -> DecomposedResult:
        """迭代检索：检索 → 不足 → 重新分解 → 再检索。

        Args:
            retriever_fn: async fn(query, top_k) → list[RetrievalResult]
        """
        import asyncio

        result = DecomposedResult(original_query=query, strategy_used="iterative")

        for iteration in range(max_iterations):
            decomposed = self.decompose_with_hub(query, hub)

            all_results = {}
            for sq in decomposed.sub_queries:
                try:
                    if asyncio.iscoroutinefunction(retriever_fn):
                        hits = asyncio.get_event_loop().run_until_complete(
                            retriever_fn(sq.query, top_k=5)
                        )
                    else:
                        hits = retriever_fn(sq.query, top_k=5)
                    all_results[sq.query] = hits
                except Exception as e:
                    logger.debug("Sub-query '%s' retrieval failed: %s", sq.query, e)

            result.sub_results = all_results
            total_hits = sum(len(v) for v in all_results.values())

            if total_hits >= min_results:
                result.strategy_used = f"iterative_{decomposed.strategy}"
                return result

            query += " 简化版"
            logger.debug("Iteration %d: %d results < %d, retrying...", iteration+1, total_hits, min_results)

        return result
