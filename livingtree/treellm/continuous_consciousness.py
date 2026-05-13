"""ContinuousConsciousness — Perpetual single-session consciousness engine.

Replaces discrete sessions with a single continuous conversation state.
The digital life form never "restarts" — it maintains one perpetual awareness
that auto-detects task boundaries, archives completed work, and retrieves
relevant past context on demand.

Core capabilities:
  1. TaskBoundaryDetector — detects when a task naturally ends
  2. ContextRelevanceScorer — scores past memory relevance to current query
  3. MemoryCompactor — compresses completed tasks into long-term memory
  4. ContextInjector — injects relevant past context into current prompt

Integration with existing modules:
  - SessionCompressor: compresses long active contexts
  - CrossSessionBridge: extracts durable memories
  - ConversationStateMachine: tracks conversation flow stages
  - StructMemory: long-term memory storage/retrieval
  - UserSignal: implicit feedback for relevance scoring

Usage:
    cc = get_continuous_consciousness()
    context = await cc.on_message(message)        # returns enriched context
    await cc.on_response(response_text, success)   # updates state after reply
    cc.state_report()                              # {task_count, memory_blocks, ...}
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

STATE_FILE = Path(".livingtree/continuous_consciousness.json")


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class TaskBoundary:
    """A detected task boundary (natural end of a sub-task)."""
    timestamp: float
    reason: str           # "closing_phrase" | "silence" | "topic_shift" | "explicit"
    confidence: float      # 0.0-1.0
    context_snapshot: str  # compressed context of the completed task
    key_points: list[str]  # extracted key decisions/facts


@dataclass
class MemoryBlock:
    """A compressed memory block stored in long-term memory."""
    id: str
    content: str            # compressed summary
    original_length: int    # chars before compression
    timestamp: float
    last_accessed: float
    access_count: int = 0
    relevance_score: float = 0.5
    topics: list[str] = field(default_factory=list)
    task_type: str = "general"


@dataclass
class RelevanceScore:
    """Scored relevance of a memory block to current context."""
    block_id: str
    score: float            # 0.0-1.0 combined
    keyword_score: float
    temporal_score: float
    task_type_match: float


# ═══ TaskBoundaryDetector ══════════════════════════════════════════


class TaskBoundaryDetector:
    """Detects natural task boundaries from conversation signals."""

    CLOSING_PHRASES = [
        "好的谢谢", "谢谢", "感谢", "拜拜", "再见", "下次见",
        "没问题了", "可以了", "就这样", "清楚了", "明白了",
        "thanks", "thank you", "bye", "goodbye", "see you",
        "that's all", "got it", "understood", "clear",
        "完美", "搞定", "done", "finished",
        "先这样", "到此为止", "结束", "收工",
    ]

    SILENCE_THRESHOLD_SECONDS = 300  # 5 minutes
    SHORT_SILENCE_SECONDS = 120      # 2 minutes → low confidence
    TOPIC_SHIFT_JACCARD = 0.15       # <15% word overlap → topic shift

    def detect(
        self, message: str, time_since_last: float,
        recent_topics: set[str],
    ) -> Optional[TaskBoundary]:
        """Detect if a task boundary has occurred. Returns None if still active."""
        now = time.time()

        # Signal 1: Closing phrase (highest confidence)
        msg_lower = message.lower().strip()
        for phrase in self.CLOSING_PHRASES:
            if phrase in msg_lower:
                return TaskBoundary(
                    timestamp=now,
                    reason=f"closing_phrase:{phrase}",
                    confidence=0.9,
                    context_snapshot="",
                    key_points=[],
                )

        # Signal 2: Extended silence (medium confidence)
        if time_since_last > self.SILENCE_THRESHOLD_SECONDS:
            return TaskBoundary(
                timestamp=now,
                reason=f"silence:{int(time_since_last)}s",
                confidence=0.8 if time_since_last > self.SILENCE_THRESHOLD_SECONDS * 2 else 0.5,
                context_snapshot="",
                key_points=[],
            )

        # Signal 3: Topic shift (lower confidence, needs corroboration)
        if recent_topics and message:
            current_words = set(message.lower().split())
            if current_words and recent_topics:
                overlap = len(current_words & recent_topics) / max(
                    len(current_words | recent_topics), 1
                )
                if overlap < self.TOPIC_SHIFT_JACCARD:
                    return TaskBoundary(
                        timestamp=now,
                        reason=f"topic_shift:{overlap:.2f}",
                        confidence=0.4,
                        context_snapshot="",
                        key_points=[],
                    )

        return None


# ═══ ContextRelevanceScorer ═══════════════════════════════════════


class ContextRelevanceScorer:
    """Scores past memory blocks for relevance to current query."""

    KEYWORD_WEIGHT = 0.4
    TEMPORAL_WEIGHT = 0.3
    TASK_TYPE_WEIGHT = 0.3
    TEMPORAL_HALFLIFE_HOURS = 24.0

    def score(
        self, query: str, block: MemoryBlock, task_type: str = "general",
    ) -> RelevanceScore:
        """Compute combined relevance score (0.0-1.0)."""
        # Keyword overlap
        query_words = set(query.lower().split())
        block_words = set(block.content.lower().split())
        if not query_words or not block_words:
            keyword_score = 0.0
        else:
            intersection = query_words & block_words
            keyword_score = len(intersection) / max(len(query_words), 1)

        # Temporal decay
        hours_ago = (time.time() - block.last_accessed) / 3600.0
        temporal_score = math.exp(-hours_ago / self.TEMPORAL_HALFLIFE_HOURS)

        # Task type match
        task_type_match = 1.0 if block.task_type == task_type else (
            0.5 if block.task_type == "general" else 0.2
        )

        combined = (
            keyword_score * self.KEYWORD_WEIGHT
            + temporal_score * self.TEMPORAL_WEIGHT
            + task_type_match * self.TASK_TYPE_WEIGHT
        )

        return RelevanceScore(
            block_id=block.id,
            score=round(combined, 3),
            keyword_score=round(keyword_score, 3),
            temporal_score=round(temporal_score, 3),
            task_type_match=round(task_type_match, 3),
        )

    def select_top(
        self, query: str, blocks: list[MemoryBlock],
        task_type: str = "general", top_k: int = 3, min_score: float = 0.15,
    ) -> list[MemoryBlock]:
        """Select top-K most relevant blocks above threshold."""
        scored = [self.score(query, b, task_type) for b in blocks]
        scored.sort(key=lambda x: -x.score)
        result = []
        block_map = {b.id: b for b in blocks}
        for s in scored[:top_k]:
            if s.score >= min_score:
                b = block_map[s.block_id]
                b.access_count += 1
                b.last_accessed = time.time()
                b.relevance_score = s.score
                result.append(b)
        return result


# ═══ ContinuousConsciousness ══════════════════════════════════════


class ContinuousConsciousness:
    """Perpetual single-session consciousness engine.

    Maintains one continuous state across all user interactions.
    Never resets — only compacts and retrieves.
    """

    _instance: Optional["ContinuousConsciousness"] = None

    @classmethod
    def instance(cls) -> "ContinuousConsciousness":
        if cls._instance is None:
            cls._instance = ContinuousConsciousness()
        return cls._instance

    def __init__(self):
        self._detector = TaskBoundaryDetector()
        self._scorer = ContextRelevanceScorer()

        # Perpetual state
        self._session_id = "perpetual"
        self._active_context: list[dict] = []          # Current task messages
        self._memory_blocks: dict[str, MemoryBlock] = {}  # Long-term memory
        self._recent_topics: set[str] = set()
        self._last_message_time: float = 0.0
        self._task_count: int = 0
        self._current_task_type: str = "general"

        # Stats
        self._total_messages = 0
        self._boundaries_detected = 0
        self._memories_retrieved = 0

        self._load()

    # ── Main Flow ──────────────────────────────────────────────────

    async def on_message(self, message: str, task_type: str = "general") -> dict:
        """Called BEFORE processing a new user message.

        Returns enriched context dict with:
          - enriched_message: original message + injected relevant memories
          - boundary_detected: True if previous task ended
          - relevant_blocks: memory blocks retrieved
          - active_context_length: current working memory size
        """
        now = time.time()
        time_since_last = now - self._last_message_time if self._last_message_time else 0
        self._last_message_time = now
        self._total_messages += 1

        # 1. Detect if previous task ended
        boundary = self._detector.detect(message, time_since_last, self._recent_topics)
        boundary_detected = False
        if boundary and boundary.confidence > 0.5:
            await self._archive_task(boundary)
            self._boundaries_detected += 1
            boundary_detected = True

        # 2. Update active context
        self._active_context.append({"role": "user", "content": message, "ts": now})
        if len(self._active_context) > 50:
            await self._compact_active_context()

        # 3. Update topic tracking
        self._recent_topics |= set(message.lower().split()[:20])

        # 4. Retrieve relevant past memories
        blocks = list(self._memory_blocks.values())
        relevant = self._scorer.select_top(message, blocks, task_type, top_k=3)
        self._memories_retrieved += len(relevant)

        # 5. Build enriched context
        enriched_message = message
        memory_context = ""
        if relevant:
            memory_lines = ["[相关历史记忆]"]
            for b in relevant:
                age = int((now - b.timestamp) / 3600.0)
                memory_lines.append(
                    f"[{age}h前] [{b.task_type}] {b.content[:300]}"
                )
            memory_context = "\n".join(memory_lines)
            enriched_message = f"{memory_context}\n\n---\n当前问题: {message}"

        return {
            "enriched_message": enriched_message,
            "boundary_detected": boundary_detected,
            "relevant_blocks": [b.id for b in relevant],
            "active_context_length": len(self._active_context),
            "memory_context": memory_context,
        }

    async def on_response(self, response_text: str, success: bool = True) -> None:
        """Called AFTER generating a response. Updates state."""
        now = time.time()
        self._active_context.append({
            "role": "assistant", "content": response_text[:2000], "ts": now,
        })

        # Extract topics from response
        if response_text:
            self._recent_topics |= set(response_text.lower().split()[:15])

        # Periodic save
        if self._total_messages % 10 == 0:
            self._save()

    # ── Internal ───────────────────────────────────────────────────

    async def _archive_task(self, boundary: TaskBoundary) -> None:
        """Compress completed task context into long-term memory."""
        if not self._active_context:
            return

        self._task_count += 1
        task_id = f"task_{self._task_count}_{int(boundary.timestamp)}"

        # Compress active context
        compact_text = await self._summarize_context(self._active_context)

        # Extract key points
        key_points = self._extract_decisions(self._active_context)

        block = MemoryBlock(
            id=task_id,
            content=compact_text,
            original_length=sum(len(str(m.get("content", ""))) for m in self._active_context),
            timestamp=boundary.timestamp,
            last_accessed=boundary.timestamp,
            topics=list(self._recent_topics)[:20],
            task_type=self._current_task_type,
        )
        self._memory_blocks[task_id] = block

        logger.info(
            f"Consciousness: archived task #{self._task_count} "
            f"({block.original_length}→{len(compact_text)} chars, "
            f"reason={boundary.reason})"
        )

        # Reset active context for new task
        self._active_context = self._active_context[-3:]  # Keep last 3 messages for continuity
        self._recent_topics.clear()

        self._save()

    async def _summarize_context(self, messages: list[dict]) -> str:
        """Compress conversation into a concise summary."""
        parts = []
        for m in messages[-20:]:
            role = m.get("role", "?")
            content = str(m.get("content", ""))[:300]
            if role == "user":
                parts.append(f"用户: {content}")
            elif role == "assistant":
                parts.append(f"AI: {content[:200]}")
        full = " | ".join(parts[-10:])

        if len(full) > 2000:
            full = full[:2000] + "..."

        return full

    def _extract_decisions(self, messages: list[dict]) -> list[str]:
        """Extract key decision points from conversation."""
        keywords = ["决定", "选择", "采用", "确认", "最终", "decided", "chose", "confirmed"]
        decisions = []
        for m in messages[-15:]:
            content = str(m.get("content", ""))
            for kw in keywords:
                if kw in content.lower():
                    idx = content.lower().find(kw)
                    snippet = content[max(0, idx - 30):idx + 80].strip()
                    decisions.append(snippet[:120])
                    break
            if len(decisions) >= 3:
                break
        return decisions

    async def _compact_active_context(self) -> None:
        """Compress oldest half of active context when too large."""
        try:
            keep = self._active_context[-25:]  # Keep recent 25
            old = self._active_context[:-25]
            if old:
                summary = await self._summarize_context(old)
                compacted = {
                    "role": "system",
                    "content": f"[早期对话摘要] {summary[:800]}",
                    "ts": time.time(),
                }
                self._active_context = [compacted] + keep
        except Exception:
            self._active_context = self._active_context[-50:]

    # ── Query ─────────────────────────────────────────────────────

    def get_active_context(self) -> list[dict]:
        return list(self._active_context)

    def get_memory_snippet(self, query: str, top_k: int = 3) -> str:
        blocks = list(self._memory_blocks.values())
        relevant = self._scorer.select_top(query, blocks, top_k=top_k)
        if not relevant:
            return ""
        return "\n".join(f"[{b.task_type}] {b.content[:300]}" for b in relevant)

    def state_report(self) -> dict:
        return {
            "session_id": self._session_id,
            "total_messages": self._total_messages,
            "task_count": self._task_count,
            "boundaries_detected": self._boundaries_detected,
            "memory_blocks": len(self._memory_blocks),
            "memories_retrieved": self._memories_retrieved,
            "active_context_size": len(self._active_context),
            "last_message_age_seconds": int(time.time() - self._last_message_time) if self._last_message_time else -1,
        }

    # ── Persistence ────────────────────────────────────────────────

    def _save(self):
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "task_count": self._task_count,
                "total_messages": self._total_messages,
                "boundaries_detected": self._boundaries_detected,
                "memory_blocks": {
                    bid: {
                        "content": b.content,
                        "original_length": b.original_length,
                        "timestamp": b.timestamp,
                        "last_accessed": b.last_accessed,
                        "access_count": b.access_count,
                        "topics": b.topics,
                        "task_type": b.task_type,
                    }
                    for bid, b in self._memory_blocks.items()
                },
                "last_message_time": self._last_message_time,
            }
            STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"Consciousness save: {e}")

    def _load(self):
        try:
            if STATE_FILE.exists():
                data = json.loads(STATE_FILE.read_text())
                self._task_count = data.get("task_count", 0)
                self._total_messages = data.get("total_messages", 0)
                self._boundaries_detected = data.get("boundaries_detected", 0)
                self._last_message_time = data.get("last_message_time", 0)
                for bid, bd in data.get("memory_blocks", {}).items():
                    self._memory_blocks[bid] = MemoryBlock(
                        id=bid,
                        content=bd.get("content", ""),
                        original_length=bd.get("original_length", 0),
                        timestamp=bd.get("timestamp", 0),
                        last_accessed=bd.get("last_accessed", 0),
                        access_count=bd.get("access_count", 0),
                        topics=bd.get("topics", []),
                        task_type=bd.get("task_type", "general"),
                    )
                logger.info(
                    f"Consciousness: loaded {self._task_count} tasks, "
                    f"{len(self._memory_blocks)} blocks, {self._total_messages} messages"
                )
        except Exception as e:
            logger.debug(f"Consciousness load: {e}")


# ═══ Singleton ════════════════════════════════════════════════════


_cc: Optional[ContinuousConsciousness] = None


def get_continuous_consciousness() -> ContinuousConsciousness:
    global _cc
    if _cc is None:
        _cc = ContinuousConsciousness()
    return _cc


__all__ = [
    "ContinuousConsciousness", "TaskBoundaryDetector",
    "ContextRelevanceScorer", "MemoryBlock", "TaskBoundary",
    "get_continuous_consciousness",
]
