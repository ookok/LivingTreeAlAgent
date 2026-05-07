"""GradualAgent — Progressive intelligence escalation for task routing.

Routes tasks through increasingly sophisticated pipelines based on complexity:

  Simple (complexity < 0.3): 直接 LLM 回答 → 零 RAG 开销
  Medium (0.3-0.6):        CONDITIONAL RAG → 条件检索
  Complex (0.6-0.8):       ITERATIVE RAG → 多轮迭代
  Very Complex (>0.8):     REFLECTIVE + PLANNING → 规划+自评+多Agent

This follows the RAG 2.0 "渐进智能" principle: only add complexity when needed,
optimizing cost-speed-quality trilemma by defaulting to the simplest pipeline.

Integration:
  - AgenticRAG:      for retrieval-aware tasks
  - EconomicPolicy:  for model selection per complexity tier
  - TreeLLM:         for provider routing

Usage:
    ga = GradualAgent(rag_engine, consciousness)
    result = await ga.process(query, task_type="code_engineering")
    # Auto-escalates: simple → conditional → iterative → reflective
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


# ── Escalation Tiers ──────────────────────────────────────────────

class EscalationTier(str, Enum):
    """Progressive intelligence tiers."""
    DIRECT = "direct"            # 直接 LLM，零 RAG
    CONDITIONAL_RAG = "conditional_rag"  # 条件检索
    ITERATIVE_RAG = "iterative_rag"      # 多轮迭代
    REFLECTIVE_RAG = "reflective_rag"    # 规划+自评
    MULTI_AGENT = "multi_agent"          # 多Agent协同


@dataclass
class GradualResult:
    """GradualAgent处理结果."""
    query: str
    answer: str = ""
    tier: EscalationTier = EscalationTier.DIRECT
    complexity: float = 0.3          # 实际复杂度
    confidence: float = 0.5
    escalation_reason: str = ""      # 为何提升/不提升
    tokens_used: int = 0
    cost_yuan: float = 0.0
    latency_ms: float = 0.0
    retrieval_rounds: int = 0

    def summary(self) -> str:
        cost_icon = "💰" if self.cost_yuan > 1.0 else "🆓"
        return (
            f"[{self.tier.value}] complexity={self.complexity:.2f} "
            f"confidence={self.confidence:.0%} {cost_icon}¥{self.cost_yuan:.3f} "
            f"{self.latency_ms:.0f}ms"
        )


class GradualAgent:
    """渐进智能任务路由器.

    从简单到复杂自动升级：
      1. 评估复杂度 → 选择初始Tier
      2. 执行当前Tier → 评估结果
      3. 置信度不足 → 自动升级到下一Tier
      4. 达到最高Tier或满意 → 返回结果
    """

    TIER_TOKEN_BUDGET: dict[EscalationTier, int] = {
        EscalationTier.DIRECT: 2_000,
        EscalationTier.CONDITIONAL_RAG: 8_000,
        EscalationTier.ITERATIVE_RAG: 20_000,
        EscalationTier.REFLECTIVE_RAG: 40_000,
        EscalationTier.MULTI_AGENT: 80_000,
    }

    # Escalation thresholds: confidence below this → upgrade tier
    ESCALATION_THRESHOLD: dict[EscalationTier, float] = {
        EscalationTier.DIRECT: 0.7,
        EscalationTier.CONDITIONAL_RAG: 0.75,
        EscalationTier.ITERATIVE_RAG: 0.8,
        EscalationTier.REFLECTIVE_RAG: 0.85,
        EscalationTier.MULTI_AGENT: 0.9,  # No further escalation
    }

    def __init__(self, rag_engine: Any = None, consciousness: Any = None):
        self._rag = rag_engine
        self._consciousness = consciousness
        self._total_processed = 0
        self._tier_counts: dict[str, int] = {
            t.value: 0 for t in EscalationTier}

    async def process(
        self,
        query: str,
        task_type: str = "general",
        max_tokens: int = 50_000,
        escalation_enabled: bool = True,
    ) -> GradualResult:
        """渐进处理查询，自动升级至最佳Tier.

        Args:
            query: 用户查询
            task_type: 任务类型（用于路由优化）
            max_tokens: 总Token预算
            escalation_enabled: 是否启用自动升级

        Returns:
            GradualResult with final answer and escalation path
        """
        start_time = time.time()
        self._total_processed += 1

        # 1. 评估复杂度
        complexity = self._assess_complexity(query, task_type)

        # 2. 选择初始Tier
        tier = self._select_tier(complexity)
        logger.info(f"GradualAgent: query='{query[:40]}...' complexity={complexity:.2f} → tier={tier.value}")

        total_tokens = 0
        final_answer = ""
        final_confidence = 0.0
        escalation_reason = ""
        retrieval_rounds = 0
        current_tier = tier

        while True:
            tier_budget = min(self.TIER_TOKEN_BUDGET[current_tier],
                              max_tokens - total_tokens)

            # Execute current tier
            answer, confidence, tokens_used = await self._execute_tier(
                query, task_type, current_tier, tier_budget)
            total_tokens += tokens_used
            final_answer = answer
            final_confidence = confidence

            self._tier_counts[current_tier.value] += 1

            # Check if we should escalate
            threshold = self.ESCALATION_THRESHOLD.get(current_tier, 0.9)
            if confidence >= threshold or not escalation_enabled:
                escalation_reason = f"满意 (confidence={confidence:.0%} ≥ threshold={threshold:.0%})"
                break

            # Find next tier
            next_tier = self._next_tier(current_tier)
            if next_tier is None:
                escalation_reason = f"已达最高Tier (confidence={confidence:.0%})"
                break

            # Check budget
            if total_tokens + self.TIER_TOKEN_BUDGET[next_tier] > max_tokens:
                escalation_reason = f"Token预算不足 (used={total_tokens}, cap={max_tokens})"
                break

            escalation_reason = f"{current_tier.value} confidence={confidence:.0%} < {threshold:.0%} → escalating to {next_tier.value}"
            logger.info(f"GradualAgent: {escalation_reason}")
            current_tier = next_tier

        return GradualResult(
            query=query,
            answer=final_answer,
            tier=current_tier,
            complexity=complexity,
            confidence=final_confidence,
            escalation_reason=escalation_reason,
            tokens_used=total_tokens,
            cost_yuan=total_tokens / 1_000_000 * 3.0,  # rough estimate
            latency_ms=(time.time() - start_time) * 1000,
            retrieval_rounds=retrieval_rounds,
        )

    # ── Complexity Assessment ────────────────────────────────────

    def _assess_complexity(self, query: str, task_type: str) -> float:
        """Assess query complexity (0-1) based on multiple signals.

        Factors:
          - Query length (longer = more complex)
          - Task type (code > analysis > question)
          - Keyword signals (compare, explain, analyze → complex)
          - Question marks count
          - Domain-specific complexity
        """
        signals = 0.0
        signal_count = 0

        # Length signal
        qlen = len(query)
        if qlen > 500:
            signals += 0.9
        elif qlen > 200:
            signals += 0.7
        elif qlen > 100:
            signals += 0.5
        elif qlen > 50:
            signals += 0.3
        else:
            signals += 0.15
        signal_count += 1

        # Task type signal
        type_complexity = {
            "code_engineering": 0.8,
            "code_generation": 0.8,
            "environmental_report": 0.85,
            "bug_fix": 0.6,
            "data_analysis": 0.6,
            "document_generation": 0.5,
            "research": 0.4,
            "question": 0.2,
            "chat": 0.1,
            "general": 0.3,
        }
        signals += type_complexity.get(task_type, 0.3)
        signal_count += 1

        # Keyword signals
        complex_keywords = [
            "compare", "对比", "analyze", "分析", "explain", "解释",
            "implement", "实现", "design", "设计", "architecture", "架构",
            "多步", "multi-step", "复杂", "complex",
        ]
        keyword_hits = sum(1 for kw in complex_keywords if kw.lower() in query.lower())
        signals += min(0.8, keyword_hits * 0.2)
        signal_count += 1

        # Question marks → ambiguous query
        qmarks = query.count("?") + query.count("？")
        signals += min(0.5, qmarks * 0.15)
        signal_count += 1

        return min(1.0, round(signals / signal_count, 2))

    def _select_tier(self, complexity: float) -> EscalationTier:
        """Map complexity score to escalation tier."""
        if complexity < 0.3:
            return EscalationTier.DIRECT
        elif complexity < 0.5:
            return EscalationTier.CONDITIONAL_RAG
        elif complexity < 0.7:
            return EscalationTier.ITERATIVE_RAG
        elif complexity < 0.85:
            return EscalationTier.REFLECTIVE_RAG
        else:
            return EscalationTier.MULTI_AGENT

    def _next_tier(self, current: EscalationTier) -> EscalationTier | None:
        tier_order = [
            EscalationTier.DIRECT,
            EscalationTier.CONDITIONAL_RAG,
            EscalationTier.ITERATIVE_RAG,
            EscalationTier.REFLECTIVE_RAG,
            EscalationTier.MULTI_AGENT,
        ]
        try:
            idx = tier_order.index(current)
            if idx < len(tier_order) - 1:
                return tier_order[idx + 1]
        except ValueError:
            pass
        return None

    # ── Tier Execution ────────────────────────────────────────────

    async def _execute_tier(
        self, query: str, task_type: str, tier: EscalationTier, budget: int,
    ) -> tuple[str, float, int]:
        """Execute a query at a specific tier and return (answer, confidence, tokens)."""

        if tier == EscalationTier.DIRECT:
            return await self._direct_answer(query, task_type, budget)

        if tier == EscalationTier.CONDITIONAL_RAG:
            return await self._conditional_rag(query, task_type, budget)

        if tier == EscalationTier.ITERATIVE_RAG:
            return await self._iterative_rag(query, task_type, budget)

        if tier == EscalationTier.REFLECTIVE_RAG:
            return await self._reflective_rag(query, task_type, budget)

        # MULTI_AGENT: combine planning + iterative + reflective
        return await self._multi_agent(query, task_type, budget)

    async def _direct_answer(
        self, query: str, _task_type: str, budget: int,
    ) -> tuple[str, float, int]:
        """直接LLM回答，零检索."""
        if not self._consciousness:
            return query, 0.3, len(query) // 3 + 100

        try:
            raw = await self._consciousness.query(
                f"Answer briefly: {query}", max_tokens=min(budget // 3, 300),
                temperature=0.3)
            confidence = 0.6  # Direct answer baseline
            tokens = len(raw) // 3 + 300
            return raw.strip(), confidence, tokens
        except Exception:
            return query, 0.3, 100

    async def _conditional_rag(
        self, query: str, task_type: str, budget: int,
    ) -> tuple[str, float, int]:
        """条件式RAG：判断是否需要检索."""
        if not self._rag:
            return await self._direct_answer(query, task_type, budget)

        try:
            from ..knowledge.agentic_rag import RAGMode
            result = await self._rag.search(
                query, mode=RAGMode.CONDITIONAL, max_tokens=budget, domain=task_type)
            return result.final_answer, result.final_confidence, result.total_tokens
        except Exception:
            return await self._direct_answer(query, task_type, budget)

    async def _iterative_rag(
        self, query: str, task_type: str, budget: int,
    ) -> tuple[str, float, int]:
        """迭代式RAG."""
        if not self._rag:
            return await self._direct_answer(query, task_type, budget)

        try:
            from ..knowledge.agentic_rag import RAGMode
            result = await self._rag.search(
                query, mode=RAGMode.ITERATIVE, max_tokens=budget,
                max_rounds=2, domain=task_type)
            return result.final_answer, result.final_confidence, result.total_tokens
        except Exception:
            return await self._direct_answer(query, task_type, budget)

    async def _reflective_rag(
        self, query: str, task_type: str, budget: int,
    ) -> tuple[str, float, int]:
        """反思式RAG."""
        if not self._rag:
            return await self._direct_answer(query, task_type, budget)

        try:
            from ..knowledge.agentic_rag import RAGMode
            result = await self._rag.search(
                query, mode=RAGMode.REFLECTIVE, max_tokens=budget,
                max_rounds=3, domain=task_type)
            return result.final_answer, result.final_confidence, result.total_tokens
        except Exception:
            return await self._direct_answer(query, task_type, budget)

    async def _multi_agent(
        self, query: str, task_type: str, budget: int,
    ) -> tuple[str, float, int]:
        """多Agent协同：规划+反思."""
        if not self._rag:
            return await self._direct_answer(query, task_type, budget)

        try:
            from ..knowledge.agentic_rag import RAGMode
            # Phase 1: Planning
            plan_result = await self._rag.search(
                query, mode=RAGMode.PLANNING, max_tokens=budget // 2,
                max_rounds=2, domain=task_type)

            # Phase 2: Reflective
            if plan_result.final_confidence < 0.8:
                reflect_result = await self._rag.search(
                    query, mode=RAGMode.REFLECTIVE,
                    max_tokens=budget - plan_result.total_tokens,
                    max_rounds=2, domain=task_type)
                return (reflect_result.final_answer,
                        max(plan_result.final_confidence, reflect_result.final_confidence),
                        plan_result.total_tokens + reflect_result.total_tokens)

            return plan_result.final_answer, plan_result.final_confidence, plan_result.total_tokens
        except Exception:
            return await self._direct_answer(query, task_type, budget)

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "total_processed": self._total_processed,
            "tier_distribution": self._tier_counts,
            "direct_pct": round(
                self._tier_counts[EscalationTier.DIRECT.value] / max(self._total_processed, 1), 3),
            "escalation_required_pct": round(
                (self._total_processed - self._tier_counts[EscalationTier.DIRECT.value])
                / max(self._total_processed, 1), 3),
        }


# ── Singleton ──────────────────────────────────────────────────────

_gradual_agent: GradualAgent | None = None


def get_gradual_agent(rag_engine: Any = None, consciousness: Any = None) -> GradualAgent:
    global _gradual_agent
    if _gradual_agent is None:
        _gradual_agent = GradualAgent(rag_engine=rag_engine, consciousness=consciousness)
    return _gradual_agent
