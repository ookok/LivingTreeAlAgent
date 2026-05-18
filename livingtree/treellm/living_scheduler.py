"""LivingScheduler — Time-space aware digital lifeform task orchestration.

Models a living organism's resource management:
  ⏱️  Temporal: urgency × benefit / cost → priority ordering
  📐 Spatial: CPU/memory/tokens/budget → capacity awareness
  🤝 HITL: human-in-the-loop escalation, never says "impossible"
  📊 DataBus: unified event model → polymorphic rendering

The organism never stops — it degrades gracefully, asks for help, and always
finds the next-best-action. Every task has a time cost, resource cost, and
expected benefit. The scheduler maximizes benefit/cost under constraints.

Architecture:
  LivingClock    → time awareness, biorhythm, deadlines
  ResourceBody   → CPU, memory, tokens, budget as "organs" with health
  TaskPriority   → EDF × value-based hybrid scheduler
  EscalationPath → confidence-based HITL, graceful degradation chain
  LivingDataBus  → canonical event format → card/table/graph/timeline/tree
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

DATA_BUS_FILE = Path(".livingtree/living_data_bus.jsonl")


# ═══ Enums ════════════════════════════════════════════════════════


class TaskPriority(StrEnum):
    CRITICAL = "critical"   # Must do now (deadline imminent)
    HIGH = "high"           # Important, do soon
    NORMAL = "normal"       # Regular
    LOW = "low"             # Nice to have
    DEFERRED = "deferred"   # Parked, wake on trigger


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DEGRADED = "degraded"   # Running with reduced capacity
    HUMAN_NEEDED = "human_needed"
    DONE = "done"
    DEFERRED = "deferred"
    FAILED = "failed"       # Tried everything, gave up gracefully


class EscalationLevel(StrEnum):
    NONE = "none"           # Handle autonomously
    HINT = "hint"           # Ask user a quick question
    CONFIRM = "confirm"     # Need user confirmation
    ASSIST = "assist"       # Need human to do part of the task
    FULL = "full"           # Can't proceed, hand over to human


class RenderFormat(StrEnum):
    CARD = "card"           # Summary card
    TABLE = "table"         # Data table
    GRAPH = "graph"         # Relationship graph
    TIMELINE = "timeline"   # Chronological
    TREE = "tree"           # Hierarchical
    METRIC = "metric"       # Single number/gauge
    LOG = "log"             # Raw event stream


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class ResourceSnapshot:
    """Current resource state of the organism."""
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_limit_mb: float = 0.0
    disk_free_gb: float = 0.0
    tokens_used_today: int = 0
    tokens_budget_today: int = 1_000_000
    budget_spent_today: float = 0.0
    budget_limit_today: float = 10.0
    active_tasks: int = 0
    provider_health: dict[str, float] = field(default_factory=dict)

    @property
    def memory_pressure(self) -> float:
        return self.memory_mb / max(self.memory_limit_mb, 1)

    @property
    def token_pressure(self) -> float:
        return self.tokens_used_today / max(self.tokens_budget_today, 1)

    @property
    def budget_pressure(self) -> float:
        return self.budget_spent_today / max(self.budget_limit_today, 1)

    @property
    def overloaded(self) -> bool:
        return (self.memory_pressure > 0.85 or self.token_pressure > 0.9
                or self.budget_pressure > 0.9 or self.cpu_percent > 90)


@dataclass
class ScheduledTask:
    """A task with temporal and spatial cost/benefit."""
    id: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    deadline: float = 0.0            # Unix timestamp, 0 = no deadline
    estimated_duration_ms: float = 1000
    estimated_tokens: int = 100
    estimated_cost_yuan: float = 0.01
    expected_benefit: float = 0.5     # 0.0-1.0
    confidence: float = 0.8           # How confident we can do this
    escalation_level: EscalationLevel = EscalationLevel.NONE
    escalation_message: str = ""
    resource_requirements: dict[str, float] = field(default_factory=dict)
    degradation_chain: list[str] = field(default_factory=list)
    result: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def urgency(self) -> float:
        """0-1: how urgent based on deadline proximity."""
        if self.deadline <= 0:
            return 0.3
        remaining = self.deadline - time.time()
        if remaining <= 0:
            return 1.0
        return min(1.0, 3600 / max(remaining, 1))  # 1h window

    @property
    def priority_score(self) -> float:
        """Composite score: (urgency × benefit) / (cost × confidence)."""
        urgency = self.urgency
        benefit = self.expected_benefit
        cost_factor = math.log2(self.estimated_tokens + 1) / 10 + self.estimated_cost_yuan
        confidence = max(self.confidence, 0.1)
        return (urgency * 0.4 + benefit * 0.4 + self.priority_weight() * 0.2) / (cost_factor + confidence * 0.3)

    def priority_weight(self) -> float:
        return {"critical": 1.0, "high": 0.7, "normal": 0.4, "low": 0.2, "deferred": 0.05}.get(
            self.priority.value, 0.4
        )


@dataclass
class LivingEvent:
    """Unified data bus event — single canonical format, polymorphic rendering."""
    id: str
    event_type: str          # "thought" | "action" | "error" | "metric" | "escalation" | "boundary"
    timestamp: float = field(default_factory=time.time)
    source_organ: str = ""   # "brain" | "heart" | "hands" | "memory" | ...
    summary: str = ""        # One-line human-readable
    detail: str = ""         # Full content
    data: dict[str, Any] = field(default_factory=dict)
    render_hints: list[RenderFormat] = field(default_factory=lambda: [RenderFormat.CARD])
    priority: TaskPriority = TaskPriority.NORMAL
    related_events: list[str] = field(default_factory=list)
    confidence: float = 0.8
    session_id: str = "perpetual"


# ═══ LivingScheduler ══════════════════════════════════════════════


class LivingScheduler:
    """Time-space aware task scheduler. Maximizes benefit/cost under constraints."""

    _instance: Optional["LivingScheduler"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "LivingScheduler":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = LivingScheduler()
        return cls._instance

    def __init__(self):
        self._tasks: dict[str, ScheduledTask] = {}
        self._events: list[LivingEvent] = []
        self._lock = asyncio.Lock()
        self._event_max = 1000
        self._clock = LivingClock()
        self._resources = ResourceBody()
        self._escalator = HITLEscalator()

    # ── Task Management ────────────────────────────────────────────

    def schedule(self, description: str, priority: TaskPriority = TaskPriority.NORMAL,
                 deadline_seconds: float = 0.0, estimated_tokens: int = 100,
                 estimated_cost: float = 0.01, expected_benefit: float = 0.5,
                 confidence: float = 0.8, **meta) -> ScheduledTask:
        """Register a new task with the scheduler."""
        task_id = f"task_{int(time.time()*1000)}_{len(self._tasks)}"
        task = ScheduledTask(
            id=task_id, description=description, priority=priority,
            deadline=time.time() + deadline_seconds if deadline_seconds > 0 else 0,
            estimated_tokens=estimated_tokens, estimated_cost_yuan=estimated_cost,
            expected_benefit=expected_benefit, confidence=confidence,
            metadata=meta,
        )

        # Check if resources allow this task
        if self._resources.overloaded:
            task.priority = TaskPriority.DEFERRED
            task.status = TaskStatus.DEFERRED
            logger.info(f"Scheduler: deferred '{description[:60]}' — system overloaded")
        else:
            task.priority = self._adjust_priority(task)
            # Assign optimal time slot
            task.metadata["scheduled_at"] = self._clock.next_slot(task)

        self._tasks[task_id] = task
        self._emit(LivingEvent(
            id=f"evt_{task_id}", event_type="task_created",
            source_organ="scheduler", summary=f"Task: {description[:80]}",
            data={"task_id": task_id, "priority": task.priority.value,
                  "score": round(task.priority_score, 3)},
        ))
        return task

    def get_next(self, max_tasks: int = 3) -> list[ScheduledTask]:
        """Get highest-priority pending tasks that fit within resource budget."""
        pending = [t for t in self._tasks.values()
                   if t.status in (TaskStatus.PENDING, TaskStatus.DEFERRED)]

        # Check which tasks can be activated (resources allow)
        activatable = []
        for t in pending:
            if self._resources.can_allocate(t.estimated_tokens, t.estimated_cost_yuan):
                activatable.append(t)

        # Sort by priority_score descending
        activatable.sort(key=lambda t: -t.priority_score)

        # Limit by current resource headroom
        selected = []
        tokens_allocated = 0
        cost_allocated = 0.0
        for t in activatable[:max_tasks]:
            if tokens_allocated + t.estimated_tokens < self._resources.available_tokens * 0.5:
                selected.append(t)
                tokens_allocated += t.estimated_tokens
                cost_allocated += t.estimated_cost_yuan

        return selected

    def start(self, task_id: str) -> bool:
        """Mark task as running."""
        t = self._tasks.get(task_id)
        if not t:
            return False
        t.status = TaskStatus.RUNNING
        self._emit(LivingEvent(
            id=f"evt_start_{task_id}", event_type="task_started",
            source_organ="scheduler", summary=f"Started: {t.description[:80]}",
            data={"task_id": task_id},
        ))
        return True

    def complete(self, task_id: str, result: Any = None, success: bool = True) -> None:
        """Mark task as done."""
        t = self._tasks.get(task_id)
        if not t:
            return
        t.status = TaskStatus.DONE if success else TaskStatus.FAILED
        t.result = result
        self._emit(LivingEvent(
            id=f"evt_done_{task_id}", event_type="task_completed",
            source_organ="scheduler",
            summary=f"{'Done' if success else 'Failed'}: {t.description[:80]}",
            data={"task_id": task_id, "success": success, "result": str(result)[:200]},
            confidence=1.0 if success else 0.3,
        ))

    def escalate(self, task_id: str, level: EscalationLevel,
                 message: str) -> ScheduledTask:
        """Escalate task to human. Never just fail."""
        t = self._tasks.get(task_id)
        if not t:
            return None
        t.escalation_level = level
        t.escalation_message = message
        t.status = TaskStatus.HUMAN_NEEDED
        self._emit(LivingEvent(
            id=f"evt_escalate_{task_id}", event_type="escalation",
            source_organ="scheduler",
            summary=f"Need human [{level.value}]: {message[:100]}",
            data={"task_id": task_id, "level": level.value, "message": message},
            confidence=0.5, priority=TaskPriority.HIGH,
            render_hints=[RenderFormat.CARD, RenderFormat.TIMELINE],
        ))
        return t

    def _adjust_priority(self, task: ScheduledTask) -> TaskPriority:
        """Adjust priority based on resource pressure."""
        if self._resources.overloaded and task.priority not in (TaskPriority.CRITICAL, TaskPriority.HIGH):
            return TaskPriority.LOW
        return task.priority

    # ── Event Bus ──────────────────────────────────────────────────

    def _emit(self, event: LivingEvent) -> None:
        self._events.append(event)
        if len(self._events) > self._event_max:
            self._events = self._events[-self._event_max:]

    def get_events(self, event_type: str = "", source_organ: str = "",
                   limit: int = 20) -> list[LivingEvent]:
        events = self._events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if source_organ:
            events = [e for e in events if e.source_organ == source_organ]
        return events[-limit:]

    def render(self, events: list[LivingEvent] = None,
               format: RenderFormat = RenderFormat.CARD,
               request: Any = None) -> list[dict]:
        """Render events using capability-probing renderer.

        With request: probes client capabilities for optimal format.
        Without request: uses the specified format directly.
        """
        events = events or self._events[-50:]

        # Use LivingRenderer if available for capability-probed rendering
        if request is not None:
            try:
                from .living_renderer import get_living_renderer, RenderLevel
                renderer = get_living_renderer()
                caps = renderer.probe(request)
                result = renderer.render(
                    {"events": [e.__dict__ if hasattr(e, '__dict__') else e for e in events]},
                    caps, format=format.value, title="Living Dashboard",
                )
                return [{
                    "format": "auto",
                    "level": LEVEL_NAMES.get(caps.max_level.value, "rich"),
                    "degraded_from": result.degraded_from.value if result.degraded_from else None,
                    "content": result.content,
                    "mime_type": result.mime_type,
                    "byte_size": result.byte_size,
                    "render_time_ms": round(result.render_time_ms, 2),
                    "events": events if isinstance(events, list) else [],
                }]
            except Exception:
                pass
        renderers = {
            RenderFormat.CARD: self._render_card,
            RenderFormat.TABLE: self._render_table,
            RenderFormat.TIMELINE: self._render_timeline,
            RenderFormat.GRAPH: self._render_graph,
            RenderFormat.TREE: self._render_tree,
            RenderFormat.METRIC: self._render_metric,
            RenderFormat.LOG: self._render_log,
        }
        return renderers.get(format, self._render_card)(events)

    # ── Renderers ─────────────────────────────────────────────────

    def _render_card(self, events):
        return [{"id": e.id, "type": e.event_type, "summary": e.summary,
                 "organ": e.source_organ, "ts": e.timestamp, "confidence": e.confidence,
                 "data": e.data} for e in events]

    def _render_table(self, events):
        return [{"id": e.id, "time": e.timestamp, "type": e.event_type,
                 "organ": e.source_organ, "summary": e.summary,
                 "confidence": round(e.confidence, 2)} for e in events]

    def _render_timeline(self, events):
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        return [{"ts": e.timestamp, "label": e.summary[:60],
                 "type": e.event_type, "group": e.source_organ,
                 "endTs": e.timestamp + 60} for e in sorted_events]

    def _render_graph(self, events):
        nodes = [{"id": e.id, "label": e.summary[:40], "group": e.source_organ}
                 for e in events]
        edges = []
        for e in events:
            for rel in e.related_events:
                edges.append({"from": e.id, "to": rel})
        return {"nodes": nodes, "edges": edges}

    def _render_tree(self, events):
        tree = {}
        for e in events:
            organ = e.source_organ or "unknown"
            tree.setdefault(organ, []).append({
                "id": e.id, "label": e.summary[:50], "children": e.data.get("children", []),
            })
        return tree

    def _render_metric(self, events):
        return [{"label": e.summary[:30], "value": e.confidence,
                 "ts": e.timestamp} for e in events]

    def _render_log(self, events):
        return [f"[{e.timestamp:.0f}] [{e.source_organ}] {e.summary}" for e in events]

    def state(self) -> dict:
        return {
            "tasks": {
                "total": len(self._tasks),
                "pending": sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING),
                "running": sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING),
                "human_needed": sum(1 for t in self._tasks.values() if t.status == TaskStatus.HUMAN_NEEDED),
                "done": sum(1 for t in self._tasks.values() if t.status == TaskStatus.DONE),
                "failed": sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED),
            },
            "events": len(self._events),
            "resources": self._resources.snapshot(),
            "clock": self._clock.state(),
            "escalations": self._escalator.pending(),
        }


# ═══ LivingClock ═══════════════════════════════════════════════════


class LivingClock:
    """Time-awareness: biorhythm, peak hours, optimal scheduling."""

    PEAK_HOURS = {9, 10, 11, 14, 15, 16, 17, 20, 21}
    LOW_HOURS = {0, 1, 2, 3, 4, 5}

    def now(self) -> float:
        return time.time()

    def hour(self) -> int:
        return time.localtime().tm_hour

    def is_peak(self) -> bool:
        return self.hour() in self.PEAK_HOURS

    def is_low(self) -> bool:
        return self.hour() in self.LOW_HOURS

    def next_slot(self, task: ScheduledTask) -> float:
        """Recommend optimal time to execute this task."""
        now = self.now()
        if task.priority == TaskPriority.CRITICAL:
            return now
        if self.is_low():
            return now + 3600  # Defer non-critical to non-low hours
        return now

    def time_of_day_factor(self) -> float:
        """0.5-1.5: resource efficiency multiplier based on time."""
        h = self.hour()
        if h in self.PEAK_HOURS:
            return 1.2
        if h in self.LOW_HOURS:
            return 0.7
        return 1.0

    def state(self) -> dict:
        return {"hour": self.hour(), "is_peak": self.is_peak(),
                "time_factor": self.time_of_day_factor()}


# ═══ ResourceBody ══════════════════════════════════════════════════


class ResourceBody:
    """Spatial resource awareness — tracks what the body can do right now."""

    def __init__(self):
        self._token_used: int = 0
        self._token_limit: int = 1_000_000
        self._budget_spent: float = 0.0
        self._budget_limit: float = 10.0

    @property
    def overloaded(self) -> bool:
        s = self.snapshot()
        return s.overloaded

    @property
    def available_tokens(self) -> int:
        return max(0, self._token_limit - self._token_used)

    def can_allocate(self, tokens: int, cost: float) -> bool:
        """Check if there's enough resource for this task."""
        if self._token_used + tokens > self._token_limit * 1.2:
            return False
        if self._budget_spent + cost > self._budget_limit * 1.2:
            return False
        return True

    def allocate(self, tokens: int, cost: float) -> None:
        self._token_used += tokens
        self._budget_spent += cost

    def snapshot(self) -> ResourceSnapshot:
        import psutil
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        disk = psutil.disk_usage("/")
        return ResourceSnapshot(
                cpu_percent=cpu,
                memory_mb=mem.used / 1024 / 1024,
                memory_limit_mb=mem.total / 1024 / 1024,
                disk_free_gb=disk.free / 1024 / 1024 / 1024,
                tokens_used_today=self._token_used,
                tokens_budget_today=self._token_limit,
                budget_spent_today=self._budget_spent,
                budget_limit_today=self._budget_limit,
            )

    def set_budget(self, tokens: int, cost_yuan: float) -> None:
        self._token_limit = tokens
        self._budget_limit = cost_yuan


