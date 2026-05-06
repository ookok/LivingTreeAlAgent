"""
AutoResearchClaw sentinel watchdog
Description: Background watchdog quality monitor for LivingTreeAlAgent observability.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from collections import deque
from typing import Callable, Awaitable, List, Optional, Dict, Any
from pathlib import Path

from loguru import logger


@dataclass
class SentinelAlert:
    check_name: str
    severity: str  # one of: "info"|"warn"|"critical"
    message: str
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SentinelCheck:
    name: str
    check_fn: Callable[[], Awaitable[Optional[List[SentinelAlert]]]]
    interval_sec: float
    enabled: bool = True
    last_run: float = 0.0
    alert_count: int = 0
    consecutive_failures: int = 0


class Sentinel:
    def __init__(self) -> None:
        self.alerts: List[SentinelAlert] = []  # in-memory alerts history (max 100)
        self.checks: Dict[str, SentinelCheck] = {}
        self.alert_callbacks: List[Callable[[SentinelAlert], Any]] = []
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None

        # Register 5 default checks
        self._register_default_checks()

    # Internal default checks (async, take no args, return Optional[List[SentinelAlert]]
    async def _nan_inf_check(self) -> Optional[List[SentinelAlert]]:
        # Template: in real usage, supply data from outside. Here we return no alerts.
        return None

    async def _consistency_check(self) -> Optional[List[SentinelAlert]]:
        return None

    async def _degradation_check(self) -> Optional[List[SentinelAlert]]:
        return None

    async def _cost_anomaly_check(self) -> Optional[List[SentinelAlert]]:
        return None

    async def _latency_spike_check(self) -> Optional[List[SentinelAlert]]:
        return None

    def _register_default_checks(self) -> None:
        self.add_check("nan_inf_check", self._nan_inf_check, interval_sec=30.0)
        self.add_check("consistency_check", self._consistency_check, interval_sec=60.0)
        self.add_check("degradation_check", self._degradation_check, interval_sec=120.0)
        self.add_check("cost_anomaly_check", self._cost_anomaly_check, interval_sec=300.0)
        self.add_check("latency_spike_check", self._latency_spike_check, interval_sec=60.0)

    def add_check(self, name: str, check_fn: Callable[[], Awaitable[Optional[List[SentinelAlert]]]], interval_sec: float = 30.0) -> SentinelCheck:
        chk = SentinelCheck(name=name, check_fn=check_fn, interval_sec=float(interval_sec), enabled=True)
        self.checks[name] = chk
        return chk

    def remove_check(self, name: str) -> None:
        if name in self.checks:
            del self.checks[name]

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None

    async def run_once(self) -> List[SentinelAlert]:
        results: List[SentinelAlert] = []
        for chk in list(self.checks.values()):
            if not chk.enabled:
                continue
            try:
                alerts = await chk.check_fn()
            except Exception as e:
                alert = SentinelAlert(
                    check_name=chk.name,
                    severity="critical",
                    message=f"Exception in check: {e}",
                    timestamp=time.time(),
                    details={"exception": str(e)},
                )
                self._alert(alert)
                results.append(alert)
                chk.last_run = time.time()
                chk.consecutive_failures += 1
                continue
            now = time.time()
            chk.last_run = now
            if alerts:
                for a in alerts:
                    self._alert(a)
                results.extend(alerts)
                chk.alert_count += len(alerts) if alerts else 0
                chk.consecutive_failures = 0
            else:
                chk.consecutive_failures = 0
        return results

    def get_alerts(self, since: Optional[float] = None) -> List[SentinelAlert]:
        if since is None:
            return list(self.alerts)
        return [a for a in self.alerts if a.timestamp >= since]

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_checks": len(self.checks),
            "enabled_checks": sum(1 for c in self.checks.values() if c.enabled),
            "alerts_in_memory": len(self.alerts),
            "checks": [
                {
                    "name": c.name,
                    "last_run": c.last_run,
                    "alert_count": c.alert_count,
                    "enabled": c.enabled,
                    "interval_sec": c.interval_sec,
                }
                for c in self.checks.values()
            ],
        }

    async def _run_loop(self) -> None:
        try:
            while self._running:
                now = time.time()
                for chk in list(self.checks.values()):
                    if not chk.enabled:
                        continue
                    due = (chk.last_run == 0.0) or (now - chk.last_run >= chk.interval_sec)
                    if due:
                        await self._run_check(chk)
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    async def _run_check(self, check: SentinelCheck) -> None:
        try:
            result = await check.check_fn()
        except Exception as e:
            alert = SentinelAlert(
                check_name=check.name,
                severity="critical",
                message=f"Check raised exception: {e}",
                timestamp=time.time(),
                details={"exception": str(e)},
            )
            self._alert(alert)
            check.last_run = time.time()
            check.consecutive_failures += 1
            return
        now = time.time()
        check.last_run = now
        if result:
            check.alert_count += len(result)
            check.consecutive_failures = 0
            for a in result:
                self._alert(a)
        else:
            check.consecutive_failures = 0

    def _alert(self, alert: SentinelAlert) -> None:
        logger.info(f"[Sentinel] {alert.check_name} [{alert.severity}] {alert.message} @ {alert.timestamp}")
        self.alerts.append(alert)
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        for cb in self.alert_callbacks:
            try:
                cb(alert)
            except Exception:
                pass


# Sentinel singleton pattern
_SENTINEL_INSTANCE: Optional[Sentinel] = None

def get_sentinel() -> Sentinel:
    global _SENTINEL_INSTANCE
    if _SENTINEL_INSTANCE is None:
        _SENTINEL_INSTANCE = Sentinel()
    return _SENTINEL_INSTANCE


# Expose a default singleton for convenience
SENTINEL = get_sentinel()
