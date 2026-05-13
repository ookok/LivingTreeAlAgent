"""TokenCircuitBreaker — Progressive budget-aware throttling with graceful degradation.

Integrates existing TokenAccountant (budget tracking) with circuit-breaker patterns.
As daily budget depletes, progressively:
  1. Reduces top_k (fewer parallel models)
  2. Disables aggregation (no multi-model fusion)
  3. Caps max_tokens (shorter responses)
  4. Switches pro→flash (cheaper models)
  5. Circuit OPEN → only L1 flash, no optional operations

Integration:
    tcb = get_token_circuit_breaker()
    top_k, max_tokens, aggregate = tcb.allocate(sid, budget_router, top_k, max_tokens)
    tcb.actual(sid, tokens_used)
"""

from __future__ import annotations

import time
from collections import defaultdict
from enum import StrEnum
from typing import Any, Optional

from loguru import logger


class BudgetState(StrEnum):
    NORMAL = "normal"         # >50% budget remaining
    WARNING = "warning"       # 20-50% remaining
    THROTTLED = "throttled"   # 5-20% remaining
    OPEN = "open"             # <5% — circuit open, minimal mode


class TokenCircuitBreaker:
    """Budget-aware circuit breaker with graceful degradation."""

    _instance: Optional["TokenCircuitBreaker"] = None

    @classmethod
    def instance(cls) -> "TokenCircuitBreaker":
        if cls._instance is None:
            cls._instance = TokenCircuitBreaker()
        return cls._instance

    def __init__(self):
        self._per_request: dict[str, int] = {}  # request_id → allocated tokens
        self._state: BudgetState = BudgetState.NORMAL
        self._degradations = 0

    def allocate(self, request_id: str, budget_router: Any,
                 top_k: int, max_tokens: int) -> tuple[int, int, bool]:
        """Allocate token budget for this request.

        Returns adjusted (top_k, max_tokens, aggregate).
        """
        aggregate = top_k > 1

        try:
            status = budget_router.status()
            total_remaining = sum(
                s.get("daily_limit", 2.0) - s.get("daily_spent", 0)
                for s in status.values()
                if not s.get("is_free")
            )
            total_limit = sum(s.get("daily_limit", 2.0) for s in status.values()
                            if not s.get("is_free"))
        except Exception:
            total_remaining = 999
            total_limit = 999

        if total_limit <= 0:
            self._state = BudgetState.NORMAL
            return top_k, max_tokens, aggregate

        ratio = total_remaining / max(total_limit, 0.01)

        # Determine circuit state
        if ratio > 0.5:
            self._state = BudgetState.NORMAL
        elif ratio > 0.2:
            self._state = BudgetState.WARNING
        elif ratio > 0.05:
            self._state = BudgetState.THROTTLED
        else:
            self._state = BudgetState.OPEN

        # Progressive degradation
        if self._state == BudgetState.OPEN:
            logger.warning("TokenCircuitBreaker: OPEN — minimal mode")
            top_k = 1
            max_tokens = min(max_tokens, 512)
            aggregate = False
            self._degradations += 1
        elif self._state == BudgetState.THROTTLED:
            top_k = max(1, top_k - 1)
            max_tokens = min(max_tokens, 1024)
            aggregate = False
            self._degradations += 1
        elif self._state == BudgetState.WARNING:
            max_tokens = min(max_tokens, 2048)

        self._per_request[request_id] = top_k * max_tokens
        return top_k, max_tokens, aggregate

    def actual(self, request_id: str, tokens: int) -> None:
        """Report actual token usage for this request."""
        allocated = self._per_request.pop(request_id, 0)
        if allocated > 0 and tokens > allocated * 1.5:
            logger.warning(f"TokenCircuitBreaker: over budget ({tokens}/{allocated})")

    @property
    def state(self) -> BudgetState:
        return self._state

    def stats(self) -> dict:
        return {
            "state": self._state.value,
            "degradations": self._degradations,
            "pending_requests": len(self._per_request),
        }


_tcb: Optional[TokenCircuitBreaker] = None


def get_token_circuit_breaker() -> TokenCircuitBreaker:
    global _tcb
    if _tcb is None:
        _tcb = TokenCircuitBreaker()
    return _tcb


__all__ = ["TokenCircuitBreaker", "BudgetState", "get_token_circuit_breaker"]
