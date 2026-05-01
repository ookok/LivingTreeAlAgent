import time
import psutil
import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from collections import deque
from enum import Enum

class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class Metric:
    name: str
    type: MetricType
    value: float
    labels: Dict[str, str] = None
    timestamp: float = 0

@dataclass
class Alert:
    id: str
    level: AlertLevel
    message: str
    metric_name: str
    threshold: float
    current_value: float
    timestamp: float = 0
    resolved: bool = False

@dataclass
class Span:
    id: str
    trace_id: str
    parent_id: Optional[str]
    name: str
    start_time: float
    end_time: Optional[float] = None
    status: str = "running"
    attributes: Dict[str, Any] = None

@dataclass
class Trace:
    id: str
    spans: List[Span]
    start_time: float
    end_time: Optional[float] = None
    status: str = "running"

@dataclass
class LogEntry:
    level: str
    message: str
    timestamp: float
    context: Dict[str, Any] = None

class ObservabilityManager:
    """增强的可观测性管理器"""
    
    def __init__(self):
        self.metrics: Dict[str, Metric] = {}
        self.alerts: List[Alert] = []
        self.traces: Dict[str, Trace] = {}
        self.logs: deque = deque(maxlen=1000)
        self.metric_history: Dict[str, deque] = {}
        
        self._monitor_thread = None
        self._monitor_running = False
        
        self._initialize_system_metrics()
    
    def _initialize_system_metrics(self):
        """初始化系统指标"""
        self.register_metric("system.cpu.usage", MetricType.GAUGE, 0.0)
        self.register_metric("system.memory.usage", MetricType.GAUGE, 0.0)
        self.register_metric("system.disk.usage", MetricType.GAUGE, 0.0)
        self.register_metric("system.network.rx", MetricType.COUNTER, 0.0)
        self.register_metric("system.network.tx", MetricType.COUNTER, 0.0)
        
        self.register_metric("ai.requests.total", MetricType.COUNTER, 0.0)
        self.register_metric("ai.requests.success", MetricType.COUNTER, 0.0)
        self.register_metric("ai.requests.failed", MetricType.COUNTER, 0.0)
        self.register_metric("ai.latency.avg", MetricType.GAUGE, 0.0)
        
        self.register_metric("tools.calls.total", MetricType.COUNTER, 0.0)
        self.register_metric("tools.calls.success", MetricType.COUNTER, 0.0)
        self.register_metric("tools.latency.avg", MetricType.GAUGE, 0.0)
        
        self.register_metric("memory.hits", MetricType.COUNTER, 0.0)
        self.register_metric("memory.misses", MetricType.COUNTER, 0.0)
        
        self.register_metric("dialogues.active", MetricType.GAUGE, 0.0)
        self.register_metric("dialogues.messages", MetricType.COUNTER, 0.0)
    
    def register_metric(self, name: str, metric_type: MetricType, initial_value: float = 0.0):
        """注册指标"""
        self.metrics[name] = Metric(
            name=name,
            type=metric_type,
            value=initial_value,
            labels={},
            timestamp=time.time()
        )
        self.metric_history[name] = deque(maxlen=100)
    
    def update_metric(self, name: str, value: float, labels: Dict = None):
        """更新指标"""
        if name not in self.metrics:
            return
        
        metric = self.metrics[name]
        metric.value = value
        metric.timestamp = time.time()
        if labels:
            metric.labels.update(labels)
        
        self.metric_history[name].append((time.time(), value))
        
        self._check_alerts(name, value)
    
    def increment_counter(self, name: str, value: float = 1.0):
        """增加计数器"""
        if name not in self.metrics:
            return
        
        metric = self.metrics[name]
        if metric.type == MetricType.COUNTER:
            metric.value += value
            metric.timestamp = time.time()
            self.metric_history[name].append((time.time(), metric.value))
    
    def _check_alerts(self, metric_name: str, value: float):
        """检查告警条件"""
        alert_rules = {
            "system.cpu.usage": {"threshold": 90, "level": AlertLevel.CRITICAL},
            "system.memory.usage": {"threshold": 85, "level": AlertLevel.WARNING},
            "system.disk.usage": {"threshold": 90, "level": AlertLevel.WARNING},
            "ai.requests.failed": {"threshold": 10, "level": AlertLevel.ERROR},
            "ai.latency.avg": {"threshold": 10, "level": AlertLevel.WARNING}
        }
        
        if metric_name in alert_rules:
            rule = alert_rules[metric_name]
            if value > rule["threshold"]:
                self.create_alert(
                    metric_name=metric_name,
                    level=rule["level"],
                    message=f"{metric_name} exceeded threshold: {value} > {rule['threshold']}",
                    threshold=rule["threshold"],
                    current_value=value
                )
    
    def create_alert(self, metric_name: str, level: AlertLevel, message: str, threshold: float, current_value: float):
        """创建告警"""
        alert_id = f"{metric_name}_{int(time.time())}"
        
        existing_alerts = [a for a in self.alerts if a.metric_name == metric_name and not a.resolved]
        if existing_alerts:
            return
        
        alert = Alert(
            id=alert_id,
            level=level,
            message=message,
            metric_name=metric_name,
            threshold=threshold,
            current_value=current_value,
            timestamp=time.time()
        )
        
        self.alerts.append(alert)
    
    def resolve_alert(self, alert_id: str):
        """解决告警"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                break
    
    def start_trace(self, trace_id: str, name: str) -> Span:
        """开始追踪"""
        span = Span(
            id=f"{trace_id}-{int(time.time())}",
            trace_id=trace_id,
            parent_id=None,
            name=name,
            start_time=time.time()
        )
        
        if trace_id not in self.traces:
            self.traces[trace_id] = Trace(
                id=trace_id,
                spans=[span],
                start_time=time.time()
            )
        else:
            self.traces[trace_id].spans.append(span)
        
        return span
    
    def end_span(self, span_id: str, trace_id: str, status: str = "success"):
        """结束Span"""
        if trace_id not in self.traces:
            return
        
        trace = self.traces[trace_id]
        for span in trace.spans:
            if span.id == span_id:
                span.end_time = time.time()
                span.status = status
                break
        
        if all(s.end_time for s in trace.spans):
            trace.end_time = max(s.end_time for s in trace.spans)
            trace.status = status
    
    def log(self, level: str, message: str, context: Dict = None):
        """记录日志"""
        entry = LogEntry(
            level=level,
            message=message,
            timestamp=time.time(),
            context=context
        )
        self.logs.append(entry)
    
    def start_monitoring(self, interval: int = 5):
        """启动系统监控"""
        self._monitor_running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,))
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
    
    def _monitor_loop(self, interval: int):
        """监控循环"""
        last_net_io = psutil.net_io_counters()
        
        while self._monitor_running:
            try:
                self.update_metric("system.cpu.usage", psutil.cpu_percent())
                self.update_metric("system.memory.usage", psutil.virtual_memory().percent)
                self.update_metric("system.disk.usage", psutil.disk_usage('/').percent)
                
                current_net_io = psutil.net_io_counters()
                rx_diff = current_net_io.bytes_recv - last_net_io.bytes_recv
                tx_diff = current_net_io.bytes_sent - last_net_io.bytes_sent
                self.update_metric("system.network.rx", rx_diff)
                self.update_metric("system.network.tx", tx_diff)
                last_net_io = current_net_io
            
            except Exception as e:
                self.log("error", f"监控错误: {str(e)}")
            
            time.sleep(interval)
    
    def stop_monitoring(self):
        """停止监控"""
        self._monitor_running = False
        if self._monitor_thread:
            self._monitor_thread.join()
    
    def get_metrics(self) -> List[Metric]:
        """获取所有指标"""
        return list(self.metrics.values())
    
    def get_alerts(self, include_resolved: bool = False) -> List[Alert]:
        """获取告警"""
        if include_resolved:
            return self.alerts
        return [a for a in self.alerts if not a.resolved]
    
    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """获取追踪"""
        return self.traces.get(trace_id)
    
    def get_recent_logs(self, limit: int = 50) -> List[LogEntry]:
        """获取最近日志"""
        return list(self.logs)[-limit:]
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """获取仪表盘数据"""
        metrics = self.get_metrics()
        alerts = self.get_alerts()
        
        return {
            "metrics": [{
                "name": m.name,
                "value": m.value,
                "type": m.type.value,
                "timestamp": m.timestamp
            } for m in metrics],
            "alerts": [{
                "id": a.id,
                "level": a.level.value,
                "message": a.message,
                "timestamp": a.timestamp,
                "resolved": a.resolved
            } for a in alerts],
            "system_info": {
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total / (1024 ** 3),
                "disk_total": psutil.disk_usage('/').total / (1024 ** 3)
            },
            "charts": self._generate_chart_data()
        }
    
    def _generate_chart_data(self) -> Dict[str, Any]:
        """生成图表数据"""
        charts = {}
        
        for metric_name in ["system.cpu.usage", "system.memory.usage", "ai.latency.avg"]:
            if metric_name in self.metric_history:
                history = self.metric_history[metric_name]
                if len(history) > 0:
                    charts[metric_name] = {
                        "labels": [t[0] for t in history],
                        "values": [t[1] for t in history]
                    }
        
        return charts
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """获取汇总统计"""
        metrics = self.get_metrics()
        
        ai_requests = next((m for m in metrics if m.name == "ai.requests.total"), None)
        ai_success = next((m for m in metrics if m.name == "ai.requests.success"), None)
        tools_calls = next((m for m in metrics if m.name == "tools.calls.total"), None)
        
        return {
            "total_ai_requests": ai_requests.value if ai_requests else 0,
            "ai_success_rate": (ai_success.value / ai_requests.value * 100) if ai_requests and ai_requests.value > 0 else 0,
            "total_tool_calls": tools_calls.value if tools_calls else 0,
            "active_alerts": len(self.get_alerts()),
            "active_traces": len([t for t in self.traces.values() if t.status == "running"]),
            "uptime": time.time() - self._start_time if hasattr(self, '_start_time') else 0
        }