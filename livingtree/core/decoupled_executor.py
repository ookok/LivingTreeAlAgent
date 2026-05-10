"""Decoupled Executor — fire-and-forget tasks with async result aggregation.

Inspired by Google DeepMind's Decoupled DiLoCo: breaks the monolithic
SPMD execution paradigm into independent workers that train/execute
asynchronously and synchronize only partial results periodically.

LivingTree mapping:
  SPMD training       → synchronous pipeline (all organs wait for each other)
  Independent learners → decoupled cells (each runs independently)
  Lightweight sync    → periodic partial result aggregation
  Fault isolation     → one failing cell doesn't block the rest
  Goodput 58%→88%    → effective throughput from decoupling

Usage:
    executor = get_decoupled_executor()
    future = executor.submit(my_task, *args)
    # task runs independently, executor continues
    result = await executor.collect(timeout=30)
    # get partial results as they arrive
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from loguru import logger


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class TaskHandle:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    retries: int = 0
    worker_id: str = ""
    _future: Optional[asyncio.Task] = field(default=None, repr=False)


@dataclass
class GoodputStats:
    """Effective throughput metrics — DiLoCo's goodput concept."""
    total_submitted: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_timeout: int = 0
    total_wall_time_ms: float = 0.0    # sum of all task wall times
    effective_time_ms: float = 0.0      # time where actual work was done
    goodput_ratio: float = 1.0          # effective / wall (higher = better)
    avg_isolation_saves: int = 0        # tasks saved by fault isolation
    fragment_syncs: int = 0             # partial result aggregations


