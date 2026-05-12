"""Token Accountant — Cross-layer marginal token allocation framework.

Based on arXiv:2605.01214 (Zhu, UIUC 2026):
  "Agentic AI Systems Should Be Designed as Marginal Token Allocators"

Core equation (shared across all 4 layers):
  marginal_benefit ≥ marginal_cost + latency_cost + risk_cost

Four layers must see a COMMON price vector:
  Layer 1 (Router):  routing_cost, provider_costs
  Layer 2 (Agent):   action_costs, plan/execute/verify/defer prices
  Layer 3 (Serving): prefill_cost, decode_cost, cache_savings
  Layer 4 (Training): trace_value, learning_roi

Today's stacks fail because each layer optimizes locally.
Token Accountant provides shared shadow prices across all layers.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ── Layer Enum ──

class AllocationLayer(str, Enum):
    ROUTER = "router"       # Which model to use
    AGENT = "agent"          # Plan/act/verify/defer
    SERVING = "serving"      # Prefill/decode/cache
    TRAINING = "training"    # Which traces to learn from


# ── Data Types ──

@dataclass
class TokenAllocation:
    """A single token allocation decision recorded across layers."""
    layer: AllocationLayer
    action: str              # "ping", "plan", "execute", "prefill", "decode", "cache_hit"
    tokens_spent: int
    cost_yuan: float = 0.0
    latency_ms: float = 0.0
    benefit_score: float = 0.0  # Estimated marginal benefit [0,1]
    risk_factor: float = 0.0    # Estimated risk [0,1]
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""

    @property
    def marginal_cost(self) -> float:
        """Total marginal cost = token cost + latency cost + risk cost."""
        return self.cost_yuan + self.latency_ms * 0.0001 + self.risk_factor * self.cost_yuan

    @property
    def roi(self) -> float:
        """Return on investment: benefit / cost."""
        cost = self.marginal_cost
        return self.benefit_score / max(1e-9, cost)


@dataclass
class LayerBudget:
    """Per-layer budget and pricing shadow prices."""
    layer: AllocationLayer
    token_budget: int = 100_000
    tokens_spent: int = 0
    avg_cost_per_1k: float = 0.0
    avg_benefit: float = 0.0
    avg_roi: float = 0.0
    allocation_count: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.token_budget - self.tokens_spent)

    @property
    def utilization(self) -> float:
        return self.tokens_spent / max(1, self.token_budget)


@dataclass
class PriceVector:
    """Shared shadow prices visible to ALL layers.

    This is the paper's key missing piece in current production stacks.
    """
    # Router prices
    ping_token_cost: int = 50          # Cost to ping one provider
    max_ping_providers: int = 5        # Don't ping more than N providers

    # Agent prices
    plan_token_cost: int = 200          # Cost to generate a plan step
    execute_token_cost: int = 500       # Cost to execute one action
    verify_token_cost: int = 300        # Cost to verify output
    defer_cost: int = 0                 # Defer to human = free (but has latency cost)

    # Serving prices
    prefill_cost_per_1k: float = 0.001  # CNY per 1K tokens
    decode_cost_per_1k: float = 0.002   # Decode is ~2x prefill
    cache_hit_savings: float = 0.90     # Cache hit saves 90% cost
    congestion_multiplier: float = 1.0  # >1.0 when server is busy

    # Training prices
    min_trace_roi: float = 0.5          # Only learn from traces with ROI > this

    # Global
    risk_free_rate: float = 0.01        # Baseline risk cost
    max_roi_target: float = 0.8         # Target ROI for allocation decisions


class TokenAccountant:
    """Cross-layer marginal token allocation framework.

    All four layers call this BEFORE spending tokens to check:
      should_allocate(layer, action, estimated_tokens, expected_benefit, risk)

    Returns True if marginal benefit >= marginal cost.
    """

    def __init__(self, total_budget: int = 1_000_000):
        self.total_budget = total_budget
        self.total_spent = 0
        self.prices = PriceVector()
        self.budgets: dict[AllocationLayer, LayerBudget] = {
            layer: LayerBudget(layer=layer, token_budget=total_budget // 4)
            for layer in AllocationLayer
        }
        self._history: list[TokenAllocation] = []
        self._session_allocations: dict[str, list[TokenAllocation]] = defaultdict(list)

    # ── Core Decision API ──

    def should_allocate(
        self,
        layer: AllocationLayer,
        action: str,
        estimated_tokens: int,
        expected_benefit: float,
        risk_factor: float = 0.0,
        session_id: str = "",
    ) -> bool:
        """Check if a token allocation passes the marginal benefit test.

        Args:
            layer: Which layer is requesting (router/agent/serving/training).
            action: Specific action ("ping", "plan", "execute", "prefill", etc.).
            estimated_tokens: How many tokens this action will consume.
            expected_benefit: Estimated marginal benefit [0, 1].
            risk_factor: Estimated risk of failure [0, 1].
            session_id: Optional session identifier.

        Returns:
            True if allocation is justified (benefit >= cost).
        """
        budget = self.budgets[layer]

        # Budget check
        if budget.tokens_spent + estimated_tokens > budget.token_budget:
            logger.debug(
                f"TokenAccountant: REJECT {layer.value}/{action} "
                f"({estimated_tokens} tokens exceeds {budget.remaining} remaining)"
            )
            return False

        # Compute marginal cost
        est_cost = self._estimate_cost(layer, action, estimated_tokens)
        latency_cost = self._estimate_latency(layer, action)
        risk_cost = risk_factor * est_cost

        marginal_cost = est_cost + latency_cost + risk_cost

        # Paper's first-order condition: MB >= MC + LC + RC
        passes = expected_benefit >= marginal_cost

        if not passes:
            logger.debug(
                f"TokenAccountant: REJECT {layer.value}/{action} "
                f"(benefit {expected_benefit:.3f} < cost {marginal_cost:.3f})"
            )

        return passes

    def record_allocation(
        self,
        layer: AllocationLayer,
        action: str,
        tokens_spent: int,
        actual_benefit: float = 0.0,
        latency_ms: float = 0.0,
        risk_factor: float = 0.0,
        session_id: str = "",
    ) -> TokenAllocation:
        """Record an actual allocation AFTER it was executed.

        Updates budgets, shadow prices, and ROI tracking.
        """
        cost = self._estimate_cost(layer, action, tokens_spent)
        alloc = TokenAllocation(
            layer=layer,
            action=action,
            tokens_spent=tokens_spent,
            cost_yuan=cost,
            latency_ms=latency_ms,
            benefit_score=actual_benefit,
            risk_factor=risk_factor,
            session_id=session_id,
        )

        # Update budgets
        budget = self.budgets[layer]
        budget.tokens_spent += tokens_spent
        self.total_spent += tokens_spent
        budget.allocation_count += 1

        # Exponential moving average updates
        alpha = 1.0 / (budget.allocation_count + 1)
        budget.avg_cost_per_1k = (1 - alpha) * budget.avg_cost_per_1k + alpha * cost * 1000 / max(1, tokens_spent)
        budget.avg_benefit = (1 - alpha) * budget.avg_benefit + alpha * actual_benefit
        budget.avg_roi = (1 - alpha) * budget.avg_roi + alpha * alloc.roi

        # History
        self._history.append(alloc)
        if session_id:
            self._session_allocations[session_id].append(alloc)

        return alloc

    # ── Cross-Layer Optimization ──

    def get_price_vector(self) -> PriceVector:
        """Get current shadow prices — shared across ALL layers.

        This is the paper's key prescription: unified price discovery.
        """
        # Adjust congestion multiplier based on total utilization
        utilization = self.total_spent / max(1, self.total_budget)
        self.prices.congestion_multiplier = 1.0 + max(0, utilization - 0.5) * 2.0

        # Adjust agent prices based on router efficiency
        router_budget = self.budgets[AllocationLayer.ROUTER]
        if router_budget.avg_roi > 0.8:
            # Router is efficient → agent can be more generous
            self.prices.max_ping_providers = 8
        else:
            self.prices.max_ping_providers = 3

        return self.prices

    def optimal_layer_split(self) -> dict[str, float]:
        """Compute Pareto-optimal token allocation across layers.

        Based on historical ROI per layer, rebalance budgets.
        """
        total_roi = sum(b.avg_roi for b in self.budgets.values())
        if total_roi <= 0:
            return {layer.value: 0.25 for layer in AllocationLayer}

        return {
            layer.value: self.budgets[layer].avg_roi / total_roi
            for layer in AllocationLayer
        }

    # ── Query API ──

    def session_summary(self, session_id: str) -> dict:
        """Get token allocation summary for a session."""
        allocs = self._session_allocations.get(session_id, [])
        if not allocs:
            return {"total_tokens": 0, "total_cost": 0.0, "layers": {}}

        by_layer = defaultdict(lambda: {"tokens": 0, "cost": 0.0, "benefit": 0.0})
        for a in allocs:
            by_layer[a.layer.value]["tokens"] += a.tokens_spent
            by_layer[a.layer.value]["cost"] += a.cost_yuan
            by_layer[a.layer.value]["benefit"] += a.benefit_score

        total_tokens = sum(v["tokens"] for v in by_layer.values())
        total_cost = sum(v["cost"] for v in by_layer.values())

        return {
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 6),
            "avg_benefit": round(
                sum(v["benefit"] for v in by_layer.values()) / max(1, len(allocs)), 3
            ),
            "layers": dict(by_layer),
        }

    def global_stats(self) -> dict:
        return {
            "total_budget": self.total_budget,
            "total_spent": self.total_spent,
            "utilization": round(self.total_spent / max(1, self.total_budget), 3),
            "layers": {
                layer.value: {
                    "budget": b.token_budget,
                    "spent": b.tokens_spent,
                    "utilization": round(b.utilization, 3),
                    "avg_roi": round(b.avg_roi, 3),
                    "avg_benefit": round(b.avg_benefit, 3),
                }
                for layer, b in self.budgets.items()
            },
            "optimal_split": self.optimal_layer_split(),
        }

    # ── Internal ──

    def _estimate_cost(self, layer: AllocationLayer, action: str, tokens: int) -> float:
        """Estimate CNY cost for an action."""
        if layer == AllocationLayer.SERVING:
            if action == "prefill":
                return tokens / 1000 * self.prices.prefill_cost_per_1k
            elif action == "decode":
                return tokens / 1000 * self.prices.decode_cost_per_1k
            elif action == "cache_hit":
                return tokens / 1000 * self.prices.prefill_cost_per_1k * (1 - self.prices.cache_hit_savings)

        # Default: rough cost estimate
        return tokens / 1000 * 0.0015 * self.prices.congestion_multiplier

    def _estimate_latency(self, layer: AllocationLayer, action: str) -> float:
        """Estimate latency cost (in same units as benefit)."""
        base = {
            "ping": 0.001,
            "plan": 0.005,
            "execute": 0.01,
            "prefill": 0.002,
            "decode": 0.008,
            "cache_hit": 0.0001,
        }
        return base.get(action, 0.005) * self.prices.congestion_multiplier

    def reset_session(self, session_id: str) -> None:
        """Clear session allocations (for new conversation)."""
        self._session_allocations.pop(session_id, None)


# ── Singleton ──

_accountant: Optional[TokenAccountant] = None


def get_token_accountant() -> TokenAccountant:
    global _accountant
    if _accountant is None:
        _accountant = TokenAccountant()
    return _accountant
