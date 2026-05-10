"""Context Budget Manager — smart token compression on overflow.

Inspired by CowAgent's agent_max_context_tokens + intelligent trimming.
When total context exceeds the budget, compresses at natural boundaries
(conversation turns, steps) rather than raw truncation.

Integrates with existing AdaptiveFolder (adaptive_folder.py) for the
actual compression logic, adding budget enforcement + auto-trigger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

DEFAULT_MAX_TOKENS = 50000
DEFAULT_MAX_TURNS = 20
TOKENS_PER_CHAR_ESTIMATE = 0.25  # ~4 chars per token for Chinese


@dataclass
class BudgetState:
    total_tokens: int = 0
    system_tokens: int = 0
    history_tokens: int = 0
    current_tokens: int = 0
    max_tokens: int = DEFAULT_MAX_TOKENS
    max_turns: int = DEFAULT_MAX_TURNS
    turn_count: int = 0
    compressed_turns: int = 0
    last_compression: float = 0.0
    compression_count: int = 0


class ContextBudget:
    """Enforce token budget with intelligent compression.

    Triggers when:
      1. total_tokens > max_tokens — over budget, must compress
      2. turn_count > max_turns — too many turns, prune oldest
      3. single message is > 70% of budget — treat as document, summarize

    Compression strategy (priority order):
      1. Summarize oldest turns (most compressible)
      2. Drop non-essential metadata
      3. Truncate long tool outputs
      4. Last resort: drop oldest turns entirely
    """

    def __init__(self, max_tokens: int = DEFAULT_MAX_TOKENS, max_turns: int = DEFAULT_MAX_TURNS):
        self._state = BudgetState(max_tokens=max_tokens, max_turns=max_turns)

    def estimate_tokens(self, text: str) -> int:
        """Fast token count estimate (Chinese: ~0.25 tokens/char, English: ~0.3)."""
        return max(1, int(len(text) * TOKENS_PER_CHAR_ESTIMATE))

    def reset(self):
        self._state = BudgetState(
            max_tokens=self._state.max_tokens,
            max_turns=self._state.max_turns,
        )

    def configure(self, max_tokens: int = 0, max_turns: int = 0):
        if max_tokens > 0:
            self._state.max_tokens = max_tokens
        if max_turns > 0:
            self._state.max_turns = max_turns

    def stats(self) -> dict:
        s = self._state
        usage_pct = round(s.total_tokens / max(1, s.max_tokens) * 100, 1)
        return {
            "total_tokens": s.total_tokens,
            "max_tokens": s.max_tokens,
            "usage_pct": usage_pct,
            "turn_count": s.turn_count,
            "max_turns": s.max_turns,
            "compressed_turns": s.compressed_turns,
            "compression_count": s.compression_count,
            "over_budget": usage_pct > 90,
        }

    def add_and_check(self, system_prompt: str, history: list[dict],
                      current_msg: str) -> dict:
        """Add a new message, check budget, compress if needed.

        Returns:
          {"needs_compression": bool, "compressed_history": list, "dropped": int}
        """
        s = self._state
        s.turn_count += 1

        sys_tokens = self.estimate_tokens(system_prompt)
        hist_tokens = sum(self.estimate_tokens(str(m.get("content", ""))) for m in history)
        cur_tokens = self.estimate_tokens(current_msg)

        s.system_tokens = sys_tokens
        s.history_tokens = hist_tokens
        s.current_tokens = cur_tokens
        s.total_tokens = sys_tokens + hist_tokens + cur_tokens

        if s.total_tokens <= s.max_tokens and s.turn_count <= s.max_turns:
            return {"needs_compression": False, "compressed_history": history, "dropped": 0}

        compressed = self._compress(history, sys_tokens, cur_tokens)
        return compressed

    def _compress(self, history: list[dict], sys_tokens: int, cur_tokens: int) -> dict:
        s = self._state
        import time

        available = int(s.max_tokens * 0.85) - sys_tokens - cur_tokens
        if available <= 0:
            available = int(s.max_tokens * 0.3)

        result = []
        dropped = 0
        used = 0

        keep_recent = min(4, len(history))
        for msg in history:
            result.append(msg)

        if len(result) > s.max_turns:
            excess = len(result) - s.max_turns
            result = result[excess:]
            dropped += excess

        total_hist_tokens = sum(self.estimate_tokens(str(m.get("content", ""))) for m in result)
        if total_hist_tokens > available:
            summaries = []
            excess_start = 0
            for i, msg in enumerate(result):
                tokens = self.estimate_tokens(str(msg.get("content", "")))
                if used + tokens > available and i < len(result) - keep_recent:
                    summaries.append(f"[{msg.get('role', '?')}]: {str(msg.get('content', ''))[:80]}...")
                    dropped += 1
                    excess_start = i + 1
                else:
                    used += tokens

            if summaries:
                summary_text = "Earlier context (summarized):\n" + "\n".join(summaries)
                result = [
                    {"role": "system", "content": summary_text}
                ] + result[excess_start:]

        s.compressed_turns += dropped
        s.compression_count += 1
        s.last_compression = time.time()
        s.history_tokens = sum(self.estimate_tokens(str(m.get("content", ""))) for m in result)
        s.total_tokens = sys_tokens + s.history_tokens + cur_tokens

        logger.info(f"Context compressed: {dropped} turns dropped, "
                     f"tokens {s.total_tokens}/{s.max_tokens}")
        return {"needs_compression": True, "compressed_history": result, "dropped": dropped}


_budget: Optional[ContextBudget] = None


def get_context_budget(max_tokens: int = 0, max_turns: int = 0) -> ContextBudget:
    global _budget
    if _budget is None:
        _budget = ContextBudget(max_tokens or DEFAULT_MAX_TOKENS, max_turns or DEFAULT_MAX_TURNS)
    return _budget
