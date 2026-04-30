"""
AttentionController - 注意力控制器

实现资源感知的任务调度器，模拟人类注意力机制：
1. 将"注意力"建模为资源配额
2. 任务队列优先级调度
3. 焦点栈（Focus Stack）支持"打断-恢复"操作
4. 上下文窗口动态分配

核心功能：
1. 任务优先级调度
2. 焦点栈管理（打断-恢复）
3. 资源配额管理
4. 上下文窗口动态分配
5. 任务状态追踪

设计原理：
- 高优先级任务分配更多GPU时间片和上下文长度
- 焦点栈保存当前处理上下文，支持思维跳跃
- 资源感知调度，避免资源争用

使用示例：
    controller = AttentionController()
    
    # 提交高优先级任务
    controller.submit_task(task_id="task1", name="紧急任务", 
                          handler=my_handler, priority="high")
    
    # 保存当前焦点
    controller.push_focus("current_context")
    
    # 处理中断任务
    controller.submit_task(task_id="task2", name="中断任务", 
                          handler=urgent_handler, priority="critical")
    
    # 恢复之前的焦点
    controller.pop_focus()
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class PriorityLevel(Enum):
    """任务优先级级别"""
    CRITICAL = "critical"   # 最高优先级，立即执行
    HIGH = "high"           # 高优先级
    MEDIUM = "medium"       # 中等优先级（默认）
    LOW = "low"             # 低优先级
    BACKGROUND = "background"  # 后台任务


class ResourceType(Enum):
    """资源类型"""
    GPU_TIME = "gpu_time"           # GPU时间片
    CONTEXT_WINDOW = "context_window"  # 上下文窗口大小
    MEMORY = "memory"             # 内存配额
    THREAD = "thread"             # 线程数


@dataclass
class ResourceQuota:
    """资源配额"""
    gpu_time_ms: int = 100        # GPU时间片（毫秒）
    context_window: int = 2048    # 上下文窗口大小
    memory_mb: int = 512          # 内存配额（MB）
    threads: int = 1              # 线程数
    
    @classmethod
    def for_priority(cls, priority: PriorityLevel) -> 'ResourceQuota':
        """根据优先级获取资源配额"""
        quotas = {
            PriorityLevel.CRITICAL: cls(gpu_time_ms=500, context_window=8192, memory_mb=2048, threads=4),
            PriorityLevel.HIGH: cls(gpu_time_ms=200, context_window=4096, memory_mb=1024, threads=2),
            PriorityLevel.MEDIUM: cls(gpu_time_ms=100, context_window=2048, memory_mb=512, threads=1),
            PriorityLevel.LOW: cls(gpu_time_ms=50, context_window=1024, memory_mb=256, threads=1),
            PriorityLevel.BACKGROUND: cls(gpu_time_ms=20, context_window=512, memory_mb=128, threads=1)
        }
        return quotas.get(priority, quotas[PriorityLevel.MEDIUM])


@dataclass
class TaskContext:
    """任务上下文"""
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    name: str = ""
    priority: PriorityLevel = PriorityLevel.MEDIUM
    resource_quota: ResourceQuota = field(default_factory=ResourceQuota)
    current_state: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    suspended_at: Optional[datetime] = None
    
    def suspend(self):
        """挂起上下文"""
        self.suspended_at = datetime.now()
    
    def resume(self):
        """恢复上下文"""
        self.suspended_at = None
    
    def is_suspended(self) -> bool:
        return self.suspended_at is not None


@dataclass
class FocusStackItem:
    """焦点栈项"""
    context_id: str
    task_context: TaskContext
    timestamp: datetime = field(default_factory=datetime.now)


class FocusStack:
    """焦点栈 - 支持打断-恢复操作"""
    
    def __init__(self, max_depth: int = 10):
        self._stack: List[FocusStackItem] = []
        self._max_depth = max_depth
        self._logger = logger.bind(component="FocusStack")
    
    def push(self, context: TaskContext):
        """压入焦点"""
        if len(self._stack) >= self._max_depth:
            self._stack.pop(0)  # 移除最旧的
        
        item = FocusStackItem(
            context_id=context.context_id,
            task_context=context
        )
        self._stack.append(item)
        self._logger.debug(f"焦点压入: {context.name} (深度: {len(self._stack)})")
    
    def pop(self) -> Optional[TaskContext]:
        """弹出焦点"""
        if not self._stack:
            return None
        
        item = self._stack.pop()
        self._logger.debug(f"焦点弹出: {item.task_context.name} (深度: {len(self._stack)})")
        return item.task_context
    
    def peek(self) -> Optional[TaskContext]:
        """查看当前焦点（不弹出）"""
        if not self._stack:
            return None
        return self._stack[-1].task_context
    
    def suspend_current(self) -> Optional[TaskContext]:
        """挂起当前焦点并返回"""
        current = self.peek()
        if current:
            current.suspend()
            self._logger.debug(f"挂起当前焦点: {current.name}")
        return current
    
    def resume_current(self):
        """恢复当前焦点"""
        current = self.peek()
        if current:
            current.resume()
            self._logger.debug(f"恢复当前焦点: {current.name}")
    
    def depth(self) -> int:
        """获取栈深度"""
        return len(self._stack)
    
    def is_empty(self) -> bool:
        """检查是否为空"""
        return len(self._stack) == 0
    
    def clear(self):
        """清空栈"""
        self._stack.clear()
        self._logger.debug("焦点栈已清空")


@dataclass
class Task:
    """任务定义"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    handler: Callable = None
    params: Dict[str, Any] = field(default_factory=dict)
    priority: PriorityLevel = PriorityLevel.MEDIUM
    resource_quota: ResourceQuota = field(default_factory=ResourceQuota)
    status: str = "pending"  # pending, running, completed, failed, cancelled
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    requires_attention: bool = False  # 是否需要立即关注


