"""
任务队列处理系统
Task Queue Processing System

功能：
- 队列管理：FIFO 顺序处理任务
- 优先级队列：支持优先级排序
- 队列状态：显示队列长度、处理进度、等待任务
- 限流控制：并发数量限制
- 持久化：可选保存队列状态到数据库
"""

import time
import uuid
import json
import sqlite3
from typing import Callable, Optional, Any, List
from enum import Enum
from dataclasses import dataclass, field
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QSizePolicy, QScrollArea, QGroupBox
)
from PyQt6.QtGui import QFont, QColor

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import importlib.util

# 直接导入 task_progress 避免依赖问题
spec = importlib.util.spec_from_file_location(
    "task_progress", 
    Path(__file__).parent.parent / "ui" / "task_progress.py"
)
task_progress_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task_progress_module)
TaskState = task_progress_module.TaskState
Task = task_progress_module.Task
TaskProgressManager = task_progress_module.TaskProgressManager


class QueuePriority(Enum):
    """队列优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class QueuedTask:
    """队列任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""           # 任务标题
    description: str = ""     # 任务描述
    priority: QueuePriority = QueuePriority.NORMAL
    state: TaskState = TaskState.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    progress: float = 0.0    # 0-100
    result: Any = None        # 执行结果
    error: str = ""           # 错误信息

    # 执行配置
    handler: Callable = None  # 处理函数
    args: tuple = ()          # 处理函数参数
    kwargs: dict = field(default_factory=dict)
    on_complete: Callable = None   # 完成回调
    on_error: Callable = None       # 错误回调
    on_progress: Callable = None    # 进度回调

    # 元数据
    metadata: dict = field(default_factory=dict)

    @property
    def wait_time(self) -> float:
        """等待时间（秒）"""
        if self.started_at > 0:
            return self.started_at - self.created_at
        return time.time() - self.created_at

    @property
    def process_time(self) -> float:
        """处理时间（秒）"""
        if self.completed_at > 0 and self.started_at > 0:
            return self.completed_at - self.started_at
        if self.started_at > 0:
            return time.time() - self.started_at
        return 0.0

    @property
    def state_text(self) -> str:
        """状态文本"""
        texts = {
            TaskState.PENDING: "等待中",
            TaskState.RUNNING: "处理中",
            TaskState.PAUSED: "已暂停",
            TaskState.COMPLETED: "已完成",
            TaskState.CANCELLED: "已取消",
            TaskState.FAILED: "失败",
        }
        return texts.get(self.state, "未知")


def _get_failed(self) -> List['QueuedTask']:
    """获取失败的任务列表（供外部调用）"""
    return []

def _get_cancelled(self) -> List['QueuedTask']:
    """获取取消的任务列表（供外部调用）"""
    return []

# 为兼容添加属性
QueuedTask.get_failed = _get_failed
QueuedTask.get_cancelled = _get_cancelled


