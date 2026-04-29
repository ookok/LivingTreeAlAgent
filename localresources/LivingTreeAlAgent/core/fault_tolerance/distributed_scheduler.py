"""
Fault Tolerance System - Distributed Scheduler
强容错分布式任务处理系统 - 智能任务调度器

实现任务分配、负载均衡、优先级调度
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from collections import defaultdict

from .models import (
    Task, TaskStatus, TaskType, Node, NodeStatus, NodeRole,
    SchedulerConfig, ReplicaStrategy, Fault, FaultType
)
from .fault_detector import FaultDetector, get_fault_detector


logger = logging.getLogger(__name__)


class ScheduleStrategy(Enum):
    """调度策略"""
    FIFO = "fifo"                 # 先进先出
    PRIORITY = "priority"         # 优先级优先
    LOAD_BALANCE = "load_balance"  # 负载均衡
    AFFINITY = "affinity"         # 亲和性调度
    MIN_MIN = "min_min"           # 最早完成优先
    SUICIDE = "suicide"           # 资源最少优先


@dataclass
class TaskMetrics:
    """任务指标"""
    task_id: str
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: int = 0
    wait_time_ms: int = 0
    retries: int = 0
    node_id: Optional[str] = None


class DistributedScheduler:
    """
    分布式任务调度器
    
    特性:
    - 智能任务分配 (基于节点评分)
    - 多种调度策略
    - 负载均衡
    - 亲和性调度
    - 任务抢占
    - 工作窃取
    """
    
    def __init__(self, config: Optional[SchedulerConfig] = None):
        self.config = config or SchedulerConfig()
        
        # 任务队列
        self._pending_tasks: List[Task] = []
        self._running_tasks: Dict[str, Task] = {}
        self._completed_tasks: Dict[str, Task] = {}
        self._failed_tasks: Dict[str, Task] = {}
        
        # 节点管理
        self._nodes: Dict[str, Node] = {}
        self._node_tasks: Dict[str, Set[str]] = defaultdict(set)  # node_id -> task_ids
        
        # 任务指标
        self._task_metrics: Dict[str, TaskMetrics] = {}
        
        # 任务处理器
        self._handlers: Dict[str, Callable] = {}
        self._default_handler: Optional[Callable] = None
        
        # 回调函数
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        # 故障检测器
        self._fault_detector: Optional[FaultDetector] = None
        
        # 锁
        self._lock = Lock()
        
        # 统计
        self.total_scheduled = 0
        self.total_completed = 0
        self.total_failed = 0
        
        # 调度策略
        self._strategy = ScheduleStrategy.PRIORITY
        
        # 状态
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
    
    # ==================== 公共API ====================
    
    def set_fault_detector(self, detector: FaultDetector) -> None:
        """设置故障检测器"""
        self._fault_detector = detector
    
    def register_handler(self, task_type: str, handler: Callable) -> None:
        """注册任务处理器"""
        self._handlers[task_type] = handler
        logger.info(f"Handler registered for task type: {task_type}")
    
    def set_default_handler(self, handler: Callable) -> None:
        """设置默认处理器"""
        self._default_handler = handler
    
    def register_callback(self, event: str, callback: Callable) -> None:
        """注册事件回调"""
        self._callbacks[event].append(callback)
    
    def register_node(self, node: Node) -> None:
        """注册节点"""
        with self._lock:
            self._nodes[node.node_id] = node
            logger.info(f"Node registered: {node.node_id} ({node.role.value})")
    
    def unregister_node(self, node_id: str) -> None:
        """注销节点"""
        with self._lock:
            node = self._nodes.pop(node_id, None)
            if node:
                # 将节点上的任务转移到其他节点
                tasks = self._node_tasks.pop(node_id, set())
                for task_id in tasks:
                    self._migrate_task(task_id)
                logger.info(f"Node unregistered: {node_id}")
    
    def update_node_status(self, node_id: str, status: NodeStatus) -> None:
        """更新节点状态"""
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].status = status
                self._nodes[node_id].updated_at = datetime.now()
                
                if status == NodeStatus.PERMANENT_FAILURE:
                    # 处理节点永久故障
                    self._handle_node_failure(node_id)
    
    def update_node_resources(self, node_id: str, 
                             cpu_usage: float, memory_usage: float,
                             active_tasks: int) -> None:
        """更新节点资源使用"""
        with self._lock:
            if node_id in self._nodes:
                node = self._nodes[node_id]
                node.cpu_usage = cpu_usage
                node.memory_usage = memory_usage
                node.active_tasks = active_tasks
                node.updated_at = datetime.now()
    
    def submit_task(self, task: Task, handler: Optional[Callable] = None) -> str:
        """提交任务"""
        with self._lock:
            task.status = TaskStatus.PENDING
            task.created_at = datetime.now()
            task.updated_at = datetime.now()
            
            self._pending_tasks.append(task)
            self._pending_tasks.sort(key=lambda t: (
                -t.priority,
                t.created_at
            ))
            
            self._task_metrics[task.task_id] = TaskMetrics(
                task_id=task.task_id,
                scheduled_at=datetime.now()
            )
            
            self.total_scheduled += 1
            logger.info(f"Task submitted: {task.task_id} (priority={task.priority})")
            
            return task.task_id
    
    def submit_tasks(self, tasks: List[Task]) -> List[str]:
        """批量提交任务"""
        task_ids = []
        for task in tasks:
            task_ids.append(self.submit_task(task))
        return task_ids
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            # 从待处理队列移除
            for i, task in enumerate(self._pending_tasks):
                if task.task_id == task_id:
                    task.status = TaskStatus.CANCELLED
                    self._pending_tasks.pop(i)
                    logger.info(f"Task cancelled: {task_id}")
                    return True
            
            # 从运行中移除
            if task_id in self._running_tasks:
                task = self._running_tasks[task_id]
                task.status = TaskStatus.CANCELLED
                del self._running_tasks[task_id]
                
                # 从节点任务列表移除
                if task.assigned_node:
                    self._node_tasks[task.assigned_node].discard(task_id)
                
                logger.info(f"Running task cancelled: {task_id}")
                return True
            
            return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        with self._lock:
            for task in self._pending_tasks:
                if task.task_id == task_id:
                    return task
            return self._running_tasks.get(task_id) or \
                   self._completed_tasks.get(task_id) or \
                   self._failed_tasks.get(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self.get_task(task_id)
        if task:
            metrics = self._task_metrics.get(task_id)
            return {
                'task_id': task.task_id,
                'status': task.status.value,
                'progress': task.progress,
                'node_id': task.assigned_node,
                'retry_count': task.retry_count,
                'error': task.error_message,
                'metrics': {
                    'wait_time_ms': metrics.wait_time_ms if metrics else 0,
                    'execution_time_ms': metrics.execution_time_ms if metrics else 0,
                } if metrics else None
            }
        return None
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        with self._lock:
            return {
                'pending': len(self._pending_tasks),
                'running': len(self._running_tasks),
                'completed': len(self._completed_tasks),
                'failed': len(self._failed_tasks),
                'total_nodes': len(self._nodes),
                'active_nodes': sum(
                    1 for n in self._nodes.values() 
                    if n.status == NodeStatus.ACTIVE
                ),
                'total_scheduled': self.total_scheduled,
                'total_completed': self.total_completed,
                'total_failed': self.total_failed,
            }
    
    def get_node_load(self, node_id: str) -> float:
        """获取节点负载"""
        with self._lock:
            if node_id not in self._nodes:
                return 1.0
            
            node = self._nodes[node_id]
            
            # 综合负载 = CPU负载 * 0.4 + 内存负载 * 0.3 + 任务负载 * 0.3
            cpu_load = node.cpu_usage / 100
            mem_load = node.memory_usage / 100
            
            # 假设最大并发任务数
            max_tasks = 10
            task_load = node.active_tasks / max_tasks
            
            return cpu_load * 0.4 + mem_load * 0.3 + task_load * 0.3
    
    def set_strategy(self, strategy: ScheduleStrategy) -> None:
        """设置调度策略"""
        self._strategy = strategy
        logger.info(f"Schedule strategy changed to: {strategy.value}")
    
    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._schedule_loop())
        logger.info("Distributed scheduler started")
    
    async def stop(self) -> None:
        """停止调度器"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Distributed scheduler stopped")
    
    # ==================== 私有方法 ====================
    
    async def _schedule_loop(self) -> None:
        """调度循环"""
        while self._running:
            try:
                await self._schedule_pending_tasks()
                await asyncio.sleep(0.1)  # 100ms调度间隔
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Schedule loop error: {e}")
    
    async def _schedule_pending_tasks(self) -> None:
        """调度待处理任务"""
        with self._lock:
            if not self._pending_tasks:
                return
            
            # 获取活跃节点
            active_nodes = [
                n for n in self._nodes.values()
                if n.status == NodeStatus.ACTIVE
            ]
            
            if not active_nodes:
                return
            
            # 按策略排序任务
            tasks_to_schedule = []
            
            while self._pending_tasks and len(active_nodes) > 0:
                task = self._pending_tasks.pop(0)
                
                # 选择最佳节点
                best_node = self._select_best_node(task, active_nodes)
                
                if best_node:
                    tasks_to_schedule.append((task, best_node))
                    # 从可用节点列表移除(防止单个节点接收过多任务)
                    if task.task_type != TaskType.CRITICAL:
                        active_nodes.remove(best_node)
        
        # 执行分配(在锁外执行)
        for task, node in tasks_to_schedule:
            await self._assign_task(task, node)
    
    def _select_best_node(self, task: Task, nodes: List[Node]) -> Optional[Node]:
        """选择最佳节点"""
        if not nodes:
            return None
        
        scored_nodes = []
        
        for node in nodes:
            score = self._calculate_node_score(task, node)
            scored_nodes.append((node, score))
        
        # 按分数排序
        scored_nodes.sort(key=lambda x: x[1], reverse=True)
        
        return scored_nodes[0][0] if scored_nodes else None
    
    def _calculate_node_score(self, task: Task, node: Node) -> float:
        """计算节点评分"""
        # 能力匹配分 (40%)
        ability_score = self._match_ability(task.task_type, node)
        
        # 负载评分 (30%) - 负载越低分数越高
        load = self.get_node_load(node.node_id)
        load_score = (1 - load) * 100
        
        # 可靠性分 (20%)
        reliability_score = node.reliability_score
        
        # 网络质量分 (10%)
        network_score = 100 - (node.avg_response_time / 100)  # 简化计算
        
        # 综合评分
        total_score = (
            ability_score * 0.4 +
            load_score * 0.3 +
            reliability_score * 0.2 +
            network_score * 0.1
        )
        
        return total_score
    
    def _match_ability(self, task_type: TaskType, node: Node) -> float:
        """能力匹配"""
        scores = {
            TaskType.COMPUTE_INTENSIVE: (node.cpu_cores / 16) * 100,
            TaskType.MEMORY_INTENSIVE: (node.memory_gb / 32) * 100,
            TaskType.IO_INTENSIVE: (node.storage_gb / 500) * 100,
            TaskType.NETWORK_INTENSIVE: (node.network_bandwidth_mbps / 1000) * 100,
            TaskType.CRITICAL: node.reliability_score,
            TaskType.BATCH: 50,  # 中等分数
        }
        return scores.get(task_type, 50)
    
    async def _assign_task(self, task: Task, node: Node) -> bool:
        """分配任务到节点"""
        with self._lock:
            task.status = TaskStatus.ASSIGNED
            task.assigned_node = node.node_id
            task.updated_at = datetime.now()
            
            self._running_tasks[task.task_id] = task
            self._node_tasks[node.node_id].add(task.task_id)
            
            node.active_tasks += 1
        
        # 触发回调
        await self._trigger_callback('task_assigned', task)
        
        logger.info(f"Task {task.task_id} assigned to node {node.node_id}")
        
        # 启动任务执行
        asyncio.create_task(self._execute_task(task, node))
        
        return True
    
    async def _execute_task(self, task: Task, node: Node) -> None:
        """执行任务"""
        # 更新指标
        with self._lock:
            metrics = self._task_metrics.get(task.task_id)
            if metrics:
                metrics.started_at = datetime.now()
                metrics.node_id = node.node_id
                metrics.wait_time_ms = int(
                    (metrics.started_at - metrics.scheduled_at).total_seconds() * 1000
                )
        
        try:
            # 获取处理器
            handler = self._handlers.get(task.task_type.value, self._default_handler)
            
            if not handler:
                raise ValueError(f"No handler for task type: {task.task_type}")
            
            # 更新状态
            with self._lock:
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()
            
            # 执行任务
            result = await asyncio.wait_for(
                handler(task),
                timeout=timedelta(seconds=self.config.task_timeout_seconds)
            )
            
            # 任务完成
            await self._complete_task(task, result)
            
        except asyncio.TimeoutError:
            await self._handle_task_timeout(task)
        except Exception as e:
            await self._handle_task_error(task, str(e))
    
    async def _complete_task(self, task: Task, result: Any) -> None:
        """任务完成"""
        with self._lock:
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now()
            task.updated_at = datetime.now()
            
            # 更新指标
            metrics = self._task_metrics.get(task.task_id)
            if metrics:
                metrics.completed_at = datetime.now()
                metrics.execution_time_ms = int(
                    (metrics.completed_at - metrics.started_at).total_seconds() * 1000
                ) if metrics.started_at else 0
            
            # 从运行中移动到完成
            self._running_tasks.pop(task.task_id, None)
            self._completed_tasks[task.task_id] = task
            
            # 更新节点任务数
            if task.assigned_node:
                self._node_tasks[task.assigned_node].discard(task.task_id)
                if task.assigned_node in self._nodes:
                    self._nodes[task.assigned_node].active_tasks = max(
                        0, self._nodes[task.assigned_node].active_tasks - 1
                    )
                    self._nodes[task.assigned_node].total_tasks += 1
            
            self.total_completed += 1
        
        # 触发回调
        await self._trigger_callback('task_completed', task)
        
        logger.info(f"Task completed: {task.task_id}")
    
    async def _handle_task_timeout(self, task: Task) -> None:
        """处理任务超时"""
        logger.warning(f"Task timeout: {task.task_id}")
        
        # 记录超时故障
        if self._fault_detector:
            self._fault_detector.record_task_timeout(task)
        
        # 尝试重新调度
        await self._retry_task(task, "Task timeout")
    
    async def _handle_task_error(self, task: Task, error: str) -> None:
        """处理任务错误"""
        logger.error(f"Task error: {task.task_id} - {error}")
        
        task.error_message = error
        task.fault_history.append({
            'timestamp': datetime.now().isoformat(),
            'error': error
        })
        
        # 记录故障
        if self._fault_detector:
            self._fault_detector.record_task_failure(task, error)
        
        # 尝试重试
        await self._retry_task(task, error)
    
    async def _retry_task(self, task: Task, error: str) -> None:
        """重试任务"""
        if task.retry_count >= task.max_retries:
            # 超过最大重试次数，标记为失败
            await self._fail_task(task, error)
            return
        
        with self._lock:
            task.retry_count += 1
            task.status = TaskStatus.RETRYING
            task.updated_at = datetime.now()
            
            # 更新指标
            metrics = self._task_metrics.get(task.task_id)
            if metrics:
                metrics.retries += 1
            
            # 从当前节点移除
            if task.assigned_node:
                self._node_tasks[task.assigned_node].discard(task.task_id)
                if task.assigned_node in self._nodes:
                    self._nodes[task.assigned_node].active_tasks = max(
                        0, self._nodes[task.assigned_node].active_tasks - 1
                    )
                    self._nodes[task.assigned_node].failed_tasks += 1
            
            task.assigned_node = None
        
        # 放回待处理队列
        with self._lock:
            self._pending_tasks.append(task)
            self._pending_tasks.sort(key=lambda t: (
                -t.priority,
                t.created_at
            ))
        
        # 触发回调
        await self._trigger_callback('task_retried', task)
        
        logger.info(f"Task {task.task_id} queued for retry (attempt {task.retry_count})")
    
    async def _fail_task(self, task: Task, error: str) -> None:
        """标记任务失败"""
        with self._lock:
            task.status = TaskStatus.FAILED
            task.error_message = error
            task.completed_at = datetime.now()
            task.updated_at = datetime.now()
            
            # 从运行中移动到失败
            self._running_tasks.pop(task.task_id, None)
            self._failed_tasks[task.task_id] = task
            
            # 从节点移除
            if task.assigned_node:
                self._node_tasks[task.assigned_node].discard(task.task_id)
            
            self.total_failed += 1
        
        # 触发回调
        await self._trigger_callback('task_failed', task)
        
        logger.error(f"Task failed: {task.task_id} - {error}")
    
    async def _migrate_task(self, task_id: str) -> None:
        """迁移任务到其他节点"""
        with self._lock:
            task = self._running_tasks.get(task_id)
            if not task:
                return
            
            task.status = TaskStatus.MIGRATING
            task.retry_count += 1
        
        # 尝试分配到其他节点
        active_nodes = [
            n for n in self._nodes.values()
            if n.status == NodeStatus.ACTIVE
        ]
        
        best_node = self._select_best_node(task, active_nodes)
        
        if best_node:
            await self._assign_task(task, best_node)
            logger.info(f"Task {task_id} migrated to {best_node.node_id}")
        else:
            # 没有可用节点，放回队列
            with self._lock:
                task.status = TaskStatus.PENDING
                self._pending_tasks.append(task)
    
    def _handle_node_failure(self, node_id: str) -> None:
        """处理节点故障"""
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return
            
            node.status = NodeStatus.PERMANENT_FAILURE
            
            # 获取该节点上的所有任务
            tasks = list(self._node_tasks.get(node_id, set()))
        
        # 迁移所有任务
        for task_id in tasks:
            asyncio.create_task(self._migrate_task(task_id))
        
        logger.warning(f"Node failure handled: {node_id}, {len(tasks)} tasks to migrate")
    
    async def _trigger_callback(self, event: str, task: Task) -> None:
        """触发事件回调"""
        callbacks = self._callbacks.get(event, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task)
                else:
                    callback(task)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")


# 便捷函数
_scheduler: Optional[DistributedScheduler] = None


def get_scheduler(config: Optional[SchedulerConfig] = None) -> DistributedScheduler:
    """获取调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = DistributedScheduler(config)
    return _scheduler
