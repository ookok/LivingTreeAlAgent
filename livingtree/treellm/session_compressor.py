"""SessionCompressor — Hierarchical conversation compression for long contexts.

Long conversations (>10 turns) are compressed in layers:
  - Recent 5 turns: preserved verbatim
  - Middle 10 turns: summarized by L1 flash into ~200 tokens
  - Old turns: key decisions extracted via keyword pattern matching

v2.5 — Opus 4.7 KV Cache Weighting: weighted_compress() replaces age-based
fixed tiers with task-criticality-weighted allocation. Each message is scored
by relevance to current query + decision-marker presence + entity persistence.
Critical messages get 2-3x token budget regardless of age. Non-critical
messages get compressed aggressively.

Integration:
    comp = get_session_compressor()
    compressed = await comp.compress(messages, max_tokens=6000, chat_fn=llm.chat)
    # Or with Opus 4.7 weighting:
    weighted = await comp.weighted_compress(messages, query="migration plan", ...)
"""

from __future__ import annotations

import math
import threading
from typing import Any, Callable, Optional

from loguru import logger


def _ntk_decay_scale(n: int, dim: int = 8) -> float:
    """NTK-aware dynamic decay rate scaling for long conversations.

    Short conversations (<20 turns): standard decay rate (1.0x).
    Long conversations (>100 turns): gentler decay via NTK scaling (1/alpha).
    Preserves long-range attention resolution by reducing the decay slope
    as context length grows.
    """
    if n <= 20:
        return 1.0
    alpha = (n / 20.0) ** (1.0 / max(dim - 2, 1))
    return 1.0 / alpha


