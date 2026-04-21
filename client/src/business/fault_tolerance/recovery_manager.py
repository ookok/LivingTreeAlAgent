"""
Fault Tolerance System - Recovery Manager
强容错分布式任务处理系统 - 恢复管理器

实现多层恢复策略：自动重试、节点转移、检查点恢复
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from threading import Lock

from .models import (
    Task, TaskStatus, TaskType, Node, NodeStatus,
    Fault, FaultType, RecoveryStrategy, RecoveryRecord,
    ReplicaStrategy, RetryConfig
)
from .checkpoint_manager import CheckpointManager, get_checkpoint_manager
from .distributed_scheduler import DistributedScheduler

if TYPE_CHECKING:
    from .fault_detector import FaultDetector

logger = logging.getLogger(__name__)


class RecoveryManager:
    """
    恢复管理器
    
    实现五层恢复策略:
    1. 快速重试 (毫秒级) - 同一节点重试
    2. 转移重试 (秒级) - 不同节点重试
    3. 降级重试 (分级) - 降低要求重试
    4. 检查点恢复 - 从检查点恢复
    5. 人工干预 - 通知用户
    """
    
    def __init__(self, 
                 checkpoint_manager: Optional[CheckpointManager] = None,
                 scheduler: Optional[DistributedScheduler] = None):
        self._checkpoint_manager = checkpoint_manager or get_checkpoint_manager()
        self._scheduler = scheduler
        self._fault_detector: Optional['FaultDetector'] = None
        
        # 重试配置
        self._retry_config = RetryConfig()
        
        # 恢复记录
        self._recovery_records: List[RecoveryRecord] = []
        self._active_recoveries: Dict[str, RecoveryRecord] = {}
        
        # 回调函数
        self._recovery_callbacks: Dict[RecoveryStrategy, List[Callable]] = {
            strategy: [] for strategy in RecoveryStrategy
        }
        self._global_callbacks: List[Callable] = []
        
        # 锁
        self._lock = Lock()
        
        # 统计
        self.total_recoveries = 0
        self.successful_recoveries = 0
        self.failed_recoveries = 0
    
    # ==================== 公共API ====================
    
    def set_fault_detector(self, detector: 'FaultDetector') -> None:
        """设置故障检测器"""
        self._fault_detector = detector
    
    def set_scheduler(self, scheduler: DistributedScheduler) -> None:
        """设置调度器"""
        self._scheduler = scheduler
    
    def set_retry_config(self, config: RetryConfig) -> None:
        """设置重试配置"""
        self._retry_config = config
    
    def register_recovery_callback(self, 
                                  strategy: RecoveryStrategy,
                                  callback: Callable) -> None:
        """注册恢复策略回调"""
        self._recovery_callbacks[strategy].append(callback)
    
    def register_global_callback(self, callback: Callable) -> None:
        """注册全局恢复回调"""
        self._global_callbacks.append(callback)
    
    async def handle_task_failure(self, task: Task, error: str) -> bool:
        """
        处理任务失败
        
        Args:
            task: 失败的任务
            error: 错误信息
            
        Returns:
            bool: 是否成功恢复
        """
        start_time = datetime.now()
        
        # 创建恢复记录
        record = RecoveryRecord(
            fault_type=self._classify_fault(error),
            recovered_task_id=task.task_id,
            details={
                'error': error,
                'retry_count': task.retry_count,
                'task_type': task.task_type.value,
            }
        )
        
        with self._lock:
            self._active_recoveries[task.task_id] = record
            self.total_recoveries += 1
        
        logger.info(f"Handling task failure: {task.task_id} - {error}")
        
        # 按层级尝试恢复
        success = await self._try_recovery_layers(task, error, record)
        
        # 更新记录
        with self._lock:
            record.is_success = success
            record.completed_at = datetime.now()
            record.recovery_time_ms = int(
                (record.completed_at - start_time).total_seconds() * 1000
            )
            
            if task.task_id in self._active_recoveries:
                del self._active_recoveries[task.task_id]
            
            self._recovery_records.append(record)
            
            if success:
                self.successful_recoveries += 1
            else:
                self.failed_recoveries += 1
        
        # 触发全局回调
        for callback in self._global_callbacks:
            try:
                await callback(record)
            except Exception as e:
                logger.error(f"Global callback error: {e}")
        
        return success
    
    async def handle_node_failure(self, node_id: str) -> int:
        """
        处理节点故障
        
        Args:
            node_id: 故障节点ID
            
        Returns:
            int: 成功迁移的任务数
        """
        logger.warning(f"Handling node failure: {node_id}")
        
        if not self._scheduler:
            logger.error("No scheduler available for recovery")
            return 0
        
        # 获取该节点上的任务
        running_tasks = []
        for task in list(self._scheduler._running_tasks.values()):
            if task.assigned_node == node_id:
                running_tasks.append(task)
        
        # 迁移所有任务
        migrated = 0
        for task in running_tasks:
            # 尝试检查点恢复
            latest_cp = self._checkpoint_manager.get_latest_checkpoint(task.task_id)
            
            if latest_cp and task.retry_count < task.max_retries:
                # 从检查点恢复
                recovered_task = self._checkpoint_manager.recover_task(latest_cp.checkpoint_id)
                if recovered_task:
                    # 更新恢复记录
                    record = RecoveryRecord(
                        fault_type=FaultType.NODE_PERMANENT,
                        strategy=RecoveryStrategy.CHECKPOINT_RECOVERY,
                        source_node=node_id,
                        recovered_task_id=recovered_task.task_id,
                        checkpoint_id=latest_cp.checkpoint_id
                    )
                    self._recovery_records.append(record)
                    
                    # 重新提交任务
                    self._scheduler.submit_task(recovered_task)
                    migrated += 1
            else:
                # 无检查点，放弃任务
                logger.warning(f"No checkpoint for task {task.task_id}, task will fail")
        
        logger.info(f"Node failure handled: {node_id}, {migrated} tasks migrated")
        return migrated
    
    async def handle_network_partition(self, partition_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理网络分区
        
        Args:
            partition_info: 分区信息
            
        Returns:
            Dict: 处理结果
        """
        primary_nodes = partition_info.get('primary_nodes', [])
        secondary_nodes = partition_info.get('secondary_nodes', [])
        
        result = {
            'action': 'none',
            'affected_tasks': 0,
            'preserved_tasks': 0,
        }
        
        # 策略：多数派继续服务，少数派暂停
        if len(primary_nodes) > len(secondary_nodes):
            # 少数派暂停正在进行的任务
            if self._scheduler:
                paused = 0
                for task in list(self._scheduler._running_tasks.values()):
                    if task.assigned_node in secondary_nodes:
                        task.status = TaskStatus.PENDING
                        task.error_message = "Network partition - task paused"
                        self._scheduler._pending_tasks.append(task)
                        paused += 1
                
                result['action'] = 'paused_secondary'
                result['affected_tasks'] = paused
        
        logger.info(f"Network partition handled: {result}")
        return result
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """获取恢复统计"""
        with self._lock:
            total = len(self._recovery_records)
            successful = sum(1 for r in self._recovery_records if r.is_success)
            
            avg_recovery_time = 0
            if self._recovery_records:
                avg_recovery_time = sum(
                    r.recovery_time_ms for r in self._recovery_records
                ) / len(self._recovery_records)
            
            # 按策略统计
            strategy_stats = {}
            for strategy in RecoveryStrategy:
                records = [r for r in self._recovery_records if r.strategy == strategy]
                if records:
                    success_count = sum(1 for r in records if r.is_success)
                    strategy_stats[strategy.value] = {
                        'total': len(records),
                        'success': success_count,
                        'rate': success_count / len(records) if records else 0,
                    }
            
            return {
                'total_recoveries': self.total_recoveries,
                'successful_recoveries': self.successful_recoveries,
                'failed_recoveries': self.failed_recoveries,
                'success_rate': self.successful_recoveries / self.total_recoveries if self.total_recoveries > 0 else 0,
                'avg_recovery_time_ms': avg_recovery_time,
                'active_recoveries': len(self._active_recoveries),
                'strategy_stats': strategy_stats,
            }
    
    def get_recovery_history(self, limit: int = 100) -> List[RecoveryRecord]:
        """获取恢复历史"""
        with self._lock:
            return sorted(
                self._recovery_records,
                key=lambda r: r.started_at,
                reverse=True
            )[:limit]
    
    # ==================== 私有方法 ====================
    
    async def _try_recovery_layers(self, task: Task, error: str,
                                   record: RecoveryRecord) -> bool:
        """尝试各层恢复策略"""
        
        # Layer 1: 快速重试 (同一节点)
        if task.retry_count < self._retry_config.fast_retries:
            record.strategy = RecoveryStrategy.AUTO_RETRY
            
            delay = self._retry_config.get_delay(task.retry_count, "fast")
            if delay > 0:
                await asyncio.sleep(delay / 1000)
            
            if await self._retry_on_same_node(task):
                await self._trigger_callbacks(RecoveryStrategy.AUTO_RETRY, task, record)
                return True
        
        # Layer 2: 转移重试 (不同节点)
        if task.retry_count < self._retry_config.fast_retries + self._retry_config.transfer_retries:
            record.strategy = RecoveryStrategy.NODE_TRANSFER
            
            delay = self._retry_config.get_delay(task.retry_count, "transfer")
            await asyncio.sleep(delay)
            
            if await self._retry_on_different_node(task):
                await self._trigger_callbacks(RecoveryStrategy.NODE_TRANSFER, task, record)
                return True
        
        # Layer 3: 降级重试
        if task.retry_count < (self._retry_config.fast_retries + 
                               self._retry_config.transfer_retries +
                               self._retry_config.degraded_retries):
            record.strategy = RecoveryStrategy.DEGRADED_MODE
            
            if await self._retry_with_degraded_mode(task):
                await self._trigger_callbacks(RecoveryStrategy.DEGRADED_MODE, task, record)
                return True
        
        # Layer 4: 检查点恢复
        latest_cp = self._checkpoint_manager.get_latest_checkpoint(task.task_id)
        if latest_cp:
            record.strategy = RecoveryStrategy.CHECKPOINT_RECOVERY
            record.checkpoint_id = latest_cp.checkpoint_id
            
            recovered_task = self._checkpoint_manager.recover_task(latest_cp.checkpoint_id)
            if recovered_task and self._scheduler:
                record.recovered_task_id = recovered_task.task_id
                self._scheduler.submit_task(recovered_task)
                await self._trigger_callbacks(RecoveryStrategy.CHECKPOINT_RECOVERY, task, record)
                return True
        
        # Layer 5: 人工干预
        record.strategy = RecoveryStrategy.MANUAL_INTERVENTION
        logger.warning(f"Task {task.task_id} requires manual intervention")
        await self._trigger_callbacks(RecoveryStrategy.MANUAL_INTERVENTION, task, record)
        
        return False
    
    async def _retry_on_same_node(self, task: Task) -> bool:
        """在同一节点重试"""
        if not self._scheduler or not task.assigned_node:
            return False
        
        # 检查节点是否恢复
        node = self._scheduler._nodes.get(task.assigned_node)
        if node and node.status == NodeStatus.ACTIVE:
            task.status = TaskStatus.RETRYING
            task.updated_at = datetime.now()
            
            # 直接重新执行
            asyncio.create_task(self._scheduler._execute_task(task, node))
            logger.info(f"Retry on same node: {task.task_id} on {node.node_id}")
            return True
        
        return False
    
    async def _retry_on_different_node(self, task: Task) -> bool:
        """在不同节点重试"""
        if not self._scheduler:
            return False
        
        # 获取活跃节点
        active_nodes = [
            n for n in self._scheduler._nodes.values()
            if n.status == NodeStatus.ACTIVE and n.node_id != task.assigned_node
        ]
        
        if not active_nodes:
            return False
        
        # 选择最佳节点
        best_node = min(
            active_nodes,
            key=lambda n: (n.cpu_usage, n.memory_usage)
        )
        
        task.status = TaskStatus.RETRYING
        task.assigned_node = best_node.node_id
        task.updated_at = datetime.now()
        
        asyncio.create_task(self._scheduler._execute_task(task, best_node))
        logger.info(f"Retry on different node: {task.task_id} on {best_node.node_id}")
        return True
    
    async def _retry_with_degraded_mode(self, task: Task) -> bool:
        """降级模式重试"""
        if not self._scheduler:
            return False
        
        # 降低任务要求
        original_type = task.task_type
        
        # 根据任务类型降级
        if task.task_type == TaskType.COMPUTE_INTENSIVE:
            task.task_type = TaskType.BATCH  # 降低CPU要求
        elif task.task_type == TaskType.MEMORY_INTENSIVE:
            task.task_type = TaskType.IO_INTENSIVE  # 降低内存要求
        
        # 增加超时时间
        if 'timeout' in task.metadata:
            task.metadata['timeout'] *= 2
        
        # 重置状态
        task.status = TaskStatus.RETRYING
        task.updated_at = datetime.now()
        
        # 尝试在不同节点执行
        return await self._retry_on_different_node(task)
    
    def _classify_fault(self, error: str) -> FaultType:
        """分类故障类型"""
        error_lower = error.lower()
        
        if 'timeout' in error_lower:
            return FaultType.TASK_TIMEOUT
        elif 'network' in error_lower or 'connection' in error_lower:
            return FaultType.NETWORK_TEMPORARY
        elif 'memory' in error_lower or 'oom' in error_lower:
            return FaultType.STORAGE_FAILURE
        else:
            return FaultType.TASK_ERROR
    
    async def _trigger_callbacks(self, strategy: RecoveryStrategy,
                                 task: Task, record: RecoveryRecord) -> None:
        """触发策略回调"""
        callbacks = self._recovery_callbacks.get(strategy, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task, record)
                else:
                    callback(task, record)
            except Exception as e:
                logger.error(f"Recovery callback error: {e}")