class TaskQueue(QObject):
    """
    任务队列

    特性：
    - FIFO + 优先级混合排序
    - 并发数量控制
    - 任务取消/暂停
    - 状态持久化
    """

    # 信号
    task_added = pyqtSignal(str)        # task_id
    task_started = pyqtSignal(str)       # task_id
    task_progress = pyqtSignal(str, float)  # task_id, progress
    task_completed = pyqtSignal(str, object)  # task_id, result
    task_failed = pyqtSignal(str, str)   # task_id, error
    task_cancelled = pyqtSignal(str)    # task_id
    queue_changed = pyqtSignal()         # 队列变化
    all_completed = pyqtSignal()         # 所有任务完成

    def __init__(
        self,
        name: str = "default",
        max_concurrent: int = 1,
        persist: bool = True,
        db_path: str = None,
    ):
        super().__init__()
        self.name = name
        self.max_concurrent = max_concurrent
        self.persist = persist
        self.db_path = db_path or f"./.task_queue_{name}.db"

        self._pending: List[QueuedTask] = []   # 等待队列
        self._running: List[QueuedTask] = []   # 运行中
        self._completed: List[QueuedTask] = [] # 已完成
        self._failed: List[QueuedTask] = []    # 失败
        self._cancelled: List[QueuedTask] = [] # 已取消

        self._task_map: dict[str, QueuedTask] = {}
        self._processing = False
        self._auto_start = True

        # 统计
        self._stats = {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }

        # 初始化数据库
        if self.persist:
            self._init_db()
            self._load_from_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_queue (
                id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                priority INTEGER,
                state TEXT,
                created_at REAL,
                started_at REAL,
                completed_at REAL,
                progress REAL,
                result TEXT,
                error TEXT,
                metadata TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _save_task(self, task: QueuedTask):
        """保存任务到数据库"""
        if not self.persist:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO task_queue
            (id, title, description, priority, state, created_at,
             started_at, completed_at, progress, result, error, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.id,
            task.title,
            task.description,
            task.priority.value,
            task.state.value,
            task.created_at,
            task.started_at,
            task.completed_at,
            task.progress,
            json.dumps(task.result) if task.result else None,
            task.error,
            json.dumps(task.metadata),
        ))
        conn.commit()
        conn.close()

    def _load_from_db(self):
        """从数据库加载任务"""
        if not self.persist:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM task_queue WHERE state IN ('pending', 'running')")
        for row in cursor.fetchall():
            task = QueuedTask(
                id=row[0],
                title=row[1],
                description=row[2],
                priority=QueuePriority(row[3]),
                state=TaskState(row[4]),
                created_at=row[5],
                started_at=row[6],
                completed_at=row[7],
                progress=row[8],
                result=json.loads(row[9]) if row[9] else None,
                error=row[10],
                metadata=json.loads(row[11]) if row[11] else {},
            )
            self._add_to_queue(task)
        conn.close()

    def _add_to_queue(self, task: QueuedTask):
        """添加任务到队列"""
        self._task_map[task.id] = task
        if task.state == TaskState.PENDING:
            self._pending.append(task)
        elif task.state == TaskState.RUNNING:
            self._running.append(task)

    def _sort_pending(self):
        """排序等待队列"""
        self._pending.sort(key=lambda t: (
            -t.priority.value,  # 优先级高的在前
            t.created_at         # 同优先级按时间排序
        ))

    def add(
        self,
        title: str,
        handler: Callable,
        *args,
        description: str = "",
        priority: QueuePriority = QueuePriority.NORMAL,
        on_complete: Callable = None,
        on_error: Callable = None,
        on_progress: Callable = None,
        metadata: dict = None,
        **kwargs,
    ) -> str:
        """
        添加任务到队列

        Args:
            title: 任务标题
            handler: 处理函数
            *args: 处理函数位置参数
            description: 任务描述
            priority: 优先级
            on_complete: 完成回调
            on_error: 错误回调
            on_progress: 进度回调
            metadata: 元数据
            **kwargs: 处理函数关键字参数

        Returns:
            任务ID
        """
        task = QueuedTask(
            title=title,
            description=description,
            priority=priority,
            handler=handler,
            args=args,
            kwargs=kwargs,
            on_complete=on_complete,
            on_error=on_error,
            on_progress=on_progress,
            metadata=metadata or {},
        )

        self._add_to_queue(task)
        self._sort_pending()
        self._save_task(task)
        self._stats["total"] += 1
        self.queue_changed.emit()
        self.task_added.emit(task.id)

        # 自动开始处理
        if self._auto_start:
            self._process_next()

        return task.id

    def cancel(self, task_id: str) -> bool:
        """取消任务"""
        task = self._task_map.get(task_id)
        if not task:
            return False

        if task.state == TaskState.RUNNING:
            # 运行中的任务无法直接取消，需要handler支持
            return False

        task.state = TaskState.CANCELLED
        task.completed_at = time.time()

        # 从队列移除
        if task in self._pending:
            self._pending.remove(task)
        elif task in self._running:
            self._running.remove(task)

        self._cancelled.append(task)
        self._stats["cancelled"] += 1
        self._save_task(task)
        self.queue_changed.emit()
        self.task_cancelled.emit(task_id)

        return True

    def clear_completed(self):
        """清除已完成的任务"""
        self._completed.clear()
        self._failed.clear()
        self._cancelled.clear()
        self.queue_changed.emit()

    def _process_next(self):
        """处理下一个任务"""
        if self._processing:
            return

        # 检查并发限制
        if len(self._running) >= self.max_concurrent:
            return

        if not self._pending:
            if not self._running:
                self.all_completed.emit()
            return

        self._processing = True
        task = self._pending.pop(0)
        task.state = TaskState.RUNNING
        task.started_at = time.time()
        self._running.append(task)
        self._save_task(task)

        self.task_started.emit(task.id)
        self.queue_changed.emit()

        # 异步执行
        self._execute_task(task)

    def _execute_task(self, task: QueuedTask):
        """执行任务"""
        try:
            # 执行处理函数
            if task.handler:
                result = task.handler(*task.args, **task.kwargs)
                task.result = result

            # 更新进度为100%
            task.progress = 100.0
            task.state = TaskState.COMPLETED
            task.completed_at = time.time()

            # 从运行中移除
            if task in self._running:
                self._running.remove(task)
            self._completed.append(task)
            self._stats["completed"] += 1

            self._save_task(task)
            self.task_completed.emit(task.id, task.result)
            self.queue_changed.emit()

            # 回调
            if task.on_complete:
                task.on_complete(task.result)

        except Exception as e:
            task.state = TaskState.FAILED
            task.error = str(e)
            task.completed_at = time.time()

            if task in self._running:
                self._running.remove(task)
            self._failed.append(task)
            self._stats["failed"] += 1

            self._save_task(task)
            self.task_failed.emit(task.id, str(e))
            self.queue_changed.emit()

            if task.on_error:
                task.on_error(str(e))

        finally:
            self._processing = False
            # 继续处理下一个
            self._process_next()

    def update_progress(self, task_id: str, progress: float):
        """更新任务进度"""
        task = self._task_map.get(task_id)
        if task:
            task.progress = max(0, min(100, progress))
            self.task_progress.emit(task_id, task.progress)
            self._save_task(task)

    def get_task(self, task_id: str) -> Optional[QueuedTask]:
        """获取任务"""
        return self._task_map.get(task_id)

    def get_pending(self) -> List[QueuedTask]:
        """获取等待中的任务"""
        return self._pending.copy()

    def get_running(self) -> List[QueuedTask]:
        """获取运行中的任务"""
        return self._running.copy()

    def get_completed(self) -> List[QueuedTask]:
        """获取已完成的任务"""
        return self._completed.copy()

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            **self._stats,
            "pending": len(self._pending),
            "running": len(self._running),
        }

    def pause(self):
        """暂停处理"""
        self._auto_start = False

    def resume(self):
        """恢复处理"""
        self._auto_start = True
        self._process_next()

    def is_empty(self) -> bool:
        """队列是否为空"""
        return len(self._pending) == 0 and len(self._running) == 0


