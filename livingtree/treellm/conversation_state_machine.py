"""ConversationStateMachine — High-level conversation flow state tracking.

Tracks 6 conversation stages (explore→clarify→design→implement→verify→summarize)
and auto-detects context switches. Each stage triggers different routing strategies:
  - explore: broad search, multiple models
  - implement: single model, focused
  - verify: adversarial review

Integrates with existing MicroTurnAware (micro-turns, ~200ms) and SessionBinding
(session model tracking).

Integration:
    csm = get_conversation_state_machine()
    state = csm.transition(sid, message, intent)
    hint = csm.routing_hint(state)  # → {top_k, deep_probe, aggregate, task_type}
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Optional

from loguru import logger

STAGE_ROUTING = {
    "explore":    {"top_k": 3, "deep_probe": True,  "aggregate": True,  "task_type": "search"},
    "clarify":    {"top_k": 1, "deep_probe": False, "aggregate": False, "task_type": "chat"},
    "design":     {"top_k": 2, "deep_probe": True,  "aggregate": False, "task_type": "reasoning"},
    "implement":  {"top_k": 1, "deep_probe": False, "aggregate": False, "task_type": "code"},
    "verify":     {"top_k": 3, "deep_probe": True,  "aggregate": True,  "task_type": "code"},
    "summarize":  {"top_k": 1, "deep_probe": False, "aggregate": False, "task_type": "general"},
}


class ConversationStateMachine:
    """High-level conversation flow tracking with stage-adaptive routing."""

    _instance: Optional["ConversationStateMachine"] = None

    @classmethod
    def instance(cls) -> "ConversationStateMachine":
        if cls._instance is None:
            cls._instance = ConversationStateMachine()
        return cls._instance

    def __init__(self):
        self._sessions: dict[str, dict] = {}  # sid → {state, history, topics, ts}
        self.MAX_SESSIONS = 500

    def transition(self, sid: str, message: str, intent: str = "general",
                   domain: str = "general") -> str:
        """Return new conversation stage based on message + intent."""
        now = time.time()
        session = self._sessions.setdefault(sid, {
            "state": "explore", "history": [], "topics": set(), "ts": now,
            "transitions": 0,
        })

        msg_lower = message.lower()
        current = session["state"]

        # Decision tree
        if any(k in msg_lower for k in ["总结", "回顾", "summarize", "summary"]):
            new_state = "summarize"
        elif intent == "code" or domain == "code":
            if any(k in msg_lower for k in ["写", "实现", "implement", "代码"]):
                new_state = "implement"
            elif any(k in msg_lower for k in ["错", "bug", "修", "fix", "调试", "debug"]):
                new_state = "verify"
            else:
                new_state = "design"
        elif any(k in msg_lower for k in ["怎么", "如何", "方案", "how", "design"]):
            new_state = "design"
        elif any(k in msg_lower for k in ["搜索", "找", "查", "search", "find"]):
            new_state = "explore"
        elif len(msg_lower) < 15:
            new_state = "clarify"
        else:
            new_state = current  # maintain current state

        # Detect context switch (topic changed)
        keywords = set(msg_lower.split()[:10])
        if session["topics"] and not (keywords & session["topics"]):
            session["context_switches"] = session.get("context_switches", 0) + 1
        session["topics"] |= keywords

        if new_state != current:
            session["transitions"] += 1
            logger.debug(f"CSM: {sid} {current}→{new_state}")

        session["state"] = new_state
        session["history"].append({"state": new_state, "ts": now, "intent": intent})
        if len(session["history"]) > 20:
            session["history"] = session["history"][-20:]
        session["ts"] = now

        self._evict_old()
        return new_state

    def routing_hint(self, state: str) -> dict[str, Any]:
        """Return routing parameters optimized for this conversation stage."""
        return dict(STAGE_ROUTING.get(state, STAGE_ROUTING["explore"]))

    def should_reset(self, sid: str) -> bool:
        """Return True if this session should be treated as a fresh start."""
        session = self._sessions.get(sid, {})
        switches = session.get("context_switches", 0)
        return switches >= 3  # 3+ context switches → reset

    def _evict_old(self):
        if len(self._sessions) <= self.MAX_SESSIONS:
            return
        old = sorted(self._sessions.keys(),
                     key=lambda k: self._sessions[k]["ts"])[:50]
        for k in old:
            del self._sessions[k]

    def stats(self) -> dict:
        return {"active_sessions": len(self._sessions)}


_csm: Optional[ConversationStateMachine] = None


def get_conversation_state_machine() -> ConversationStateMachine:
    global _csm
    if _csm is None:
        _csm = ConversationStateMachine()
    return _csm


__all__ = ["ConversationStateMachine", "get_conversation_state_machine", "STAGE_ROUTING"]
