"""AutoPrompt — Self-optimizing system prompt via Thompson Sampling Bandit.

Maintains a pool of prompt variants per task type. Each variant has a Beta
distribution representing its quality. Thompson Sampling selects the best
variant for each request. UserSignal feedback updates the distributions.
Periodically mutates new variants by asking L1 to "improve this prompt."

Integration:
    ap = get_auto_prompt()
    prompt = ap.select(task_type)              # Thompson sample best variant
    result = await llm.chat([{prompt}, {query}])
    ap.feedback(task_type, variant_id, quality)  # from UserSignal

Every 50 requests, auto-mutates a new variant for ongoing improvement.
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Optional

from loguru import logger

DEFAULT_PROMPTS = {
    "general": "",
    "code": "Write clean, well-documented code with error handling.",
    "chat": "Keep responses friendly and concise.",
    "reasoning": "Think step by step. Show your reasoning before concluding.",
}


class AutoPrompt:
    """Self-optimizing prompt pool using Thompson Sampling."""

    _instance: Optional["AutoPrompt"] = None

    @classmethod
    def instance(cls) -> "AutoPrompt":
        if cls._instance is None:
            cls._instance = AutoPrompt()
        return cls._instance

    def __init__(self):
        self._pool: dict[str, dict[str, dict]] = {}  # task_type → variant_id → {text, alpha, beta}
        self._last_used: dict[str, str] = {}          # task_type → last variant_id used
        self._request_counts: dict[str, int] = {}
        self._init_defaults()

    def _init_defaults(self):
        for task_type, prompt in DEFAULT_PROMPTS.items():
            self._pool.setdefault(task_type, {})["default"] = {
                "text": prompt, "alpha": 5.0, "beta": 2.0,
            }

    def select(self, task_type: str) -> tuple[str, str]:
        """Select the best prompt variant via Thompson Sampling.

        Returns (prompt_text, variant_id).
        """
        variants = self._pool.get(task_type, {})
        if not variants:
            return DEFAULT_PROMPTS.get("general", ""), "default"

        # Thompson sample all variants
        samples = []
        for vid, v in variants.items():
            score = random.betavariate(
                max(v["alpha"], 0.1),
                max(v["beta"], 0.1),
            )
            samples.append((vid, score))

        samples.sort(key=lambda x: -x[1])
        best_vid = samples[0][0]
        self._last_used[task_type] = best_vid
        self._request_counts[task_type] = self._request_counts.get(task_type, 0) + 1

        # Every 50 requests, mutate a new variant
        if self._request_counts[task_type] % 50 == 0:
            self._schedule_mutation(task_type)

        return variants[best_vid]["text"], best_vid

    def feedback(self, task_type: str, variant_id: str, quality: float) -> None:
        """Update Beta distribution based on user satisfaction signal."""
        v = self._pool.get(task_type, {}).get(variant_id)
        if not v:
            return
        reward = min(1.0, max(0.0, quality))
        v["alpha"] += reward * 3.0
        v["beta"] += (1.0 - reward) * 3.0

    def last_variant(self, task_type: str) -> str:
        return self._last_used.get(task_type, "default")

    async def _schedule_mutation(self, task_type: str):
        """Generate a new prompt variant by asking an LLM."""
        try:
            current = self._pool.get(task_type, {}).get("default", {}).get("text", "")
            # Simple heuristic mutation: inject a strategy keyword
            strategies = [
                "Be concise and direct.",
                "Use examples to illustrate.",
                "Think step by step before answering.",
                "Consider edge cases and alternatives.",
                "Prioritize accuracy over speed.",
            ]
            new_text = current + " " + random.choice(strategies)
            n = len(self._pool.get(task_type, {}))
            vid = f"v{n}"
            self._pool.setdefault(task_type, {})[vid] = {
                "text": new_text, "alpha": 3.0, "beta": 3.0,
            }
            logger.info(f"AutoPrompt: mutated new variant {vid} for {task_type}")
        except Exception as e:
            logger.debug(f"AutoPrompt mutation: {e}")

    def stats(self) -> dict:
        return {
            task_type: {
                "variants": len(variants),
                "requests": self._request_counts.get(task_type, 0),
                "best": max(variants.items(), key=lambda x: x[1]["alpha"] /
                           max(x[1]["alpha"] + x[1]["beta"], 0.01))[0]
                if variants else "none",
            }
            for task_type, variants in self._pool.items()
        }


_auto_prompt: Optional[AutoPrompt] = None


def get_auto_prompt() -> AutoPrompt:
    global _auto_prompt
    if _auto_prompt is None:
        _auto_prompt = AutoPrompt()
    return _auto_prompt


__all__ = ["AutoPrompt", "get_auto_prompt"]
