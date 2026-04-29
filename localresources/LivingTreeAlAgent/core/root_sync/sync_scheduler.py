"""
同步调度器 - Sync Scheduler

负责：
- 同步任务调度
- 并发控制
- 带宽限制
- 调度策略
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import IntEnum
from heapq import heappush, heappop

from .models import FolderConfig


class TaskPriority(IntEnum):
    """任务优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class SyncTask:
    """同步任务"""
    task_id: str
    folder_id: str
    device_id: str  # 目标设备

    # 文件信息
    file_id: str
    file_name: str
    file_size: int

    # 操作类型
    operation: str  # "pull", "push", "delete"

    # 优先级
    priority: TaskPriority = TaskPriority.NORMAL

    # 状态
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3

    # 进度
    bytes_transferred: int = 0

    # 错误
    error: Optional[str] = None

    # 比较键（用于堆排序）
    def __lt__(self, other: "SyncTask"):
        # 优先级高的先执行，优先级相同则时间早的先执行
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.created_at < other.created_at


class SyncState(IntEnum):
    """同步状态"""
    PENDING = 0
    RUNNING = 1
    COMPLETED = 2
    FAILED = 3
    CANCELLED = 4


class SyncScheduler:
    """
    同步调度器

    特性：
    1. 优先级调度
    2. 并发限制
    3. 带宽限制
    4. 自动重试
    5. 任务取消
    """

    def __init__(self,
                 max_concurrent: int = 3,
                 max_bandwidth_mbps: float = 0):  # 0 = 无限制
        self.max_concurrent = max_concurrent
        self.max_bandwidth = max_bandwidth_mbps * 1024 * 1024  # 转换为 bytes

        # 任务队列
        self._pending_tasks: List[SyncTask] = []
        self._running_tasks: Dict[str, SyncTask] = {}
        self._completed_tasks: List[SyncTask] = []

        # 按文件夹分组
        self._folder_tasks: Dict[str, Set[str]] = {}

        # 状态
        self._running = False
        self._paused = False

        # 回调
        self._on_task_start: Optional[Callable] = None
        self._on_task_progress: Optional[Callable] = None
        self._on_task_complete: Optional[Callable] = None
        self._on_task_fail: Optional[Callable] = None

        # 调度器任务
        self._scheduler_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def pending_count(self) -> int:
        return len(self._pending_tasks)

    @property
    def running_count(self) -> int:
        return len(self._running_tasks)

    def set_callbacks(self,
                      on_start: Optional[Callable] = None,
                      on_progress: Optional[Callable] = None,
                      on_complete: Optional[Callable] = None,
                      on_fail: Optional[Callable] = None):
        """设置回调"""
        self._on_task_start = on_start
        self._on_task_progress = on_progress
        self._on_task_complete = on_complete
        self._on_task_fail = on_fail

    def add_task(self, task: SyncTask) -> str:
        """
        添加同步任务

        Args:
            task: 同步任务

        Returns:
            任务ID
        """
        # 去重
        if task.task_id in self._running_tasks:
            return task.task_id

        # 添加到队列
        heappush(self._pending_tasks, task)

        # 更新文件夹索引
        if task.folder_id not in self._folder_tasks:
            self._folder_tasks[task.folder_id] = set()
        self._folder_tasks[task.folder_id].add(task.task_id)

        return task.task_id

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        # 检查是否在运行
        if task_id in self._running_tasks:
            self._running_tasks[task_id].error = "Cancelled"
            return True

        # 检查是否在队列
        for i, task in enumerate(self._pending_tasks):
            if task.task_id == task_id:
                task.error = "Cancelled"
                del self._pending_tasks[i]
                return True

        return False

    def cancel_folder_tasks(self, folder_id: str) -> int:
        """取消文件夹的所有任务"""
        cancelled = 0

        # 取消运行中的任务
        for task_id in list(self._running_tasks.keys()):
            task = self._running_tasks[task_id]
            if task.folder_id == folder_id:
                task.error = "Cancelled"
                cancelled += 1

        # 取消队列中的任务
        new_pending = []
        for task in self._pending_tasks:
            if task.folder_id == folder_id:
                task.error = "Cancelled"
                cancelled += 1
            else:
                new_pending.append(task)

        self._pending_tasks = new_pending
        return cancelled

    def get_task(self, task_id: str) -> Optional[SyncTask]:
        """获取任务"""
        if task_id in self._running_tasks:
            return self._running_tasks[task_id]

        for task in self._pending_tasks:
            if task.task_id == task_id:
                return task

        for task in self._completed_tasks:
            if task.task_id == task_id:
                return task

        return None

    def get_folder_tasks(self, folder_id: str) -> List[SyncTask]:
        """获取文件夹的任务列表"""
        tasks = []

        for task_id in self._folder_tasks.get(folder_id, set()):
            task = self.get_task(task_id)
            if task:
                tasks.append(task)

        return tasks

    def get_stats(self) -> dict:
        """获取统计信息"""
        total_bytes = sum(t.file_size for t in self._completed_tasks)
        transferred_bytes = sum(t.bytes_transferred for t in self._running_tasks)

        return {
            "pending": len(self._pending_tasks),
            "running": len(self._running_tasks),
            "completed": len(self._completed_tasks),
            "total_bytes": total_bytes,
            "transferred_bytes": transferred_bytes,
            "concurrent_limit": self.max_concurrent,
            "bandwidth_limit_mbps": self.max_bandwidth / (1024 * 1024),
        }

    async def start(self):
        """启动调度器"""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._schedule_loop())

    async def stop(self):
        """停止调度器"""
        self._running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

    async def pause(self):
        """暂停调度"""
        self._paused = True

    async def resume(self):
        """恢复调度"""
        self._paused = False

    async def _schedule_loop(self):
        """调度循环"""
        while self._running:
            try:
                if not self._paused:
                    await self._process_tasks()

                await asyncio.sleep(0.1)  # 避免 CPU 忙等待

            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _process_tasks(self):
        """处理任务"""
        # 检查是否达到并发限制
        if len(self._running_tasks) >= self.max_concurrent:
            return

        # 获取下一个任务
        while self._pending_tasks and len(self._running_tasks) < self.max_concurrent:
            task = heappop(self._pending_tasks)

            if task.error == "Cancelled":
                continue

            # 执行任务
            asyncio.create_task(self._execute_task(task))

    async def _execute_task(self, task: SyncTask):
        """执行任务"""
        task.started_at = time.time()
        task.state = SyncState.RUNNING

        self._running_tasks[task.task_id] = task

        if self._on_task_start:
            await self._on_task_start(task)

        try:
            # 执行同步操作
            await self._do_sync(task)

            # 完成
            task.completed_at = time.time()
            task.state = SyncState.COMPLETED

            if self._on_task_complete:
                await self._on_task_complete(task)

        except Exception as e:
            task.error = str(e)
            task.retry_count += 1

            if task.retry_count < task.max_retries:
                # 重试
                task.started_at = None
                heappush(self._pending_tasks, task)
            else:
                task.completed_at = time.time()
                task.state = SyncState.FAILED

                if self._on_task_fail:
                    await self._on_task_fail(task)

        finally:
            if task.task_id in self._running_tasks:
                del self._running_tasks[task.task_id]

            self._completed_tasks.append(task)

            # 限制完成列表大小
            if len(self._completed_tasks) > 1000:
                self._completed_tasks = self._completed_tasks[-500:]

    async def _do_sync(self, task: SyncTask):
        """
        执行同步操作

        子类实现具体的同步逻辑
        """
        # 模拟同步过程
        chunk_size = 64 * 1024  # 64KB
        transferred = 0

        while transferred < task.file_size:
            # 检查带宽限制
            if self.max_bandwidth > 0:
                await self._apply_bandwidth_limit(chunk_size)

            # 模拟数据传输
            await asyncio.sleep(0.01)

            transferred += chunk_size
            task.bytes_transferred = transferred

            if self._on_task_progress:
                await self._on_task_progress(task)

    async def _apply_bandwidth_limit(self, chunk_size: int):
        """应用带宽限制"""
        if self.max_bandwidth <= 0:
            return

        # 计算传输时间
        expected_time = chunk_size / self.max_bandwidth
        await asyncio.sleep(expected_time)


class BandwidthLimiter:
    """
    带宽限制器

    实现令牌桶算法的带宽限制
    """

    def __init__(self, max_rate_mbps: float):
        self.max_rate = max_rate_mbps * 1024 * 1024  # bytes/s
        self.tokens = self.max_rate
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self, size: int):
        """获取带宽"""
        async with self.lock:
            # 补充令牌
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.max_rate, self.tokens + elapsed * self.max_rate)
            self.last_update = now

            # 等待足够的令牌
            if self.tokens < size:
                wait_time = (size - self.tokens) / self.max_rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= size

    def set_rate(self, max_rate_mbps: float):
        """设置最大速率"""
        self.max_rate = max_rate_mbps * 1024 * 1024
