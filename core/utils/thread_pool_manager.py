"""
Thread Pool Manager - 线程池管理器
====================================

统一管理 PyQt6 应用程序的线程池，提供：
- 全局单例访问
- 任务优先级
- 进度追踪
- 错误处理
"""

from PyQt6.QtCore import QThreadPool, QRunnable, pyqtSignal, QObject
from PyQt6.QtWidgets import QApplication
from typing import Optional, Callable, Any, List
from dataclasses import dataclass, field
from enum import IntEnum
from datetime import datetime
import traceback


class TaskPriority(IntEnum):
    """任务优先级"""
    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    worker: QRunnable
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    status: str = "pending"  # pending/running/completed/failed
    result: Any = None
    error: Optional[str] = None

    @property
    def duration(self) -> Optional[float]:
        """运行时长（秒）"""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class Worker(QRunnable):
    """
    标准工作器基类

    使用方式:
        class MyWorker(Worker):
            finished = pyqtSignal(object)
            progress = pyqtSignal(str)

            def run(self):
                try:
                    self.progress.emit("步骤1...")
                    result = step1()
                    self.progress.emit("步骤2...")
                    result = step2(result)
                    self.finished.emit(result)
                except Exception as e:
                    self.error.emit(str(e))
    """

    # 信号定义
    finished = pyqtSignal(object)  # 任务完成，结果
    progress = pyqtSignal(str)     # 进度更新，消息
    error = pyqtSignal(str)        # 错误发生，错误信息

    def __init__(self, task_id: Optional[str] = None, priority: TaskPriority = TaskPriority.NORMAL):
        super().__init__()
        self.task_id = task_id or f"task_{id(self)}"
        self.priority = priority
        self.setAutoDelete(True)  # 自动删除

    def run(self):
        """子类重写此方法"""
        raise NotImplementedError("子类必须实现 run 方法")


