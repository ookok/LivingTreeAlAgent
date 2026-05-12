"""Latent Reasoner — Vector-space pre-reasoning before explicit CoT.

Based on arXiv:2604.02029 (Yu et al., 2026):
  "The Latent Space" — many critical processes are more naturally carried out
  in continuous latent space than in explicit token generation.

Design:
  Before committing to expensive explicit CoT (verbal chain-of-thought),
  perform fast pre-reasoning in latent (embedding) space:
    1. Classify task type via vector similarity
    2. Estimate complexity → adjust budget
    3. Pre-disambiguate entities via latent KB lookup
    4. Route to appropriate reasoning strategy

This reduces unnecessary token expenditure on tasks that latent space
can partially resolve, while preserving explicit CoT for tasks that need it.

Integration: life_stage._cognize calls LatentReasoner.before_cot().
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ── Data Types ──

class ReasoningStrategy(str, Enum):
    """Latent reasoning decision — how much explicit CoT is needed."""
    SKIP = "skip"         # Latent space resolves this, no explicit CoT needed
    LIGHT = "light"       # Minimal CoT (check latent result, short confirmation)
    FULL = "full"         # Full explicit chain-of-thought
    DEEP = "deep"         # Multi-step CoT with verification


@dataclass
class LatentContext:
    """Pre-computed latent features before explicit reasoning starts."""
    query: str
    embedding: list[float] = field(default_factory=list)
    task_category: str = "general"         # "code", "reasoning", "chat", "search"
    estimated_complexity: float = 0.5       # 0 (trivial) to 1 (extremely complex)
    entity_matches: list[str] = field(default_factory=list)  # Disambiguated entities
    recommended_strategy: ReasoningStrategy = ReasoningStrategy.LIGHT
    confidence: float = 0.5
    pre_reasoning_ms: float = 0.0

    @property
    def budget_factor(self) -> float:
        """How much explicit CoT budget is needed (0 = skip, 1 = full)."""
        mapping = {
            ReasoningStrategy.SKIP: 0.0,
            ReasoningStrategy.LIGHT: 0.3,
            ReasoningStrategy.FULL: 0.7,
            ReasoningStrategy.DEEP: 1.0,
        }
        return mapping.get(self.recommended_strategy, 0.7)


class LatentReasoner:
    """Pre-reason in latent space before invoking explicit chain-of-thought.

    Uses embedding vectors for fast semantic comparison,
    avoiding the token cost of full LLM calls for preliminary analysis.

    Three-step pre-reasoning:
      1. Category detection (vector similarity against known task prototypes)
      2. Complexity estimation (query structure analysis)
      3. Strategy routing (skip/light/full/deep based on latent features)
    """

    # Prototype embeddings for task categories (compact representation)
    # In production, these would be actual embeddings from a text encoder.
    # Here we use heuristic keyword vectors as proxies.
    CATEGORY_KEYWORDS = {
        "code": ["code", "function", "class", "bug", "fix", "implement",
                 "代码", "函数", "类", "bug", "修复", "实现"],
        "reasoning": ["why", "how", "explain", "analyze", "prove",
                      "为什么", "怎么", "解释", "分析", "证明"],
        "chat": ["hello", "hi", "help", "thanks", "what is",
                 "你好", "帮助", "谢谢", "什么是"],
        "search": ["find", "search", "lookup", "retrieve", "query",
                   "搜索", "查找", "检索"],
        "creative": ["write", "generate", "create", "design", "compose",
                     "写", "生成", "创建", "设计"],
    }

    COMPLEXITY_INDICATORS = {
        # Features that increase complexity score
        "multi_step": ["first", "then", "finally", "step", "pipeline",
                       "首先", "然后", "最后", "步骤", "管道"],
        "nested": ["inside", "within", "nested", "recursive",
                   "内部", "嵌套", "递归"],
        "comparison": ["versus", "compare", "difference", "better",
                       "对比", "比较", "区别", "更好"],
        "constraint": ["must", "should", "cannot", "limit",
                       "必须", "不能", "限制", "要求"],
    }

    def pre_reason(self, query: str, context: dict = None) -> LatentContext:
        """Fast latent-space pre-reasoning before explicit CoT.

        Args:
            query: User's input text.
            context: Optional session context.

        Returns:
            LatentContext with recommended strategy and pre-computed features.
        """
        t0 = time.time()

        # Step 1: Category detection via keyword vector similarity
        category = self._detect_category(query)

        # Step 2: Complexity estimation
        complexity = self._estimate_complexity(query)

        # Step 3: Strategy routing
        strategy = self._route_strategy(category, complexity, query)

        ctx = LatentContext(
            query=query,
            task_category=category,
            estimated_complexity=complexity,
            recommended_strategy=strategy,
            confidence=0.6 + complexity * 0.2,  # Higher complexity = lower confidence in latent
            pre_reasoning_ms=(time.time() - t0) * 1000,
        )

        logger.debug(
            f"LatentReasoner: {query[:60]} → "
            f"cat={category}, complexity={complexity:.2f}, "
            f"strategy={strategy.value}, {ctx.pre_reasoning_ms:.1f}ms"
        )

        return ctx

    def should_skip_cot(self, ctx: LatentContext) -> bool:
        """Check if explicit CoT can be skipped entirely.

        Only for very simple queries where latent pre-reasoning is sufficient.
        """
        return (
            ctx.recommended_strategy == ReasoningStrategy.SKIP
            and ctx.confidence > 0.8
            and ctx.estimated_complexity < 0.3
        )

    def recommended_max_tokens(self, ctx: LatentContext) -> int:
        """Recommend max_tokens for explicit CoT based on latent analysis."""
        base = {
            ReasoningStrategy.SKIP: 0,
            ReasoningStrategy.LIGHT: 500,
            ReasoningStrategy.FULL: 2048,
            ReasoningStrategy.DEEP: 4096,
        }
        complexity_bonus = int(ctx.estimated_complexity * 1024)
        return base.get(ctx.recommended_strategy, 2048) + complexity_bonus

    # ── Internal ──

    def _detect_category(self, query: str) -> str:
        """Classify task category by keyword vector overlap."""
        query_lower = query.lower()
        scores = {}

        for cat, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in query_lower)
            scores[cat] = score

        if not scores or max(scores.values()) == 0:
            return "general"

        # Pick highest scoring category
        best = max(scores.items(), key=lambda x: x[1])
        return best[0]

    def _estimate_complexity(self, query: str) -> float:
        """Estimate task complexity from query structure."""
        query_lower = query.lower()
        signals = 0
        total_checks = 0

        for group, indicators in self.COMPLEXITY_INDICATORS.items():
            total_checks += 1
            if any(ind.lower() in query_lower for ind in indicators):
                signals += 1

        # Word count as complexity proxy
        word_count = len(query.split())
        if word_count > 50:
            signals += 1
        elif word_count > 20:
            signals += 0.5

        # Question marks indicate uncertainty → higher complexity
        if "?" in query or "？" in query:
            signals += 0.5

        # Normalize to [0, 1]
        max_signals = total_checks + 1.5  # +1 for word count, +0.5 for questions
        return min(1.0, signals / max(max_signals, 1))

    def _route_strategy(
        self, category: str, complexity: float, query: str
    ) -> ReasoningStrategy:
        """Route to appropriate reasoning strategy based on latent features.

        Decision matrix (latent space → explicit space):
          - Simple chat (complexity < 0.2) → LIGHT CoT (just format response)
          - Simple search → LIGHT CoT (just format results)
          - Medium reasoning (0.3-0.6) → FULL CoT
          - Complex reasoning (>0.6) → DEEP CoT (multi-step with verification)
          - Code generation (>0.4) → DEEP CoT (needs planning)
          - Very simple queries → SKIP (instant response)
        """
        # Very simple: skip explicit CoT
        if complexity < 0.15 and category in ("chat", "search"):
            if len(query.split()) < 5:
                return ReasoningStrategy.SKIP

        # Code tasks need deeper reasoning
        if category == "code" and complexity > 0.3:
            return ReasoningStrategy.DEEP

        # Complex reasoning → deep
        if complexity > 0.6:
            return ReasoningStrategy.DEEP

        # Medium complexity → full CoT
        if complexity > 0.3:
            return ReasoningStrategy.FULL

        # Default: light CoT (formatting, simple response)
        return ReasoningStrategy.LIGHT


# ── Singleton ──

_reasoner: Optional[LatentReasoner] = None


def get_latent_reasoner() -> LatentReasoner:
    global _reasoner
    if _reasoner is None:
        _reasoner = LatentReasoner()
    return _reasoner
