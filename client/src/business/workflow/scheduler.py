"""
Scheduler - 定时调度器

支持定时调度执行工作流。

遵循自我进化原则：
- 从执行历史中学习优化调度策略
- 支持动态添加/删除定时任务
"""

import asyncio
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime, timedelta
from enum import Enum


class ScheduleType(Enum):
    """调度类型"""
    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    CRON = "cron"


@dataclass
class ScheduledTask:
    """定时任务"""
    task_id: str
    name: str
    handler: Callable
    schedule_type: ScheduleType
    schedule_params: Dict[str, Any]
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0


class Scheduler:
    """
    定时调度器
    
    支持定时调度执行工作流。
    """

    def __init__(self):
        self._logger = logger.bind(component="Scheduler")
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._loop = None
        self._scheduler_task = None

    async def start(self):
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        self._loop = asyncio.get_event_loop()
        self._logger.info("启动定时调度器")
        
        # 启动调度循环
        self._scheduler_task = self._loop.create_task(self._scheduler_loop())

    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
        self._logger.info("停止定时调度器")

    async def _scheduler_loop(self):
        """调度循环"""
        while self._running:
            now = datetime.now()
            
            for task_id, task in list(self._tasks.items()):
                if not task.enabled:
                    continue
                
                if task.next_run is None:
                    task.next_run = self._calculate_next_run(task, now)
                
                if task.next_run <= now:
                    await self._execute_task(task, now)
                    task.next_run = self._calculate_next_run(task, now)
            
            await asyncio.sleep(1)

    def _calculate_next_run(self, task: ScheduledTask, now: datetime) -> datetime:
        """计算下次执行时间"""
        if task.schedule_type == ScheduleType.ONCE:
            # 单次执行，使用指定时间
            return task.schedule_params.get("time", now)
        
        elif task.schedule_type == ScheduleType.HOURLY:
            interval = task.schedule_params.get("interval", 1)
            return now + timedelta(hours=interval)
        
        elif task.schedule_type == ScheduleType.DAILY:
            # 在指定时间执行
            time_str = task.schedule_params.get("time", "00:00")
            hours, minutes = map(int, time_str.split(":"))
            
            next_run = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            
            return next_run
        
        elif task.schedule_type == ScheduleType.WEEKLY:
            day_of_week = task.schedule_params.get("day_of_week", 0)  # 0=周一
            time_str = task.schedule_params.get("time", "00:00")
            hours, minutes = map(int, time_str.split(":"))
            
            days_ahead = (day_of_week - now.weekday()) % 7
            if days_ahead == 0 and now.hour >= hours and now.minute >= minutes:
                days_ahead = 7
            
            next_run = now + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            
            return next_run
        
        elif task.schedule_type == ScheduleType.CRON:
            # 简单的 cron 支持
            cron_expr = task.schedule_params.get("cron", "* * * * *")
            # 解析 cron 表达式（简化实现）
            parts = cron_expr.split()
            if len(parts) == 5:
                minute, hour, day, month, weekday = parts
                
                # 简单实现：只处理分钟和小时
                try:
                    next_minute = int(minute) if minute != "*" else now.minute
                    next_hour = int(hour) if hour != "*" else now.hour
                    
                    next_run = now.replace(hour=next_hour, minute=next_minute, second=0, microsecond=0)
                    if next_run <= now:
                        next_run += timedelta(hours=1)
                    return next_run
                except:
                    pass
            
            # 默认每小时执行
            return now + timedelta(hours=1)
        
        return now + timedelta(hours=1)

    async def _execute_task(self, task: ScheduledTask, now: datetime):
        """执行任务"""
        self._logger.info(f"执行定时任务: {task.name}")
        task.last_run = now
        task.run_count += 1
        
        try:
            await task.handler()
            self._logger.info(f"任务 {task.name} 执行成功")
        except Exception as e:
            task.error_count += 1
            self._logger.error(f"任务 {task.name} 执行失败: {e}")

    def add_task(
        self,
        task_id: str,
        name: str,
        handler: Callable,
        schedule_type: ScheduleType,
        **schedule_params
    ):
        """
        添加定时任务
        
        Args:
            task_id: 任务 ID
            name: 任务名称
            handler: 任务处理函数
            schedule_type: 调度类型
            schedule_params: 调度参数
        """
        if task_id in self._tasks:
            raise ValueError(f"任务已存在: {task_id}")
        
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            handler=handler,
            schedule_type=schedule_type,
            schedule_params=schedule_params
        )
        
        self._tasks[task_id] = task
        self._logger.info(f"已添加定时任务: {name}")

    def remove_task(self, task_id: str):
        """
        删除定时任务
        
        Args:
            task_id: 任务 ID
        """
        if task_id not in self._tasks:
            raise ValueError(f"任务不存在: {task_id}")
        
        del self._tasks[task_id]
        self._logger.info(f"已删除定时任务: {task_id}")

    def enable_task(self, task_id: str):
        """启用任务"""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = True
            self._logger.info(f"已启用任务: {task_id}")

    def disable_task(self, task_id: str):
        """禁用任务"""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = False
            self._logger.info(f"已禁用任务: {task_id}")

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """获取任务"""
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有任务"""
        result = []
        for task in self._tasks.values():
            result.append({
                "task_id": task.task_id,
                "name": task.name,
                "schedule_type": task.schedule_type.value,
                "enabled": task.enabled,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "next_run": task.next_run.isoformat() if task.next_run else None,
                "run_count": task.run_count,
                "error_count": task.error_count
            })
        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取调度器统计信息"""
        total_tasks = len(self._tasks)
        enabled_tasks = sum(1 for t in self._tasks.values() if t.enabled)
        total_runs = sum(t.run_count for t in self._tasks.values())
        total_errors = sum(t.error_count for t in self._tasks.values())
        
        return {
            "status": "running" if self._running else "stopped",
            "total_tasks": total_tasks,
            "enabled_tasks": enabled_tasks,
            "total_runs": total_runs,
            "total_errors": total_errors,
            "error_rate": total_errors / max(total_runs, 1)
        }