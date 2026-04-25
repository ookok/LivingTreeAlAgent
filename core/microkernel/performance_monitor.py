"""
Performance Monitor - 性能监控器

采集系统资源 + 应用指标，提供实时监控数据。
支持阈值告警、数据聚合、历史记录。
"""

import time
import threading
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# 指标定义
# ──────────────────────────────────────────────────────────

@dataclass
class MetricPoint:
    """单个指标数据点"""
    name: str
    value: float
    timestamp: float
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class Threshold:
    """告警阈值"""
    metric_name: str
    min_value: Optional[float] = None  # 低于此值告警
    max_value: Optional[float] = None  # 高于此值告警
    check_interval: float = 5.0  # 检查间隔（秒）
    message: str = ""

    def check(self, value: float) -> Optional[str]:
        """
        检查是否触发告警

        Returns:
            告警消息，未触发则返回 None
        """
        if self.min_value is not None and value < self.min_value:
            return self.message or f"{self.metric_name} too low: {value} < {self.min_value}"
        if self.max_value is not None and value > self.max_value:
            return self.message or f"{self.metric_name} too high: {value} > {self.max_value}"
        return None


# ──────────────────────────────────────────────────────────
# 系统指标采集器
# ──────────────────────────────────────────────────────────

class SystemMetricsCollector:
    """系统指标采集器"""

    def __init__(self):
        self._last_cpu_times: Optional[tuple] = None
        self._last_cpu_time: Optional[float] = None

    def collect(self) -> Dict[str, float]:
        """
        采集系统指标

        Returns:
            指标字典 {
                "cpu_percent": float,
                "memory_percent": float,
                "memory_used_mb": float,
                "memory_total_mb": float,
                "disk_read_kb": float,
                "disk_write_kb": float,
                "network_sent_kb": float,
                "network_recv_kb": float,
            }
        """
        metrics = {}

        try:
            import psutil

            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            metrics["cpu_percent"] = cpu_percent

            # 内存
            mem = psutil.virtual_memory()
            metrics["memory_percent"] = mem.percent
            metrics["memory_used_mb"] = mem.used / 1024 / 1024
            metrics["memory_total_mb"] = mem.total / 1024 / 1024

            # 磁盘 I/O
            disk_io = psutil.disk_io_counters()
            if disk_io:
                metrics["disk_read_kb"] = disk_io.read_bytes / 1024
                metrics["disk_write_kb"] = disk_io.write_bytes / 1024

            # 网络 I/O
            net_io = psutil.net_io_counters()
            if net_io:
                metrics["network_sent_kb"] = net_io.bytes_sent / 1024
                metrics["network_recv_kb"] = net_io.bytes_recv / 1024

            # 进程数
            metrics["process_count"] = len(psutil.pids())

            # 文件描述符（Unix）
            try:
                metrics["open_files"] = len(psutil.Process().open_files())
            except Exception:
                metrics["open_files"] = 0

        except ImportError:
            logger.warning("[PerformanceMonitor] psutil not installed. Run: pip install psutil")
            # 降级：返回模拟数据
            metrics = self._collect_fallback()

        except Exception as e:
            logger.error(f"[PerformanceMonitor] Collect system metrics failed: {e}")
            metrics = self._collect_fallback()

        return metrics

    def _collect_fallback(self) -> Dict[str, float]:
        """降级采集（不使用 psutil）"""
        return {
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "memory_used_mb": 0.0,
            "memory_total_mb": 0.0,
            "disk_read_kb": 0.0,
            "disk_write_kb": 0.0,
            "network_sent_kb": 0.0,
            "network_recv_kb": 0.0,
            "process_count": 0,
            "open_files": 0,
        }


# ──────────────────────────────────────────────────────────
# 应用指标采集器
# ──────────────────────────────────────────────────────────

