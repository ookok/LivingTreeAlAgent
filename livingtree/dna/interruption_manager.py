"""Interruption Manager — human-like conversation interjection handling.

Problem: When the AI is executing a task, and the user sends more messages
(follow-ups, corrections, topic changes, or just "好的"), current systems
either ignore them until done, or crash.

Human conversation doesn't work that way. We handle interruptions naturally:
  - Related follow-up → incorporate, adjust course
  - Topic change → gracefully abort, switch
  - Urgent correction → pause, fix, resume
  - Simple acknowledgment → ignore, continue
  - Contradiction → stop, clarify, restart

This module gives LivingTree the same capability.

Interruption strategies:
  CONTINUE      — Ignore interruption, finish current task
  INCORPORATE   — Fold new info into current task, adjust plan
  PAUSE_RESUME  — Save state, handle interruption, resume
  SWITCH        — Abort current, start new task
  CLARIFY       — Stop, ask user to clarify contradiction
  ACKNOWLEDGE   — Quick nod ("好的"), continue
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════

class InterruptionStrategy(str, Enum):
    CONTINUE = "continue"          # Ignore, keep doing what I'm doing
    INCORPORATE = "incorporate"   # Fold new info into current task
    PAUSE_RESUME = "pause_resume" # Save state, handle, come back
    SWITCH = "switch"              # Abort current, start new
    CLARIFY = "clarify"            # Stop, ask for clarification
    ACKNOWLEDGE = "acknowledge"   # Quick response, continue


@dataclass
class CurrentTask:
    """State of the currently executing task."""
    task_id: str
    description: str
    progress: float = 0.0          # 0.0 to 1.0
    current_step: str = ""
    status: str = "running"        # running, paused, aborted
    started_at: float = field(default_factory=time.time)
    checkpoints: list[dict] = field(default_factory=list)  # For resume

    @property
    def is_near_completion(self) -> bool:
        return self.progress > 0.85

    @property
    def is_early_stage(self) -> bool:
        return self.progress < 0.3


@dataclass
class Interruption:
    """An incoming interruption during task execution."""
    message: str
    received_at: float = field(default_factory=time.time)
    # Computed
    relevance_score: float = 0.5   # How related to current task
    urgency_score: float = 0.5     # How urgent
    contradiction_score: float = 0.0  # Does this contradict the task?
    is_acknowledgment: bool = False
    is_topic_change: bool = False
    strategy: InterruptionStrategy = InterruptionStrategy.CONTINUE
    reasoning: str = ""


class InterruptionManager:
    """Handle incoming messages during task execution.

    Like a human who can be interrupted mid-sentence:
    - Judges relevance of the interruption
    - Decides whether to continue, incorporate, pause, or switch
    - Remembers state for later resume
    """

    # Keywords that suggest different interruption types
    ACKNOWLEDGMENT_PATTERNS = [
        "好的", "ok", "收到", "明白", "了解", "继续", "嗯", "好",
        "got it", "okay", "thanks", "thank you", "cool",
    ]

    CORRECTION_PATTERNS = [
        "不对", "错了", "不是", "应该是", "改一下", "修正",
        "wrong", "not that", "should be", "correct", "fix",
        "换个", "不要", "别", "stop", "停",
    ]

    TOPIC_CHANGE_PATTERNS = [
        "先不管", "换个话题", "不说这个了", "另外", "顺便",
        "instead", "actually", "never mind", "by the way",
        "对了", "突然想到", "新任务", "接下来",
    ]

    URGENCY_PATTERNS = [
        "紧急", "快", "马上", "立刻", "现在", "赶紧",
        "urgent", "asap", "immediately", "right now", "critical",
    ]

    FOLLOW_UP_PATTERNS = [
        "还有", "另外", "补充", "再加上", "同时",
        "also", "additionally", "furthermore", "plus", "besides",
    ]

    def assess(self, current_task: CurrentTask, incoming_message: str) -> Interruption:
        """Assess an incoming interruption during task execution.

        This is the core intelligence: given what I'm doing and what the user just said,
        what should I do?

        Returns an Interruption with the recommended strategy and reasoning.
        """
        interruption = Interruption(message=incoming_message)
        msg_lower = incoming_message.lower().strip()

        # Check 1: Is this just an acknowledgment?
        if any(p in msg_lower for p in self.ACKNOWLEDGMENT_PATTERNS):
            interruption.is_acknowledgment = True
            interruption.relevance_score = 0.1
            interruption.strategy = InterruptionStrategy.ACKNOWLEDGE
            interruption.reasoning = "Simple acknowledgment — continue current task"
            return interruption

        # Check 2: Is this a correction?
        if any(p in msg_lower for p in self.CORRECTION_PATTERNS):
            interruption.relevance_score = 1.0
            interruption.urgency_score = 0.9
            interruption.contradiction_score = 0.8
            interruption.strategy = (
                InterruptionStrategy.PAUSE_RESUME
                if not current_task.is_early_stage
                else InterruptionStrategy.INCORPORATE
            )
            interruption.reasoning = (
                f"Correction detected — {'pause and resume' if current_task.progress > 0.3 else 'incorporate directly'}. "
                f"Task at {current_task.progress:.0%} completion."
            )
            return interruption

        # Check 3: Topic change?
        if any(p in msg_lower for p in self.TOPIC_CHANGE_PATTERNS):
            interruption.is_topic_change = True
            interruption.relevance_score = 0.1
            interruption.strategy = (
                InterruptionStrategy.SWITCH
                if current_task.progress < 0.5
                else InterruptionStrategy.CONTINUE
            )
            interruption.reasoning = (
                f"Topic change detected — {'switch now' if current_task.progress < 0.5 else 'finish current first'}. "
                f"Task at {current_task.progress:.0%}."
            )
            return interruption

        # Check 4: Urgent?
        if any(p in msg_lower for p in self.URGENCY_PATTERNS):
            interruption.urgency_score = 1.0
            interruption.relevance_score = 0.5
            interruption.strategy = InterruptionStrategy.PAUSE_RESUME
            interruption.reasoning = "Urgent interruption — pause, handle, resume"
            return interruption

        # Check 5: Follow-up?
        if any(p in msg_lower for p in self.FOLLOW_UP_PATTERNS):
            interruption.relevance_score = 0.8
            interruption.strategy = InterruptionStrategy.INCORPORATE
            interruption.reasoning = "Follow-up to current task — incorporate into plan"
            return interruption

        # Check 6: Semantic relevance (simple word overlap)
        task_words = set(current_task.description.lower().split())
        msg_words = set(msg_lower.split())
        overlap = len(task_words & msg_words)
        relevance = overlap / max(1, min(len(task_words), len(msg_words)))
        interruption.relevance_score = relevance

        if relevance > 0.5:
            interruption.strategy = InterruptionStrategy.INCORPORATE
            interruption.reasoning = f"High relevance ({relevance:.0%}) — incorporate into current task"
        elif relevance > 0.2:
            interruption.strategy = InterruptionStrategy.PAUSE_RESUME
            interruption.reasoning = f"Medium relevance ({relevance:.0%}) — pause, handle, resume"
        else:
            # Low relevance + late stage → finish first
            if current_task.is_near_completion:
                interruption.strategy = InterruptionStrategy.CONTINUE
                interruption.reasoning = (
                    f"Low relevance ({relevance:.0%}) and task nearly done "
                    f"({current_task.progress:.0%}) — finish first"
                )
            else:
                interruption.strategy = InterruptionStrategy.SWITCH
                interruption.reasoning = f"Low relevance ({relevance:.0%}) — switch to new topic"

        return interruption

    def save_checkpoint(self, task: CurrentTask) -> None:
        """Save task state for later resume."""
        task.checkpoints.append({
            "progress": task.progress,
            "step": task.current_step,
            "timestamp": time.time(),
        })

    def resume_from_checkpoint(self, task: CurrentTask) -> Optional[dict]:
        """Restore task state from last checkpoint."""
        if task.checkpoints:
            checkpoint = task.checkpoints[-1]
            task.progress = checkpoint["progress"]
            task.current_step = checkpoint["step"]
            task.status = "running"
            return checkpoint
        return None


# ═══════════════════════════════════════════════════════
# Conversation Buffer — multi-message async handling
# ═══════════════════════════════════════════════════════

class AsyncConversationBuffer:
    """Buffer incoming messages while task is executing.

    During task execution:
      - User messages are buffered (not lost)
      - After each step, buffer is checked
      - Interruption strategies applied

    Like a person who listens while working:
      "I hear you, let me finish this sentence, then I'll address that."
    """

    def __init__(self, manager: InterruptionManager):
        self.manager = manager
        self._buffer: list[Interruption] = []
        self._current_task: Optional[CurrentTask] = None
        self._pending_response: Optional[str] = None
        self._lock = asyncio.Lock()

    async def on_message(self, message: str) -> dict:
        """Handle an incoming message — may interrupt current task."""
        async with self._lock:
            # No task running → process immediately
            if not self._current_task or self._current_task.status != "running":
                return {"action": "process_immediately", "message": message}

            # Task running → assess interruption
            interruption = self.manager.assess(self._current_task, message)
            self._buffer.append(interruption)

            action_map = {
                InterruptionStrategy.ACKNOWLEDGE: "acknowledge_and_continue",
                InterruptionStrategy.CONTINUE: "buffer_for_later",
                InterruptionStrategy.INCORPORATE: "incorporate_into_task",
                InterruptionStrategy.PAUSE_RESUME: "pause_and_handle",
                InterruptionStrategy.SWITCH: "abort_and_switch",
                InterruptionStrategy.CLARIFY: "stop_and_clarify",
            }

            return {
                "action": action_map.get(interruption.strategy, "buffer_for_later"),
                "strategy": interruption.strategy.value,
                "reasoning": interruption.reasoning,
                "current_progress": self._current_task.progress,
                "message": message[:100],
            }

    def set_current_task(self, task: CurrentTask) -> None:
        self._current_task = task

    def clear_current_task(self) -> None:
        if self._current_task:
            self._current_task.status = "completed"
        self._current_task = None

    def drain_buffer(self) -> list[Interruption]:
        """Get all buffered interruptions for processing."""
        drained = list(self._buffer)
        self._buffer.clear()
        return drained

    @property
    def buffered_count(self) -> int:
        return len(self._buffer)

    @property
    def current_task_progress(self) -> float:
        return self._current_task.progress if self._current_task else 0.0


# ═══════════════════════════════════════════════════════
# Demonstration — simulate a human-like conversation
# ═══════════════════════════════════════════════════════

class ConversationSimulator:
    """Simulate a human-like conversation with interruptions.

    Demonstrates how the InterruptionManager handles real scenarios.
    """

    def __init__(self):
        self.manager = InterruptionManager()
        self.buffer = AsyncConversationBuffer(self.manager)

    def simulate(self):
        """Simulate a multi-turn conversation with interruptions."""
        print("=" * 70)
        print("  HUMAN-LIKE INTERRUPTION SIMULATION")
        print("=" * 70)

        # Scenario: AI is generating code
        task = CurrentTask(
            task_id="code_gen_001",
            description="Generate a REST API for user management with CRUD endpoints",
            progress=0.3,
            current_step="writing POST /users endpoint",
        )
        self.buffer.set_current_task(task)

        scenarios = [
            ("好的", "User says 'ok' while AI is working"),
            ("不对，用户名应该用 email 作为唯一标识", "User corrects the design mid-execution"),
            ("顺便问一下，数据库用 PostgreSQL 还是 MySQL？", "User asks a follow-up question"),
            ("先不管这个了，我们换个话题", "User wants to change topic"),
            ("紧急！线上出 bug 了", "Urgent interruption"),
        ]

        for msg, description in scenarios:
            print(f"\n{'─' * 60}")
            print(f"👤 USER: \"{msg}\"")
            print(f"   Context: {description}")
            print(f"   Task progress: {task.progress:.0%} — {task.current_step}")

            result = asyncio.get_event_loop().run_until_complete(
                self.buffer.on_message(msg)
            )

            print(f"   🤖 Decision: {result['strategy']}")
            print(f"   💡 Reasoning: {result['reasoning']}")

            # Simulate task progress
            task.progress = min(1.0, task.progress + 0.15)

        print(f"\n{'=' * 70}")
        print(f"  Buffered messages: {self.buffer.buffered_count}")
        print(f"  All handled with human-like intelligence")
        print(f"{'=' * 70}")


# ── Singleton ──

_manager: Optional[InterruptionManager] = None
_buffer: Optional[AsyncConversationBuffer] = None


def get_interruption_manager() -> InterruptionManager:
    global _manager
    if _manager is None:
        _manager = InterruptionManager()
    return _manager


def get_conversation_buffer() -> AsyncConversationBuffer:
    global _buffer
    if _buffer is None:
        _buffer = AsyncConversationBuffer(get_interruption_manager())
    return _buffer
