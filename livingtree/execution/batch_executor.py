"""Batch Executor — FIFO/LIFO queued task execution (Clibor-inspired).

Enqueues tasks with optional priority and executes them in FIFO or LIFO order.
Supports per-task handlers, stats tracking, and batch execution with mode override.

Usage:
    from livingtree.execution.batch_executor import BatchExecutor, BatchMode, BatchTask

    executor = BatchExecutor(mode=BatchMode.FIFO)
    executor.enqueue(BatchTask(name="parse_doc", handler=parse, priority=3))
    executor.enqueue(BatchTask(name="summarize", handler=summarize, priority=1))
    results = await executor.execute_all()
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable, Optional

from loguru import logger


class BatchMode(str, Enum):
    FIFO = "fifo"   # First-in, first-out (default queue behavior)
    LIFO = "lifo"   # Last-in, first-out (stack behavior)


@dataclass(order=True)
class BatchTask:
    """A task unit for batch execution with priority support."""
    name: str = field(compare=False)
    handler: Optional[Callable[[], Awaitable[Any]]] = field(compare=False, default=None)
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)
    created_at: float = field(default_factory=time.time, compare=True)

    # Runtime state
    result: Any = field(default=None, compare=False)
    error: Optional[str] = field(default=None, compare=False)
    status: str = field(default="pending", compare=False)  # pending, running, completed, failed
    started_at: float = field(default=0.0, compare=False)
    completed_at: float = field(default=0.0, compare=False)

    @property
    def latency_ms(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return 0.0


class BatchExecutor:
    """Priority-aware FIFO/LIFO task queue executor.

    Tasks are sorted by priority (higher first), then by creation_time
    (ascending for FIFO, descending for LIFO within same priority).
    """

    def __init__(self, mode: BatchMode = BatchMode.FIFO):
        self.mode = mode
        self._queue: deque[BatchTask] = deque()
        self._stats = {
            "enqueued": 0,
            "completed": 0,
            "failed": 0,
            "total_latency_ms": 0.0,
        }
        self._history: list[BatchTask] = []

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def enqueue(self, task: BatchTask) -> BatchTask:
        """Add a task to the queue (auto-sorts by priority + creation time)."""
        self._queue.append(task)
        self._stats["enqueued"] += 1
        self._sort_queue()
        return task

    def enqueue_batch(self, tasks: list[BatchTask]) -> list[BatchTask]:
        """Add multiple tasks at once, then sort."""
        for task in tasks:
            self._queue.append(task)
            self._stats["enqueued"] += 1
        self._sort_queue()
        return tasks

    def next_task(self) -> Optional[BatchTask]:
        """Peek at the next task without removing it."""
        if not self._queue:
            return None
        if self.mode == BatchMode.FIFO:
            return self._queue[0]
        else:
            return self._queue[-1]

    def _pop_next(self) -> Optional[BatchTask]:
        """Remove and return the next task based on current mode."""
        if not self._queue:
            return None
        if self.mode == BatchMode.FIFO:
            return self._queue.popleft()
        else:
            return self._queue.pop()

    async def execute_next(self) -> Optional[BatchTask]:
        """Pop and execute the next task based on current mode.

        Returns the executed task (with result/error set), or None if queue empty.
        """
        task = self._pop_next()
        if task is None:
            return None
        return await self._execute_task(task)

    async def execute_all(self, mode: Optional[BatchMode] = None) -> list[BatchTask]:
        """Execute ALL tasks in the queue.

        Args:
            mode: Optional mode override for this batch (does not change self.mode).

        Returns:
            List of all executed tasks with results.
        """
        saved_mode = self.mode
        if mode is not None:
            self.mode = mode

        results: list[BatchTask] = []
        while not self.is_empty:
            task = await self.execute_next()
            if task:
                results.append(task)

        self.mode = saved_mode
        return results

    async def execute_generator(self, mode: Optional[BatchMode] = None):
        """Execute tasks one by one, yielding each result.

        Useful for streaming task results to a UI.
        """
        saved_mode = self.mode
        if mode is not None:
            self.mode = mode

        while not self.is_empty:
            task = await self.execute_next()
            if task:
                yield task

        self.mode = saved_mode

    def clear(self) -> None:
        """Remove all pending tasks from the queue."""
        self._queue.clear()

    def get_stats(self) -> dict[str, Any]:
        avg_latency = 0.0
        total = self._stats["completed"] + self._stats["failed"]
        if total > 0:
            avg_latency = round(self._stats["total_latency_ms"] / total, 1)
        return {
            **self._stats,
            "queue_size": self.queue_size,
            "total_tasks": total,
            "avg_latency_ms": avg_latency,
            "mode": self.mode.value,
        }

    def pending_tasks(self) -> list[BatchTask]:
        """Return all pending tasks in execution order."""
        tasks = list(self._queue)
        if self.mode == BatchMode.LIFO:
            tasks.reverse()
        return tasks

    # ── Private ──

    def _sort_queue(self) -> None:
        """Sort queue: priority descending, then by creation_time.

        For LIFO: newer tasks (higher creation_time) at end (popped first via pop()).
        For FIFO: older tasks (lower creation_time) at front (popped first via popleft()).
        The base sort is priority descending, creation_time ascending.
        """
        items = sorted(self._queue, key=lambda t: (-t.priority, t.created_at))
        self._queue = deque(items)

    async def _execute_task(self, task: BatchTask) -> BatchTask:
        """Execute a single task and update stats."""
        task.status = "running"
        task.started_at = time.time()

        if task.handler is None:
            task.status = "completed"
            task.completed_at = time.time()
            self._stats["completed"] += 1
            self._history.append(task)
            return task

        try:
            result = task.handler()
            if hasattr(result, "__await__"):
                task.result = await result
            else:
                task.result = result
            task.status = "completed"
            self._stats["completed"] += 1
        except Exception as e:
            task.error = str(e)
            task.status = "failed"
            self._stats["failed"] += 1
            logger.warning(f"Batch task '{task.name}' failed: {e}")

        task.completed_at = time.time()
        self._stats["total_latency_ms"] += task.latency_ms
        self._history.append(task)
        return task


# Convenience factory
def create_batch_executor(mode: str = "fifo") -> BatchExecutor:
    """Create a BatchExecutor from a mode string."""
    return BatchExecutor(mode=BatchMode(mode.lower()))
