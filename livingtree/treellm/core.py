"""TreeLLM — Lightweight multi-provider LLM routing engine.

Replaces LiteLLM for LivingTree's specific needs. Features:
- Direct HTTP calls (no heavy dependency)
- Multi-provider tree with automatic failover
- Streaming support
- Cost/latency tracking
- Built-in tiny classifier for smart routing

Architecture:
    TreeLLM
    ├── providers (list of Provider)
    │   ├── DeepSeekProvider   (api.deepseek.com)
    │   ├── LongCatProvider    (api.longcat.chat)
    │   └── OpenCodeProvider   (localhost:4096)
    ├── router (RoutingStrategy)
    │   ├── ElectRouter       (ping all, pick first alive)
    │   ├── CostRouter        (cheapest first)
    │   ├── LatencyRouter     (fastest first)
    │   └── SmartRouter       (classifier-based)
    └── classifier (TinyClassifier)
        └── TF-IDF + Logistic Regression (pure numpy)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from .classifier import TinyClassifier
from .providers import Provider, ProviderResult, create_deepseek_provider, create_longcat_provider


@dataclass
class RouterStats:
    provider: str
    calls: int = 0
    successes: int = 0
    failures: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    last_latency_ms: float = 0.0
    last_error: str = ""

    @property
    def success_rate(self) -> float:
        return self.successes / max(self.calls, 1)

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / max(self.calls, 1)


class TreeLLM:

    def __init__(self):
        self._providers: dict[str, Provider] = {}
        self._stats: dict[str, RouterStats] = {}
        self._elected: str = ""
        self._classifier = TinyClassifier()

    # ── Provider management ──

    def add_provider(self, provider: Provider) -> None:
        self._providers[provider.name] = provider
        self._stats[provider.name] = RouterStats(provider=provider.name)

    def remove_provider(self, name: str) -> None:
        self._providers.pop(name, None)

    def get_provider(self, name: str) -> Provider | None:
        return self._providers.get(name)

    @property
    def provider_names(self) -> list[str]:
        return list(self._providers.keys())

    # ── Routing ──

    async def elect(self, candidates: list[str] | None = None) -> str:
        """Elect best provider: holistic scoring (latency + quality + cost + capability)."""
        names = candidates or list(self._providers.keys())
        from .holistic_election import get_election
        election = get_election()

        # Holistic scoring
        free_models = []  # populated externally
        scored = await election.score_providers(names, self._providers, free_models)
        if scored:
            best = scored[0]
            self._elected = best.name
            logger.info(
                f"Elected {best.name}: "
                f"score={best.total:.2f} "
                f"latency={best.latency_ms:.0f}ms "
                f"quality={best.scores.get('quality',0):.1%} "
                f"match={best.capability_match:.1%}"
            )
            return best.name

        self._elected = ""
        return ""

    async def smart_route(self, prompt: str, candidates: list[str] | None = None) -> str:
        names = candidates or list(self._providers.keys())
        alive = []
        for name in names:
            p = self._providers.get(name)
            if p:
                ok, _ = await p.ping()
                if ok:
                    alive.append(name)

        if not alive:
            return ""

        if len(alive) == 1:
            return alive[0]

        # Step 1: TinyClassifier (fast, keyword-based)
        route = self._classifier.predict(prompt, alive, self._stats)
        if route and route in alive:
            score = self._classifier._last_score if hasattr(self._classifier, '_last_score') else 0.5
            if score > 0.3:  # High confidence → use classifier
                return route

        # Step 2: UnifiedSkillSystem (semantic, full-text based)
        try:
            from ..dna.unified_skill_system import get_skill_system
            router = get_skill_system()
            decision = router.route(prompt)
            for candidate in decision.providers:
                if candidate.name in alive:
                    return candidate.name
        except Exception:
            pass

        # Step 3: Fallback to best success rate
        best = max(alive, key=lambda n: self._stats.get(n, RouterStats(n)).success_rate)
        return best

    # ── Chat ──

    async def chat(self, messages: list[dict], provider: str = "",
                   temperature: float = 0.7, max_tokens: int = 4096,
                   timeout: int = 120, model: str = "", **kwargs) -> ProviderResult:
        p = self._resolve_provider(provider)
        if not p:
            return ProviderResult.empty(f"No provider: {provider}")

        # ── Token optimization: apply CacheDirector for prefix caching ──
        provider_name = p.name if p else ""
        from .cache_director import get_cache_director
        director = get_cache_director()
        if director.supports_cache(provider_name):
            messages = director.prepare(messages, provider_name)

        t0 = time.monotonic()
        result = None
        try:
            result = await p.chat(messages, temperature=temperature,
                                  max_tokens=max_tokens, timeout=timeout,
                                  model=model or kwargs.get("model_extra", ""))
            if result and result.text:
                self._record_success(p.name, result.tokens, (time.monotonic() - t0) * 1000)
                self._classifier.learn(prompt=str(messages[-1].get("content", ""))[:200],
                                        chosen=p.name, success=True)
                # ── Record cache performance ──
                if result.prompt_tokens:
                    from .cache_director import get_cache_director
                    get_cache_director().record(
                        p.name, result.prompt_tokens,
                        result.cache_hit_tokens,
                    )
            elif result and (result.error or result.rate_limited):
                self._record_failure(p.name, result.error, rate_limited=result.rate_limited)
            return result or ProviderResult.empty("No result")
        except Exception as e:
            self._record_failure(p.name, str(e), rate_limited=getattr(result, 'rate_limited', False))
            return ProviderResult.empty(str(e))

    async def stream(self, messages: list[dict], provider: str = "",
                     temperature: float = 0.3, max_tokens: int = 4096,
                     timeout: int = 120) -> AsyncIterator[str]:
        p = self._resolve_provider(provider)
        if not p:
            yield f"[No provider: {provider}]"
            return

        # ── Token optimization ──
        messages = self._optimize_messages(messages)

        t0 = time.monotonic()
        tokens = 0
        try:
            async for token in p.stream(messages, temperature=temperature,
                                         max_tokens=max_tokens, timeout=timeout):
                tokens += 1
                yield token
            self._record_success(p.name, tokens, (time.monotonic() - t0) * 1000)
        except Exception as e:
            self._record_failure(p.name, str(e))
            yield f"\n[Error: {e}]"

    # ── Stats ──

    def get_stats(self) -> dict:
        return {
            name: {
                "calls": s.calls, "success_rate": s.success_rate,
                "avg_latency_ms": s.avg_latency_ms, "total_tokens": s.total_tokens,
                "last_error": s.last_error[:80] if s.last_error else "",
            }
            for name, s in self._stats.items()
        }

    def _optimize_messages(self, messages: list[dict]) -> list[dict]:
        """Apply token optimizations: prefix caching + system prompt trimming."""
        try:
            from ..dna.cache_optimizer import CacheOptimizer
            # Use a shared optimizer instance per TreeLLM
            if not hasattr(self, '_cache_optimizer'):
                self._cache_optimizer = CacheOptimizer(max_tokens=64000, cache_budget=0.85)
            return self._cache_optimizer.prepare(messages)
        except Exception:
            return messages

    # ── Private ──

    def _resolve_provider(self, name: str) -> Provider | None:
        if name and name in self._providers:
            return self._providers[name]
        if self._elected and self._elected in self._providers:
            return self._providers[self._elected]
        for p in self._providers.values():
            return p
        return None

    def _record_success(self, name: str, tokens: int, latency_ms: float) -> None:
        s = self._stats.get(name)
        if not s:
            return
        s.calls += 1; s.successes += 1
        s.total_tokens += tokens; s.total_latency_ms += latency_ms
        s.last_latency_ms = latency_ms
        s.recent_successes.append(True)
        s.recent_latencies.append(latency_ms)
        if len(s.recent_successes) > 20:
            s.recent_successes = s.recent_successes[-20:]
            s.recent_latencies = s.recent_latencies[-20:]
        from .holistic_election import get_election
        get_election().record_result(name, True, latency_ms, tokens)
        # ── Cost tracking ──
        try:
            from ..capability.industrial_doc_engine import get_cost_dash
            get_cost_dash().record(name, tokens, tokens)
        except Exception: pass
        # ── P2P cost report to relay ──
        try:
            from ..network.p2p_node import get_p2p_node
            get_p2p_node().report_cost(name, tokens, tokens)
        except Exception: pass

    def _record_failure(self, name: str, error: str, rate_limited: bool = False) -> None:
        s = self._stats.get(name)
        if not s:
            return
        s.calls += 1; s.failures += 1
        if rate_limited:
            s.rate_limits += 1
        s.last_error = error
        s.recent_successes.append(False)
        if len(s.recent_successes) > 20:
            s.recent_successes = s.recent_successes[-20:]
        from .holistic_election import get_election
        get_election().record_result(name, False, 0, 0, error, rate_limited)
