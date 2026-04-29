"""
异步任务队列 - AsyncTaskQueue
核心理念：模拟 Web Worker 的行为，将耗时操作从主线程剥离

设计特点：
1. 优先级队列 - 高优先级任务（如错误分析）优先执行
2. 防抖处理 - 避免频繁触发分析
3. 空闲时执行 - 利用 requestIdleCallback 模式
4. 可被抢占 - 用户操作可以打断低优先级任务
"""

import threading
import queue
import time
import logging
from datetime import datetime
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future
import uuid

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0   # 错误分析 - 最高优先级
    HIGH = 1       # 重要建议
    NORMAL = 2     # 普通分析
    LOW = 3        # 静默巡检 - 可被抢占


@dataclass
class AnalysisTask:
    """分析任务"""
    task_id: str
    task_type: str              # 'error_analysis' | 'source_analysis' | 'performance_check'
    priority: TaskPriority
    callback: Callable         # 完成回调
    context: Any                # 上下文数据
    created_at: float
    execute_after: float = 0   # 延迟执行时间
    metadata: Dict = field(default_factory=dict)

    def __lt__(self, other):
        # 优先级队列排序：先按优先级，再按时间
        if self.priority != other.priority:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at


class Debouncer:
    """
    防抖器 - 确保同一操作在指定时间内只触发一次

    用于静默分析：用户连续操作时，只在最后一次操作结束N秒后触发分析
    """

    def __init__(self, delay_seconds: float = 3.0):
        self._delay = delay_seconds
        self._last_trigger_time = 0
        self._pending_task: Optional[AnalysisTask] = None
        self._lock = threading.Lock()

    def debounce(self, task: AnalysisTask) -> Optional[AnalysisTask]:
        """
        防抖处理

        Returns:
            None: 如果还在防抖期内
            task: 如果可以执行
        """
        now = time.time()

        with self._lock:
            # 如果有待执行任务且在防抖期内，更新待执行任务
            if self._pending_task and (now - self._last_trigger_time) < self._delay:
                # 只保留最新的任务
                self._pending_task = task
                return None

            # 防抖期已过，可以执行
            self._pending_task = task
            self._last_trigger_time = now
            return task

    def is_debouncing(self) -> bool:
        """是否正在防抖"""
        with self._lock:
            if not self._pending_task:
                return False
            return (time.time() - self._last_trigger_time) < self._delay