class LambdaWorker(Worker):
    """
    Lambda 工作器 - 支持直接传入函数

    使用方式:
        worker = LambdaWorker(
            task_fn=lambda: do_work(),
            finished_callback=lambda r: logger.info(r),
            progress_callback=lambda p: update_ui(p)
        )
        pool.run(worker)
    """

    def __init__(
        self,
        task_fn: Callable[[], Any],
        finished_callback: Optional[Callable[[Any], None]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
        error_callback: Optional[Callable[[str], None]] = None,
        task_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL
    ):
        super().__init__(task_id, priority)
        self.task_fn = task_fn
        self.finished_callback = finished_callback
        self.progress_callback = progress_callback
        self.error_callback = error_callback

        # 连接信号
        if finished_callback:
            self.finished.connect(finished_callback)
        if progress_callback:
            self.progress.connect(progress_callback)
        if error_callback:
            self.error.connect(error_callback)

    def run(self):
        """执行任务"""
        try:
            result = self.task_fn()
            self.finished.emit(result)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.info(f"[LambdaWorker] Error in {self.task_id}: {error_msg}")
            traceback.print_exc()
            self.error.emit(error_msg)


class ThreadPoolManager:
    """
    线程池管理器

    提供全局线程池的便捷访问和任务管理
    """

    _instance: Optional['ThreadPoolManager'] = None

    def __init__(self, max_threads: Optional[int] = None):
        # 获取全局线程池
        self._pool = QThreadPool.globalInstance()

        # 设置最大线程数
        if max_threads is not None:
            self._pool.setMaxThreadCount(max_threads)
        else:
            # 自动根据 CPU 核心数设置
            import os
            cpu_count = os.cpu_count() or 4
            self._pool.setMaxThreadCount(max(2, cpu_count - 1))

        # 任务跟踪
        self._tasks: dict[str, TaskInfo] = {}
        self._task_callbacks: dict[str, Callable] = {}

    @classmethod
    def get_instance(cls) -> 'ThreadPoolManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def pool(self) -> QThreadPool:
        """获取线程池"""
        return self._pool

    @property
    def max_threads(self) -> int:
        """最大线程数"""
        return self._pool.maxThreadCount()

    @property
    def active_threads(self) -> int:
        """活跃线程数"""
        return self._pool.activeThreadCount()

    def run(
        self,
        worker: Worker,
        finished_callback: Optional[Callable[[Any], None]] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """
        运行工作器

        Args:
            worker: Worker 实例
            finished_callback: 完成回调
            progress_callback: 进度回调

        Returns:
            task_id: 任务 ID
        """
        task_id = worker.task_id

        # 记录任务
        task_info = TaskInfo(task_id=task_id, worker=worker, priority=worker.priority)
        self._tasks[task_id] = task_info

        # 连接信号
        def on_finished(result):
            task_info.status = "completed"
            task_info.finished_at = datetime.now()
            task_info.result = result
            if finished_callback:
                finished_callback(result)

        def on_progress(msg):
            if progress_callback:
                progress_callback(msg)

        worker.finished.connect(on_finished)
        worker.progress.connect(on_progress)

        # 设置优先级
        self._pool.start(worker, worker.priority)

        return task_id

    def run_lambda(
        self,
        task_fn: Callable[[], Any],
        finished_callback: Optional[Callable[[Any], None]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
        error_callback: Optional[Callable[[str], None]] = None,
        task_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> str:
        """
        运行 Lambda 函数

        Args:
            task_fn: 要执行的函数
            finished_callback: 完成回调
            progress_callback: 进度回调
            error_callback: 错误回调
            task_id: 任务 ID
            priority: 优先级

        Returns:
            task_id: 任务 ID
        """
        worker = LambdaWorker(
            task_fn=task_fn,
            finished_callback=finished_callback,
            progress_callback=progress_callback,
            error_callback=error_callback,
            task_id=task_id,
            priority=priority
        )
        return self.run(worker, finished_callback, progress_callback)

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务信息"""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[TaskInfo]:
        """获取所有任务"""
        return list(self._tasks.values())

    def get_active_tasks(self) -> List[TaskInfo]:
        """获取活跃任务"""
        return [t for t in self._tasks.values() if t.status == "running"]

    def clear_finished_tasks(self):
        """清理已完成任务"""
        self._tasks = {
            k: v for k, v in self._tasks.items()
            if v.status in ("pending", "running")
        }

    def cancel_task(self, task_id: str) -> bool:
        """取消任务（仅对 pending 任务有效）"""
        task = self._tasks.get(task_id)
        if task and task.status == "pending":
            # QThreadPool 不支持取消单个任务
            # 只能标记
            task.status = "cancelled"
            return True
        return False

    def cancel_all(self):
        """取消所有任务"""
        self._pool.cancel()
        for task in self._tasks.values():
            if task.status == "pending":
                task.status = "cancelled"

    def wait_for_done(self, msecs: int = -1) -> bool:
        """
        等待所有任务完成

        Args:
            msecs: 超时毫秒，-1 表示无限等待

        Returns:
            是否全部完成
        """
        return self._pool.waitForDone(msecs)


# ═══════════════════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════════════════

def get_pool() -> ThreadPoolManager:
    """获取线程池管理器"""
    return ThreadPoolManager.get_instance()


def run_async(
    task_fn: Callable[[], Any],
    finished_callback: Optional[Callable[[Any], None]] = None,
    progress_callback: Optional[Callable[[str], None]] = None
) -> str:
    """
    便捷函数：异步运行任务

    使用方式:
        def long_task():
            for i in range(10):
                time.sleep(0.5)
            return "完成!"

        def on_done(result):
            logger.info(f"结果: {result}")

        run_async(long_task, on_done)
    """
    return get_pool().run_lambda(
        task_fn=task_fn,
        finished_callback=finished_callback,
        progress_callback=progress_callback
    )


# ═══════════════════════════════════════════════════════════════════════════
# 示例
# ═══════════════════════════════════════════════════════════════════════════

"""
# 示例 1: 使用 LambdaWorker
from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget
import time
from core.logger import get_logger
logger = get_logger('utils.thread_pool_manager')


def heavy_task():
    time.sleep(2)
    return "任务完成!"

def on_finished(result):
    logger.info(f"收到结果: {result}")

button = QPushButton("执行任务")
button.clicked.connect(lambda:
    get_pool().run_lambda(
        heavy_task,
        finished_callback=on_finished,
        progress_callback=lambda p: logger.info(f"进度: {p}")
    )
)


# 示例 2: 自定义 Worker
class MyWorker(Worker):
    def __init__(self, data):
        super().__init__(task_id="my_task")
        self.data = data

    def run(self):
        self.progress.emit("开始处理...")
        result = process(self.data)
        self.progress.emit("处理完成!")
        self.finished.emit(result)


worker = MyWorker(data)
get_pool().run(worker, on_finished)


# 示例 3: 在 UI 中使用
class MyWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.result_label = QLabel()

    def do_async_work(self):
        self.result_label.setText("处理中...")

        def task():
            time.sleep(2)
            return "结果: 42"

        def on_done(result):
            self.result_label.setText(result)

        run_async(task, on_done)
"""
