"""AgenticRAG — Autonomous iterative retrieval loop with self-reflection.

RAG 2.0的核心范式转变：从"固定的检索-生成流水线"到"Agent自主决策
的思考-检索-反思-生成循环"。

Agentic RAG模式（2026主流）:
  1. 单步条件式: 判断是否需要检索，不需要则直接回答
  2. 迭代式: 检索→评估→不满意→重新检索（最多N轮）
  3. 工具路由式: 动态选择向量/图谱/FTS5/外部API
  4. 规划式: Agent先规划检索步骤，再顺序执行
  5. 反思自评估: 生成答案后自我评估质量，不达标重新检索
  6. 多智能体: 多个Agent协同检索不同数据源

本模块实现模式 2+5 (迭代+反思)，并支持与 KnowledgeRouter 联动实现模式3。

Integration:
  - KnowledgeRouter: 获取路由决策，动态选择检索源
  - KnowledgeBase: unified_retrieve_with_fusion() 多路召回
  - QueryDecomposer: 复杂查询分解为子查询链
  - HallucinationGuard: 检索后幻觉校验
  - RetrievalValidator: 检索质量验证

Usage:
    agentic = get_agentic_rag(consciousness=llm)
    result = await agentic.search("GB3095-2012中SO2的24小时平均浓度限值是多少？")
    # 自动决策检索策略 → 多轮迭代 → 自我评估 → 返回最终答案
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


# ── Agentic RAG Modes ──────────────────────────────────────────────

class RAGMode(str, Enum):
    """Agentic RAG的六种模式."""
    CONDITIONAL = "conditional"       # 条件式：先判断需不需要检索
    ITERATIVE = "iterative"           # 迭代式：不满意就再查
    TOOL_ROUTING = "tool_routing"     # 工具路由：动态选检索源
    PLANNING = "planning"             # 规划式：先规划再执行
    REFLECTIVE = "reflective"         # 反思式：生成后自评
    MULTI_AGENT = "multi_agent"       # 多智能体协同
    HITL = "hitl"                     # 人机协同：低置信度时请求人工确认


# ── Data Types ─────────────────────────────────────────────────────

@dataclass
class RetrievalRound:
    """单轮检索的结果记录."""
    round_id: int
    query: str                          # 本轮使用的查询
    sources: list[str]                  # 使用的检索源 ["vector","fts5","graph"]
    doc_count: int                      # 检索到的文档数
    top_docs: list[str] = field(default_factory=list)  # 顶部文档摘要
    answer: str = ""                    # 基于本轮检索生成的答案
    confidence: float = 0.0             # Agent对答案的置信度
    needs_more: bool = True             # 是否需要更多检索
    reasoning: str = ""                 # Agent的决策推理
    latency_ms: float = 0.0
    tokens_used: int = 0


@dataclass
class AgenticResult:
    """Agentic RAG的最终结果."""
    original_query: str
    rounds: list[RetrievalRound] = field(default_factory=list)
    final_answer: str = ""
    final_confidence: float = 0.0
    sources_used: list[str] = field(default_factory=list)
    total_rounds: int = 0
    total_tokens: int = 0
    total_ms: float = 0.0
    mode: str = ""                      # 使用的模式
    evaluation: str = ""                # 自我评估摘要

    @property
    def is_satisfactory(self) -> bool:
        return self.final_confidence >= 0.7

    def summary(self) -> str:
        return (
            f"[{self.mode}] {self.original_query[:50]}... → "
            f"{self.total_rounds} rounds, confidence={self.final_confidence:.0%}, "
            f"{len(self.sources_used)} sources, {self.total_tokens} tokens"
        )


# ── Agentic RAG Engine ─────────────────────────────────────────────

class RAGCircuitBreaker:
    """Per-session circuit breaker for AgenticRAG iterations.

    Prevents runaway loops: if confidence fails to improve over
    consecutive rounds, breaks the circuit and returns best-so-far.
    """
    def __init__(self, stale_threshold: int = 3, min_improvement: float = 0.05):
        self.stale_threshold = stale_threshold
        self.min_improvement = min_improvement
        self._consecutive_stale = 0
        self._best_confidence = 0.0
        self._total_failures = 0
        self._open = False

    def record(self, confidence: float) -> bool:
        """Record a round's confidence. Returns True if circuit should break."""
        if self._open:
            return True
        if confidence > self._best_confidence + self.min_improvement:
            self._best_confidence = confidence
            self._consecutive_stale = 0
        else:
            self._consecutive_stale += 1
        if self._consecutive_stale >= self.stale_threshold:
            self._open = True
        return self._open

    def record_failure(self) -> bool:
        self._total_failures += 1
        if self._total_failures >= self.stale_threshold * 2:
            self._open = True
        return self._open

    def reset(self):
        self._consecutive_stale = 0
        self._best_confidence = 0.0
        self._total_failures = 0
        self._open = False


