"""
优先级任务队列 (Priority Task Queue)
=====================================

实现支持优先级的任务队列：
1. 四级优先级：critical > high > normal > low
2. 优先级抢占机制
3. 任务队列管理

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import asyncio
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from loguru import logger


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 3
    HIGH = 2
    NORMAL = 1
    LOW = 0
    
    @classmethod
    def from_string(cls, priority_str: str) -> 'TaskPriority':
        """从字符串转换为优先级"""
        mapping = {
            'critical': cls.CRITICAL,
            'high': cls.HIGH,
            'normal': cls.NORMAL,
            'low': cls.LOW
        }
        return mapping.get(priority_str.lower(), cls.NORMAL)


@dataclass
class PriorityTask:
    """优先级任务"""
    task_id: str
    context: Any
    priority: TaskPriority
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    deadline: Optional[float] = None
    callback: Optional[Callable] = None
    
    def is_expired(self) -> bool:
        """检查任务是否过期"""
        if self.deadline is None:
            return False
        return asyncio.get_event_loop().time() > self.deadline


class PriorityTaskQueue:
    """
    优先级任务队列
    
    支持四级优先级调度：
    - CRITICAL (3): 关键任务，立即执行
    - HIGH (2): 高优先级任务
    - NORMAL (1): 普通任务
    - LOW (0): 低优先级任务
    """
    
    def __init__(self, max_pending: int = 1000):
        """
        初始化任务队列
        
        Args:
            max_pending: 最大待处理任务数
        """
        self._queues: Dict[TaskPriority, List[PriorityTask]] = {
            TaskPriority.CRITICAL: [],
            TaskPriority.HIGH: [],
            TaskPriority.NORMAL: [],
            TaskPriority.LOW: []
        }
        self._max_pending = max_pending
        self._total_tasks = 0
        self._pending_event = asyncio.Event()
        self._closed = False
        
    def enqueue(self, task: PriorityTask) -> bool:
        """
        入队任务
        
        Args:
            task: 任务对象
            
        Returns:
            是否入队成功
        """
        if self._closed:
            logger.warning("[PriorityTaskQueue] 队列已关闭")
            return False
            
        if self._total_tasks >= self._max_pending:
            logger.warning("[PriorityTaskQueue] 队列已满")
            return False
            
        self._queues[task.priority].append(task)
        self._total_tasks += 1
        self._pending_event.set()
        
        logger.debug(f"[PriorityTaskQueue] 任务入队: {task.task_id} (优先级: {task.priority.name})")
        return True
        
    def dequeue(self) -> Optional[PriorityTask]:
        """
        出队任务（优先高优先级）
        
        Returns:
            任务对象，如果队列为空返回 None
        """
        # 按优先级顺序出队
        for priority in [TaskPriority.CRITICAL, TaskPriority.HIGH, TaskPriority.NORMAL, TaskPriority.LOW]:
            if self._queues[priority]:
                task = self._queues[priority].pop(0)
                self._total_tasks -= 1
                
                # 检查队列是否为空
                if self._total_tasks == 0:
                    self._pending_event.clear()
                    
                logger.debug(f"[PriorityTaskQueue] 任务出队: {task.task_id} (优先级: {priority.name})")
                return task
                
        return None
        
    async def dequeue_wait(self) -> Optional[PriorityTask]:
        """
        出队任务（阻塞等待直到有任务）
        
        Returns:
            任务对象，如果队列关闭返回 None
        """
        while not self._closed:
            task = self.dequeue()
            if task:
                return task
            
            # 等待有新任务
            try:
                await asyncio.wait_for(self._pending_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
                
        return None
        
    def peek(self) -> Optional[PriorityTask]:
        """
        查看下一个任务（不出队）
        
        Returns:
            任务对象，如果队列为空返回 None
        """
        for priority in [TaskPriority.CRITICAL, TaskPriority.HIGH, TaskPriority.NORMAL, TaskPriority.LOW]:
            if self._queues[priority]:
                return self._queues[priority][0]
        return None
        
    def remove(self, task_id: str) -> bool:
        """
        移除指定任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否移除成功
        """
        for priority in [TaskPriority.CRITICAL, TaskPriority.HIGH, TaskPriority.NORMAL, TaskPriority.LOW]:
            for i, task in enumerate(self._queues[priority]):
                if task.task_id == task_id:
                    del self._queues[priority][i]
                    self._total_tasks -= 1
                    if self._total_tasks == 0:
                        self._pending_event.clear()
                    return True
        return False
        
    def get_queue_size(self, priority: Optional[TaskPriority] = None) -> int:
        """
        获取队列大小
        
        Args:
            priority: 指定优先级，如果为 None 则返回总大小
            
        Returns:
            队列大小
        """
        if priority is not None:
            return len(self._queues[priority])
        return self._total_tasks
        
    def get_priority_counts(self) -> Dict[str, int]:
        """获取各优先级任务数量"""
        return {
            'critical': len(self._queues[TaskPriority.CRITICAL]),
            'high': len(self._queues[TaskPriority.HIGH]),
            'normal': len(self._queues[TaskPriority.NORMAL]),
            'low': len(self._queues[TaskPriority.LOW]),
            'total': self._total_tasks
        }
        
    def clear(self):
        """清空队列"""
        for priority in self._queues:
            self._queues[priority].clear()
        self._total_tasks = 0
        self._pending_event.clear()
        
    def close(self):
        """关闭队列"""
        self._closed = True
        self._pending_event.set()
        
    def is_closed(self) -> bool:
        """检查队列是否关闭"""
        return self._closed


class PriorityTaskManager:
    """
    优先级任务管理器
    
    提供便捷的任务提交和管理接口
    """
    
    def __init__(self):
        """初始化管理器"""
        self._queue = PriorityTaskQueue()
        self._task_counter = 0
        
    async def submit_task(
        self,
        context: Any,
        priority: TaskPriority = TaskPriority.NORMAL,
        deadline: Optional[float] = None,
        callback: Optional[Callable] = None
    ) -> str:
        """
        提交任务
        
        Args:
            context: 任务上下文
            priority: 任务优先级
            deadline: 截止时间（时间戳）
            callback: 完成回调
            
        Returns:
            任务ID
        """
        self._task_counter += 1
        task_id = f"task-{self._task_counter}-{asyncio.get_event_loop().time():.6f}"
        
        task = PriorityTask(
            task_id=task_id,
            context=context,
            priority=priority,
            deadline=deadline,
            callback=callback
        )
        
        success = self._queue.enqueue(task)
        if success:
            return task_id
        else:
            raise RuntimeError("任务入队失败")
            
    async def process_tasks(self, handler: Callable[[Any], Any]):
        """
        处理任务队列
        
        Args:
            handler: 任务处理函数
        """
        while not self._queue.is_closed():
            task = await self._queue.dequeue_wait()
            if task is None:
                continue
                
            if task.is_expired():
                logger.warning(f"[PriorityTaskManager] 任务过期: {task.task_id}")
                continue
                
            try:
                await handler(task.context)
                
                if task.callback:
                    task.callback(success=True, task_id=task.task_id)
                    
            except Exception as e:
                logger.error(f"[PriorityTaskManager] 任务处理失败 {task.task_id}: {e}")
                if task.callback:
                    task.callback(success=False, task_id=task.task_id, error=str(e))
                    
    def get_stats(self) -> Dict[str, int]:
        """获取队列统计信息"""
        return self._queue.get_priority_counts()
        
    def close(self):
        """关闭管理器"""
        self._queue.close()
