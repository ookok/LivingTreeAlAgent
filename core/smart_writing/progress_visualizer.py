# -*- coding: utf-8 -*-
"""
进度可视化系统 - Progress Visualizer
====================================

功能：
1. 多种进度条样式（水平、圆形、环形、步骤指示器）
2. 状态指示器（加载中、成功、错误、警告）
3. 实时统计显示（速度、ETA、已用时间）
4. PyQt6 集成（QProgressBar、自定义 widget）
5. 终端输出（Unicode 进度条、颜色）
6. 日志集成

设计：
- 模块化设计，可独立使用
- 与 agent_progress.py 完全集成
- 支持自定义渲染

Author: Hermes Desktop Team
"""

import time
import sys
import threading
from typing import Optional, Callable, Dict, Any, List, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

# PyQt6 支持
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
        QProgressBar, QFrame, QApplication
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
    from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QPalette
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    QObject = object

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# 进度样式枚举
# =============================================================================

class ProgressStyle(Enum):
    """进度条样式"""
    HORIZONTAL = "horizontal"          # 水平进度条
    CIRCULAR = "circular"              # 圆形进度
    RING = "ring"                      # 环形进度条
    STEPS = "steps"                    # 步骤指示器
    DOT = "dot"                        # 点状进度
    PULSE = "pulse"                    # 脉冲动画
    TEXT_ONLY = "text"                 # 仅文本
    STATS = "stats"                    # 统计信息