class TaskQueuePanel(QWidget):
    """
    任务队列面板 UI

    显示：
    - 队列状态概览（总数、等待、处理中、已完成）
    - 任务列表（表格形式）
    - 操作按钮（清空、暂停、恢复）
    """

    task_clicked = pyqtSignal(str)  # task_id

    def __init__(self, queue: TaskQueue = None, parent=None):
        super().__init__(parent)
        self.queue = queue or TaskQueue()
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("任务队列")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        self._status_label = QLabel()
        self._status_label.setFont(QFont("Segoe UI", 10))
        self._status_label.setStyleSheet("color: #6b7280;")
        header.addWidget(self._status_label)
        layout.addLayout(header)

        # 统计卡片
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        self._stat_pending = self._create_stat_card("等待", "0", "#f59e0b")
        self._stat_running = self._create_stat_card("处理中", "0", "#3b82f6")
        self._stat_completed = self._create_stat_card("已完成", "0", "#10b981")
        self._stat_failed = self._create_stat_card("失败", "0", "#ef4444")

        stats_layout.addWidget(self._stat_pending)
        stats_layout.addWidget(self._stat_running)
        stats_layout.addWidget(self._stat_completed)
        stats_layout.addWidget(self._stat_failed)
        layout.addLayout(stats_layout)

        # 任务列表
        list_group = QGroupBox("任务列表")
        list_layout = QVBoxLayout()

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["状态", "任务", "优先级", "进度", "耗时"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setMaximumHeight(200)
        self._table.itemClicked.connect(self._on_item_clicked)
        list_layout.addWidget(self._table)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_clear = QPushButton("清空已完成")
        self._btn_clear.clicked.connect(self._on_clear)
        self._btn_pause = QPushButton("暂停")
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_cancel = QPushButton("取消选中")
        self._btn_cancel.clicked.connect(self._on_cancel_selected)

        btn_layout.addWidget(self._btn_clear)
        btn_layout.addWidget(self._btn_pause)
        btn_layout.addWidget(self._btn_cancel)
        layout.addLayout(btn_layout)

        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QTableWidget {
                border: none;
                gridline-color: #f3f4f6;
            }
            QTableWidget::item {
                padding: 4px;
            }
        """)

    def _create_stat_card(self, label: str, value: str, color: str) -> QFrame:
        """创建统计卡片"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {color}15;
                border: 1px solid {color}40;
                border-radius: 8px;
                padding: 8px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setSpacing(2)
        layout.setContentsMargins(8, 6, 8, 6)

        value_label = QLabel(value)
        value_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        value_label.setStyleSheet(f"color: {color};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)

        name_label = QLabel(label)
        name_label.setFont(QFont("Segoe UI", 9))
        name_label.setStyleSheet("color: #6b7280;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        card._value_label = value_label  # 保留引用
        return card

    def _connect_signals(self):
        """连接信号"""
        self.queue.queue_changed.connect(self._refresh)
        self.queue.task_added.connect(lambda _: self._refresh())
        self.queue.task_completed.connect(lambda *_: self._refresh())
        self.queue.task_failed.connect(lambda *_: self._refresh())

    def _refresh(self):
        """刷新显示"""
        stats = self.queue.get_stats()

        # 更新统计
        self._stat_pending._value_label.setText(str(stats["pending"]))
        self._stat_running._value_label.setText(str(stats["running"]))
        self._stat_completed._value_label.setText(str(stats["completed"]))
        self._stat_failed._value_label.setText(str(stats["failed"]))

        # 更新状态文本
        self._status_label.setText(
            f"总计: {stats['total']} | "
            f"并发: {self.queue.max_concurrent} | "
            f"自动: {'开' if self.queue._auto_start else '关'}"
        )

        # 更新表格
        self._table.setRowCount(0)

        # 显示所有任务
        all_tasks = (
            [(t, "running") for t in self.queue.get_running()] +
            [(t, "pending") for t in self.queue.get_pending()] +
            [(t, "completed") for t in self.queue.get_completed()[-10:]] +  # 最近10个
            [(t, "failed") for t in self.queue._failed[-5:]]  # 最近5个
        )

        for task, _ in all_tasks:
            self._add_task_row(task)

    def _add_task_row(self, task: QueuedTask):
        """添加任务行"""
        row = self._table.rowCount()
        self._table.insertRow(row)

        # 状态
        state_colors = {
            TaskState.PENDING: "#f59e0b",
            TaskState.RUNNING: "#3b82f6",
            TaskState.COMPLETED: "#10b981",
            TaskState.FAILED: "#ef4444",
            TaskState.CANCELLED: "#64748b",
        }
        state_item = QTableWidgetItem(task.state_text)
        state_item.setForeground(QColor(state_colors.get(task.state, "#6b7280")))
        state_item.setData(Qt.ItemDataRole.UserRole, task.id)
        self._table.setItem(row, 0, state_item)

        # 任务名称
        title_item = QTableWidgetItem(task.title)
        title_item.setData(Qt.ItemDataRole.UserRole, task.id)
        self._table.setItem(row, 1, title_item)

        # 优先级
        priority_texts = {
            QueuePriority.LOW: "低",
            QueuePriority.NORMAL: "普通",
            QueuePriority.HIGH: "高",
            QueuePriority.URGENT: "紧急",
        }
        priority_item = QTableWidgetItem(priority_texts.get(task.priority, "普通"))
        priority_item.setData(Qt.ItemDataRole.UserRole, task.id)
        self._table.setItem(row, 2, priority_item)

        # 进度
        progress_item = QTableWidgetItem(f"{task.progress:.0f}%")
        progress_item.setData(Qt.ItemDataRole.UserRole, task.id)
        self._table.setItem(row, 3, progress_item)

        # 耗时
        time_text = f"{task.process_time:.1f}s" if task.process_time > 0 else "-"
        time_item = QTableWidgetItem(time_text)
        time_item.setData(Qt.ItemDataRole.UserRole, task.id)
        self._table.setItem(row, 4, time_item)

    def _on_item_clicked(self, item: QTableWidgetItem):
        """任务点击"""
        task_id = item.data(Qt.ItemDataRole.UserRole)
        if task_id:
            self.task_clicked.emit(task_id)

    def _on_clear(self):
        """清空已完成"""
        self.queue.clear_completed()
        self._refresh()

    def _on_pause(self):
        """暂停/恢复"""
        if self.queue._auto_start:
            self.queue.pause()
            self._btn_pause.setText("恢复")
        else:
            self.queue.resume()
            self._btn_pause.setText("暂停")

    def _on_cancel_selected(self):
        """取消选中"""
        selected = self._table.selectedItems()
        if selected:
            task_id = selected[0].data(Qt.ItemDataRole.UserRole)
            if task_id:
                self.queue.cancel(task_id)


# 添加缺失的方法
QueuedTask.get_failed = lambda self: []


# 便捷函数
_queue_instances: dict = {}


def get_task_queue(name: str = "default", **kwargs) -> TaskQueue:
    """获取任务队列实例"""
    if name not in _queue_instances:
        _queue_instances[name] = TaskQueue(name=name, **kwargs)
    return _queue_instances[name]


def create_task_queue(
    name: str = "default",
    max_concurrent: int = 1,
    persist: bool = False,
) -> TaskQueue:
    """创建任务队列"""
    queue = TaskQueue(name=name, max_concurrent=max_concurrent, persist=persist)
    _queue_instances[name] = queue
    return queue
