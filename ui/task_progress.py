"""
任务进度 UI 系统
Task Progress UI System

功能：
- 任务进度条显示（整体 + 当前步骤）
- 操作锁定机制（执行期间禁用相关控件）
- 取消功能
- 多任务堆叠通知
- 预估剩余时间
"""

import sys
import time
import uuid
from typing import Callable, Optional, Any
from enum import Enum
from dataclasses import dataclass, field

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QParallelAnimationGroup
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QGraphicsOpacityEffect, QSizePolicy,
    QApplication
)
from PyQt6.QtGui import QFont


class TaskState(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class TaskStep:
    """任务步骤"""
    name: str  # 步骤名称
    description: str = ""  # 步骤描述
    weight: float = 1.0  # 权重（用于计算进度）
    status: TaskState = TaskState.PENDING
    start_time: float = 0.0
    end_time: float = 0.0
    error: str = ""

    @property
    def duration(self) -> float:
        """实际耗时（秒）"""
        if self.end_time > 0 and self.start_time > 0:
            return self.end_time - self.start_time
        return 0.0


@dataclass
class Task:
    """任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""  # 任务标题
    description: str = ""  # 任务描述
    steps: list[TaskStep] = field(default_factory=list)
    current_step: int = 0  # 当前步骤索引
    state: TaskState = TaskState.PENDING
    start_time: float = 0.0
    end_time: float = 0.0
    cancel_callback: Callable = None  # 取消回调
    complete_callback: Callable = None  # 完成回调
    progress_callback: Callable = None  # 进度回调

    # 锁定配置
    lock_targets: list[str] = field(default_factory=list)  # 要锁定的目标标识符
    lock_message: str = "正在执行任务，请稍候..."

    @property
    def total_weight(self) -> float:
        """总权重"""
        return sum(s.weight for s in self.steps) if self.steps else 1.0

    @property
    def current_step_obj(self) -> Optional[TaskStep]:
        """当前步骤对象"""
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    @property
    def progress(self) -> float:
        """计算进度（0-100）"""
        if not self.steps:
            return 0.0

        completed_weight = 0.0
        for i, step in enumerate(self.steps):
            if step.status == TaskState.COMPLETED:
                completed_weight += step.weight
            elif i == self.current_step and step.status == TaskState.RUNNING:
                # 当前步骤：估算进度
                elapsed = time.time() - step.start_time if step.start_time > 0 else 0
                # 基于历史数据估算（如果有）
                estimated = self._estimate_step_time(step.name)
                if estimated > 0 and elapsed > 0:
                    step_progress = min(elapsed / estimated, 0.99)
                    completed_weight += step.weight * step_progress
                break

        return (completed_weight / self.total_weight) * 100

    @property
    def estimated_remaining(self) -> float:
        """预估剩余时间（秒）"""
        if not self.steps or self.current_step >= len(self.steps):
            return 0.0

        current = self.current_step_obj
        if not current:
            return 0.0

        elapsed = time.time() - current.start_time if current.start_time > 0 else 0
        estimated = self._estimate_step_time(current.name)

        if estimated > 0:
            remaining = estimated - elapsed
        else:
            # 估算：使用已完成步骤的平均时间
            completed_steps = [s for s in self.steps if s.status == TaskState.COMPLETED]
            if completed_steps:
                avg_time = sum(s.duration for s in completed_steps) / len(completed_steps)
                remaining = avg_time * (len(self.steps) - self.current_step)
            else:
                remaining = 0.0

        return max(0, remaining)

    def _estimate_step_time(self, step_name: str) -> float:
        """估算步骤时间（基于历史数据）"""
        # 简单实现：可以从配置文件或数据库读取历史数据
        # 这里返回默认值
        return _STEP_TIME_ESTIMATES.get(step_name, 30.0)


# 步骤时间估算表（秒）
_STEP_TIME_ESTIMATES = {
    "初始化": 2.0,
    "下载模型": 120.0,
    "加载模型": 60.0,
    "处理中": 30.0,
    "保存中": 10.0,
    "分析中": 20.0,
    "生成中": 15.0,
    "编译中": 45.0,
    "安装中": 60.0,
    "解压中": 30.0,
    "验证中": 15.0,
    "同步中": 20.0,
}


class TaskProgressWidget(QWidget):
    """
    单个任务进度组件

    特性：
    - 进度条显示
    - 步骤说明
    - 预估剩余时间
    - 取消按钮
    - 状态指示
    """

    cancelled = pyqtSignal(str)  # 任务ID
    closed = pyqtSignal(str)  # 任务ID

    # 状态颜色
    STATE_COLORS = {
        TaskState.PENDING: ("#94a3b8", "#f1f5f9"),   # 灰色
        TaskState.RUNNING: ("#3b82f6", "#eff6ff"),   # 蓝色
        TaskState.PAUSED: ("#f59e0b", "#fffbeb"),   # 橙色
        TaskState.COMPLETED: ("#10b981", "#ecfdf5"), # 绿色
        TaskState.CANCELLED: ("#64748b", "#f1f5f9"), # 暗灰
        TaskState.FAILED: ("#ef4444", "#fef2f2"),   # 红色
    }

    def __init__(self, task: Task, parent=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.task = task
        self.parent_widget = parent

        # 样式
        self._setup_style()

        # UI
        self._setup_ui()

        # 动画
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(0)

        # 定时器（用于更新预估时间）
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_time_display)
        self._update_timer.setInterval(1000)

        # 初始化显示
        self._update_display()

    def _setup_style(self):
        """设置样式"""
        state = self.task.state
        border_color, bg_color = self.STATE_COLORS.get(state, self.STATE_COLORS[TaskState.PENDING])

        self.setFixedWidth(380)
        self.setMinimumHeight(120)
        self.setMaximumHeight(200)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
                color: #1f2937;
            }}
            QPushButton {{
                background: transparent;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px 12px;
                color: #4b5563;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: rgba(0,0,0,0.05);
                border-color: #9ca3af;
            }}
            QPushButton:pressed {{
                background: rgba(0,0,0,0.1);
            }}
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background: rgba(0,0,0,0.1);
                height: 8px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                border-radius: 4px;
                background: {border_color};
            }}
        """)

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # 标题行
        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)

        self._state_icon = QLabel()
        self._state_icon.setFont(QFont("Segoe UI", 14))
        self._state_icon.setFixedWidth(24)

        self._title_label = QLabel(self.task.title)
        self._title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._title_label.setStyleSheet("color: #1f2937;")

        title_layout.addWidget(self._state_icon)
        title_layout.addWidget(self._title_label, 1)
        self._title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # 关闭按钮
        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setFont(QFont("Segoe UI", 14))
        self._close_btn.clicked.connect(lambda: self._request_close())
        self._close_btn.setVisible(self.task.state not in [TaskState.RUNNING, TaskState.PENDING])

        title_layout.addWidget(self._close_btn)

        layout.addLayout(title_layout)

        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1000)  # 精度：0.1%
        self._progress_bar.setFormat("%p%")
        layout.addWidget(self._progress_bar)

        # 当前步骤
        self._step_label = QLabel()
        self._step_label.setFont(QFont("Segoe UI", 10))
        self._step_label.setStyleSheet("color: #6b7280;")
        layout.addWidget(self._step_label)

        # 时间预估
        self._time_layout = QHBoxLayout()
        self._time_layout.setSpacing(8)

        self._time_icon = QLabel("⏱")
        self._time_icon.setFont(QFont("Segoe UI", 11))

        self._time_label = QLabel()
        self._time_label.setFont(QFont("Segoe UI", 10))
        self._time_label.setStyleSheet("color: #6b7280;")

        self._time_layout.addWidget(self._time_icon)
        self._time_layout.addWidget(self._time_label)
        self._time_layout.addStretch()

        layout.addLayout(self._time_layout)

        # 锁定提示
        self._lock_label = QLabel()
        self._lock_label.setFont(QFont("Segoe UI", 9))
        self._lock_label.setStyleSheet("color: #9ca3af;")
        self._lock_label.setVisible(bool(self.task.lock_message))
        self._lock_label.setText(f"🔒 {self.task.lock_message}")
        layout.addWidget(self._lock_label)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(lambda: self._request_cancel())
        self._cancel_btn.setVisible(self.task.state in [TaskState.RUNNING, TaskState.PENDING])

        self._retry_btn = QPushButton("重试")
        self._retry_btn.clicked.connect(lambda: self._request_retry())
        self._retry_btn.setVisible(self.task.state in [TaskState.FAILED, TaskState.CANCELLED])

        btn_layout.addWidget(self._cancel_btn)
        btn_layout.addWidget(self._retry_btn)

        layout.addLayout(btn_layout)

    def _get_state_icon(self, state: TaskState) -> str:
        """获取状态图标"""
        icons = {
            TaskState.PENDING: "⏳",
            TaskState.RUNNING: "🔄",
            TaskState.PAUSED: "⏸",
            TaskState.COMPLETED: "✅",
            TaskState.CANCELLED: "🚫",
            TaskState.FAILED: "❌",
        }
        return icons.get(state, "📋")

    def _format_time(self, seconds: float) -> str:
        """格式化时间"""
        if seconds <= 0:
            return "计算中..."

        if seconds < 60:
            return f"约 {int(seconds)} 秒"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"约 {minutes} 分 {secs} 秒"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"约 {hours} 小时 {minutes} 分钟"

    def _update_display(self):
        """更新显示"""
        state = self.task.state
        border_color, bg_color = self.STATE_COLORS.get(state, self.STATE_COLORS[TaskState.PENDING])

        # 更新样式
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
                color: #1f2937;
            }}
            QPushButton {{
                background: transparent;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px 12px;
                color: #4b5563;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: rgba(0,0,0,0.05);
                border-color: #9ca3af;
            }}
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background: rgba(0,0,0,0.1);
                height: 8px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                border-radius: 4px;
                background: {border_color};
            }}
        """)

        # 状态图标
        self._state_icon.setText(self._get_state_icon(state))

        # 进度条
        progress = int(self.task.progress * 10)
        self._progress_bar.setValue(progress)

        # 步骤说明
        if self.task.steps:
            step_info = f"步骤 {self.task.current_step + 1}/{len(self.task.steps)}"
            current = self.task.current_step_obj
            if current:
                step_info += f"：{current.name}"
            self._step_label.setText(step_info)
        else:
            self._step_label.setText(self.task.description or "处理中...")

        # 时间显示
        self._update_time_display()

        # 按钮可见性
        self._cancel_btn.setVisible(state == TaskState.RUNNING)
        self._retry_btn.setVisible(state in [TaskState.FAILED, TaskState.CANCELLED])
        self._close_btn.setVisible(state not in [TaskState.RUNNING, TaskState.PENDING])

        # 锁定提示
        self._lock_label.setVisible(state == TaskState.RUNNING and bool(self.task.lock_message))

    def _update_time_display(self):
        """更新时间显示"""
        if self.task.state == TaskState.RUNNING:
            remaining = self.task.estimated_remaining
            self._time_label.setText(f"剩余 {self._format_time(remaining)}")
            self._time_label.setVisible(True)
        elif self.task.state == TaskState.COMPLETED:
            total_time = self.task.end_time - self.task.start_time if self.task.end_time > 0 else 0
            self._time_label.setText(f"总耗时 {self._format_time(total_time)}")
            self._time_label.setVisible(True)
        elif self.task.state == TaskState.FAILED:
            self._time_label.setText("任务失败")
            self._time_label.setVisible(True)
        elif self.task.state == TaskState.CANCELLED:
            self._time_label.setText("任务已取消")
            self._time_label.setVisible(True)
        else:
            self._time_label.setVisible(False)

    def showEvent(self, event):
        """显示动画"""
        super().showEvent(event)
        self._fade_in()
        if self.task.state == TaskState.RUNNING:
            self._update_timer.start()

    def hideEvent(self, event):
        """隐藏"""
        super().hideEvent(event)
        self._update_timer.stop()

    def _fade_in(self):
        """淡入动画"""
        anim = QPropertyAnimation(self._opacity, b"opacity")
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
        self._update_timer.start()

    def _fade_out(self, callback=None):
        """淡出动画"""
        self._update_timer.stop()
        anim = QPropertyAnimation(self._opacity, b"opacity")
        anim.setDuration(200)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        if callback:
            anim.finished.connect(callback)
        anim.start()

    def _request_cancel(self):
        """请求取消"""
        self.cancelled.emit(self.task.id)
        # 停止更新
        self._update_timer.stop()
        # 更新状态
        self.task.state = TaskState.CANCELLED
        self._update_display()

    def _request_retry(self):
        """请求重试"""
        self.task.state = TaskState.PENDING
        self.task.current_step = 0
        for step in self.task.steps:
            step.status = TaskState.PENDING
            step.start_time = 0
            step.end_time = 0
        self._update_display()
        self._update_timer.start()

    def _request_close(self):
        """请求关闭"""
        self._fade_out(lambda: self.closed.emit(self.task.id))


class OperationLockOverlay(QWidget):
    """
    操作锁定遮罩层

    在执行任务时覆盖整个界面，显示锁定状态
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setStyleSheet("""
            background-color: rgba(0, 0, 0, 0.3);
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 锁定图标
        self._icon = QLabel("🔒")
        self._icon.setFont(QFont("Segoe UI", 48))
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet("background: transparent; color: white;")

        # 锁定消息
        self._message = QLabel("正在执行任务，请稍候...")
        self._message.setFont(QFont("Segoe UI", 14))
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setStyleSheet("background: transparent; color: white;")

        layout.addWidget(self._icon)
        layout.addWidget(self._message)

    def set_message(self, message: str):
        """设置锁定消息"""
        self._message.setText(message)

    def showEvent(self, event):
        """显示动画"""
        super().showEvent(event)
        # 设置为父窗口大小
        if self.parent():
            self.setGeometry(self.parent().rect())


class TaskProgressManager:
    """
    任务进度管理器

    功能：
    - 任务注册和跟踪
    - 进度显示管理
    - 操作锁定
    - 任务队列
    """

    def __init__(self, parent=None):
        self.parent = parent
        self._tasks: dict[str, Task] = {}
        self._widgets: dict[str, TaskProgressWidget] = {}
        self._enabled = True

        # 锁定覆盖层
        self._lock_overlay: Optional[OperationLockOverlay] = None

        # 定时器（用于重新定位）
        self._reposition_timer = QTimer(self)
        self._reposition_timer.timeout.connect(self._reposition_all)
        self._reposition_timer.setInterval(500)

    @property
    def enabled(self) -> bool:
        """是否启用"""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        """设置启用状态"""
        self._enabled = value

    def register_task(
        self,
        title: str,
        description: str = "",
        steps: list[str] = None,
        lock_targets: list[str] = None,
        lock_message: str = "正在执行任务，请稍候...",
        cancel_callback: Callable = None,
        complete_callback: Callable = None,
        progress_callback: Callable = None,
    ) -> str:
        """
        注册新任务

        Args:
            title: 任务标题
            description: 任务描述
            steps: 步骤名称列表
            lock_targets: 要锁定的目标标识符
            lock_message: 锁定时显示的消息
            cancel_callback: 取消回调
            complete_callback: 完成回调
            progress_callback: 进度回调

        Returns:
            任务ID
        """
        if not self._enabled:
            return ""

        task = Task(
            title=title,
            description=description,
            steps=[TaskStep(name=s) for s in (steps or [])],
            lock_targets=lock_targets or [],
            lock_message=lock_message,
            cancel_callback=cancel_callback,
            complete_callback=complete_callback,
            progress_callback=progress_callback,
        )

        self._tasks[task.id] = task
        self._show_task_widget(task)

        return task.id

    def update_progress(
        self,
        task_id: str,
        step: int = None,
        step_name: str = None,
        description: str = None,
        state: TaskState = None,
    ):
        """
        更新任务进度

        Args:
            task_id: 任务ID
            step: 步骤索引（从0开始）
            step_name: 步骤名称
            description: 描述
            state: 任务状态
        """
        if task_id not in self._tasks:
            return

        task = self._tasks[task_id]

        # 更新步骤
        if step is not None:
            if 0 <= step < len(task.steps):
                # 标记当前步骤
                if task.current_step < len(task.steps):
                    task.steps[task.current_step].status = TaskState.COMPLETED
                    task.steps[task.current_step].end_time = time.time()

                task.current_step = step

                # 启动新步骤
                if task.current_step < len(task.steps):
                    task.steps[task.current_step].status = TaskState.RUNNING
                    task.steps[task.current_step].start_time = time.time()

        # 更新步骤名称
        if step_name and task.current_step < len(task.steps):
            task.steps[task.current_step].name = step_name

        # 更新描述
        if description:
            task.description = description

        # 更新状态
        if state:
            task.state = state

            if state == TaskState.RUNNING:
                if task.start_time == 0:
                    task.start_time = time.time()
                # 显示锁定
                self._show_lock_overlay(task.lock_message)

            elif state in [TaskState.COMPLETED, TaskState.CANCELLED, TaskState.FAILED]:
                task.end_time = time.time()
                # 隐藏锁定
                self._hide_lock_overlay()
                # 调用完成回调
                if state == TaskState.COMPLETED and task.complete_callback:
                    task.complete_callback()

        # 更新显示
        if task_id in self._widgets:
            widget = self._widgets[task_id]
            widget.task = task
            widget._update_display()

        # 调用进度回调
        if task.progress_callback:
            task.progress_callback(task.progress, task.current_step, len(task.steps))

    def cancel_task(self, task_id: str):
        """取消任务"""
        if task_id not in self._tasks:
            return

        task = self._tasks[task_id]

        # 调用取消回调
        if task.cancel_callback:
            task.cancel_callback()

        # 更新状态
        self.update_progress(task_id, state=TaskState.CANCELLED)

    def complete_task(self, task_id: str):
        """完成任务"""
        if task_id not in self._tasks:
            return

        task = self._tasks[task_id]

        # 标记当前步骤为完成
        if task.current_step < len(task.steps):
            task.steps[task.current_step].status = TaskState.COMPLETED
            task.steps[task.current_step].end_time = time.time()

        self.update_progress(task_id, state=TaskState.COMPLETED)

    def fail_task(self, task_id: str, error: str = ""):
        """任务失败"""
        if task_id not in self._tasks:
            return

        task = self._tasks[task_id]

        if task.current_step < len(task.steps):
            task.steps[task.current_step].status = TaskState.FAILED
            task.steps[task.current_step].error = error

        self.update_progress(task_id, state=TaskState.FAILED)

    def remove_task(self, task_id: str):
        """移除任务"""
        if task_id in self._widgets:
            widget = self._widgets[task_id]
            widget._fade_out(lambda: widget.close())
            del self._widgets[task_id]

        if task_id in self._tasks:
            del self._tasks[task_id]

        self._reposition_all()

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)

    def is_locked(self, target: str = None) -> bool:
        """检查是否锁定"""
        if target:
            # 检查特定目标是否被锁定
            for task in self._tasks.values():
                if task.state == TaskState.RUNNING and target in task.lock_targets:
                    return True
        else:
            # 检查是否有任何运行中的任务
            for task in self._tasks.values():
                if task.state == TaskState.RUNNING:
                    return True
        return False

    def get_locked_targets(self) -> list[str]:
        """获取被锁定的目标列表"""
        targets = []
        for task in self._tasks.values():
            if task.state == TaskState.RUNNING:
                targets.extend(task.lock_targets)
        return targets

    def get_running_tasks(self) -> list[Task]:
        """获取运行中的任务"""
        return [t for t in self._tasks.values() if t.state == TaskState.RUNNING]

    def _show_task_widget(self, task: Task):
        """显示任务组件"""
        widget = TaskProgressWidget(task, self.parent)
        widget.cancelled.connect(self._on_task_cancelled)
        widget.closed.connect(self._on_task_closed)

        self._widgets[task.id] = widget
        self._position_widget(widget)
        widget.show()
        self._reposition_timer.start()

    def _position_widget(self, widget: TaskProgressWidget):
        """定位组件"""
        # 获取屏幕几何
        if self.parent:
            screen = self.parent.screen()
        else:
            screen = QApplication.primaryScreen()

        if not screen:
            return

        screen_geo = screen.geometry()

        # 左上角位置（可调整）
        x = screen_geo.x() + 20
        y = screen_geo.y() + 20

        widget.move(x, y)

    def _reposition_all(self):
        """重新定位所有组件"""
        if not self._widgets:
            self._reposition_timer.stop()
            return

        # 垂直堆叠
        y_offset = 20
        x_offset = 20

        for widget in self._widgets.values():
            if widget.isVisible():
                widget.move(x_offset, y_offset)
                y_offset += widget.height() + 10

    def _on_task_cancelled(self, task_id: str):
        """任务取消处理"""
        self.cancel_task(task_id)

    def _on_task_closed(self, task_id: str):
        """任务关闭处理"""
        self.remove_task(task_id)

    def _show_lock_overlay(self, message: str):
        """显示锁定覆盖层"""
        if self._lock_overlay is None and self.parent:
            self._lock_overlay = OperationLockOverlay(self.parent)
            self._lock_overlay.set_message(message)
            self._lock_overlay.setGeometry(self.parent.rect())
            self._lock_overlay.show()
        elif self._lock_overlay:
            self._lock_overlay.set_message(message)

    def _hide_lock_overlay(self):
        """隐藏锁定覆盖层"""
        if self._lock_overlay:
            self._lock_overlay.hide()
            self._lock_overlay.deleteLater()
            self._lock_overlay = None

    def clear_all(self):
        """清除所有任务"""
        for task_id in list(self._tasks.keys()):
            self.remove_task(task_id)
        self._hide_lock_overlay()


# 便捷函数
_manager: Optional[TaskProgressManager] = None


def get_task_progress_manager(parent=None) -> TaskProgressManager:
    """获取任务进度管理器单例"""
    global _manager
    if _manager is None:
        _manager = TaskProgressManager(parent)
    return _manager


def register_task(title: str, **kwargs) -> str:
    """快捷函数：注册任务"""
    return get_task_progress_manager().register_task(title, **kwargs)


def update_progress(task_id: str, **kwargs):
    """快捷函数：更新进度"""
    get_task_progress_manager().update_progress(task_id, **kwargs)


def complete_task(task_id: str):
    """快捷函数：完成任务"""
    get_task_progress_manager().complete_task(task_id)


def fail_task(task_id: str, error: str = ""):
    """快捷函数：任务失败"""
    get_task_progress_manager().fail_task(task_id, error)


def cancel_task(task_id: str):
    """快捷函数：取消任务"""
    get_task_progress_manager().cancel_task(task_id)


def is_operation_locked(target: str = None) -> bool:
    """快捷函数：检查是否锁定"""
    return get_task_progress_manager().is_locked(target)


def get_locked_targets() -> list[str]:
    """快捷函数：获取被锁定的目标"""
    return get_task_progress_manager().get_locked_targets()