class ProgressStatus(Enum):
    """进度状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    CANCELLED = "cancelled"


# =============================================================================
# 进度数据模型
# =============================================================================

@dataclass
class ProgressData:
    """进度数据"""
    task_id: str = ""
    task_name: str = ""
    status: ProgressStatus = ProgressStatus.IDLE
    progress: float = 0.0
    current: int = 0
    total: int = 100
    start_time: float = 0
    end_time: float = 0
    elapsed: float = 0
    eta: float = 0
    speed: float = 0
    message: str = ""
    sub_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def percentage(self) -> float:
        return self.progress * 100
    
    @property
    def is_active(self) -> bool:
        return self.status in (ProgressStatus.RUNNING, ProgressStatus.PAUSED)
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "status": self.status.value,
            "progress": self.progress,
            "percentage": self.percentage,
            "current": self.current,
            "total": self.total,
            "elapsed": self.elapsed,
            "eta": self.eta,
            "speed": self.speed,
            "message": self.message,
            "sub_message": self.sub_message,
        }


@dataclass
class StepData:
    """步骤数据"""
    name: str
    status: ProgressStatus = ProgressStatus.IDLE
    message: str = ""
    
    def is_completed(self) -> bool:
        return self.status == ProgressStatus.SUCCESS


# =============================================================================
# 抽象渲染器
# =============================================================================

class ProgressRenderer(ABC):
    """进度条渲染器抽象基类"""
    
    @abstractmethod
    def render(self, data: ProgressData) -> str:
        pass
    
    @abstractmethod
    def clear(self) -> str:
        pass


# =============================================================================
# 终端渲染器
# =============================================================================

class TerminalRenderer(ProgressRenderer):
    """终端渲染器 - 使用 Unicode 和 ANSI 颜色"""
    
    BLOCK = "█"
    EMPTY = "░"
    DOTS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    
    COLOR_RESET = "\033[0m"
    COLOR_GREEN = "\033[92m"
    COLOR_YELLOW = "\033[93m"
    COLOR_RED = "\033[91m"
    COLOR_BLUE = "\033[94m"
    COLOR_GRAY = "\033[90m"
    
    STATUS_COLORS = {
        ProgressStatus.IDLE: COLOR_GRAY,
        ProgressStatus.RUNNING: COLOR_BLUE,
        ProgressStatus.PAUSED: COLOR_YELLOW,
        ProgressStatus.SUCCESS: COLOR_GREEN,
        ProgressStatus.ERROR: COLOR_RED,
        ProgressStatus.WARNING: COLOR_YELLOW,
        ProgressStatus.CANCELLED: COLOR_GRAY,
    }
    
    def __init__(self, width: int = 40):
        self.width = width
        self._dot_index = 0
        self._last_line_len = 0
    
    def render(self, data: ProgressData) -> str:
        if not data.is_active and data.status == ProgressStatus.IDLE:
            return ""
        
        color = self.STATUS_COLORS.get(data.status, self.COLOR_RESET)
        reset = self.COLOR_RESET
        
        filled = int(data.progress * self.width)
        empty = self.width - filled
        
        if data.status == ProgressStatus.RUNNING:
            dot = self.DOTS[self._dot_index % len(self.DOTS)]
            self._dot_index += 1
        else:
            dot = " "
        
        bar = f"{color}{self.BLOCK * filled}{self.EMPTY * empty}{reset}"
        pct_str = f"{data.percentage:.1f}%"
        
        lines = []
        if data.task_name:
            lines.append(f"{color}● {data.task_name}{reset}")
        
        progress_line = f"[{bar}] {pct_str} {dot}"
        lines.append(progress_line)
        
        if data.message:
            lines.append(f"  {data.message}")
        
        if data.status == ProgressStatus.RUNNING:
            stats = self._format_stats(data)
            lines.append(f"  {stats}")
        
        result = "\n".join(lines)
        self._last_line_len = len(lines)
        return result
    
    def render_inline(self, data: ProgressData) -> str:
        color = self.STATUS_COLORS.get(data.status, self.COLOR_RESET)
        reset = self.COLOR_RESET
        
        filled = int(data.progress * self.width)
        empty = self.width - filled
        
        if data.status == ProgressStatus.RUNNING:
            dot = self.DOTS[self._dot_index % len(self.DOTS)]
            self._dot_index += 1
        else:
            dot = " "
        
        bar = f"{color}{self.BLOCK * filled}{self.EMPTY * empty}{reset}"
        pct_str = f"{data.percentage:.1f}%"
        
        line = f"\r[{bar}] {pct_str} {dot}"
        if data.message:
            line += f" {data.message}"
        
        return line
    
    def render_steps(self, steps: List[StepData], current: int) -> str:
        lines = []
        
        for i, step in enumerate(steps):
            if step.is_completed():
                icon = "✓"
                step_color = self.COLOR_GREEN
            elif i == current:
                icon = "●"
                step_color = self.COLOR_BLUE
            elif i < current:
                icon = "✓"
                step_color = self.COLOR_GREEN
            else:
                icon = "○"
                step_color = self.COLOR_GRAY
            
            line = f"{step_color}{icon} {step.name}{reset}"
            if step.message:
                line += f" - {step.message}"
            
            lines.append(line)
        
        return "\n".join(lines)
    
    def _get_status_icon(self, status: ProgressStatus) -> str:
        icons = {
            ProgressStatus.IDLE: "○",
            ProgressStatus.RUNNING: "◐",
            ProgressStatus.PAUSED: "⏸",
            ProgressStatus.SUCCESS: "✓",
            ProgressStatus.ERROR: "✗",
            ProgressStatus.WARNING: "⚠",
            ProgressStatus.CANCELLED: "⊘",
        }
        return icons.get(status, "○")
    
    def _format_stats(self, data: ProgressData) -> str:
        stats = []
        if data.elapsed > 0:
            elapsed_str = self._format_time(data.elapsed)
            stats.append(f"⏱ {elapsed_str}")
        if data.eta > 0:
            eta_str = self._format_time(data.eta)
            stats.append(f"ETA {eta_str}")
        if data.speed > 0:
            stats.append(f"⚡ {data.speed:.1f}/s")
        return " ".join(stats)
    
    def _format_time(self, seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"
    
    def clear(self) -> str:
        return "\r" + " " * self._last_line_len + "\r"


# =============================================================================
# PyQt6 Widget
# =============================================================================

if PYQT6_AVAILABLE:
    class QtProgressWidget(QFrame):
        """Qt 进度条 Widget"""
        
        updated = pyqtSignal(dict)
        
        def __init__(
            self,
            parent: Optional[QWidget] = None,
            style: ProgressStyle = ProgressStyle.HORIZONTAL,
        ):
            super().__init__(parent)
            self.style = style
            self._data = ProgressData()
            self._steps: List[StepData] = []
            self._current_step = 0
            self._anim_angle = 0
            
            self._setup_ui()
            self._setup_animation()
        
        def _setup_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            
            self.name_label = QLabel()
            self.name_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            layout.addWidget(self.name_label)
            
            self.progress_bar = QProgressBar()
            self.progress_bar.setMinimumHeight(20)
            layout.addWidget(self.progress_bar)
            
            self.status_label = QLabel()
            self.status_label.setFont(QFont("Microsoft YaHei", 9))
            layout.addWidget(self.status_label)
            
            self.stats_label = QLabel()
            self.stats_label.setFont(QFont("Consolas", 8))
            self.stats_label.setStyleSheet("color: gray;")
            layout.addWidget(self.stats_label)
        
        def _setup_animation(self):
            self._anim_timer = QTimer(self)
            self._anim_timer.timeout.connect(self._update_animation)
        
        def _update_animation(self):
            self._anim_angle = (self._anim_angle + 30) % 360
            if self._data.status == ProgressStatus.RUNNING:
                self.update_progress(self._data.to_dict())
        
        def update_progress(self, data: Dict[str, Any]):
            self._data = ProgressData(
                task_id=data.get("task_id", ""),
                task_name=data.get("task_name", ""),
                status=ProgressStatus(data.get("status", "idle")),
                progress=data.get("progress", 0),
                current=data.get("current", 0),
                total=data.get("total", 100),
                message=data.get("message", ""),
                sub_message=data.get("sub_message", ""),
            )
            
            self.name_label.setText(self._data.task_name)
            self.progress_bar.setValue(int(self._data.percentage))
            self.status_label.setText(self._data.message)
            
            status_colors = {
                ProgressStatus.SUCCESS: "green",
                ProgressStatus.ERROR: "red",
                ProgressStatus.WARNING: "orange",
                ProgressStatus.RUNNING: "blue",
                ProgressStatus.PAUSED: "gray",
            }
            color = status_colors.get(self._data.status, "black")
            self.status_label.setStyleSheet(f"color: {color};")
            
            if self._data.is_active:
                elapsed = self._format_time(self._data.elapsed)
                eta = self._format_time(self._data.eta) if self._data.eta > 0 else "..."
                self.stats_label.setText(f"Elapsed: {elapsed} | ETA: {eta}")
            else:
                self.stats_label.setText("")
            
            self.updated.emit(data)
        
        def update_steps(self, steps: List[Dict], current: int):
            self._steps = [StepData(**s) for s in steps]
            self._current_step = current
            self._render_steps()
        
        def _render_steps(self):
            lines = []
            for i, step in enumerate(self._steps):
                if step.is_completed():
                    icon = "✓"
                elif i == self._current_step:
                    icon = "●"
                else:
                    icon = "○"
                lines.append(f"{icon} {step.name}")
            
            self.name_label.setText("\n".join(lines))
            if self._steps:
                self.progress_bar.setValue(int((self._current_step / len(self._steps)) * 100))
        
        def start_animation(self):
            self._anim_timer.start(100)
        
        def stop_animation(self):
            self._anim_timer.stop()
        
        def _format_time(self, seconds: float) -> str:
            if seconds < 60:
                return f"{seconds:.0f}s"
            elif seconds < 3600:
                return f"{seconds/60:.1f}m"
            else:
                return f"{seconds/3600:.1f}h"
        
        def get_progress_data(self) -> ProgressData:
            return self._data


# =============================================================================
# 进度管理器
# =============================================================================

class ProgressManager:
    """进度管理器"""
    
    def __init__(self, renderer: Optional[ProgressRenderer] = None):
        self._tasks: Dict[str, ProgressData] = {}
        self._steps: Dict[str, List[StepData]] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._lock = threading.Lock()
        self._renderer = renderer or TerminalRenderer()
        self._terminal_mode = True
        self._qt_widgets: Dict[str, Any] = {}
    
    def start_task(
        self,
        task_id: str,
        task_name: str,
        total: int = 100,
        message: str = "",
        callback: Optional[Callable[[ProgressData], None]] = None,
    ) -> ProgressData:
        with self._lock:
            data = ProgressData(
                task_id=task_id,
                task_name=task_name,
                status=ProgressStatus.RUNNING,
                total=total,
                start_time=time.time(),
                message=message,
            )
            self._tasks[task_id] = data
            if callback:
                self._callbacks[task_id] = callback
            return data
    
    def update_task(
        self,
        task_id: str,
        current: Optional[int] = None,
        progress: Optional[float] = None,
        message: str = "",
        sub_message: str = "",
    ) -> Optional[ProgressData]:
        with self._lock:
            if task_id not in self._tasks:
                return None
            
            data = self._tasks[task_id]
            
            if current is not None:
                data.current = current
                data.progress = data.current / data.total if data.total > 0 else 0
            elif progress is not None:
                data.progress = min(1.0, max(0, progress))
                data.current = int(data.progress * data.total)
            
            data.elapsed = time.time() - data.start_time
            if data.progress > 0:
                data.speed = data.current / data.elapsed
                data.eta = (data.total - data.current) / data.speed if data.speed > 0 else 0
            
            if message:
                data.message = message
            if sub_message:
                data.sub_message = sub_message
            
            if task_id in self._callbacks:
                self._callbacks[task_id](data)
            
            self._render(data)
            return data
    
    def complete_task(
        self,
        task_id: str,
        message: str = "完成",
        status: ProgressStatus = ProgressStatus.SUCCESS,
    ) -> Optional[ProgressData]:
        with self._lock:
            if task_id not in self._tasks:
                return None
            
            data = self._tasks[task_id]
            data.status = status
            data.message = message
            data.progress = 1.0 if status == ProgressStatus.SUCCESS else data.progress
            data.end_time = time.time()
            data.elapsed = data.end_time - data.start_time
            
            self._render(data)
            
            if task_id in self._callbacks:
                del self._callbacks[task_id]
            
            return data
    
    def fail_task(self, task_id: str, error: str) -> Optional[ProgressData]:
        return self.complete_task(task_id, error, ProgressStatus.ERROR)
    
    def pause_task(self, task_id: str) -> Optional[ProgressData]:
        with self._lock:
            if task_id not in self._tasks:
                return None
            self._tasks[task_id].status = ProgressStatus.PAUSED
            self._render(self._tasks[task_id])
            return self._tasks[task_id]
    
    def resume_task(self, task_id: str) -> Optional[ProgressData]:
        with self._lock:
            if self._tasks.get(task_id):
                self._tasks[task_id].status = ProgressStatus.RUNNING
                self._render(self._tasks[task_id])
                return self._tasks[task_id]
        return None
    
    def cancel_task(self, task_id: str) -> Optional[ProgressData]:
        return self.complete_task(task_id, "已取消", ProgressStatus.CANCELLED)
    
    def set_steps(self, task_id: str, steps: List[str]):
        with self._lock:
            self._steps[task_id] = [StepData(name=name) for name in steps]
    
    def activate_step(self, task_id: str, step_index: int, message: str = ""):
        with self._lock:
            if task_id not in self._steps:
                return
            
            steps = self._steps[task_id]
            for i, step in enumerate(steps):
                if i < step_index:
                    step.status = ProgressStatus.SUCCESS
                elif i == step_index:
                    step.status = ProgressStatus.RUNNING
                    step.message = message
                else:
                    step.status = ProgressStatus.IDLE
                    step.message = ""
            
            self._render_steps(task_id, step_index)
    
    def complete_step(self, task_id: str, step_index: int, message: str = ""):
        with self._lock:
            if task_id not in self._steps:
                return
            
            self._steps[task_id][step_index].status = ProgressStatus.SUCCESS
            self._steps[task_id][step_index].message = message
            self._render_steps(task_id, step_index)
    
    def _render(self, data: ProgressData):
        if self._terminal_mode:
            output = self._renderer.render_inline(data)
            print(output, end="", flush=True)
    
    def _render_steps(self, task_id: str, current: int):
        if self._terminal_mode and task_id in self._steps:
            output = self._renderer.render_steps(self._steps[task_id], current)
            print(f"\r{output}", end="", flush=True)
    
    def clear(self):
        if self._terminal_mode:
            print(self._renderer.clear(), end="", flush=True)
    
    def get_task(self, task_id: str) -> Optional[ProgressData]:
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[ProgressData]:
        return list(self._tasks.values())


# =============================================================================
# 上下文管理器
# =============================================================================

class progress:
    """进度上下文管理器"""
    
    _manager: Optional[ProgressManager] = None
    _task_id_counter = 0
    
    @classmethod
    def set_manager(cls, manager: ProgressManager):
        cls._manager = manager
    
    @classmethod
    def get_manager(cls) -> ProgressManager:
        if cls._manager is None:
            cls._manager = ProgressManager()
        return cls._manager
    
    def __init__(
        self,
        task_name: str,
        total: int = 100,
        task_id: Optional[str] = None,
        message: str = "",
    ):
        self.task_name = task_name
        self.total = total
        self.task_id = task_id or f"task_{self._task_id_counter}"
        self._progress = 0
        progress._task_id_counter += 1
    
    def __enter__(self):
        manager = self.get_manager()
        self.data = manager.start_task(self.task_id, self.task_name, self.total)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        manager = self.get_manager()
        if exc_type:
            manager.fail_task(self.task_id, str(exc_val))
        else:
            manager.complete_task(self.task_id)
    
    def update(self, current: int = None, progress: float = None, message: str = ""):
        manager = self.get_manager()
        manager.update_task(self.task_id, current, progress, message)
        if current is not None:
            self._progress = current
        elif progress is not None:
            self._progress = int(progress * self.total)


# =============================================================================
# 全局实例
# =============================================================================

_progress_manager: Optional[ProgressManager] = None


def get_progress_manager() -> ProgressManager:
    global _progress_manager
    if _progress_manager is None:
        _progress_manager = ProgressManager()
    return _progress_manager


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=== 测试进度可视化系统 ===\n")
    
    manager = get_progress_manager()
    
    print("1. 简单进度条:")
    task = manager.start_task("test1", "下载文件", total=100)
    for i in range(101):
        manager.update_task("test1", current=i, message=f"下载中... {i}%")
        time.sleep(0.02)
    manager.complete_task("test1")
    print("\n")
    
    print("2. 步骤指示器:")
    manager.set_steps("test2", ["准备", "处理", "验证", "完成"])
    for i in range(4):
        manager.activate_step("test2", i, f"执行第{i+1}步")
        time.sleep(0.3)
    print("\n")
    
    print("3. 上下文管理器:")
    with progress("批量处理", total=50) as p:
        for i in range(50):
            p.update(message=f"处理第{i+1}项")
            time.sleep(0.03)
    print("\n完成！")
