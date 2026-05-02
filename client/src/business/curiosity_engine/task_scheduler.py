"""
定时任务调度器 - 支持用户查看和取消任务

核心功能：
1. 定时扫描任务
2. 定时学习任务
3. 用户可查看任务列表
4. 用户可取消任务
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(Enum):
    """任务类型"""
    AUTO_SCAN = "auto_scan"
    LEARNING = "learning"
    AUDIT = "audit"
    IMPROVEMENT = "improvement"


@dataclass
class ScheduledTask:
    """定时任务"""
    task_id: str
    task_type: TaskType
    name: str
    description: str
    schedule: str  # cron表达式或间隔时间（秒）
    status: TaskStatus = TaskStatus.PENDING
    next_run_time: float = 0
    last_run_time: float = 0
    run_count: int = 0
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    _cancelled: bool = False


class TaskScheduler:
    """
    定时任务调度器
    
    支持：
    - 定时扫描本地文件
    - 定时学习任务
    - 用户查看任务列表
    - 用户取消任务
    """
    
    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
        self.is_running = False
        self._task_futures: Dict[str, asyncio.Future] = {}
    
    def start(self):
        """启动调度器"""
        if self.is_running:
            return
        
        self.is_running = True
        asyncio.create_task(self._scheduler_loop())
        logger.info("🚀 定时任务调度器启动")
    
    def stop(self):
        """停止调度器"""
        self.is_running = False
        
        # 取消所有任务
        for future in self._task_futures.values():
            if not future.done():
                future.cancel()
        
        logger.info("🛑 定时任务调度器停止")
    
    def add_task(
        self,
        task_type: TaskType,
        name: str,
        description: str,
        schedule: str,
        callback: Callable,
        **kwargs
    ) -> str:
        """
        添加定时任务
        
        Args:
            task_type: 任务类型
            name: 任务名称
            description: 任务描述
            schedule: 调度间隔（秒）或cron表达式
            callback: 任务回调函数
            kwargs: 额外参数
        
        Returns:
            任务ID
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        
        # 解析调度时间
        try:
            interval = int(schedule)
            next_run = time.time() + interval
        except ValueError:
            # 尝试解析cron表达式（简化实现）
            next_run = time.time() + 3600  # 默认1小时
        
        task = ScheduledTask(
            task_id=task_id,
            task_type=task_type,
            name=name,
            description=description,
            schedule=schedule,
            next_run_time=next_run,
            metadata={
                "callback": callback,
                "kwargs": kwargs
            }
        )
        
        self.tasks[task_id] = task
        logger.info(f"➕ 添加定时任务: {name} (ID: {task_id})")
        
        return task_id
    
    def remove_task(self, task_id: str) -> bool:
        """
        移除任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            是否成功
        """
        if task_id in self.tasks:
            # 取消正在运行的任务
            if task_id in self._task_futures:
                self._task_futures[task_id].cancel()
            
            del self.tasks[task_id]
            logger.info(f"➖ 移除定时任务: {task_id}")
            return True
        
        return False
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务（标记为已取消，下次不执行）
        
        Args:
            task_id: 任务ID
        
        Returns:
            是否成功
        """
        if task_id in self.tasks:
            self.tasks[task_id]._cancelled = True
            self.tasks[task_id].status = TaskStatus.CANCELLED
            
            # 取消正在运行的任务
            if task_id in self._task_futures:
                self._task_futures[task_id].cancel()
            
            logger.info(f"❌ 取消定时任务: {task_id}")
            return True
        
        return False
    
    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """获取任务信息"""
        return self.tasks.get(task_id)
    
    def get_tasks(self, status: Optional[TaskStatus] = None) -> List[ScheduledTask]:
        """
        获取任务列表
        
        Args:
            status: 按状态筛选（可选）
        
        Returns:
            任务列表
        """
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        return sorted(tasks, key=lambda t: t.next_run_time)
    
    def get_tasks_summary(self) -> List[Dict[str, Any]]:
        """获取任务摘要列表（用于前端展示）"""
        summary = []
        
        for task in self.get_tasks():
            summary.append({
                "task_id": task.task_id,
                "name": task.name,
                "type": task.task_type.value,
                "status": task.status.value,
                "schedule": task.schedule,
                "next_run_time": datetime.fromtimestamp(task.next_run_time).isoformat(),
                "last_run_time": datetime.fromtimestamp(task.last_run_time).isoformat() if task.last_run_time else None,
                "run_count": task.run_count,
                "error_message": task.error_message
            })
        
        return summary
    
    async def _scheduler_loop(self):
        """调度器主循环"""
        while self.is_running:
            await asyncio.sleep(1)
            
            now = time.time()
            
            for task_id, task in list(self.tasks.items()):
                # 检查任务是否已取消
                if task._cancelled:
                    continue
                
                # 检查是否到执行时间
                if now >= task.next_run_time:
                    await self._execute_task(task_id)
    
    async def _execute_task(self, task_id: str):
        """执行任务"""
        task = self.tasks.get(task_id)
        if not task or task._cancelled:
            return
        
        task.status = TaskStatus.RUNNING
        task.last_run_time = time.time()
        
        logger.debug(f"🔄 执行任务: {task.name}")
        
        try:
            callback = task.metadata.get("callback")
            kwargs = task.metadata.get("kwargs", {})
            
            if callback:
                # 异步执行回调
                future = asyncio.create_task(callback(**kwargs))
                self._task_futures[task_id] = future
                
                try:
                    await future
                except asyncio.CancelledError:
                    task.status = TaskStatus.CANCELLED
                    logger.info(f"任务已取消: {task.name}")
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                    logger.error(f"❌ 任务执行失败 {task.name}: {e}")
                else:
                    task.status = TaskStatus.COMPLETED
                    task.run_count += 1
                    logger.debug(f"✅ 任务完成: {task.name}")
                finally:
                    del self._task_futures[task_id]
            
            # 计算下次执行时间
            try:
                interval = int(task.schedule)
                task.next_run_time = time.time() + interval
            except ValueError:
                task.next_run_time = time.time() + 3600
        
        except Exception as e:
            logger.error(f"❌ 任务调度失败 {task.name}: {e}")
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
    
    def schedule_auto_scan(self, interval: int = 3600) -> str:
        """
        调度自动扫描任务
        
        Args:
            interval: 扫描间隔（秒），默认1小时
        
        Returns:
            任务ID
        """
        from .curiosity_engine import get_curiosity_engine
        
        async def scan_callback():
            engine = get_curiosity_engine()
            await asyncio.to_thread(engine.auto_scan)
        
        return self.add_task(
            task_type=TaskType.AUTO_SCAN,
            name="自动扫描",
            description="自动扫描本地文件系统",
            schedule=str(interval),
            callback=scan_callback
        )
    
    def schedule_learning(self, interval: int = 1800) -> str:
        """
        调度学习任务
        
        Args:
            interval: 学习间隔（秒），默认30分钟
        
        Returns:
            任务ID
        """
        from .curiosity_engine import get_curiosity_engine
        
        async def learning_callback():
            engine = get_curiosity_engine()
            # 检查是否有待处理任务
            pending = engine.get_learning_tasks(status="pending")
            if pending:
                for task in pending[:2]:  # 每次最多处理2个任务
                    await engine._execute_learning_task(task)
        
        return self.add_task(
            task_type=TaskType.LEARNING,
            name="自主学习",
            description="处理待学习任务",
            schedule=str(interval),
            callback=learning_callback
        )


# 单例模式
_task_scheduler = None


def get_task_scheduler() -> TaskScheduler:
    """获取任务调度器单例"""
    global _task_scheduler
    if _task_scheduler is None:
        _task_scheduler = TaskScheduler()
    return _task_scheduler