"""
任务调度器
DocLifecycle 任务调度器 - 智能调度批量审核任务
"""

import asyncio
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Any
from enum import Enum
from queue import PriorityQueue, Empty
import logging

from .models import ReviewTask, ReviewStatus, ReviewLevel, DocumentInfo


logger = logging.getLogger(__name__)


class SchedulerMode(Enum):
    """调度模式"""
    PARALLEL = "parallel"     # 并行调度
    SERIAL = "serial"        # 串行调度
    HYBRID = "hybrid"        # 混合调度
    DISTRIBUTED = "distributed"  # 分布式调度


@dataclass
class SchedulerConfig:
    """调度器配置"""
    mode: SchedulerMode = SchedulerMode.PARALLEL
    max_parallel_tasks: int = 4          # 最大并行任务数
    max_memory_per_task: int = 500 * 1024 * 1024  # 每个任务最大内存 500MB
    task_timeout: int = 300             # 任务超时时间(秒)
    retry_interval: int = 60            # 重试间隔(秒)
    max_retries: int = 3               # 最大重试次数
    queue_size: int = 100              # 队列大小
    enable_load_balancing: bool = True  # 启用负载均衡


class TaskScheduler:
    """审核任务调度器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, config: Optional[SchedulerConfig] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config: Optional[SchedulerConfig] = None):
        if self._initialized:
            return
            
        self.config = config or SchedulerConfig()
        self._task_queue: PriorityQueue = PriorityQueue(maxsize=self.config.queue_size)
        self._running_tasks: Dict[str, ReviewTask] = {}
        self._completed_tasks: Dict[str, ReviewTask] = {}
        self._task_handlers: Dict[str, Callable] = {}
        
        self._executor: Optional[ThreadPoolExecutor] = None
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False
        
        # 操作锁 - 保护 _running_tasks 和队列操作的线程安全
        self._lock = threading.Lock()
        
        # 统计信息
        self._stats = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "total_processing_time": 0.0
        }
        
        # 回调
        self._callbacks: Dict[str, List[Callable]] = {
            "task_started": [],
            "task_progress": [],
            "task_completed": [],
            "task_failed": [],
            "task_cancelled": [],
            "queue_updated": []
        }
        
        self._initialized = True
        logger.info("TaskScheduler initialized")
    
    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._task_handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")
    
    def register_callback(self, event: str, callback: Callable):
        """注册事件回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
        else:
            logger.warning(f"Unknown callback event: {event}")
    
    def submit_task(self, task: ReviewTask) -> str:
        """提交审核任务"""
        task.task_id = task.task_id or str(uuid.uuid4())
        task.created_at = datetime.now()
        task.status = ReviewStatus.QUEUED
        
        # 计算优先级
        priority = self._calculate_priority(task)
        
        # 线程安全：先加入 _running_tasks，再放入队列
        with self._lock:
            self._running_tasks[task.task_id] = task
            self._task_queue.put((priority, task.task_id, task))
        self._stats["total_submitted"] += 1
        
        logger.info(f"Task submitted: {task.task_id}, priority: {priority}")
        
        # 触发回调
        self._emit("queue_updated", self.get_queue_status())
        
        return task.task_id
    
    def submit_batch(self, tasks: List[ReviewTask]) -> List[str]:
        """批量提交任务"""
        task_ids = []
        for task in tasks:
            task_ids.append(self.submit_task(task))
        
        logger.info(f"Batch submitted: {len(tasks)} tasks")
        return task_ids
    
    def _calculate_priority(self, task: ReviewTask) -> int:
        """计算任务优先级"""
        # 优先级公式: 文档重要性 × 0.3 + 用户优先级 × 0.3 + 时间要求 × 0.2 + 资源需求 × 0.2
        # 映射到 1-10 范围
        
        doc_importance = 5  # 默认为中等
        if hasattr(task, 'doc_info') and task.doc_info:
            # 根据文档类型判断重要性
            if task.doc_info.file_type.value in ['pdf', 'doc', 'docx']:
                doc_importance = 7
            elif task.doc_info.file_type.value in ['xls', 'xlsx']:
                doc_importance = 6
        
        user_priority = task.priority
        time_requirement = 5  # 默认中等
        
        # 根据审核级别判断资源需求
        resource_need = 5
        if task.review_level == ReviewLevel.DEEP:
            resource_need = 8
        elif task.review_level == ReviewLevel.QUICK:
            resource_need = 3
        
        raw_priority = (
            doc_importance * 0.3 +
            user_priority * 0.3 +
            time_requirement * 0.2 +
            resource_need * 0.2
        )
        
        # 转换为 1-10
        return max(1, min(10, int(raw_priority)))
    
    def start(self):
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        
        # 创建线程池
        self._executor = ThreadPoolExecutor(
            max_workers=self.config.max_parallel_tasks,
            thread_name_prefix="doc_review_"
        )
        
        # 启动调度线程
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="TaskScheduler"
        )
        self._scheduler_thread.start()
        
        logger.info("TaskScheduler started")
    
    def stop(self):
        """停止调度器"""
        self._running = False
        
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
        
        logger.info("TaskScheduler stopped")
    
    def _scheduler_loop(self):
        """调度循环"""
        while self._running:
            try:
                self._dispatch_tasks()
                time.sleep(0.1)  # 避免CPU空转
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
    
    def _dispatch_tasks(self):
        """分发任务"""
        # 获取当前运行中的任务数（线程安全）
        with self._lock:
            active_count = sum(
                1 for t in self._running_tasks.values()
                if t.status == ReviewStatus.PROCESSING
            )
        
        # 根据调度模式分发
        if self.config.mode == SchedulerMode.PARALLEL:
            # 尽可能并行
            slots = self.config.max_parallel_tasks - active_count
        elif self.config.mode == SchedulerMode.SERIAL:
            # 串行：同时只运行一个
            slots = 1 if active_count == 0 else 0
        elif self.config.mode == SchedulerMode.HYBRID:
            # 混合：优先处理小文档和高优先级
            slots = self.config.max_parallel_tasks - active_count
        else:
            slots = self.config.max_parallel_tasks - active_count
        
        # 分发任务
        for _ in range(min(slots, self._task_queue.qsize())):
            try:
                _, task_id, task = self._task_queue.get_nowait()
                
                # 再次检查任务状态（线程安全）
                with self._lock:
                    if task_id in self._running_tasks:
                        task.status = ReviewStatus.PROCESSING
                        task.started_at = datetime.now()
                        
                        # 提交到线程池
                        self._executor.submit(self._execute_task, task)
                        
                        logger.info(f"Task dispatched: {task_id}")
            except Empty:
                break
            except Exception as e:
                logger.error(f"Error dispatching task: {e}")
    
    def _execute_task(self, task: ReviewTask):
        """执行任务"""
        try:
            logger.info(f"Executing task: {task.task_id}")
            
            # 触发开始回调
            self._emit("task_started", task)
            
            # 获取处理器
            handler = self._task_handlers.get("default")
            if handler is None:
                # 创建一个默认的处理器
                handler = self._default_task_handler
            
            # 执行处理
            if asyncio.iscoroutinefunction(handler):
                # 异步处理
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(handler(task))
                finally:
                    loop.close()
            else:
                # 同步处理
                result = handler(task)
            
            # 更新任务状态
            task.status = ReviewStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            task.progress = 1.0
            
            self._stats["total_completed"] += 1
            if task.completed_at and task.started_at:
                processing_time = (task.completed_at - task.started_at).total_seconds()
                self._stats["total_processing_time"] += processing_time
            
            logger.info(f"Task completed: {task.task_id}")
            
            # 触发完成回调
            self._emit("task_completed", task)
            
        except Exception as e:
            logger.error(f"Task execution error: {task.task_id}: {e}")
            task.status = ReviewStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now()
            
            # 尝试重试（线程安全）
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = ReviewStatus.QUEUED
                with self._lock:
                    self._task_queue.put((task.priority, task.task_id, task))
                logger.info(f"Task rescheduled for retry: {task.task_id}")
            else:
                self._stats["total_failed"] += 1
                self._emit("task_failed", task)
        finally:
            # 从运行中移到已完成（线程安全）
            with self._lock:
                if task.task_id in self._running_tasks:
                    self._running_tasks.pop(task.task_id)
                self._completed_tasks[task.task_id] = task
    
    def _default_task_handler(self, task: ReviewTask) -> Dict[str, Any]:
        """默认任务处理器"""
        # 模拟处理过程
        total_steps = 10
        for step in range(total_steps):
            if task.status == ReviewStatus.CANCELLED:
                raise Exception("Task cancelled")
            
            # 更新进度
            task.progress = (step + 1) / total_steps
            self._emit("task_progress", task)
            
            # 模拟处理
            time.sleep(0.1)
        
        return {
            "success": True,
            "message": "Task completed successfully",
            "doc_id": task.doc_id
        }
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            if task_id in self._running_tasks:
                task = self._running_tasks[task_id]
                
                if task.status == ReviewStatus.PROCESSING:
                    task.status = ReviewStatus.CANCELLED
                    self._stats["total_cancelled"] += 1
                    self._emit("task_cancelled", task)
                    logger.info(f"Task cancelled: {task_id}")
                    return True
                elif task.status == ReviewStatus.QUEUED:
                    # 从运行任务中移除（注意：无法从 PriorityQueue 中直接移除）
                    self._running_tasks.pop(task_id)
                    task.status = ReviewStatus.CANCELLED
                    self._stats["total_cancelled"] += 1
                    self._emit("task_cancelled", task)
                    logger.info(f"Task removed from queue: {task_id}")
                    return True
            
            return False
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        if task_id in self._running_tasks:
            task = self._running_tasks[task_id]
            if task.status == ReviewStatus.PROCESSING:
                # 标记为暂停状态
                task.status = ReviewStatus.PENDING
                logger.info(f"Task paused: {task_id}")
                return True
        return False
    
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        if task_id in self._running_tasks:
            task = self._running_tasks[task_id]
            if task.status == ReviewStatus.PENDING:
                task.status = ReviewStatus.QUEUED
                self._task_queue.put((task.priority, task.task_id, task))
                logger.info(f"Task resumed: {task_id}")
                return True
        return False
    
    def get_task(self, task_id: str) -> Optional[ReviewTask]:
        """获取任务信息（线程安全）"""
        with self._lock:
            if task_id in self._running_tasks:
                return self._running_tasks[task_id]
            if task_id in self._completed_tasks:
                return self._completed_tasks[task_id]
            return None
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态（线程安全）"""
        with self._lock:
            active_tasks = [
                t for t in self._running_tasks.values()
                if t.status == ReviewStatus.PROCESSING
            ]
            queued_tasks = [
                t for t in self._running_tasks.values()
                if t.status == ReviewStatus.QUEUED
            ]
            
            return {
                "queue_size": self._task_queue.qsize(),
                "running_count": len(active_tasks),
                "queued_count": len(queued_tasks),
                "completed_count": len(self._completed_tasks),
                "stats": self._stats.copy()
            }
    
    def get_all_tasks(self, status: Optional[ReviewStatus] = None) -> List[ReviewTask]:
        """获取所有任务（线程安全）"""
        with self._lock:
            all_tasks = list(self._running_tasks.values()) + list(self._completed_tasks.values())
            
            if status:
                all_tasks = [t for t in all_tasks if t.status == status]
            
            return sorted(all_tasks, key=lambda t: t.created_at, reverse=True)
    
    def _emit(self, event: str, *args):
        """触发事件回调"""
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                try:
                    callback(*args)
                except Exception as e:
                    logger.error(f"Callback error for {event}: {e}")
    
    def clear_completed(self, keep_recent: int = 100):
        """清理已完成任务"""
        completed_list = sorted(
            self._completed_tasks.items(),
            key=lambda x: x[1].completed_at or datetime.min,
            reverse=True
        )
        
        # 保留最近的
        to_keep = completed_list[:keep_recent]
        to_remove = completed_list[keep_recent:]
        
        for task_id, _ in to_remove:
            self._completed_tasks.pop(task_id, None)
        
        logger.info(f"Cleared {len(to_remove)} completed tasks")
        return len(to_remove)


# 全局实例
_scheduler_instance: Optional[TaskScheduler] = None


def get_task_scheduler(config: Optional[SchedulerConfig] = None) -> TaskScheduler:
    """获取任务调度器实例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = TaskScheduler(config)
    return _scheduler_instance
