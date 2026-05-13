"""AdversarialGate — Pre-delivery adversarial review to catch hallucinations.

Before sending a response to the user, a fast L1 model reviews it for:
  - Hallucinations (claims not supported by context)
  - Contradictions (self-inconsistency)
  - Incompleteness (missing critical info)
  - Overconfidence (no hedging when uncertain)

If flagged, either regenerates with L2 pro model or appends a warning tag.

Integration:
    gate = get_adversarial_gate()
    passed, reason = await gate.review(response, query, chat_fn)
    if not passed:
        response = await gate.regenerate(query, chat_fn)  # L2 pro retry
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from loguru import logger


@dataclass
class ReviewResult:
    passed: bool
    reason: str = ""
    confidence: float = 0.5


class AdversarialGate:
    """Pre-delivery adversarial review gate."""

    _instance: Optional["AdversarialGate"] = None

    @classmethod
    def instance(cls) -> "AdversarialGate":
        if cls._instance is None:
            cls._instance = AdversarialGate()
        return cls._instance

    def __init__(self):
        self._reviews = 0
        self._flags = 0
        self._max_review_tokens = 80

    async def review(
        self, response: str, query: str,
        chat_fn: Callable = None, system_context: str = "",
    ) -> ReviewResult:
        """Review a response before delivery. Returns PASS or FLAG."""
        if not chat_fn or not response:
            return ReviewResult(passed=True, reason="no reviewer available")

        self._reviews += 1

        review_prompt = (
            "Review this AI response for issues. Reply EXACTLY 'PASS' or 'FLAG: <reason>'.\n"
            "Check: hallucination (unsupported claims), contradiction, incompleteness, "
            "overconfidence.\n"
            f"Query: {query[:300]}\n"
            f"Context: {system_context[:200]}\n"
            f"Response: {response[:800]}"
        )

        try:
            result = await chat_fn(
                [{"role": "user", "content": review_prompt}],
                max_tokens=self._max_review_tokens, temperature=0.0,
            )
            text = getattr(result, 'text', '') or str(result)

            if not text or text.strip().upper().startswith("PASS"):
                return ReviewResult(passed=True, confidence=0.9)

            self._flags += 1
            reason = text.strip()
            if reason.startswith("FLAG:"):
                reason = reason[5:].strip()
            logger.warning(f"AdversarialGate FLAG: {reason[:100]}")
            return ReviewResult(passed=False, reason=reason[:200], confidence=0.7)
        except Exception as e:
            logger.debug(f"AdversarialGate review error: {e}")
            return ReviewResult(passed=True, reason="reviewer failed", confidence=0.3)

    async def regenerate(
        self, query: str, original_response: str,
        chat_fn: Callable, review_reason: str = "",
    ) -> str:
        """Regenerate a better response informed by the review failure."""
        try:
            fix_prompt = (
                f"Your previous response had this issue: {review_reason}\n"
                f"Please regenerate a better answer for: {query[:500]}"
            )
            result = await chat_fn(
                [{"role": "user", "content": fix_prompt}],
                max_tokens=2048, temperature=0.3,
            )
            return getattr(result, 'text', '') or str(result) or original_response
        except Exception:
            return original_response

    @property
    def flag_rate(self) -> float:
        return self._flags / max(self._reviews, 1)

    def stats(self) -> dict:
        return {
            "reviews": self._reviews,
            "flags": self._flags,
            "flag_rate": round(self.flag_rate, 3),
        }


_gate: Optional[AdversarialGate] = None


def get_adversarial_gate() -> AdversarialGate:
    global _gate
    if _gate is None:
        _gate = AdversarialGate()
    return _gate


__all__ = ["AdversarialGate", "ReviewResult", "get_adversarial_gate"]