class AttentionController:
    """注意力控制器"""
    
    def __init__(self):
        self._logger = logger.bind(component="AttentionController")
        
        # 任务队列（按优先级分组）
        self._task_queues: Dict[PriorityLevel, List[Task]] = {
            PriorityLevel.CRITICAL: [],
            PriorityLevel.HIGH: [],
            PriorityLevel.MEDIUM: [],
            PriorityLevel.LOW: [],
            PriorityLevel.BACKGROUND: []
        }
        
        # 任务存储
        self._tasks: Dict[str, Task] = {}
        
        # 焦点栈
        self._focus_stack = FocusStack()
        
        # 当前运行任务
        self._current_task: Optional[Task] = None
        
        # 资源使用状态
        self._resource_usage: Dict[ResourceType, float] = {
            ResourceType.GPU_TIME: 0.0,
            ResourceType.CONTEXT_WINDOW: 0.0,
            ResourceType.MEMORY: 0.0,
            ResourceType.THREAD: 0.0
        }
        
        # 运行状态
        self._running = False
        self._worker_task = None
        
        # 事件监听器
        self._listeners: List[Callable[[Dict], None]] = []
        
        self._logger.info("注意力控制器初始化完成")
    
    async def start(self):
        """启动控制器"""
        if self._running:
            return
        
        self._running = True
        self._logger.info("启动注意力控制器")
        self._worker_task = asyncio.create_task(self._worker_loop())
    
    async def stop(self):
        """停止控制器"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
        self._logger.info("停止注意力控制器")
    
    async def _worker_loop(self):
        """工作循环"""
        while self._running:
            # 获取下一个任务
            task = self._get_next_task()
            
            if task:
                await self._execute_task(task)
            
            await asyncio.sleep(0.01)
    
    def _get_next_task(self) -> Optional[Task]:
        """获取下一个任务（按优先级）"""
        priority_order = [
            PriorityLevel.CRITICAL,
            PriorityLevel.HIGH,
            PriorityLevel.MEDIUM,
            PriorityLevel.LOW,
            PriorityLevel.BACKGROUND
        ]
        
        for priority in priority_order:
            if self._task_queues[priority]:
                # 检查资源是否足够
                task = self._task_queues[priority][0]
                if self._can_allocate_resources(task.resource_quota):
                    return self._task_queues[priority].pop(0)
        
        return None
    
    def _can_allocate_resources(self, quota: ResourceQuota) -> bool:
        """检查资源是否足够"""
        # 简化的资源检查逻辑
        return True
    
    async def _execute_task(self, task: Task):
        """执行任务"""
        self._current_task = task
        task.status = "running"
        task.started_at = datetime.now()
        
        await self._notify_event("task_started", {"task_id": task.task_id, "name": task.name})
        
        # 更新资源使用
        self._update_resource_usage(task.resource_quota, True)
        
        try:
            # 创建任务上下文并压入焦点栈
            context = TaskContext(
                task_id=task.task_id,
                name=task.name,
                priority=task.priority,
                resource_quota=task.resource_quota
            )
            self._focus_stack.push(context)
            
            # 执行任务
            if asyncio.iscoroutinefunction(task.handler):
                result = await task.handler(**task.params)
            else:
                result = task.handler(**task.params)
            
            task.status = "completed"
            task.result = result
            task.completed_at = datetime.now()
            
            await self._notify_event("task_completed", {
                "task_id": task.task_id, 
                "name": task.name,
                "result": str(result)[:100]
            })
            
            self._logger.info(f"任务完成: {task.name}")
        
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now()
            
            await self._notify_event("task_failed", {
                "task_id": task.task_id, 
                "name": task.name,
                "error": str(e)
            })
            
            self._logger.error(f"任务失败: {task.name}, 错误: {e}")
        
        finally:
            # 弹出焦点栈
            self._focus_stack.pop()
            
            # 释放资源
            self._update_resource_usage(task.resource_quota, False)
            
            self._current_task = None
    
    def submit_task(
        self,
        name: str,
        handler: Callable,
        params: Optional[Dict[str, Any]] = None,
        priority: str = "medium",
        task_id: Optional[str] = None
    ) -> str:
        """
        提交任务
        
        Args:
            name: 任务名称
            handler: 任务处理函数
            params: 任务参数
            priority: 优先级（critical/high/medium/low/background）
            task_id: 任务ID（可选，自动生成）
        
        Returns:
            任务ID
        """
        task_id = task_id or str(uuid.uuid4())
        
        if task_id in self._tasks:
            raise ValueError(f"任务已存在: {task_id}")
        
        priority_level = PriorityLevel(priority)
        resource_quota = ResourceQuota.for_priority(priority_level)
        
        task = Task(
            task_id=task_id,
            name=name,
            handler=handler,
            params=params or {},
            priority=priority_level,
            resource_quota=resource_quota
        )
        
        self._tasks[task_id] = task
        self._task_queues[priority_level].append(task)
        
        # 如果是紧急任务，触发中断
        if priority_level == PriorityLevel.CRITICAL:
            self._trigger_interrupt()
        
        self._logger.info(f"任务已提交: {name} (优先级: {priority})")
        
        return task_id
    
    def _trigger_interrupt(self):
        """触发中断处理"""
        if self._current_task and self._current_task.priority != PriorityLevel.CRITICAL:
            # 挂起当前任务
            self._focus_stack.suspend_current()
            self._logger.info(f"任务中断: {self._current_task.name}")
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        task.status = "cancelled"
        
        # 从队列中移除
        for queue in self._task_queues.values():
            if task in queue:
                queue.remove(task)
                break
        
        self._logger.info(f"任务已取消: {task.name}")
        return True
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def list_tasks(self, priority: Optional[str] = None) -> List[Task]:
        """列出任务"""
        if priority:
            priority_level = PriorityLevel(priority)
            return self._task_queues[priority_level] + [
                t for t in self._tasks.values() 
                if t.priority == priority_level and t.status != "pending"
            ]
        
        return list(self._tasks.values())
    
    def get_current_task(self) -> Optional[Task]:
        """获取当前运行的任务"""
        return self._current_task
    
    def get_focus_stack_depth(self) -> int:
        """获取焦点栈深度"""
        return self._focus_stack.depth()
    
    def get_resource_usage(self) -> Dict[str, float]:
        """获取资源使用情况"""
        return {rt.name: usage for rt, usage in self._resource_usage.items()}
    
    def _update_resource_usage(self, quota: ResourceQuota, allocate: bool):
        """更新资源使用"""
        delta = 1.0 if allocate else -1.0
        
        # 简化的资源使用更新
        self._resource_usage[ResourceType.GPU_TIME] += delta * quota.gpu_time_ms / 1000.0
        self._resource_usage[ResourceType.CONTEXT_WINDOW] += delta * quota.context_window / 8192.0
        self._resource_usage[ResourceType.MEMORY] += delta * quota.memory_mb / 2048.0
        self._resource_usage[ResourceType.THREAD] += delta * quota.threads / 4.0
    
    def add_listener(self, listener: Callable[[Dict], None]):
        """添加事件监听器"""
        self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[Dict], None]):
        """移除事件监听器"""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    async def _notify_event(self, event_type: str, data: Dict):
        """通知事件"""
        event = {"type": event_type, "timestamp": datetime.now().isoformat(), "data": data}
        
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event)
                else:
                    listener(event)
            except Exception as e:
                self._logger.error(f"事件通知失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "total_tasks": len(self._tasks),
            "current_task": self._current_task.name if self._current_task else None,
            "focus_stack_depth": self._focus_stack.depth(),
            "resource_usage": self.get_resource_usage(),
            "queue_sizes": {}
        }
        
        for priority, queue in self._task_queues.items():
            stats["queue_sizes"][priority.value] = len(queue)
        
        return stats


def create_attention_controller() -> AttentionController:
    """创建注意力控制器实例"""
    return AttentionController()
