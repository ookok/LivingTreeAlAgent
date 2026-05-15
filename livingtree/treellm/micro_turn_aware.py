"""MicroTurnAware — Time-aware routing with micro-turn sensitivity.

Based on Thinking Machines Lab "Interaction Models" (May 2026):
  "Time-aligned micro-turns... there are no artificial turn boundaries.
   The model can do things like speak while listening or react to visual
   cues without explicit prompting. Silence, overlap, and interruption
   remain part of the model's context."

Key insight: In the TML architecture, the model operates on 200ms micro-turns
where input and output streams are interleaved. The model perceives the user's
stream continuously — it doesn't wait for a complete "turn" to respond.

For LivingTree (text-based, multi-LM orchestration):
  - Detect user typing patterns (speed, pauses, deletions)
  - Classify micro-turn state: thinking, typing, pausing, done
  - Calculate optimal response timing
  - Predict when pro model insights should be woven into flash stream
  - Track conversational rhythm for natural interaction

Design:
  The MicroTurnAware engine sits BETWEEN user input and the routing system.
  It classifies the current conversational state and advises when to route,
  when to wait, and when to interject.

Usage:
    mta = get_micro_turn_aware()
    state = mta.classify(current_text, time_since_last_input=0.8, is_typing=True)
    if state == MicroTurnState.USER_DONE:
        await route_layered(...)
    elif state == MicroTurnState.INSERTION_POINT:
        weave_pro_insight(...)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


class MicroTurnState(StrEnum):
    """Classification of the current conversational micro-turn state.

    From TML: the model should maintain awareness of whether the speaker
    is: thinking, yielding, self-correcting, or inviting a response.
    """
    USER_TYPING = "user_typing"          # Actively composing input
    USER_THINKING = "user_thinking"      # Paused, likely deliberating
    USER_CORRECTING = "user_correcting"  # Deleting/rewriting
    USER_DONE = "user_done"              # Finished, expects response
    USER_CONTINUING = "user_continuing"  # More to say after brief pause
    INSERTION_POINT = "insertion_point"  # Good moment to weave pro insight
    INTERRUPT_NEEDED = "interrupt_needed" # Model should proactively interject
    CONVERSATION_IDLE = "conversation_idle"  # No recent activity


@dataclass
class TurnTiming:
    """Timing data for a micro-turn transition."""
    state: MicroTurnState
    duration_ms: float = 0.0            # How long in this state
    time_since_last_input_ms: float = 0.0
    text_length: int = 0
    text_growth_rate: float = 0.0       # chars per second
    deletion_count: int = 0             # Backspace/delete events
    pause_count: int = 0                # Number of pauses > 200ms
    is_sentence_complete: bool = False  # Ends with .!?。！？


@dataclass
class MicroTurnContext:
    """Full micro-turn context for routing decisions."""
    current_state: MicroTurnState
    current_text: str = ""
    timing: TurnTiming = field(default_factory=lambda: TurnTiming(state=MicroTurnState.CONVERSATION_IDLE))
    state_history: list[TurnTiming] = field(default_factory=list)
    conversation_rhythm: float = 0.5    # 0=rapid exchange, 1=deliberative
    optimal_response_delay_ms: float = 500.0
    should_route_now: bool = False
    should_probe_deep: bool = False
    weave_opportunity: bool = False


# ═══ MicroTurnAware Engine ════════════════════════════════════════


class MicroTurnAware:
    """Time-aware micro-turn classification engine.

    Design: Tracks the rhythm of user input at ~200ms resolution to determine
    the optimal moment for routing, interjecting, or weaving pro insights.

    From TML: "200ms chunks of these streams enables near real-time
    concurrency of multiple input and output modalities."
    """

    MICRO_TURN_MS = 200                 # TML's micro-turn resolution
    THINKING_PAUSE_MS = 800             # Pause > this = likely thinking
    DONE_PAUSE_MS = 2000                # Pause > this = likely done
    CONTINUING_PAUSE_MS = 500           # Pause < this = likely continuing
    CORRECTION_BURST_MS = 300           # Rapid delete+type = correcting
    MIN_TEXT_FOR_DONE = 10              # At least this many chars before "done"
    WEAVE_COOLDOWN_MS = 3000            # Minimum gap between weave insertions

    # Text growth rate thresholds (chars/second)
    TYPING_FAST = 8.0                   # Fast typing
    TYPING_SLOW = 2.0                   # Slow/deliberate typing

    def __init__(self, conversation_id: str = ""):
        self._conv_id = conversation_id
        self._text_history: list[tuple[float, str]] = []  # (timestamp, text)
        self._last_weave_time: float = 0.0
        self._state_start_time: float = time.time()
        self._current_state = MicroTurnState.CONVERSATION_IDLE
        self._state_durations: dict[str, float] = {}
        self._delete_count: int = 0
        self._sessions: int = 0

    # ── Main Classification ───────────────────────────────────────

    def classify(
        self, current_text: str, time_since_last_input: float = 0.0,
        is_typing: bool = False, deletion_occurred: bool = False,
    ) -> MicroTurnContext:
        """Classify the current conversational micro-turn state.

        Args:
            current_text: Current accumulated user text.
            time_since_last_input: Seconds since last keystroke/input event.
            is_typing: Whether user is actively composing.
            deletion_occurred: Whether the user just deleted text.

        Returns:
            MicroTurnContext with state classification and routing advice.
        """
        now = time.time()
        timing = TurnTiming(
            state=self._current_state,
            time_since_last_input_ms=time_since_last_input * 1000,
            text_length=len(current_text),
            deletion_count=self._delete_count,
        )

        # ── State classification ──
        if is_typing and deletion_occurred:
            new_state = MicroTurnState.USER_CORRECTING
            timing.text_growth_rate = 0.0

        elif is_typing:
            new_state = MicroTurnState.USER_TYPING
            timing.text_growth_rate = self._compute_growth_rate(current_text)

        elif time_since_last_input > self.DONE_PAUSE_MS / 1000:
            new_state = MicroTurnState.USER_DONE
            timing.text_growth_rate = 0.0
            timing.is_sentence_complete = self._is_sentence_complete(current_text)

        elif time_since_last_input > self.THINKING_PAUSE_MS / 1000:
            new_state = MicroTurnState.USER_THINKING
            timing.text_growth_rate = 0.0

        elif time_since_last_input > self.CONTINUING_PAUSE_MS / 1000:
            new_state = MicroTurnState.USER_CONTINUING
            timing.text_growth_rate = self._compute_growth_rate(current_text)

        else:
            # Still within brief pause — likely continuing
            new_state = MicroTurnState.USER_TYPING
            timing.text_growth_rate = self._compute_growth_rate(current_text)

        # ── Track state transitions ──
        if new_state != self._current_state:
            self._state_durations[self._current_state] = now - self._state_start_time
            self._state_start_time = now
            self._current_state = new_state

        timing.state = self._current_state
        timing.duration_ms = (now - self._state_start_time) * 1000

        # ── State history (keep last 10) ──
        self._text_history.append((now, current_text))
        if len(self._text_history) > 10:
            self._text_history = self._text_history[-10:]

        # ── Compute conversation rhythm ──
        rhythm = self._compute_rhythm(timing)

        # ── Compute optimal response delay ──
        optimal_delay = self._compute_optimal_delay(timing, rhythm)

        # ── Routing advice ──
        should_route = self._should_route_now(timing, new_state, current_text)
        should_deep = self._should_probe_deep(timing, new_state, current_text)
        can_weave = self._is_weave_opportunity(timing, new_state)

        context = MicroTurnContext(
            current_state=self._current_state,
            current_text=current_text,
            timing=timing,
            state_history=[],  # simplified — rebuild from _text_history if needed
            conversation_rhythm=rhythm,
            optimal_response_delay_ms=optimal_delay,
            should_route_now=should_route,
            should_probe_deep=should_deep,
            weave_opportunity=can_weave,
        )

        logger.debug(
            f"MicroTurnAware: state={self._current_state} "
            f"pause={timing.time_since_last_input_ms:.0f}ms "
            f"route={should_route} deep={should_deep} weave={can_weave}"
        )

        return context

    # ── State Detection Logic ─────────────────────────────────────

    @staticmethod
    def _is_sentence_complete(text: str) -> bool:
        """Check if text ends with a sentence terminator."""
        if not text:
            return False
        terminators = [". ", "。", "!", "！", "?", "？", ".\n", "\n\n"]
        return any(text.rstrip().endswith(t) or text.rstrip()[-1] in ".!?。！？" for t in terminators)

    def _compute_growth_rate(self, current_text: str) -> float:
        """Compute text growth rate in chars/second from history."""
        if len(self._text_history) < 2:
            return 0.0
        # Compare current text to 2 seconds ago
        now = time.time()
        for ts, text in reversed(self._text_history):
            if now - ts >= 2.0:
                delta_chars = len(current_text) - len(text)
                delta_time = now - ts
                return delta_chars / max(delta_time, 0.1)
        return 0.0

    def _compute_rhythm(self, timing: TurnTiming) -> float:
        """Compute conversation rhythm score (0=rapid, 1=deliberative).

        Based on: typing speed, pause frequency, correction frequency.
        """
        rhythm = 0.5  # neutral
        if timing.text_growth_rate > self.TYPING_FAST:
            rhythm -= 0.2  # Fast = more rapid
        elif timing.text_growth_rate < self.TYPING_SLOW and timing.text_growth_rate > 0:
            rhythm += 0.2  # Slow = more deliberative
        if timing.pause_count > 2:
            rhythm += 0.15
        if timing.deletion_count > 0:
            rhythm += 0.1  # Corrections suggest deliberation
        return max(0.0, min(1.0, rhythm))

    def _compute_optimal_delay(self, timing: TurnTiming, rhythm: float) -> float:
        """Compute optimal response delay in milliseconds.

        Fast conversation → respond quickly. Deliberative → give more time.
        """
        base_delay = 500.0  # ms
        if rhythm > 0.7:  # Deliberative
            base_delay = 800.0
        elif rhythm < 0.3:  # Rapid
            base_delay = 250.0

        if timing.is_sentence_complete:
            base_delay -= 200.0  # Sentence complete → respond faster

        return max(100.0, base_delay)

    def _should_route_now(
        self, timing: TurnTiming, state: MicroTurnState, text: str,
    ) -> bool:
        """Determine if now is the right moment to route to a model."""
        if state == MicroTurnState.USER_DONE:
            return len(text) >= self.MIN_TEXT_FOR_DONE
        if state == MicroTurnState.USER_CORRECTING:
            return False  # User is revising — wait
        if state == MicroTurnState.USER_THINKING and timing.duration_ms > 3000:
            # User has been thinking for >3 seconds — might need help
            return len(text) >= self.MIN_TEXT_FOR_DONE
        return False

    def _should_probe_deep(
        self, timing: TurnTiming, state: MicroTurnState, text: str,
    ) -> bool:
        """Determine if DeepProbe should be applied.

        Deep probing is more valuable when:
          - User has been deliberative (slow typing, many pauses)
          - Text is substantive (long, with complex structure)
          - User self-corrected (signal of careful thinking)
        """
        if state != MicroTurnState.USER_DONE:
            return False
        if len(text) < 50:
            return False
        if timing.deletion_count > 0:
            return True  # Self-correction → user cares about precision
        if timing.pause_count > 3:
            return True  # Many pauses → complex thinking
        if timing.text_growth_rate < self.TYPING_SLOW and len(text) > 200:
            return True  # Slow typing + long text = deep topic
        return False

    def _is_weave_opportunity(
        self, timing: TurnTiming, state: MicroTurnState,
    ) -> bool:
        """Check if now is a good time to weave a pro model insight.

        Weave points: after user completes a thought (sentence end) and
        enough time has passed since the last weave.
        """
        if not timing.is_sentence_complete:
            return False
        if state not in (MicroTurnState.USER_DONE, MicroTurnState.USER_THINKING):
            return False
        now = time.time()
        if now - self._last_weave_time < self.WEAVE_COOLDOWN_MS / 1000:
            return False
        return True

    def mark_weave_complete(self) -> None:
        """Mark that a weave just happened — resets cooldown."""
        self._last_weave_time = time.time()

    # ── Session Management ────────────────────────────────────────

    def reset(self) -> None:
        """Reset for a new conversation."""
        self._text_history.clear()
        self._delete_count = 0
        self._state_start_time = time.time()
        self._current_state = MicroTurnState.CONVERSATION_IDLE
        self._last_weave_time = 0.0
        self._sessions += 1

    # ── Statistics ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        total_duration = sum(self._state_durations.values())
        return {
            "sessions": self._sessions,
            "current_state": self._current_state,
            "state_distribution": {
                k: round(v / max(total_duration, 1), 3)
                for k, v in self._state_durations.items()
            },
            "text_history_depth": len(self._text_history),
            "weave_cooldown_remaining_ms": max(
                0.0, self.WEAVE_COOLDOWN_MS - (time.time() - self._last_weave_time) * 1000,
            ),
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_mta: Optional[MicroTurnAware] = None
_mta_lock = threading.Lock()


def get_micro_turn_aware() -> MicroTurnAware:
    global _mta
    if _mta is None:
        with _mta_lock:
            if _mta is None:
                _mta = MicroTurnAware()
    return _mta


__all__ = [
    "MicroTurnAware", "MicroTurnState", "MicroTurnContext", "TurnTiming",
    "get_micro_turn_aware",
]
