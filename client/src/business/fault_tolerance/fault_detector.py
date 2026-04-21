"""
Fault Tolerance System - Fault Detector
强容错分布式任务处理系统 - 多维度故障检测器

实现网络层、节点层、任务层的多维度故障检测
"""

import asyncio
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
from threading import Lock

from .models import (
    Node, NodeStatus, NodeRole, Fault, FaultType,
    Task, TaskStatus, SystemMetrics
)


logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    node_id: str
    is_healthy: bool
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 检测详情
    network_latency_ms: float = 0.0
    packet_loss_rate: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    
    # 异常指标
    anomalies: List[str] = field(default_factory=list)
    confidence: float = 1.0  # 置信度 0-1


class HeartbeatMonitor:
    """心跳监测器"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.last_heartbeat: Optional[datetime] = None
        self.heartbeat_count: int = 0
        self.failed_heartbeats: int = 0
        self.consecutive_failures: int = 0
        
        # 历史数据
        self.latency_history: List[float] = []
        self.max_history_size = 100
        
        # 状态
        self._lock = Lock()
    
    def record_heartbeat(self, latency_ms: float = 0.0) -> None:
        """记录心跳"""
        with self._lock:
            self.last_heartbeat = datetime.now()
            self.heartbeat_count += 1
            self.consecutive_failures = 0
            self.failed_heartbeats = 0
            
            self.latency_history.append(latency_ms)
            if len(self.latency_history) > self.max_history_size:
                self.latency_history.pop(0)
    
    def record_failure(self) -> None:
        """记录失败"""
        with self._lock:
            self.failed_heartbeats += 1
            self.consecutive_failures += 1
    
    def get_avg_latency(self) -> float:
        """获取平均延迟"""
        with self._lock:
            if not self.latency_history:
                return 0.0
            return sum(self.latency_history) / len(self.latency_history)
    
    def is_suspicious(self, threshold: int = 3) -> bool:
        """是否可疑"""
        with self._lock:
            return self.consecutive_failures >= threshold


class FaultDetector:
    """
    多维度故障检测器
    
    实现三层检测:
    1. 网络层检测 - 心跳、延迟、丢包
    2. 节点层检测 - 资源、进程、服务
    3. 任务层检测 - 进度、超时、结果
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # 检测阈值
        self.heartbeat_interval = self.config.get('heartbeat_interval', 1.0)  # 秒
        self.heartbeat_timeout = self.config.get('heartbeat_timeout', 5.0)  # 秒
        self.suspicious_threshold = self.config.get('suspicious_threshold', 3)  # 连续失败次数
        self.failure_threshold = self.config.get('failure_threshold', 5)  # 确认故障次数
        
        # 节点监控
        self._monitors: Dict[str, HeartbeatMonitor] = {}
        self._nodes: Dict[str, Node] = {}
        self._lock = Lock()
        
        # 故障记录
        self._faults: Dict[str, Fault] = {}
        self._fault_history: List[Fault] = []
        
        # 回调函数
        self._fault_callbacks: List[Callable[[Fault], None]] = []
        
        # 统计
        self.total_faults_detected = 0
        self.total_false_positives = 0
        
        # 状态
        self._running = False
        self._detection_task: Optional[asyncio.Task] = None
    
    # ==================== 公共API ====================
    
    def register_node(self, node: Node) -> None:
        """注册节点"""
        with self._lock:
            self._nodes[node.node_id] = node
            self._monitors[node.node_id] = HeartbeatMonitor(node.node_id)
            logger.info(f"Node registered: {node.node_id}")
    
    def unregister_node(self, node_id: str) -> None:
        """注销节点"""
        with self._lock:
            self._nodes.pop(node_id, None)
            self._monitors.pop(node_id, None)
            logger.info(f"Node unregistered: {node_id}")
    
    def record_heartbeat(self, node_id: str, latency_ms: float = 0.0) -> None:
        """记录节点心跳"""
        with self._lock:
            if node_id not in self._monitors:
                monitor = HeartbeatMonitor(node_id)
                self._monitors[node_id] = monitor
            
            self._monitors[node_id].record_heartbeat(latency_ms)
            
            # 更新节点状态
            if node_id in self._nodes:
                self._nodes[node_id].last_heartbeat = datetime.now()
                self._nodes[node_id].status = NodeStatus.ACTIVE
    
    def record_task_failure(self, task: Task, error: str) -> None:
        """记录任务失败"""
        fault = Fault(
            fault_type=FaultType.TASK_ERROR,
            task_id=task.task_id,
            node_id=task.assigned_node,
            description=error,
            severity=self._calculate_severity(error)
        )
        self._record_fault(fault)
    
    def record_task_timeout(self, task: Task) -> None:
        """记录任务超时"""
        fault = Fault(
            fault_type=FaultType.TASK_TIMEOUT,
            task_id=task.task_id,
            node_id=task.assigned_node,
            description=f"Task {task.task_id} timeout after {task.metadata.get('timeout', 'unknown')}s",
            severity="high"
        )
        self._record_fault(fault)
    
    def register_callback(self, callback: Callable[[Fault], None]) -> None:
        """注册故障回调"""
        self._fault_callbacks.append(callback)
    
    def get_node_health(self, node_id: str) -> HealthCheckResult:
        """获取节点健康状态"""
        with self._lock:
            monitor = self._monitors.get(node_id)
            node = self._nodes.get(node_id)
            
            if not monitor or not node:
                return HealthCheckResult(node_id=node_id, is_healthy=False)
            
            anomalies = []
            
            # 检查心跳
            if monitor.consecutive_failures >= self.suspicious_threshold:
                anomalies.append(f"Heartbeat failures: {monitor.consecutive_failures}")
            
            # 检查延迟
            avg_latency = monitor.get_avg_latency()
            if avg_latency > 1000:  # > 1秒
                anomalies.append(f"High latency: {avg_latency:.2f}ms")
            
            # 检查资源
            if node.cpu_usage > 90:
                anomalies.append(f"High CPU: {node.cpu_usage:.1f}%")
            if node.memory_usage > 90:
                anomalies.append(f"High memory: {node.memory_usage:.1f}%")
            
            is_healthy = len(anomalies) == 0 and monitor.consecutive_failures < self.suspicious_threshold
            
            return HealthCheckResult(
                node_id=node_id,
                is_healthy=is_healthy,
                network_latency_ms=avg_latency,
                cpu_usage=node.cpu_usage,
                memory_usage=node.memory_usage,
                anomalies=anomalies,
                confidence=self._calculate_confidence(monitor, anomalies)
            )
    
    def get_active_faults(self) -> List[Fault]:
        """获取活跃故障"""
        with self._lock:
            return [f for f in self._faults.values() if not f.is_resolved]
    
    def get_fault_history(self, limit: int = 100) -> List[Fault]:
        """获取故障历史"""
        with self._lock:
            return sorted(self._fault_history, 
                         key=lambda x: x.created_at, 
                         reverse=True)[:limit]
    
    def get_system_metrics(self) -> SystemMetrics:
        """获取系统指标"""
        with self._lock:
            metrics = SystemMetrics()
            
            metrics.total_nodes = len(self._nodes)
            metrics.active_nodes = sum(
                1 for n in self._nodes.values() 
                if n.status == NodeStatus.ACTIVE
            )
            metrics.failed_nodes = sum(
                1 for n in self._nodes.values() 
                if n.status in (NodeStatus.PERMANENT_FAILURE, NodeStatus.OFFLINE)
            )
            
            metrics.active_faults = len([f for f in self._faults.values() if not f.is_resolved])
            metrics.resolved_faults = sum(1 for f in self._fault_history if f.is_resolved)
            
            return metrics
    
    async def start(self) -> None:
        """启动检测"""
        if self._running:
            return
        
        self._running = True
        self._detection_task = asyncio.create_task(self._detection_loop())
        logger.info("Fault detector started")
    
    async def stop(self) -> None:
        """停止检测"""
        self._running = False
        if self._detection_task:
            self._detection_task.cancel()
            try:
                await self._detection_task
            except asyncio.CancelledError:
                pass
        logger.info("Fault detector stopped")
    
    # ==================== 私有方法 ====================
    
    def _record_fault(self, fault: Fault) -> None:
        """记录故障"""
        with self._lock:
            self._faults[fault.fault_id] = fault
            self._fault_history.append(fault)
            self.total_faults_detected += 1
            
            # 限制历史记录大小
            if len(self._fault_history) > 1000:
                self._fault_history = self._fault_history[-500:]
        
        # 触发回调
        for callback in self._fault_callbacks:
            try:
                callback(fault)
            except Exception as e:
                logger.error(f"Fault callback error: {e}")
        
        logger.warning(f"Fault detected: {fault.fault_type.value} - {fault.description}")
    
    def _calculate_severity(self, error: str) -> str:
        """计算严重程度"""
        error_lower = error.lower()
        
        if any(kw in error_lower for kw in ['critical', 'fatal', 'corruption']):
            return 'critical'
        elif any(kw in error_lower for kw in ['error', 'fail', 'exception']):
            return 'high'
        elif any(kw in error_lower for kw in ['warn', 'warning']):
            return 'medium'
        else:
            return 'low'
    
    def _calculate_confidence(self, monitor: HeartbeatMonitor, anomalies: List[str]) -> float:
        """计算置信度"""
        confidence = 1.0
        
        # 基于连续失败次数降低置信度
        if monitor.consecutive_failures >= self.failure_threshold:
            confidence = 0.9
        elif monitor.consecutive_failures >= self.suspicious_threshold:
            confidence = 0.7
        
        # 基于异常数量降低置信度
        if len(anomalies) > 3:
            confidence *= 0.8
        elif len(anomalies) > 1:
            confidence *= 0.9
        
        return confidence
    
    async def _detection_loop(self) -> None:
        """检测循环"""
        while self._running:
            try:
                await self._check_nodes()
                await self._check_tasks()
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Detection loop error: {e}")
    
    async def _check_nodes(self) -> None:
        """检查节点"""
        now = datetime.now()
        timeout = timedelta(seconds=self.heartbeat_timeout)
        
        with self._lock:
            for node_id, monitor in self._monitors.items():
                node = self._nodes.get(node_id)
                if not node:
                    continue
                
                # 检查心跳超时
                if monitor.last_heartbeat:
                    elapsed = now - monitor.last_heartbeat
                    if elapsed > timeout:
                        monitor.record_failure()
                        
                        if monitor.consecutive_failures == self.suspicious_threshold:
                            # 进入可疑状态
                            node.status = NodeStatus.SUSPECTED
                            logger.warning(f"Node {node_id} marked as suspicious")
                        
                        elif monitor.consecutive_failures >= self.failure_threshold:
                            # 确认故障
                            node.status = NodeStatus.TEMPORARY_FAILURE
                            fault = Fault(
                                fault_type=FaultType.NODE_TEMPORARY,
                                node_id=node_id,
                                description=f"Node {node_id} heartbeat timeout after {monitor.consecutive_failures} attempts",
                                severity="high"
                            )
                            self._record_fault(fault)
    
    async def _check_tasks(self) -> None:
        """检查任务"""
        # 任务超时检查由调度器负责
        pass


