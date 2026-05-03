"""SelfHealer — Auto-healing system for task execution and component recovery.

Monitors system health, detects failures, and executes recovery strategies
including checkpoint restore, cell regeneration, and service restart.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from loguru import logger
from pydantic import BaseModel, Field


class HealthCheck(BaseModel):
    """A health check for a system component."""
    name: str
    status: str = "healthy"
    last_check: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    consecutive_failures: int = 0
    max_failures: int = 3
    metadata: dict[str, Any] = Field(default_factory=dict)

    def record_failure(self, reason: str = "") -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_failures:
            self.status = "unhealthy"
            logger.warning(f"Health check {self.name}: unhealthy ({self.consecutive_failures} failures): {reason}")

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.status = "healthy"
        self.last_check = datetime.now(timezone.utc).isoformat()


class RecoveryAction(BaseModel):
    """A recovery action taken by the self-healer."""
    name: str
    target: str
    strategy: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "pending"
    result: Any = None

    def mark_completed(self, result: Any = None) -> None:
        self.status = "completed"
        self.result = result

    def mark_failed(self, error: str = "") -> None:
        self.status = "failed"
        self.result = {"error": error}


class SelfHealer:
    """Autonomous healing system for the digital life form.

    Monitors components, detects failures, and executes recovery actions:
    - Cell regeneration (restore from checkpoints)
    - Service restart
    - Knowledge base repair
    - Configuration rollback
    """

    def __init__(self, check_interval: float = 60.0):
        self.check_interval = check_interval
        self._checks: dict[str, HealthCheck] = {}
        self._recovery_history: list[RecoveryAction] = []
        self._strategies: dict[str, list[Callable]] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def register_check(self, name: str, check_fn: Callable,
                       recovery_strategies: list[Callable] | None = None,
                       max_failures: int = 3) -> None:
        """Register a health check with recovery strategies.

        Args:
            name: Unique check name
            check_fn: Async callable returning (bool, dict) for (healthy, metadata)
            recovery_strategies: List of async callables to try in order
            max_failures: Consecutive failures before marking unhealthy
        """
        self._checks[name] = HealthCheck(name=name, max_failures=max_failures)
        self._strategies[name] = recovery_strategies or []
        self._check_fns[name] = check_fn
        logger.info(f"Registered health check: {name}")

    async def start(self) -> None:
        """Start the continuous health monitoring loop."""
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("SelfHealer started")

    async def stop(self) -> None:
        """Stop the health monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SelfHealer stopped")

    async def run_check(self, name: str) -> HealthCheck:
        """Manually run a single health check."""
        check = self._checks.get(name)
        if not check:
            return HealthCheck(name=name, status="unknown")

        check_fn = self._check_fns.get(name)
        if not check_fn:
            return check

        try:
            healthy, metadata = await check_fn()
            if healthy:
                check.record_success()
            else:
                check.record_failure(str(metadata))
                await self._execute_recovery(name, metadata)
            check.metadata = metadata or {}
        except Exception as e:
            check.record_failure(str(e))
            await self._execute_recovery(name, {"error": str(e)})

        return check

    async def run_all_checks(self) -> dict[str, HealthCheck]:
        """Run all registered health checks."""
        results = {}
        for name in self._checks:
            results[name] = await self.run_check(name)
        return results

    async def heal_cell(self, cell: Any) -> dict[str, Any]:
        """Attempt to heal a failed cell via regeneration."""
        action = RecoveryAction(name="heal_cell", target=cell.name if hasattr(cell, 'name') else "unknown", strategy="regeneration")
        try:
            from ..cell.regen import Regen
            restored = await Regen.restore(cell)
            validation = await Regen.validate(cell)
            if restored and validation.get("genome_valid", False):
                action.mark_completed({"regenerated": True, "validation": validation})
            else:
                action.mark_failed("Regeneration failed validation")
        except Exception as e:
            action.mark_failed(str(e))
        self._recovery_history.append(action)
        return action.model_dump()

    async def _monitor_loop(self) -> None:
        """Continuous monitoring loop."""
        while self._running:
            try:
                await self.run_all_checks()
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
            await asyncio.sleep(self.check_interval)

    async def _execute_recovery(self, check_name: str, metadata: dict[str, Any]) -> None:
        """Execute recovery strategies for a failed check."""
        strategies = self._strategies.get(check_name, [])
        for i, strategy in enumerate(strategies):
            action = RecoveryAction(
                name=f"recover_{check_name}",
                target=check_name,
                strategy=f"strategy_{i}",
            )
            try:
                result = await strategy(metadata)
                action.mark_completed(result)
                logger.info(f"Recovery successful for {check_name}: strategy {i}")
                self._recovery_history.append(action)
                return
            except Exception as e:
                action.mark_failed(str(e))
                logger.warning(f"Recovery strategy {i} failed for {check_name}: {e}")
                self._recovery_history.append(action)
        logger.error(f"All recovery strategies failed for {check_name}")

    def get_status(self) -> dict[str, Any]:
        healthy = sum(1 for c in self._checks.values() if c.status == "healthy")
        unhealthy = sum(1 for c in self._checks.values() if c.status == "unhealthy")
        return {
            "running": self._running,
            "total_checks": len(self._checks),
            "healthy": healthy,
            "unhealthy": unhealthy,
            "recovery_actions": len(self._recovery_history),
        }

    _check_fns: dict[str, Callable] = {}
