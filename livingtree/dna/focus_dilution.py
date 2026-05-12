"""Focus-Dilution Scheduler — Multi-stage attention learning cycle.

Based on SJTU Math4AI (Chen, Lin, Xu & Luo, ICML 2026 Spotlight):
  "Focus and Dilution: The Multi-stage Learning Process of Attention"

Key finding: Attention training is NOT monotonic. It repeatedly cycles through:
  1. FOCUS:   Embedding + projection condense to near rank-1, attention focuses on
              high-frequency tokens. (parameters freeze except attention weights)
  2. DILUTION: Attention growth induces second-order perturbation in embeddings,
              redistributing weight and diluting the previous focus.
  3. RE-FOCUS: Low-frequency asymmetries break the degenerate critical point,
              opening new embedding directions → next learning cycle begins.

Implications for LivingTree's 7-stage pipeline:
  The pipeline itself IS a focus-dilution cycle:
    perceive → FOCUS (condense on relevant information)
    cognize  → FOCUS (align embeddings with intent)
    plan     → DILUTION (redistribute attention across options)
    execute  → FOCUS (commit to specific actions)
    reflect  → DILUTION (re-distribute learnings broadly)

  We can make this EXPLICIT: schedule focus/dilute phases and
  detect when a cycle completes to trigger the next one.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


class FocusPhase(str, Enum):
    """Focus-Dilution cycle phase."""
    FOCUS = "focus"         # Concentrating attention, high gradient on specific params
    DILUTION = "dilution"   # Redistributing weight, exploring alternatives
    RE_FOCUS = "re_focus"   # Breaking symmetry, opening new directions
    IDLE = "idle"           # Between cycles


@dataclass
class CycleSnapshot:
    """A complete focus-dilution cycle record."""
    cycle_id: int
    focus_duration_ms: float = 0.0
    dilution_duration_ms: float = 0.0
    refocus_duration_ms: float = 0.0
    focus_params: list[str] = field(default_factory=list)    # Which params were focused
    dilution_params: list[str] = field(default_factory=list) # Which params were diluted
    new_directions: int = 0  # New embedding directions discovered
    timestamp: float = field(default_factory=time.time)


class FocusDilutionScheduler:
    """Explicitly schedule focus-dilution cycles in the reasoning pipeline.

    Based on the paper's finding that attention learning is multi-stage
    with repeated focus→dilute→re-focus cycles. We make this explicit
    in the LivingTree pipeline to:
      1. Prevent over-focusing (rank collapse) → schedule dilution
      2. Ensure sufficient exploration → delay re-focus until stable
      3. Track cycle patterns → optimize for different task types
    """

    def __init__(self):
        self._current_phase = FocusPhase.IDLE
        self._phase_start = time.time()
        self._cycles: list[CycleSnapshot] = []
        self._current_cycle: Optional[CycleSnapshot] = None
        self._focus_count = 0
        self._dilution_count = 0
        self._cycle_id = 0

        # Scheduling parameters
        self.min_focus_duration_ms = 500
        self.min_dilution_duration_ms = 300
        self.focus_threshold = 3          # After N focus steps, trigger dilution
        self.dilution_threshold = 2       # After N dilution steps, trigger re-focus

    def step(self, phase: str, metadata: dict = None) -> FocusPhase:
        """Advance the focus-dilution cycle by one step.

        Called after each pipeline stage (perceive, cognize, plan, etc.).

        Args:
            phase: Pipeline phase name ("perceive", "cognize", "plan", "execute", "reflect").
            metadata: Optional metadata about the current step.

        Returns:
            Current FocusPhase (what mode should the system be in).
        """
        self._ensure_cycle()

        # Map pipeline phase to focus/dilution tendency
        if phase in ("perceive", "cognize", "execute"):
            self._focus_count += 1
            self._current_cycle.focus_params.append(phase)
        elif phase in ("plan", "reflect"):
            self._dilution_count += 1
            self._current_cycle.dilution_params.append(phase)

        # State transitions based on the paper's findings
        old_phase = self._current_phase

        if self._current_phase == FocusPhase.IDLE:
            self._current_phase = FocusPhase.FOCUS
            self._phase_start = time.time()

        elif self._current_phase == FocusPhase.FOCUS:
            elapsed = (time.time() - self._phase_start) * 1000
            if self._focus_count >= self.focus_threshold and elapsed >= self.min_focus_duration_ms:
                # Paper: "attention growth induces second-order perturbation"
                # → we've focused enough, time to dilute
                self._current_phase = FocusPhase.DILUTION
                self._phase_start = time.time()
                self._current_cycle.focus_duration_ms = elapsed

        elif self._current_phase == FocusPhase.DILUTION:
            elapsed = (time.time() - self._phase_start) * 1000
            if self._dilution_count >= self.dilution_threshold and elapsed >= self.min_dilution_duration_ms:
                # Paper: "low-frequency asymmetries break degenerate critical point"
                # → dilution has redistributed, time to re-focus
                self._current_phase = FocusPhase.RE_FOCUS
                self._phase_start = time.time()
                self._current_cycle.dilution_duration_ms = elapsed

        elif self._current_phase == FocusPhase.RE_FOCUS:
            # After re-focus, start a new cycle
            self._current_cycle.refocus_duration_ms = (time.time() - self._phase_start) * 1000
            self._cycles.append(self._current_cycle)
            self._cycle_id += 1
            self._current_cycle = CycleSnapshot(cycle_id=self._cycle_id)
            self._focus_count = 0
            self._dilution_count = 0
            self._current_phase = FocusPhase.FOCUS
            self._phase_start = time.time()

        # Log transitions
        if old_phase != self._current_phase:
            logger.debug(
                f"FocusDilution: {old_phase.value} → {self._current_phase.value} "
                f"(focus_steps={self._focus_count}, dilution_steps={self._dilution_count})"
            )

        return self._current_phase

    def should_focus(self) -> bool:
        """Check if the system should be in FOCUS mode (concentrate attention)."""
        return self._current_phase in (FocusPhase.FOCUS, FocusPhase.RE_FOCUS)

    def should_dilute(self) -> bool:
        """Check if the system should be in DILUTION mode (explore broadly)."""
        return self._current_phase == FocusPhase.DILUTION

    def get_topk_factor(self) -> float:
        """Get retrieval top_k multiplier based on current phase.

        FOCUS: narrow search (0.5x top_k)
        DILUTION: broad search (2x top_k)
        RE_FOCUS: expanding search (1.5x top_k)
        """
        mapping = {
            FocusPhase.FOCUS: 0.5,
            FocusPhase.DILUTION: 2.0,
            FocusPhase.RE_FOCUS: 1.5,
            FocusPhase.IDLE: 1.0,
        }
        return mapping.get(self._current_phase, 1.0)

    def get_temperature_shift(self) -> float:
        """Get temperature adjustment for LLM generation based on phase.

        FOCUS: lower temperature (more deterministic, exploit)
        DILUTION: higher temperature (more random, explore)
        """
        mapping = {
            FocusPhase.FOCUS: -0.2,
            FocusPhase.DILUTION: +0.3,
            FocusPhase.RE_FOCUS: +0.1,
            FocusPhase.IDLE: 0.0,
        }
        return mapping.get(self._current_phase, 0.0)

    # ── Query ──

    @property
    def current_phase(self) -> FocusPhase:
        return self._current_phase

    @property
    def cycle_count(self) -> int:
        return len(self._cycles)

    @property
    def cycle_summary(self) -> dict:
        """Summary of all completed cycles."""
        if not self._cycles:
            return {"cycles": 0, "avg_focus_ms": 0, "avg_dilution_ms": 0}

        avg_focus = sum(c.focus_duration_ms for c in self._cycles) / len(self._cycles)
        avg_dilute = sum(c.dilution_duration_ms for c in self._cycles) / len(self._cycles)

        return {
            "cycles": len(self._cycles),
            "current_phase": self._current_phase.value,
            "avg_focus_ms": round(avg_focus, 0),
            "avg_dilution_ms": round(avg_dilute, 0),
            "focus_steps": self._focus_count,
            "dilution_steps": self._dilution_count,
        }

    # ── Internal ──

    def _ensure_cycle(self) -> None:
        if self._current_cycle is None:
            self._current_cycle = CycleSnapshot(cycle_id=self._cycle_id)


# ── Singleton ──

_scheduler: Optional[FocusDilutionScheduler] = None


def get_focus_dilution_scheduler() -> FocusDilutionScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = FocusDilutionScheduler()
    return _scheduler
