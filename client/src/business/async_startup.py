# -*- coding: utf-8 -*-
"""
异步启动管理器
Async Startup Manager

核心理念：主窗口快速显示，后台异步加载模型和状态
"""

import time
import logging
import threading
from typing import Callable, Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

logger = logging.getLogger(__name__)


class StartupStage(Enum):
    """启动阶段"""
    INIT = "init"                     # 初始化
    UI_READY = "ui_ready"             # UI就绪
    AGENT = "agent"                   # Agent初始化
    MODEL_DETECT = "model_detect"     # 模型检测
    MODEL_LOAD = "model_load"         # 模型加载
    SERVICES = "services"             # 服务初始化
    READY = "ready"                   # 完全就绪


@dataclass
class StartupTask:
    """启动任务"""
    name: str
    stage: StartupStage
    callback: Callable
    is_critical: bool = False        # 关键任务，失败会阻塞
    timeout: float = 30.0            # 超时时间（秒）
    retry_count: int = 0
    max_retries: int = 1


@dataclass
class StartupStatus:
    """启动状态"""
    current_stage: StartupStage = StartupStage.INIT
    stage_display: str = "启动中..."
    progress: float = 0.0            # 0-100
    progress_detail: str = ""
    is_ready: bool = False
    errors: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    stage_times: Dict[str, float] = field(default_factory=dict)

    @property
    def elapsed_str(self) -> str:
        """已用时间"""
        elapsed = time.time() - self.start_time
        if elapsed < 60:
            return f"{elapsed:.1f}秒"
        return f"{elapsed/60:.1f}分钟"


class StartupManager(QObject):
    """
    异步启动管理器

    特性：
    - 后台线程执行初始化任务
    - 实时进度反馈
    - 超时控制
    - 关键任务失败告警
    """

    # 信号
    status_changed = pyqtSignal(StartupStatus)   # 状态更新
    stage_completed = pyqtSignal(StartupStage)   # 阶段完成
    ready = pyqtSignal()                         # 全部就绪
    error = pyqtSignal(str)                       # 错误发生

    def __init__(self):
        super().__init__()
        self._tasks: Dict[StartupStage, StartupTask] = {}
        self._status = StartupStatus()
        self._running = False
        self._stopped = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def register_task(
        self,
        name: str,
        stage: StartupStage,
        callback: Callable,
        is_critical: bool = False,
        timeout: float = 30.0,
        max_retries: int = 1,
    ) -> None:
        """注册启动任务"""
        self._tasks[stage] = StartupTask(
            name=name,
            stage=stage,
            callback=callback,
            is_critical=is_critical,
            timeout=timeout,
            max_retries=max_retries,
        )

    def start(self) -> None:
        """开始启动流程"""
        if self._running:
            return

        self._running = True
        self._stopped = False
        self._status = StartupStatus()
        self._status.start_time = time.time()

        self._thread = threading.Thread(target=self._run, daemon=True, name="StartupManager")
        self._thread.start()

    def stop(self) -> None:
        """停止启动流程"""
        self._stopped = True
        self._running = False

    def _run(self) -> None:
        """执行启动流程"""
        try:
            # 阶段1: UI就绪（不需要等待，假设UI已经构建完成）
            self._update_status(StartupStage.INIT, "初始化...", 0)

            # 通知UI可以显示了
            self._update_status(StartupStage.UI_READY, "界面已就绪", 10)
            QTimer.singleShot(0, lambda: self.stage_completed.emit(StartupStage.UI_READY))

            # 阶段2: 按优先级执行任务
            stages_order = [
                StartupStage.AGENT,
                StartupStage.MODEL_DETECT,
                StartupStage.MODEL_LOAD,
                StartupStage.SERVICES,
            ]

            total_stages = len(stages_order)
            for i, stage in enumerate(stages_order):
                if self._stopped:
                    break

                if stage not in self._tasks:
                    # 没有注册的任务，直接标记完成
                    self._update_status(stage, f"{stage.value} 已跳过", (i+1)/total_stages * 100)
                    continue

                task = self._tasks[stage]
                self._update_status(stage, f"正在{task.name}...", (i+1)/total_stages * 100)

                success = self._execute_task(task)
                if success:
                    self._status.stage_times[stage.value] = time.time() - self._status.start_time
                    self.stage_completed.emit(stage)
                elif task.is_critical:
                    # 关键任务失败，停止启动
                    self._status.errors.append(f"关键任务失败: {task.name}")
                    self.error.emit(f"启动失败: {task.name}")
                    return

            # 全部完成
            self._status.is_ready = True
            self._status.current_stage = StartupStage.READY
            self._status.progress = 100.0
            self._status.stage_display = "启动完成"
            self._update_status(StartupStage.READY, "就绪", 100)
            self.ready.emit()

        except Exception as e:
            logger.exception("启动流程异常")
            self.error.emit(str(e))
        finally:
            self._running = False

    def _execute_task(self, task: StartupTask) -> bool:
        """执行单个任务"""
        for attempt in range(task.max_retries + 1):
            if self._stopped:
                return False

            try:
                # 在后台线程执行
                if task.stage == StartupStage.MODEL_LOAD:
                    # 模型加载特殊处理：支持进度回调
                    result = [None]
                    progress = [0]

                    def with_progress_callback(callback_progress):
                        def wrapper(*args, **kwargs):
                            result[0] = callback_progress(*args, **kwargs)
                            # 更新进度
                            if progress[0] < 90:
                                progress[0] += 10
                                self._status.progress_detail = f"{task.name}: {progress[0]}%"
                                self.status_changed.emit(self._status)
                        return wrapper

                    # 检查是否有进度回调
                    callback = task.callback
                    if callable(callback):
                        callback()
                        return True
                else:
                    result = [None]
                    error = [None]

                    def run_callback():
                        try:
                            result[0] = task.callback()
                        except Exception as e:
                            error[0] = e

                    t = threading.Thread(target=run_callback, daemon=True)
                    t.start()
                    t.join(timeout=task.timeout)

                    if t.is_alive():
                        logger.warning(f"任务超时: {task.name}")
                        self._status.errors.append(f"任务超时: {task.name}")
                        return False

                    if error[0]:
                        raise error[0]

                    return result[0] is not None or task.max_retries == 0

            except Exception as e:
                logger.warning(f"任务执行失败 ({attempt+1}/{task.max_retries+1}): {task.name} - {e}")
                if attempt >= task.max_retries:
                    self._status.errors.append(f"{task.name}: {e}")
                    return False

        return True

    def _update_status(self, stage: StartupStage, display: str, progress: float) -> None:
        """更新状态"""
        self._status.current_stage = stage
        self._status.stage_display = display
        self._status.progress = progress
        self.status_changed.emit(self._status)

    def get_status(self) -> StartupStatus:
        """获取当前状态"""
        return self._status