class AgenticRAG:
    """自主迭代检索引擎 — 实现 RAG 2.0 的 Agentic 范式.

    RAG模式选择（基于文章决策树）:
      - 查询明确、单数据源 → CONDITIONAL（单步）
      - 查询模糊、可能不足 → ITERATIVE（多轮）
      - 多数据源、异构 → TOOL_ROUTING（动态选源）
      - 复杂多步骤 → PLANNING（先规划）
      - 高风险领域 → REFLECTIVE（自评估）

    默认自适应策略: 简单查询走 SHORT_PATH（FTS5+LLM直答），
    复杂查询走 ITERATIVE，极端任务走 PLANNING。
    """

    MAX_ROUNDS = 5
    MIN_IMPROVEMENT = 0.1  # 最少置信度提升
    COST_PER_ROUND_TOKENS = 3000  # 预估每轮token消耗
    CB_STALE_THRESHOLD = 3

    # Short-path: queries matching these patterns skip the full RAG pipeline
    SHORT_PATH_PATTERNS: list[str] = [
        r"^(你好|hi|hello|谢谢|bye|再见)",
        r"^[?？]?[^?？]{1,15}[?？]?$",        # Very short queries
        r"^(是|否|对|错|yes|no|true|false)[?？]?$",
        r"^(现在几|今天星期|今天是|日期|时间)",
    ]

    def __init__(self, consciousness: Any = None):
        """初始化.

        Args:
            consciousness: LLM consciousness for reasoning + generation.
        """
        self._consciousness = consciousness
        self._total_queries = 0
        self._total_tokens = 0
        self._cb = RAGCircuitBreaker(
            stale_threshold=self.CB_STALE_THRESHOLD,
            min_improvement=self.MIN_IMPROVEMENT,
        )

    async def search(
        self,
        query: str,
        mode: RAGMode = RAGMode.ITERATIVE,
        max_rounds: int = 3,
        max_tokens: int = 50_000,
        domain: str = "general",
        hitl_callback=None,  # async fn(result) → bool (approved)
    ) -> AgenticResult:
        """Agentic RAG主入口——自动决策→检索→生成→反思.

        Args:
            query: 用户查询
            mode: RAG模式（默认 iterative，auto 走自适应短路径）
            max_rounds: 最大检索轮数
            max_tokens: Token预算上限
            domain: 领域上下文
            hitl_callback: HITL模式回调 async def callback(result) -> bool

        Returns:
            AgenticResult with full retrieval trajectory
        """
        self._total_queries += 1
        start_time = time.time()
        self._cb.reset()

        # 0. Adaptive short-path: auto-detect simple queries and route directly
        if mode == RAGMode.ITERATIVE and self._is_short_path(query):
            result = await self._short_path_rag(query, domain, max_tokens)
            result.total_ms = (time.time() - start_time) * 1000
            self._total_tokens += result.total_tokens
            logger.info(result.summary())
            return result

        # 1. 选择模式（如 auto）
        if mode == RAGMode.CONDITIONAL:
            result = await self._conditional_rag(query, domain, max_tokens)
        elif mode == RAGMode.PLANNING:
            result = await self._planning_rag(query, domain, max_rounds, max_tokens)
        elif mode == RAGMode.REFLECTIVE:
            result = await self._reflective_rag(query, domain, max_rounds, max_tokens)
        elif mode == RAGMode.HITL:
            result = await self._iterative_rag(query, domain, max_rounds, max_tokens)
            # HITL: 低置信度时请求人工确认
            if result.final_confidence < 0.7 and hitl_callback:
                try:
                    approved = await hitl_callback(result)
                    if approved:
                        result.evaluation += " | 已获人工确认"
                        result.final_confidence = max(result.final_confidence, 0.8)
                    else:
                        result.final_answer += "\n\n[⚠ 人工审核未通过，建议重新检索]"
                        result.final_confidence = 0.3
                except Exception as e:
                    logger.debug(f"HITL callback: {e}")
        else:
            # ITERATIVE / TOOL_ROUTING / 默认混合
            result = await self._iterative_rag(query, domain, max_rounds, max_tokens)

        result.total_ms = (time.time() - start_time) * 1000
        self._total_tokens += result.total_tokens
        logger.info(result.summary())
        return result

    # ── Iterative RAG（迭代式）───────────────────────────────────

    async def _iterative_rag(
        self, query: str, domain: str, max_rounds: int, max_tokens: int,
    ) -> AgenticResult:
        """迭代式检索：检索→生成→评估→不满意就重来."""
        rounds: list[RetrievalRound] = []
        current_query = query
        total_tokens = 0

        for r in range(max_rounds):
            if total_tokens >= max_tokens:
                logger.warning(f"AgenticRAG: token budget exceeded at round {r}")
                break

            # Circuit breaker: break if confidence stagnates
            if r > 0 and rounds:
                last_conf = rounds[-1].confidence
                stale = self._cb.record(last_conf)
                if stale:
                    logger.warning(f"AgenticRAG: circuit breaker tripped at round {r} (stale confidence)")
                    break

            # 工具路由：动态选择检索源
            sources = await self._select_sources(current_query, domain, rounds)

            # 检索
            docs = await self._retrieve(current_query, sources, domain)
            doc_summaries = [d[:100] for d in docs[:5]] if docs else []

            # 生成答案
            answer, confidence, reasoning = await self._generate_and_evaluate(
                current_query, docs, domain, rounds)

            round_info = RetrievalRound(
                round_id=r + 1,
                query=current_query,
                sources=sources,
                doc_count=len(docs),
                top_docs=doc_summaries,
                answer=answer,
                confidence=confidence,
                needs_more=confidence < 0.7 and r < max_rounds - 1,
                reasoning=reasoning,
                latency_ms=0,
                tokens_used=self.COST_PER_ROUND_TOKENS,
            )
            rounds.append(round_info)
            total_tokens += self.COST_PER_ROUND_TOKENS

            # 检查是否满意
            if confidence >= 0.8:
                logger.info(f"AgenticRAG: satisfied at round {r + 1} (confidence={confidence:.0%})")
                break

            # 改进查询
            if confidence < 0.5:
                current_query = await self._refine_query(
                    query, rounds, domain)
            elif confidence < 0.7:
                current_query = await self._expand_query(
                    query, rounds, domain)

        # 取最高置信度的答案
        if rounds:
            best = max(rounds, key=lambda r: r.confidence)
            final_answer = best.answer
            final_confidence = best.confidence
        else:
            final_answer = "检索未返回有效结果"
            final_confidence = 0.0

        all_sources = list(set(s for r in rounds for s in r.sources))

        return AgenticResult(
            original_query=query,
            rounds=rounds,
            final_answer=final_answer,
            final_confidence=final_confidence,
            sources_used=all_sources,
            total_rounds=len(rounds),
            total_tokens=total_tokens,
            mode="iterative",
            evaluation=(
                f"经过{len(rounds)}轮检索，置信度{final_confidence:.0%}" if rounds
                else "无检索结果"
            ),
        )

    # ── Conditional RAG（条件式）─────────────────────────────────

    async def _conditional_rag(
        self, query: str, domain: str, max_tokens: int,
    ) -> AgenticResult:
        """条件式：先判断是否需要检索，不需要则直接回答."""
        needs_retrieval = await self._needs_retrieval(query)
        if not needs_retrieval:
            # 直接用LLM知识回答
            answer = await self._llm_answer(query, domain, "")
            return AgenticResult(
                original_query=query,
                final_answer=answer,
                final_confidence=0.6,
                sources_used=["llm_knowledge"],
                total_rounds=0,
                mode="conditional",
                evaluation="无需检索，直接回答",
            )
        # 需要检索 → 走迭代式
        return await self._iterative_rag(query, domain, max_rounds=2, max_tokens=max_tokens)

    # ── Planning RAG（规划式）────────────────────────────────────

    async def _planning_rag(
        self, query: str, domain: str, max_rounds: int, max_tokens: int,
    ) -> AgenticResult:
        """规划式：先让Agent规划检索步骤，再顺序执行."""
        plan = await self._plan_retrieval_steps(query, domain, max_rounds)
        if not plan:
            return await self._iterative_rag(query, domain, max_rounds, max_tokens)

        rounds: list[RetrievalRound] = []
        total_tokens = 0

        for i, step in enumerate(plan[:max_rounds]):
            step_query = step.get("query", query)
            step_sources = step.get("sources", ["vector"])
            docs = await self._retrieve(step_query, step_sources, domain)
            answer, conf, reasoning = await self._generate_and_evaluate(
                step_query, docs, domain, rounds)

            rounds.append(RetrievalRound(
                round_id=i + 1, query=step_query,
                sources=step_sources, doc_count=len(docs),
                top_docs=[d[:80] for d in docs[:5]] if docs else [],
                answer=answer, confidence=conf,
                needs_more=conf < 0.7, reasoning=reasoning,
                tokens_used=self.COST_PER_ROUND_TOKENS,
            ))
            total_tokens += self.COST_PER_ROUND_TOKENS
            if conf >= 0.8:
                break

        best = max(rounds, key=lambda r: r.confidence) if rounds else None
        return AgenticResult(
            original_query=query, rounds=rounds,
            final_answer=best.answer if best else plan[-1].get("query", query),
            final_confidence=best.confidence if best else 0.3,
            total_rounds=len(rounds), total_tokens=total_tokens,
            mode="planning",
            evaluation=f"按计划执行{len(plan)}步检索",
        )

    # ── Reflective RAG（反思式）──────────────────────────────────

    async def _reflective_rag(
        self, query: str, domain: str, max_rounds: int, max_tokens: int,
    ) -> AgenticResult:
        """反思式：首先生成答案，然后自我评估，不达标重新检索."""
        result = await self._iterative_rag(query, domain, max_rounds, max_tokens)

        # 额外自我评估
        if result.final_confidence < 0.7:
            self_eval = await self._self_evaluate(
                query, result.final_answer, result.rounds)
            result.evaluation = self_eval

            # 如果不满意且还有 token 预算
            if "不充分" in self_eval and result.total_tokens < max_tokens:
                retry = await self._iterative_rag(
                    query, domain, max_rounds=2,
                    max_tokens=max_tokens - result.total_tokens)
                if retry.final_confidence > result.final_confidence:
                    return retry

        result.mode = "reflective"
        return result

    # ── Internal: Query Planning ──────────────────────────────────

    async def _plan_retrieval_steps(
        self, query: str, domain: str, max_steps: int,
    ) -> list[dict]:
        """让Agent规划检索步骤."""
        if not self._consciousness:
            # Heuristic: single step with all sources
            return [{"query": query, "sources": ["vector", "fts5", "graph"]}]

        prompt = (
            f"[Retrieval Planning] For the query in domain '{domain}', "
            f"plan up to {max_steps} retrieval steps.\n\n"
            f"Query: {query}\n\n"
            f"Available sources: vector (semantic), fts5 (keyword), "
            f"graph (entity relationships), engram (fast lookup)\n\n"
            f"Output JSON array of steps:\n"
            f'[{{"query": "sub-query", "sources": ["vector","fts5"], '
            f'"reasoning": "why this step"}}]'
        )
        try:
            raw = await self._consciousness.query(
                prompt, max_tokens=400, temperature=0.3)
            return self._parse_json_array(raw)
        except Exception:
            return [{"query": query, "sources": ["vector", "fts5"]}]

    async def _refine_query(
        self, original: str, rounds: list[RetrievalRound], domain: str,
    ) -> str:
        """基于前几轮结果精炼查询."""
        if not self._consciousness or not rounds:
            return original

        prev = rounds[-1]
        prompt = (
            f"Original query: {original}\n"
            f"Previous attempt retrieved {prev.doc_count} docs with "
            f"confidence {prev.confidence:.0%}. Answer was insufficient.\n"
            f"Suggest a refined query to get better results. Return only the query."
        )
        try:
            raw = await self._consciousness.query(
                prompt, max_tokens=200, temperature=0.3)
            return raw.strip().strip('"')
        except Exception:
            return original

    async def _expand_query(
        self, original: str, rounds: list[RetrievalRound], domain: str,
    ) -> str:
        """扩展查询——添加同义词、相关术语."""
        if not self._consciousness:
            return original

        prompt = (
            f"Expand this query with synonyms and related terms for better "
            f"retrieval: '{original}'. Return only the expanded query."
        )
        try:
            raw = await self._consciousness.query(
                prompt, max_tokens=200, temperature=0.5)
            return raw.strip().strip('"')
        except Exception:
            return original

    # ── Internal: Retrieval ──────────────────────────────────────

    async def _select_sources(
        self, query: str, domain: str, history: list[RetrievalRound],
    ) -> list[str]:
        """动态选择检索源（TOOL_ROUTING模式）."""
        try:
            from .knowledge_router import get_knowledge_router
            router = get_knowledge_router()
            decision = router.classify(query)
            sources = [decision.primary_source] + list(decision.secondary_sources)
            return [s for s in sources if s] if sources else ["vector", "fts5"]
        except Exception:
            pass
        return ["vector", "fts5", "graph"]

    async def _retrieve(
        self, query: str, sources: list[str], domain: str,
    ) -> list[str]:
        """执行检索并返回文档内容列表."""
        try:
            from .intelligent_kb import unified_retrieve
            results = await unified_retrieve(
                query, top_k=5)
            docs = [r.text if hasattr(r, 'text') else str(r) for r in results]
            return docs
        except Exception as e:
            logger.debug(f"AgenticRAG retrieve: {e}")
            return []

    # ── Internal: Generation + Evaluation ─────────────────────────

    async def _generate_and_evaluate(
        self, query: str, docs: list[str], domain: str,
        history: list[RetrievalRound],
    ) -> tuple[str, float, str]:
        """生成答案 + 置信度评估."""
        if not docs:
            return "未找到相关文档", 0.0, "no_docs"

        if not self._consciousness:
            # Heuristic: return first doc summary
            return docs[0][:500], 0.5, "heuristic"

        context = "\n\n".join(f"[{i+1}] {d[:800]}" for i, d in enumerate(docs[:5]))
        prompt = (
            f"[RAG Generation] Answer the query using ONLY the provided context.\n\n"
            f"Query: {query}\n"
            f"Domain: {domain}\n\n"
            f"Context:\n{context}\n\n"
            f"Output JSON:\n"
            f'{{"answer": "your answer based on context", '
            f'"confidence": 0.0-1.0, '
            f'"reasoning": "why this confidence", '
            f'"needs_more": true/false}}'
        )
        try:
            raw = await self._consciousness.query(
                prompt, max_tokens=800, temperature=0.3)
            data = self._parse_llm_json(raw)
            if data:
                base_confidence = float(data.get("confidence", 0.5))
                # OKH-RAG: blend in structural correctness
                structural = self._structural_score(query, docs)
                confidence = base_confidence * 0.7 + structural * 0.3
                return (
                    data.get("answer", docs[0][:300]),
                    round(confidence, 3),
                    data.get("reasoning", "") + (" +structural" if structural > base_confidence else ""),
                )
        except Exception as e:
            logger.debug(f"AgenticRAG generate: {e}")

        return docs[0][:500], 0.5, "fallback"

    async def _needs_retrieval(self, query: str) -> bool:
        """判断查询是否需要外部检索."""
        # Heuristic: short, factual queries need retrieval
        if len(query) < 20:
            return True
        # Common knowledge → no retrieval
        no_retrieval_patterns = [
            r"^(你好|hi|hello|谢谢|bye|再见)", r"^你(是|能|会).{0,10}[?？]",
        ]
        import re
        for pat in no_retrieval_patterns:
            if re.match(pat, query.strip()):
                return False
        return True

    async def _llm_answer(
        self, query: str, domain: str, context: str,
    ) -> str:
        """纯LLM回答（无检索）."""
        if not self._consciousness:
            return f"关于 '{query}' 的问题，我需要更多信息。"
        try:
            raw = await self._consciousness.query(
                f"Answer briefly: {query}", max_tokens=300, temperature=0.5)
            return raw.strip()
        except Exception:
            return f"无法回答 '{query}'"

    async def _self_evaluate(
        self, query: str, answer: str, rounds: list[RetrievalRound],
    ) -> str:
        """LLM自我评估答案质量."""
        if not self._consciousness:
            return "评估不可用"
        prompt = (
            f"Evaluate this RAG answer:\n"
            f"Query: {query}\n"
            f"Answer: {answer[:500]}\n"
            f"Retrieval rounds: {len(rounds)}\n\n"
            f"Rate: '充分' (good), '基本充分' (acceptable), or "
            f"'不充分' (needs more). Return only the rating."
        )
        try:
            raw = await self._consciousness.query(
                prompt, max_tokens=100, temperature=0.2)
            return raw.strip()
        except Exception:
            return "基本充分"

    # ── OKH-RAG Structural Scoring ────────────────────────────────

    @staticmethod
    def _structural_score(query: str, docs: list[str]) -> float:
        """Calculate structural correctness score based on document ordering.

        Uses the OrderAwareReranker to check if retrieved documents follow
        a coherent reasoning sequence. High score = docs are well-ordered.
        """
        if len(docs) < 2:
            return 0.5
        try:
            from .order_aware_reranker import get_order_aware_reranker
            reranker = get_order_aware_reranker()
            doc_types = [reranker.infer_doc_type(d[:200]) for d in docs]
            from .precedence_model import get_precedence_model
            model = get_precedence_model()
            return model.score_ordering(doc_types)
        except Exception:
            pass
        return 0.5

    # ── JSON Helpers ──────────────────────────────────────────────

    @staticmethod
    def _parse_llm_json(raw: str) -> dict | None:
        import json
        try:
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
                return json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            pass
        return None

    @staticmethod
    def _parse_json_array(raw: str) -> list[dict]:
        import json
        try:
            if "```json" in raw:
                s = raw.index("```json") + 7
                e = raw.index("```", s)
                raw = raw[s:e]
            elif "```" in raw:
                s = raw.index("```") + 3
                e = raw.index("```", s)
                raw = raw[s:e]
            raw = raw.strip()
            if raw.startswith("["):
                return json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            pass
        return []

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "total_queries": self._total_queries,
            "total_tokens": self._total_tokens,
            "has_consciousness": self._consciousness is not None,
        }


# ── Singleton ──────────────────────────────────────────────────────

_agentic_rag: AgenticRAG | None = None


def get_agentic_rag(consciousness: Any = None) -> AgenticRAG:
    global _agentic_rag
    if _agentic_rag is None:
        _agentic_rag = AgenticRAG(consciousness=consciousness)
    elif consciousness and not _agentic_rag._consciousness:
        _agentic_rag._consciousness = consciousness
    return _agentic_rag


def reset_agentic_rag() -> None:
    global _agentic_rag
    _agentic_rag = None
