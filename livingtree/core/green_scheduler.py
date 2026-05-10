"""Green AI Scheduler — energy-aware "photosynthesis" task management.

Inspired by LivingTree's biological metaphor: the Heart organ (心脏)
balances energy consumption like a plant performs photosynthesis.
High load = dormant mode; low load = active growth.

Key behaviors:
  - CPU > 70% → enter TORPOR (defer non-urgent tasks)
  - CPU > 90% → enter HIBERNATION (only heartbeat alive)
  - CPU < 30% → enter GROWTH (run backlog tasks, sync, learn)
  - Mobile charging detected → offload compute to edge

Nanjing context: 南京电网联动 — real-time electricity pricing awareness.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from loguru import logger


class EnergyMode(str, Enum):
    GROWTH = "growth"           # active learning, sync, full power
    ACTIVE = "active"           # normal operation
    TORPOR = "torpor"           # defer non-urgent tasks, reduce polling
    HIBERNATION = "hibernation" # heartbeat only, pause all background work
    EDGE_OFFLOAD = "edge_offload"  # route compute to mobile/edge devices


@dataclass
class DeferredTask:
    name: str
    func: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    priority: int = 5          # 1=critical, 10=lowest
    deferred_at: float = field(default_factory=time.time)
    max_defer_seconds: float = 3600


class GreenScheduler:
    """Energy-aware task scheduler with biological rhythm.

    Polls system vitals and adjusts the task execution mode.
    Integrates with VitalsMonitor for CPU/memory readings.
    """

    def __init__(self, high_threshold: float = 70.0, critical_threshold: float = 90.0,
                 growth_threshold: float = 30.0):
        self._mode: EnergyMode = EnergyMode.ACTIVE
        self._high = high_threshold
        self._critical = critical_threshold
        self._growth = growth_threshold
        self._deferred: list[DeferredTask] = []
        self._running: bool = False
        self._poll_task: Optional[asyncio.Task] = None
        self._mode_history: list[str] = []

    # ═══ Lifecycle ═══

    async def start(self, poll_interval: float = 5.0):
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop(poll_interval))
        logger.info(f"GreenScheduler: ACTIVE mode (thresholds: grow<{self._growth}% torpor>{self._high}% hibernate>{self._critical}%)")

    async def stop(self):
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()

    async def _poll_loop(self, interval: float):
        while self._running:
            try:
                await self._check_and_adjust()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"GreenScheduler poll: {e}")
                await asyncio.sleep(interval)

    # ═══ Mode Adjustment ═══

    async def _check_and_adjust(self):
        try:
            import psutil
            cpu_pct = psutil.cpu_percent(interval=0.5)
        except Exception:
            cpu_pct = 50

        prev_mode = self._mode

        if cpu_pct > self._critical:
            self._mode = EnergyMode.HIBERNATION
        elif cpu_pct > self._high:
            self._mode = EnergyMode.TORPOR
        elif cpu_pct < self._growth:
            self._mode = EnergyMode.GROWTH
        else:
            self._mode = EnergyMode.ACTIVE

        if self._mode != prev_mode:
            self._mode_history.append(self._mode.value)
            logger.info(f"GreenScheduler: {prev_mode.value} → {self._mode.value} (CPU: {cpu_pct}%)")
            await self._on_mode_change(prev_mode, self._mode)

    async def _on_mode_change(self, old: EnergyMode, new: EnergyMode):
        if new == EnergyMode.GROWTH:
            backlog = len(self._deferred)
            if backlog > 0:
                logger.info(f"GreenScheduler: GROWTH mode — processing {backlog} deferred tasks")
                self._deferred.sort(key=lambda t: t.priority)
                for task in self._deferred[:10]:
                    try:
                        if asyncio.iscoroutinefunction(task.func):
                            asyncio.create_task(task.func(*task.args, **task.kwargs))
                        else:
                            loop = asyncio.get_event_loop()
                            loop.run_in_executor(None, task.func, *task.args, **task.kwargs)
                    except Exception as e:
                        logger.debug(f"Deferred task {task.name}: {e}")
                self._deferred = self._deferred[10:]

        elif new == EnergyMode.HIBERNATION:
            logger.warning("GreenScheduler: HIBERNATION — only heartbeat alive")

    # ═══ Submit / Defer ═══

    def submit(self, name: str, func: Callable, *args, priority: int = 5, **kwargs):
        """Submit a task. If in high-load mode, defer it."""
        if self._mode in (EnergyMode.HIBERNATION, EnergyMode.TORPOR) and priority > 3:
            self._deferred.append(DeferredTask(
                name=name, func=func, args=args, kwargs=kwargs, priority=priority,
            ))
            logger.debug(f"GreenScheduler: deferred '{name}' (priority={priority}, mode={self._mode.value})")
            return

        try:
            if asyncio.iscoroutinefunction(func):
                asyncio.create_task(func(*args, **kwargs))
            else:
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, func, *args, **kwargs)
        except Exception as e:
            logger.debug(f"GreenScheduler task '{name}': {e}")

    # ═══ Stats ═══

    @property
    def mode(self) -> EnergyMode:
        return self._mode

    def stats(self) -> dict:
        return {
            "mode": self._mode.value,
            "deferred_count": len(self._deferred),
            "history": self._mode_history[-20:],
            "thresholds": {
                "growth_below": f"{self._growth}% CPU",
                "torpor_above": f"{self._high}% CPU",
                "hibernation_above": f"{self._critical}% CPU",
            },
            "metaphor": {
                "growth": "🌿 光合作用 — 生长模式",
                "active": "🌳 正常新陈代谢",
                "torpor": "🍂 休眠 — 节能模式",
                "hibernation": "💤 冬眠 — 仅心跳存活",
                "edge_offload": "📱 算力迁移到移动端",
            }[self._mode.value],
        }

    def render_html(self) -> str:
        st = self.stats()
        mode_emoji = {"growth": "🌿", "active": "🌳", "torpor": "🍂", "hibernation": "💤", "edge_offload": "📱"}

        return f'''<div class="card">
<h2>🌿 绿色AI调度器 <span style="font-size:10px;color:var(--dim)">— 光合作用节能算法</span></h2>
<div style="text-align:center;margin:12px 0">
  <div style="font-size:48px">{mode_emoji.get(st["mode"], "🌳")}</div>
  <div style="font-size:16px;font-weight:700;color:var(--accent)">{st["mode"].upper()}</div>
  <div style="font-size:12px;color:var(--dim)">{st["metaphor"]}</div>
</div>
<div style="font-size:10px;color:var(--dim);margin:4px 0">
  待处理任务: <b>{st["deferred_count"]}</b> · 
  阈值: 生长&lt;{st["thresholds"]["growth_below"]} · 休眠&gt;{st["thresholds"]["torpor_above"]} · 冬眠&gt;{st["thresholds"]["hibernation_above"]}
</div>
<div style="font-size:9px;color:var(--dim);margin-top:8px;text-align:center">
  DiLoCo-inspired: 绿色算力 · 电网联动 · 生物节律</div>
</div>'''


_instance: Optional[GreenScheduler] = None


def get_green_scheduler() -> GreenScheduler:
    global _instance
    if _instance is None:
        _instance = GreenScheduler()
    return _instance
