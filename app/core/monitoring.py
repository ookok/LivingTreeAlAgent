"""
企业级监控系统
支持系统指标收集、告警管理、Prometheus 指标导出
"""
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
from enum import Enum


class AlertSeverity(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class SystemMetrics:
    """系统指标"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_free_gb: float
    gpu_count: int = 0
    gpu_memory_percent: List[float] = field(default_factory=list)
    gpu_utilization: List[float] = field(default_factory=list)


@dataclass
class Alert:
    """告警"""
    id: str
    metric: str
    value: float
    threshold: float
    operator: str
    severity: AlertSeverity
    message: str
    start_time: datetime
    end_time: Optional[datetime] = None
    resolved: bool = False


class MetricsCollector:
    """系统指标收集器"""
    
    def __init__(self, collect_interval: int = 5, history_size: int = 1000):
        self.collect_interval = collect_interval
        self.history = deque(maxlen=history_size)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # 告警状态
        self._active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=100)
    
    def start(self):
        """启动指标收集"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """停止指标收集"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _collect_loop(self):
        """收集循环"""
        while self._running:
            try:
                metrics = self._collect_system_metrics()
                self.history.append(metrics)
                self._check_alerts(metrics)
            except Exception as e:
                print(f"Metrics collection error: {e}")
            time.sleep(self.collect_interval)
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """收集系统指标"""
        import psutil
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # 内存
        mem = psutil.virtual_memory()
        
        # 磁盘
        disk = psutil.disk_usage('/')
        
        # GPU (尝试获取)
        gpu_count = 0
        gpu_memory_percent = []
        gpu_utilization = []
        
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            gpu_count = len(gpus)
            for gpu in gpus:
                gpu_memory_percent.append(gpu.memoryUtil * 100)
                gpu_utilization.append(gpu.load * 100)
        except ImportError:
            pass
        except Exception:
            pass
        
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=mem.percent,
            memory_used_gb=mem.used / (1024**3),
            memory_total_gb=mem.total / (1024**3),
            disk_percent=disk.percent,
            disk_free_gb=disk.free / (1024**3),
            gpu_count=gpu_count,
            gpu_memory_percent=gpu_memory_percent,
            gpu_utilization=gpu_utilization
        )
    
    def _check_alerts(self, metrics: SystemMetrics):
        """检查告警"""
        # CPU 告警
        if metrics.cpu_percent > 90:
            self._trigger_alert("cpu", metrics.cpu_percent, 90, ">")
        else:
            self._resolve_alert("cpu")
        
        # 内存告警
        if metrics.memory_percent > 85:
            self._trigger_alert("memory", metrics.memory_percent, 85, ">")
        else:
            self._resolve_alert("memory")
        
        # 磁盘告警
        if metrics.disk_percent > 90:
            self._trigger_alert("disk", metrics.disk_percent, 90, ">")
        else:
            self._resolve_alert("disk")
        
        # GPU 告警
        if metrics.gpu_count > 0:
            for i, (util, mem) in enumerate(zip(metrics.gpu_utilization, metrics.gpu_memory_percent)):
                if mem > 95:
                    self._trigger_alert(f"gpu_{i}_memory", mem, 95, ">")
                else:
                    self._resolve_alert(f"gpu_{i}_memory")
    
    def _trigger_alert(self, metric: str, value: float, threshold: float, operator: str):
        """触发告警"""
        if metric in self._active_alerts:
            return
        
        alert_id = f"{metric}_{operator}_{threshold}"
        alert = Alert(
            id=alert_id,
            metric=metric,
            value=value,
            threshold=threshold,
            operator=operator,
            severity=AlertSeverity.WARNING if value < 98 else AlertSeverity.CRITICAL,
            message=f"{metric} {operator} {threshold} (当前: {value:.1f})",
            start_time=datetime.now()
        )
        
        self._active_alerts[metric] = alert
        self.alert_history.append(alert)
        print(f"[ALERT] {alert.message}")
    
    def _resolve_alert(self, metric: str):
        """解决告警"""
        if metric in self._active_alerts:
            alert = self._active_alerts.pop(metric)
            alert.end_time = datetime.now()
            alert.resolved = True
            print(f"[RESOLVED] {alert.message}")
    
    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """获取当前指标"""
        return self.history[-1] if self.history else None
    
    def get_metrics_history(self, limit: int = 100) -> List[Dict]:
        """获取指标历史"""
        return [
            {
                "timestamp": m.timestamp.isoformat(),
                "cpu_percent": m.cpu_percent,
                "memory_percent": m.memory_percent,
                "disk_percent": m.disk_percent,
                "gpu_count": m.gpu_count
            }
            for m in list(self.history)[-limit:]
        ]
    
    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return list(self._active_alerts.values())
    
    def get_prometheus_metrics(self) -> str:
        """导出 Prometheus 格式指标"""
        metrics = self.get_current_metrics()
        if not metrics:
            return ""
        
        lines = [
            "# HELP system_cpu_usage_percent CPU使用率",
            "# TYPE system_cpu_usage_percent gauge",
            f"system_cpu_usage_percent {metrics.cpu_percent}",
            "",
            "# HELP system_memory_usage_percent 内存使用率",
            "# TYPE system_memory_usage_percent gauge",
            f"system_memory_usage_percent {metrics.memory_percent}",
            "",
            "# HELP system_disk_usage_percent 磁盘使用率",
            "# TYPE system_disk_usage_percent gauge",
            f"system_disk_usage_percent {metrics.disk_percent}",
            "",
            "# HELP system_memory_used_gb 已使用内存(GB)",
            "# TYPE system_memory_used_gb gauge",
            f"system_memory_used_gb {metrics.memory_used_gb:.2f}",
            "",
            "# HELP model_loaded_count 已加载模型数量",
            "# TYPE model_loaded_count gauge",
            f"model_loaded_count 0",
        ]
        
        return "\n".join(lines)


class InferenceMetrics:
    """推理指标"""
    
    def __init__(self):
        self.total_requests = 0
        self.total_tokens = 0
        self.total_duration = 0.0
        self._lock = threading.Lock()
    
    def record_inference(self, tokens: int, duration: float):
        """记录推理"""
        with self._lock:
            self.total_requests += 1
            self.total_tokens += tokens
            self.total_duration += duration
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            avg_tokens = self.total_tokens / self.total_requests if self.total_requests > 0 else 0
            avg_duration = self.total_duration / self.total_requests if self.total_requests > 0 else 0
            return {
                "total_requests": self.total_requests,
                "total_tokens": self.total_tokens,
                "total_duration_sec": self.total_duration,
                "avg_tokens_per_request": avg_tokens,
                "avg_duration_sec": avg_duration,
                "tokens_per_second": avg_tokens / avg_duration if avg_duration > 0 else 0
            }


# 全局实例
metrics_collector = MetricsCollector()
inference_metrics = InferenceMetrics()
