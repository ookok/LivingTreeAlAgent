"""
ResourceMonitor - 自适应资源调度器
让系统稳如老狗，7×24 小时稳定运行

核心能力：
- psutil 实时监控（CPU/内存/磁盘/网络）
- 动态限流（CPU > 85% 暂停非关键任务）
- 阈值告警（可配置）
- PyQt 状态栏集成
- 后台任务调度优化

监控指标：
- CPU 使用率（%）
- 内存 RSS（MB）
- 磁盘读写速度（MB/s）
- 网络 IO（可选）
- GPU 使用率（如果有）
"""

import time
import threading
import statistics
from dataclasses import dataclass, field
from typing import Callable, Optional, TypedDict
from enum import Enum

from core.logger import get_logger

logger = get_logger('resource_monitor')
from datetime import datetime

# psutil 依赖
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class LoadLevel(Enum):
    """系统负载等级"""
    IDLE = "idle"      # 空闲
    LIGHT = "light"    # 轻度
    MODERATE = "moderate"  # 中度
    HEAVY = "heavy"    # 重度
    CRITICAL = "critical"  # 危险

    @classmethod
    def from_cpu(cls, cpu_percent: float) -> "LoadLevel":
        if cpu_percent < 20:
            return cls.IDLE
        elif cpu_percent < 50:
            return cls.LIGHT
        elif cpu_percent < 70:
            return cls.MODERATE
        elif cpu_percent < 85:
            return cls.HEAVY
        else:
            return cls.CRITICAL


@dataclass
class ResourceSnapshot:
    """资源快照"""
    timestamp: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_read_mbps: float = 0.0
    disk_write_mbps: float = 0.0
    network_sent_mbps: float = 0.0
    network_recv_mbps: float = 0.0
    gpu_percent: float = -1.0  # -1 表示无 GPU
    gpu_memory_mb: float = 0.0

    def get_load_level(self) -> LoadLevel:
        return LoadLevel.from_cpu(self.cpu_percent)

    def to_dict(self) -> dict:
        d = {
            "timestamp": self.timestamp,
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "memory_percent": self.memory_percent,
            "load_level": self.get_load_level().value,
        }
        if self.disk_read_mbps > 0:
            d["disk_read_mbps"] = self.disk_read_mbps
        if self.disk_write_mbps > 0:
            d["disk_write_mbps"] = self.disk_write_mbps
        if self.gpu_percent >= 0:
            d["gpu_percent"] = self.gpu_percent
            d["gpu_memory_mb"] = self.gpu_memory_mb
        return d


class Thresholds(TypedDict):
    """阈值配置"""
    cpu_warning: float
    cpu_critical: float
    memory_warning: float
    memory_critical: float
    disk_warning: float
    disk_critical: float


@dataclass
class Alert:
    """告警"""
    level: str
    metric: str
    value: float
    threshold: float
    message: str
    timestamp: float = field(default_factory=time.time)


