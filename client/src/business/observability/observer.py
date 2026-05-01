"""
观察者管理器

整合追踪、指标和日志系统，提供统一的可观测性接口。
"""

import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from .trace_system import Tracer, SpanKind, SpanStatus, get_tracer
from .metrics_system import MetricsSystem, Counter, Gauge, Histogram, Summary, get_metrics_system
from .logger_system import LoggerSystem, LogLevel, get_logger

class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class Alert:
    """告警"""
    alert_id: str
    level: AlertLevel
    message: str
    timestamp: float
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

class Observer:
    """
    观察者管理器
    
    统一管理追踪、指标和日志，提供一站式可观测性接口。
    """
    
    def __init__(self):
        self.tracer = get_tracer()
        self.metrics = get_metrics_system()
        self.logger = get_logger()
        
        # 告警管理
        self.alerts: List[Alert] = []
        self.alert_callbacks: List[Callable[[Alert], None]] = []
        
        # 初始化默认指标
        self._init_default_metrics()
    
    def _init_default_metrics(self):
        """初始化默认指标"""
        # 任务链相关指标
        self.metrics.create_counter("task_chain.started", "任务链启动次数")
        self.metrics.create_counter("task_chain.completed", "任务链完成次数")
        self.metrics.create_counter("task_chain.failed", "任务链失败次数")
        
        # 任务相关指标
        self.metrics.create_counter("task.started", "任务启动次数")
        self.metrics.create_counter("task.completed", "任务完成次数")
        self.metrics.create_counter("task.failed", "任务失败次数")
        
        # 延迟指标
        self.metrics.create_histogram("task.duration", "任务执行延迟", 
                                    buckets=[0.001, 0.01, 0.1, 1.0, 5.0, 30.0, 60.0])
        self.metrics.create_summary("task_chain.duration", "任务链执行时间摘要")
        
        # 并发指标
        self.metrics.create_gauge("active_tasks", "活跃任务数")
        self.metrics.create_gauge("active_chains", "活跃任务链数")
    
    def start_task_chain(self, chain_name: str, chain_id: Optional[str] = None) -> str:
        """
        开始任务链
        
        Args:
            chain_name: 任务链名称
            chain_id: 任务链ID（可选）
        
        Returns:
            追踪ID
        """
        trace_id = self.tracer.start_trace(chain_id)
        
        # 记录指标
        self.metrics.get_counter("task_chain.started").inc()
        self.metrics.get_gauge("active_chains").inc()
        
        # 记录日志
        self.logger.info(f"任务链启动: {chain_name}", trace_id=trace_id)
        
        # 创建根跨度
        self.tracer.start_span(chain_name, trace_id, kind=SpanKind.SERVER)
        
        return trace_id
    
    def end_task_chain(self, trace_id: str, success: bool = True):
        """
        结束任务链
        
        Args:
            trace_id: 追踪ID
            success: 是否成功
        """
        # 获取追踪信息
        trace = self.tracer.get_trace(trace_id)
        if not trace:
            return
        
        # 完成根跨度
        root_span = trace.spans[0] if trace.spans else None
        if root_span:
            self.tracer.finish_span(root_span.span_id, 
                                  SpanStatus.OK if success else SpanStatus.ERROR)
        
        # 更新指标
        if success:
            self.metrics.get_counter("task_chain.completed").inc()
        else:
            self.metrics.get_counter("task_chain.failed").inc()
            self._create_alert(AlertLevel.WARNING, f"任务链失败: {trace_id}")
        
        self.metrics.get_gauge("active_chains").dec()
        
        # 记录执行时间
        if trace.end_time:
            duration = trace.end_time - trace.start_time
            self.metrics.get_summary("task_chain.duration").observe(duration)
        
        # 记录日志
        status = "成功" if success else "失败"
        self.logger.info(f"任务链完成: {trace_id}, 状态: {status}", trace_id=trace_id)
    
    def start_task(self, trace_id: str, task_name: str, 
                  parent_span_id: Optional[str] = None) -> str:
        """
        开始任务
        
        Args:
            trace_id: 追踪ID
            task_name: 任务名称
            parent_span_id: 父跨度ID
        
        Returns:
            跨度ID
        """
        span_id = self.tracer.start_span(
            task_name,
            trace_id,
            parent_span_id=parent_span_id,
            kind=SpanKind.INTERNAL
        )
        
        # 更新指标
        self.metrics.get_counter("task.started").inc()
        self.metrics.get_gauge("active_tasks").inc()
        
        # 记录日志
        self.logger.debug(f"任务开始: {task_name}", trace_id=trace_id, span_id=span_id)
        
        return span_id
    
    def end_task(self, span_id: str, success: bool = True, 
                error_message: Optional[str] = None):
        """
        结束任务
        
        Args:
            span_id: 跨度ID
            success: 是否成功
            error_message: 错误信息
        """
        # 获取跨度信息
        trace = None
        for t in self.tracer.traces.values():
            for s in t.spans:
                if s.span_id == span_id:
                    trace = t
                    break
            if trace:
                break
        
        # 完成跨度
        status = SpanStatus.OK if success else SpanStatus.ERROR
        self.tracer.finish_span(span_id, status)
        
        # 更新指标
        if success:
            self.metrics.get_counter("task.completed").inc()
        else:
            self.metrics.get_counter("task.failed").inc()
            if error_message:
                self._create_alert(AlertLevel.ERROR, f"任务失败: {error_message}")
        
        self.metrics.get_gauge("active_tasks").dec()
        
        # 记录延迟
        for t in self.tracer.traces.values():
            for s in t.spans:
                if s.span_id == span_id and s.duration:
                    self.metrics.get_histogram("task.duration").observe(s.duration)
                    break
        
        # 记录日志
        status_str = "成功" if success else "失败"
        self.logger.debug(f"任务完成: {span_id}, 状态: {status_str}", span_id=span_id)
    
    def log_task_event(self, span_id: str, event_name: str, **kwargs):
        """
        记录任务事件
        
        Args:
            span_id: 跨度ID
            event_name: 事件名称
            **kwargs: 事件属性
        """
        self.tracer.add_span_event(span_id, event_name, kwargs)
        self.logger.debug(f"任务事件: {event_name}", span_id=span_id, **kwargs)
    
    def _create_alert(self, level: AlertLevel, message: str, **kwargs):
        """
        创建告警
        
        Args:
            level: 告警级别
            message: 告警消息
            **kwargs: 额外元数据
        """
        alert = Alert(
            alert_id=f"alert_{int(time.time())}",
            level=level,
            message=message,
            timestamp=time.time(),
            metadata=kwargs
        )
        
        self.alerts.append(alert)
        
        # 通知回调
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"告警回调失败: {e}")
        
        # 记录日志
        log_method = {
            AlertLevel.INFO: self.logger.info,
            AlertLevel.WARNING: self.logger.warning,
            AlertLevel.CRITICAL: self.logger.critical
        }[level]
        log_method(f"告警 [{level.value}]: {message}")
    
    def add_alert_callback(self, callback: Callable[[Alert], None]):
        """
        添加告警回调
        
        Args:
            callback: 回调函数
        """
        self.alert_callbacks.append(callback)
    
    def get_alerts(self, limit: int = 50, level: Optional[AlertLevel] = None) -> List[Alert]:
        """
        获取告警列表
        
        Args:
            limit: 返回数量限制
            level: 告警级别过滤
        
        Returns:
            告警列表
        """
        alerts = self.alerts
        if level:
            alerts = [a for a in alerts if a.level == level]
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        return alerts[:limit]
    
    def resolve_alert(self, alert_id: str):
        """
        解决告警
        
        Args:
            alert_id: 告警ID
        """
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                self.logger.info(f"告警已解决: {alert_id}")
                break
    
    def get_observability_data(self) -> Dict[str, Any]:
        """
        获取完整的可观测性数据
        
        Returns:
            包含追踪、指标、日志和告警的字典
        """
        return {
            "traces": self.tracer.list_traces(limit=5),
            "metrics": self.metrics.collect_all(),
            "logs": self.logger.get_logs(limit=50),
            "alerts": [{
                "alert_id": a.alert_id,
                "level": a.level.value,
                "message": a.message,
                "timestamp": a.timestamp,
                "resolved": a.resolved,
                "metadata": a.metadata
            } for a in self.get_alerts(limit=20)],
            "timestamp": time.time()
        }
    
    def clear_all(self):
        """清除所有数据"""
        self.tracer.clear_traces()
        self.metrics.reset()
        self.logger.clear_logs()
        self.alerts.clear()

# 全局观察者实例
_observer_instance = None

def get_observer() -> Observer:
    """获取全局观察者实例"""
    global _observer_instance
    if _observer_instance is None:
        _observer_instance = Observer()
    return _observer_instance