# ── 进度覆盖层 ──────────────────────────────────────────────────────────────


class StartupSplash:
    """
    启动进度覆盖层

    在主窗口完全加载前显示，覆盖在窗口上
    加载完成后自动隐藏并显示主窗口
    """

    def __init__(self, parent: QObject = None):
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QApplication
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QFont

        self.widget = QWidget()
        self.widget.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 居中显示
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            w, h = 400, 200
            self.widget.setGeometry(
                (geo.width() - w) // 2,
                (geo.height() - h) // 2,
                w, h
            )

        layout = QVBoxLayout(self.widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 标题
        self.title_label = QLabel("🌿 LivingTreeAI")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.title_label.setFont(title_font)

        # 状态
        self.status_label = QLabel("正在启动...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)

        # 细节
        self.detail_label = QLabel("")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_font = QFont()
        detail_font.setPointSize(9)
        self.detail_label.setFont(detail_font)

        layout.addWidget(self.title_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.detail_label)

    def show(self) -> None:
        """显示覆盖层"""
        self.widget.show()

    def hide(self) -> None:
        """隐藏覆盖层"""
        self.widget.hide()
        self.widget.close()

    def update_status(self, status: StartupStatus) -> None:
        """更新状态"""
        self.status_label.setText(status.stage_display)
        self.progress_bar.setValue(int(status.progress))
        if status.progress_detail:
            self.detail_label.setText(status.progress_detail)

    def bind_manager(self, manager: StartupManager) -> None:
        """绑定启动管理器"""
        manager.status_changed.connect(self.update_status)
        manager.ready.connect(self.hide)


# ── 状态栏快速集成 ────────────────────────────────────────────────────────────


class QuickStatusBar:
    """
    快速状态栏集成

    用于在主窗口底部显示启动状态
    启动完成后隐藏或变为正常状态栏
    """

    def __init__(self, status_bar):
        from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QProgressBar
        from PyQt6.QtCore import Qt

        self._status_bar = status_bar
        self._container = QWidget()
        self._layout = QHBoxLayout(self._container)
        self._layout.setContentsMargins(4, 2, 4, 2)

        self._label = QLabel("🌿 启动中...")
        self._progress = QProgressBar()
        self._progress.setFixedWidth(150)
        self._progress.setFixedHeight(6)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)

        self._layout.addWidget(self._label)
        self._layout.addWidget(self._progress)
        self._layout.addStretch()

        # 替换状态栏的小部件
        self._status_bar.clear()
        self._status_bar.addPermanentWidget(self._container)

    def update_status(self, status: StartupStatus) -> None:
        """更新状态"""
        self._label.setText(f"🌿 {status.stage_display}")
        self._progress.setValue(int(status.progress))

        # 根据状态调整颜色
        if status.is_ready:
            self._label.setText("🌿 就绪")
            self._label.setStyleSheet("color: #22c55e;")
            self._progress.hide()
        elif status.errors:
            self._label.setStyleSheet("color: #f59e0b;")
        else:
            self._label.setStyleSheet("")

    def bind_manager(self, manager: StartupManager) -> None:
        """绑定启动管理器"""
        manager.status_changed.connect(self.update_status)
        manager.ready.connect(lambda: self.update_status(manager.get_status()))


# ── 异步初始化装饰器 ──────────────────────────────────────────────────────────


def async_init(stage: StartupStage, name: str = "", is_critical: bool = False):
    """
    异步初始化装饰器

    用于标记方法为异步启动任务

    示例：
        @async_init(StartupStage.MODEL_DETECT, "检测Ollama")
        def detect_ollama(self):
            # 后台执行的任务
            return True
    """
    def decorator(func):
        func._async_init_stage = stage
        func._async_init_name = name or func.__name__
        func._async_init_critical = is_critical
        return func
    return decorator


# ── 全局实例 ─────────────────────────────────────────────────────────────────

_manager: Optional[StartupManager] = None


def get_startup_manager() -> StartupManager:
    """获取启动管理器单例"""
    global _manager
    if _manager is None:
        _manager = StartupManager()
    return _manager


__all__ = [
    "StartupManager",
    "StartupStatus",
    "StartupStage",
    "StartupTask",
    "StartupSplash",
    "QuickStatusBar",
    "async_init",
    "get_startup_manager",
]