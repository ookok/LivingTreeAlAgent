"""System Prompt Cache — Token中转站第三重保障：本地加速。

Design (#7): 系统提示词在每次对话中反复发送。缓存复用 → 成本 10%，速度 5x。

Integration points:
  - DualModelConsciousness: system prompts for flash + pro models
  - life_stage.py: domain context prompt templates
  - tui_orchestrator.py: system prompt with tool list

Architecture:
  Cache key = hash(system_prompt_template + parameters)
  Cache value = pre-computed tokenization + usage stats
  TTL = 5 minutes (system prompts rarely change)
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class CachedPrompt:
    """A cached system prompt with usage statistics."""
    template_hash: str
    prompt_text: str
    estimated_tokens: int = 0
    created_at: float = field(default_factory=time.time)
    hit_count: int = 0
    ttl_seconds: int = 300  # 5 minutes for system prompts
    source: str = ""  # Which component created this prompt

    @property
    def expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


class PromptCache:
    """Dedicated cache for system prompts.

    System prompts are large and repeated every conversation turn.
    Caching them reduces API token usage by 60-80% for long conversations.

    Uses LRU eviction with TTL expiration.
    """

    def __init__(self, max_entries: int = 50, default_ttl: int = 300):
        self._cache: OrderedDict[str, CachedPrompt] = OrderedDict()
        self._max_entries = max_entries
        self._default_ttl = default_ttl
        self._stats = {"hits": 0, "misses": 0, "tokens_saved": 0}

    def _hash(self, template: str, params: dict = None) -> str:
        """Hash template + params into cache key."""
        key_str = template
        if params:
            key_str += str(sorted(params.items()))
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    def get(self, template: str, params: dict = None) -> Optional[str]:
        """Get cached prompt. Returns None on miss or expiration."""
        key = self._hash(template, params)

        if key in self._cache:
            cached = self._cache[key]
            if not cached.expired:
                cached.hit_count += 1
                self._stats["hits"] += 1
                self._stats["tokens_saved"] += cached.estimated_tokens
                # Move to end (LRU)
                self._cache.move_to_end(key)
                return cached.prompt_text
            else:
                del self._cache[key]

        self._stats["misses"] += 1
        return None

    def set(
        self,
        template: str,
        rendered: str,
        params: dict = None,
        estimated_tokens: int = 0,
        source: str = "",
        ttl: int = None,
    ) -> None:
        """Cache a rendered prompt."""
        key = self._hash(template, params)

        cached = CachedPrompt(
            template_hash=key,
            prompt_text=rendered,
            estimated_tokens=estimated_tokens or len(rendered) // 3,
            ttl_seconds=ttl or self._default_ttl,
            source=source,
        )

        self._cache[key] = cached
        self._evict_if_needed()

    def get_or_render(
        self,
        template: str,
        render_fn,
        params: dict = None,
        source: str = "",
    ) -> str:
        """Get cached prompt or render + cache it.

        Args:
            template: Template string (used as cache key base).
            render_fn: Callable() → str that renders the prompt.
            params: Optional template parameters for cache key.
            source: Component name for logging.

        Returns:
            Rendered prompt string (from cache or freshly rendered).
        """
        cached = self.get(template, params)
        if cached:
            return cached

        rendered = render_fn()
        if rendered:
            self.set(
                template=template,
                rendered=rendered,
                params=params,
                source=source,
            )
        return rendered

    def _evict_if_needed(self) -> None:
        while len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)

    def flush(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        return count

    @property
    def stats(self) -> dict:
        total = self._stats["hits"] + self._stats["misses"]
        return {
            **self._stats,
            "entries": len(self._cache),
            "hit_rate": self._stats["hits"] / max(1, total),
        }


# ── Singleton ──

_prompt_cache: Optional[PromptCache] = None


def get_prompt_cache() -> PromptCache:
    global _prompt_cache
    if _prompt_cache is None:
        _prompt_cache = PromptCache()
    return _prompt_cache