class AutomaticRecovery:
    """
    自动恢复处理器
    
    集成故障检测、任务调度、检查点管理的自动恢复
    """
    
    def __init__(self,
                 fault_detector: 'FaultDetector',
                 scheduler: DistributedScheduler,
                 checkpoint_manager: CheckpointManager):
        self._fault_detector = fault_detector
        self._scheduler = scheduler
        self._checkpoint_manager = checkpoint_manager
        
        # 创建恢复管理器
        self._recovery_manager = RecoveryManager(
            checkpoint_manager=checkpoint_manager,
            scheduler=scheduler
        )
        self._recovery_manager.set_fault_detector(fault_detector)
        
        # 注册故障检测回调
        self._fault_detector.register_callback(self._on_fault_detected)
        
        # 状态
        self._running = False
        self._recovery_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """启动自动恢复"""
        if self._running:
            return
        
        self._running = True
        self._recovery_task = asyncio.create_task(self._recovery_loop())
        logger.info("Automatic recovery started")
    
    async def stop(self) -> None:
        """停止自动恢复"""
        self._running = False
        if self._recovery_task:
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass
        logger.info("Automatic recovery stopped")
    
    def _on_fault_detected(self, fault: Fault) -> None:
        """故障检测回调"""
        logger.warning(f"Fault detected for automatic recovery: {fault.fault_type.value}")
        
        if fault.node_id:
            asyncio.create_task(self._recovery_manager.handle_node_failure(fault.node_id))
    
    async def _recovery_loop(self) -> None:
        """恢复循环"""
        while self._running:
            try:
                # 检查活跃故障
                active_faults = self._fault_detector.get_active_faults()
                
                for fault in active_faults:
                    if fault.node_id and not fault.is_resolved:
                        # 尝试处理节点故障
                        await self._recovery_manager.handle_node_failure(fault.node_id)
                
                await asyncio.sleep(1)  # 每秒检查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Recovery loop error: {e}")


# 全局实例
_recovery_manager: Optional[RecoveryManager] = None


def get_recovery_manager(
    checkpoint_manager: Optional[CheckpointManager] = None,
    scheduler: Optional[DistributedScheduler] = None
) -> RecoveryManager:
    """获取恢复管理器实例"""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = RecoveryManager(checkpoint_manager, scheduler)
    return _recovery_manager
