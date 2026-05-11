"""TaskGuard — protects long/complex tasks from crashes.

Wraps execution with:
  1. Global timeout (configurable per task type)
  2. Circuit breaker with cooldown (consecutive failures → pause)
  3. Atomic checkpoint writes (write to temp file, then rename)
  4. Dead-letter queue for failed persistent operations
  5. Rate limiting for API calls
  6. Automatic cleanup on timeout/cancellation

Integrates with ErrorInterceptor for crash recording.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from loguru import logger

DEAD_LETTER_DIR = Path(".livingtree/dead_letters")

TASK_TIMEOUTS: dict[str, float] = {
    "chat": 120.0,
    "document": 300.0,
    "code_gen": 180.0,
    "training": 3600.0,
    "search": 30.0,
    "default": 120.0,
}

CIRCUIT_COOLDOWN = 60.0  # seconds before retry after circuit opens
CIRCUIT_MAX_FAILURES = 5


@dataclass
class CircuitState:
    failures: int = 0
    last_failure: float = 0.0
    open: bool = False

    def record_failure(self):
        self.failures += 1
        self.last_failure = time.time()
        if self.failures >= CIRCUIT_MAX_FAILURES:
            self.open = True
            logger.warning(f"Circuit OPEN after {self.failures} failures")

    def record_success(self):
        self.failures = 0
        self.open = False

    def can_retry(self) -> bool:
        if not self.open:
            return True
        if time.time() - self.last_failure > CIRCUIT_COOLDOWN:
            self.open = False
            self.failures = 0
            return True
        return False


@dataclass
class TaskResult:
    success: bool
    data: Any = None
    error: str = ""
    timed_out: bool = False
    circuit_open: bool = False
    attempts: int = 0
    duration_ms: float = 0.0


class TaskGuard:
    """Protects long-running tasks from crashes."""

    def __init__(self):
        self._circuits: dict[str, CircuitState] = {}
        self._rate_limits: dict[str, float] = {}
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._dead_letter_count = 0

    # ═══ Core execution ═══

    async def run(
        self,
        task_type: str,
        coro_or_fn,
        *,
        timeout: float | None = None,
        max_retries: int = 2,
        task_id: str = "",
        cleanup_fn: Callable | None = None,
    ) -> TaskResult:
        """Execute a task with full protection.

        Returns TaskResult — never raises. All exceptions captured.
        """
        tid = task_id or str(uuid.uuid4())[:8]
        timeout_val = timeout or TASK_TIMEOUTS.get(task_type, TASK_TIMEOUTS["default"])
        circuit = self._circuits.setdefault(task_type, CircuitState())
        t0 = time.time()

        # Circuit breaker check
        if not circuit.can_retry():
            return TaskResult(
                success=False, circuit_open=True,
                error=f"Circuit open for {task_type} ({circuit.failures} failures)",
                duration_ms=0,
            )

        # Rate limit check
        self._rate_limits.setdefault(task_type, 0)
        elapsed = time.time() - self._rate_limits[task_type]
        if elapsed < 0.1:  # max 10 calls/sec
            await asyncio.sleep(0.1 - elapsed)

        result = TaskResult(success=False, timed_out=False)

        for attempt in range(max_retries + 1):
            result.attempts = attempt + 1
            try:
                if asyncio.iscoroutinefunction(coro_or_fn) or asyncio.iscoroutine(coro_or_fn):
                    task = asyncio.create_task(coro_or_fn if asyncio.iscoroutine(coro_or_fn) else coro_or_fn())
                else:
                    task = asyncio.create_task(asyncio.to_thread(coro_or_fn))

                self._active_tasks[tid] = task

                try:
                    data = await asyncio.wait_for(task, timeout=timeout_val)
                except asyncio.TimeoutError:
                    result.timed_out = True
                    result.error = f"Task {tid} timed out after {timeout_val}s"
                    if cleanup_fn:
                        try:
                            await cleanup_fn() if asyncio.iscoroutinefunction(cleanup_fn) else cleanup_fn()
                        except Exception:
                            pass
                    continue
                finally:
                    self._active_tasks.pop(tid, None)

                result.success = True
                result.data = data
                result.duration_ms = (time.time() - t0) * 1000
                self._rate_limits[task_type] = time.time()
                circuit.record_success()
                return result

            except asyncio.CancelledError:
                result.error = f"Task {tid} cancelled"
                circuit.record_failure()
                return result

            except Exception as e:
                result.error = str(e)[:200]
                if attempt < max_retries:
                    delay = 2 ** attempt
                    logger.debug(f"Task {tid} retry {attempt + 1}/{max_retries} in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Task {tid} failed after {max_retries + 1} attempts: {e}")
                    circuit.record_failure()
                    self._dead_letter(tid, task_type, result.error)

                if cleanup_fn:
                    try:
                        await cleanup_fn() if asyncio.iscoroutinefunction(cleanup_fn) else cleanup_fn()
                    except Exception:
                        pass

        result.duration_ms = (time.time() - t0) * 1000
        return result

    # ═══ Atomic file writes ═══

    @staticmethod
    def atomic_write(path: Path, content: str | bytes):
        """Atomic write: temp file → rename. Crash during write leaves original intact."""
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                tmp.write_text(content, encoding="utf-8")
            else:
                tmp.write_bytes(content)
            os.replace(str(tmp), str(path))  # Atomic on POSIX + Windows
        except Exception as e:
            logger.debug(f"Atomic write {path}: {e}")
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

    # ═══ Dead letter queue ═══

    def _dead_letter(self, task_id: str, task_type: str, error: str):
        try:
            DEAD_LETTER_DIR.mkdir(parents=True, exist_ok=True)
            dl = DEAD_LETTER_DIR / f"{task_id}.json"
            dl.write_text(json.dumps({
                "task_id": task_id, "type": task_type,
                "error": error, "timestamp": time.time(),
            }, indent=2, ensure_ascii=False))
            self._dead_letter_count += 1
            logger.info(f"Dead letter: {task_id} ({task_type})")
        except Exception:
            pass

    # ═══ Status ═══

    def cancel_all(self):
        for tid, task in list(self._active_tasks.items()):
            if not task.done():
                task.cancel()

    def get_status(self) -> dict:
        return {
            "active_tasks": len(self._active_tasks),
            "dead_letters": self._dead_letter_count,
            "circuits": {
                k: {"open": v.open, "failures": v.failures}
                for k, v in self._circuits.items()
            },
        }


# ═══ Global ═══

_guard: TaskGuard | None = None


def get_guard() -> TaskGuard:
    global _guard
    if _guard is None:
        _guard = TaskGuard()
    return _guard
