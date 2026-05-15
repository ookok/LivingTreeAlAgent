"""ConversationStateMachine — High-level conversation flow state tracking.

Tracks 6 conversation stages and auto-detects context switches. Each stage
triggers different routing strategies.

v2.5 Opus 4.7: Information Priority Map.
v2.6 PersonaVLM (CVPR 2026): Retrieval urgency computation + force-retrieve
  entry point for R3 Reasoning phase. When urgency crosses threshold, triggers
  proactive memory retrieval across all memory layers.
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
        self._sessions: dict[str, dict] = {}
        self.MAX_SESSIONS = 500
        self._priority_cache: dict[str, dict[str, float]] = {}

    def transition(self, sid: str, message: str, intent: str = "general",
                   domain: str = "general") -> str:
        now = time.time()
        session = self._sessions.setdefault(sid, {
            "state": "explore", "history": [], "topics": set(), "ts": now,
            "transitions": 0,
        })

        msg_lower = message.lower()
        current = session["state"]

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
            new_state = current

        keywords = set(msg_lower.split()[:10])
        if session["topics"] and not (keywords & session["topics"]):
            session["context_switches"] = session.get("context_switches", 0) + 1
        session["topics"] |= keywords

        if new_state != current:
            session["transitions"] += 1
            logger.debug(f"CSM: {sid} {current}->{new_state}")

        session["state"] = new_state
        session["history"].append({"state": new_state, "ts": now, "intent": intent})
        if len(session["history"]) > 20:
            session["history"] = session["history"][-20:]
        session["ts"] = now

        self._evict_old()
        return new_state

    def routing_hint(self, state: str) -> dict[str, Any]:
        return dict(STAGE_ROUTING.get(state, STAGE_ROUTING["explore"]))

    def should_reset(self, sid: str) -> bool:
        session = self._sessions.get(sid, {})
        switches = session.get("context_switches", 0)
        return switches >= 3

    # ── Opus 4.7: Information Priority Map ──

    def get_priority_map(self, sid: str) -> dict[str, float]:
        session = self._sessions.get(sid, {})
        history_entries = session.get("history", [])
        topics = session.get("topics", set())

        if not topics:
            return {}

        priorities = {}
        topic_list = list(topics)
        for i, topic in enumerate(topic_list):
            cited = sum(1 for h in history_entries
                        if topic.lower() in str(h.get("intent", "")).lower())
            recency = (i + 1) / max(len(topic_list), 1)
            priorities[topic] = min(1.0, (cited * 0.15 + recency * 0.10 + 0.60))

        self._priority_cache[sid] = priorities
        return priorities

    def preserve_on_reset(self, sid: str, threshold: float = 0.6) -> dict[str, float]:
        priorities = self._priority_cache.get(sid) or self.get_priority_map(sid)
        return {k: v for k, v in priorities.items() if v >= threshold}

    def track_entity_mention(self, sid: str, entity: str) -> None:
        session = self._sessions.get(sid, {})
        mentions = session.setdefault("entity_mentions", {})
        mentions[entity] = mentions.get(entity, 0) + 1

    # ── PersonaVLM v2.6: Retrieval Urgency + Force Retrieve ──

    def compute_retrieval_urgency(self, sid: str) -> float:
        """PersonaVLM R3: compute how urgently we need persona memory retrieval.

        Combines: context switches + query complexity + topic novelty +
        session depth. When > 0.65, triggers force_retrieve_all().
        """
        session = self._sessions.get(sid, {})
        if not session:
            return 0.0

        switches = session.get("context_switches", 0)
        transitions = session.get("transitions", 0)
        topics = session.get("topics", set())
        history = session.get("history", [])

        switch_score = min(1.0, switches * 0.25)
        transition_score = min(1.0, transitions * 0.15)
        topic_novelty = min(1.0, len(topics) * 0.08) if topics else 0.3
        depth_score = min(1.0, len(history) * 0.04) if history else 0.2

        urgency = (switch_score * 0.30 + transition_score * 0.20
                   + topic_novelty * 0.25 + depth_score * 0.25)
        return round(min(1.0, urgency), 4)

    def force_retrieve_all(self, sid: str, query: str = "",
                           user_id: str = "default") -> dict[str, Any]:
        """PersonaVLM R3: force-retrieve all memory layers for the current context.

        Bypasses all gates (SurpriseGate, retention thresholds) and retrieves:
          - PersonaMemory: 8-domain structured facts
          - StructMemory: user-specific episodes
          - EmotionalMemory: user emotional timeline
        """
        results = {"persona_facts": [], "episodes": [], "emotions": {},
                   "user_traits": {}, "urgency": 0.0}

        urgency = self.compute_retrieval_urgency(sid)
        results["urgency"] = urgency

        try:
            from ..memory.persona_memory import get_persona_memory
            pm = get_persona_memory()
            facts = pm.retrieve(query, user_id) if query else []
            results["persona_facts"] = [
                {"domain": f.domain.value, "fact": f.fact,
                 "confidence": f.confidence} for f in facts[:10]
            ]
        except Exception:
            pass

        try:
            from ..memory.user_model import get_user_model
            um = get_user_model()
            results["user_traits"] = um.get_user_traits()
            results["communication_style"] = um.get_adaptive_communication_style()
        except Exception:
            pass

        try:
            from ..knowledge.struct_mem import get_struct_memory
            sm = get_struct_memory()
            entries = sm.retrieve_for_query(query, user_only=True) if query else []
            results["episodes"] = [
                {"event": e.content[:150], "timestamp": str(e.timestamp)}
                for e in entries[:5]
            ] if entries and hasattr(entries[0], 'content') else []
        except Exception:
            pass

        try:
            from ..memory.emotional_memory import get_emotional_memory
            em = get_emotional_memory()
            results["emotions"] = em.get_user_emotional_timeline() if hasattr(em, "get_user_emotional_timeline") else {}
        except Exception:
            pass

        return results

    def memory_retrieval_plan(self, sid: str) -> dict[str, Any]:
        """PersonaVLM R3: generate retrieval plan based on urgency.

        Returns which memory types to retrieve, in what priority, with budget.
        """
        urgency = self.compute_retrieval_urgency(sid)
        plan = {"urgency": urgency, "types": [], "budget_tokens": 500}

        if urgency > 0.7:
            plan["types"] = ["core_identity", "preferences", "procedural",
                             "episodic", "semantic"]
            plan["budget_tokens"] = 1500
        elif urgency > 0.5:
            plan["types"] = ["core_identity", "preferences", "procedural"]
            plan["budget_tokens"] = 800
        elif urgency > 0.3:
            plan["types"] = ["core_identity", "preferences"]
            plan["budget_tokens"] = 400

        return plan

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
