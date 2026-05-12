"""Circuit Breaker for TreeLLM providers.

Design: Token中转站稳定性第1重保障 — 多源备份 + 毫秒级切换。

Three states (standard circuit breaker pattern):
  CLOSED   → Normal operation, requests pass through
  OPEN     → Provider is failing, requests are blocked
  HALF_OPEN → Testing if provider has recovered

Triggers:
  - Consecutive failures >= threshold → OPEN (isolate for cooldown)
  - Cooldown expires → HALF_OPEN (allow 1 probe request)
  - Probe succeeds → CLOSED (resume normal)
  - Probe fails → OPEN (reset cooldown)

Integration:
  TreeLLM._request_with_retry() calls breaker.before_call(name) first.
  HolisticElection._score_all() skips providers with breaker.is_open(name).

  This prevents the "王教授噩梦": one failing provider doesn't take down the app.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from loguru import logger


class BreakerState(str, Enum):
    CLOSED = "closed"        # Normal — requests flow
    OPEN = "open"            # Tripped — requests blocked
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class BreakerStats:
    """Per-provider circuit breaker statistics."""
    provider: str
    state: BreakerState = BreakerState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    consecutive_failures: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    tripped_at: float = 0.0
    trip_count: int = 0       # How many times has this breaker tripped
    total_blocked: int = 0    # Requests blocked while OPEN


class CircuitBreaker:
    """Multi-provider circuit breaker with per-provider state tracking.

    Attributes:
        failure_threshold: Consecutive failures to trip breaker (default 3).
        cooldown_seconds: Time to stay OPEN before allowing probe (default 30).
        half_open_max: Max probe requests in HALF_OPEN before deciding (default 1).
        recovery_threshold: Consecutive successes in HALF_OPEN to CLOSE (default 2).
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        recovery_threshold: int = 2,
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.recovery_threshold = recovery_threshold
        self._providers: dict[str, BreakerStats] = defaultdict(
            lambda: BreakerStats(provider="")
        )
        self._half_open_tokens: dict[str, int] = defaultdict(int)

    # ── Core API ──

    def before_call(self, provider: str) -> bool:
        """Check if request should proceed. Returns True if allowed.

        Call this BEFORE every provider request.
        """
        stats = self._ensure_stats(provider)

        if stats.state == BreakerState.CLOSED:
            return True

        if stats.state == BreakerState.OPEN:
            # Check if cooldown has expired
            elapsed = time.time() - stats.tripped_at
            if elapsed >= self.cooldown_seconds:
                # Transition to HALF_OPEN — allow one probe
                stats.state = BreakerState.HALF_OPEN
                self._half_open_tokens[provider] = 0
                logger.info(
                    f"CircuitBreaker: {provider} → HALF_OPEN "
                    f"(cooldown {elapsed:.1f}s >= {self.cooldown_seconds}s)"
                )
                return True
            else:
                stats.total_blocked += 1
                logger.debug(
                    f"CircuitBreaker: {provider} BLOCKED "
                    f"(OPEN, {elapsed:.1f}s remaining)"
                )
                return False

        if stats.state == BreakerState.HALF_OPEN:
            # Allow limited probe requests
            token_count = self._half_open_tokens.get(provider, 0)
            if token_count < 2:  # Allow up to 2 probes
                self._half_open_tokens[provider] = token_count + 1
                return True
            else:
                stats.total_blocked += 1
                return False

        return True

    def on_success(self, provider: str, latency_ms: float = 0) -> None:
        """Report a successful call. Transitions HALF_OPEN → CLOSED."""
        stats = self._ensure_stats(provider)
        stats.success_count += 1
        stats.consecutive_failures = 0
        stats.last_success_time = time.time()

        if stats.state == BreakerState.HALF_OPEN:
            # Count consecutive successes
            token_count = self._half_open_tokens.get(provider, 0)
            if token_count >= self.recovery_threshold:
                stats.state = BreakerState.CLOSED
                self._half_open_tokens.pop(provider, None)
                logger.info(f"CircuitBreaker: {provider} → CLOSED (recovered)")

    def on_failure(self, provider: str, error: str = "") -> None:
        """Report a failed call. May trip breaker."""
        stats = self._ensure_stats(provider)
        stats.failure_count += 1
        stats.consecutive_failures += 1
        stats.last_failure_time = time.time()

        if stats.state == BreakerState.HALF_OPEN:
            # Probe failed → back to OPEN, reset cooldown
            stats.state = BreakerState.OPEN
            stats.tripped_at = time.time()
            stats.trip_count += 1
            self._half_open_tokens.pop(provider, None)
            logger.warning(
                f"CircuitBreaker: {provider} probe FAILED → OPEN "
                f"(error: {error[:100]})"
            )
        elif stats.consecutive_failures >= self.failure_threshold:
            # Trip the breaker
            stats.state = BreakerState.OPEN
            stats.tripped_at = time.time()
            stats.trip_count += 1
            logger.warning(
                f"CircuitBreaker: {provider} TRIPPED → OPEN "
                f"({stats.consecutive_failures} consecutive failures, "
                f"cooldown {self.cooldown_seconds}s)"
            )

    def is_open(self, provider: str) -> bool:
        """Check if breaker is currently OPEN (blocking requests)."""
        stats = self._providers.get(provider)
        if not stats:
            return False
        if stats.state != BreakerState.OPEN:
            return False
        # Double-check: has cooldown expired?
        if (time.time() - stats.tripped_at) >= self.cooldown_seconds:
            return False
        return True

    def force_close(self, provider: str) -> None:
        """Manually reset a provider's breaker to CLOSED."""
        stats = self._ensure_stats(provider)
        stats.state = BreakerState.CLOSED
        stats.consecutive_failures = 0
        self._half_open_tokens.pop(provider, None)
        logger.info(f"CircuitBreaker: {provider} → CLOSED (manual reset)")

    def force_open(self, provider: str) -> None:
        """Manually trip a provider's breaker to OPEN."""
        stats = self._ensure_stats(provider)
        stats.state = BreakerState.OPEN
        stats.tripped_at = time.time()
        stats.trip_count += 1
        logger.info(f"CircuitBreaker: {provider} → OPEN (manual trip)")

    # ── Query ──

    def get_stats(self, provider: str) -> BreakerStats:
        return self._ensure_stats(provider)

    def all_stats(self) -> dict[str, BreakerStats]:
        return dict(self._providers)

    def blocked_providers(self) -> list[str]:
        """List all providers currently blocked by circuit breaker."""
        return [p for p in self._providers if self.is_open(p)]

    def healthy_providers(self, all_providers: list[str]) -> list[str]:
        """Filter list to only providers with CLOSED or HALF_OPEN breakers."""
        return [p for p in all_providers if not self.is_open(p)]

    # ── Internal ──

    def _ensure_stats(self, provider: str) -> BreakerStats:
        if provider not in self._providers:
            self._providers[provider] = BreakerStats(provider=provider)
        return self._providers[provider]


# ── Singleton ──

_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    global _breaker
    if _breaker is None:
        _breaker = CircuitBreaker()
    return _breaker
