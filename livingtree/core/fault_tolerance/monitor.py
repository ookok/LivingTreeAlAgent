"""
Fault Tolerance System - Monitor Dashboard
强容错分布式任务处理系统 - 监控仪表板

实时监控系统状态、故障、恢复等指标
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from threading import Lock

from .models import (
    Task, TaskStatus, Node, NodeStatus, NodeRole,
    Fault, FaultType, SystemMetrics, RecoveryRecord,
    RecoveryStrategy
)
from .fault_detector import FaultDetector
from .distributed_scheduler import DistributedScheduler
from .checkpoint_manager import CheckpointManager
from .recovery_manager import RecoveryManager

# 延迟导入node_manager(需要psutil)
NodeManager = None
try:
    from .node_manager import NodeManager
except ImportError:
    pass

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """告警"""
    alert_id: str
    level: AlertLevel
    title: str
    message: str
    source: str  # 告警来源
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimeSeriesPoint:
    """时间序列数据点"""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


class MonitorDashboard:
    """
    监控仪表板
    
    功能:
    - 实时指标收集
    - 告警管理
    - 历史数据存储
    - 可视化数据导出
    """
    
    def __init__(self):
        # 组件引用
        self._fault_detector: Optional[FaultDetector] = None
        self._scheduler: Optional[DistributedScheduler] = None
        self._checkpoint_manager: Optional[CheckpointManager] = None
        self._recovery_manager: Optional[RecoveryManager] = None
        self._node_manager: Optional[NodeManager] = None
        
        # 告警管理
        self._alerts: Dict[str, Alert] = {}
        self._alert_callbacks: List[Callable] = []
        
        # 历史数据
        self._metrics_history: List[SystemMetrics] = []
        self._max_history_size = 1000
        
        # 时间序列数据
        self._time_series: Dict[str, List[TimeSeriesPoint]] = defaultdict(list)
        self._max_series_size = 500
        
        # 统计
        self._stats = {
            'start_time': datetime.now(),
            'total_alerts': 0,
            'critical_alerts': 0,
            'resolved_alerts': 0,
        }
        
        # 告警规则
        self._alert_rules: List[Dict[str, Any]] = [
            {
                'name': 'high_cpu',
                'condition': 'cpu_usage > 90',
                'level': AlertLevel.WARNING,
                'source': 'node',
                'cooldown': 300  # 5分钟冷却
            },
            {
                'name': 'high_memory',
                'condition': 'memory_usage > 90',
                'level': AlertLevel.WARNING,
                'source': 'node',
                'cooldown': 300
            },
            {
                'name': 'node_offline',
                'condition': 'status == OFFLINE',
                'level': AlertLevel.ERROR,
                'source': 'node',
                'cooldown': 60
            },
            {
                'name': 'task_failure_rate',
                'condition': 'failure_rate > 0.1',
                'level': AlertLevel.WARNING,
                'source': 'scheduler',
                'cooldown': 600
            },
            {
                'name': 'recovery_failed',
                'condition': 'recovery_success < 0.8',
                'level': AlertLevel.ERROR,
                'source': 'recovery',
                'cooldown': 300
            },
        ]
        
        # 冷却追踪
        self._alert_cooldowns: Dict[str, datetime] = {}
        
        # 锁
        self._lock = Lock()
        
        # 状态
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    # ==================== 组件绑定 ====================
    
    def bind_fault_detector(self, detector: FaultDetector) -> None:
        """绑定故障检测器"""
        self._fault_detector = detector
    
    def bind_scheduler(self, scheduler: DistributedScheduler) -> None:
        """绑定调度器"""
        self._scheduler = scheduler
    
    def bind_checkpoint_manager(self, manager: CheckpointManager) -> None:
        """绑定检查点管理器"""
        self._checkpoint_manager = manager
    
    def bind_recovery_manager(self, manager: RecoveryManager) -> None:
        """绑定恢复管理器"""
        self._recovery_manager = manager
    
    def bind_node_manager(self, manager: NodeManager) -> None:
        """绑定节点管理器"""
        self._node_manager = manager
    
    # ==================== 告警管理 ====================
    
    def register_alert_callback(self, callback: Callable) -> None:
        """注册告警回调"""
        self._alert_callbacks.append(callback)
    
    def create_alert(self, level: AlertLevel, title: str, message: str,
                    source: str, metadata: Optional[Dict[str, Any]] = None) -> Alert:
        """创建告警"""
        import uuid
        
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            level=level,
            title=title,
            message=message,
            source=source,
            metadata=metadata or {}
        )
        
        with self._lock:
            self._alerts[alert.alert_id] = alert
            self._stats['total_alerts'] += 1
            
            if level == AlertLevel.CRITICAL:
                self._stats['critical_alerts'] += 1
        
        # 触发回调
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(alert))
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
        
        logger.log(
            logging.WARNING if level in (AlertLevel.WARNING, AlertLevel.ERROR) else logging.INFO,
            f"Alert [{level.value}]: {title} - {message}"
        )
        
        return alert
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        with self._lock:
            if alert_id in self._alerts:
                self._alerts[alert_id].acknowledged = True
                return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        with self._lock:
            if alert_id in self._alerts:
                alert = self._alerts[alert_id]
                alert.resolved = True
                self._stats['resolved_alerts'] += 1
                return True
        return False
    
    def get_active_alerts(self, level: Optional[AlertLevel] = None) -> List[Alert]:
        """获取活跃告警"""
        with self._lock:
            alerts = [a for a in self._alerts.values() if not a.resolved]
            
            if level:
                alerts = [a for a in alerts if a.level == level]
            
            return sorted(alerts, key=lambda a: (
                -a.level.value,
                a.timestamp
            ))
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """获取告警历史"""
        with self._lock:
            return sorted(
                [a for a in self._alerts.values() if a.resolved],
                key=lambda a: a.timestamp,
                reverse=True
            )[:limit]
    
    # ==================== 监控API ====================
    
    async def start(self) -> None:
        """启动监控"""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Monitor dashboard started")
    
    async def stop(self) -> None:
        """停止监控"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Monitor dashboard stopped")
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        status = {
            'healthy': True,
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': (datetime.now() - self._stats['start_time']).total_seconds(),
            'components': {},
            'summary': {},
            'alerts': {
                'active': len(self.get_active_alerts()),
                'critical': len([a for a in self._alerts.values() 
                                if not a.resolved and a.level == AlertLevel.CRITICAL]),
            }
        }
        
        # 节点状态
        if self._node_manager:
            node_stats = self._node_manager.get_stats()
            status['components']['nodes'] = node_stats
            
            # 检查是否健康
            if node_stats.get('active_nodes', 0) == 0:
                status['healthy'] = False
        
        # 调度器状态
        if self._scheduler:
            queue_status = self._scheduler.get_queue_status()
            status['components']['scheduler'] = queue_status
            
            # 检查是否有过多失败
            if queue_status.get('failed', 0) > 50:
                status['healthy'] = False
        
        # 恢复状态
        if self._recovery_manager:
            recovery_stats = self._recovery_manager.get_recovery_stats()
            status['components']['recovery'] = recovery_stats
            
            # 检查恢复成功率
            if recovery_stats.get('success_rate', 1.0) < 0.8:
                status['healthy'] = False
        
        # 检查点状态
        if self._checkpoint_manager:
            checkpoint_stats = self._checkpoint_manager.get_stats()
            status['components']['checkpoints'] = checkpoint_stats
        
        # 总结
        status['summary'] = {
            'total_nodes': status['components'].get('nodes', {}).get('total_nodes', 0),
            'active_nodes': status['components'].get('nodes', {}).get('active_nodes', 0),
            'pending_tasks': status['components'].get('scheduler', {}).get('pending', 0),
            'running_tasks': status['components'].get('scheduler', {}).get('running', 0),
            'completed_tasks': status['components'].get('scheduler', {}).get('completed', 0),
            'failed_tasks': status['components'].get('scheduler', {}).get('failed', 0),
            'recovery_success_rate': status['components'].get('recovery', {}).get('success_rate', 1.0),
        }
        
        return status
    
    def get_metrics(self) -> SystemMetrics:
        """获取系统指标"""
        metrics = SystemMetrics()
        metrics.timestamp = datetime.now()
        
        if self._node_manager:
            stats = self._node_manager.get_stats()
            metrics.total_nodes = stats.get('total_nodes', 0)
            metrics.active_nodes = stats.get('active_nodes', 0)
        
        if self._scheduler:
            queue = self._scheduler.get_queue_status()
            metrics.total_tasks = queue.get('pending', 0) + queue.get('running', 0) + \
                                   queue.get('completed', 0) + queue.get('failed', 0)
            metrics.pending_tasks = queue.get('pending', 0)
            metrics.running_tasks = queue.get('running', 0)
            metrics.completed_tasks = queue.get('completed', 0)
            metrics.failed_tasks = queue.get('failed', 0)
            
            # 计算平均任务时长
            if metrics.completed_tasks > 0:
                # 这里简化处理，实际应该跟踪每个任务的时间
                metrics.avg_task_duration_ms = 1000  # 假设1秒
        
        if self._fault_detector:
            fault_metrics = self._fault_detector.get_system_metrics()
            metrics.active_faults = fault_metrics.active_faults
            metrics.resolved_faults = fault_metrics.resolved_faults
        
        if self._recovery_manager:
            recovery_stats = self._recovery_manager.get_recovery_stats()
            metrics.recovery_success_rate = recovery_stats.get('success_rate', 1.0)
        
        return metrics
    
    def record_time_series(self, metric_name: str, value: float,
                          labels: Optional[Dict[str, str]] = None) -> None:
        """记录时间序列数据"""
        point = TimeSeriesPoint(
            timestamp=datetime.now(),
            value=value,
            labels=labels or {}
        )
        
        with self._lock:
            self._time_series[metric_name].append(point)
            
            # 限制大小
            if len(self._time_series[metric_name]) > self._max_series_size:
                self._time_series[metric_name] = self._time_series[metric_name][-self._max_series_size:]
    
    def get_time_series(self, metric_name: str, 
                       duration: Optional[timedelta] = None) -> List[TimeSeriesPoint]:
        """获取时间序列数据"""
        with self._lock:
            points = self._time_series.get(metric_name, [])
            
            if duration:
                cutoff = datetime.now() - duration
                points = [p for p in points if p.timestamp > cutoff]
            
            return points
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        return {
            'uptime_seconds': (datetime.now() - self._stats['start_time']).total_seconds(),
            'total_alerts': self._stats['total_alerts'],
            'critical_alerts': self._stats['critical_alerts'],
            'resolved_alerts': self._stats['resolved_alerts'],
            'active_alerts': len(self.get_active_alerts()),
            'metrics_samples': len(self._metrics_history),
        }
    
    # ==================== 私有方法 ====================
    
    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                # 收集指标
                await self._collect_metrics()
                
                # 检查告警规则
                await self._check_alert_rules()
                
                # 清理历史数据
                self._cleanup_history()
                
                await asyncio.sleep(5)  # 5秒监控间隔
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
    
    async def _collect_metrics(self) -> None:
        """收集指标"""
        metrics = self.get_metrics()
        
        with self._lock:
            self._metrics_history.append(metrics)
            
            if len(self._metrics_history) > self._max_history_size:
                self._metrics_history = self._metrics_history[-self._max_history_size:]
        
        # 记录关键时间序列
        if self._scheduler:
            queue = self._scheduler.get_queue_status()
            self.record_time_series('tasks.pending', queue.get('pending', 0))
            self.record_time_series('tasks.running', queue.get('running', 0))
            self.record_time_series('tasks.completed', queue.get('completed', 0))
        
        if self._node_manager:
            stats = self._node_manager.get_stats()
            local_node = stats.get('local_node', {})
            self.record_time_series('node.cpu_usage', local_node.get('cpu_usage', 0))
            self.record_time_series('node.memory_usage', local_node.get('memory_usage', 0))
    
    async def _check_alert_rules(self) -> None:
        """检查告警规则"""
        for rule in self._alert_rules:
            rule_name = rule['name']
            condition = rule['condition']
            level = rule['level']
            source = rule['source']
            cooldown = rule.get('cooldown', 300)
            
            # 检查冷却
            last_alert = self._alert_cooldowns.get(rule_name)
            if last_alert:
                elapsed = (datetime.now() - last_alert).total_seconds()
                if elapsed < cooldown:
                    continue
            
            # 检查条件
            should_alert = await self._evaluate_condition(condition, source)
            
            if should_alert:
                self.create_alert(
                    level=level,
                    title=f"Alert: {rule_name}",
                    message=f"Condition met: {condition}",
                    source=source,
                    metadata={'rule': rule_name}
                )
                self._alert_cooldowns[rule_name] = datetime.now()
    
    async def _evaluate_condition(self, condition: str, source: str) -> bool:
        """评估告警条件"""
        try:
            # 简单条件解析
            # 格式: "field > value" 或 "field == value"
            
            if '>' in condition:
                field, value_str = condition.split('>')
                field = field.strip()
                value = float(value_str.strip())
                
                # 获取字段值
                value_from_source = self._get_metric_value(field, source)
                return value_from_source is not None and value_from_source > value
            
            elif '==' in condition:
                field, value_str = condition.split('==')
                field = field.strip()
                value = value_str.strip().strip('"\'')
                
                value_from_source = self._get_metric_value(field, source)
                return str(value_from_source) == value
            
            return False
            
        except Exception as e:
            logger.error(f"Condition evaluation error: {e}")
            return False
    
    def _get_metric_value(self, field: str, source: str) -> Optional[float]:
        """获取指标值"""
        if source == 'node' and self._node_manager:
            stats = self._node_manager.get_stats()
            return stats.get('local_node', {}).get(field, 0)
        
        elif source == 'scheduler' and self._scheduler:
            queue = self._scheduler.get_queue_status()
            return queue.get(field, 0)
        
        elif source == 'recovery' and self._recovery_manager:
            stats = self._recovery_manager.get_recovery_stats()
            return stats.get(field, 0)
        
        return None
    
    def _cleanup_history(self) -> None:
        """清理历史数据"""
        with self._lock:
            # 清理过期的告警
            cutoff = datetime.now() - timedelta(days=7)
            resolved_alerts = [
                aid for aid, a in self._alerts.items()
                if a.resolved and a.timestamp < cutoff
            ]
            
            for aid in resolved_alerts:
                del self._alerts[aid]
            
            # 清理指标历史
            cutoff_metrics = datetime.now() - timedelta(hours=24)
            self._metrics_history = [
                m for m in self._metrics_history
                if m.timestamp > cutoff_metrics
            ]


