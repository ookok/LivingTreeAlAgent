"""ReasoningBudget — Continuous reasoning effort allocator.

Based on DeepSeek-V4 "Three Reasoning Modes" (April 2026):
  Non-think: fast, intuitive, ~0 thinking tokens
  Think High: conscious analysis, ~1-4K thinking tokens
  Think Max:  maximum reasoning, ~32K+ thinking tokens (requires 384K context)

Key insight from DeepSeek-V4: Reasoning effort is a CONTINUOUS parameter,
not a binary choice between "flash" and "pro". The same model can operate
at different reasoning depths depending on the compute budget allocated.

For LivingTree: Instead of "use flash or pro?", ask "how many thinking
tokens should we invest in this task?"

The ReasoningBudget engine:
  1. Estimates task difficulty from query analysis
  2. Considers available context window budget
  3. Accounts for conversation rhythm and user patience
  4. Allocates thinking token budget (0-32K+)
  5. Maps budget to concrete strategy parameters:
     - deep_probe depth (1-3)
     - self_play max_rounds (0-3)
     - aggregate top_k (1-3)
     - model tier preference (flash/pro/max)

Integration:
  - Called BEFORE route_layered() to set strategy parameters
  - Controls deep_probe, self_play, and aggregate features
  - Feeds into depth_grading to compare actual vs. budgeted depth
  - CompetitiveEliminator uses budget efficiency for Elo weighting

Usage:
    rb = get_reasoning_budget()
    budget = rb.allocate(query, task_type="analysis", context_available=100000)
    # budget.thinking_tokens = 8000
    # budget.deep_probe_depth = 3
    # budget.self_play_rounds = 2
    # budget.model_tier = "pro"
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


class ReasoningTier(StrEnum):
    """Three reasoning tiers — mapped from DeepSeek-V4 thinking modes."""
    NON_THINK = "non_think"    # ≤1K tokens, fast response
    THINK_HIGH = "think_high"  # 1-8K tokens, structured reasoning
    THINK_MAX = "think_max"    # 8K+ tokens, exhaustive exploration


@dataclass
class ReasoningBudget:
    """Allocated reasoning resources for a single request.

    Maps DeepSeek-V4's three reasoning modes to LivingTree's
    multi-strategy orchestration parameters.
    """
    thinking_tokens: int = 1000          # Total thinking token budget
    tier: ReasoningTier = ReasoningTier.THINK_HIGH

    # Strategy control flags (derived from budget)
    deep_probe_depth: int = 1            # 1=light, 2=medium, 3=full
    self_play_rounds: int = 0            # 0=disabled, 1-3 rounds
    aggregate_models: int = 1            # 1=single model, 2-3=multi-model fusion
    model_tier: str = "flash"            # flash, pro, max

    # Context constraints
    context_available: int = 128000      # Available context window
    context_allocated: int = 0           # How much context this request uses
    context_remaining_after: int = 0     # Remaining after this request

    # Timing constraints
    estimated_latency_ms: float = 2000.0 # Expected total latency
    user_patience_ms: float = 5000.0     # Max user is willing to wait

    # Task metadata
    task_type: str = "general"
    task_complexity: float = 0.5         # 0-1 estimated difficulty
    conversation_rhythm: float = 0.5     # 0=rapid, 1=deliberative

    # Feedback tracking
    actual_tokens_used: int = 0
    budget_efficiency: float = 1.0       # actual / budgeted (1.0 = perfect)
    allocated_at: float = field(default_factory=time.time)


# ═══ ReasoningBudget Engine ═══════════════════════════════════════


class ReasoningBudgetEngine:
    """Continuous reasoning effort allocator.

    Design: Maps DeepSeek-V4's three reasoning modes to LivingTree's
    orchestration parameters. The key innovation is treating reasoning
    as a BUDGET to be allocated, not a model to be chosen.

    Budget formula:
      thinking_tokens = base_tokens × complexity × patience × context_ratio
    """

    # Token baselines per tier (from DeepSeek-V4 paper)
    TIER_BASELINES = {
        ReasoningTier.NON_THINK: 500,
        ReasoningTier.THINK_HIGH: 4000,
        ReasoningTier.THINK_MAX: 32000,
    }

    # Tier → strategy mapping
    TIER_STRATEGIES = {
        ReasoningTier.NON_THINK: {
            "deep_probe_depth": 1,
            "self_play_rounds": 0,
            "aggregate_models": 1,
            "model_tier": "flash",
        },
        ReasoningTier.THINK_HIGH: {
            "deep_probe_depth": 2,
            "self_play_rounds": 1,
            "aggregate_models": 2,
            "model_tier": "pro",
        },
        ReasoningTier.THINK_MAX: {
            "deep_probe_depth": 3,
            "self_play_rounds": 3,
            "aggregate_models": 3,
            "model_tier": "max",
        },
    }

    # Context overhead per reasoning token (DeepSeek-V4: ~4x for thinking)
    CONTEXT_OVERHEAD_RATIO = 4.0  # Each thinking token costs ~4 context tokens

    # Minimum context required per tier
    MIN_CONTEXT = {
        ReasoningTier.NON_THINK: 4096,
        ReasoningTier.THINK_HIGH: 32000,
        ReasoningTier.THINK_MAX: 196000,  # DeepSeek-V4: 384K recommended
    }

    def __init__(self):
        self._allocations: list[ReasoningBudget] = []
        self._stats = {"total_allocated_tokens": 0, "allocations": 0}

    # ── Main Allocation ───────────────────────────────────────────

    def allocate(
        self, query: str, task_type: str = "general",
        context_available: int = 128000,
        user_patience_ms: float = 5000.0,
        conversation_rhythm: float = 0.5,
        force_tier: ReasoningTier | None = None,
    ) -> ReasoningBudget:
        """Allocate reasoning budget for a request.

        Args:
            query: User query text.
            task_type: Inferred task category.
            context_available: Total available context window (tokens).
            user_patience_ms: How long user is willing to wait (ms).
            conversation_rhythm: 0=rapid exchange, 1=deliberative.
            force_tier: Override automatic tier selection.

        Returns:
            ReasoningBudget with allocated resources and strategy parameters.
        """
        # Step 1: Estimate task complexity
        complexity = self._estimate_complexity(query, task_type)

        # Step 2: Select tier (unless forced)
        if force_tier:
            tier = force_tier
        else:
            tier = self._select_tier(complexity, user_patience_ms,
                                     context_available, conversation_rhythm)

        # Step 3: Compute thinking token budget
        base_tokens = self.TIER_BASELINES[tier]
        patience_factor = self._patience_factor(user_patience_ms)
        context_factor = self._context_factor(context_available, tier)
        thinking_tokens = int(
            base_tokens * complexity * patience_factor * context_factor
        )
        thinking_tokens = max(100, min(64000, thinking_tokens))

        # Step 4: Check context constraints
        context_needed = int(thinking_tokens * self.CONTEXT_OVERHEAD_RATIO)
        if context_needed > context_available:
            # Downgrade tier if not enough context
            if tier == ReasoningTier.THINK_MAX and context_available < self.MIN_CONTEXT[ReasoningTier.THINK_MAX]:
                tier = ReasoningTier.THINK_HIGH
                thinking_tokens = self.TIER_BASELINES[tier]
            elif tier == ReasoningTier.THINK_HIGH and context_available < self.MIN_CONTEXT[ReasoningTier.THINK_HIGH]:
                tier = ReasoningTier.NON_THINK
                thinking_tokens = self.TIER_BASELINES[tier]

        # Step 5: Get strategy parameters for selected tier
        strategies = self.TIER_STRATEGIES[tier]

        # Step 6: Adjust strategies by complexity
        if complexity > 0.8 and tier != ReasoningTier.THINK_MAX:
            strategies = dict(strategies)
            strategies["deep_probe_depth"] = min(3, strategies["deep_probe_depth"] + 1)
            strategies["self_play_rounds"] = min(3, strategies["self_play_rounds"] + 1)

        # Step 7: Estimate latency
        # Rough: 20ms per thinking token (varies by model)
        est_latency = thinking_tokens * 20.0

        # Step 8: Compute context allocation
        context_allocated = int(thinking_tokens * self.CONTEXT_OVERHEAD_RATIO)
        context_remaining = context_available - context_allocated

        budget = ReasoningBudget(
            thinking_tokens=thinking_tokens,
            tier=tier,
            deep_probe_depth=strategies["deep_probe_depth"],
            self_play_rounds=strategies["self_play_rounds"],
            aggregate_models=strategies["aggregate_models"],
            model_tier=strategies["model_tier"],
            context_available=context_available,
            context_allocated=context_allocated,
            context_remaining_after=max(0, context_remaining),
            estimated_latency_ms=est_latency,
            user_patience_ms=user_patience_ms,
            task_type=task_type,
            task_complexity=complexity,
            conversation_rhythm=conversation_rhythm,
        )

        # Track
        self._allocations.append(budget)
        self._stats["allocations"] += 1
        self._stats["total_allocated_tokens"] += thinking_tokens
        if len(self._allocations) > 100:
            self._allocations = self._allocations[-50:]

        logger.info(
            f"ReasoningBudget: [{task_type}] tier={tier} "
            f"tokens={thinking_tokens} depth={budget.deep_probe_depth} "
            f"self_play={budget.self_play_rounds} agg={budget.aggregate_models} "
            f"model={budget.model_tier} est_latency={est_latency:.0f}ms"
        )

        return budget

    # ── Complexity Estimation ─────────────────────────────────────

    @staticmethod
    def _estimate_complexity(query: str, task_type: str) -> float:
        """Estimate task difficulty 0-1 from query characteristics."""
        q = query or ""
        ql = q.lower()
        score = 0.3  # baseline

        # Length-based
        if len(q) > 500:
            score += 0.2
        elif len(q) > 200:
            score += 0.1
        elif len(q) < 30:
            score -= 0.1

        # Task-type baseline
        type_baseline = {
            "reasoning": 0.7, "analysis": 0.65, "code": 0.55,
            "decision": 0.6, "creative": 0.45, "chat": 0.3,
            "search": 0.35, "general": 0.4,
        }
        score = (score + type_baseline.get(task_type, 0.4)) / 2

        # Complexity keywords
        complex_markers = [
            "架构", "设计", "优化", "分析", "策略", "系统",
            "architecture", "design", "optimize", "analyze", "strategy",
        ]
        matches = sum(1 for m in complex_markers if m in ql)
        score += min(0.2, matches * 0.05)

        # Multi-step indicators
        multi_step = ["首先", "然后", "最后", "first", "then", "finally"]
        if any(m in ql for m in multi_step):
            score += 0.15

        # Code with error/debug → harder
        if task_type == "code" and any(k in ql for k in ["bug", "error", "错误", "修复", "fix"]):
            score += 0.1

        return max(0.1, min(1.0, score))

    # ── Tier Selection ────────────────────────────────────────────

    @staticmethod
    def _select_tier(
        complexity: float, patience_ms: float,
        context_available: int, rhythm: float,
    ) -> ReasoningTier:
        """Select reasoning tier based on multiple factors.

        High complexity → Think Max (if context permits)
        Low patience → Non-Think (fast response)
        High context → Think Max feasible
        Deliberative rhythm → Willing to wait for depth
        """
        # Non-think: always an option for simple tasks
        if complexity < 0.25:
            return ReasoningTier.NON_THINK
        if patience_ms < 1000:  # User wants instant
            return ReasoningTier.NON_THINK

        # Think Max: high complexity + enough resources
        if complexity > 0.7 and context_available >= 196000 and patience_ms > 8000:
            return ReasoningTier.THINK_MAX
        if complexity > 0.8 and rhythm > 0.6:  # Deliberative + very hard
            return ReasoningTier.THINK_MAX

        # Think High: default for medium-hard tasks
        if complexity > 0.35 and patience_ms > 2000:
            return ReasoningTier.THINK_HIGH

        return ReasoningTier.NON_THINK

    @staticmethod
    def _patience_factor(patience_ms: float) -> float:
        """Map user patience to budget multiplier (0.5x - 2.0x)."""
        if patience_ms < 1000:
            return 0.5   # Rush mode
        if patience_ms < 3000:
            return 0.8
        if patience_ms > 15000:
            return 2.0   # Very patient
        if patience_ms > 8000:
            return 1.5
        return 1.0

    @staticmethod
    def _context_factor(context_available: int, tier: ReasoningTier) -> float:
        """Map available context to budget multiplier.

        More context → can afford deeper reasoning.
        """
        min_for_tier = {
            ReasoningTier.NON_THINK: 4096,
            ReasoningTier.THINK_HIGH: 32000,
            ReasoningTier.THINK_MAX: 196000,
        }
        minimum = min_for_tier.get(tier, 4096)
        if context_available < minimum:
            return 0.5  # Constrained
        ratio = context_available / max(minimum * 4, 1)
        return min(2.0, max(0.3, ratio))

    # ── Post-execution Feedback ───────────────────────────────────

    def record_actual(
        self, budget: ReasoningBudget, actual_tokens: int,
    ) -> None:
        """Record actual tokens used vs. budgeted — for efficiency tracking."""
        budget.actual_tokens_used = actual_tokens
        budget.budget_efficiency = round(
            min(2.0, actual_tokens / max(budget.thinking_tokens, 1)), 4
        )

    def get_efficiency_for_elo(self, budget: ReasoningBudget) -> float:
        """Convert budget efficiency to Elo adjustment factor."""
        eff = budget.budget_efficiency or 1.0
        if 0.8 <= eff <= 1.2:
            return 0.05
        elif eff > 1.5:
            return -0.1
        elif eff < 0.5:
            return -0.05
        return 0.0

    # ── EMA Adaptive Thresholds ──────────────────────────────────

    def adapt_thresholds(self) -> dict[str, float]:
        """EMA-adapt TIER_BASELINES based on actual vs budget deviation.

        If models consistently overshoot the budget, increase baselines.
        If consistently undershoot (shallow answers), decrease baselines.
        Returns the adjusted baseline values.
        """
        recent = [b for b in self._allocations[-30:] if b.budget_efficiency > 0]
        if len(recent) < 10:
            return dict(self.TIER_BASELINES)

        for b in recent:
            tier = b.tier
            eff = b.budget_efficiency
            current = self.TIER_BASELINES.get(tier, 4000)
            # EMA: overshoot → reduce budget; undershoot → increase
            if eff > 1.3:   # Way over budget
                adjustment = current * 0.9
            elif eff > 1.1:  # Slightly over
                adjustment = current * 0.95
            elif eff < 0.6:  # Under-budget (potentially shallow)
                adjustment = current * 1.1
            else:
                adjustment = current
            self.TIER_BASELINES[tier] = int(
                0.85 * current + 0.15 * adjustment  # Slow EMA
            )

        logger.debug(
            f"ReasoningBudget EMA: {self.TIER_BASELINES}"
        )
        return dict(self.TIER_BASELINES)

    # ── Statistics ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        recent = self._allocations[-20:] if self._allocations else []
        tiers = {}
        for b in recent:
            t = str(b.tier)
            tiers[t] = tiers.get(t, 0) + 1

        avg_efficiency = (
            sum(b.budget_efficiency for b in recent) / max(len(recent), 1)
        ) if recent else 0.0

        return {
            "total_allocations": self._stats["allocations"],
            "total_tokens_allocated": self._stats["total_allocated_tokens"],
            "tier_distribution": tiers,
            "avg_budget_efficiency": round(avg_efficiency, 3),
            "avg_complexity": round(
                sum(b.task_complexity for b in recent) / max(len(recent), 1), 3
            ) if recent else 0.0,
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_rb: Optional[ReasoningBudgetEngine] = None
_rb_lock = threading.Lock()


def get_reasoning_budget() -> ReasoningBudgetEngine:
    global _rb
    if _rb is None:
        with _rb_lock:
            if _rb is None:
                _rb = ReasoningBudgetEngine()
    return _rb


__all__ = [
    "ReasoningBudgetEngine", "ReasoningBudget", "ReasoningTier",
    "get_reasoning_budget",
]