class AppMetricsCollector:
    """应用指标采集器"""

    def __init__(self):
        self._start_time = time.time()

    def collect(self) -> Dict[str, float]:
        """
        采集应用指标

        Returns:
            指标字典 {
                "uptime_seconds": float,
                "event_count": int,
                "cache_hit_rate": float,
                "active_plugins": int,
                "loaded_plugins": int,
                "memory_usage_mb": float,  # Python 进程内存
            }
        """
        metrics = {}

        try:
            # 运行时间
            metrics["uptime_seconds"] = time.time() - self._start_time

            # 事件总线统计
            from core.plugin_framework.event_bus import get_event_bus
            eb = get_event_bus()
            if eb:
                stats = eb.get_stats()
                metrics["event_count"] = float(stats.get("event_count", 0))
                metrics["listener_count"] = float(stats.get("listener_count", 0))

            # 插件统计
            from core.plugin_framework.plugin_manager import get_plugin_manager
            pm = get_plugin_manager()
            if pm:
                plugins = pm.get_all_plugins()
                metrics["active_plugins"] = float(
                    sum(1 for p in plugins.values() if p.state.value == "active")
                )
                metrics["loaded_plugins"] = float(
                    sum(1 for p in plugins.values() if p.state.value in ("loaded", "active"))
                )

            # Python 进程内存
            try:
                import psutil
                process = psutil.Process()
                metrics["memory_usage_mb"] = process.memory_info().rss / 1024 / 1024
            except ImportError:
                metrics["memory_usage_mb"] = 0.0

            # 缓存命中率（如果有 UnifiedIntentCache）
            try:
                from core.intent_engine.unified_intent_cache import get_unified_cache
                cache = get_unified_cache()
                if cache:
                    stats = cache.get_stats()
                    metrics["cache_hit_rate"] = stats.get("hit_rate", 0.0)
                    metrics["cache_size"] = float(stats.get("size", 0))
            except Exception:
                metrics["cache_hit_rate"] = 0.0
                metrics["cache_size"] = 0.0

        except Exception as e:
            logger.error(f"[PerformanceMonitor] Collect app metrics failed: {e}")
            logger.error(traceback.format_exc())

        return metrics


# ──────────────────────────────────────────────────────────
# 性能监控器（主类）
# ──────────────────────────────────────────────────────────