class PrometheusExporter:
    """
    Prometheus指标导出器
    
    将监控数据导出为Prometheus格式
    """
    
    def __init__(self, dashboard: MonitorDashboard):
        self._dashboard = dashboard
        self._metrics_prefix = "hermes_"
    
    def export(self) -> str:
        """导出Prometheus格式指标"""
        lines = []
        metrics = self._dashboard.get_metrics()
        stats = self._dashboard.get_stats_summary()
        
        # 节点指标
        lines.append(f"# HELP {self._metrics_prefix}nodes_total Total number of nodes")
        lines.append(f"# TYPE {self._metrics_prefix}nodes_total gauge")
        lines.append(f"{self._metrics_prefix}nodes_total {metrics.total_nodes}")
        
        lines.append(f"# HELP {self._metrics_prefix}nodes_active Active nodes")
        lines.append(f"# TYPE {self._metrics_prefix}nodes_active gauge")
        lines.append(f"{self._metrics_prefix}nodes_active {metrics.active_nodes}")
        
        # 任务指标
        lines.append(f"# HELP {self._metrics_prefix}tasks_pending Pending tasks")
        lines.append(f"# TYPE {self._metrics_prefix}tasks_pending gauge")
        lines.append(f"{self._metrics_prefix}tasks_pending {metrics.pending_tasks}")
        
        lines.append(f"# HELP {self._metrics_prefix}tasks_running Running tasks")
        lines.append(f"# TYPE {self._metrics_prefix}tasks_running gauge")
        lines.append(f"{self._metrics_prefix}tasks_running {metrics.running_tasks}")
        
        lines.append(f"# HELP {self._metrics_prefix}tasks_completed Completed tasks")
        lines.append(f"# TYPE {self._metrics_prefix}tasks_completed counter")
        lines.append(f"{self._metrics_prefix}tasks_completed {metrics.completed_tasks}")
        
        lines.append(f"# HELP {self._metrics_prefix}tasks_failed Failed tasks")
        lines.append(f"# TYPE {self._metrics_prefix}tasks_failed counter")
        lines.append(f"{self._metrics_prefix}tasks_failed {metrics.failed_tasks}")
        
        # 恢复指标
        lines.append(f"# HELP {self._metrics_prefix}recovery_success_rate Recovery success rate")
        lines.append(f"# TYPE {self._metrics_prefix}recovery_success_rate gauge")
        lines.append(f"{self._metrics_prefix}recovery_success_rate {metrics.recovery_success_rate}")
        
        # 告警指标
        lines.append(f"# HELP {self._metrics_prefix}alerts_active Active alerts")
        lines.append(f"# TYPE {self._metrics_prefix}alerts_active gauge")
        lines.append(f"{self._metrics_prefix}alerts_active {stats['active_alerts']}")
        
        lines.append(f"# HELP {self._metrics_prefix}alerts_total Total alerts")
        lines.append(f"# TYPE {self._metrics_prefix}alerts_total counter")
        lines.append(f"{self._metrics_prefix}alerts_total {stats['total_alerts']}")
        
        return '\n'.join(lines)


# 全局实例
_dashboard: Optional[MonitorDashboard] = None


def get_monitor_dashboard() -> MonitorDashboard:
    """获取监控仪表板实例"""
    global _dashboard
    if _dashboard is None:
        _dashboard = MonitorDashboard()
    return _dashboard
