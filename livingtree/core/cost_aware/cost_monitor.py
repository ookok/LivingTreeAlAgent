"""
CostMonitor - 成本监控器

实现成本认知系统的第三层：成本监控
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import time
import threading


class MonitorStatus(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    STOPPED = "stopped"


class CostMetrics:
    def __init__(self):
        self.money_spent_usd = 0.0
        self.money_budget_usd = 0.0
        self.time_spent_seconds = 0.0
        self.time_budget_seconds = 0.0
        self.space_used_mb = 0.0
        self.space_budget_mb = 0.0
        self.api_calls = 0
        self.l4_calls = 0
        self.steps_completed = 0


class CostMonitor:

    def __init__(self):
        self._logger = logger.bind(component="CostMonitor")
        self._status: Dict[str, MonitorStatus] = {}
        self._metrics: Dict[str, CostMetrics] = {}
        self._on_fuse_callbacks: List[callable] = []
        self._monitor_threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._logger.info("✅ CostMonitor 初始化完成")

    def start_monitoring(self, session_id: str, budget_usd: float,
                        time_budget_seconds: float = 600,
                        space_budget_mb: float = 1000):
        self._metrics[session_id] = CostMetrics()
        self._metrics[session_id].money_budget_usd = budget_usd
        self._metrics[session_id].time_budget_seconds = time_budget_seconds
        self._metrics[session_id].space_budget_mb = space_budget_mb
        self._status[session_id] = MonitorStatus.NORMAL
        self._stop_events[session_id] = threading.Event()
        monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(session_id,),
            daemon=True
        )
        self._monitor_threads[session_id] = monitor_thread
        monitor_thread.start()
        self._logger.debug(f"🔍 开始监控: {session_id}, 预算: ${budget_usd}")

    def _monitor_loop(self, session_id: str):
        stop_event = self._stop_events[session_id]
        while not stop_event.is_set():
            metrics = self._metrics.get(session_id)
            if not metrics:
                break
            self._check_money_budget(session_id, metrics)
            self._check_time_budget(session_id, metrics)
            self._check_space_budget(session_id, metrics)
            if self._status[session_id] == MonitorStatus.CRITICAL:
                self._trigger_fuse(session_id)
                break
            stop_event.wait(1.0)

    def _check_money_budget(self, session_id: str, metrics: CostMetrics):
        if metrics.money_budget_usd <= 0:
            return
        ratio = metrics.money_spent_usd / metrics.money_budget_usd
        if ratio >= 1.0:
            self._status[session_id] = MonitorStatus.CRITICAL
            self._logger.warning(f"🔥 金钱成本超预算: {session_id}")
        elif ratio >= 0.8:
            if self._status[session_id] == MonitorStatus.NORMAL:
                self._status[session_id] = MonitorStatus.WARNING
                self._logger.warning(f"⚠️ 金钱成本接近预算上限: {session_id}, 已消耗 {ratio:.0%}")

    def _check_time_budget(self, session_id: str, metrics: CostMetrics):
        if metrics.time_budget_seconds <= 0:
            return
        ratio = metrics.time_spent_seconds / metrics.time_budget_seconds
        if ratio >= 1.0:
            self._status[session_id] = MonitorStatus.CRITICAL
            self._logger.warning(f"🔥 时间成本超预算: {session_id}")
        elif ratio >= 0.8:
            if self._status[session_id] == MonitorStatus.NORMAL:
                self._status[session_id] = MonitorStatus.WARNING
                self._logger.warning(f"⚠️ 时间成本接近预算上限: {session_id}, 已耗时 {ratio:.0%}")

    def _check_space_budget(self, session_id: str, metrics: CostMetrics):
        if metrics.space_budget_mb <= 0:
            return
        ratio = metrics.space_used_mb / metrics.space_budget_mb
        if ratio >= 1.0:
            self._status[session_id] = MonitorStatus.CRITICAL
            self._logger.warning(f"🔥 空间成本超预算: {session_id}")
        elif ratio >= 0.8:
            if self._status[session_id] == MonitorStatus.NORMAL:
                self._status[session_id] = MonitorStatus.WARNING
                self._logger.warning(f"⚠️ 空间成本接近预算上限: {session_id}, 已使用 {ratio:.0%}")

    def _trigger_fuse(self, session_id: str):
        self._status[session_id] = MonitorStatus.STOPPED
        self._logger.error(f"🔴 触发熔断: {session_id}")
        for callback in self._on_fuse_callbacks:
            try:
                callback(session_id)
            except Exception as e:
                self._logger.error(f"熔断回调失败: {e}")

    def stop_monitoring(self, session_id: str):
        if session_id in self._stop_events:
            self._stop_events[session_id].set()
        if session_id in self._monitor_threads:
            self._monitor_threads[session_id].join(timeout=5.0)
        self._logger.debug(f"⏹️ 停止监控: {session_id}")

    def record_spending(self, session_id: str, amount_usd: float):
        if session_id in self._metrics:
            self._metrics[session_id].money_spent_usd += amount_usd

    def record_time(self, session_id: str, seconds: float):
        if session_id in self._metrics:
            self._metrics[session_id].time_spent_seconds += seconds

    def record_space(self, session_id: str, mb: float):
        if session_id in self._metrics:
            self._metrics[session_id].space_used_mb += mb

    def record_api_call(self, session_id: str, is_l4: bool = False):
        if session_id in self._metrics:
            self._metrics[session_id].api_calls += 1
            if is_l4:
                self._metrics[session_id].l4_calls += 1

    def record_step(self, session_id: str):
        if session_id in self._metrics:
            self._metrics[session_id].steps_completed += 1

    def get_status(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self._status:
            return {"error": "未找到会话"}
        metrics = self._metrics.get(session_id)
        return {
            "session_id": session_id,
            "status": self._status[session_id].value,
            "money": {
                "spent": metrics.money_spent_usd if metrics else 0.0,
                "budget": metrics.money_budget_usd if metrics else 0.0,
                "ratio": (metrics.money_spent_usd / metrics.money_budget_usd * 100) if metrics and metrics.money_budget_usd > 0 else 0.0
            },
            "time": {
                "spent": metrics.time_spent_seconds if metrics else 0.0,
                "budget": metrics.time_budget_seconds if metrics else 0.0,
                "ratio": (metrics.time_spent_seconds / metrics.time_budget_seconds * 100) if metrics and metrics.time_budget_seconds > 0 else 0.0
            },
            "space": {
                "used": metrics.space_used_mb if metrics else 0.0,
                "budget": metrics.space_budget_mb if metrics else 0.0,
                "ratio": (metrics.space_used_mb / metrics.space_budget_mb * 100) if metrics and metrics.space_budget_mb > 0 else 0.0
            },
            "calls": {
                "api": metrics.api_calls if metrics else 0,
                "l4": metrics.l4_calls if metrics else 0,
                "steps": metrics.steps_completed if metrics else 0
            }
        }

    def register_fuse_callback(self, callback: callable):
        self._on_fuse_callbacks.append(callback)

    def is_running(self, session_id: str) -> bool:
        return session_id in self._status and self._status[session_id] != MonitorStatus.STOPPED


cost_monitor = CostMonitor()


def get_cost_monitor() -> CostMonitor:
    return cost_monitor
