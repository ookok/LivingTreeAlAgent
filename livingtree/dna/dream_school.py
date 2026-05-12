"""DreamSchool — idle-time inter-head learning via cooperative play.

When the system is idle, Shesha heads teach each other through cooperative
play scenarios. The highest-phase head (most experienced) teaches the
lowest-phase head (least experienced), using the PlayEngine's TEACHING
scenario. The learning outcome is recorded for analytics.

Core flow (Mumford 2026 "AIs and Humans with Agency" + Shesha architecture):
    idle → DreamSchool.night_session() →
        ├─ Find teacher (max total_tasks head)
        ├─ Find student (min total_tasks head)
        ├─ Run PlayEngine TEACHING scenario
        └─ Record cooperation score

Integration:
    ds = get_dream_school()
    outcome = await ds.night_session(consciousness=consc)
    stats = ds.stats()
"""

from __future__ import annotations

import random
import time
from typing import Any

from loguru import logger


class DreamSchool:
    """Night school: when system is idle, Shesha heads teach each other.

    Inspired by human memory consolidation during sleep (hippocampal replay)
    and Mumford's multi-head theory: each head has independent experiences
    that can benefit other heads through structured teaching play.

    Usage:
        ds = get_dream_school()
        result = await ds.night_session(consciousness=world.consciousness)
        print(ds.stats())
    """

    def __init__(self) -> None:
        self._sessions: list[dict] = []
        self._total_sessions: int = 0
        self._last_session_time: float = 0.0

    # ── Night session ──────────────────────────────────────────────

    async def night_session(self, consciousness: Any = None) -> dict:
        """Run one night school session: teacher head teaches student head.

        Args:
            consciousness: Shared TreeLLM/Consciousness for thought generation.
                           If None, PlayEngine will use simulated thinking.

        Returns:
            {
                "status": "completed" | "not_enough_heads" | "error",
                "teacher": str (head name) | None,
                "student": str (head name) | None,
                "cooperation": float (0.0–1.0) | None,
            }
        """
        try:
            from .shesha_heads import get_shesha
            from .play_engine import get_play_engine, PlayScenario

            shesha = get_shesha()
            play = get_play_engine()

            heads = shesha.list_heads()
            if heads is None:
                heads = []
            if len(heads) < 2:
                return {"status": "not_enough_heads", "teacher": None, "student": None}

            # ── Find teacher and student ──
            # Teacher: head with most tasks completed (highest experience)
            # Student: head with fewest tasks completed (lowest experience)
            teacher = max(heads, key=lambda h: getattr(h, "total_tasks", 0))
            student = min(heads, key=lambda h: getattr(h, "total_tasks", 0))

            # Don't teach if they're the same head
            if getattr(teacher, "name", str(teacher)) == getattr(student, "name", str(student)):
                # Fall back to random selection
                others = [h for h in heads if h is not teacher]
                if not others:
                    return {"status": "not_enough_heads", "teacher": None, "student": None}
                student = others[0]

            teacher_name = getattr(teacher, "name", str(teacher))
            student_name = getattr(student, "name", str(student))

            # ── Run teaching scenario ──
            teacher_id = getattr(teacher, "head_id", teacher_name)
            student_id = getattr(student, "head_id", student_name)

            outcome = await play.run_scenario(
                PlayScenario.TEACHING,
                [teacher_id, student_id],
                consciousness,
            )

            cooperation = outcome.cooperation_score if outcome else 0.5

            # ── Record session ──
            session_record = {
                "teacher": teacher_name,
                "student": student_name,
                "cooperation": cooperation,
                "timestamp": time.time(),
            }
            self._sessions.append(session_record)
            self._total_sessions += 1
            self._last_session_time = time.time()
            # Keep last 200 sessions
            if len(self._sessions) > 200:
                self._sessions = self._sessions[-200:]

            logger.info(
                f"DreamSchool #{self._total_sessions}: {teacher_name} taught {student_name} "
                f"(cooperation={cooperation:.2f})"
            )

            return {
                "status": "completed",
                "teacher": teacher_name,
                "student": student_name,
                "cooperation": cooperation,
            }

        except Exception as e:
            logger.debug(f"DreamSchool night_session failed: {e}")
            return {
                "status": "error",
                "teacher": None,
                "student": None,
                "error": str(e)[:200],
            }

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return dream school statistics for monitoring."""
        if not self._sessions:
            return {"total_sessions": 0, "avg_cooperation": 0.0}
        avg_coop = sum(s.get("cooperation", 0.0) for s in self._sessions) / len(self._sessions)
        return {
            "total_sessions": len(self._sessions),
            "avg_cooperation": round(avg_coop, 3),
            "last_session_time": self._last_session_time,
        }


# ═══ Singleton ═══

_school: DreamSchool | None = None


def get_dream_school() -> DreamSchool:
    """Get or create the global DreamSchool singleton."""
    global _school
    if _school is None:
        _school = DreamSchool()
        logger.info("DreamSchool singleton initialized")
    return _school


__all__ = [
    "DreamSchool",
    "get_dream_school",
]
