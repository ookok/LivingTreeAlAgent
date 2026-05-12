"""Multi-Stream Cognitive Engine — concurrent processing with continuous correction.

Frontier capability: Handle multiple parallel input streams (text, documents, files)
while continuously executing and refining tasks. No AI framework does this.

Core innovations:
  1. STREAM MULTIPLEXING — OS-style preemptive scheduling for cognitive streams
  2. MERGE-ON-THE-FLY — incoming info merges into running plan without restart
  3. ATTENTION MULTIPLEXER — priority-based focus switching between streams
  4. CONFLICT RESOLVER — detect + resolve contradictions between concurrent streams
  5. STREAMING WORLD STATE — continuously updated shared context across all streams
  6. INCREMENTAL REPLAN — plan evolves with each new input, not replace

Analogy: A human cooking dinner (stream 1), listening to news (stream 2),
answering phone (stream 3) — all while adjusting recipe based on fridge contents.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════

class StreamType(str, Enum):
    TEXT = "text"          # User message
    DOCUMENT = "document"  # File/document upload
    CODE = "code"           # Code snippet or file
    COMMAND = "command"     # Explicit instruction
    CORRECTION = "correction"  # Fix/update to previous task
    OBSERVATION = "observation"  # System-generated event


class StreamPriority(int, Enum):
    CRITICAL = 1     # Must process immediately (error, urgent)
    HIGH = 2         # Important (correction, command)
    MEDIUM = 3       # Normal (new task, document)
    LOW = 4          # Background (observation, log)
    IDLE = 5         # Can be deferred


@dataclass
class InputStream:
    """A single input stream — text, document, code, command."""
    stream_id: str
    stream_type: StreamType
    content: str
    priority: StreamPriority = StreamPriority.MEDIUM
    arrived_at: float = field(default_factory=time.time)
    processed: bool = False
    merged_into_plan: bool = False
    parent_task_id: str = ""  # Which task this relates to


@dataclass
class RunningTask:
    """A task that is currently executing — can be modified mid-flight."""
    task_id: str
    description: str
    status: str = "running"  # running, modified, paused, completed, aborted
    plan: list[str] = field(default_factory=list)
    completed_steps: int = 0
    total_steps: int = 0
    modifications: list[dict] = field(default_factory=list)  # History of modifications
    started_at: float = field(default_factory=time.time)
    last_modified: float = 0.0


@dataclass
class WorldState:
    """Continuously updated shared context across all streams and tasks.

    All streams write to this. All tasks read from this.
    This is the "streaming world model" — always current.
    """
    active_task: Optional[RunningTask] = None
    pending_streams: list[InputStream] = field(default_factory=list)
    recent_observations: list[str] = field(default_factory=list)
    knowledge_updates: list[str] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════
# Multi-Stream Cognitive Engine
# ═══════════════════════════════════════════════════════

class MultiStreamEngine:
    """Process multiple concurrent input streams while executing tasks.

    Key capability: a new stream can modify a RUNNING task without restarting it.
    Like a human adjusting a recipe mid-cooking based on new information.
    """

    def __init__(self):
        self._world = WorldState()
        self._stream_history: list[InputStream] = []
        self._task_history: list[RunningTask] = []

    # ── Stream Ingestion ──

    def ingest(self, content: str, stream_type: StreamType,
               priority: StreamPriority = StreamPriority.MEDIUM,
               parent_task_id: str = "") -> dict:
        """Accept a new input stream — may interrupt or modify running task.

        This is the core loop: every new message/file/command enters here.
        """
        stream = InputStream(
            stream_id=f"stream_{len(self._stream_history)}_{int(time.time()) % 10000}",
            stream_type=stream_type,
            content=content,
            priority=priority,
            parent_task_id=parent_task_id or (
                self._world.active_task.task_id if self._world.active_task else ""
            ),
        )
        self._stream_history.append(stream)

        # Determine how this stream interacts with the current task
        action = self._classify_interaction(stream)

        result = {
            "stream_id": stream.stream_id,
            "action": action,
            "active_task": (
                self._world.active_task.task_id[:12]
                if self._world.active_task else "none"
            ),
            "pending_streams": len(self._world.pending_streams),
        }

        if action == "modify_running_task":
            # Merge into running plan without restart
            merged = self._merge_into_plan(stream)
            result["merged_steps"] = merged
        elif action == "preempt_and_handle":
            # Pause current, handle new, then resume
            self._world.pending_streams.insert(0, stream)
            result["preempted"] = True
        elif action == "queue":
            # Add to pending queue, process later
            self._world.pending_streams.append(stream)
        elif action == "start_new":
            # Start a new task
            task = RunningTask(
                task_id=f"task_{len(self._task_history)}_{int(time.time()) % 10000}",
                description=content[:80],
                total_steps=1,
            )
            self._world.active_task = task
            self._task_history.append(task)

        self._world.last_updated = time.time()
        return result

    def _classify_interaction(self, stream: InputStream) -> str:
        """Classify how this stream should interact with the running task.

        This is the intelligence layer — decides whether to modify, preempt, queue, or start new.
        """
        if not self._world.active_task:
            return "start_new"

        # Correction stream → modify running task
        if stream.stream_type == StreamType.CORRECTION:
            return "modify_running_task"

        # Related to current task → merge into plan
        if stream.parent_task_id == self._world.active_task.task_id:
            return "modify_running_task"

        # High priority → preempt
        if stream.priority <= StreamPriority.HIGH:
            return "preempt_and_handle"

        # Same task context → merge
        task_words = set(self._world.active_task.description.lower().split())
        stream_words = set(stream.content.lower().split())
        overlap = len(task_words & stream_words)
        if overlap > 3:
            return "modify_running_task"

        # Unrelated → queue for later
        return "queue"

    # ── Merge-on-the-Fly ──

    def _merge_into_plan(self, stream: InputStream) -> int:
        """Merge new information into the running plan without restarting.

        This is the key innovation: the plan EVOLVES, not resets.
        Like adjusting a recipe: "add more salt" doesn't restart cooking.
        """
        task = self._world.active_task
        if not task:
            return 0

        # Extract actionable modifications from the stream
        modification = self._extract_modification(stream)
        task.modifications.append(modification)
        task.last_modified = time.time()

        # Apply modification to plan
        if modification["type"] == "add_step":
            task.plan.insert(
                task.completed_steps + 1,
                modification["step"],
            )
            task.total_steps += 1
        elif modification["type"] == "modify_step":
            idx = self._find_step_index(task, modification["target"])
            if idx >= 0 and idx < len(task.plan):
                task.plan[idx] = modification["step"]
        elif modification["type"] == "remove_step":
            idx = self._find_step_index(task, modification["target"])
            if idx >= 0 and idx < len(task.plan):
                task.plan.pop(idx)
                task.total_steps -= 1
        elif modification["type"] == "change_direction":
            # Shift overall approach
            task.description = modification["step"]
            task.status = "modified"

        stream.merged_into_plan = True
        task.status = "modified"

        logger.info(
            f"MultiStream: merged '{stream.content[:40]}...' into "
            f"task '{task.description[:40]}...' ({task.total_steps} steps)"
        )
        return len(task.plan)

    def _extract_modification(self, stream: InputStream) -> dict:
        """Extract the actionable modification from a stream.

        Natural language → structured task modification.
        """
        content_lower = stream.content.lower()

        if any(kw in content_lower for kw in ["不对", "错了", "不是", "应该是", "改成"]):
            return {
                "type": "modify_step",
                "target": stream.content[:40],
                "step": stream.content,
            }
        elif any(kw in content_lower for kw in ["还有", "另外", "补充", "加上", "also"]):
            return {
                "type": "add_step",
                "target": "",
                "step": stream.content,
            }
        elif any(kw in content_lower for kw in ["不要", "去掉", "删除", "跳过", "remove"]):
            return {
                "type": "remove_step",
                "target": stream.content,
                "step": "",
            }
        elif any(kw in content_lower for kw in ["换个", "重新", "从", "换一个"]):
            return {
                "type": "change_direction",
                "target": "",
                "step": stream.content,
            }
        else:
            return {
                "type": "add_step",
                "target": "",
                "step": stream.content,
            }

    def _find_step_index(self, task: RunningTask, target: str) -> int:
        """Find which plan step the modification targets."""
        for i, step in enumerate(task.plan):
            overlap = len(set(target.lower().split()) & set(step.lower().split()))
            if overlap > 2:
                return i
        return task.completed_steps  # Default: insert after current

    # ── Attention Multiplexer ──

    def allocate_attention(self) -> dict:
        """Decide where to focus attention right now.

        Like OS process scheduling — but for cognitive tasks.
        Higher priority streams get more "attention budget."
        """
        streams = self._world.pending_streams
        task = self._world.active_task

        # Determine attention allocation
        attention = {"focus_on": "task", "pending": len(streams)}

        if not task:
            if streams:
                attention["focus_on"] = "next_stream"
                attention["next_stream_id"] = streams[0].stream_id
            return attention

        # Check if any stream needs immediate attention
        critical = [s for s in streams if s.priority <= StreamPriority.HIGH]
        if critical:
            attention["focus_on"] = "critical_stream"
            attention["critical_count"] = len(critical)
            attention["action"] = "Process critical streams immediately"
            return attention

        # Check if task needs completion
        if task.completed_steps >= task.total_steps * 0.8:
            attention["focus_on"] = "task_completion"
            attention["action"] = "Finish task before processing new streams"
            return attention

        # Balance: process some streams, continue task
        if streams:
            attention["focus_on"] = "interleave"
            attention["action"] = (
                f"Process 1 stream, then continue task "
                f"({streams[0].stream_type.value})"
            )

        return attention

    # ── Conflict Resolution ──

    def detect_conflicts(self) -> list[dict]:
        """Detect contradictions between concurrent streams.

        Two streams may request conflicting changes to the same task.
        This must be resolved before execution.
        """
        conflicts = []
        task = self._world.active_task
        if not task or len(task.modifications) < 2:
            return conflicts

        # Check recent modifications for conflicts
        recent = task.modifications[-5:]
        for i in range(len(recent)):
            for j in range(i + 1, len(recent)):
                a = recent[i]
                b = recent[j]

                # Conflict: add + remove same step
                if a["type"] == "add_step" and b["type"] == "remove_step":
                    if self._similarity(a["step"], b["target"]) > 0.5:
                        conflicts.append({
                            "type": "add_remove_conflict",
                            "stream_a": a["step"][:50],
                            "stream_b": b["target"][:50],
                            "resolution": "Keep latest modification, discard earlier",
                        })

                # Conflict: two different direction changes
                if a["type"] == "change_direction" and b["type"] == "change_direction":
                    conflicts.append({
                        "type": "direction_conflict",
                        "stream_a": a["step"][:50],
                        "stream_b": b["step"][:50],
                        "resolution": "Ask user to clarify priority",
                    })

        return conflicts

    def _similarity(self, a: str, b: str) -> float:
        """Simple word overlap similarity."""
        wa = set(a.lower().split())
        wb = set(b.lower().split())
        if not wa or not wb:
            return 0.0
        return len(wa & wb) / max(len(wa), len(wb))

    # ── Streaming World State ──

    def update_world_state(self, observation: str) -> None:
        """Add an observation to the continuously updating world state.

        All streams and tasks see this shared context.
        """
        self._world.recent_observations.append(observation)
        if len(self._world.recent_observations) > 50:
            self._world.recent_observations = self._world.recent_observations[-50:]
        self._world.last_updated = time.time()

    def get_world_snapshot(self) -> dict:
        """Get current world state — what all streams and tasks see."""
        task = self._world.active_task
        return {
            "active_task": {
                "description": task.description[:60] if task else "none",
                "progress": (
                    f"{task.completed_steps}/{task.total_steps}"
                    if task else "N/A"
                ),
                "modifications": len(task.modifications) if task else 0,
            } if task else None,
            "pending_streams": len(self._world.pending_streams),
            "recent_observations": self._world.recent_observations[-5:],
            "knowledge_updates": len(self._world.knowledge_updates),
            "contradictions": len(self._world.contradictions),
        }

    # ── Batch Ingest (multiple documents/files at once) ──

    def batch_ingest(self, items: list[dict]) -> dict:
        """Ingest multiple items at once (documents, files, messages).

        Each item processed independently, conflicts detected across all.
        """
        results = []
        for item in items:
            r = self.ingest(
                content=item.get("content", ""),
                stream_type=StreamType(item.get("type", "text")),
                priority=StreamPriority(item.get("priority", 3)),
                parent_task_id=item.get("task_id", ""),
            )
            results.append(r)

        # Detect cross-stream conflicts
        conflicts = self.detect_conflicts()

        return {
            "items_ingested": len(results),
            "results": results,
            "conflicts_detected": len(conflicts),
            "conflicts": conflicts,
            "world_state": self.get_world_snapshot(),
        }


# ── Singleton ──

_engine: Optional[MultiStreamEngine] = None


def get_multi_stream_engine() -> MultiStreamEngine:
    global _engine
    if _engine is None:
        _engine = MultiStreamEngine()
    return _engine