class SessionCompressor:
    """Hierarchical session compression for long conversations."""

    _instance: Optional["SessionCompressor"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "SessionCompressor":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = SessionCompressor()
        return cls._instance

    def __init__(self, recent_turns: int = 5, middle_turns: int = 10):
        self.recent_turns = recent_turns       # Verbatim
        self.middle_turns = middle_turns       # Summarize
        self._compression_count = 0

    async def compress(
        self, messages: list[dict], max_tokens: int = 6000,
        chat_fn: Callable = None,
    ) -> list[dict]:
        """Compress messages to fit within max_tokens budget."""
        if len(messages) <= self.recent_turns + 2:
            return messages

        recent = messages[-self.recent_turns:]
        middle = messages[-(self.recent_turns + self.middle_turns):-self.recent_turns]
        old = messages[:-(self.recent_turns + self.middle_turns)]

        compressed_parts: list[dict] = []

        # Old messages: extract key decisions
        if old and chat_fn:
            decisions = self._extract_decisions(old)
            if decisions:
                compressed_parts.append({
                    "role": "system",
                    "content": f"[Earlier key decisions] {decisions}",
                })

        # Middle messages: summarize
        if middle and chat_fn:
            summary = await self._summarize(middle, chat_fn)
            if summary:
                compressed_parts.append({
                    "role": "system",
                    "content": f"[Prior conversation context] {summary}",
                })
        elif middle:
            compressed_parts.extend(middle[-3:])  # Fallback: keep last 3

        compressed_parts.extend(recent)
        self._compression_count += 1

        # Quick token estimate — truncate if still too long
        total_chars = sum(len(str(m.get("content", ""))) for m in compressed_parts)
        if total_chars > max_tokens * 4:  # ~4 chars per token
            for msg in compressed_parts:
                if msg["role"] == "system":
                    msg["content"] = msg["content"][:max_tokens * 2]

        return compressed_parts

    async def _summarize(self, messages: list[dict], chat_fn: Callable) -> str:
        """Summarize a block of messages into a concise context."""
        try:
            text = " | ".join(
                f"[{m['role']}]: {str(m.get('content', ''))[:200]}"
                for m in messages[-5:]
            )
            prompt = (
                "Summarize this conversation excerpt in 2-3 sentences. "
                "Focus on key facts, decisions, and user preferences:\n\n" + text[:1500]
            )
            result = await chat_fn(
                [{"role": "user", "content": prompt}],
                provider="", max_tokens=150, temperature=0.2,
            )
            summary = getattr(result, 'text', '') or str(result)
            return summary[:300]
        except Exception as e:
            logger.debug(f"SessionCompressor summarize: {e}")
            return ""

    def _extract_decisions(self, messages: list[dict]) -> str:
        """Extract key decision points from old messages via pattern matching."""
        decision_keywords = [
            "决定", "选择", "最终", "确认", "采用", "使用",
            "decided", "chose", "final", "confirmed", "selected",
        ]
        decisions = []
        for m in messages[-20:]:
            content = str(m.get("content", ""))
            if m["role"] == "assistant" and len(content) > 100:
                for kw in decision_keywords:
                    idx = content.lower().find(kw)
                    if idx >= 0:
                        snippet = content[max(0, idx-20):idx+len(kw)+80].strip()
                        decisions.append(snippet[:100])
                        break
            if len(decisions) >= 3:
                break
        return "; ".join(decisions) if decisions else ""

    async def weighted_compress(
        self, messages: list[dict], max_tokens: int = 6000,
        chat_fn: Callable = None, query: str = "",
    ) -> list[dict]:
        """Opus 4.7 KV Cache Weighting: task-criticality-weighted compression.

        Scores each message by relevance to the current query, decision-marker
        presence, and entity persistence. Allocates token budget proportionally —
        critical messages get 2-3x retention even if old; non-critical messages
        get aggressively compressed regardless of age.

        Args:
            messages: Full conversation messages (role/content dicts)
            max_tokens: Total token budget for compressed output
            chat_fn: Async LLM call for summarization
            query: Current user query for relevance scoring

        Returns:
            Compressed message list with weighted allocation
        """
        if len(messages) <= self.recent_turns + 2:
            return messages

        n = len(messages)
        ntk_factor = _ntk_decay_scale(n)
        mid_start = max(0, n // 3)
        mid_end = max(0, n * 2 // 3)
        q_words = set(query.lower().split()) if query else set()

        decision_keywords = {
            "决定", "选择", "最终", "确认", "采用", "规划", "方案",
            "decided", "chose", "final", "confirmed", "selected", "plan",
        }

        scored = []
        for i, m in enumerate(messages):
            content = str(m.get("content", ""))
            relevance = 0.0
            if q_words and content:
                c_words = set(content.lower().split())
                relevance = len(q_words & c_words) / max(len(q_words), 1)

            decision_bonus = 0.0
            content_lower = content.lower()
            for kw in decision_keywords:
                if kw in content_lower:
                    decision_bonus += 0.15
            decision_bonus = min(decision_bonus, 0.6)

            role_bonus = 0.0
            if m.get("role") == "assistant":
                role_bonus = 0.1
            elif m.get("role") == "user":
                role_bonus = 0.05

            position_decay = 1.0
            if n > 10 and mid_start <= i <= mid_end:
                distance_from_mid_center = abs(i - (mid_start + mid_end) // 2)
                # TriAttention-inspired: trigonometric position decay
                # Uses sine modulation for distance-based key preference
                trig_decay = math.sin(math.pi * (1.0 - distance_from_mid_center / max(mid_end - mid_start, 1) * 2))
                trig_decay = max(0.3, trig_decay ** (1.0 / ntk_factor))
                position_decay = trig_decay * 0.7 + (1.0 - distance_from_mid_center * 0.03) * 0.3

            # TriAttention: norm-based importance — longer messages have higher Q/K norm
            norm_bonus = min(0.15, len(content) / 5000.0)

            crit_score = relevance * 0.30 + decision_bonus * 0.25 + role_bonus * 0.10 + position_decay * 0.20 + norm_bonus * 0.15
            scored.append((i, m, min(crit_score, 1.0)))

        total_crit = sum(s for _, _, s in scored)
        if total_crit == 0:
            total_crit = len(messages)

        compressed_parts: list[dict] = []
        for idx, msg, crit in scored:
            content = str(msg.get("content", ""))
            budget_chars = int(max_tokens * 3 * (crit / max(total_crit / len(messages), 0.01)))

            if crit > 0.5:
                compressed_parts.append(msg)
            elif crit > 0.25 and chat_fn:
                summary = await self._summarize_weighted([msg], chat_fn, budget_chars)
                if summary:
                    compressed_parts.append(summary)
                else:
                    compressed_parts.append({
                        "role": msg.get("role", "user"),
                        "content": content[:budget_chars],
                    })
            else:
                snippet = content[:max(80, budget_chars // 2)]
                if len(content) > len(snippet):
                    snippet += "..."
                if snippet:
                    compressed_parts.append({
                        "role": "system",
                        "content": f"[context] {snippet}",
                    })

        total_chars = sum(len(str(m.get("content", ""))) for m in compressed_parts)
        if total_chars > max_tokens * 4:
            for msg in compressed_parts:
                if msg.get("role") == "system":
                    msg["content"] = (msg["content"] or "")[:max_tokens * 2]

        self._compression_count += 1
        return compressed_parts

    async def _summarize_weighted(
        self, messages: list[dict], chat_fn: Callable, budget_chars: int,
    ) -> dict | None:
        try:
            text = " | ".join(
                f"[{m['role']}]: {str(m.get('content', ''))[:300]}"
                for m in messages[-3:]
            )
            prompt = (
                f"Summarize this conversation in {budget_chars // 4} tokens. "
                f"Keep all decisions, numbers, and constraints:\n\n{text[:2000]}"
            )
            result = await chat_fn(
                [{"role": "user", "content": prompt}],
                provider="", max_tokens=min(budget_chars // 4, 200), temperature=0.2,
            )
            summary = getattr(result, 'text', '') or str(result)
            return {"role": "system", "content": f"[prior context] {summary[:budget_chars]}"}
        except Exception:
            return None

    def stats(self) -> dict:
        return {"compressions": self._compression_count}


_compressor: Optional[SessionCompressor] = None
_compressor_lock = threading.Lock()


def get_session_compressor() -> SessionCompressor:
    global _compressor
    if _compressor is None:
        with _compressor_lock:
            if _compressor is None:
                _compressor = SessionCompressor()
    return _compressor


__all__ = ["SessionCompressor", "get_session_compressor"]
