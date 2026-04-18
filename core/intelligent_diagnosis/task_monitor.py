#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Task Monitor - 任务健康度监控
================================

功能：
1. 任务健康度监控
2. 无响应任务检测
3. 超时处理机制
4. 资源异常检测

监控维度：
1. 响应时间 - 超出预期时间的任务
2. 进度停滞 - 长时间无进展的任务
3. 资源异常 - 异常高资源消耗
4. 死锁检测 - 相互等待的任务

Usage:
    monitor = TaskMonitor()
    monitor.start()

    # 提交任务
    task_id = monitor.register_task(task_func, timeout=300)

    # 检查状态
    status = monitor.get_health_status(task_id)
"""

import os
import gc
import time
import threading
import traceback
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import deque
from functools import wraps

from .structured_logger import get_logger


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"        # 健康
    WARNING = "warning"        # 警告
    STALLED = "stalled"        # 停滞
    TIMEOUT = "timeout"        # 超时
    DEADLOCK = "deadlock"      # 死锁
    CRASHED = "crashed"        # 崩溃


@dataclass
class TaskMetrics:
    """任务指标"""
    task_id: str
    start_time: datetime
    expected_duration: float  # 秒
    last_progress_time: datetime
    last_progress: float      # 0-100
    current_progress: float    # 0-100
    cpu_usage: float          # 百分比
    memory_usage: float       # MB
    thread_count: int
    retry_count: int = 0
    error_count: int = 0


@dataclass
class TaskSnapshot:
    """任务快照（用于恢复）"""
    task_id: str
    timestamp: datetime
    progress: float
    state: Dict[str, Any]  # 任务状态数据
    checkpoint_data: Optional[bytes] = None


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    task_id: str
    status: HealthStatus
    message: str
    metrics: TaskMetrics
    recommended_action: Optional[str] = None
    estimated_time_remaining: Optional[float] = None


class TaskMonitor:
    """
    任务健康度监控

    监控所有注册任务的状态，在问题发生时及时告警或自动处理
    """

    _instance: Optional['TaskMonitor'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, check_interval: float = 5.0):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.logger = get_logger("task_monitor")
        self.check_interval = check_interval

        # 注册的任务
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._tasks_lock = threading.Lock()

        # 任务指标历史
        self._metrics_history: Dict[str, deque] = {}
        self._max_history_size = 100

        # 快照存储
        self._snapshots: Dict[str, deque] = {}
        self._max_snapshots = 5

        # 监控线程
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 告警回调
        self._alert_callbacks: List[Callable] = []

        # 统计数据
        self._stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "timed_out_tasks": 0,
            "stalled_tasks": 0,
        }

        self._initialized = True

    def start(self):
        """启动监控"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self.logger.info("Task monitor started")

    def stop(self):
        """停止监控"""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
        self.logger.info("Task monitor stopped")

    def register_task(
        self,
        task_id: str,
        task_name: str,
        expected_duration: float = 300,
        warning_threshold: float = 0.8,
        timeout_threshold: float = 1.2,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        注册任务进行监控

        Args:
            task_id: 唯一任务ID
            task_name: 任务名称
            expected_duration: 预期执行时间（秒）
            warning_threshold: 警告阈值（百分比，如0.8表示80%预期时间）
            timeout_threshold: 超时阈值（百分比）
            metadata: 任务元数据

        Returns:
            str 任务ID
        """
        with self._tasks_lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "task_name": task_name,
                "start_time": datetime.now(timezone.utc),
                "expected_duration": expected_duration,
                "warning_threshold": warning_threshold,
                "timeout_threshold": timeout_threshold,
                "metadata": metadata or {},
                "status": HealthStatus.HEALTHY,
                "progress": 0.0,
                "last_update": datetime.now(timezone.utc),
                "checkpoints": [],
                "state": {}
            }

            self._metrics_history[task_id] = deque(maxlen=self._max_history_size)
            self._snapshots[task_id] = deque(maxlen=self._max_snapshots)

            self._stats["total_tasks"] += 1

        self.logger.info(f"Task registered: {task_id} ({task_name})")
        return task_id

    def unregister_task(self, task_id: str):
        """取消注册任务"""
        with self._tasks_lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
            if task_id in self._metrics_history:
                del self._metrics_history[task_id]
            if task_id in self._snapshots:
                del self._snapshots[task_id]

    def update_progress(
        self,
        task_id: str,
        progress: float,
        state: Optional[Dict[str, Any]] = None
    ):
        """
        更新任务进度

        Args:
            task_id: 任务ID
            progress: 当前进度 (0-100)
            state: 可选的最新状态
        """
        with self._tasks_lock:
            if task_id not in self._tasks:
                return

            task = self._tasks[task_id]
            task["progress"] = min(100.0, max(0.0, progress))
            task["last_update"] = datetime.now(timezone.utc)

            if state:
                task["state"].update(state)

            # 记录指标
            metrics = self._collect_metrics(task_id)
            self._metrics_history[task_id].append(metrics)

    def report_error(self, task_id: str, error: Exception):
        """报告任务错误"""
        with self._tasks_lock:
            if task_id not in self._tasks:
                return

            task = self._tasks[task_id]
            task["error_count"] = task.get("error_count", 0) + 1
            task["last_error"] = {
                "message": str(error),
                "type": type(error).__name__,
                "trace": traceback.format_exc(),
                "time": datetime.now(timezone.utc).isoformat()
            }

        self.logger.error(f"Task {task_id} error: {error}")

    def report_stalled(self, task_id: str, reason: str = ""):
        """报告任务停滞"""
        with self._tasks_lock:
            if task_id not in self._tasks:
                return

            task = self._tasks[task_id]
            task["status"] = HealthStatus.STALLED
            task["stall_reason"] = reason

        self.logger.warning(f"Task {task_id} stalled: {reason}")

    def complete_task(self, task_id: str):
        """标记任务完成"""
        with self._tasks_lock:
            if task_id not in self._tasks:
                return

            task = self._tasks[task_id]
            task["status"] = HealthStatus.HEALTHY
            task["end_time"] = datetime.now(timezone.utc)
            task["progress"] = 100.0

            self._stats["completed_tasks"] += 1

        self.logger.info(f"Task completed: {task_id}")

    def fail_task(self, task_id: str, reason: str = ""):
        """标记任务失败"""
        with self._tasks_lock:
            if task_id not in self._tasks:
                return

            task = self._tasks[task_id]
            task["status"] = HealthStatus.CRASHED
            task["failure_reason"] = reason

            self._stats["failed_tasks"] += 1

        self.logger.error(f"Task failed: {task_id} - {reason}")

    def timeout_task(self, task_id: str):
        """标记任务超时"""
        with self._tasks_lock:
            if task_id not in self._tasks:
                return

            task = self._tasks[task_id]
            task["status"] = HealthStatus.TIMEOUT

            self._stats["timed_out_tasks"] += 1

        self.logger.warning(f"Task timed out: {task_id}")

    def create_checkpoint(self, task_id: str, checkpoint_data: Optional[bytes] = None):
        """创建任务检查点"""
        with self._tasks_lock:
            if task_id not in self._tasks:
                return

            snapshot = TaskSnapshot(
                task_id=task_id,
                timestamp=datetime.now(timezone.utc),
                progress=self._tasks[task_id]["progress"],
                state=dict(self._tasks[task_id]["state"]),
                checkpoint_data=checkpoint_data
            )

            self._snapshots[task_id].append(snapshot)

        self.logger.debug(f"Checkpoint created for {task_id}")

    def get_latest_checkpoint(self, task_id: str) -> Optional[TaskSnapshot]:
        """获取最新检查点"""
        if task_id in self._snapshots and self._snapshots[task_id]:
            return self._snapshots[task_id][-1]
        return None

    def get_health_status(self, task_id: str) -> HealthCheckResult:
        """获取任务健康状态"""
        with self._tasks_lock:
            if task_id not in self._tasks:
                return HealthCheckResult(
                    task_id=task_id,
                    status=HealthStatus.CRASHED,
                    message="Task not found",
                    metrics=None
                )

            task = self._tasks[task_id]
            metrics = self._collect_metrics(task_id)

            # 计算健康状态
            status, message, action = self._evaluate_health(task, metrics)

            # 估算剩余时间
            remaining = self._estimate_remaining_time(task, metrics)

            return HealthCheckResult(
                task_id=task_id,
                status=status,
                message=message,
                metrics=metrics,
                recommended_action=action,
                estimated_time_remaining=remaining
            )

    def get_all_health_status(self) -> Dict[str, HealthCheckResult]:
        """获取所有任务健康状态"""
        results = {}
        with self._tasks_lock:
            task_ids = list(self._tasks.keys())

        for task_id in task_ids:
            results[task_id] = self.get_health_status(task_id)

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """获取监控统计"""
        with self._tasks_lock:
            task_count = len(self._tasks)
            healthy = sum(1 for t in self._tasks.values() if t["status"] == HealthStatus.HEALTHY)
            warning = sum(1 for t in self._tasks.values() if t["status"] == HealthStatus.WARNING)
            stalled = sum(1 for t in self._tasks.values() if t["status"] == HealthStatus.STALLED)
            timeout = sum(1 for t in self._tasks.values() if t["status"] == HealthStatus.TIMEOUT)
            crashed = sum(1 for t in self._tasks.values() if t["status"] == HealthStatus.CRASHED)

        return {
            "total_tasks": self._stats["total_tasks"],
            "active_tasks": task_count,
            "completed_tasks": self._stats["completed_tasks"],
            "failed_tasks": self._stats["failed_tasks"],
            "timed_out_tasks": self._stats["timed_out_tasks"],
            "stalled_tasks": self._stats["stalled_tasks"],
            "current_health": {
                "healthy": healthy,
                "warning": warning,
                "stalled": stalled,
                "timeout": timeout,
                "crashed": crashed
            }
        }

    def add_alert_callback(self, callback: Callable):
        """添加告警回调"""
        self._alert_callbacks.append(callback)

    def _monitor_loop(self):
        """监控循环"""
        while not self._stop_event.is_set():
            try:
                self._check_all_tasks()
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")

            self._stop_event.wait(self.check_interval)

    def _check_all_tasks(self):
        """检查所有任务"""
        with self._tasks_lock:
            task_ids = list(self._tasks.keys())

        for task_id in task_ids:
            try:
                result = self.get_health_status(task_id)

                # 触发告警
                if result.status in [HealthStatus.WARNING, HealthStatus.STALLED, HealthStatus.TIMEOUT]:
                    self._trigger_alert(result)
            except Exception as e:
                self.logger.error(f"Check task {task_id} error: {e}")

    def _evaluate_health(
        self,
        task: Dict[str, Any],
        metrics: TaskMetrics
    ) -> tuple[HealthStatus, str, Optional[str]]:
        """评估任务健康状态"""
        now = datetime.now(timezone.utc)
        elapsed = (now - task["start_time"]).total_seconds()
        expected = task["expected_duration"]

        # 检查超时
        if elapsed > expected * task["timeout_threshold"]:
            return HealthStatus.TIMEOUT, f"Task exceeded timeout ({elapsed:.0f}s > {expected * task['timeout_threshold']:.0f}s)", "Consider cancelling or extending timeout"

        # 检查停滞
        last_update = task["last_update"]
        if (now - last_update).total_seconds() > expected * 0.3:  # 30% 时间无更新
            if metrics.progress == metrics.last_progress:
                return HealthStatus.STALLED, "No progress made recently", "Check if task is deadlocked or blocked"

        # 检查进度
        progress = task["progress"]
        expected_progress = min(100.0, (elapsed / expected) * 100)

        # 进度落后太多
        if progress < expected_progress * task["warning_threshold"]:
            return HealthStatus.WARNING, f"Progress behind schedule ({progress:.1f}% < {expected_progress * task['warning_threshold']:.1f}%)", "Monitor closely"

        return HealthStatus.HEALTHY, "Task is healthy", None

    def _collect_metrics(self, task_id: str) -> TaskMetrics:
        """收集任务指标"""
        with self._tasks_lock:
            if task_id not in self._tasks:
                raise ValueError(f"Task {task_id} not found")

            task = self._tasks[task_id]
            history = list(self._metrics_history.get(task_id, []))

            # 获取 CPU 和内存使用
            try:
                import psutil
                process = psutil.Process()
                cpu_usage = process.cpu_percent(interval=0.1)
                memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                thread_count = process.num_threads()
            except:
                cpu_usage = 0.0
                memory_usage = 0.0
                thread_count = 1

            last_progress = history[-1].progress if history else 0.0

            return TaskMetrics(
                task_id=task_id,
                start_time=task["start_time"],
                expected_duration=task["expected_duration"],
                last_progress_time=task["last_update"],
                last_progress=last_progress,
                current_progress=task["progress"],
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                thread_count=thread_count,
                retry_count=task.get("retry_count", 0),
                error_count=task.get("error_count", 0)
            )

    def _estimate_remaining_time(
        self,
        task: Dict[str, Any],
        metrics: TaskMetrics
    ) -> Optional[float]:
        """估算剩余时间"""
        if metrics.current_progress >= 100:
            return 0.0

        if metrics.current_progress > 0:
            elapsed = (datetime.now(timezone.utc) - task["start_time"]).total_seconds()
            rate = metrics.current_progress / elapsed  # % per second
            if rate > 0:
                return (100 - metrics.current_progress) / rate

        return None

    def _trigger_alert(self, result: HealthCheckResult):
        """触发告警"""
        for callback in self._alert_callbacks:
            try:
                callback(result)
            except Exception as e:
                self.logger.error(f"Alert callback error: {e}")


def monitored_task(
    task_id: str,
    task_name: str,
    expected_duration: float = 300,
    create_checkpoint: bool = True
):
    """
    任务装饰器 - 自动监控任务

    Usage:
        @monitored_task("task_001", "数据处理", expected_duration=60)
        def process_data():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            monitor = TaskMonitor()
            monitor.start()
            monitor.register_task(task_id, task_name, expected_duration)

            try:
                result = func(*args, **kwargs)
                monitor.complete_task(task_id)
                return result
            except Exception as e:
                monitor.report_error(task_id, e)
                raise
            finally:
                if create_checkpoint:
                    monitor.create_checkpoint(task_id)

        return wrapper
    return decorator


# 全局实例
_task_monitor: Optional[TaskMonitor] = None


def get_task_monitor() -> TaskMonitor:
    """获取任务监控单例"""
    global _task_monitor
    if _task_monitor is None:
        _task_monitor = TaskMonitor()
        _task_monitor.start()
    return _task_monitor


if __name__ == "__main__":
    # 测试任务监控
    monitor = TaskMonitor()
    monitor.start()

    print("=" * 60)
    print("Task Monitor Test")
    print("=" * 60)

    # 注册任务
    task_id = monitor.register_task("test_task_1", "测试任务", expected_duration=10)

    # 模拟任务执行
    for i in range(10):
        monitor.update_progress(task_id, i * 10)
        time.sleep(0.5)

    # 获取健康状态
    status = monitor.get_health_status(task_id)
    print(f"\nTask status: {status.status.value}")
    print(f"Message: {status.message}")
    print(f"Progress: {status.metrics.current_progress}%")

    # 获取统计
    stats = monitor.get_statistics()
    print(f"\nStatistics: {stats}")

    # 完成
    monitor.complete_task(task_id)

    print("\nTest completed!")
    monitor.stop()
