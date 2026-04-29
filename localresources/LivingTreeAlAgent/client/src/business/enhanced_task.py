"""
增强版任务管理核心模块
Enhanced Task Management Core

功能：
- 任务生命周期管理（暂停/恢复/取消/编辑）
- 可取消的异步任务执行
- 任务批量操作
- 任务搜索和筛选
- 操作历史记录
"""

import time
import uuid
import asyncio
import threading
import traceback
from typing import Callable, Optional, Any, List, Dict
from enum import Enum
from dataclasses import dataclass, field, asdict
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject

# 任务状态
class TaskStatus(Enum):
    PENDING = "pending"       # 等待中
    RUNNING = "running"       # 执行中
    PAUSED = "paused"         # 已暂停
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消


class TaskPriority(Enum):
    LOW = 0      # 低优先级
    NORMAL = 1   # 普通
    HIGH = 2     # 高
    URGENT = 3   # 紧急


@dataclass
class TaskConfig:
    """任务可编辑配置"""
    title: str = ""
    description: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TaskConfig":
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            priority=TaskPriority(data.get("priority", 1)),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskContext:
    """任务执行上下文（可传递给handler）"""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    message: str = ""
    cancelled: bool = False
    paused: bool = False
    
    def report_progress(self, progress: float, message: str = ""):
        """报告进度"""
        self.progress = max(0, min(100, progress))
        if message:
            self.message = message
    
    def check_cancelled(self) -> bool:
        """检查是否被取消"""
        return self.cancelled
    
    def check_paused(self) -> bool:
        """检查是否被暂停"""
        # 如果被暂停，等待恢复
        while self.paused and not self.cancelled:
            time.sleep(0.1)
        return self.cancelled