class AdaptiveThresholdDetector:
    """
    自适应阈值检测器
    
    基于历史数据动态调整检测阈值
    """
    
    def __init__(self):
        self._baseline: Dict[str, List[float]] = defaultdict(list)
        self._max_baseline_size = 1000
        
        # 动态阈值
        self._thresholds: Dict[str, float] = {
            'latency': 1000.0,      # 毫秒
            'cpu': 90.0,            # 百分比
            'memory': 90.0,         # 百分比
            'packet_loss': 5.0,     # 百分比
        }
        
        # 调整因子
        self._adjustment_factor = 0.1
    
    def record_baseline(self, metric_name: str, value: float) -> None:
        """记录基线数据"""
        self._baseline[metric_name].append(value)
        if len(self._baseline[metric_name]) > self._max_baseline_size:
            self._baseline[metric_name].pop(0)
    
    def get_threshold(self, metric_name: str) -> float:
        """获取动态阈值"""
        if metric_name not in self._baseline:
            return self._thresholds.get(metric_name, 1000.0)
        
        values = self._baseline[metric_name]
        if len(values) < 10:
            return self._thresholds.get(metric_name, 1000.0)
        
        # 计算平均值和标准差
        import statistics
        avg = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0
        
        # 动态阈值 = 平均值 + 2*标准差
        dynamic_threshold = avg + 2 * std
        
        # 与默认阈值取较大值
        default = self._thresholds.get(metric_name, 1000.0)
        return max(dynamic_threshold, default)
    
    def is_anomaly(self, metric_name: str, value: float) -> bool:
        """判断是否异常"""
        threshold = self.get_threshold(metric_name)
        return value > threshold
    
    def update_threshold(self, metric_name: str, new_value: float) -> None:
        """更新阈值"""
        self._thresholds[metric_name] = new_value


# 全局实例
_detector: Optional[FaultDetector] = None


def get_fault_detector(config: Optional[Dict[str, Any]] = None) -> FaultDetector:
    """获取故障检测器实例"""
    global _detector
    if _detector is None:
        _detector = FaultDetector(config)
    return _detector
