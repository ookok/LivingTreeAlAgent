# -*- coding: utf-8 -*-
"""
monitor.py — 资源监控

监控系统资源使用情况（GPU/CPU/内存）和应用层指标（延迟/吞吐量）。
提供资源快照和实时统计。
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional

from .base import DriverState, ModelDriver

logger = logging.getLogger(__name__)


# ── 资源快照 ──────────────────────────────────────────────────────

@dataclass
class GPUMetrics:
    """GPU 指标"""
    index: int = 0
    name: str = ""
    utilization_pct: float = 0.0      # GPU 利用率 (%)
    memory_used_mb: float = 0.0        # 已用显存 (MB)
    memory_total_mb: float = 0.0       # 总显存 (MB)
    memory_utilization_pct: float = 0.0  # 显存利用率 (%)
    temperature_c: float = 0.0         # 温度 (°C)
    power_draw_w: float = 0.0          # 功耗 (W)


@dataclass
class CPUMetrics:
    """CPU 指标"""
    utilization_pct: float = 0.0       # CPU 利用率 (%)
    count_logical: int = 0
    count_physical: int = 0
    frequency_mhz: float = 0.0


@dataclass
class MemoryMetrics:
    """内存指标"""
    used_mb: float = 0.0
    total_mb: float = 0.0
    available_mb: float = 0.0
    utilization_pct: float = 0.0


@dataclass
class AppMetrics:
    """应用层指标"""
    total_requests: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    requests_per_sec: float = 0.0
    tokens_per_sec: float = 0.0


@dataclass
class ResourceSnapshot:
    """
    资源快照 — 某一时刻的完整资源状态
    """
    timestamp: float = field(default_factory=time.time)
    gpus: List[GPUMetrics] = field(default_factory=list)
    cpu: CPUMetrics = field(default_factory=CPUMetrics)
    memory: MemoryMetrics = field(default_factory=MemoryMetrics)
    app: AppMetrics = field(default_factory=AppMetrics)
    driver_states: Dict[str, str] = field(default_factory=dict)


# ── 资源监控器 ──────────────────────────────────────────────────

class ResourceMonitor:
    """
    资源监控器

    支持：
      - GPU 监控（通过 pynvml / nvidia-smi）
      - CPU/内存监控（通过 psutil）
      - 应用层指标（延迟/吞吐量）
      - 历史快照存储
      - 阈值告警
    """

    # 默认配置
    DEFAULT_HISTORY_SIZE = 300        # 保留最近 300 个快照（约 5 分钟 @ 1s）
    DEFAULT_SAMPLE_INTERVAL = 5.0     # 默认采样间隔（秒）
    DEFAULT_LATENCY_WINDOW = 100      # 延迟统计窗口

    def __init__(
        self,
        sample_interval: float = DEFAULT_SAMPLE_INTERVAL,
        history_size: int = DEFAULT_HISTORY_SIZE,
        latency_window: int = DEFAULT_LATENCY_WINDOW,
    ):
        self.sample_interval = sample_interval
        self._history: Deque[ResourceSnapshot] = deque(maxlen=history_size)
        self._latency_window = latency_window
        self._latencies: Deque[float] = deque(maxlen=latency_window)
        self._token_counts: Deque[int] = deque(maxlen=latency_window)
        self._total_requests = 0
        self._total_errors = 0

        # 延迟检测
        self._has_psutil = False
        self._has_pynvml = False
        self._detect_dependencies()

        # 后台采样
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 告警回调
        self._alert_callbacks: List[Callable] = []
        self._gpu_threshold_pct: float = 95.0
        self._memory_threshold_pct: float = 90.0

    def _detect_dependencies(self) -> None:
        """检测可用依赖"""
        try:
            import psutil
            self._has_psutil = True
        except ImportError:
            logger.debug("psutil not installed, CPU/memory monitoring disabled")
        try:
            import pynvml
            pynvml.nvmlInit()
            self._has_pynvml = True
        except (ImportError, Exception):
            logger.debug("pynvml not available, GPU monitoring disabled")

    # ── 采样 ─────────────────────────────────────────────────

    def take_snapshot(self) -> ResourceSnapshot:
        """采集当前资源快照"""
        snapshot = ResourceSnapshot(
            timestamp=time.time(),
            gpus=self._collect_gpu(),
            cpu=self._collect_cpu(),
            memory=self._collect_memory(),
            app=self._collect_app(),
        )
        self._history.append(snapshot)
        self._check_alerts(snapshot)
        return snapshot

    def _collect_gpu(self) -> List[GPUMetrics]:
        """采集 GPU 指标"""
        if not self._has_pynvml:
            return []
        try:
            import pynvml
            count = pynvml.nvmlDeviceGetCount()
            metrics = []
            for i in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                try:
                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                except Exception:
                    temp = 0.0
                try:
                    power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
                except Exception:
                    power = 0.0
                try:
                    name = pynvml.nvmlDeviceGetName(handle)
                    if isinstance(name, bytes):
                        name = name.decode()
                except Exception:
                    name = f"GPU {i}"
                metrics.append(GPUMetrics(
                    index=i, name=name,
                    utilization_pct=float(util.gpu),
                    memory_used_mb=mem.used / 1024 / 1024,
                    memory_total_mb=mem.total / 1024 / 1024,
                    memory_utilization_pct=(mem.used / mem.total * 100) if mem.total else 0,
                    temperature_c=float(temp),
                    power_draw_w=float(power),
                ))
            return metrics
        except Exception as e:
            logger.debug(f"GPU collection error: {e}")
            return []

    def _collect_cpu(self) -> CPUMetrics:
        """采集 CPU 指标"""
        if not self._has_psutil:
            return CPUMetrics()
        try:
            import psutil
            return CPUMetrics(
                utilization_pct=psutil.cpu_percent(interval=0),
                count_logical=psutil.cpu_count(),
                count_physical=psutil.cpu_count(logical=False) or psutil.cpu_count(),
                frequency_mhz=psutil.cpu_freq().current if psutil.cpu_freq() else 0.0,
            )
        except Exception:
            return CPUMetrics()

    def _collect_memory(self) -> MemoryMetrics:
        """采集内存指标"""
        if not self._has_psutil:
            return MemoryMetrics()
        try:
            import psutil
            mem = psutil.virtual_memory()
            return MemoryMetrics(
                used_mb=mem.used / 1024 / 1024,
                total_mb=mem.total / 1024 / 1024,
                available_mb=mem.available / 1024 / 1024,
                utilization_pct=mem.percent,
            )
        except Exception:
            return MemoryMetrics()

    def _collect_app(self) -> AppMetrics:
        """采集应用层指标"""
        avg_lat = 0.0
        p50 = p95 = p99 = 0.0
        if self._latencies:
            sorted_lat = sorted(self._latencies)
            avg_lat = sum(sorted_lat) / len(sorted_lat)
            p50 = sorted_lat[len(sorted_lat) // 2]
            p95 = sorted_lat[int(len(sorted_lat) * 0.95)] if len(sorted_lat) > 1 else sorted_lat[-1]
            p99 = sorted_lat[int(len(sorted_lat) * 0.99)] if len(sorted_lat) > 1 else sorted_lat[-1]

        return AppMetrics(
            total_requests=self._total_requests,
            total_errors=self._total_errors,
            avg_latency_ms=avg_lat,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
        )

    # ── 请求记录 ─────────────────────────────────────────────

    def record_request(self, latency_ms: float, tokens: int = 0, error: bool = False) -> None:
        """记录请求指标"""
        self._total_requests += 1
        self._latencies.append(latency_ms)
        self._token_counts.append(tokens)
        if error:
            self._total_errors += 1

    # ── 告警 ─────────────────────────────────────────────────

    def add_alert_callback(self, callback: Callable) -> None:
        """添加告警回调"""
        self._alert_callbacks.append(callback)

    def set_gpu_threshold(self, pct: float) -> None:
        """设置 GPU 利用率告警阈值"""
        self._gpu_threshold_pct = pct

    def set_memory_threshold(self, pct: float) -> None:
        """设置内存利用率告警阈值"""
        self._memory_threshold_pct = pct

    def _check_alerts(self, snapshot: ResourceSnapshot) -> None:
        """检查是否触发告警"""
        alerts = []
        for gpu in snapshot.gpus:
            if gpu.utilization_pct > self._gpu_threshold_pct:
                alerts.append(f"GPU {gpu.index} ({gpu.name}) utilization {gpu.utilization_pct:.1f}% > {self._gpu_threshold_pct}%")
            if gpu.memory_utilization_pct > self._memory_threshold_pct:
                alerts.append(f"GPU {gpu.index} ({gpu.name}) memory {gpu.memory_utilization_pct:.1f}% > {self._memory_threshold_pct}%")
        if snapshot.memory.utilization_pct > self._memory_threshold_pct:
            alerts.append(f"RAM {snapshot.memory.utilization_pct:.1f}% > {self._memory_threshold_pct}%")

        for alert in alerts:
            logger.warning(f"[Monitor] {alert}")
            for cb in self._alert_callbacks:
                try:
                    cb(alert, snapshot)
                except Exception as e:
                    logger.debug(f"Alert callback error: {e}")

    # ── 后台采样 ─────────────────────────────────────────────

    def start(self) -> None:
        """启动后台采样"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._sample_loop,
            daemon=True,
            name="resource-monitor",
        )
        self._thread.start()
        logger.info(f"[Monitor] started (interval={self.sample_interval}s)")

    def stop(self) -> None:
        """停止后台采样"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("[Monitor] stopped")

    def _sample_loop(self) -> None:
        """采样循环"""
        while not self._stop_event.wait(self.sample_interval):
            try:
                self.take_snapshot()
            except Exception as e:
                logger.debug(f"[Monitor] sample error: {e}")

    # ── 查询 ─────────────────────────────────────────────────

    def get_latest(self) -> Optional[ResourceSnapshot]:
        """获取最新快照"""
        return self._history[-1] if self._history else None

    def get_history(self, last_n: int = 60) -> List[ResourceSnapshot]:
        """获取历史快照"""
        return list(self._history)[-last_n:]

    def get_driver_summary(self, drivers: Dict[str, ModelDriver]) -> Dict[str, Any]:
        """获取驱动状态摘要"""
        return {
            name: {
                "mode": driver.mode.value,
                "state": driver.state.value,
                "latency_ms": driver._last_latency,
                "errors": driver._error_count,
                "total": driver._total_requests,
            }
            for name, driver in drivers.items()
        }

    def get_summary_text(self) -> str:
        """获取文本摘要"""
        snap = self.get_latest()
        if not snap:
            return "No data"

        lines = [f"--- Resource Monitor ({time.strftime('%H:%M:%S')}) ---"]

        if snap.gpus:
            for gpu in snap.gpus:
                lines.append(
                    f"  GPU {gpu.index} ({gpu.name}): "
                    f"{gpu.utilization_pct:.0f}% | "
                    f"VRAM {gpu.memory_used_mb:.0f}/{gpu.memory_total_mb:.0f} MB | "
                    f"{gpu.temperature_c:.0f}°C"
                )

        lines.append(
            f"  CPU: {snap.cpu.utilization_pct:.0f}% | "
            f"RAM: {snap.memory.utilization_pct:.0f}% "
            f"({snap.memory.used_mb:.0f}/{snap.memory.total_mb:.0f} MB)"
        )

        lines.append(
            f"  Requests: {snap.app.total_requests} | "
            f"Errors: {snap.app.total_errors} | "
            f"Avg Latency: {snap.app.avg_latency_ms:.0f}ms | "
            f"P95: {snap.app.p95_latency_ms:.0f}ms"
        )

        return "\n".join(lines)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
