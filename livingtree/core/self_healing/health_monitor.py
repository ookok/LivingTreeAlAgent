"""
健康监控模块 - 实时监控系统健康指标

功能：
1. 收集系统性能指标
2. 评估健康状态
3. 预测性预警
4. 历史数据追踪
"""

import logging
import time
import threading
import psutil
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    PROCESS = "process"
    CUSTOM = "custom"


class MetricStatus(Enum):
    """指标状态"""
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class HealthMetric:
    """健康指标"""
    name: str
    metric_type: MetricType
    value: float
    threshold: float
    unit: str = ""
    status: MetricStatus = MetricStatus.UNKNOWN
    timestamp: float = None
    history: List[float] = None
    trend: str = "stable"  # increasing/decreasing/stable
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.history is None:
            self.history = []
        
        self._update_status()
        self._update_trend()
    
    def _update_status(self):
        """自动判断状态"""
        if self.value > self.threshold * 1.2:
            self.status = MetricStatus.ERROR
        elif self.value > self.threshold:
            self.status = MetricStatus.WARNING
        else:
            self.status = MetricStatus.HEALTHY
    
    def _update_trend(self):
        """更新趋势"""
        if len(self.history) >= 3:
            recent = self.history[-3:]
            if recent[-1] > recent[0] * 1.1:
                self.trend = "increasing"
            elif recent[-1] < recent[0] * 0.9:
                self.trend = "decreasing"
            else:
                self.trend = "stable"
    
    def update_value(self, value: float):
        """更新值"""
        self.history.append(self.value)
        if len(self.history) > 10:
            self.history = self.history[-10:]
        
        self.value = value
        self.timestamp = time.time()
        self._update_status()
        self._update_trend()
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'type': self.metric_type.value,
            'value': self.value,
            'threshold': self.threshold,
            'unit': self.unit,
            'status': self.status.value,
            'trend': self.trend,
            'timestamp': self.timestamp,
            'history': self.history
        }


