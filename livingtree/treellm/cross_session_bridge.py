"""CrossSessionBridge — Persistent cross-session memory injection.

When a session ends, durable memories (preferences, pending tasks, key decisions)
are extracted and stored. Next session, relevant memories are injected into the
initial context so the system "remembers" across sessions.

v2.5 Opus 4.7: Added relevance-weighted injection — memories scored against current
query by semantic overlap. High-relevance memories get more context budget (higher
kv_weight), low-relevance memories are suppressed. Replaces uniform prefix injection.

Memories decay with time: older memories fade out after 7 days.

Integration:
    bridge = get_cross_session_bridge()
    await bridge.extract_memories(session_id, messages)  # on session end
    context = bridge.inject_weighted_context(user_id, query)       # Opus 4.7 weighted
    context = bridge.inject_context(user_id, query)               # legacy uniform
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from loguru import logger

MEMORY_FILE = Path(".livingtree/cross_session_memories.json")
MAX_MEMORIES_PER_USER = 30
MEMORY_TTL_DAYS = 7


class CrossSessionBridge:
    """Extracts and injects durable cross-session memories."""

    _instance: Optional["CrossSessionBridge"] = None

    @classmethod
    def instance(cls) -> "CrossSessionBridge":
        if cls._instance is None:
            cls._instance = CrossSessionBridge()
        return cls._instance

    def __init__(self):
        self._memories: dict[str, list[dict]] = defaultdict(list)  # user_id → [{type, text, ts}]
        self._load()

    async def extract_memories(self, user_id: str, messages: list[dict]) -> int:
        """Extract durable memories from completed session messages."""
        extracted = 0
        for m in messages[-15:]:
            content = str(m.get("content", ""))
            if len(content) < 50:
                continue

            if m.get("role") == "assistant":
                if self._has_decision_keywords(content):
                    self._add_memory(user_id, "decision",
                                     self._extract_snippet(content, 200))
                    extracted += 1
                if self._has_preference_keywords(content):
                    self._add_memory(user_id, "preference",
                                     self._extract_snippet(content, 150))
                    extracted += 1
                if self._has_pending_keywords(content):
                    self._add_memory(user_id, "pending",
                                     self._extract_snippet(content, 200))
                    extracted += 1

            if m.get("role") == "user":
                if "偏好" in content or "喜欢" in content or "prefer" in content.lower():
                    self._add_memory(user_id, "user_preference",
                                     content[:150])
                    extracted += 1

        if extracted:
            self._save()
            logger.info(f"CrossSessionBridge: extracted {extracted} memories for {user_id}")
        return extracted

    def inject_context(self, user_id: str, current_query: str) -> str:
        """Inject relevant past memories into the current query context (legacy)."""
        return self.inject_weighted_context(user_id, current_query)

    def inject_weighted_context(self, user_id: str, current_query: str,
                                max_budget_chars: int = 400) -> str:
        """Opus 4.7: Relevance-weighted memory injection.

        Scores each memory against the current query for semantic relevance.
        High-relevance memories (>0.5) get full text; medium (0.25-0.5) get
        half budget; low (<0.25) are suppressed.
        Returns formatted context string with memories + current query.
        """
        past = self._get_recent(user_id, limit=8)
        if not past:
            return current_query

        scored = []
        q_words = set(current_query.lower().split())
        for days_ago, mtype, text, ts in past:
            m_words = set(text.lower().split())
            overlap = len(q_words & m_words) / max(len(q_words | m_words), 1)
            recency_decay = max(0.0, 1.0 - days_ago / MEMORY_TTL_DAYS)
            kv_weight = overlap * 0.6 + recency_decay * 0.4
            scored.append((kv_weight, days_ago, mtype, text, ts))

        scored.sort(key=lambda x: -x[0])

        lines = []
        budget_used = 0
        for kv_weight, days_ago, mtype, text, ts in scored:
            if kv_weight < 0.15 or budget_used >= max_budget_chars:
                break
            icon = {"decision": "决定", "preference": "偏好", "pending": "待处理",
                    "user_preference": "用户偏好"}.get(mtype, "记忆")
            if kv_weight > 0.5:
                snippet = text[:120]
            elif kv_weight > 0.25:
                snippet = text[:60]
            else:
                snippet = text[:30]
            lines.append(f"- [{days_ago}天前] [{icon}] w={kv_weight:.2f} {snippet}")
            budget_used += len(snippet)

        if lines:
            context = "之前的对话记忆:\n" + "\n".join(lines)
            return f"{context}\n\n当前问题: {current_query}"

        return current_query

    def _add_memory(self, user_id: str, mtype: str, text: str):
        self._memories[user_id].append({
            "type": mtype, "text": text, "ts": time.time(),
        })
        while len(self._memories[user_id]) > MAX_MEMORIES_PER_USER:
            self._memories[user_id].pop(0)

    def _get_recent(self, user_id: str, limit: int = 5) -> list[tuple]:
        """Get recent valid memories sorted by recency."""
        now = time.time()
        valid = []
        for m in self._memories.get(user_id, []):
            days = (now - m["ts"]) / 86400.0
            if days <= MEMORY_TTL_DAYS:
                valid.append((int(days), m["type"], m["text"], m["ts"]))
        valid.sort(key=lambda x: -x[3])  # most recent first
        return valid[:limit]

    @staticmethod
    def _has_decision_keywords(text: str) -> bool:
        kw = ["决定", "选择", "最终", "采用", "decided", "chose", "selected", "conclusion"]
        return any(k in text.lower() for k in kw)

    @staticmethod
    def _has_preference_keywords(text: str) -> bool:
        kw = ["你倾向于", "你喜欢", "偏好", "推荐你", "根据你的", "you prefer", "your preference"]
        return any(k in text.lower() for k in kw)

    @staticmethod
    def _has_pending_keywords(text: str) -> bool:
        kw = ["未完成", "待处理", "下一步", "还需要", "pending", "todo", "remaining", "接下来"]
        return any(k in text.lower() for k in kw)

    @staticmethod
    def _extract_snippet(text: str, max_len: int) -> str:
        return text[:max_len].strip()

    def stats(self) -> dict:
        return {
            "users": len(self._memories),
            "total_memories": sum(len(v) for v in self._memories.values()),
        }

    def _save(self):
        try:
            MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v[-MAX_MEMORIES_PER_USER:] for k, v in self._memories.items()}
            MEMORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"CrossSessionBridge save: {e}")

    def _load(self):
        try:
            if MEMORY_FILE.exists():
                data = json.loads(MEMORY_FILE.read_text())
                self._memories = defaultdict(list, data)
        except Exception:
            pass


_bridge: Optional[CrossSessionBridge] = None


def get_cross_session_bridge() -> CrossSessionBridge:
    global _bridge
    if _bridge is None:
        _bridge = CrossSessionBridge()
    return _bridge


__all__ = ["CrossSessionBridge", "get_cross_session_bridge"]
