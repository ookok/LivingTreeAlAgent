"""SessionBinding — keeps models sticky within a conversation session.

    Prevents jarring model switches mid-conversation. A model is "bound"
    to a session and stays unless there's a clear reason to switch.

    Switch conditions (only these trigger a change):
    1. Current model rate-limited (429 penalty > 0.5)
    2. Current model dead (ping failed)
    3. Cost saving > 50% (free model became available)
    4. Task type shifted dramatically (chat → reasoning)
    5. User explicitly requested a change (/prefer)

    Stickiness bonus: +0.15 to bound model's election score.
    Transition injection: when switching, prepend a bridge context.

    Usage:
        sb = get_session_binding()
        sb.bind("deepseek", "temperature=0.3, max_tokens=4096")
        should_switch, reason = sb.should_switch("nvidia-reasoning", "429 rate limited")
        ctx = sb.transition_context("deepseek", "nvidia-reasoning")
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

BINDING_FILE = Path(".livingtree/session_bindings.json")


@dataclass
class SessionState:
    session_id: str
    bound_model: str = ""
    bound_since: float = 0.0
    turn_count: int = 0
    consecutive_turns: int = 0        # turns with same model
    switch_count: int = 0             # total switches in this session
    switch_history: list[dict] = field(default_factory=list)
    last_task_type: str = ""          # chat, reasoning, code, document
    user_preference: str = ""         # user-locked model via /prefer
    cache_hit_rate: float = 0.0


class SessionBinding:
    """Per-session model sticky election."""

    # Only switch if cost saving exceeds this threshold
    COST_SAVING_THRESHOLD = 0.50
    # Stickiness bonus added to election score for bound model
    STICKINESS_BONUS = 0.15

    def __init__(self):
        BINDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, SessionState] = {}
        self._load()

    def get_session(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(
                session_id=session_id, bound_since=time.time()
            )
        return self._sessions[session_id]

    def bind(self, session_id: str, model: str, task_type: str = ""):
        """Bind a model to a session. Records the election result."""
        session = self.get_session(session_id)

        if session.bound_model and session.bound_model != model:
            # Model switch occurred
            session.switch_count += 1
            session.switch_history.append({
                "from": session.bound_model,
                "to": model,
                "at_turn": session.turn_count,
                "timestamp": time.time(),
            })
            session.consecutive_turns = 1
        else:
            session.consecutive_turns += 1

        session.bound_model = model
        session.turn_count += 1
        if task_type:
            session.last_task_type = task_type
        self._maybe_save()

    def should_switch(
        self,
        session_id: str,
        candidate: str,
        reason: str = "",
    ) -> tuple[bool, str]:
        """Determine if switching from bound model to candidate is justified.

        Returns (should_switch, explanation).
        """
        session = self.get_session(session_id)

        # User locked a model — never switch
        if session.user_preference:
            return False, f"User locked {session.user_preference}"

        # First turn — no binding yet
        if not session.bound_model:
            return True, "First turn"

        # Same model — no switch needed
        if candidate == session.bound_model:
            return False, "Already bound"

        # Only these conditions justify a switch:
        if "rate_limit" in reason.lower() or "429" in reason:
            return True, f"Rate limited ({session.bound_model})"
        if "dead" in reason.lower() or "failed" in reason.lower():
            return True, f"Model failed ({session.bound_model})"
        if "cost_saving" in reason.lower():
            return True, "Significant cost saving"
        if "task_shift" in reason.lower():
            return True, "Task type changed"
        if "user" in reason.lower():
            return True, "User requested"

        # Not a strong enough reason — stay sticky
        return False, f"Sticky to {session.bound_model}"

    def stickiness_score(self, session_id: str, candidate: str) -> float:
        """Return stickiness bonus for election scoring.

        0.0 = no bonus (different model)
        STICKINESS_BONUS = bound model gets bonus
        """
        session = self.get_session(session_id)
        if session.bound_model == candidate:
            return self.STICKINESS_BONUS
        return 0.0

    def transition_context(self, session_id: str, from_model: str, to_model: str) -> str:
        """Generate a bridge context for model handoff.

        This tiny prompt (30 tokens) tells the new model what the old one
        was doing, preventing context breakage.
        """
        session = self.get_session(session_id)
        task_hint = f" (task: {session.last_task_type})" if session.last_task_type else ""
        return (
            f"[SYSTEM: Conversation started with {from_model}{task_hint}. "
            f"Turns {session.turn_count}. Continue naturally from the last exchange.]"
        )

    def set_preference(self, session_id: str, model: str = ""):
        """User-lock a model for this session. /prefer command."""
        session = self.get_session(session_id)
        session.user_preference = model
        if model:
            logger.info(f"Session {session_id[:8]}: user locked {model}")
        else:
            logger.info(f"Session {session_id[:8]}: user unlocked")

    def stats(self, session_id: str) -> dict:
        session = self.get_session(session_id)
        return {
            "bound_model": session.bound_model,
            "turns": session.turn_count,
            "consecutive": session.consecutive_turns,
            "switches": session.switch_count,
            "preference": session.user_preference or "auto",
            "switch_history": session.switch_history[-5:],
        }

    def _save(self):
        data = {}
        for sid, s in self._sessions.items():
            data[sid] = {
                "session_id": s.session_id,
                "bound_model": s.bound_model,
                "bound_since": s.bound_since,
                "turn_count": s.turn_count,
                "switch_count": s.switch_count,
                "user_preference": s.user_preference,
            }
        BINDING_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        if not BINDING_FILE.exists():
            return
        try:
            data = json.loads(BINDING_FILE.read_text(encoding="utf-8"))
            for sid, d in data.items():
                self._sessions[sid] = SessionState(
                    session_id=d.get("session_id", ""),
                    bound_model=d.get("bound_model", ""),
                    bound_since=d.get("bound_since", 0),
                    turn_count=d.get("turn_count", 0),
                    switch_count=d.get("switch_count", 0),
                    user_preference=d.get("user_preference", ""),
                )
        except Exception:
            pass

    def _maybe_save(self):
        if sum(s.turn_count for s in self._sessions.values()) % 10 == 0:
            self._save()


_sb: SessionBinding | None = None


def get_session_binding() -> SessionBinding:
    global _sb
    if _sb is None:
        _sb = SessionBinding()
    return _sb
