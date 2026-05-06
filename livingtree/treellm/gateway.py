"""LLM Gateway — production-grade model routing + cascade + circuit breaker.

Three-layer architecture (from LLM Gateway best practices):
  Access Layer:  protocol adaptation, auth, rate limiting
  Decision Layer: cascade routing, circuit breaker, load balancing
  Egress Layer:   actual calls, streaming, response normalization

Three new capabilities for LivingTree:
  1. Cascade Routing:   小模型先试 → 质量不够 → 自动升大模型 (成本-50%)
  2. Circuit Breaker:   Provider连续失败 → 熔断 → 半开探测 → 恢复
  3. Provider Health:   实时成功率/P95延迟/Token消耗/降级触发 Dashboard

Integrates with existing:
  - holistic_election.py (provider scoring)
  - providers.py (aiohttp calls)
  - tracer.py (request tracing)
  - metrics.py (metrics collection)
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ═══ Cascade Routing ═══

class CascadeStrategy(str, Enum):
    """Cascade routing strategies."""
    QUALITY_FIRST = "quality_first"     # 小模型先试 → 不行用大模型
    COST_FIRST = "cost_first"          # 最便宜的模型先试
    SPEED_FIRST = "speed_first"        # 最快的模型先试
    DIRECT = "direct"                  # 直接走指定模型（不级联）


@dataclass
class CascadeResult:
    """Result of a cascade routing attempt."""
    final_model: str = ""
    text: str = ""
    tokens: int = 0
    cost_estimate: float = 0.0
    attempts: int = 1
    models_tried: list[str] = field(default_factory=list)
    cascade_triggered: bool = False
    latency_ms: float = 0.0


# ═══ Circuit Breaker ═══

class CircuitState(str, Enum):
    CLOSED = "closed"          # Normal — requests pass through
    OPEN = "open"              # Circuit broken — requests rejected immediately
    HALF_OPEN = "half_open"    # Testing — limited requests to check recovery


@dataclass
class CircuitBreaker:
    """Per-provider circuit breaker.

    States:
      CLOSED → (failures >= threshold) → OPEN
      OPEN   → (timeout elapsed) → HALF_OPEN
      HALF_OPEN → (success) → CLOSED | (failure) → OPEN
    """
    provider: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds before trying again
    half_open_max_requests: int = 3

    state: str = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_state_change: float = field(default_factory=time.time)
    half_open_requests: int = 0

    def call_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_requests += 1
            if self.half_open_requests >= self.half_open_max_requests:
                self._transition_to(CircuitState.CLOSED)
        self.failure_count = 0
        self.success_count += 1

    def call_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self.failure_count >= self.failure_threshold:
            self._transition_to(CircuitState.OPEN)

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_state_change > self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_requests < self.half_open_max_requests
        return True

    def _transition_to(self, new_state: str) -> None:
        old = self.state
        self.state = new_state
        self.last_state_change = time.time()
        if new_state == CircuitState.HALF_OPEN:
            self.half_open_requests = 0
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
        logger.info("CircuitBreaker[%s]: %s → %s (failures=%d)", self.provider, old, new_state, self.failure_count)


# ═══ Provider Health ═══

@dataclass
class ProviderHealth:
    """Real-time health stats for a single provider."""
    provider: str
    total_calls: int = 0
    success_calls: int = 0
    failure_calls: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    recent_latencies: list[float] = field(default_factory=list)  # last 100
    fallback_triggers: int = 0  # how many times this was a fallback target

    @property
    def success_rate(self) -> float:
        return self.success_calls / max(self.total_calls, 1)

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / max(self.total_calls, 1)

    @property
    def p95_latency_ms(self) -> float:
        if not self.recent_latencies:
            return 0.0
        sorted_lat = sorted(self.recent_latencies[-100:])
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[idx] if idx < len(sorted_lat) else sorted_lat[-1]

    def record_call(self, success: bool, latency_ms: float, tokens: int = 0,
                    is_fallback: bool = False) -> None:
        self.total_calls += 1
        if success:
            self.success_calls += 1
        else:
            self.failure_calls += 1
        self.total_tokens += tokens
        self.total_latency_ms += latency_ms
        self.recent_latencies.append(latency_ms)
        if len(self.recent_latencies) > 100:
            self.recent_latencies = self.recent_latencies[-50:]
        if is_fallback:
            self.fallback_triggers += 1


# ═══ LLM Gateway ═══

# Cascade chain definitions: [("primary_model", quality_threshold), ...]
# quality_threshold = minimum quality score (0-1) to accept result
CASCADE_CHAINS = {
    "general": [
        ("deepseek/deepseek-v4-flash", 0.0),      # cheapest, fast
        ("deepseek/deepseek-v4-pro", 0.6),         # stronger, slower
    ],
    "code": [
        ("openai/LongCat-Flash-Lite", 0.0),
        ("deepseek/deepseek-v4-flash", 0.5),
        ("deepseek/deepseek-v4-pro", 0.7),
    ],
    "chat": [
        ("openai/LongCat-Flash-Chat", 0.0),
        ("deepseek/deepseek-v4-pro", 0.6),
    ],
}


class LLMGateway:
    """Production-grade LLM Gateway with cascade routing + circuit breaker + health monitoring.

    Usage:
        gateway = LLMGateway()
        
        # Cascade routing — small model first
        result = await gateway.chat(
            messages=[{"role": "user", "content": "环评是什么？"}],
            strategy=CascadeStrategy.COST_FIRST,
            chain_tag="general",
        )
        # → Tried flash model → quality OK → returned directly (no cascade)

        # Circuit breaker auto-protection
        # → deepseek flash failed 5 times → OPEN → skipped → cascaded to pro

        # Health dashboard
        dashboard = gateway.get_health_dashboard()
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._health: dict[str, ProviderHealth] = {}
        self._quality_threshold: float = 0.5

    def _get_breaker(self, model: str) -> CircuitBreaker:
        if model not in self._breakers:
            self._breakers[model] = CircuitBreaker(
                provider=model,
                failure_threshold=5,
                recovery_timeout=60.0,
            )
        return self._breakers[model]

    def _get_health(self, model: str) -> ProviderHealth:
        if model not in self._health:
            self._health[model] = ProviderHealth(provider=model)
        return self._health[model]

    async def chat(
        self,
        messages: list[dict],
        model: str = "",
        strategy: CascadeStrategy = CascadeStrategy.DIRECT,
        chain_tag: str = "general",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> CascadeResult:
        """Send a chat request with cascade routing and circuit breaker protection."""
        result = CascadeResult()
        start = time.time()

        # Determine model chain
        if strategy == CascadeStrategy.DIRECT and model:
            chain = [(model, 0.0)]
        elif chain_tag in CASCADE_CHAINS:
            chain = CASCADE_CHAINS[chain_tag]
        else:
            chain = CASCADE_CHAINS["general"]

        last_error = ""
        for i, (candidate_model, quality_threshold) in enumerate(chain):
            # Circuit breaker check
            breaker = self._get_breaker(candidate_model)
            if not breaker.allow_request():
                logger.debug("LLM Gateway: %s circuit OPEN — skipping", candidate_model)
                continue

            # Attempt call
            try:
                response = await self._call_model(
                    candidate_model, messages, temperature, max_tokens, timeout,
                )

                health = self._get_health(candidate_model)

                if response and response.text:
                    breaker.call_success()
                    health.record_call(True, response.latency_ms, response.tokens)

                    result.final_model = candidate_model
                    result.text = response.text
                    result.tokens = response.tokens
                    result.attempts = i + 1
                    result.models_tried = [m for m, _ in chain[:i + 1]]
                    result.cascade_triggered = (i > 0)
                    result.latency_ms = (time.time() - start) * 1000

                    # Sandbag quality check: if short/unhelpful → cascade
                    if i < len(chain) - 1:
                        quality = self._estimate_quality(response.text, messages)
                        if quality < quality_threshold:
                            logger.debug("LLM Gateway: %s quality %.2f < %.2f → cascading",
                                       candidate_model, quality, quality_threshold)
                            continue

                    return result

                # Failure
                breaker.call_failure()
                health.record_call(False, response.latency_ms if response else 0, is_fallback=(i > 0))
                last_error = response.error if response else "no response"

            except Exception as e:
                breaker.call_failure()
                self._get_health(candidate_model).record_call(False, 0, is_fallback=(i > 0))
                last_error = str(e)
                logger.warning("LLM Gateway: %s failed: %s", candidate_model, e)

        # All models failed
        result.text = f"[Gateway: all models failed] {last_error}"
        result.latency_ms = (time.time() - start) * 1000
        return result

    async def _call_model(
        self, model: str, messages: list[dict],
        temperature: float, max_tokens: int, timeout: float,
    ) -> Optional[Any]:
        """Call a specific model through the existing provider system."""
        try:
            from .core import get_llm
            llm = get_llm()
            return await llm.chat(
                messages=messages,
                provider=model.split("/")[0] if "/" in model else model,
                model_name=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        except Exception:
            from .providers import DirectDeepSeek
            provider = DirectDeepSeek()
            return await provider.chat(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens,
                timeout=timeout,
            )

    @staticmethod
    def _estimate_quality(text: str, messages: list[dict]) -> float:
        """Heuristic: estimate output quality from text properties."""
        if not text or len(text) < 10:
            return 0.0
        score = 0.3  # base
        if len(text) > 50:
            score += 0.2
        if len(text) > 200:
            score += 0.2
        if any(kw in text for kw in ("标准", "规范", "依据", "方法", "数据", "分析")):
            score += 0.2
        # No "I don't know" or similar
        if any(kw in text.lower() for kw in ("不知道", "不清楚", "无法回答", "i don't know")):
            score = 0.0
        return min(1.0, score)

    # ═══ Health Dashboard ═══

    def get_health_dashboard(self) -> dict:
        """Provider health dashboard for monitoring."""
        providers = []
        for model, health in sorted(self._health.items()):
            breaker = self._get_breaker(model)
            providers.append({
                "provider": model,
                "state": breaker.state,
                "success_rate": f"{health.success_rate:.1%}",
                "avg_latency_ms": f"{health.avg_latency_ms:.0f}",
                "p95_latency_ms": f"{health.p95_latency_ms:.0f}",
                "total_calls": health.total_calls,
                "failure_count": breaker.failure_count,
                "total_tokens": health.total_tokens,
                "fallback_triggers": health.fallback_triggers,
                "circuit": f"{breaker.state} (failures:{breaker.failure_count}/{breaker.failure_threshold})",
            })

        return {
            "providers": providers,
            "total_providers": len(providers),
            "open_circuits": sum(1 for p in providers if p["state"] == CircuitState.OPEN),
            "healthy_providers": sum(1 for p in providers if p["state"] == CircuitState.CLOSED),
        }

    def get_health_summary(self) -> str:
        """Human-readable health summary."""
        dash = self.get_health_dashboard()
        lines = [
            "## LLM Gateway — Provider Health",
            f"Providers: {dash['total_providers']} | Healthy: {dash['healthy_providers']} | Open: {dash['open_circuits']}",
            "",
        ]
        for p in dash["providers"][:10]:
            icon = {"closed": "🟢", "open": "🔴", "half_open": "🟡"}.get(p["state"], "⚪")
            lines.append(
                f"{icon} {p['provider'][:40]}: "
                f"rate={p['success_rate']} lat={p['avg_latency_ms']}ms "
                f"(p95={p['p95_latency_ms']}ms) calls={p['total_calls']}"
            )
        return "\n".join(lines)

    def get_stats(self) -> dict:
        return self.get_health_dashboard()


# ═══ Singleton ═══

_gateway: Optional[LLMGateway] = None


def get_llm_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