class HealthMonitor:
    """
    健康监控器 - 实时监控系统健康状态
    
    监控指标：
    1. CPU使用率
    2. 内存使用率
    3. 磁盘IO
    4. 网络状态
    5. 进程状态
    """
    
    def __init__(self, monitor_interval: int = 5):
        self.monitor_interval = monitor_interval
        self._metrics: Dict[str, HealthMetric] = {}
        self._running = False
        self._thread = None
        self._last_check = 0
        
        # 回调函数
        self._on_metric_update = None
        self._on_status_change = None
        
        # 初始化默认指标
        self._init_default_metrics()
    
    def _init_default_metrics(self):
        """初始化默认监控指标"""
        # CPU指标
        self._metrics['cpu_usage'] = HealthMetric(
            name='cpu_usage',
            metric_type=MetricType.CPU,
            value=0.0,
            threshold=80.0,
            unit='%'
        )
        
        # 内存指标
        self._metrics['memory_usage'] = HealthMetric(
            name='memory_usage',
            metric_type=MetricType.MEMORY,
            value=0.0,
            threshold=85.0,
            unit='%'
        )
        
        # 磁盘使用
        self._metrics['disk_usage'] = HealthMetric(
            name='disk_usage',
            metric_type=MetricType.DISK,
            value=0.0,
            threshold=90.0,
            unit='%'
        )
        
        # 网络发送速率
        self._metrics['network_sent'] = HealthMetric(
            name='network_sent',
            metric_type=MetricType.NETWORK,
            value=0.0,
            threshold=100.0,  # MB/s
            unit='MB/s'
        )
        
        # 网络接收速率
        self._metrics['network_recv'] = HealthMetric(
            name='network_recv',
            metric_type=MetricType.NETWORK,
            value=0.0,
            threshold=100.0,  # MB/s
            unit='MB/s'
        )
    
    def start(self):
        """启动监控线程"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="HealthMonitor"
        )
        self._thread.start()
        logger.info("健康监控器已启动")
    
    def stop(self):
        """停止监控线程"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("健康监控器已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        # 记录上一次网络状态
        net_io_counters = psutil.net_io_counters()
        last_recv = net_io_counters.bytes_recv
        last_sent = net_io_counters.bytes_sent
        last_time = time.time()
        
        while self._running:
            try:
                # 更新CPU指标
                cpu_usage = psutil.cpu_percent(interval=0.1)
                self._metrics['cpu_usage'].update_value(cpu_usage)
                
                # 更新内存指标
                mem = psutil.virtual_memory()
                self._metrics['memory_usage'].update_value(mem.percent)
                
                # 更新磁盘指标
                disk = psutil.disk_usage('/')
                self._metrics['disk_usage'].update_value(disk.percent)
                
                # 更新网络指标
                current_io = psutil.net_io_counters()
                current_time = time.time()
                elapsed = current_time - last_time
                
                if elapsed > 0:
                    recv_mbs = (current_io.bytes_recv - last_recv) / (1024 * 1024 * elapsed)
                    sent_mbs = (current_io.bytes_sent - last_sent) / (1024 * 1024 * elapsed)
                    
                    self._metrics['network_recv'].update_value(recv_mbs)
                    self._metrics['network_sent'].update_value(sent_mbs)
                
                last_recv = current_io.bytes_recv
                last_sent = current_io.bytes_sent
                last_time = current_time
                
                # 触发回调
                if self._on_metric_update:
                    self._on_metric_update(self.get_metrics())
                
                # 检查状态变化
                self._check_status_changes()
                
            except Exception as e:
                logger.error(f"健康监控错误: {e}")
            
            time.sleep(self.monitor_interval)
    
    def _check_status_changes(self):
        """检查状态变化并触发回调"""
        for metric in self._metrics.values():
            if metric.status != MetricStatus.HEALTHY:
                # 发布健康告警事件
                self._publish_health_alert(metric)
                
                if self._on_status_change:
                    self._on_status_change(metric)
    
    def _publish_health_alert(self, metric: HealthMetric):
        """发布健康告警事件"""
        try:
            from livingtree.core.integration import EventType, publish
            
            event_data = {
                'metric_name': metric.name,
                'metric_type': metric.metric_type.value,
                'value': metric.value,
                'threshold': metric.threshold,
                'status': metric.status.value,
                'unit': metric.unit,
                'timestamp': metric.timestamp
            }
            
            publish(EventType.HEALTH_ALERT, 'self_healing', event_data)
        except ImportError:
            pass
    
    def add_custom_metric(self, name: str, metric_type: MetricType, threshold: float, unit: str = ""):
        """添加自定义指标"""
        if name not in self._metrics:
            self._metrics[name] = HealthMetric(
                name=name,
                metric_type=metric_type,
                value=0.0,
                threshold=threshold,
                unit=unit
            )
    
    def update_custom_metric(self, name: str, value: float):
        """更新自定义指标"""
        if name in self._metrics:
            self._metrics[name].update_value(value)
    
    def get_metrics(self) -> Dict[str, Dict]:
        """获取所有指标"""
        return {name: metric.to_dict() for name, metric in self._metrics.items()}
    
    def get_metric(self, name: str) -> Optional[HealthMetric]:
        """获取单个指标"""
        return self._metrics.get(name)
    
    def get_overall_status(self) -> MetricStatus:
        """获取整体健康状态"""
        error_count = sum(1 for m in self._metrics.values() if m.status == MetricStatus.ERROR)
        warning_count = sum(1 for m in self._metrics.values() if m.status == MetricStatus.WARNING)
        
        if error_count > 0:
            return MetricStatus.ERROR
        elif warning_count > 0:
            return MetricStatus.WARNING
        else:
            return MetricStatus.HEALTHY
    
    def get_summary(self) -> Dict:
        """获取健康摘要"""
        return {
            'overall_status': self.get_overall_status().value,
            'metrics': self.get_metrics(),
            'timestamp': time.time(),
            'monitoring': self._running
        }
    
    def set_callback(self, on_metric_update=None, on_status_change=None):
        """设置回调函数"""
        self._on_metric_update = on_metric_update
        self._on_status_change = on_status_change