# ═══ HITLEscalator ════════════════════════════════════════════════


class HITLEscalator:
    """Human-in-the-loop escalation. Never says 'impossible'."""

    # Confidence thresholds for auto-escalation
    CONFIDENCE_ASK = 0.3     # Below this: ask user
    CONFIDENCE_CONFIRM = 0.5  # Below this: confirm with user
    CONFIDENCE_AUTO = 0.7     # Above this: autonomous

    def __init__(self):
        self._pending: list[dict] = []

    def assess(self, task: ScheduledTask) -> EscalationLevel:
        """Determine if task needs human intervention."""
        if task.confidence < self.CONFIDENCE_ASK:
            return EscalationLevel.ASSIST
        if task.confidence < self.CONFIDENCE_CONFIRM:
            return EscalationLevel.CONFIRM
        if task.estimated_cost_yuan > 1.0:  # Expensive → confirm
            return EscalationLevel.CONFIRM
        if task.status == TaskStatus.FAILED:
            return EscalationLevel.ASSIST
        return EscalationLevel.NONE

    def degrade_plan(self, task: ScheduledTask) -> list[str]:
        """Generate a degradation chain — never fail, just do less.

        Returns list of progressively simpler approaches.
        """
        base = task.description.lower()
        chain = task.degradation_chain or []

        if not chain:
            if "生成" in base or "generate" in base:
                chain = [
                    "用最详细的方式完整生成",
                    "生成核心部分 + 其余用摘要",
                    "只生成关键结论 + 框架",
                    "只返回一句话建议 + 下一步方向",
                ]
            elif "修复" in base or "fix" in base:
                chain = [
                    "完整修复 + 测试验证",
                    "修复主要问题 + 手动验证提示",
                    "提供修复方案 + 代码片段",
                    "分析根因 + 建议人工修复步骤",
                ]
            elif "分析" in base or "analyze" in base:
                chain = [
                    "深度分析 + 多维度对比 + 可视化",
                    "核心分析 + 关键指标",
                    "简要分析 + 关键发现",
                    "一句话结论 + 参考方向",
                ]
            else:
                chain = [
                    "完整执行",
                    "核心部分执行 + 其余框架",
                    "简要执行 + 建议",
                    "一句话建议 + 方向",
                ]

        return chain

    def submit(self, task_id: str, level: EscalationLevel,
               message: str, options: list[str] = None) -> dict:
        """Submit a human escalation request."""
        entry = {
            "task_id": task_id, "level": level.value,
            "message": message, "options": options or [],
            "timestamp": time.time(), "status": "pending",
        }
        self._pending.append(entry)
        if len(self._pending) > 100:
            self._pending = self._pending[-100:]
        return entry

    def resolve(self, task_id: str, human_decision: str) -> None:
        """Human resolved an escalation."""
        for e in self._pending:
            if e["task_id"] == task_id:
                e["status"] = "resolved"
                e["resolution"] = human_decision
                break

    def pending(self) -> list[dict]:
        return [e for e in self._pending if e["status"] == "pending"]


# ═══ Singleton ════════════════════════════════════════════════════


_scheduler: Optional[LivingScheduler] = None
_scheduler_lock = threading.Lock()


def get_living_scheduler() -> LivingScheduler:
    global _scheduler
    if _scheduler is None:
        with _scheduler_lock:
            if _scheduler is None:
                _scheduler = LivingScheduler()
    return _scheduler


__all__ = [
    "LivingScheduler", "LivingClock", "ResourceBody", "HITLEscalator",
    "LivingEvent", "ScheduledTask", "ResourceSnapshot",
    "TaskPriority", "TaskStatus", "EscalationLevel", "RenderFormat",
    "get_living_scheduler",
]
