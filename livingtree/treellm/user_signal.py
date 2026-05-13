"""UserSignal — Implicit user feedback collector for routing optimization.

Instead of asking "was this helpful?", infers satisfaction from user behavior:
  - User continues conversation within 30s → positive signal
  - User repeats question or corrects → negative signal
  - User abandons session → neutral

Feeds into CompetitiveEliminator Elo updates and RouteLearner weight adjustment.

Integration:
    collector = get_user_signal()
    collector.mark_response(session_id, provider, query)
    # On next message:
    signal = collector.on_next_message(session_id, message)
    if signal: get_eliminator().record_match(provider, quality=signal.quality, ...)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from loguru import logger


@dataclass
class UserSignal:
    provider: str
    quality: float          # 0.0-1.0 inferred quality
    confidence: float        # How confident we are in this signal
    reason: str


class UserSignalCollector:
    """Infers user satisfaction from implicit behavioral signals."""

    _instance: Optional["UserSignalCollector"] = None

    @classmethod
    def instance(cls) -> "UserSignalCollector":
        if cls._instance is None:
            cls._instance = UserSignalCollector()
        return cls._instance

    def __init__(self):
        self._pending: dict[str, tuple[str, str, float]] = {}  # sid → (provider, query, ts)

    def mark_response(self, session_id: str, provider: str, query: str = "") -> None:
        """Mark that a response was delivered for this session."""
        self._pending[session_id] = (provider, query[:200], time.time())
        # Cleanup old entries
        if len(self._pending) > 1000:
            old = sorted(self._pending.keys(),
                         key=lambda k: self._pending[k][2])[:200]
            for k in old:
                del self._pending[k]

    def on_next_message(self, session_id: str, message: str) -> Optional[UserSignal]:
        """Process user's next message and derive a satisfaction signal."""
        entry = self._pending.pop(session_id, None)
        if not entry:
            return None

        provider, original_query, ts = entry
        elapsed = time.time() - ts

        # Positive: user continues conversation quickly → good response
        if elapsed < 30:
            return UserSignal(
                provider=provider,
                quality=0.8,
                confidence=0.7,
                reason="user_continued_quickly",
            )

        # Negative: explicit correction keywords
        neg_keywords = ["不对", "错了", "重新", "wrong", "incorrect", "不是", "错误",
                        "no", "bad", "不要", "不对的"]
        msg_lower = message.lower()
        if any(k in msg_lower for k in neg_keywords):
            return UserSignal(
                provider=provider,
                quality=0.2,
                confidence=0.8,
                reason="user_corrected",
            )

        # Negative: user repeats nearly the same question
        if original_query and _jaccard_similarity(original_query[:100], message[:100]) > 0.7:
            return UserSignal(
                provider=provider,
                quality=0.3,
                confidence=0.6,
                reason="user_repeated_query",
            )

        # Neutral: user continues after delay (no strong signal)
        if elapsed < 300:
            return UserSignal(
                provider=provider,
                quality=0.5,
                confidence=0.3,
                reason="user_continued_delayed",
            )

        return None

    def on_session_end(self, session_id: str) -> Optional[UserSignal]:
        """Session ended without follow-up — weak negative signal."""
        entry = self._pending.pop(session_id, None)
        if not entry:
            return None
        provider, _, ts = entry
        elapsed = time.time() - ts
        if elapsed > 120:
            return UserSignal(
                provider=provider,
                quality=0.4,
                confidence=0.3,
                reason="session_abandoned",
            )
        return None

    def stats(self) -> dict:
        return {"pending_sessions": len(self._pending)}


def _jaccard_similarity(a: str, b: str) -> float:
    set_a = set(a.split())
    set_b = set(b.split())
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


_user_signal: Optional[UserSignalCollector] = None


def get_user_signal() -> UserSignalCollector:
    global _user_signal
    if _user_signal is None:
        _user_signal = UserSignalCollector()
    return _user_signal


__all__ = ["UserSignalCollector", "UserSignal", "get_user_signal"]
