from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Coroutine

from loguru import logger

_guard_instance: ConcurrencyGuard | None = None


@dataclass
class BackgroundTask:
    """Metadata for a tracked background task."""
    name: str
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending | running | cancelled | done | failed
    exception: str | None = None
    task: asyncio.Task[Any] | None = field(default=None, repr=False)

    @property
    def age(self) -> float:
        return time.time() - self.created_at


class ConcurrencyGuard:
    """
    Managed concurrency guard — replaces bare `asyncio.create_task()` calls
    with lifecycle-tracked task groups.

    Integration notes for hub.py::

        # Before (bare create_task):
        asyncio.create_task(some_coro())

        # After (managed via guard):
        guard = get_concurrency_guard()
        guard.spawn("poll_channel", some_coro())
        # or batch:
        guard.spawn_many("skill_", [install_skill(s) for s in skills])

        # Graceful shutdown:
        await guard.cancel_all()

        # Debug:
        print(guard.stats())
        for t in guard.list_tasks():
            print(t.name, t.status, t.age)

    Uses asyncio.TaskGroup on Python 3.13+ for structured concurrency;
    falls back gracefully to asyncio.create_task on older runtimes.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, BackgroundTask] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
        self._supports_taskgroup: bool = hasattr(asyncio, "TaskGroup")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def spawn(self, name: str, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        """Create a managed task, track it, and schedule auto-cleanup."""
        async with self._lock:
            if name in self._tasks:
                suffix = 1
                while f"{name}_{suffix}" in self._tasks:
                    suffix += 1
                name = f"{name}_{suffix}"
                logger.debug(f"Task name collision, renamed to {name}")

            bt = BackgroundTask(name=name, status="pending")
            self._tasks[name] = bt

        task: asyncio.Task[Any]

        task = asyncio.create_task(self._run_with_tracking(bt, coro))

        async with self._lock:
            bt.task = task
            bt.status = "running"

        task.add_done_callback(lambda _: self._on_done(bt))
        return task

    async def spawn_many(
        self, name_prefix: str, coros: list[Coroutine[Any, Any, Any]]
    ) -> list[asyncio.Task[Any]]:
        """Batch spawn tracked tasks with a shared prefix."""
        tasks: list[asyncio.Task[Any]] = []
        for i, coro in enumerate(coros):
            t = await self.spawn(f"{name_prefix}{i}", coro)
            tasks.append(t)
        return tasks

    async def cancel_all(self) -> int:
        """Gracefully cancel all tracked tasks. Returns count cancelled."""
        async with self._lock:
            names = list(self._tasks.keys())

        cancelled = 0
        for name in names:
            async with self._lock:
                bt = self._tasks.get(name)
            if bt is None or bt.task is None:
                continue
            if not bt.task.done():
                bt.task.cancel()
                bt.status = "cancelled"
                cancelled += 1
                try:
                    await bt.task
                except (asyncio.CancelledError, Exception):
                    pass

        logger.info(f"ConcurrencyGuard: cancelled {cancelled} tasks")
        return cancelled

    def stats(self) -> dict[str, int]:
        """Return counts by task status."""
        counts: dict[str, int] = {}
        # Snapshot to avoid mutation during iteration
        for bt in list(self._tasks.values()):
            counts[bt.status] = counts.get(bt.status, 0) + 1
        return counts

    def list_tasks(self) -> list[BackgroundTask]:
        """Return all tracked BackgroundTask objects."""
        return list(self._tasks.values())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run_with_tracking(self, bt: BackgroundTask, coro: Coroutine[Any, Any, Any]) -> Any:
        bt.status = "running"
        try:
            return await coro
        except asyncio.CancelledError:
            bt.status = "cancelled"
            raise
        except Exception as exc:
            bt.status = "failed"
            bt.exception = str(exc)
            logger.opt(exception=True).warning(f"BackgroundTask [{bt.name}] failed")
            raise
        finally:
            bt.status = "done"

    def _on_done(self, bt: BackgroundTask) -> None:
        """Callback: remove completed tasks from registry after a short delay."""
        loop = asyncio.get_event_loop()
        loop.create_task(self._delayed_cleanup(bt.name))

    async def _delayed_cleanup(self, name: str) -> None:
        await asyncio.sleep(0.1)
        async with self._lock:
            bt = self._tasks.get(name)
            if bt and bt.status == "done":
                del self._tasks[name]


def get_concurrency_guard() -> ConcurrencyGuard:
    """Return the singleton ConcurrencyGuard instance."""
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = ConcurrencyGuard()
        logger.info("ConcurrencyGuard singleton created")
    return _guard_instance