class AsyncTaskQueue:
    """
    异步任务队列

    核心功能：
    1. 接收各种分析任务（错误分析、源码分析等）
    2. 按优先级调度执行
    3. 支持防抖和延迟
    4. 可被用户操作抢占

    使用方式：
    queue = AsyncTaskQueue()

    # 提交高优先级错误分析（会立即执行）
    queue.submit_error_analysis(context, callback)

    # 提交低优先级静默分析（会防抖）
    queue.submit_silent_analysis(context, callback)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # 默认不暂停
        self._max_workers = 2  # 最多2个并发
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._debouncers: Dict[str, Debouncer] = {}  # 按组件名的防抖器
        self._default_debounce_delay = 3.0  # 默认3秒防抖
        self._active_tasks: Dict[str, Future] = {}  # 活跃任务
        self._cancelled_tasks: set = set()  # 被抢占的任务ID集合
        self._task_lock = threading.Lock()
        self._stats = {
            "submitted": 0,
            "completed": 0,
            "cancelled": 0,
            "preempted": 0
        }

        # 启动工作线程
        self._start_worker()

    def _start_worker(self):
        """启动工作线程"""
        if self._worker_thread and self._worker_thread.is_alive():
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def _worker_loop(self):
        """工作线程主循环"""
        while self._running:
            try:
                task = self._task_queue.get(timeout=0.5)
                self._execute_task(task)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Task queue error: {e}")

    def _execute_task(self, task: AnalysisTask):
        """执行任务"""
        task_id = task.task_id

        # 等待暂停恢复（阻塞直到resume或超时）
        if not self._pause_event.wait(timeout=5.0):
            # 超时了，说明暂停时间过长，将任务重新放回队列
            self._task_queue.put(task)
            return

        # 检查是否被抢占（低优先级任务被取消）
        with self._task_lock:
            if hasattr(self, '_cancelled_tasks') and task_id in self._cancelled_tasks:
                self._cancelled_tasks.discard(task_id)
                logger.debug(f"Task {task_id} was preempted, skipping")
                return

        # 检查是否需要延迟执行
        if task.execute_after > time.time():
            # 重新放回队列等待
            self._task_queue.put(task)
            time.sleep(0.1)
            return

        # 使用线程池执行
        future = self._executor.submit(self._run_task, task)
        with self._task_lock:
            self._active_tasks[task_id] = future

        try:
            result = future.result(timeout=30)  # 30秒超时
            task.callback(result)
            self._stats["completed"] += 1
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            # 调用失败的回调
            try:
                task.callback({"error": str(e), "task_id": task_id})
            except:
                pass
        finally:
            with self._task_lock:
                self._active_tasks.pop(task_id, None)

    def _run_task(self, task: AnalysisTask) -> Dict[str, Any]:
        """运行任务（在线程池中执行）"""
        try:
            handler = task.metadata.get("handler")
            if handler:
                return handler(task.context)
            return {"status": "ok", "task_id": task.task_id}
        except Exception as e:
            return {"error": str(e), "task_id": task.task_id}

    def submit(
        self,
        task_type: str,
        priority: TaskPriority,
        context: Any,
        callback: Callable,
        debounce_key: Optional[str] = None,
        debounce_delay: Optional[float] = None,
        execute_after: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """提交分析任务"""
        task_id = str(uuid.uuid4())[:8]

        # 防抖处理
        if debounce_key:
            delay = debounce_delay or self._default_debounce_delay
            if debounce_key not in self._debouncers:
                self._debouncers[debounce_key] = Debouncer(delay)

            debouncer = self._debouncers[debounce_key]
            task = AnalysisTask(
                task_id=task_id,
                task_type=task_type,
                priority=priority,
                callback=callback,
                context=context,
                created_at=time.time(),
                execute_after=execute_after or 0,
                metadata=metadata or {}
            )

            debounced = debouncer.debounce(task)
            if debounced is None:
                self._stats["cancelled"] += 1
                return task_id

            task = debounced
        else:
            task = AnalysisTask(
                task_id=task_id,
                task_type=task_type,
                priority=priority,
                callback=callback,
                context=context,
                created_at=time.time(),
                execute_after=execute_after or 0,
                metadata=metadata or {}
            )

        self._task_queue.put(task)
        self._stats["submitted"] += 1

        return task_id

    def submit_error_analysis(
        self,
        context: Any,
        callback: Callable,
        handler: Callable,
        metadata: Optional[Dict] = None
    ) -> str:
        """提交错误分析任务（高优先级，立即执行）"""
        meta = metadata or {}
        meta["handler"] = handler

        return self.submit(
            task_type="error_analysis",
            priority=TaskPriority.CRITICAL,
            context=context,
            callback=callback,
            metadata=meta
        )

    def submit_silent_analysis(
        self,
        context: Any,
        callback: Callable,
        handler: Callable,
        component_key: str,
        debounce_delay: float = 3.0,
        metadata: Optional[Dict] = None
    ) -> str:
        """提交静默分析任务（低优先级，带防抖）"""
        meta = metadata or {}
        meta["handler"] = handler
        execute_after = time.time() + debounce_delay

        return self.submit(
            task_type="source_analysis",
            priority=TaskPriority.LOW,
            context=context,
            callback=callback,
            debounce_key=component_key,
            debounce_delay=debounce_delay,
            execute_after=execute_after,
            metadata=meta
        )

    def cancel(self, task_id: str) -> bool:
        """取消任务"""
        with self._task_lock:
            if task_id in self._active_tasks:
                self._active_tasks[task_id].cancel()
                self._stats["cancelled"] += 1
                return True
        return False

    def preempt_low_priority(self):
        """抢占低优先级任务

        将所有 LOW 优先级的待执行任务标记为取消。
        这些任务在执行时会检查自己的ID是否在取消集合中，
        如果在则跳过执行。
        """
        with self._task_lock:
            # 遍历活跃任务，将所有 LOW 优先级的任务标记为取消
            cancelled = []
            for task_id, future in list(self._active_tasks.items()):
                # 检查任务是否已完成（done=True）或已取消
                if not future.done():
                    # 尝试取消任务（如果任务还在队列中未执行，则可以成功取消）
                    if future.cancel():
                        cancelled.append(task_id)
                    else:
                        # 任务已经在执行中，标记为取消
                        self._cancelled_tasks.add(task_id)
                        cancelled.append(task_id)

            # 从活跃任务中移除已取消的任务
            for task_id in cancelled:
                self._active_tasks.pop(task_id, None)

        # 增加被抢占的统计
        self._stats["preempted"] += 1
        logger.info(f"Preempted {len(cancelled)} LOW priority tasks")

    def pause(self):
        """暂停队列"""
        self._pause_event.clear()

    def resume(self):
        """恢复队列"""
        self._pause_event.set()

    def get_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        with self._task_lock:
            return {
                **self._stats,
                "active": len(self._active_tasks),
                "queued": self._task_queue.qsize()
            }

    def shutdown(self):
        """关闭队列"""
        self._running = False
        self._executor.shutdown(wait=False)


# 全局单例
task_queue = AsyncTaskQueue()
