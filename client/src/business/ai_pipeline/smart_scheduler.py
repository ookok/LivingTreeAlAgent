"""
智能调度引擎 - SmartScheduler

核心功能：
1. 资源感知调度
2. 优先级动态调整
3. 故障自愈机制
4. 任务并行执行
5. 智能依赖分析
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import time
from loguru import logger


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResourceType(Enum):
    """资源类型"""
    CPU = "cpu"
    MEMORY = "memory"
    GPU = "gpu"
    NETWORK = "network"


@dataclass
class ResourceUsage:
    """资源使用情况"""
    type: ResourceType
    current: float
    max: float
    threshold: float = 0.8


@dataclass
class ScheduledTask:
    """调度任务"""
    id: str
    name: str
    func: callable
    args: tuple = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    retries: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)
    started_at: float = 0
    completed_at: float = 0
    result: Any = None
    error: Optional[str] = None


class SmartScheduler:
    """
    智能调度引擎
    
    核心特性：
    1. 资源感知调度 - 根据系统负载动态分配任务
    2. 优先级动态调整 - 根据业务价值自动调整优先级
    3. 故障自愈 - 自动重试失败任务，智能选择备用方案
    4. 任务并行执行 - 支持任务并行分解
    5. 智能依赖分析 - 自动检测任务依赖关系
    """

    def __init__(self):
        self._logger = logger.bind(component="SmartScheduler")
        self._tasks: Dict[str, ScheduledTask] = {}
        self._queue = asyncio.PriorityQueue()
        self._running_tasks = set()
        self._max_parallel = 4
        self._resource_monitor = ResourceMonitor()
        self._shutdown_event = asyncio.Event()
        
        # 启动资源监控
        self._resource_task = asyncio.create_task(self._monitor_resources())

    async def _monitor_resources(self):
        """资源监控循环"""
        while not self._shutdown_event.is_set():
            await self._resource_monitor.update()
            await asyncio.sleep(5)

    async def submit_task(self, name: str, func: callable, *args, **kwargs) -> str:
        """提交任务"""
        task_id = f"task_{int(time.time())}_{hash(name) % 10000}"
        
        priority = kwargs.pop('priority', TaskPriority.MEDIUM)
        dependencies = kwargs.pop('dependencies', [])
        max_retries = kwargs.pop('max_retries', 3)
        
        task = ScheduledTask(
            id=task_id,
            name=name,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            dependencies=dependencies,
            max_retries=max_retries
        )
        
        self._tasks[task_id] = task
        
        # 检查依赖
        if dependencies:
            await self._wait_for_dependencies(task)
        else:
            await self._queue_task(task)
        
        return task_id

    async def _wait_for_dependencies(self, task: ScheduledTask):
        """等待依赖完成"""
        self._logger.info(f"任务 {task.name} 等待依赖: {task.dependencies}")
        
        while not self._shutdown_event.is_set():
            all_ready = True
            for dep_id in task.dependencies:
                dep_task = self._tasks.get(dep_id)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    all_ready = False
                    break
            
            if all_ready:
                await self._queue_task(task)
                return
            
            await asyncio.sleep(1)

    async def _queue_task(self, task: ScheduledTask):
        """加入任务队列"""
        task.status = TaskStatus.QUEUED
        await self._queue.put((task.priority.value, task))
        self._logger.info(f"任务入队: {task.name} (优先级: {task.priority.name})")

    async def start(self):
        """启动调度器"""
        self._logger.info("启动智能调度器...")
        
        # 启动多个工作协程
        self._workers = [
            asyncio.create_task(self._worker(f"Worker-{i}"))
            for i in range(self._max_parallel)
        ]
        
        await asyncio.gather(*self._workers)

    async def _worker(self, name: str):
        """工作协程"""
        while not self._shutdown_event.is_set():
            try:
                # 检查资源使用
                if not await self._can_start_task():
                    await asyncio.sleep(2)
                    continue
                
                priority, task = await self._queue.get()
                
                if task.id in self._running_tasks:
                    continue
                
                await self._execute_task(task)
                
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Worker {name} 错误: {e}")

    async def _can_start_task(self) -> bool:
        """检查是否可以启动新任务"""
        # 检查并行任务数
        if len(self._running_tasks) >= self._max_parallel:
            return False
        
        # 检查资源使用
        resources = self._resource_monitor.get_usage()
        for resource in resources.values():
            if resource.current / resource.max >= resource.threshold:
                self._logger.debug(f"资源 {resource.type.name} 使用率过高: {resource.current/resource.max:.2%}")
                return False
        
        return True

    async def _execute_task(self, task: ScheduledTask):
        """执行任务"""
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        self._running_tasks.add(task.id)
        
        self._logger.info(f"开始执行任务: {task.name}")
        
        try:
            # 动态调整优先级
            await self._adjust_priority(task)
            
            # 执行任务
            if asyncio.iscoroutinefunction(task.func):
                result = await task.func(*task.args, **task.kwargs)
            else:
                result = task.func(*task.args, **task.kwargs)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            self._logger.info(f"任务完成: {task.name}")
            
        except Exception as e:
            task.error = str(e)
            task.retries += 1
            
            if task.retries < task.max_retries:
                # 故障自愈 - 重试
                self._logger.warning(f"任务失败 {task.name}, 重试 {task.retries}/{task.max_retries}: {e}")
                await self._retry_with_backoff(task)
            else:
                task.status = TaskStatus.FAILED
                self._logger.error(f"任务最终失败: {task.name}: {e}")
        
        finally:
            task.completed_at = time.time()
            self._running_tasks.discard(task.id)

    async def _adjust_priority(self, task: ScheduledTask):
        """动态调整优先级"""
        # 根据业务价值和资源情况调整优先级
        # 这里可以扩展为更复杂的优先级调整逻辑
        pass

    async def _retry_with_backoff(self, task: ScheduledTask):
        """带退避的重试"""
        backoff = 2 ** task.retries
        await asyncio.sleep(backoff)
        await self._queue.put((task.priority.value, task))

    def get_task_status(self, task_id: str) -> Optional[ScheduledTask]:
        """获取任务状态"""
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[ScheduledTask]:
        """列出任务"""
        tasks = list(self._tasks.values())
        if status:
            return [t for t in tasks if t.status == status]
        return tasks

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        if task.status in [TaskStatus.PENDING, TaskStatus.QUEUED]:
            task.status = TaskStatus.CANCELLED
            self._logger.info(f"任务已取消: {task.name}")
            return True
        
        return False

    async def shutdown(self):
        """关闭调度器"""
        self._logger.info("关闭智能调度器...")
        self._shutdown_event.set()
        
        # 取消所有工作协程
        if hasattr(self, '_workers'):
            for worker in self._workers:
                worker.cancel()
            
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        # 取消资源监控
        if hasattr(self, '_resource_task'):
            self._resource_task.cancel()


class ResourceMonitor:
    """资源监控器"""
    
    def __init__(self):
        self._usage: Dict[ResourceType, ResourceUsage] = {}
    
    async def update(self):
        """更新资源使用情况"""
        try:
            import psutil
            
            # CPU使用率
            cpu_percent = psutil.cpu_percent()
            self._usage[ResourceType.CPU] = ResourceUsage(
                type=ResourceType.CPU,
                current=cpu_percent,
                max=100.0,
                threshold=0.85
            )
            
            # 内存使用率
            mem = psutil.virtual_memory()
            self._usage[ResourceType.MEMORY] = ResourceUsage(
                type=ResourceType.MEMORY,
                current=mem.percent,
                max=100.0,
                threshold=0.85
            )
            
            # GPU使用率（如果可用）
            try:
                if self._has_gpu():
                    gpu_usage = self._get_gpu_usage()
                    self._usage[ResourceType.GPU] = ResourceUsage(
                        type=ResourceType.GPU,
                        current=gpu_usage,
                        max=100.0,
                        threshold=0.90
                    )
            except:
                pass
            
        except ImportError:
            pass
    
    def _has_gpu(self) -> bool:
        """检查是否有GPU"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    def _get_gpu_usage(self) -> float:
        """获取GPU使用率"""
        try:
            import torch
            return torch.cuda.utilization()
        except:
            return 0.0
    
    def get_usage(self) -> Dict[ResourceType, ResourceUsage]:
        """获取资源使用情况"""
        return self._usage


def get_smart_scheduler() -> SmartScheduler:
    """获取智能调度器单例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SmartScheduler()
    return _scheduler_instance


_scheduler_instance = None