@dataclass
class Task:
    """
    可管理任务
    
    特性：
    - 完整生命周期管理
    - 支持暂停/恢复/取消
    - 可编辑配置
    - 进度追踪
    - 执行历史
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    config: TaskConfig = field(default_factory=TaskConfig)
    
    # 状态
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    message: str = ""
    error: str = ""
    
    # 时间
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    paused_at: float = 0.0
    total_paused_time: float = 0.0  # 累计暂停时间
    
    # 执行
    handler: Callable = None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    
    # 回调
    on_progress: Callable = None
    on_complete: Callable = None
    on_error: Callable = None
    on_cancel: Callable = None
    
    # 内部
    _cancel_requested: bool = field(default=False, repr=False)
    _pause_requested: bool = field(default=False, repr=False)
    _resume_requested: bool = field(default=False, repr=False)
    _context: TaskContext = field(init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    
    def __post_init__(self):
        self._context = TaskContext(task_id=self.id)
    
    @property
    def title(self) -> str:
        return self.config.title or f"任务 {self.id}"
    
    @title.setter
    def title(self, value: str):
        self.config.title = value
    
    @property
    def description(self) -> str:
        return self.config.description
    
    @description.setter
    def description(self, value: str):
        self.config.description = value
    
    @property
    def priority(self) -> TaskPriority:
        return self.config.priority
    
    @priority.setter
    def priority(self, value: TaskPriority):
        self.config.priority = value
    
    @property
    def is_cancellable(self) -> bool:
        """是否可以取消"""
        return self.status in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.PAUSED)
    
    @property
    def is_pausable(self) -> bool:
        """是否可以暂停"""
        return self.status == TaskStatus.RUNNING
    
    @property
    def is_resumable(self) -> bool:
        """是否可以恢复"""
        return self.status == TaskStatus.PAUSED
    
    @property
    def is_editable(self) -> bool:
        """是否可以编辑"""
        return self.status in (TaskStatus.PENDING, TaskStatus.PAUSED)
    
    @property
    def execution_time(self) -> float:
        """实际执行时间（排除暂停）"""
        if self.started_at == 0:
            return 0.0
        
        end = self.completed_at if self.completed_at > 0 else time.time()
        return end - self.started_at - self.total_paused_time
    
    @property
    def wait_time(self) -> float:
        """等待时间"""
        if self.started_at > 0:
            return self.started_at - self.created_at
        return time.time() - self.created_at
    
    @property
    def state_text(self) -> str:
        """状态中文"""
        texts = {
            TaskStatus.PENDING: "等待中",
            TaskStatus.RUNNING: "执行中",
            TaskStatus.PAUSED: "已暂停",
            TaskStatus.COMPLETED: "已完成",
            TaskStatus.FAILED: "失败",
            TaskStatus.CANCELLED: "已取消",
        }
        return texts.get(self.status, "未知")
    
    @property
    def priority_text(self) -> str:
        """优先级中文"""
        texts = {
            TaskPriority.LOW: "低",
            TaskPriority.NORMAL: "普通",
            TaskPriority.HIGH: "高",
            TaskPriority.URGENT: "紧急",
        }
        return texts.get(self.priority, "普通")
    
    def update_config(self, **kwargs):
        """更新配置"""
        if not self.is_editable:
            return False
        
        with self._lock:
            if "title" in kwargs:
                self.config.title = kwargs["title"]
            if "description" in kwargs:
                self.config.description = kwargs["description"]
            if "priority" in kwargs:
                self.config.priority = kwargs["priority"]
            if "metadata" in kwargs:
                self.config.metadata.update(kwargs["metadata"])
        return True
    
    def request_pause(self):
        """请求暂停"""
        if self.is_pausable:
            self._pause_requested = True
            self._context.paused = True
            return True
        return False
    
    def request_resume(self):
        """请求恢复"""
        if self.is_resumable:
            self._resume_requested = True
            self._context.paused = False
            return True
        return False
    
    def request_cancel(self):
        """请求取消"""
        if self.is_cancellable:
            self._cancel_requested = True
            self._context.cancelled = True
            return True
        return False
    
    def _check_pause(self):
        """检查暂停请求"""
        while self._pause_requested and not self._cancel_requested:
            if self.status != TaskStatus.PAUSED:
                self.status = TaskStatus.PAUSED
                self.paused_at = time.time()
            time.sleep(0.1)
        
        # 恢复时记录暂停时间
        if self._resume_requested and self.status == TaskStatus.PAUSED:
            self.total_paused_time += time.time() - self.paused_at
            self.status = TaskStatus.RUNNING
            self._pause_requested = False
            self._resume_requested = False
    
    def _should_stop(self) -> bool:
        """检查是否应该停止"""
        return self._cancel_requested


class TaskManager(QObject):
    """
    任务管理器
    
    功能：
    - 任务注册和执行
    - 暂停/恢复/取消
    - 任务编辑
    - 批量操作
    - 事件信号
    """
    
    # 信号
    task_added = pyqtSignal(str)           # task_id
    task_updated = pyqtSignal(str)         # task_id
    task_started = pyqtSignal(str)         # task_id
    task_progress = pyqtSignal(str, float, str)  # task_id, progress, message
    task_completed = pyqtSignal(str, object)      # task_id, result
    task_failed = pyqtSignal(str, str)     # task_id, error
    task_cancelled = pyqtSignal(str)       # task_id
    task_paused = pyqtSignal(str)          # task_id
    task_resumed = pyqtSignal(str)         # task_id
    task_edited = pyqtSignal(str)           # task_id
    
    def __init__(self, max_concurrent: int = 3):
        super().__init__()
        self.max_concurrent = max_concurrent
        self._tasks: Dict[str, Task] = {}
        self._running: List[str] = []       # 正在执行的任务ID
        self._lock = threading.Lock()
        self._processing = False
        
        # 操作历史
        self._history: List[dict] = []
        self._max_history = 100
    
    # ── 任务注册 ──────────────────────────────────────────────────────────────
    
    def create_task(
        self,
        title: str,
        handler: Callable,
        *args,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        metadata: dict = None,
        on_progress: Callable = None,
        on_complete: Callable = None,
        on_error: Callable = None,
        on_cancel: Callable = None,
        **kwargs,
    ) -> str:
        """
        创建任务
        
        Args:
            title: 任务标题
            handler: 执行函数，支持接收 TaskContext 参数
            *args: 位置参数
            description: 描述
            priority: 优先级
            metadata: 元数据
            on_progress: 进度回调 (progress: float, message: str)
            on_complete: 完成回调 (result: Any)
            on_error: 错误回调 (error: str)
            on_cancel: 取消回调
            **kwargs: 关键字参数
            
        Returns:
            task_id
        """
        task = Task(
            config=TaskConfig(
                title=title,
                description=description,
                priority=priority,
                metadata=metadata or {},
            ),
            handler=handler,
            args=args,
            kwargs=kwargs,
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
            on_cancel=on_cancel,
        )
        
        with self._lock:
            self._tasks[task.id] = task
        
        self._add_history("created", task.id)
        self.task_added.emit(task.id)
        
        return task.id
    
    def execute_task(self, task_id: str) -> bool:
        """开始执行任务"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            if len(self._running) >= self.max_concurrent:
                return False
            
            task = self._tasks[task_id]
            
            if task.status != TaskStatus.PENDING:
                return False
            
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            self._running.append(task_id)
        
        self.task_started.emit(task_id)
        self._run_task_async(task)
        return True
    
    def _run_task_async(self, task: Task):
        """异步执行任务"""
        def run():
            try:
                # 准备上下文
                context = task._context
                context.status = TaskStatus.RUNNING
                
                # 执行前检查暂停
                task._check_pause()
                
                if task._should_stop():
                    self._finish_task(task, None, cancelled=True)
                    return
                
                # 调用处理器
                # 传递 context 作为第一个参数（如果 handler 接受）
                import inspect
                sig = inspect.signature(task.handler) if callable(task.handler) else None
                if sig and len(sig.parameters) > 0:
                    # handler 接受 TaskContext
                    result = task.handler(context, *task.args, **task.kwargs)
                else:
                    result = task.handler(*task.args, **task.kwargs)
                
                self._finish_task(task, result)
                
            except Exception as e:
                task.error = str(e)
                task.status = TaskStatus.FAILED
                task.completed_at = time.time()
                self._finish_task(task, None, error=str(e))
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
    
    def _finish_task(self, task: Task, result: Any, cancelled: bool = False, error: str = ""):
        """完成任务处理"""
        with self._lock:
            if task.id in self._running:
                self._running.remove(task.id)
            
            if cancelled:
                task.status = TaskStatus.CANCELLED
                task.completed_at = time.time()
                self._add_history("cancelled", task.id)
                self.task_cancelled.emit(task.id)
                if task.on_cancel:
                    try:
                        task.on_cancel()
                    except Exception:
                        pass
            
            elif error:
                task.status = TaskStatus.FAILED
                task.completed_at = time.time()
                task.error = error
                self._add_history("failed", task.id)
                self.task_failed.emit(task.id, error)
                if task.on_error:
                    try:
                        task.on_error(error)
                    except Exception:
                        pass
            
            else:
                task.status = TaskStatus.COMPLETED
                task.completed_at = time.time()
                self._add_history("completed", task.id)
                self.task_completed.emit(task.id, result)
                if task.on_complete:
                    try:
                        task.on_complete(result)
                    except Exception:
                        pass
        
        self.task_updated.emit(task.id)
    
    # ── 任务控制 ──────────────────────────────────────────────────────────────
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            task = self._tasks[task_id]
            
            if not task.is_pausable:
                return False
            
            task.request_pause()
        
        self.task_paused.emit(task_id)
        self._add_history("paused", task_id)
        return True
    
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            task = self._tasks[task_id]
            
            if not task.is_resumable:
                return False
            
            task.request_resume()
        
        self.task_resumed.emit(task_id)
        self._add_history("resumed", task_id)
        return True
    
    def cancel_task(self, task_id: str, force: bool = False) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            force: 是否强制取消（运行中的任务需要handler支持）
        """
        with self._lock:
            if task_id not in self._tasks:
                return False
            task = self._tasks[task_id]
            
            if not task.is_cancellable:
                return False
            
            # 如果是运行中的任务且不强制取消
            if task.status == TaskStatus.RUNNING and not force:
                # 请求取消，handler 需要检查 context.check_cancelled()
                task.request_cancel()
                return True
            
            # 直接取消
            task.request_cancel()
        
        # 如果在运行中，等待线程结束
        if task.status == TaskStatus.RUNNING:
            # 标记请求，让任务自行结束
            pass
        
        return True
    
    def cancel_all(self, status_filter: List[TaskStatus] = None) -> int:
        """批量取消任务"""
        if status_filter is None:
            status_filter = [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.PAUSED]
        
        count = 0
        with self._lock:
            for task_id, task in self._tasks.items():
                if task.status in status_filter:
                    task.request_cancel()
                    count += 1
        
        return count
    
    def retry_task(self, task_id: str) -> bool:
        """重试任务"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            task = self._tasks[task_id]
            
            if task.status not in (TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False
            
            # 重置状态
            task.status = TaskStatus.PENDING
            task.progress = 0.0
            task.message = ""
            task.error = ""
            task.started_at = 0.0
            task.completed_at = 0.0
            task.total_paused_time = 0.0
            task._cancel_requested = False
            task._pause_requested = False
            task._resume_requested = False
            task._context = TaskContext(task_id=task.id)
        
        self._add_history("retried", task_id)
        self.task_updated.emit(task_id)
        return self.execute_task(task_id)
    
    # ── 任务编辑 ──────────────────────────────────────────────────────────────
    
    def edit_task(
        self,
        task_id: str,
        title: str = None,
        description: str = None,
        priority: TaskPriority = None,
        metadata: dict = None,
    ) -> bool:
        """编辑任务配置"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            task = self._tasks[task_id]
            
            if not task.is_editable:
                return False
            
            updates = {}
            if title is not None and task.config.title != title:
                task.config.title = title
                updates["title"] = title
            if description is not None:
                task.config.description = description
                updates["description"] = description
            if priority is not None:
                task.config.priority = priority
                updates["priority"] = priority.value
            if metadata is not None:
                task.config.metadata.update(metadata)
                updates["metadata"] = metadata
        
        if updates:
            self._add_history("edited", task_id, updates)
            self.task_edited.emit(task_id)
        
        return True
    
    # ── 任务查询 ──────────────────────────────────────────────────────────────
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """按状态筛选"""
        return [t for t in self._tasks.values() if t.status == status]
    
    def get_running_tasks(self) -> List[Task]:
        """获取运行中的任务"""
        return self.get_tasks_by_status(TaskStatus.RUNNING)
    
    def get_pending_tasks(self) -> List[Task]:
        """获取等待中的任务"""
        return self.get_tasks_by_status(TaskStatus.PENDING)
    
    def get_paused_tasks(self) -> List[Task]:
        """获取暂停的任务"""
        return self.get_tasks_by_status(TaskStatus.PAUSED)
    
    def get_stats(self) -> dict:
        """获取统计"""
        stats = {
            "total": len(self._tasks),
            "pending": 0,
            "running": 0,
            "paused": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
        for task in self._tasks.values():
            stats[task.status.value] = stats.get(task.status.value, 0) + 1
        return stats
    
    def search_tasks(self, keyword: str) -> List[Task]:
        """搜索任务"""
        keyword = keyword.lower()
        results = []
        for task in self._tasks.values():
            if (keyword in task.title.lower() or
                keyword in task.description.lower() or
                keyword in task.id.lower()):
                results.append(task)
        return results
    
    # ── 任务清理 ──────────────────────────────────────────────────────────────
    
    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            if task.status == TaskStatus.RUNNING:
                return False
            
            if task_id in self._running:
                self._running.remove(task_id)
            
            del self._tasks[task_id]
        
        self._add_history("removed", task_id)
        return True
    
    def clear_completed(self) -> int:
        """清除已完成的任务"""
        count = 0
        with self._lock:
            to_remove = [
                tid for tid, t in self._tasks.items()
                if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            ]
            for tid in to_remove:
                del self._tasks[tid]
                count += 1
        
        return count
    
    # ── 历史记录 ──────────────────────────────────────────────────────────────
    
    def _add_history(self, action: str, task_id: str, details: dict = None):
        """添加历史记录"""
        record = {
            "action": action,
            "task_id": task_id,
            "timestamp": time.time(),
            "details": details or {},
        }
        self._history.append(record)
        
        # 限制历史数量
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
    
    def get_history(self, limit: int = 50) -> List[dict]:
        """获取历史记录"""
        return self._history[-limit:]
    
    # ── 进度更新 ──────────────────────────────────────────────────────────────
    
    def report_progress(self, task_id: str, progress: float, message: str = ""):
        """报告进度（供外部调用）"""
        with self._lock:
            if task_id not in self._tasks:
                return
            task = self._tasks[task_id]
            task.progress = max(0, min(100, progress))
            if message:
                task.message = message
            task._context.progress = task.progress
            task._context.message = message
        
        self.task_progress.emit(task_id, progress, message)
        
        # 调用回调
        task = self._tasks.get(task_id)
        if task and task.on_progress:
            try:
                task.on_progress(progress, message)
            except Exception:
                pass


# 全局单例
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """获取任务管理器单例"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager


# ── 导出 ─────────────────────────────────────────────────────────────────────

__all__ = [
    "TaskStatus",
    "TaskPriority",
    "TaskConfig",
    "TaskContext",
    "Task",
    "TaskManager",
    "get_task_manager",
]
