"""
增强版任务进度面板
Enhanced Task Progress Panel

功能：
- 任务列表显示
- 暂停/恢复/取消/编辑操作
- 右键上下文菜单
- 批量操作
- 任务搜索和筛选
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
from typing import Optional, List
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu,
    QToolButton, QLineEdit, QComboBox, QFrame, QProgressBar,
    QGraphicsOpacityEffect, QStyledItemDelegate, QStyleOptionProgressBar,
    QStyle, QAbstractItemView, QScrollArea, QCheckBox, QGroupBox,
    QButtonGroup, QRadioButton, QDialog, QDialogButtonBox, QApplication
)
from PyQt6.QtGui import QFont, QColor, QAction, QIcon, QPainter, QCursor

from .business.enhanced_task import TaskManager, Task, TaskStatus, TaskPriority


# ── 样式配置 ────────────────────────────────────────────────────────────────

COLORS = {
    "pending": ("#f59e0b", "#fffbeb"),    # 橙色
    "running": ("#3b82f6", "#eff6ff"),    # 蓝色
    "paused": ("#8b5cf6", "#f5f3ff"),     # 紫色
    "completed": ("#10b981", "#ecfdf5"), # 绿色
    "failed": ("#ef4444", "#fef2f2"),     # 红色
    "cancelled": ("#64748b", "#f1f5f9"),  # 灰色
}

STATE_ICONS = {
    TaskStatus.PENDING: "⏳",
    TaskStatus.RUNNING: "🔄",
    TaskStatus.PAUSED: "⏸",
    TaskStatus.COMPLETED: "✅",
    TaskStatus.FAILED: "❌",
    TaskStatus.CANCELLED: "🚫",
}

PRIORITY_ICONS = {
    TaskPriority.LOW: "🔽",
    TaskPriority.NORMAL: "📋",
    TaskPriority.HIGH: "🔼",
    TaskPriority.URGENT: "🚨",
}


class ProgressBarDelegate(QStyledItemDelegate):
    """自定义进度条代理"""
    
    def paint(self, painter: QPainter, option, index):
        progress = index.data(Qt.ItemDataRole.UserRole) or 0
        
        opt = QStyleOptionProgressBar()
        opt.rect = option.rect
        opt.minimum = 0
        opt.maximum = 100
        opt.progress = int(progress)
        opt.text = f"{progress:.0f}%"
        opt.textVisible = True
        opt.textAlignment = Qt.AlignmentFlag.AlignCenter
        
        QApplication.style().drawControl(QStyle.ControlElement.CE_ProgressBar, opt, painter)


class TaskListItem(QFrame):
    """任务列表项组件"""
    
    clicked = pyqtSignal(str)  # task_id
    action_requested = pyqtSignal(str, str)  # task_id, action
    
    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self.task_id = task.id
        self._setup_ui()
        self._update_display()
    
    def _setup_ui(self):
        """设置UI"""
        self.setFixedHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # 根据状态设置样式
        self._setup_style()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        # 顶部行
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)
        
        # 状态图标
        self._state_icon = QLabel()
        self._state_icon.setFixedWidth(24)
        self._state_icon.setFont(QFont("Segoe UI", 14))
        
        # 标题
        self._title = QLabel()
        self._title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._title.setStyleSheet("color: #1f2937;")
        
        top_layout.addWidget(self._state_icon)
        top_layout.addWidget(self._title, 1)
        
        # 优先级
        self._priority = QLabel()
        self._priority.setFont(QFont("Segoe UI", 10))
        top_layout.addWidget(self._priority)
        
        layout.addLayout(top_layout)
        
        # 进度条
        self._progress = QProgressBar()
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 3px;
                background: rgba(0,0,0,0.1);
            }
            QProgressBar::chunk {
                border-radius: 3px;
            }
        """)
        layout.addWidget(self._progress)
        
        # 底部行
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)
        
        # 状态文本
        self._status_text = QLabel()
        self._status_text.setFont(QFont("Segoe UI", 9))
        self._status_text.setStyleSheet("color: #6b7280;")
        
        bottom_layout.addWidget(self._status_text)
        bottom_layout.addStretch()
        
        # 操作按钮
        self._action_btn = QToolButton()
        self._action_btn.setText("▶")
        self._action_btn.setFixedSize(28, 22)
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_btn.clicked.connect(self._toggle_action)
        
        bottom_layout.addWidget(self._action_btn)
        
        layout.addLayout(bottom_layout)
    
    def _setup_style(self):
        """设置样式"""
        color_key = self.task.status.value
        border_color, bg_color = COLORS.get(color_key, COLORS["pending"])
        
        self.setStyleSheet(f"""
            QFrame {{
                background: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QFrame:hover {{
                border-width: 2px;
            }}
        """)
    
    def _update_display(self):
        """更新显示"""
        self._setup_style()
        
        # 状态图标
        self._state_icon.setText(STATE_ICONS.get(self.task.status, "📋"))
        
        # 标题
        title = self.task.title
        if len(title) > 30:
            title = title[:28] + "..."
        self._title.setText(title)
        
        # 优先级
        self._priority.setText(PRIORITY_ICONS.get(self.task.priority, "📋"))
        
        # 进度
        self._progress.setValue(int(self.task.progress))
        
        # 状态文本
        status_parts = [self.task.state_text]
        if self.task.status == TaskStatus.RUNNING and self.task.progress > 0:
            status_parts.append(f"{self.task.progress:.0f}%")
        if self.task.message:
            status_parts.append(f"- {self.task.message[:20]}")
        self._status_text.setText(" ".join(status_parts))
        
        # 操作按钮
        if self.task.status == TaskStatus.RUNNING:
            self._action_btn.setText("⏸")
        elif self.task.status == TaskStatus.PAUSED:
            self._action_btn.setText("▶")
        elif self.task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            self._action_btn.setText("↻")
        else:
            self._action_btn.setText("×")
    
    def _toggle_action(self):
        """切换操作"""
        if self.task.status == TaskStatus.RUNNING:
            self.action_requested.emit(self.task_id, "pause")
        elif self.task.status == TaskStatus.PAUSED:
            self.action_requested.emit(self.task_id, "resume")
        elif self.task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            self.action_requested.emit(self.task_id, "retry")
        else:
            self.action_requested.emit(self.task_id, "cancel")
    
    def mousePressEvent(self, event):
        """鼠标点击"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.task_id)
        super().mousePressEvent(event)
    
    def contextMenuEvent(self, event):
        """右键菜单"""
        menu = QMenu(self)
        
        if self.task.status == TaskStatus.RUNNING:
            menu.addAction("⏸ 暂停", lambda: self.action_requested.emit(self.task_id, "pause"))
            menu.addAction("🚫 取消", lambda: self.action_requested.emit(self.task_id, "cancel"))
        elif self.task.status == TaskStatus.PAUSED:
            menu.addAction("▶ 恢复", lambda: self.action_requested.emit(self.task_id, "resume"))
            menu.addAction("🚫 取消", lambda: self.action_requested.emit(self.task_id, "cancel"))
        elif self.task.status == TaskStatus.PENDING:
            menu.addAction("✏️ 编辑", lambda: self.action_requested.emit(self.task_id, "edit"))
            menu.addAction("🚫 取消", lambda: self.action_requested.emit(self.task_id, "cancel"))
        elif self.task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            menu.addAction("↻ 重试", lambda: self.action_requested.emit(self.task_id, "retry"))
            menu.addAction("🗑️ 删除", lambda: self.action_requested.emit(self.task_id, "remove"))
        
        menu.exec(event.globalPos())


class EnhancedTaskPanel(QWidget):
    """
    增强版任务管理面板
    
    功能：
    - 任务列表（卡片/列表视图）
    - 搜索和筛选
    - 批量操作
    - 统计概览
    """
    
    task_selected = pyqtSignal(str)  # task_id
    task_action = pyqtSignal(str, str)  # task_id, action
    
    def __init__(self, manager: TaskManager = None, parent=None):
        super().__init__(parent)
        self.manager = manager or TaskManager()
        self._task_widgets: dict = {}
        self._setup_ui()
        self._connect_signals()
        
        # 刷新定时器
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_all)
        self._refresh_timer.setInterval(500)
    
    def _setup_ui(self):
        """设置UI"""
        self.setStyleSheet("""
            QWidget {
                background: #f8fafc;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 8px;
                padding: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #475569;
            }
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background: white;
            }
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background: white;
            }
            QPushButton {
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 500;
                background: #e2e8f0;
                color: #475569;
            }
            QPushButton:hover {
                background: #cbd5e1;
            }
            QPushButton[primary="true"] {
                background: #3b82f6;
                color: white;
            }
            QPushButton[primary="true"]:hover {
                background: #2563eb;
            }
            QPushButton[danger="true"] {
                background: #ef4444;
                color: white;
            }
            QPushButton[danger="true"]:hover {
                background: #dc2626;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        
        # 标题
        title = QLabel("任务管理")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        toolbar.addWidget(title)
        
        toolbar.addStretch()
        
        # 搜索框
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 搜索任务...")
        self._search_input.setFixedWidth(180)
        self._search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_input)
        
        # 筛选
        self._filter_combo = QComboBox()
        self._filter_combo.addItem("全部", None)
        self._filter_combo.addItem("⏳ 等待中", TaskStatus.PENDING)
        self._filter_combo.addItem("🔄 进行中", TaskStatus.RUNNING)
        self._filter_combo.addItem("⏸ 已暂停", TaskStatus.PAUSED)
        self._filter_combo.addItem("✅ 已完成", TaskStatus.COMPLETED)
        self._filter_combo.addItem("❌ 失败", TaskStatus.FAILED)
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self._filter_combo)
        
        layout.addLayout(toolbar)
        
        # 统计卡片
        stats_group = QGroupBox("概览")
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
        
        self._stat_widgets = {}
        for key, label, color in [
            ("pending", "等待", "#f59e0b"),
            ("running", "进行中", "#3b82f6"),
            ("paused", "已暂停", "#8b5cf6"),
            ("completed", "已完成", "#10b981"),
            ("failed", "失败", "#ef4444"),
        ]:
            card = self._create_stat_card(label, color)
            self._stat_widgets[key] = card
            stats_layout.addWidget(card)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # 操作按钮
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)
        
        self._btn_pause_all = QPushButton("⏸ 暂停全部")
        self._btn_pause_all.clicked.connect(self._pause_all)
        
        self._btn_cancel_all = QPushButton("🚫 取消全部")
        self._btn_cancel_all.setProperty("danger", True)
        self._btn_cancel_all.clicked.connect(self._cancel_all)
        
        self._btn_clear = QPushButton("🗑️ 清除完成")
        self._btn_clear.clicked.connect(self._clear_completed)
        
        action_layout.addWidget(self._btn_pause_all)
        action_layout.addWidget(self._btn_cancel_all)
        action_layout.addWidget(self._btn_clear)
        action_layout.addStretch()
        
        layout.addLayout(action_layout)
        
        # 任务列表
        list_group = QGroupBox("任务列表")
        list_layout = QVBoxLayout()
        list_layout.setSpacing(8)
        
        # 任务列表滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(300)
        
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()
        
        scroll.setWidget(self._list_container)
        list_layout.addWidget(scroll)
        
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
    
    def _create_stat_card(self, label: str, color: str) -> QFrame:
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
        
        value_label = QLabel("0")
        value_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        value_label.setStyleSheet(f"color: {color};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        name_label = QLabel(label)
        name_label.setFont(QFont("Segoe UI", 9))
        name_label.setStyleSheet("color: #6b7280;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(value_label)
        layout.addWidget(name_label)
        
        card._value_label = value_label
        return card
    
    def _connect_signals(self):
        """连接信号"""
        self.manager.task_added.connect(self._on_task_added)
        self.manager.task_updated.connect(self._on_task_updated)
        self.manager.task_cancelled.connect(self._on_task_cancelled)
        self.manager.task_completed.connect(self._on_task_completed)
        self.manager.task_failed.connect(self._on_task_failed)
    
    # ── 任务操作 ──────────────────────────────────────────────────────────────
    
    def add_task(self, title: str, handler, *args, **kwargs) -> str:
        """添加任务"""
        task_id = self.manager.create_task(title, handler, *args, **kwargs)
        self.manager.execute_task(task_id)
        return task_id
    
    def pause_task(self, task_id: str):
        """暂停任务"""
        self.manager.pause_task(task_id)
    
    def resume_task(self, task_id: str):
        """恢复任务"""
        self.manager.resume_task(task_id)
    
    def cancel_task(self, task_id: str):
        """取消任务"""
        self.manager.cancel_task(task_id)
    
    def retry_task(self, task_id: str):
        """重试任务"""
        self.manager.retry_task(task_id)
    
    def remove_task(self, task_id: str):
        """移除任务"""
        self.manager.remove_task(task_id)
    
    def _pause_all(self):
        """暂停所有任务"""
        for task in self.manager.get_running_tasks():
            self.manager.pause_task(task.id)
    
    def _cancel_all(self):
        """取消所有任务"""
        self.manager.cancel_all()
    
    def _clear_completed(self):
        """清除已完成"""
        self.manager.clear_completed()
    
    # ── 事件处理 ──────────────────────────────────────────────────────────────
    
    def _on_task_added(self, task_id: str):
        """任务添加"""
        task = self.manager.get_task(task_id)
        if task:
            self._add_task_widget(task)
            self._refresh_stats()
    
    def _on_task_updated(self, task_id: str):
        """任务更新"""
        if task_id in self._task_widgets:
            self._task_widgets[task_id].task = self.manager.get_task(task_id)
            self._task_widgets[task_id]._update_display()
        self._refresh_stats()
    
    def _on_task_cancelled(self, task_id: str):
        """任务取消"""
        self._on_task_updated(task_id)
    
    def _on_task_completed(self, task_id: str):
        """任务完成"""
        self._on_task_updated(task_id)
    
    def _on_task_failed(self, task_id: str):
        """任务失败"""
        self._on_task_updated(task_id)
    
    def _add_task_widget(self, task: Task):
        """添加任务组件"""
        if task.id in self._task_widgets:
            return
        
        widget = TaskListItem(task)
        widget.clicked.connect(lambda tid: self.task_selected.emit(tid))
        widget.action_requested.connect(self._on_task_action)
        
        # 插入到列表
        self._task_widgets[task.id] = widget
        
        # 根据状态排序插入
        status_order = {
            TaskStatus.RUNNING: 0,
            TaskStatus.PAUSED: 1,
            TaskStatus.PENDING: 2,
            TaskStatus.FAILED: 3,
            TaskStatus.CANCELLED: 4,
            TaskStatus.COMPLETED: 5,
        }
        
        insert_pos = 0
        for i in range(self._list_layout.count() - 1):  # -1 排除 stretch
            w = self._list_layout.itemAt(i).widget()
            if isinstance(w, TaskListItem):
                if status_order.get(w.task.status, 99) > status_order.get(task.status, 99):
                    insert_pos = i
                    break
                insert_pos = i + 1
        
        self._list_layout.insertWidget(insert_pos, widget)
    
    def _on_task_action(self, task_id: str, action: str):
        """处理任务操作"""
        if action == "pause":
            self.pause_task(task_id)
        elif action == "resume":
            self.resume_task(task_id)
        elif action == "cancel":
            self.cancel_task(task_id)
        elif action == "retry":
            self.retry_task(task_id)
        elif action == "remove":
            self.remove_task(task_id)
        
        self.task_action.emit(task_id, action)
    
    def _refresh_all(self):
        """刷新所有显示"""
        for task_id, widget in self._task_widgets.items():
            task = self.manager.get_task(task_id)
            if task:
                widget.task = task
                widget._update_display()
        self._refresh_stats()
    
    def _refresh_stats(self):
        """刷新统计"""
        stats = self.manager.get_stats()
        
        for key in self._stat_widgets:
            value = stats.get(key, 0)
            self._stat_widgets[key]._value_label.setText(str(value))
    
    def _on_search(self, text: str):
        """搜索"""
        for task_id, widget in self._task_widgets.items():
            task = self.manager.get_task(task_id)
            if not text:
                widget.setVisible(True)
            else:
                visible = text.lower() in task.title.lower() if task else False
                widget.setVisible(visible)
    
    def _on_filter_changed(self, index: int):
        """筛选变化"""
        status = self._filter_combo.currentData()
        
        for task_id, widget in self._task_widgets.items():
            task = self.manager.get_task(task_id)
            if not status:
                widget.setVisible(True)
            else:
                widget.setVisible(task.status == status if task else False)


# ── 便捷函数 ────────────────────────────────────────────────────────────────

_panel_instance: Optional[EnhancedTaskPanel] = None


def get_task_panel(manager: TaskManager = None) -> EnhancedTaskPanel:
    """获取任务面板单例"""
    global _panel_instance
    if _panel_instance is None:
        _panel_instance = EnhancedTaskPanel(manager)
    return _panel_instance


# ── 导出 ─────────────────────────────────────────────────────────────────────

__all__ = [
    "EnhancedTaskPanel",
    "TaskListItem",
    "get_task_panel",
]
