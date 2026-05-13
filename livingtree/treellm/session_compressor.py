"""SessionCompressor — Hierarchical conversation compression for long contexts.

Long conversations (>10 turns) are compressed in layers:
  - Recent 5 turns: preserved verbatim
  - Middle 10 turns: summarized by L1 flash into ~200 tokens
  - Old turns: key decisions extracted via keyword pattern matching

Ensures context never exceeds budget while preserving critical information.

Integration:
    comp = get_session_compressor()
    compressed = await comp.compress(messages, max_tokens=6000, chat_fn=llm.chat)
    result = await llm.chat(compressed, provider=...)  # uses compressed context
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from loguru import logger


class SessionCompressor:
    """Hierarchical session compression for long conversations."""

    _instance: Optional["SessionCompressor"] = None

    @classmethod
    def instance(cls) -> "SessionCompressor":
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

    def stats(self) -> dict:
        return {"compressions": self._compression_count}


_compressor: Optional[SessionCompressor] = None


def get_session_compressor() -> SessionCompressor:
    global _compressor
    if _compressor is None:
        _compressor = SessionCompressor()
    return _compressor


__all__ = ["SessionCompressor", "get_session_compressor"]
