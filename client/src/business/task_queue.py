"""
TaskQueue - 任务队列（双队列架构）

参考 ml-intern 的 submission_queue + event_queue

功能：
1. 任务提交队列（submission_queue）- 处理任务提交和执行
2. 事件通知队列（event_queue）- 处理状态变更通知
3. 支持实时状态推送（PyQt6 信号槽）
4. 支持任务中断和审批流程

遵循自我进化原则：
- 从队列状态中学习优化调度策略
- 动态调整队列优先级
"""

import asyncio
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    APPROVAL = "approval"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """任务优先级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EventType(Enum):
    """事件类型"""
    TASK_SUBMITTED = "task_submitted"
    TASK_APPROVED = "task_approved"
    TASK_REJECTED = "task_rejected"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    STATUS_CHANGED = "status_changed"


@dataclass
class Task:
    """任务"""
    task_id: str
    name: str
    handler: Callable
    params: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    requires_approval: bool = False
    approved_by: Optional[str] = None


@dataclass
class Event:
    """事件"""
    event_id: str
    event_type: EventType
    task_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)


class TaskQueue:
    """
    任务队列（双队列架构）
    
    包含两个队列：
    1. submission_queue - 任务提交队列，负责任务的提交、审批和执行
    2. event_queue - 事件通知队列，负责状态变更的实时推送
    
    支持：
    - 优先级队列
    - 任务审批流程
    - 任务中断
    - 实时状态推送
    """

    def __init__(self):
        self._logger = logger.bind(component="TaskQueue")
        
        # 任务提交队列（按优先级排序）
        self._submission_queue: List[Task] = []
        
        # 事件通知队列
        self._event_queue: List[Event] = []
        
        # 任务存储
        self._tasks: Dict[str, Task] = {}
        
        # 事件监听器
        self._event_listeners: List[Callable[[Event], None]] = []
        
        # 运行状态
        self._running = False
        self._worker_task = None

    async def start(self):
        """启动任务队列"""
        if self._running:
            return
        
        self._running = True
        self._logger.info("启动任务队列")
        
        # 启动工作线程
        self._worker_task = asyncio.create_task(self._worker_loop())
        
        # 启动事件处理线程
        self._event_task = asyncio.create_task(self._event_processor_loop())

    async def stop(self):
        """停止任务队列"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
        if self._event_task:
            self._event_task.cancel()
        self._logger.info("停止任务队列")

    async def _worker_loop(self):
        """任务处理循环"""
        while self._running:
            # 获取优先级最高的待处理任务
            task = self._get_next_task()
            
            if task:
                await self._process_task(task)
            
            await asyncio.sleep(0.1)

    async def _event_processor_loop(self):
        """事件处理循环"""
        while self._running:
            if self._event_queue:
                event = self._event_queue.pop(0)
                await self._dispatch_event(event)
            
            await asyncio.sleep(0.05)

    def _get_next_task(self) -> Optional[Task]:
        """获取下一个待处理任务"""
        # 筛选出待处理的任务
        pending = [t for t in self._submission_queue 
                   if t.status == TaskStatus.PENDING or t.status == TaskStatus.APPROVAL]
        
        if not pending:
            return None

        # 按优先级排序
        priority_order = {TaskPriority.HIGH: 0, TaskPriority.MEDIUM: 1, TaskPriority.LOW: 2}
        pending.sort(key=lambda t: (priority_order[t.priority], t.created_at))
        
        # 返回优先级最高的任务
        return pending[0]

    async def _process_task(self, task: Task):
        """处理任务"""
        # 如果需要审批，跳过
        if task.status == TaskStatus.APPROVAL:
            return

        # 开始执行
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        await self._publish_event(EventType.TASK_STARTED, task.task_id, {"task": task.__dict__})

        try:
            # 执行任务
            result = await task.handler(**task.params)
            
            # 完成任务
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            
            await self._publish_event(EventType.TASK_COMPLETED, task.task_id, {"result": result})
            self._logger.info(f"任务完成: {task.name}")

        except Exception as e:
            # 任务失败
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)
            
            await self._publish_event(EventType.TASK_FAILED, task.task_id, {"error": str(e)})
            self._logger.error(f"任务失败: {task.name}, 错误: {e}")

        # 从队列中移除
        if task in self._submission_queue:
            self._submission_queue.remove(task)

    def submit_task(
        self,
        task_id: str,
        name: str,
        handler: Callable,
        params: Optional[Dict[str, Any]] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        requires_approval: bool = False
    ) -> Task:
        """
        提交任务
        
        Args:
            task_id: 任务 ID
            name: 任务名称
            handler: 任务处理函数
            params: 任务参数
            priority: 任务优先级
            requires_approval: 是否需要审批
            
        Returns:
            Task
        """
        if task_id in self._tasks:
            raise ValueError(f"任务已存在: {task_id}")

        status = TaskStatus.APPROVAL if requires_approval else TaskStatus.PENDING

        task = Task(
            task_id=task_id,
            name=name,
            handler=handler,
            params=params or {},
            priority=priority,
            status=status,
            requires_approval=requires_approval
        )

        self._tasks[task_id] = task
        self._submission_queue.append(task)
        
        self._logger.info(f"任务已提交: {name}")
        
        # 发布事件
        asyncio.create_task(self._publish_event(
            EventType.TASK_SUBMITTED,
            task_id,
            {"task": task.__dict__}
        ))

        return task

    def approve_task(self, task_id: str, approver_id: str) -> bool:
        """
        审批任务
        
        Args:
            task_id: 任务 ID
            approver_id: 审批人 ID
            
        Returns:
            是否审批成功
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status != TaskStatus.APPROVAL:
            return False

        task.status = TaskStatus.PENDING
        task.approved_by = approver_id
        
        self._logger.info(f"任务已审批: {task.name}")
        
        # 发布事件
        asyncio.create_task(self._publish_event(
            EventType.TASK_APPROVED,
            task_id,
            {"approver_id": approver_id}
        ))

        return True

    def reject_task(self, task_id: str, approver_id: str, reason: str) -> bool:
        """
        拒绝任务
        
        Args:
            task_id: 任务 ID
            approver_id: 审批人 ID
            reason: 拒绝原因
            
        Returns:
            是否拒绝成功
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status != TaskStatus.APPROVAL:
            return False

        task.status = TaskStatus.CANCELLED
        
        self._logger.info(f"任务已拒绝: {task.name}, 原因: {reason}")
        
        # 发布事件
        asyncio.create_task(self._publish_event(
            EventType.TASK_REJECTED,
            task_id,
            {"approver_id": approver_id, "reason": reason}
        ))

        # 从队列中移除
        if task in self._submission_queue:
            self._submission_queue.remove(task)

        return True

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            是否取消成功
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status == TaskStatus.COMPLETED:
            return False

        task.status = TaskStatus.CANCELLED
        
        self._logger.info(f"任务已取消: {task.name}")
        
        # 发布事件
        asyncio.create_task(self._publish_event(
            EventType.TASK_CANCELLED,
            task_id,
            {}
        ))

        # 从队列中移除
        if task in self._submission_queue:
            self._submission_queue.remove(task)

        return True

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """列出任务"""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def add_event_listener(self, listener: Callable[[Event], None]):
        """添加事件监听器"""
        self._event_listeners.append(listener)
        self._logger.info("已添加事件监听器")

    def remove_event_listener(self, listener: Callable[[Event], None]):
        """移除事件监听器"""
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)

    async def _publish_event(self, event_type: EventType, task_id: str, data: Dict[str, Any]):
        """发布事件"""
        event = Event(
            event_id=f"event_{len(self._event_queue)}",
            event_type=event_type,
            task_id=task_id,
            data=data
        )
        self._event_queue.append(event)

    async def _dispatch_event(self, event: Event):
        """分发事件给所有监听器"""
        for listener in self._event_listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event)
                else:
                    listener(event)
            except Exception as e:
                self._logger.error(f"事件分发失败: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        status_counts = {}
        for status in TaskStatus:
            status_counts[status.value] = sum(1 for t in self._tasks.values() if t.status == status)
        
        priority_counts = {}
        for priority in TaskPriority:
            priority_counts[priority.value] = sum(1 for t in self._tasks.values() if t.priority == priority)
        
        return {
            "total_tasks": len(self._tasks),
            "queue_size": len(self._submission_queue),
            "event_queue_size": len(self._event_queue),
            "status_counts": status_counts,
            "priority_counts": priority_counts,
            "running": self._running
        }