class ResourceMonitor:
    """
    自适应资源调度器

    每 N 秒采样一次系统资源，根据负载动态调整任务调度
    """

    DEFAULT_THRESHOLDS = Thresholds(
        cpu_warning=70.0,
        cpu_critical=85.0,
        memory_warning=8192.0,
        memory_critical=16384.0,
        disk_warning=30.0,
        disk_critical=50.0,
    )

    PRIORITY_LIMITS = {
        "critical": 100.0,
        "high": 90.0,
        "normal": 80.0,
        "low": 60.0,
    }

    def __init__(
        self,
        interval: float = 5.0,
        thresholds: Optional[Thresholds] = None,
        history_size: int = 60,
    ):
        self.interval = interval
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self.history_size = history_size

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        self._snapshots: list[ResourceSnapshot] = []
        self._current_snapshot: Optional[ResourceSnapshot] = None

        self._active_tasks: dict[str, float] = {}
        self._task_history: list[dict] = []

        self._alert_callbacks: list[Callable[[Alert], None]] = []
        self._load_callbacks: list[Callable[[LoadLevel], None]] = []
        self._last_load: Optional[LoadLevel] = None

        self._max_parallel_tasks = 3
        self._auto_throttle = True

        self._gpu_available = False
        self._init_gpu()

    def _init_gpu(self):
        """初始化 GPU 监控"""
        try:
            import GPUtil
            self._gpu_available = True
            logger.info("✓ GPU 监控已启用")
        except ImportError:
            try:
                import pynvml
                pynvml.nvmlInit()
                self._gpu_available = True
                logger.info("✓ NVIDIA GPU 监控已启用")
            except (ImportError, Exception):
                self._gpu_available = False

    def start(self):
        """启动监控线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(f"✓ 资源监控已启动 (interval={self.interval}s)")

    def stop(self):
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("✓ 资源监控已停止")

    def _monitor_loop(self):
        """监控循环"""
        prev_disk_io = psutil.disk_io_counters() if PSUTIL_AVAILABLE else None
        prev_net_io = psutil.net_io_counters() if PSUTIL_AVAILABLE else None

        while self._running:
            try:
                snapshot = self._take_snapshot(prev_disk_io, prev_net_io)
                prev_disk_io = psutil.disk_io_counters() if PSUTIL_AVAILABLE else None
                prev_net_io = psutil.net_io_counters() if PSUTIL_AVAILABLE else None

                with self._lock:
                    self._current_snapshot = snapshot
                    self._snapshots.append(snapshot)
                    if len(self._snapshots) > self.history_size:
                        self._snapshots.pop(0)
                    self._check_alerts(snapshot)
                    load = snapshot.get_load_level()
                    if load != self._last_load:
                        self._last_load = load
                        self._notify_load_change(load)
                    if self._auto_throttle:
                        self._adjust_thresholds(snapshot)

                time.sleep(self.interval)

            except Exception as e:
                logger.info(f"⚠️ 监控采样失败: {e}")
                time.sleep(self.interval)

    def _take_snapshot(
        self,
        prev_disk: Optional[object] = None,
        prev_net: Optional[object] = None,
    ) -> ResourceSnapshot:
        """采集资源快照"""
        if not PSUTIL_AVAILABLE:
            return ResourceSnapshot(
                timestamp=time.time(),
                cpu_percent=0.0,
                memory_mb=0.0,
                memory_percent=0.0,
            )

        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        memory_mb = mem.used / (1024 * 1024)

        disk_read_mbps = 0.0
        disk_write_mbps = 0.0
        if prev_disk:
            disk = psutil.disk_io_counters()
            read_bytes = disk.read_bytes - prev_disk.read_bytes
            write_bytes = disk.write_bytes - prev_disk.write_bytes
            disk_read_mbps = (read_bytes / (1024 * 1024)) / self.interval
            disk_write_mbps = (write_bytes / (1024 * 1024)) / self.interval

        net_sent_mbps = 0.0
        net_recv_mbps = 0.0
        if prev_net:
            net = psutil.net_io_counters()
            sent_bytes = net.bytes_sent - prev_net.bytes_sent
            recv_bytes = net.bytes_recv - prev_net.bytes_recv
            net_sent_mbps = (sent_bytes / (1024 * 1024)) / self.interval
            net_recv_mbps = (recv_bytes / (1024 * 1024)) / self.interval

        gpu_percent = -1.0
        gpu_memory_mb = 0.0
        if self._gpu_available:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    gpu_percent = gpu.load * 100
                    gpu_memory_mb = gpu.memoryUsed
            except Exception:
                pass

        return ResourceSnapshot(
            timestamp=time.time(),
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            memory_percent=mem.percent,
            disk_read_mbps=disk_read_mbps,
            disk_write_mbps=disk_write_mbps,
            network_sent_mbps=net_sent_mbps,
            network_recv_mbps=net_recv_mbps,
            gpu_percent=gpu_percent,
            gpu_memory_mb=gpu_memory_mb,
        )

    def _check_alerts(self, snapshot: ResourceSnapshot):
        """检查告警条件"""
        alerts = []

        if snapshot.cpu_percent >= self.thresholds["cpu_critical"]:
            alerts.append(Alert(
                level="critical",
                metric="cpu",
                value=snapshot.cpu_percent,
                threshold=self.thresholds["cpu_critical"],
                message=f"CPU 使用率危险: {snapshot.cpu_percent:.1f}%",
            ))
        elif snapshot.cpu_percent >= self.thresholds["cpu_warning"]:
            alerts.append(Alert(
                level="warning",
                metric="cpu",
                value=snapshot.cpu_percent,
                threshold=self.thresholds["cpu_warning"],
                message=f"CPU 使用率偏高: {snapshot.cpu_percent:.1f}%",
            ))

        if snapshot.memory_mb >= self.thresholds["memory_critical"]:
            alerts.append(Alert(
                level="critical",
                metric="memory",
                value=snapshot.memory_mb,
                threshold=self.thresholds["memory_critical"],
                message=f"内存使用危险: {snapshot.memory_mb / 1024:.1f} GB",
            ))
        elif snapshot.memory_mb >= self.thresholds["memory_warning"]:
            alerts.append(Alert(
                level="warning",
                metric="memory",
                value=snapshot.memory_mb,
                threshold=self.thresholds["memory_warning"],
                message=f"内存使用偏高: {snapshot.memory_mb / 1024:.1f} GB",
            ))

        if snapshot.disk_write_mbps >= self.thresholds["disk_critical"]:
            alerts.append(Alert(
                level="warning",
                metric="disk_write",
                value=snapshot.disk_write_mbps,
                threshold=self.thresholds["disk_critical"],
                message=f"磁盘写入过高: {snapshot.disk_write_mbps:.1f} MB/s",
            ))

        for alert in alerts:
            self._notify_alert(alert)

    def _adjust_thresholds(self, snapshot: ResourceSnapshot):
        """动态调整"""
        load = snapshot.get_load_level()
        if load == LoadLevel.CRITICAL:
            self._max_parallel_tasks = 1
        elif load == LoadLevel.HEAVY:
            self._max_parallel_tasks = 2
        elif load == LoadLevel.MODERATE:
            self._max_parallel_tasks = 3
        else:
            self._max_parallel_tasks = 5

    def _notify_alert(self, alert: Alert):
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.info(f"⚠️ 告警回调失败: {e}")

    def _notify_load_change(self, load: LoadLevel):
        for callback in self._load_callbacks:
            try:
                callback(load)
            except Exception as e:
                logger.info(f"⚠️ 负载回调失败: {e}")

    def get_current_snapshot(self) -> Optional[ResourceSnapshot]:
        with self._lock:
            return self._current_snapshot

    def get_load_level(self) -> LoadLevel:
        snapshot = self.get_current_snapshot()
        return snapshot.get_load_level() if snapshot else LoadLevel.IDLE

    def get_average_load(self, duration_seconds: Optional[float] = None) -> float:
        with self._lock:
            snapshots = self._snapshots
            if duration_seconds and snapshots:
                cutoff = time.time() - duration_seconds
                snapshots = [s for s in snapshots if s.timestamp >= cutoff]
            if not snapshots:
                return 0.0
            return statistics.mean(s.cpu_percent for s in snapshots)

    def can_run_task(self, priority: str = "normal") -> tuple[bool, str]:
        snapshot = self.get_current_snapshot()
        if not snapshot:
            return True, "监控未启动"
        if len(self._active_tasks) >= self._max_parallel_tasks:
            return False, f"并行任务数已达上限 ({self._max_parallel_tasks})"
        cpu_limit = self.PRIORITY_LIMITS.get(priority, 80.0)
        if snapshot.cpu_percent >= cpu_limit:
            return False, f"CPU 负载过高 ({snapshot.cpu_percent:.1f}%)"
        if snapshot.memory_mb >= self.thresholds["memory_critical"]:
            return False, f"内存使用危险 ({snapshot.memory_mb / 1024:.1f} GB)"
        return True, "资源充足"

    def report_task_start(self, task_name: str):
        with self._lock:
            self._active_tasks[task_name] = time.time()

    def report_task_done(self, task_name: str):
        with self._lock:
            if task_name in self._active_tasks:
                duration = time.time() - self._active_tasks[task_name]
                self._task_history.append({
                    "name": task_name,
                    "duration": duration,
                    "timestamp": time.time(),
                })
                del self._active_tasks[task_name]
                if len(self._task_history) > 100:
                    self._task_history = self._task_history[-100:]

    def get_status_dict(self) -> dict:
        snapshot = self.get_current_snapshot()
        load = self.get_load_level()
        return {
            "load_level": load.value,
            "load_emoji": {"idle": "🟢", "light": "🟡", "moderate": "🟠", "heavy": "🔴", "critical": "⚠️"}.get(load.value, "⚪"),
            "cpu_percent": snapshot.cpu_percent if snapshot else 0,
            "memory_mb": snapshot.memory_mb if snapshot else 0,
            "memory_percent": snapshot.memory_percent if snapshot else 0,
            "active_tasks": len(self._active_tasks),
            "max_parallel": self._max_parallel_tasks,
            "queue_info": f"{len(self._active_tasks)}/{self._max_parallel_tasks}",
            "gpu_available": self._gpu_available,
            "gpu_percent": snapshot.gpu_percent if snapshot and snapshot.gpu_percent >= 0 else None,
        }

    def on_alert(self, callback: Callable[[Alert], None]):
        self._alert_callbacks.append(callback)

    def on_load_change(self, callback: Callable[[LoadLevel], None]):
        self._load_callbacks.append(callback)

    def set_thresholds(self, **kwargs):
        for key, value in kwargs.items():
            if key in self.thresholds:
                self.thresholds[key] = value

    def get_stats(self) -> dict:
        with self._lock:
            snapshots = self._snapshots
            stats = {
                "monitoring": self._running,
                "interval": self.interval,
                "snapshots_count": len(snapshots),
                "active_tasks": len(self._active_tasks),
                "max_parallel": self._max_parallel_tasks,
                "thresholds": dict(self.thresholds),
            }
            if snapshots:
                stats["cpu_avg"] = statistics.mean(s.cpu_percent for s in snapshots)
                stats["cpu_max"] = max(s.cpu_percent for s in snapshots)
                stats["memory_avg_mb"] = statistics.mean(s.memory_mb for s in snapshots)
                stats["memory_max_mb"] = max(s.memory_mb for s in snapshots)
            return stats


# PyQt 集成
if PSUTIL_AVAILABLE:
    class PyQtResourceMonitor(ResourceMonitor):
        def __init__(self, statusbar=None, parent=None, **kwargs):
            super().__init__(**kwargs)
            self.statusbar = statusbar
            self.parent = parent
            self._last_status_update = 0
            self._update_interval = 2.0

        def update_statusbar(self):
            if not self.statusbar:
                return
            now = time.time()
            if now - self._last_status_update < self._update_interval:
                return
            self._last_status_update = now
            status = self.get_status_dict()
            cpu = status["cpu_percent"]
            mem = status["memory_mb"] / 1024
            queue = status["queue_info"]
            level_text = {"idle": "空闲", "light": "轻度", "moderate": "中度", "heavy": "重度", "critical": "危险"}.get(status["load_level"], "")
            text = f"系统负载: {level_text} | CPU: {cpu:.0f}% | 内存: {mem:.1f} GB | 任务: {queue}"
            self.statusbar.showMessage(text)

        def get_chart_data(self, duration_seconds: float = 60) -> dict:
            with self._lock:
                cutoff = time.time() - duration_seconds
                relevant = [s for s in self._snapshots if s.timestamp >= cutoff]
                return {
                    "timestamps": [s.timestamp for s in relevant],
                    "cpu": [s.cpu_percent for s in relevant],
                    "memory": [s.memory_percent for s in relevant],
                    "memory_mb": [s.memory_mb for s in relevant],
                }
