"""Cache-Safe Prompt Builder — Maximize provider KV cache hit rate.

Based on "Prompt caching in LLMs, clearly explained":
  - KV cache requires EXACT prefix matching (token-for-token from beginning)
  - Static content at top → dynamic content at bottom → 90% cost reduction
  - Claude Code achieves 92% cache hit rate by design discipline

Design principles:
  1. STABLE-FIRST: system prompt + tool definitions ALWAYS at position 0
  2. IMMUTABLE PREFIX: never modify anything upstream of cache breakpoint
  3. APPEND-ONLY UPDATES: add context as new blocks at the end
  4. CACHE-AWARE ORDERING: highest-hit-rate content first in static section

Integration: replaces ad-hoc prompt concatenation in life_stage._cognize
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class PromptBlock:
    """A cache-safe prompt block with stability tracking."""
    content: str
    block_type: str  # "system", "tools", "context", "history", "query"
    is_stable: bool   # True if this block rarely changes (cached)
    hash: str = ""
    token_estimate: int = 0
    last_modified: float = 0.0

    def __post_init__(self):
        if not self.hash:
            self.hash = hashlib.sha256(self.content.encode()).hexdigest()[:16]
        if not self.token_estimate:
            self.token_estimate = len(self.content) // 3


@dataclass
class PromptAssembly:
    """An assembled prompt with cache structure metadata."""
    full_text: str
    blocks: list[PromptBlock] = field(default_factory=list)
    stable_prefix_tokens: int = 0    # Tokens in the stable (cached) prefix
    dynamic_tokens: int = 0           # Tokens in the dynamic (uncached) suffix
    cache_hit_likelihood: float = 0.0 # Estimated KV cache hit probability
    total_tokens: int = 0
    assembly_time_ms: float = 0.0


class CacheSafePrompt:
    """Build prompts that maximize provider KV cache hit rate.

    Structure (stable → dynamic):
      [system prompt]       ← STABLE (cached, 90% discount)
      [tool definitions]    ← STABLE (cached)
      [retrieved context]   ← SEMI-STABLE (cached within session)
      [conversation history] ← DYNAMIC (uncached, full price)
      [user query]          ← DYNAMIC (uncached)

    Key insight from article:
    "Don't inject timestamps into system prompts, don't shuffle tool definitions,
    don't switch models mid-session, and don't mutate anything upstream
    of the cache breakpoint."
    """

    def __init__(self, max_tokens: int = 8192):
        self.max_tokens = max_tokens
        self._system_prompt_hash = ""
        self._tool_defs_hash = ""
        self._cache_hits = 0
        self._cache_misses = 0

    def build(
        self,
        system_prompt: str = "",
        tool_definitions: str = "",
        retrieved_context: str = "",
        conversation_history: list[dict] = None,
        user_query: str = "",
    ) -> PromptAssembly:
        """Build a cache-safe prompt following stability-first ordering.

        Args:
            system_prompt: Static system instructions.
            tool_definitions: Static tool/function definitions.
            retrieved_context: Semi-stable retrieved knowledge.
            conversation_history: Dynamic conversation turns.
            user_query: The current user message.

        Returns:
            PromptAssembly with cache structure metadata.
        """
        t0 = time.time()
        blocks = []

        # Layer 1: SYSTEM PROMPT — most stable, highest cache benefit
        if system_prompt:
            block = PromptBlock(
                content=system_prompt.strip(),
                block_type="system",
                is_stable=True,
            )
            blocks.append(block)
            self._system_prompt_hash = block.hash

        # Layer 2: TOOL DEFINITIONS — stable within session
        if tool_definitions:
            block = PromptBlock(
                content=tool_definitions.strip(),
                block_type="tools",
                is_stable=True,
            )
            blocks.append(block)
            self._tool_defs_hash = block.hash

        # Layer 3: RETRIEVED CONTEXT — semi-stable (changes per query, stable per session)
        if retrieved_context:
            block = PromptBlock(
                content=retrieved_context.strip(),
                block_type="context",
                is_stable=False,  # May change per query
            )
            blocks.append(block)

        # Layer 4: CONVERSATION HISTORY — dynamic
        if conversation_history:
            history_text = self._format_history(conversation_history)
            if history_text:
                block = PromptBlock(
                    content=history_text,
                    block_type="history",
                    is_stable=False,
                )
                blocks.append(block)

        # Layer 5: USER QUERY — most dynamic
        if user_query:
            block = PromptBlock(
                content=user_query.strip(),
                block_type="query",
                is_stable=False,
            )
            blocks.append(block)

        # Assemble: join all blocks with double newline
        full_text = "\n\n".join(b.content for b in blocks)

        # Compute cache metrics
        stable_tokens = sum(b.token_estimate for b in blocks if b.is_stable)
        dynamic_tokens = sum(b.token_estimate for b in blocks if not b.is_stable)
        total = stable_tokens + dynamic_tokens

        # Cache hit likelihood heuristic:
        #   - More stable tokens → higher hit rate
        #   - Stable prefix > 50% of total → likely hit
        cache_likelihood = stable_tokens / max(1, total) if total > 0 else 0.0

        # Record for tracking
        if cache_likelihood > 0.5:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

        return PromptAssembly(
            full_text=full_text,
            blocks=blocks,
            stable_prefix_tokens=stable_tokens,
            dynamic_tokens=dynamic_tokens,
            cache_hit_likelihood=cache_likelihood,
            total_tokens=total,
            assembly_time_ms=(time.time() - t0) * 1000,
        )

    def check_prefix_stability(self, new_system: str, new_tools: str) -> bool:
        """Check if new prompt shares the same stable prefix as previous.

        Returns True if system prompt + tools are identical (cache hit).
        Returns False if they changed (cache miss — prefix invalidated).
        """
        if new_system and self._system_prompt_hash:
            new_hash = hashlib.sha256(new_system.encode()).hexdigest()[:16]
            if new_hash != self._system_prompt_hash:
                logger.debug(
                    f"CacheSafePrompt: PREFIX INVALIDATED — system prompt changed"
                )
                return False

        if new_tools and self._tool_defs_hash:
            new_hash = hashlib.sha256(new_tools.encode()).hexdigest()[:16]
            if new_hash != self._tool_defs_hash:
                logger.debug(
                    f"CacheSafePrompt: PREFIX INVALIDATED — tool definitions changed"
                )
                return False

        return True

    def get_cache_stats(self) -> dict:
        """Get KV cache hit/miss statistics."""
        total = self._cache_hits + self._cache_misses
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": self._cache_hits / max(1, total),
            "estimated_savings_pct": round(
                self._cache_hits / max(1, total) * 90, 1
            ),
        }

    # ── Internal ──

    def _format_history(self, history: list[dict]) -> str:
        """Format conversation history as cache-safe suffix."""
        if not history:
            return ""
        lines = ["## Conversation History"]
        for turn in history[-20:]:  # Last 20 turns max
            role = turn.get("role", "unknown")
            content = str(turn.get("content", ""))[:500]
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)


# ── Singleton ──

_builder: Optional[CacheSafePrompt] = None


def get_cache_safe_prompt(max_tokens: int = 8192) -> CacheSafePrompt:
    global _builder
    if _builder is None:
        _builder = CacheSafePrompt(max_tokens=max_tokens)
    return _builder
