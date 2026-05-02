"""
好奇心驱动引擎 (Curiosity Engine)

核心功能：
1. 自动扫描本地文件系统（极速扫描）
2. 文件/文件夹监控
3. 信息增益计算（好奇心权重）
4. 自主学习触发机制
5. 智能学习策略（核心优先/按需学习）
6. 定时任务调度（可查看/取消）
7. Idle循环调度

基于强化学习中的Curiosity-driven Exploration机制。
"""
from .curiosity_engine import CuriosityEngine, CuriosityLevel, LearningTask, LearningStrategy, get_curiosity_engine
from .file_monitor import FileMonitor
from .auto_scanner import AutoScanner, ScannedFile, ScanResult
from .task_scheduler import TaskScheduler, ScheduledTask, TaskStatus, TaskType, get_task_scheduler

__all__ = [
    "CuriosityEngine",
    "CuriosityLevel",
    "LearningTask",
    "LearningStrategy",
    "get_curiosity_engine",
    "FileMonitor",
    "AutoScanner",
    "ScannedFile",
    "ScanResult",
    "TaskScheduler",
    "ScheduledTask",
    "TaskStatus",
    "TaskType",
    "get_task_scheduler",
]