class PerformanceMonitor:
    """
    性能监控器

    功能：
    1. 定期采集系统和应用指标
    2. 检查告警阈值
    3. 保存历史数据
    4. 提供查询接口
    """

    def __init__(
        self,
        collect_interval: float = 5.0,  # 采集间隔（秒）
        max_history: int = 1000,       # 最大历史记录数
    ):
        """
        Args:
            collect_interval: 采集间隔（秒）
            max_history: 最大历史记录数（超过此数会截断）
        """
        self._collect_interval = collect_interval
        self._max_history = max_history

        self._system_collector = SystemMetricsCollector()
        self._app_collector = AppMetricsCollector()

        # 历史数据：metric_name -> List[(timestamp, value)]
        self._history: Dict[str, List[tuple]] = {}

        # 告警阈值：metric_name -> List[Threshold]
        self._thresholds: Dict[str, List[Threshold]] = {}

        # 告警回调：当告警触发时调用
        self._alert_callbacks: List[callable] = []

        # 监控线程
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.RLock()

        # 当前指标缓存
        self._current_metrics: Dict[str, float] = {}

        logger.info("[PerformanceMonitor] Initialized")

    # ──────────────────────────────────────────────────────
    # 启动/停止
    # ──────────────────────────────────────────────────────

    def start(self) -> None:
        """启动监控"""
        if self._running:
            return

        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="PerformanceMonitor",
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info("[PerformanceMonitor] Started")

    def stop(self) -> None:
        """停止监控"""
        self._running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        logger.info("[PerformanceMonitor] Stopped")

    # ──────────────────────────────────────────────────────
    # 指标采集
    # ──────────────────────────────────────────────────────

    def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                self._collect_and_store()
                self._check_thresholds()
            except Exception as e:
                logger.error(f"[PerformanceMonitor] Monitor loop error: {e}")

            time.sleep(self._collect_interval)

    def _collect_and_store(self) -> None:
        """采集并存储指标"""
        # 采集系统指标
        system_metrics = self._system_collector.collect()
        for name, value in system_metrics.items():
            self._store_metric(f"system.{name}", value)

        # 采集应用指标
        app_metrics = self._app_collector.collect()
        for name, value in app_metrics.items():
            self._store_metric(f"app.{name}", value)

        # 更新当前指标缓存
        with self._lock:
            self._current_metrics.update(system_metrics)
            self._current_metrics.update(app_metrics)

    def _store_metric(self, name: str, value: float) -> None:
        """存储指标到历史"""
        with self._lock:
            if name not in self._history:
                self._history[name] = []

            self._history[name].append((time.time(), value))

            # 截断历史数据
            if len(self._history[name]) > self._max_history:
                self._history[name] = self._history[name][-self._max_history:]

    # ──────────────────────────────────────────────────────
    # 告警阈值
    # ──────────────────────────────────────────────────────

    def add_threshold(self, threshold: Threshold) -> None:
        """添加告警阈值"""
        with self._lock:
            if threshold.metric_name not in self._thresholds:
                self._thresholds[threshold.metric_name] = []
            self._thresholds[threshold.metric_name].append(threshold)

        logger.info(f"[PerformanceMonitor] Added threshold for: {threshold.metric_name}")

    def remove_thresholds(self, metric_name: str) -> None:
        """移除告警阈值"""
        with self._lock:
            if metric_name in self._thresholds:
                del self._thresholds[metric_name]

    def _check_thresholds(self) -> None:
        """检查告警阈值"""
        alerts = []

        with self._lock:
            current = self._current_metrics.copy()

        for metric_name, thresholds in self._thresholds.items():
            value = current.get(metric_name)
            if value is None:
                continue

            for threshold in thresholds:
                alert_msg = threshold.check(value)
                if alert_msg:
                    alerts.append({
                        "metric": metric_name,
                        "value": value,
                        "message": alert_msg,
                        "timestamp": time.time(),
                    })

        # 触发告警回调
        for alert in alerts:
            for cb in self._alert_callbacks:
                try:
                    cb(alert)
                except Exception as e:
                    logger.error(f"[PerformanceMonitor] Alert callback error: {e}")

            logger.warning(f"[PerformanceMonitor] Alert: {alert['message']}")

    def add_alert_callback(self, callback: callable) -> None:
        """添加告警回调"""
        self._alert_callbacks.append(callback)

    # ──────────────────────────────────────────────────────
    # 查询接口
    # ──────────────────────────────────────────────────────

    def get_current_metrics(self) -> Dict[str, float]:
        """获取当前指标"""
        with self._lock:
            return self._current_metrics.copy()

    def get_metric_history(
        self,
        metric_name: str,
        duration: float = 3600,  # 最近 1 小时
    ) -> List[tuple]:
        """
        获取指标历史

        Args:
            metric_name: 指标名称
            duration: 时间范围（秒）

        Returns:
            [(timestamp, value), ...]
        """
        with self._lock:
            if metric_name not in self._history:
                return []

            cutoff = time.time() - duration
            return [
                (ts, val) for ts, val in self._history[metric_name]
                if ts >= cutoff
            ]

    def get_all_metric_names(self) -> List[str]:
        """获取所有指标名称"""
        with self._lock:
            return list(self._history.keys())

    def get_stats(self) -> Dict[str, Any]:
        """获取监控统计"""
        with self._lock:
            return {
                "metric_count": len(self._history),
                "threshold_count": sum(len(v) for v in self._thresholds.values()),
                "alert_callback_count": len(self._alert_callbacks),
                "collect_interval": self._collect_interval,
                "max_history": self._max_history,
                "current_metrics": self._current_metrics.copy(),
            }

    # ──────────────────────────────────────────────────────
    # 预设阈值
    # ──────────────────────────────────────────────────────

    def setup_default_thresholds(self) -> None:
        """设置默认告警阈值"""
        defaults = [
            Threshold(
                metric_name="system.cpu_percent",
                max_value=90.0,
                message="CPU 使用率过高（> 90%）",
            ),
            Threshold(
                metric_name="system.memory_percent",
                max_value=90.0,
                message="内存使用率过高（> 90%）",
            ),
            Threshold(
                metric_name="app.cache_hit_rate",
                min_value=0.5,
                message="缓存命中率过低（< 50%）",
            ),
            Threshold(
                metric_name="app.memory_usage_mb",
                max_value=1000.0,
                message="Python 进程内存使用过高（> 1000 MB）",
            ),
        ]

        for t in defaults:
            self.add_threshold(t)

        logger.info("[PerformanceMonitor] Default thresholds set")


# ──────────────────────────────────────────────────────────
# 全局单例
# ──────────────────────────────────────────────────────────

_monitor_instance: Optional[PerformanceMonitor] = None
_monitor_lock = threading.RLock()


def get_performance_monitor() -> PerformanceMonitor:
    """获取性能监控器单例"""
    global _monitor_instance
    with _monitor_lock:
        if _monitor_instance is None:
            _monitor_instance = PerformanceMonitor()
        return _monitor_instance


def start_performance_monitoring() -> None:
    """启动性能监控"""
    monitor = get_performance_monitor()
    monitor.setup_default_thresholds()
    monitor.start()


def stop_performance_monitoring() -> None:
    """停止性能监控"""
    global _monitor_instance
    with _monitor_lock:
        if _monitor_instance:
            _monitor_instance.stop()
            _monitor_instance = None
