"""Dream Integration — combine DreamSchool + WorldModel for sleep-time self-training.

Bridges two existing subsystems:
  1. DreamSchool: idle-time inter-head teaching (teacher → student via PlayEngine)
  2. WorldModel: JEPA-style consequence prediction (what if Y?)

Together they form a night-cycle that not only teaches but also simulates
the downstream effects of the learned lesson, creating a closed-loop
self-training system that operates while the system is idle.

Architecture:
    dream_cycle(consciousness) →
        ├─ DreamSchool.night_session() → teaching session
        ├─ If session completed:
        │   └─ WorldModel.simulate("student applies lesson") → predicted outcome
        ├─ Store dream record in FIFO buffer
        └─ Return enriched session dict

Integration:
    di = get_dream_integration()
    result = await di.dream_cycle(consciousness=consc)
    stats = di.stats()

Related modules:
    - dream_school.py — inter-head cooperative teaching
    - world_model.py — JEPA-style consequence prediction
    - play_engine.py — scenario-driven head interaction
    - shesha_heads.py — multi-head architecture
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from typing import Optional
from typing import List


@dataclass
class DreamRecord:
    """A single dream cycle: teaching session + predicted outcome."""
    teacher: str | None = None
    student: str | None = None
    session_status: str = "unknown"
    cooperation_score: float = 0.0
    predicted_outcome: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"Dream(teacher={self.teacher}, student={self.student}, "
            f"status={self.session_status}, cooperation={self.cooperation_score:.2f})"
        )


class DreamIntegration:
    """Integrates DreamSchool teaching with WorldModel consequence simulation.

    At night (system idle), heads teach each other via DreamSchool. Then
    WorldModel predicts what happens when the student applies the lesson —
    providing a "mental rehearsal" that strengthens learning through
    anticipated consequences. This mirrors human sleep consolidation:
    hippocampus replays experiences while cortex simulates futures.

    Usage:
        di = get_dream_integration()
        result = await di.dream_cycle(consciousness=consc)
        if result.get("status") == "completed":
            print(f"Dream: {result['teacher']} taught {result['student']}")
    """

    _MAX_DREAMS: int = 20
    _MAX_OUTCOME_PREVIEW: int = 200
    _MAX_SIM_PREVIEW: int = 120

    def __init__(self) -> None:
        self._dreams: deque[DreamRecord] = deque(maxlen=self._MAX_DREAMS)
        self._total_cycles: int = 0
        self._completed_cycles: int = 0
        self._last_cycle_time: float = 0.0

    # ── Dream cycle ────────────────────────────────────────────────

    async def dream_cycle(self, consciousness: Any = None) -> dict:
        """Run one full dream cycle: teach + simulate consequences.

        Args:
            consciousness: Optional shared consciousness for thought generation.
                           Passed through to both DreamSchool and WorldModel.

        Returns:
            {
                "status": "completed" | "not_enough_heads" | "skipped" | "error",
                "teacher": str | None,
                "student": str | None,
                "cooperation": float | None,
                "predicted_outcome": str | None,
                "dream_index": int,
            }
        """
        self._total_cycles += 1
        self._last_cycle_time = time.time()

            from .dream_school import get_dream_school
            from .world_model import get_world_model

            school = get_dream_school()
            wm = get_world_model(consciousness=consciousness)

            # ── Step 1: Run teaching session ──
            logger.debug("DreamIntegration: starting teaching session via DreamSchool")
            session = await school.night_session(consciousness=consciousness)

            status = session.get("status", "error")
            teacher = session.get("teacher")
            student = session.get("student")
            cooperation = session.get("cooperation", 0.0)

            predicted_outcome = None

            # ── Step 2: Simulate consequences if teaching succeeded ──
            if status == "completed" and teacher and student:
                sim_prompt = (
                    f"head '{student}' (the student) has just been taught "
                    f"a lesson by head '{teacher}' (the teacher) with "
                    f"cooperation score {cooperation:.2f}. "
                    f"Simulate: what does '{student}' do next? "
                    f"How does this learning affect the overall system?"
                )
                try:
                    outcome = await wm.simulate(
                        description=sim_prompt[:self._MAX_SIM_PREVIEW],
                        state=None,
                        consciousness=consciousness,
                    )
                    predicted_outcome = getattr(outcome, "reasoning", "")
                    if predicted_outcome:
                        predicted_outcome = predicted_outcome[:self._MAX_OUTCOME_PREVIEW]
                        logger.debug(
                            f"DreamIntegration: predicted outcome for "
                            f"{teacher}→{student}: {predicted_outcome[:60]}..."
                        )
                except Exception:
                    logger.warning(
                        f"DreamIntegration: WorldModel simulation failed for "
                        f"{teacher}→{student}"
                    )

            elif status == "completed" and (not teacher or not student):
                # Simulation without resolved teacher/student
                try:
                    outcome = await wm.simulate(
                        description="inter-head teaching session completed",
                        state=None,
                        consciousness=consciousness,
                    )
                    pred = getattr(outcome, "reasoning", "")
                    predicted_outcome = pred[:self._MAX_OUTCOME_PREVIEW] if pred else None
                except Exception:
                    pass

            # ── Step 3: Record dream ──
            record = DreamRecord(
                teacher=teacher,
                student=student,
                session_status=status,
                cooperation_score=cooperation if cooperation else 0.0,
                predicted_outcome=predicted_outcome or "",
                metadata={"dream_index": self._total_cycles},
            )
            self._dreams.append(record)

            if status == "completed":
                self._completed_cycles += 1

            logger.info(
                f"DreamIntegration: cycle #{self._total_cycles} — "
                f"status={status}, teacher={teacher}, student={student}"
            )

            return {
                "status": status,
                "teacher": teacher,
                "student": student,
                "cooperation": cooperation,
                "predicted_outcome": predicted_outcome,
                "dream_index": self._total_cycles,
            }

        except ImportError as e:
            logger.warning(f"DreamIntegration: required module not available — {e}")
            return {
                "status": "skipped",
                "teacher": None,
                "student": None,
                "cooperation": None,
                "predicted_outcome": None,
                "dream_index": self._total_cycles,
            }
        except Exception:
            logger.exception("DreamIntegration: dream cycle failed")
            return {
                "status": "error",
                "teacher": None,
                "student": None,
                "cooperation": None,
                "predicted_outcome": None,
                "dream_index": self._total_cycles,
            }

    # ── Bulk cycles ────────────────────────────────────────────────

    async def dream_night(
        self, cycles: int = 3, consciousness: Any = None
    ) -> list[dict]:
        """Run multiple dream cycles (a full "night" of sleeping).

        Args:
            cycles: Number of dream cycles to run (default 3).
            consciousness: Optional consciousness instance.

        Returns:
            List of cycle result dicts.
        """
        results: list[dict] = []
        for i in range(cycles):
            logger.debug(f"DreamIntegration: night cycle {i + 1}/{cycles}")
            result = await self.dream_cycle(consciousness=consciousness)
            if result:
                results.append(result)
            # Brief pause between cycles to allow state changes
            await _async_sleep(0.1)
        logger.info(
            f"DreamIntegration: night complete — "
            f"{len(results)} cycles, "
            f"{sum(1 for r in results if r.get('status') == 'completed')} completed"
        )
        return results

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return summary statistics for dream integration."""
        recent = list(self._dreams)[-5:]
        return {
            "total_cycles": self._total_cycles,
            "completed_cycles": self._completed_cycles,
            "completion_rate": (
                self._completed_cycles / max(self._total_cycles, 1)
            ),
            "total_dreams_stored": len(self._dreams),
            "last_cycle_time": self._last_cycle_time,
            "last_dream": (
                {
                    "teacher": self._dreams[-1].teacher,
                    "student": self._dreams[-1].student,
                    "status": self._dreams[-1].session_status,
                    "cooperation": self._dreams[-1].cooperation_score,
                }
                if self._dreams
                else None
            ),
            "recent_dreams": [
                {
                    "teacher": d.teacher,
                    "student": d.student,
                    "status": d.session_status,
                    "cooperation": d.cooperation_score,
                    "timestamp": d.timestamp,
                }
                for d in reversed(recent)
            ],
        }

    def dreams(self) -> list[DreamRecord]:
        """Return all stored dream records."""
        return list(self._dreams)


# ═══ Internal helpers ═══


async def _async_sleep(seconds: float) -> None:
    """Lightweight async sleep — avoids asyncio import at module level."""
        import asyncio as _aio
        await _aio.sleep(seconds)
    except Exception:
        time.sleep(max(seconds, 0))


# ═══ Singleton ═══

_dream_integration: DreamIntegration | None = None


def get_dream_integration() -> DreamIntegration:
    """Get or create the global DreamIntegration singleton."""
    global _dream_integration
    if _dream_integration is None:
        _dream_integration = DreamIntegration()
        logger.info("DreamIntegration singleton initialized")
    return _dream_integration


__all__ = [
    "DreamRecord",
    "DreamIntegration",
    "get_dream_integration",
]
