"""
TaskBoardPanel - 任务看板面板

参考 Multica 的任务管理设计，提供可视化任务管理界面。

功能：
1. 可视化任务状态（待办/进行中/已完成/失败）
2. 支持手动分配/自动认领
3. 实时进度推送（PyQt6 信号槽）
4. 支持拖拽操作
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QProgressBar, QMenu, QAction, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QIcon, QCursor
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import List, Dict, Optional
import asyncio


class TaskStatus(Enum):
    """任务状态"""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(Enum):
    """任务优先级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TaskItem:
    """任务项"""
    task_id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee: Optional[str] = None
    progress: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class TaskCard(QListWidgetItem):
    """任务卡片"""
    
    def __init__(self, task: TaskItem):
        super().__init__()
        self.task = task
        self._update_display()
    
    def _update_display(self):
        """更新显示"""
        # 设置图标
        icon = self._get_status_icon()
        self.setIcon(icon)
        
        # 设置文本
        priority_color = self._get_priority_color()
        text = f"<b>{self.task.title}</b>"
        if self.task.description:
            text += f"<br><small>{self.task.description[:50]}...</small>"
        text += f"<br><span style='color:{priority_color}'>{self.task.priority.value}</span>"
        self.setText(text)
        
        # 设置背景色
        bg_color = self._get_status_color()
        self.setBackground(bg_color)
    
    def _get_status_icon(self):
        """获取状态图标"""
        icons = {
            TaskStatus.TODO: "📝",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌"
        }
        return QIcon.fromTheme(icons.get(self.task.status, "📋"))
    
    def _get_status_color(self):
        """获取状态背景色"""
        colors = {
            TaskStatus.TODO: "#f0f0f0",
            TaskStatus.IN_PROGRESS: "#fff3cd",
            TaskStatus.COMPLETED: "#d4edda",
            TaskStatus.FAILED: "#f8d7da"
        }
        from PyQt6.QtGui import QColor
        return QColor(colors.get(self.task.status, "#ffffff"))
    
    def _get_priority_color(self):
        """获取优先级颜色"""
        colors = {
            TaskPriority.HIGH: "#dc3545",
            TaskPriority.MEDIUM: "#ffc107",
            TaskPriority.LOW: "#28a745"
        }
        return colors.get(self.task.priority, "#6c757d")


