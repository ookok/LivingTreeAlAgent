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
        names = candidates or list(self._providers.keys())
        for name in names:
            p = self._providers.get(name)
            if not p:
                continue
            ok, _ = await p.ping()
            if ok:
                self._elected = name
                return name
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

        route = self._classifier.predict(prompt, alive, self._stats)
        if route and route in alive:
            return route

        best = max(alive, key=lambda n: self._stats.get(n, RouterStats(n)).success_rate)
        return best

    # ── Chat ──

    async def chat(self, messages: list[dict], provider: str = "",
                   temperature: float = 0.7, max_tokens: int = 4096,
                   timeout: int = 120, model: str = "", **kwargs) -> ProviderResult:
        p = self._resolve_provider(provider)
        if not p:
            return ProviderResult.empty(f"No provider: {provider}")

        t0 = time.monotonic()
        try:
            result = await p.chat(messages, temperature=temperature,
                                  max_tokens=max_tokens, timeout=timeout,
                                  model=model or kwargs.get("model_extra", ""))
            self._record_success(p.name, result.tokens, (time.monotonic() - t0) * 1000)
            if result.text:
                self._classifier.learn(prompt=str(messages[-1].get("content", ""))[:200],
                                       chosen=p.name, success=True)
            return result
        except Exception as e:
            self._record_failure(p.name, str(e))
            return ProviderResult.empty(str(e))

    async def stream(self, messages: list[dict], provider: str = "",
                     temperature: float = 0.3, max_tokens: int = 4096,
                     timeout: int = 120) -> AsyncIterator[str]:
        p = self._resolve_provider(provider)
        if not p:
            yield f"[No provider: {provider}]"
            return

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
        if s:
            s.calls += 1
            s.successes += 1
            s.total_tokens += tokens
            s.total_latency_ms += latency_ms
            s.last_latency_ms = latency_ms

    def _record_failure(self, name: str, error: str) -> None:
        s = self._stats.get(name)
        if s:
            s.calls += 1
            s.failures += 1
            s.last_error = error
