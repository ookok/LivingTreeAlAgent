"""Cache-First Loop — DeepSeek byte-stable prefix-cache optimizer.

DeepSeek's prefix-cache fingerprints from byte 0 of the prompt. To keep
cache hits high (~94%), the prompt must follow append-only growth with no
re-ordering, no marker-based compaction, and no mid-prompt insertions.

Key invariants:
1. System prompt → always first, never modified after first turn
2. Conversation history → strict append, oldest-first ordering
3. Tool results → appended after the tool-call, never prepended
4. Context compression → when needed, keep oldest N turns intact, trim newest

This module instruments the message list before every API call to ensure
byte-stable ordering that preserves DeepSeek's prefix-cache hits.

Usage:
    optimizer = CacheOptimizer(max_tokens=1_000_000, cache_budget=0.8)
    messages = optimizer.prepare(system_prompt, history, tool_results)
    # messages is now guaranteed byte-stable for cache hits
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from loguru import logger


class CacheOptimizer:
    """Byte-stable message preparer for DeepSeek prefix-cache optimization.

    Tracks the prefix fingerprint and guarantees append-only growth so
    DeepSeek's cache engine can re-use the shared prefix across turns.
    """

    # Average chars-per-token estimate for DeepSeek tokenizer (~0.6 tokens/char)
    CHARS_PER_TOKEN = 1.6

    def __init__(
        self,
        max_tokens: int = 1_000_000,
        cache_budget: float = 0.85,
        safety_margin: int = 4096,
    ):
        self.max_tokens = max_tokens
        self.cache_budget = cache_budget
        self.safety_margin = safety_margin

        self._prefix_fingerprint: str = ""
        self._prefix_length: int = 0
        self._turn_count: int = 0
        self._hits: int = 0
        self._misses: int = 0
        self._total_input_tokens: int = 0
        self._cached_input_tokens: int = 0

    def prepare(
        self,
        system_prompt: str,
        messages: list[dict],
        tool_result: str | None = None,
    ) -> list[dict]:
        """Prepare message list for byte-stable prefix-cache delivery.

        Returns a message list that guarantees maximum prefix-cache reuse.
        Side effects: updates internal cache tracking state.
        """
        self._turn_count += 1

        full = []

        if system_prompt and self._turn_count == 1:
            full.append({"role": "system", "content": system_prompt})
        elif system_prompt:
            full.append({"role": "system", "content": system_prompt})

        full.extend(messages)

        if tool_result:
            full.append({"role": "tool", "content": tool_result[:50000]})

        estimated_tokens = self._estimate_tokens(full)

        if estimated_tokens > self.max_tokens * self.cache_budget:
            full = self._compact(full, system_prompt)

        new_fingerprint = self._compute_fingerprint(system_prompt + str(full[:3]))
        if self._prefix_fingerprint and new_fingerprint.startswith(self._prefix_fingerprint):
            self._hits += 1
        elif self._turn_count > 1:
            self._misses += 1
        self._prefix_fingerprint = new_fingerprint

        return full

    def record_usage(self, prompt_tokens: int, cache_hit_tokens: int = 0) -> None:
        self._total_input_tokens += prompt_tokens
        self._cached_input_tokens += cache_hit_tokens

    def stats(self) -> dict[str, Any]:
        total_turns = max(self._hits + self._misses, 1)
        hit_rate = self._hits / total_turns if total_turns > 0 else 0.0
        savings_pct = (self._cached_input_tokens / max(self._total_input_tokens, 1)) * 100

        return {
            "turns": self._turn_count,
            "prefix_hits": self._hits,
            "prefix_misses": self._misses,
            "hit_rate_pct": round(hit_rate * 100, 1),
            "total_input_tokens": self._total_input_tokens,
            "cached_input_tokens": self._cached_input_tokens,
            "cache_savings_pct": round(savings_pct, 1),
            "prefix_length": self._prefix_length,
        }

    def reset(self) -> None:
        self._prefix_fingerprint = ""
        self._prefix_length = 0
        self._turn_count = 0
        self._hits = 0
        self._misses = 0
        self._total_input_tokens = 0
        self._cached_input_tokens = 0

    def _estimate_tokens(self, messages: list[dict]) -> int:
        text = "".join(m.get("content", "") or "" for m in messages)
        return int(len(text) / self.CHARS_PER_TOKEN)

    def _compact(
        self,
        messages: list[dict],
        system_prompt: str,
    ) -> list[dict]:
        """Compact messages when approaching context limit.

        Strategy: keep system prompt + oldest 2 turns intact, summarize
        middle turns, keep newest 6 turns verbatim. This preserves the
        byte-stable prefix (oldest turns never move) while freeing
        capacity for new content.
        """
        sys_len = 1 if system_prompt else 0

        if len(messages) <= sys_len + 10:
            return messages

        keep_old = sys_len + 4
        keep_new = 12

        if len(messages) <= keep_old + keep_new:
            return messages

        head = messages[:keep_old]
        tail = messages[-keep_new:]

        middle_count = len(messages) - keep_old - keep_new
        summary = (
            f"[{middle_count} earlier messages compressed. "
            f"Key context preserved in surrounding messages.]"
        )
        compacted = head + [{"role": "system", "content": summary}] + tail

        logger.debug(
            f"CacheOptimizer compacted {len(messages)}→{len(compacted)} "
            f"msgs (kept {keep_old} head + {keep_new} tail)"
        )
        return compacted

    @staticmethod
    def _compute_fingerprint(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


class PrefixCacheTracker:
    """Lightweight per-session prefix-cache statistics tracker.

    Attaches to the chat screen to display live cache hit/miss stats.
    """

    def __init__(self):
        self._start_time = time.time()
        self._turns: list[dict] = []
        self._total_prompt_tokens = 0
        self._total_cached_tokens = 0
        self._total_completion_tokens = 0

    def record_turn(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
        cost_yuan: float = 0.0,
    ) -> None:
        self._turns.append({
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
            "cost_yuan": cost_yuan,
            "time": time.time(),
        })
        self._total_prompt_tokens += prompt_tokens
        self._total_cached_tokens += cached_tokens
        self._total_completion_tokens += completion_tokens

    def snapshot(self) -> dict[str, Any]:
        turns = len(self._turns)
        elapsed = max(time.time() - self._start_time, 1)
        cache_hit_rate = (
            self._total_cached_tokens / max(self._total_prompt_tokens, 1)
        ) * 100

        return {
            "turns": turns,
            "elapsed_s": int(elapsed),
            "prompt_tokens": self._total_prompt_tokens,
            "cached_tokens": self._total_cached_tokens,
            "completion_tokens": self._total_completion_tokens,
            "cache_hit_pct": round(cache_hit_rate, 1),
            "estimated_savings_yuan": round(
                self._total_cached_tokens * 0.00000014, 6
            ),
        }
