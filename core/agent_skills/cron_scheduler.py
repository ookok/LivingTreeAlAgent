"""
自然语言定时任务调度器
=====================

参考 Hermes Agent 的 Cron 模块：
- 使用自然语言配置定时任务
- 支持 cron 表达式解析
- 任务执行和通知

核心功能：
1. 自然语言解析 - 将日常语言转换为定时任务
2. Cron 调度 - 标准 cron 表达式支持
3. 任务执行 - 自动执行预定义任务
4. 执行记录 - 追踪任务执行历史

Author: Hermes Desktop Team
Date: 2026-04-25
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import threading
import time
import queue

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"      # 等待执行
    RUNNING = "running"     # 执行中
    COMPLETED = "completed" # 已完成
    FAILED = "failed"       # 失败
    CANCELLED = "cancelled" # 已取消
    PAUSED = "paused"       # 暂停


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


@dataclass
class ScheduledTask:
    """定时任务"""
    task_id: str
    name: str
    description: str = ""
    
    # 调度配置
    cron_expression: Optional[str] = None  # Cron 表达式
    interval_seconds: Optional[int] = None  # 间隔秒数
    scheduled_time: Optional[datetime] = None  # 一次性执行时间
    
    # 执行配置
    command: str = ""  # 要执行的命令/任务
    agent_action: Optional[str] = None  # Agent 动作
    params: Dict[str, Any] = field(default_factory=dict)
    
    # 状态
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    enabled: bool = True
    
    # 执行统计
    run_count: int = 0
    success_count: int = 0
    last_run: Optional[datetime] = None
    last_result: Optional[str] = None
    last_error: Optional[str] = None
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    next_run: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "cron_expression": self.cron_expression,
            "interval_seconds": self.interval_seconds,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "command": self.command,
            "agent_action": self.agent_action,
            "params": self.params,
            "status": self.status.value,
            "priority": self.priority.value,
            "enabled": self.enabled,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "tags": self.tags,
        }


@dataclass
class ExecutionRecord:
    """执行记录"""
    task_id: str
    execution_time: datetime
    status: TaskStatus
    duration_seconds: float
    result: Optional[str] = None
    error: Optional[str] = None


class CronParser:
    """
    Cron 表达式解析器
    
    支持标准 5 段 cron 表达式：
    ┌───────────── 分钟 (0 - 59)
    │ ┌─────────── 小时 (0 - 23)
    │ │ ┌───────── 日 (1 - 31)
    │ │ │ ┌─────── 月 (1 - 12)
    │ │ │ │ ┌───── 星期 (0 - 6, 0 = 周日)
    │ │ │ │ │
    * * * * *
    """
    
    # 时间字段范围
    FIELDS = {
        "minute": (0, 59),
        "hour": (0, 23),
        "day": (1, 31),
        "month": (1, 12),
        "weekday": (0, 6),
    }
    
    @classmethod
    def parse(cls, expression: str) -> Dict[str, List[int]]:
        """
        解析 cron 表达式
        
        Args:
            expression: cron 表达式字符串
            
        Returns:
            解析后的字段值字典
        """
        parts = expression.split()
        if len(parts) != 5:
            raise ValueError(f"无效的 cron 表达式: {expression}，需要5个字段")
            
        result = {}
        field_names = ["minute", "hour", "day", "month", "weekday"]
        
        for i, part in enumerate(parts):
            field_name = field_names[i]
            min_val, max_val = cls.FIELDS[field_name]
            result[field_name] = cls._parse_field(part, min_val, max_val, field_name)
            
        return result
        
    @classmethod
    def _parse_field(
        cls,
        field_str: str,
        min_val: int,
        max_val: int,
        field_name: str
    ) -> List[int]:
        """解析单个字段"""
        values = set()
        
        for part in field_str.split(','):
            if '/' in part:
                # 步进值: */5, 1-10/2
                base, step = part.split('/')
                step = int(step)
                if base == '*':
                    range_vals = range(min_val, max_val + 1)
                elif '-' in base:
                    start, end = base.split('-')
                    range_vals = range(int(start), int(end) + 1)
                else:
                    range_vals = range(int(base), max_val + 1)
                values.update(range_vals[::step])
            elif '-' in part:
                # 范围: 1-5
                start, end = part.split('-')
                values.update(range(int(start), int(end) + 1))
            elif part == '*':
                # 所有值
                values.update(range(min_val, max_val + 1))
            else:
                # 单个值
                values.add(int(part))
                
        return sorted(values)
        
    @classmethod
    def get_next_run(cls, expression: str, from_time: Optional[datetime] = None) -> datetime:
        """
        计算下次执行时间
        
        Args:
            expression: cron 表达式
            from_time: 起始时间（默认现在）
            
        Returns:
            下次执行时间
        """
        if from_time is None:
            from_time = datetime.now()
            
        fields = cls.parse(expression)
        
        # 向前推进到下一个可能的执行时间
        current = from_time.replace(second=0, microsecond=0)
        
        for _ in range(366 * 24 * 60):  # 最多检查一年
            current += timedelta(minutes=1)
            
            if (
                current.minute in fields["minute"] and
                current.hour in fields["hour"] and
                (current.day in fields["day"] or fields["day"] == list(range(1, 32))) and
                current.month in fields["month"] and
                current.weekday in fields["weekday"]
            ):
                return current
                
        raise ValueError("无法计算下次执行时间")


class NaturalLanguageScheduler:
    """
    自然语言定时解析器
    
    将日常语言转换为定时任务配置
    
    Examples:
        "每天早上9点" → cron="0 9 * * *"
        "每5分钟" → interval=300
        "每周一早上8点" → cron="0 8 * * 1"
        "明天下午3点" → scheduled_time=tomorrow 15:00
    """
    
    # 时间模式
    TIME_PATTERNS = {
        # 间隔模式
        r"每(\d+)秒": {"unit": "second", "group": 1},
        r"每(\d+)分钟": {"unit": "minute", "group": 1},
        r"每(\d+)小时": {"unit": "hour", "group": 1},
        r"每(\d+)天": {"unit": "day", "group": 1},
        r"每秒": {"unit": "second", "value": 1},
        r"每分钟": {"unit": "minute", "value": 1},
        r"每小时": {"unit": "hour", "value": 1},
        r"每天": {"unit": "day", "value": 1},
        r"每周": {"unit": "week", "value": 1},
        
        # 时刻模式
        r"早上(\d+)点": {"hour": 1, "suffix": "AM"},
        r"下午(\d+)点": {"hour": 2, "suffix": "PM"},
        r"晚上(\d+)点": {"hour": 3, "suffix": "PM"},
        r"凌晨(\d+)点": {"hour": 0, "suffix": "AM"},
        r"中午(\d+)点": {"hour": 12, "suffix": "PM"},
        r"(\d+)点": {"hour": 3, "suffix": "AUTO"},
    }
    
    # 星期映射
    WEEKDAY_MAP = {
        "周一": 1, "星期一": 1, "monday": 1,
        "周二": 2, "星期二": 2, "tuesday": 2,
        "周三": 3, "星期三": 3, "wednesday": 3,
        "周四": 4, "星期四": 4, "thursday": 4,
        "周五": 5, "星期五": 5, "friday": 5,
        "周六": 6, "星期六": 6, "saturday": 6,
        "周日": 0, "星期日": 0, "sunday": 0,
    }
    
    @classmethod
    def parse(cls, natural_text: str) -> Dict[str, Any]:
        """
        解析自然语言定时描述
        
        Args:
            natural_text: 自然语言描述
            
        Returns:
            定时配置字典
        """
        text = natural_text.strip().lower()
        config: Dict[str, Any] = {}
        
        # 解析星期
        weekday = None
        for day_name, day_num in cls.WEEKDAY_MAP.items():
            if day_name.lower() in text:
                weekday = day_num
                break
                
        # 解析间隔
        for pattern, spec in cls.TIME_PATTERNS.items():
            match = re.search(pattern, text)
            if match:
                if "unit" in spec:
                    unit = spec["unit"]
                    if "value" in spec:
                        value = spec["value"]
                    else:
                        value = int(match.group(int(spec["group"])))
                        
                    if unit == "second":
                        config["interval_seconds"] = value
                    elif unit == "minute":
                        config["interval_seconds"] = value * 60
                    elif unit == "hour":
                        config["interval_seconds"] = value * 3600
                    elif unit == "day":
                        config["interval_seconds"] = value * 86400
                    elif unit == "week":
                        config["cron_expression"] = f"0 0 * * {weekday or 0}"
                    break
                    
                elif "hour" in spec:
                    hour_str = match.group(1)
                    hour = int(hour_str)
                    suffix = spec.get("suffix", "AUTO")
                    
                    if suffix == "AM":
                        pass  # 保持原样
                    elif suffix == "PM" and hour != 12:
                        hour += 12
                    elif suffix == "PM" and hour == 12:
                        pass  # 中午12点
                    elif suffix == "AUTO":
                        # 智能判断上下午
                        if "早上" in text or "上午" in text:
                            pass
                        elif "下午" in text or hour > 6:
                            hour += 12
                            
                    config["hour"] = hour
                    config["minute"] = 0
                    break
                    
        # 构建 cron 表达式
        if "hour" in config and "minute" in config:
            hour = config.pop("hour")
            minute = config.pop("minute")
            day = "*"
            month = "*"
            weekday_str = str(weekday) if weekday is not None else "*"
            config["cron_expression"] = f"{minute} {hour} {day} {month} {weekday_str}"
            
        return config


class CronScheduler:
    """
    定时任务调度器
    
    支持：
    - Cron 表达式调度
    - 间隔执行
    - 一次性定时
    - 自然语言配置
    
    Usage:
        scheduler = CronScheduler()
        
        # 方式1: Cron 表达式
        scheduler.schedule_cron(
            name="每日报告",
            cron="0 9 * * *",
            command="generate_report"
        )
        
        # 方式2: 自然语言
        scheduler.schedule_natural(
            name="每小时检查",
            natural="每1小时",
            command="health_check"
        )
        
        # 方式3: 间隔执行
        scheduler.schedule_interval(
            name="数据同步",
            interval=300,  # 5分钟
            command="sync_data"
        )
        
        # 启动调度器
        scheduler.start()
        
        # 停止
        scheduler.stop()
    """
    
    def __init__(self, max_concurrent: int = 5):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._execution_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._max_concurrent = max_concurrent
        self._active_executions = 0
        self._execution_history: List[ExecutionRecord] = []
        self._max_history = 100
        
        # 回调函数
        self._on_task_execute: Optional[Callable] = None
        self._on_task_complete: Optional[Callable] = None
        self._on_task_error: Optional[Callable] = None
        
    def schedule_cron(
        self,
        name: str,
        cron_expression: str,
        command: str = "",
        agent_action: Optional[str] = None,
        params: Optional[Dict] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        tags: Optional[List[str]] = None,
    ) -> ScheduledTask:
        """
        创建 Cron 定时任务
        
        Args:
            name: 任务名称
            cron_expression: cron 表达式
            command: 要执行的命令
            agent_action: Agent 动作
            params: 额外参数
            priority: 优先级
            tags: 标签
            
        Returns:
            创建的任务
        """
        task_id = f"cron-{name.lower().replace(' ', '-')[:30]}-{datetime.now().strftime('%Y%m%d%H%M')}"
        
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            cron_expression=cron_expression,
            command=command,
            agent_action=agent_action,
            params=params or {},
            priority=priority,
            tags=tags or [],
        )
        
        # 计算下次执行时间
        task.next_run = CronParser.get_next_run(cron_expression)
        
        self._tasks[task_id] = task
        logger.info(f"[CronScheduler] 创建定时任务: {name} (ID: {task_id}), 下次执行: {task.next_run}")
        
        return task
        
    def schedule_natural(
        self,
        name: str,
        natural: str,
        command: str = "",
        agent_action: Optional[str] = None,
        params: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> ScheduledTask:
        """
        使用自然语言创建定时任务
        
        Args:
            name: 任务名称
            natural: 自然语言描述
            command: 要执行的命令
            agent_action: Agent 动作
            params: 额外参数
            tags: 标签
            
        Returns:
            创建的任务
        """
        config = NaturalLanguageScheduler.parse(natural)
        
        if "interval_seconds" in config:
            return self.schedule_interval(
                name=name,
                interval=config["interval_seconds"],
                command=command,
                agent_action=agent_action,
                params=params,
                tags=tags,
            )
        elif "cron_expression" in config:
            return self.schedule_cron(
                name=name,
                cron_expression=config["cron_expression"],
                command=command,
                agent_action=agent_action,
                params=params,
                tags=tags,
            )
        elif "scheduled_time" in config:
            return self.schedule_once(
                name=name,
                scheduled_time=config["scheduled_time"],
                command=command,
                agent_action=agent_action,
                params=params,
                tags=tags,
            )
        else:
            raise ValueError(f"无法解析自然语言定时描述: {natural}")
            
    def schedule_interval(
        self,
        name: str,
        interval: int,
        command: str = "",
        agent_action: Optional[str] = None,
        params: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> ScheduledTask:
        """
        创建间隔执行任务
        
        Args:
            name: 任务名称
            interval: 间隔秒数
            command: 要执行的命令
            agent_action: Agent 动作
            params: 额外参数
            tags: 标签
            
        Returns:
            创建的任务
        """
        task_id = f"interval-{name.lower().replace(' ', '-')[:30]}-{datetime.now().strftime('%Y%m%d%H%M')}"
        
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            interval_seconds=interval,
            command=command,
            agent_action=agent_action,
            params=params or {},
            tags=tags or [],
            next_run=datetime.now() + timedelta(seconds=interval),
        )
        
        self._tasks[task_id] = task
        logger.info(f"[CronScheduler] 创建间隔任务: {name} (ID: {task_id}), 间隔: {interval}秒")
        
        return task
        
    def schedule_once(
        self,
        name: str,
        scheduled_time: datetime,
        command: str = "",
        agent_action: Optional[str] = None,
        params: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> ScheduledTask:
        """
        创建一次性定时任务
        
        Args:
            name: 任务名称
            scheduled_time: 执行时间
            command: 要执行的命令
            agent_action: Agent 动作
            params: 额外参数
            tags: 标签
            
        Returns:
            创建的任务
        """
        task_id = f"once-{name.lower().replace(' ', '-')[:30]}-{datetime.now().strftime('%Y%m%d%H%M')}"
        
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            scheduled_time=scheduled_time,
            command=command,
            agent_action=agent_action,
            params=params or {},
            tags=tags or [],
            next_run=scheduled_time,
        )
        
        self._tasks[task_id] = task
        logger.info(f"[CronScheduler] 创建一次性任务: {name} (ID: {task_id}), 执行时间: {scheduled_time}")
        
        return task
        
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            是否成功取消
        """
        if task_id in self._tasks:
            self._tasks[task_id].status = TaskStatus.CANCELLED
            self._tasks[task_id].enabled = False
            logger.info(f"[CronScheduler] 取消任务: {task_id}")
            return True
        return False
        
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        if task_id in self._tasks:
            self._tasks[task_id].status = TaskStatus.PAUSED
            logger.info(f"[CronScheduler] 暂停任务: {task_id}")
            return True
        return False
        
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = TaskStatus.PENDING
            # 重新计算下次执行
            if task.cron_expression:
                task.next_run = CronParser.get_next_run(task.cron_expression)
            elif task.interval_seconds:
                task.next_run = datetime.now() + timedelta(seconds=task.interval_seconds)
            logger.info(f"[CronScheduler] 恢复任务: {task_id}")
            return True
        return False
        
    def execute_now(self, task_id: str) -> bool:
        """
        立即执行任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            是否成功触发执行
        """
        if task_id in self._tasks and self._active_executions < self._max_concurrent:
            task = self._tasks[task_id]
            self._execution_queue.put((task.priority.value, datetime.now(), task))
            return True
        return False
        
    def set_callbacks(
        self,
        on_execute: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        """设置回调函数"""
        self._on_task_execute = on_execute
        self._on_task_complete = on_complete
        self._on_task_error = on_error
        
    def start(self):
        """启动调度器"""
        if self._running:
            return
            
        self._running = True
        self._worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._worker_thread.start()
        logger.info("[CronScheduler] 调度器已启动")
        
    def stop(self):
        """停止调度器"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("[CronScheduler] 调度器已停止")
        
    def _run_loop(self):
        """主循环"""
        while self._running:
            try:
                # 检查待执行任务
                now = datetime.now()
                for task in self._tasks.values():
                    if task.enabled and task.status in (TaskStatus.PENDING, TaskStatus.PAUSED):
                        if task.next_run and now >= task.next_run:
                            if self._active_executions < self._max_concurrent:
                                self._execute_task(task)
                
                # 处理执行队列
                while not self._execution_queue.empty():
                    if self._active_executions < self._max_concurrent:
                        _, _, task = self._execution_queue.get_nowait()
                        self._execute_task(task)
                    else:
                        break
                        
            except Exception as e:
                logger.error(f"[CronScheduler] 调度循环错误: {e}")
                
            time.sleep(1)  # 每秒检查一次
            
    def _execute_task(self, task: ScheduledTask):
        """执行任务"""
        task.status = TaskStatus.RUNNING
        task.run_count += 1
        task.last_run = datetime.now()
        self._active_executions += 1
        
        logger.info(f"[CronScheduler] 执行任务: {task.name} (ID: {task.task_id})")
        
        # 触发回调
        if self._on_task_execute:
            try:
                self._on_task_execute(task)
            except Exception as e:
                logger.error(f"[CronScheduler] 执行回调失败: {e}")
                
        # 执行任务（异步）
        thread = threading.Thread(target=self._execute_task_async, args=(task,), daemon=True)
        thread.start()
        
    def _execute_task_async(self, task: ScheduledTask):
        """异步执行任务"""
        start_time = datetime.now()
        error = None
        result = None
        
        try:
            # TODO: 实现实际的任务执行逻辑
            # 这里应该调用 Agent 或执行相应的命令
            
            if task.agent_action:
                # 执行 Agent 动作
                result = f"Agent action executed: {task.agent_action}"
            elif task.command:
                # 执行命令
                result = f"Command executed: {task.command}"
            else:
                result = "No action specified"
                
            task.success_count += 1
            task.status = TaskStatus.COMPLETED
            task.last_result = result
            
        except Exception as e:
            error = str(e)
            task.status = TaskStatus.FAILED
            task.last_error = error
            logger.error(f"[CronScheduler] 任务执行失败: {task.task_id}, 错误: {error}")
            
            if self._on_task_error:
                try:
                    self._on_task_error(task, error)
                except Exception as e:
                    logger.error(f"[CronScheduler] 错误回调失败: {e}")
                    
        finally:
            duration = (datetime.now() - start_time).total_seconds()
            
            # 记录执行历史
            record = ExecutionRecord(
                task_id=task.task_id,
                execution_time=start_time,
                status=task.status,
                duration_seconds=duration,
                result=result,
                error=error,
            )
            self._execution_history.append(record)
            if len(self._execution_history) > self._max_history:
                self._execution_history.pop(0)
                
            self._active_executions -= 1
            
            # 计算下次执行时间
            if task.enabled and task.status == TaskStatus.COMPLETED:
                if task.cron_expression:
                    task.next_run = CronParser.get_next_run(task.cron_expression)
                    task.status = TaskStatus.PENDING
                elif task.interval_seconds:
                    task.next_run = datetime.now() + timedelta(seconds=task.interval_seconds)
                    task.status = TaskStatus.PENDING
                elif task.scheduled_time:
                    # 一次性任务完成后取消
                    task.status = TaskStatus.CANCELLED
                    task.enabled = False
                    
            # 触发完成回调
            if self._on_task_complete:
                try:
                    self._on_task_complete(task)
                except Exception as e:
                    logger.error(f"[CronScheduler] 完成回调失败: {e}")
                    
    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """获取任务"""
        return self._tasks.get(task_id)
        
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        tag: Optional[str] = None,
    ) -> List[ScheduledTask]:
        """列出任务"""
        tasks = list(self._tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        if tag:
            tasks = [t for t in tasks if tag in t.tags]
            
        return sorted(tasks, key=lambda t: t.priority.value, reverse=True)
        
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_tasks": len(self._tasks),
            "active_tasks": sum(1 for t in self._tasks.values() if t.enabled),
            "pending_tasks": sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING),
            "running_tasks": sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING),
            "completed_today": sum(
                1 for t in self._execution_history
                if t.status == TaskStatus.COMPLETED and
                t.execution_time.date() == datetime.now().date()
            ),
            "failed_today": sum(
                1 for t in self._execution_history
                if t.status == TaskStatus.FAILED and
                t.execution_time.date() == datetime.now().date()
            ),
        }
        
    def get_execution_history(
        self,
        task_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[ExecutionRecord]:
        """获取执行历史"""
        history = self._execution_history
        
        if task_id:
            history = [r for r in history if r.task_id == task_id]
            
        return history[-limit:]
