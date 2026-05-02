"""
Fault Tolerance System - Unified Entry Point
强容错分布式任务处理系统 - 统一入口

整合所有容错组件，提供统一的API接口
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .models import (
    Task, TaskType, TaskStatus, Node, NodeStatus, NodeRole,
    SchedulerConfig, RetryConfig, ConsensusAlgorithm,
    Fault, RecoveryRecord, RecoveryStrategy,
    SystemMetrics, Checkpoint, CheckpointType
)
from .fault_detector import FaultDetector, get_fault_detector
from .distributed_scheduler import DistributedScheduler, ScheduleStrategy, get_scheduler
from .checkpoint_manager import CheckpointManager, get_checkpoint_manager
from .recovery_manager import RecoveryManager, AutomaticRecovery, get_recovery_manager
from .consensus_protocol import ConsensusProtocol, GossipProtocol, RaftProtocol
from .monitor import MonitorDashboard, Alert, AlertLevel, get_monitor_dashboard

# 延迟导入node_manager(需要psutil)
NodeManager = None
get_node_manager = None

logger = logging.getLogger(__name__)

try:
    from .node_manager import NodeManager, get_node_manager
except ImportError:
    logger.warning("psutil not installed, NodeManager not available")

logger = logging.getLogger(__name__)


class FaultToleranceSystem:
    """
    强容错分布式任务处理系统
    
    整合以下组件:
    - 故障检测器 (FaultDetector)
    - 任务调度器 (DistributedScheduler)
    - 检查点管理器 (CheckpointManager)
    - 恢复管理器 (RecoveryManager)
    - 节点管理器 (NodeManager)
    - 监控仪表板 (MonitorDashboard)
    
    使用示例:
    ```python
    # 创建系统
    system = FaultToleranceSystem()
    
    # 启动
    await system.start()
    
    # 提交任务
    task = Task(
        task_type=TaskType.BATCH,
        payload={'data': 'example'}
    )
    task_id = system.submit_task(task)
    
    # 监控状态
    status = system.get_status()
    
    # 停止
    await system.stop()
    ```
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if self._initialized:
            return
        
        self.config = config or {}
        
        # 创建配置
        scheduler_config = SchedulerConfig(**self.config.get('scheduler', {}))
        retry_config = RetryConfig(**self.config.get('retry', {}))
        consensus_algorithm = ConsensusAlgorithm(
            self.config.get('consensus', 'raft')
        )
        
        # 初始化组件
        self._fault_detector = get_fault_detector()
        self._scheduler = get_scheduler(scheduler_config)
        self._checkpoint_manager = get_checkpoint_manager(scheduler_config)
        self._recovery_manager = get_recovery_manager(
            self._checkpoint_manager,
            self._scheduler
        )
        self._monitor = get_monitor_dashboard()
        
        # node_manager需要psutil,尝试加载
        self._node_manager = None
        if get_node_manager is not None:
            self._node_manager = get_node_manager(algorithm=consensus_algorithm)
        else:
            logger.warning("NodeManager not available (psutil not installed)")
        
        # 初始化自动恢复
        self._auto_recovery: Optional[AutomaticRecovery] = None
        
        # 组件绑定
        self._scheduler.set_fault_detector(self._fault_detector)
        self._recovery_manager.set_fault_detector(self._fault_detector)
        self._recovery_manager.set_scheduler(self._scheduler)
        
        self._monitor.bind_fault_detector(self._fault_detector)
        self._monitor.bind_scheduler(self._scheduler)
        self._monitor.bind_checkpoint_manager(self._checkpoint_manager)
        self._monitor.bind_recovery_manager(self._recovery_manager)
        if self._node_manager:
            self._monitor.bind_node_manager(self._node_manager)
        
        # 默认任务处理器
        self._scheduler.set_default_handler(self._default_task_handler)
        
        # 注册故障检测回调
        self._fault_detector.register_callback(self._on_fault_detected)
        
        self._initialized = True
        self._running = False
        
        logger.info("FaultToleranceSystem initialized")
    
    # ==================== 系统生命周期 ====================
    
    async def start(self) -> None:
        """启动系统"""
        if self._running:
            return
        
        self._running = True
        
        # 启动各组件
        if self._node_manager:
            await self._node_manager.start()
        await self._fault_detector.start()
        await self._scheduler.start()
        await self._checkpoint_manager.start()
        
        # 启动自动恢复
        self._auto_recovery = AutomaticRecovery(
            self._fault_detector,
            self._scheduler,
            self._checkpoint_manager
        )
        await self._auto_recovery.start()
        
        # 启动监控
        await self._monitor.start()
        
        logger.info("FaultToleranceSystem started")
    
    async def stop(self) -> None:
        """停止系统"""
        if not self._running:
            return
        
        self._running = False
        
        # 停止各组件
        await self._monitor.stop()
        
        if self._auto_recovery:
            await self._auto_recovery.stop()
        
        await self._checkpoint_manager.stop()
        await self._scheduler.stop()
        await self._fault_detector.stop()
        if self._node_manager:
            await self._node_manager.stop()
        
        logger.info("FaultToleranceSystem stopped")
    
    # ==================== 节点管理 ====================
    
    def get_local_node(self) -> Node:
        """获取本节点"""
        return self._node_manager.get_node()
    
    def get_all_nodes(self) -> List[Node]:
        """获取所有节点"""
        return self._node_manager.get_all_nodes()
    
    def get_active_nodes(self) -> List[Node]:
        """获取活跃节点"""
        return self._node_manager.get_active_nodes()
    
    def add_node(self, node: Node) -> None:
        """添加节点"""
        self._node_manager.register_node(node)
    
    def remove_node(self, node_id: str) -> bool:
        """移除节点"""
        return self._node_manager.unregister_node(node_id)
    
    # ==================== 任务管理 ====================
    
    def submit_task(self, task: Task, handler: Optional[Callable] = None) -> str:
        """
        提交任务
        
        Args:
            task: 任务对象
            handler: 可选的任务处理器
            
        Returns:
            str: 任务ID
        """
        if handler:
            self._scheduler.register_handler(task.task_type.value, handler)
        
        return self._scheduler.submit_task(task)
    
    def submit_tasks(self, tasks: List[Task]) -> List[str]:
        """批量提交任务"""
        return self._scheduler.submit_tasks(tasks)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return self._scheduler.get_task_status(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        return self._scheduler.cancel_task(task_id)
    
    def register_task_callback(self, event: str, callback: Callable) -> None:
        """注册任务回调"""
        self._scheduler.register_callback(event, callback)
    
    # ==================== 检查点管理 ====================
    
    def create_checkpoint(self, task_id: str,
                          checkpoint_type: CheckpointType = CheckpointType.INCREMENTAL,
                          custom_state: Optional[Dict[str, Any]] = None) -> Optional[Checkpoint]:
        """创建检查点"""
        task = self._scheduler.get_task(task_id)
        if not task:
            return None
        
        return self._checkpoint_manager.create_checkpoint(
            task, checkpoint_type, custom_state
        )
    
    def recover_from_checkpoint(self, checkpoint_id: str) -> Optional[Task]:
        """从检查点恢复任务"""
        return self._checkpoint_manager.recover_task(checkpoint_id)
    
    def get_task_checkpoints(self, task_id: str) -> List[Checkpoint]:
        """获取任务所有检查点"""
        return self._checkpoint_manager.get_task_checkpoints(task_id)
    
    # ==================== 故障与恢复 ====================
    
    def get_active_faults(self) -> List[Fault]:
        """获取活跃故障"""
        return self._fault_detector.get_active_faults()
    
    def get_fault_history(self, limit: int = 100) -> List[Fault]:
        """获取故障历史"""
        return self._fault_detector.get_fault_history(limit)
    
    def get_recovery_history(self, limit: int = 100) -> List[RecoveryRecord]:
        """获取恢复历史"""
        return self._recovery_manager.get_recovery_history(limit)
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """获取恢复统计"""
        return self._recovery_manager.get_recovery_stats()
    
    async def trigger_recovery(self, task_id: str, strategy: RecoveryStrategy) -> bool:
        """手动触发恢复"""
        task = self._scheduler.get_task(task_id)
        if not task:
            return False
        
        record = RecoveryRecord(
            fault_type=FaultType.TASK_ERROR,
            strategy=strategy,
            recovered_task_id=task_id
        )
        
        # 根据策略执行
        if strategy == RecoveryStrategy.NODE_TRANSFER:
            return await self._recovery_manager._retry_on_different_node(task)
        elif strategy == RecoveryStrategy.CHECKPOINT_RECOVERY:
            cp = self._checkpoint_manager.get_latest_checkpoint(task_id)
            if cp:
                recovered = self._checkpoint_manager.recover_task(cp.checkpoint_id)
                if recovered:
                    self._scheduler.submit_task(recovered)
                    return True
        
        return False
    
    # ==================== 监控与告警 ====================
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return self._monitor.get_system_status()
    
    def get_system_metrics(self) -> SystemMetrics:
        """获取系统指标"""
        return self._monitor.get_metrics()
    
    def get_active_alerts(self, level: Optional[AlertLevel] = None) -> List[Alert]:
        """获取活跃告警"""
        return self._monitor.get_active_alerts(level)
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        return self._monitor.acknowledge_alert(alert_id)
    
    def register_alert_callback(self, callback: Callable) -> None:
        """注册告警回调"""
        self._monitor.register_alert_callback(callback)
    
    def get_prometheus_metrics(self) -> str:
        """获取Prometheus格式指标"""
        from .monitor import PrometheusExporter
        exporter = PrometheusExporter(self._monitor)
        return exporter.export()
    
    # ==================== 统计与报告 ====================
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return self._scheduler.get_queue_status()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取完整统计"""
        return {
            'system': self.get_system_status(),
            'scheduler': self.get_queue_status(),
            'nodes': self._node_manager.get_stats(),
            'recovery': self.get_recovery_stats(),
            'checkpoints': self._checkpoint_manager.get_stats(),
            'alerts': {
                'active': len(self.get_active_alerts()),
                'total': self._monitor._stats['total_alerts'],
            }
        }
    
    # ==================== 配置 ====================
    
    def set_schedule_strategy(self, strategy: ScheduleStrategy) -> None:
        """设置调度策略"""
        self._scheduler.set_strategy(strategy)
    
    def set_retry_config(self, config: RetryConfig) -> None:
        """设置重试配置"""
        self._recovery_manager.set_retry_config(config)
    
    def set_checkpoint_interval(self, seconds: int) -> None:
        """设置检查点间隔"""
        self.config['scheduler']['checkpoint_interval_seconds'] = seconds
        self._checkpoint_manager.config.checkpoint_interval_seconds = seconds
    
    # ==================== 默认处理器 ====================
    
    async def _default_task_handler(self, task: Task) -> Dict[str, Any]:
        """默认任务处理器"""
        # 模拟任务执行
        import random
        import time
        
        # 更新进度
        for progress in [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
            task.progress = progress
            await asyncio.sleep(0.1)  # 模拟处理
        
        # 模拟可能的任务失败
        if random.random() < 0.05:  # 5%失败率
            raise RuntimeError("Simulated task failure")
        
        return {
            'status': 'completed',
            'result': f"Task {task.task_id} completed successfully",
            'processed_at': datetime.now().isoformat()
        }
    
    def _on_fault_detected(self, fault: Fault) -> None:
        """故障检测回调"""
        logger.warning(
            f"Fault detected: {fault.fault_type.value} - "
            f"Node: {fault.node_id}, Task: {fault.task_id}"
        )
        
        # 可以在这里添加自动响应逻辑
        if fault.node_id and fault.severity in ('high', 'critical'):
            # 触发节点故障处理
            asyncio.create_task(
                self._recovery_manager.handle_node_failure(fault.node_id)
            )


# ==================== 便捷函数 ====================

_system: Optional[FaultToleranceSystem] = None


def get_fault_tolerance_system(config: Optional[Dict[str, Any]] = None) -> FaultToleranceSystem:
    """获取容错系统实例"""
    global _system
    if _system is None:
        _system = FaultToleranceSystem(config)
    return _system


async def quick_submit_task(task_type: str = "batch",
                           payload: Optional[Dict[str, Any]] = None,
                           priority: int = 5) -> str:
    """快速提交任务"""
    system = get_fault_tolerance_system()
    
    task = Task(
        task_type=TaskType(task_type),
        payload=payload or {},
        priority=priority
    )
    
    return system.submit_task(task)


def quick_status() -> Dict[str, Any]:
    """快速获取状态"""
    system = get_fault_tolerance_system()
    return system.get_system_status()