class DecoupledExecutor:
    """Fire-and-forget executor with async partial aggregation.

    Maps DiLoCo's architecture:
      - Each `submit()` is like a learner starting independent training
      - `collect()` is like the lightweight synchronizer — aggregates
        partial results without blocking the rest
      - Fault isolation: one failing task is logged but doesn't affect others
    """

    def __init__(self, max_concurrent: int = 20, collect_interval: float = 0.1):
        self._max_concurrent = max_concurrent
        self._collect_interval = collect_interval
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._pending: dict[str, TaskHandle] = {}
        self._results: deque[TaskHandle] = deque()
        self._goodput = GoodputStats()
        self._running = False
        self._counter = 0

    # ═══ Core API ═══

    async def submit(
        self, coro_or_func, *args, task_id: str = "", worker_id: str = "",
        retries: int = 0, timeout: float = 60.0, **kwargs,
    ) -> TaskHandle:
        """Submit a task for decoupled execution. Returns immediately.

        Like spawning an independent learner — the task runs in the
        background while the main thread continues processing.
        """
        self._counter += 1
        tid = task_id or f"task_{self._counter}"
        handle = TaskHandle(
            task_id=tid, worker_id=worker_id, retries=retries,
            status=TaskStatus.PENDING,
        )

        if asyncio.iscoroutinefunction(coro_or_func) or asyncio.iscoroutine(coro_or_func):
            task = asyncio.create_task(
                self._run_async(handle, coro_or_func, *args, timeout=timeout, **kwargs)
            )
        else:
            task = asyncio.create_task(
                self._run_sync(handle, coro_or_func, *args, timeout=timeout, **kwargs)
            )

        handle._future = task
        self._pending[tid] = handle
        self._goodput.total_submitted += 1
        return handle

    async def submit_all(
        self, tasks: list[tuple], worker_id: str = "", retries: int = 0,
    ) -> list[TaskHandle]:
        """Submit multiple tasks. They all run independently in parallel."""
        handles = []
        for t in tasks:
            func = t[0]
            args = t[1:] if len(t) > 1 else ()
            h = await self.submit(func, *args, worker_id=worker_id, retries=retries)
            handles.append(h)
        return handles

    async def collect(
        self, timeout: float = 30.0, partial: bool = True,
    ) -> list[TaskHandle]:
        """Collect completed results. Returns partial results if partial=True.

        Like the lightweight synchronizer — aggregates whatever has
        completed without waiting for stragglers.
        """
        results = []
        deadline = time.time() + timeout if timeout > 0 else float("inf")

        while time.time() < deadline:
            while self._results:
                results.append(self._results.popleft())
            if not partial and self._pending:
                await asyncio.sleep(self._collect_interval)
                continue
            if results or not self._pending:
                break
            await asyncio.sleep(self._collect_interval)

        return results

    async def collect_all(self, timeout: float = 60.0) -> list[TaskHandle]:
        """Wait for ALL pending tasks to complete (or timeout)."""
        return await self.collect(timeout=timeout, partial=False)

    # ═══ Status & Goodput ═══

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def goodput(self) -> GoodputStats:
        s = self._goodput
        if s.total_wall_time_ms > 0:
            s.goodput_ratio = min(1.0, s.effective_time_ms / s.total_wall_time_ms)
        return s

    def stats(self) -> dict:
        gp = self.goodput
        return {
            "pending": self.pending_count,
            "submitted": gp.total_submitted,
            "completed": gp.total_completed,
            "failed": gp.total_failed,
            "timeout": gp.total_timeout,
            "goodput_ratio": round(gp.goodput_ratio, 3),
            "isolation_saves": gp.avg_isolation_saves,
            "max_concurrent": self._max_concurrent,
            "diag": f"effective={gp.effective_time_ms:.0f}ms / wall={gp.total_wall_time_ms:.0f}ms",
        }

    # ═══ Internal ═══

    async def _run_async(
        self, handle: TaskHandle, coro, *args, timeout: float, **kwargs,
    ):
        async with self._semaphore:
            handle.status = TaskStatus.RUNNING
            handle.started_at = time.time()
            t0 = handle.started_at

            for attempt in range(handle.retries + 1):
                try:
                    result = await asyncio.wait_for(coro(*args, **kwargs), timeout=timeout)
                    handle.result = result
                    handle.status = TaskStatus.DONE
                    break
                except asyncio.TimeoutError:
                    if attempt < handle.retries:
                        logger.debug(f"Task {handle.task_id} timeout, retry {attempt+1}")
                        continue
                    handle.status = TaskStatus.TIMEOUT
                    handle.error = "timeout"
                except Exception as e:
                    if attempt < handle.retries:
                        logger.debug(f"Task {handle.task_id} error, retry {attempt+1}: {e}")
                        continue
                    handle.status = TaskStatus.FAILED
                    handle.error = str(e)[:200]

            elapsed = (time.time() - t0) * 1000
            self._goodput.total_wall_time_ms += elapsed

            if handle.status == TaskStatus.DONE:
                self._goodput.total_completed += 1
                self._goodput.effective_time_ms += elapsed
            elif handle.status == TaskStatus.FAILED:
                self._goodput.total_failed += 1
                self._goodput.avg_isolation_saves += 1
            else:
                self._goodput.total_timeout += 1

            handle.finished_at = time.time()
            self._pending.pop(handle.task_id, None)
            self._results.append(handle)

    async def _run_sync(
        self, handle: TaskHandle, func, *args, timeout: float, **kwargs,
    ):
        async with self._semaphore:
            handle.status = TaskStatus.RUNNING
            handle.started_at = time.time()
            t0 = handle.started_at

            loop = asyncio.get_event_loop()
            for attempt in range(handle.retries + 1):
                try:
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                        timeout=timeout,
                    )
                    handle.result = result
                    handle.status = TaskStatus.DONE
                    break
                except asyncio.TimeoutError:
                    if attempt < handle.retries:
                        continue
                    handle.status = TaskStatus.TIMEOUT
                    handle.error = "timeout"
                except Exception as e:
                    if attempt < handle.retries:
                        continue
                    handle.status = TaskStatus.FAILED
                    handle.error = str(e)[:200]

            elapsed = (time.time() - t0) * 1000
            self._goodput.total_wall_time_ms += elapsed

            if handle.status == TaskStatus.DONE:
                self._goodput.total_completed += 1
                self._goodput.effective_time_ms += elapsed
            elif handle.status == TaskStatus.FAILED:
                self._goodput.total_failed += 1
                self._goodput.avg_isolation_saves += 1
            else:
                self._goodput.total_timeout += 1

            handle.finished_at = time.time()
            self._pending.pop(handle.task_id, None)
            self._results.append(handle)


_instance: Optional[DecoupledExecutor] = None


def get_decoupled_executor(max_concurrent: int = 20) -> DecoupledExecutor:
    global _instance
    if _instance is None:
        _instance = DecoupledExecutor(max_concurrent=max_concurrent)
    return _instance
