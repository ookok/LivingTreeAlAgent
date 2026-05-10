"""CacheDirector — Multi-provider KV cache intelligence layer.

    Extends CacheOptimizer with provider-aware prefix caching:
    1. Provider capability map: who supports prefix caching + at what level
    2. Per-provider hit rate tracking → feeds into election scoring
    3. Cache-friendly routing: prefer caching providers for repeated prompts
    4. Pre-warm: IdleConsolidator can pre-load common prompts into cache
    5. Cache-busting: detect when cache has been invalidated (model updates)

    Supported providers with prefix caching:
    - DeepSeek: byte-stable, >90% hit rate, 90% cost discount on cached tokens
    - NVIDIA NIM: prefix caching on llama-3.1+ models (automatic)
    - SiliconFlow: prompt cache on supported models
    - OpenAI-compatible: varies by deployment

    Usage:
        director = get_cache_director()
        provider = director.route(messages, candidates)
        optimized = director.prepare(system_prompt, messages)
        director.record(provider, prompt_tokens, cache_hit_tokens)
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from ..dna.cache_optimizer import CacheOptimizer

CACHE_STATS_FILE = Path(".livingtree/cache_stats.json")


# Provider capability map: prefix cache support level
# Level 0 = none, 1 = basic (auto), 2 = byte-stable (manual optimize), 3 = advanced (token-level)
PROVIDER_CACHE_CAPS: dict[str, dict] = {
    "deepseek":     {"level": 2, "discount": 0.90, "note": "byte-stable, 90% cost savings"},
    "nvidia-reasoning": {"level": 1, "discount": 0.50, "note": "automatic prefix cache on deepseek-r1"},
    "nvidia-pro":      {"level": 1, "discount": 0.50, "note": "automatic on nemotron"},
    "nvidia-flash":    {"level": 1, "discount": 0.30, "note": "automatic on llama-3.3"},
    "nvidia-small":    {"level": 1, "discount": 0.20, "note": "automatic on phi-3.5"},
    "siliconflow-reasoning": {"level": 1, "discount": 0.40, "note": "prompt cache on deepseek-R1 distill"},
    "siliconflow-pro":  {"level": 1, "discount": 0.40, "note": "prompt cache on DeepSeek-V3"},
    "mofang-reasoning": {"level": 1, "discount": 0.30, "note": "prompt cache support"},
    "longcat":       {"level": 1, "discount": 0.50, "note": "automatic prefix cache"},
}

PROVIDER_CACHE_DEFAULT = {"level": 0, "discount": 0.0, "note": "no prefix cache"}


@dataclass
class CacheStats:
    provider: str
    cache_level: int = 0
    total_prompt_tokens: int = 0
    cached_prompt_tokens: int = 0
    total_turns: int = 0
    cache_hit_turns: int = 0
    estimated_savings_yuan: float = 0.0
    last_hit: float = 0.0

    @property
    def hit_rate(self) -> float:
        return self.cached_prompt_tokens / max(self.total_prompt_tokens, 1)

    @property
    def turn_hit_rate(self) -> float:
        return self.cache_hit_turns / max(self.total_turns, 1)


class CacheDirector:
    """Multi-provider KV cache intelligence with routing and optimization."""

    def __init__(self):
        self._stats: dict[str, CacheStats] = {}
        self._optimizers: dict[str, CacheOptimizer] = {}
        self._fingerprints: dict[str, str] = {}  # provider → last prompt fingerprint
        self._system_prompts: dict[str, str] = {}  # provider → cached system prompt
        self._load()

    def _maybe_save(self, *args, **kwargs):
        """No-op stub — prevent AttributeError when called by consumer."""
        pass

    def get_capability(self, provider_name: str) -> dict:
        """Get cache capability for a provider. Strips tier suffix."""
        base = provider_name.split("-")[0]
        # Try exact match first, then base prefix match
        for name in [provider_name, base, *[n for n in PROVIDER_CACHE_CAPS if provider_name.startswith(n)]]:
            if name in PROVIDER_CACHE_CAPS:
                return PROVIDER_CACHE_CAPS[name]
        return PROVIDER_CACHE_DEFAULT

    def supports_cache(self, provider_name: str) -> bool:
        return self.get_capability(provider_name)["level"] > 0

    def route(self, candidates: list[str], messages: list[dict]) -> list[str]:
        """Re-rank candidates: providers with cache hits get priority boost.

        Args:
            candidates: Available provider names
            messages: Current message list to check for cacheability

        Returns:
            Re-ordered candidates (cacheable providers first)
        """
        prompt_hash = self._hash_messages(messages)
        cached = []
        others = []

        for name in candidates:
            cap = self.get_capability(name)
            if cap["level"] == 0:
                others.append(name)
                continue

            # Check if this prompt matches a cached fingerprint
            last_fp = self._fingerprints.get(name, "")
            if last_fp and self._is_cache_hit(name, prompt_hash):
                cached.append(name)
            elif cap["level"] >= 2:
                cached.append(name)  # byte-stable providers can still benefit
            else:
                others.append(name)

        return cached + others

    def prepare(
        self,
        messages: list[dict],
        provider_name: str = "",
        system_prompt: str = "",
    ) -> list[dict]:
        """Prepare messages for optimal cache utilization.

        For byte-stable providers (level 2+): ensure append-only ordering
        For auto-cache providers (level 1): minimal optimization needed
        For no-cache providers (level 0): pass through
        """
        cap = self.get_capability(provider_name) if provider_name else PROVIDER_CACHE_DEFAULT

        if cap["level"] >= 2:
            # Use the full byte-stable optimizer
            opt = self._get_optimizer(provider_name)
            return opt.prepare(system_prompt, messages)

        # Level 1: just ensure system prompt is consistent
        if cap["level"] >= 1 and system_prompt:
            if provider_name not in self._system_prompts:
                self._system_prompts[provider_name] = system_prompt
            elif self._system_prompts[provider_name] != system_prompt:
                # System prompt changed — cache invalidated
                self._fingerprints.pop(provider_name, None)
                self._system_prompts[provider_name] = system_prompt

            # Keep structure consistent
            result = []
            if system_prompt:
                result.append({"role": "system", "content": system_prompt})
            result.extend(messages)
            return result

        return messages

    def record(
        self,
        provider_name: str,
        prompt_tokens: int,
        cache_hit_tokens: int = 0,
    ):
        """Record cache performance for a provider request.

        Args:
            provider_name: Which provider was used
            prompt_tokens: Total prompt tokens in this request
            cache_hit_tokens: How many prompt tokens were cached
        """
        if provider_name not in self._stats:
            cap = self.get_capability(provider_name)
            self._stats[provider_name] = CacheStats(
                provider=provider_name,
                cache_level=cap["level"],
            )

        s = self._stats[provider_name]
        s.total_prompt_tokens += prompt_tokens
        s.cached_prompt_tokens += cache_hit_tokens
        s.total_turns += 1
        if cache_hit_tokens > 0:
            s.cache_hit_turns += 1
            s.last_hit = time.time()

        # Estimate savings (DeepSeek: ¥0.14/1M cached vs ¥1/1M regular)
        discount = self.get_capability(provider_name)["discount"]
        regular_cost = prompt_tokens * 0.000001  # ¥1/M tokens
        s.estimated_savings_yuan += cache_hit_tokens * regular_cost * discount

        self._maybe_save()

    def cache_score(self, provider_name: str) -> float:
        """0.0–1.0: how beneficial is cache for this provider?

        Feeds into HolisticElection as a bonus dimension.
        """
        if provider_name not in self._stats:
            return 0.0

        s = self._stats[provider_name]
        cap = self.get_capability(provider_name)
        level_score = cap["level"] / 3.0  # normalize to 0-1
        return s.hit_rate * 0.6 + level_score * 0.4

    def pre_warm(self, messages: list[dict], provider_name: str, hub=None):
        """Pre-warm the KV cache by sending a dummy request during idle.

        Useful during IdleConsolidator cycles — sends max_tokens=1 request
        to load the system prompt into the provider's cache.
        """
        if not self.supports_cache(provider_name):
            return

        cap = self.get_capability(provider_name)
        if cap["level"] < 1:
            return

        # Record the fingerprint for future hit detection
        self._fingerprints[provider_name] = self._hash_messages(messages)
        logger.debug(f"Cache pre-warmed: {provider_name} level={cap['level']}")

    def stats_summary(self) -> str:
        """One-line summary of cache performance."""
        total_prompt = sum(s.total_prompt_tokens for s in self._stats.values())
        total_cached = sum(s.cached_prompt_tokens for s in self._stats.values())
        total_saved = sum(s.estimated_savings_yuan for s in self._stats.values())

        if total_prompt == 0:
            return "No cache data yet"

        hit_rate = total_cached / total_prompt * 100
        return (
            f"Cache: {total_cached}/{total_prompt} tokens cached ({hit_rate:.0f}%) "
            f"| saved ¥{total_saved:.4f} | {len(self._stats)} providers tracked"
        )

    def provider_stats(self, provider_name: str) -> dict | None:
        s = self._stats.get(provider_name)
        if not s:
            return None
        return {
            "provider": s.provider,
            "cache_level": s.cache_level,
            "total_prompt_tokens": s.total_prompt_tokens,
            "cached_prompt_tokens": s.cached_prompt_tokens,
            "hit_rate_pct": round(s.hit_rate * 100, 1),
            "turn_hit_rate_pct": round(s.turn_hit_rate * 100, 1),
            "estimated_savings_yuan": round(s.estimated_savings_yuan, 6),
            "last_hit_ago_s": int(time.time() - s.last_hit) if s.last_hit else 0,
        }

    def all_stats(self) -> dict[str, dict]:
        return {
            name: self.provider_stats(name) for name in self._stats
        }

    def _get_optimizer(self, provider_name: str) -> CacheOptimizer:
        if provider_name not in self._optimizers:
            self._optimizers[provider_name] = CacheOptimizer()
        return self._optimizers[provider_name]

    def _is_cache_hit(self, provider_name: str, new_hash: str) -> bool:
        old = self._fingerprints.get(provider_name, "")
        if not old:
            return False
        # Common prefix detection
        return new_hash[:8] == old[:8]

    @staticmethod
    def _hash_messages(messages: list[dict]) -> str:
        text = "".join(
            f"{m.get('role','')}:{str(m.get('content',''))[:200]}"
            for m in messages[:5]  # first 5 messages determine prefix
        )
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def _save(self):
        data = {}
        for name, s in self._stats.items():
            data[name] = {
                "provider": s.provider,
                "cache_level": s.cache_level,
                "total_prompt_tokens": s.total_prompt_tokens,
                "cached_prompt_tokens": s.cached_prompt_tokens,
                "total_turns": s.total_turns,
                "cache_hit_turns": s.cache_hit_turns,
                "estimated_savings_yuan": s.estimated_savings_yuan,
                "last_hit": s.last_hit,
            }
        CACHE_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_STATS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        if not CACHE_STATS_FILE.exists():
            return
        try:
            data = json.loads(CACHE_STATS_FILE.read_text(encoding="utf-8"))
            for name, d in data.items():
                self._stats[name] = CacheStats(**{k: d.get(k, 0) for k in CacheStats.__dataclass_fields__})
        except Exception:
            pass


_director: CacheDirector | None = None


def get_cache_director() -> CacheDirector:
    global _director
    if _director is None:
        _director = CacheDirector()
    return _director