class TaskBoardPanel(QWidget):
    """
    任务看板面板
    
    设计理念：
    1. 可视化任务状态（待办/进行中/已完成/失败）
    2. 支持手动分配/自动认领
    3. 实时进度推送（PyQt6 信号槽）
    4. 支持拖拽操作
    """
    
    task_updated = pyqtSignal(TaskItem)
    task_created = pyqtSignal(TaskItem)
    task_deleted = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.tasks: Dict[str, TaskItem] = {}
        self.init_ui()
        self._start_polling()
    
    def init_ui(self):
        """初始化 UI"""
        layout = QHBoxLayout()
        layout.setSpacing(10)
        
        # 四个列：待办、进行中、已完成、失败
        self.columns = {}
        statuses = [
            (TaskStatus.TODO, "待办", "#f0f0f0"),
            (TaskStatus.IN_PROGRESS, "进行中", "#fff3cd"),
            (TaskStatus.COMPLETED, "已完成", "#d4edda"),
            (TaskStatus.FAILED, "失败", "#f8d7da")
        ]
        
        for status, label, color in statuses:
            column = self._create_column(status, label, color)
            self.columns[status] = column
            layout.addWidget(column)
        
        # 添加任务按钮
        add_btn = QPushButton("+ 新建任务")
        add_btn.clicked.connect(self._show_add_task_dialog)
        layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        
        self.setLayout(layout)
    
    def _create_column(self, status: TaskStatus, label: str, bg_color: str) -> QWidget:
        """创建列"""
        column = QWidget()
        column.setStyleSheet(f"background-color: {bg_color}; border-radius: 8px; padding: 8px;")
        
        layout = QVBoxLayout(column)
        
        # 列标题
        header = QLabel(f"<h3>{label}</h3>")
        layout.addWidget(header)
        
        # 任务列表
        task_list = QListWidget()
        task_list.setDragEnabled(True)
        task_list.setAcceptDrops(True)
        task_list.setDropIndicatorShown(True)
        task_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        task_list.itemClicked.connect(lambda item: self._on_task_click(item, status))
        task_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        task_list.customContextMenuRequested.connect(lambda pos, tl=task_list, s=status: self._show_context_menu(tl, pos, s))
        layout.addWidget(task_list)
        
        # 统计信息
        count_label = QLabel(f"共 0 个任务")
        layout.addWidget(count_label)
        
        return column
    
    def _start_polling(self):
        """启动任务轮询"""
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll_tasks)
        self._timer.start(5000)  # 每5秒更新一次
    
    @pyqtSlot()
    def _poll_tasks(self):
        """轮询任务状态"""
        asyncio.create_task(self._update_tasks())
    
    async def _update_tasks(self):
        """更新任务列表"""
        # 模拟获取任务列表
        mock_tasks = self._get_mock_tasks()
        
        for task in mock_tasks:
            self.tasks[task.task_id] = task
        
        self._refresh_columns()
    
    def _get_mock_tasks(self) -> List[TaskItem]:
        """获取模拟任务"""
        return [
            TaskItem(
                task_id="1",
                title="完成统一架构层设计",
                description="实现 ToolRegistry 和 BaseTool",
                status=TaskStatus.COMPLETED,
                priority=TaskPriority.HIGH,
                assignee="系统",
                progress=100
            ),
            TaskItem(
                task_id="2",
                title="实现自我进化引擎",
                description="实现 ToolMissingDetector 等组件",
                status=TaskStatus.IN_PROGRESS,
                priority=TaskPriority.HIGH,
                assignee="系统",
                progress=80
            ),
            TaskItem(
                task_id="3",
                title="添加语音交互功能",
                description="集成 Whisper 和 ElevenLabs",
                status=TaskStatus.IN_PROGRESS,
                priority=TaskPriority.MEDIUM,
                assignee="系统",
                progress=60
            ),
            TaskItem(
                task_id="4",
                title="新建 Markdown 转换工具",
                description="支持 HTML/PDF/DOCX 转 Markdown",
                status=TaskStatus.TODO,
                priority=TaskPriority.MEDIUM
            ),
            TaskItem(
                task_id="5",
                title="优化语义搜索能力",
                description="引入向量检索",
                status=TaskStatus.TODO,
                priority=TaskPriority.LOW
            ),
            TaskItem(
                task_id="6",
                title="测试 ML 全流程自动化",
                description="测试训练/评估/部署流程",
                status=TaskStatus.FAILED,
                priority=TaskPriority.HIGH,
                assignee="系统"
            )
        ]
    
    def _refresh_columns(self):
        """刷新所有列"""
        for status, column in self.columns.items():
            task_list = column.findChild(QListWidget)
            count_label = column.findChild(QLabel, options=Qt.FindChildOption.FindDirectChildrenOnly)
            
            task_list.clear()
            status_tasks = [t for t in self.tasks.values() if t.status == status]
            
            for task in status_tasks:
                item = TaskCard(task)
                task_list.addItem(item)
            
            count_label.setText(f"共 {len(status_tasks)} 个任务")
    
    def _on_task_click(self, item, status):
        """点击任务"""
        if isinstance(item, TaskCard):
            task = item.task
            self._show_task_details(task)
    
    def _show_task_details(self, task: TaskItem):
        """显示任务详情"""
        from PyQt6.QtWidgets import QDialog, QFormLayout, QTextEdit
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"任务详情: {task.title}")
        
        layout = QFormLayout(dialog)
        
        layout.addRow("任务ID:", QLabel(task.task_id))
        layout.addRow("标题:", QLabel(task.title))
        layout.addRow("描述:", QTextEdit(task.description))
        layout.addRow("状态:", QLabel(task.status.value))
        layout.addRow("优先级:", QLabel(task.priority.value))
        layout.addRow("负责人:", QLabel(task.assignee or "未分配"))
        
        progress_bar = QProgressBar()
        progress_bar.setValue(task.progress)
        layout.addRow("进度:", progress_bar)
        
        dialog.exec()
    
    def _show_context_menu(self, task_list, pos, status):
        """显示右键菜单"""
        item = task_list.itemAt(pos)
        if not item:
            return
        
        menu = QMenu()
        
        # 状态切换
        for s in TaskStatus:
            if s != status:
                action = QAction(f"移动到 {s.value}", self)
                action.triggered.connect(lambda checked, it=item, new_status=s: self._move_task(it, new_status))
                menu.addAction(action)
        
        menu.addSeparator()
        
        # 分配任务
        assign_action = QAction("分配任务", self)
        assign_action.triggered.connect(lambda: self._assign_task(item))
        menu.addAction(assign_action)
        
        # 删除任务
        delete_action = QAction("删除任务", self)
        delete_action.triggered.connect(lambda: self._delete_task(item))
        menu.addAction(delete_action)
        
        menu.exec(task_list.mapToGlobal(pos))
    
    def _move_task(self, item, new_status: TaskStatus):
        """移动任务到新状态"""
        if isinstance(item, TaskCard):
            item.task.status = new_status
            item.task.updated_at = datetime.now()
            item._update_display()
            self._refresh_columns()
            self.task_updated.emit(item.task)
    
    def _assign_task(self, item):
        """分配任务"""
        if isinstance(item, TaskCard):
            # 简单实现：自动分配给当前用户
            item.task.assignee = "当前用户"
            item.task.updated_at = datetime.now()
            item._update_display()
            self.task_updated.emit(item.task)
    
    def _delete_task(self, item):
        """删除任务"""
        if isinstance(item, TaskCard):
            task_id = item.task.task_id
            del self.tasks[task_id]
            self._refresh_columns()
            self.task_deleted.emit(task_id)
    
    def _show_add_task_dialog(self):
        """显示添加任务对话框"""
        from PyQt6.QtWidgets import QDialog, QFormLayout, QComboBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("新建任务")
        
        layout = QFormLayout(dialog)
        
        title_edit = QLineEdit()
        layout.addRow("标题:", title_edit)
        
        desc_edit = QTextEdit()
        layout.addRow("描述:", desc_edit)
        
        priority_combo = QComboBox()
        priority_combo.addItems([p.value for p in TaskPriority])
        layout.addRow("优先级:", priority_combo)
        
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(lambda: self._add_task(title_edit.text(), desc_edit.toPlainText(), priority_combo.currentText()))
        layout.addWidget(ok_btn)
        
        dialog.exec()
    
    def _add_task(self, title: str, description: str, priority: str):
        """添加任务"""
        if not title.strip():
            return
        
        task = TaskItem(
            task_id=f"task_{len(self.tasks) + 1}",
            title=title,
            description=description,
            priority=TaskPriority(priority)
        )
        
        self.tasks[task.task_id] = task
        self._refresh_columns()
        self.task_created.emit(task)