"""
任务组件 - 美观展示任务和子任务

功能特性：
1. 支持任务层级显示（父任务和子任务）
2. 子任务可折叠/展开
3. 点击查看任务详情
4. 支持任务状态管理
5. 美观的卡片式设计
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QToolButton, QScrollArea,
    QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation
from PyQt6.QtGui import QFont


class TaskStatus(Enum):
    """任务状态枚举"""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Task:
    """任务数据结构"""
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    children: List['Task'] = field(default_factory=list)
    assignee: str = ""
    due_date: str = ""
    tags: List[str] = field(default_factory=list)
    progress: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "children": [child.to_dict() for child in self.children],
            "assignee": self.assignee,
            "due_date": self.due_date,
            "tags": self.tags,
            "progress": self.progress
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        children = []
        for child_data in data.get("children", []):
            children.append(cls.from_dict(child_data))
        
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "todo")),
            priority=TaskPriority(data.get("priority", "medium")),
            children=children,
            assignee=data.get("assignee", ""),
            due_date=data.get("due_date", ""),
            tags=data.get("tags", []),
            progress=data.get("progress", 0)
        )


class TaskItem(QFrame):
    """单个任务项组件"""
    
    clicked = pyqtSignal(Task)
    expanded = pyqtSignal(bool)
    
    def __init__(self, task: Task, level: int = 0, parent=None):
        super().__init__(parent)
        self._task = task
        self._level = level
        self._is_expanded = True
        self._child_widgets = []
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setStyleSheet("""
            TaskItem {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-bottom: 4px;
            }
            TaskItem:hover {
                border-color: #2563eb;
                background-color: #f8fafc;
            }
        """)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 任务头部（可点击区域）
        self.header = QFrame()
        self.header.setStyleSheet("background-color: transparent;")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(8)
        
        # 缩进（根据层级）
        indent = QWidget()
        indent.setFixedWidth(self._level * 24)
        header_layout.addWidget(indent)
        
        # 展开/折叠按钮（只有有子任务时显示）
        if self._task.children:
            self.expand_btn = QToolButton()
            self.expand_btn.setText("▶")
            self.expand_btn.setFixedSize(20, 20)
            self.expand_btn.setStyleSheet("""
                QToolButton {
                    color: #64748b;
                    border: none;
                    font-size: 10px;
                }
            """)
            self.expand_btn.clicked.connect(self._toggle_expand)
            header_layout.addWidget(self.expand_btn)
        
        # 状态图标
        status_icon = QLabel(self._get_status_icon())
        status_icon.setStyleSheet(f"font-size: 16px;")
        header_layout.addWidget(status_icon)
        
        # 任务标题
        title_label = QLabel(self._task.title)
        title_label.setStyleSheet(self._get_title_style())
        title_label.setFont(QFont("Microsoft YaHei", 13))
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header_layout.addWidget(title_label)
        
        # 优先级标签
        priority_label = QLabel(self._get_priority_label())
        priority_label.setStyleSheet(self._get_priority_style())
        priority_label.setFixedHeight(24)
        priority_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header_layout.addWidget(priority_label)
        
        layout.addWidget(self.header)
        
        # 进度条（如果有进度）
        if self._task.progress > 0:
            progress_bar = QFrame()
            progress_bar.setStyleSheet("background-color: #e2e8f0; height: 4px; border-radius: 2px; margin: 0 12px;")
            
            progress_fill = QFrame()
            progress_fill.setStyleSheet(f"""
                background-color: {self._get_progress_color()};
                border-radius: 2px;
                height: 4px;
            """)
            progress_fill.setFixedWidth(int(self._task.progress))
            
            bar_layout = QHBoxLayout(progress_bar)
            bar_layout.setContentsMargins(0, 0, 0, 0)
            bar_layout.addWidget(progress_fill)
            
            layout.addWidget(progress_bar)
        
        # 子任务区域
        self.children_area = QFrame()
        self.children_layout = QVBoxLayout(self.children_area)
        self.children_layout.setContentsMargins(24, 0, 0, 0)
        self.children_layout.setSpacing(0)
        
        # 添加子任务
        for child in self._task.children:
            child_widget = TaskItem(child, self._level + 1)
            child_widget.clicked.connect(self.clicked.emit)
            self._child_widgets.append(child_widget)
            self.children_layout.addWidget(child_widget)
        
        layout.addWidget(self.children_area)
        
        # 点击事件
        self.header.mousePressEvent = lambda e: self.clicked.emit(self._task)
    
    def _get_status_icon(self) -> str:
        """获取状态图标"""
        icons = {
            TaskStatus.TODO: "○",
            TaskStatus.IN_PROGRESS: "◐",
            TaskStatus.DONE: "✓",
            TaskStatus.BLOCKED: "⚠",
            TaskStatus.CANCELLED: "✕"
        }
        return icons.get(self._task.status, "○")
    
    def _get_title_style(self) -> str:
        """获取标题样式"""
        colors = {
            TaskStatus.TODO: "color: #334155;",
            TaskStatus.IN_PROGRESS: "color: #2563eb;",
            TaskStatus.DONE: "color: #10b981; text-decoration: line-through;",
            TaskStatus.BLOCKED: "color: #f59e0b;",
            TaskStatus.CANCELLED: "color: #64748b; text-decoration: line-through;"
        }
        return colors.get(self._task.status, "color: #334155;")
    
    def _get_priority_label(self) -> str:
        """获取优先级标签文本"""
        labels = {
            TaskPriority.LOW: "低",
            TaskPriority.MEDIUM: "中",
            TaskPriority.HIGH: "高",
            TaskPriority.CRITICAL: "紧急"
        }
        return labels.get(self._task.priority, "中")
    
    def _get_priority_style(self) -> str:
        """获取优先级样式"""
        styles = {
            TaskPriority.LOW: """
                QLabel {
                    background-color: #e2e8f0;
                    color: #64748b;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 11px;
                }
            """,
            TaskPriority.MEDIUM: """
                QLabel {
                    background-color: #dbeafe;
                    color: #2563eb;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 11px;
                }
            """,
            TaskPriority.HIGH: """
                QLabel {
                    background-color: #fef3c7;
                    color: #d97706;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 11px;
                }
            """,
            TaskPriority.CRITICAL: """
                QLabel {
                    background-color: #fee2e2;
                    color: #dc2626;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 11px;
                }
            """
        }
        return styles.get(self._task.priority, styles[TaskPriority.MEDIUM])
    
    def _get_progress_color(self) -> str:
        """获取进度条颜色"""
        if self._task.progress >= 100:
            return "#10b981"
        elif self._task.progress >= 50:
            return "#2563eb"
        else:
            return "#f59e0b"
    
    def _toggle_expand(self):
        """切换展开/折叠状态"""
        self._is_expanded = not self._is_expanded
        
        # 更新按钮图标
        self.expand_btn.setText("▼" if self._is_expanded else "▶")
        
        # 显示/隐藏子任务
        self.children_area.setVisible(self._is_expanded)
        
        self.expanded.emit(self._is_expanded)


class TaskDetailPanel(QFrame):
    """任务详情面板"""
    
    closed = pyqtSignal()
    task_updated = pyqtSignal(Task)
    
    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self._task = task
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setStyleSheet("""
            TaskDetailPanel {
                background-color: #ffffff;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 头部
        header_layout = QHBoxLayout()
        
        status_label = QLabel(self._get_status_text())
        status_label.setStyleSheet(self._get_status_style())
        header_layout.addWidget(status_label)
        
        priority_label = QLabel(self._get_priority_text())
        priority_label.setStyleSheet(self._get_priority_style())
        header_layout.addWidget(priority_label)
        
        header_layout.addStretch()
        
        close_btn = QToolButton()
        close_btn.setText("✕")
        close_btn.setStyleSheet("""
            QToolButton {
                color: #64748b;
                border: none;
                font-size: 16px;
            }
            QToolButton:hover {
                color: #1e293b;
            }
        """)
        close_btn.clicked.connect(self.closed.emit)
        header_layout.addWidget(close_btn)
        
        layout.addLayout(header_layout)
        
        # 标题
        title_label = QLabel(self._task.title)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b;")
        layout.addWidget(title_label)
        
        # 描述
        if self._task.description:
            desc_label = QLabel("📋 描述")
            desc_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #475569;")
            layout.addWidget(desc_label)
            
            desc_content = QLabel(self._task.description)
            desc_content.setStyleSheet("font-size: 14px; color: #64748b;")
            desc_content.setWordWrap(True)
            layout.addWidget(desc_content)
        
        # 进度
        if self._task.progress > 0:
            progress_label = QLabel(f"📊 进度: {self._task.progress}%")
            progress_label.setStyleSheet("font-size: 14px; color: #475569;")
            layout.addWidget(progress_label)
            
            progress_bar = QFrame()
            progress_bar.setStyleSheet("background-color: #e2e8f0; height: 8px; border-radius: 4px;")
            
            progress_fill = QFrame()
            progress_fill.setStyleSheet(f"""
                background-color: {self._get_progress_color()};
                border-radius: 4px;
                height: 8px;
            """)
            progress_fill.setFixedWidth(int(self._task.progress * 2))
            
            bar_layout = QHBoxLayout(progress_bar)
            bar_layout.setContentsMargins(0, 0, 0, 0)
            bar_layout.addWidget(progress_fill)
            
            layout.addWidget(progress_bar)
        
        # 负责人
        if self._task.assignee:
            assignee_label = QLabel(f"👤 负责人: {self._task.assignee}")
            assignee_label.setStyleSheet("font-size: 14px; color: #475569;")
            layout.addWidget(assignee_label)
        
        # 截止日期
        if self._task.due_date:
            due_label = QLabel(f"📅 截止日期: {self._task.due_date}")
            due_label.setStyleSheet("font-size: 14px; color: #475569;")
            layout.addWidget(due_label)
        
        # 标签
        if self._task.tags:
            tags_label = QLabel("🏷️ 标签")
            tags_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #475569;")
            layout.addWidget(tags_label)
            
            tags_layout = QHBoxLayout()
            tags_layout.setSpacing(8)
            
            for tag in self._task.tags:
                tag_label = QLabel(tag)
                tag_label.setStyleSheet("""
                    QLabel {
                        background-color: #e0e7ff;
                        color: #4338ca;
                        padding: 4px 12px;
                        border-radius: 16px;
                        font-size: 12px;
                    }
                """)
                tags_layout.addWidget(tag_label)
            
            layout.addLayout(tags_layout)
        
        # 子任务数量
        if self._task.children:
            children_label = QLabel(f"📝 子任务: {len(self._task.children)} 个")
            children_label.setStyleSheet("font-size: 14px; color: #475569;")
            layout.addWidget(children_label)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        edit_btn = QPushButton("✏️ 编辑")
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        btn_layout.addWidget(edit_btn)
        
        complete_btn = QPushButton("✅ 完成")
        complete_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        btn_layout.addWidget(complete_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
    
    def _get_status_text(self) -> str:
        """获取状态文本"""
        texts = {
            TaskStatus.TODO: "待办",
            TaskStatus.IN_PROGRESS: "进行中",
            TaskStatus.DONE: "已完成",
            TaskStatus.BLOCKED: "阻塞",
            TaskStatus.CANCELLED: "已取消"
        }
        return texts.get(self._task.status, "待办")
    
    def _get_status_style(self) -> str:
        """获取状态样式"""
        styles = {
            TaskStatus.TODO: """
                QLabel {
                    background-color: #e2e8f0;
                    color: #64748b;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                }
            """,
            TaskStatus.IN_PROGRESS: """
                QLabel {
                    background-color: #dbeafe;
                    color: #2563eb;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                }
            """,
            TaskStatus.DONE: """
                QLabel {
                    background-color: #d1fae5;
                    color: #059669;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                }
            """,
            TaskStatus.BLOCKED: """
                QLabel {
                    background-color: #fef3c7;
                    color: #d97706;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                }
            """,
            TaskStatus.CANCELLED: """
                QLabel {
                    background-color: #f3f4f6;
                    color: #9ca3af;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                }
            """
        }
        return styles.get(self._task.status, styles[TaskStatus.TODO])
    
    def _get_priority_text(self) -> str:
        """获取优先级文本"""
        texts = {
            TaskPriority.LOW: "低优先级",
            TaskPriority.MEDIUM: "中优先级",
            TaskPriority.HIGH: "高优先级",
            TaskPriority.CRITICAL: "紧急"
        }
        return texts.get(self._task.priority, "中优先级")
    
    def _get_priority_style(self) -> str:
        """获取优先级样式"""
        styles = {
            TaskPriority.LOW: """
                QLabel {
                    background-color: #f1f5f9;
                    color: #64748b;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                }
            """,
            TaskPriority.MEDIUM: """
                QLabel {
                    background-color: #dbeafe;
                    color: #2563eb;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                }
            """,
            TaskPriority.HIGH: """
                QLabel {
                    background-color: #fef3c7;
                    color: #d97706;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                }
            """,
            TaskPriority.CRITICAL: """
                QLabel {
                    background-color: #fee2e2;
                    color: #dc2626;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                }
            """
        }
        return styles.get(self._task.priority, styles[TaskPriority.MEDIUM])
    
    def _get_progress_color(self) -> str:
        """获取进度条颜色"""
        if self._task.progress >= 100:
            return "#10b981"
        elif self._task.progress >= 50:
            return "#2563eb"
        else:
            return "#f59e0b"


class TaskListWidget(QWidget):
    """任务列表组件"""
    
    task_clicked = pyqtSignal(Task)
    task_double_clicked = pyqtSignal(Task)
    
    def __init__(self, tasks: List[Task] = None, parent=None):
        super().__init__(parent)
        self._tasks = tasks or []
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(4)
        
        # 添加任务
        for task in self._tasks:
            task_item = TaskItem(task)
            task_item.clicked.connect(self.task_clicked.emit)
            task_item.clicked.connect(self.task_double_clicked.emit)
            self.content_layout.addWidget(task_item)
        
        self.content_layout.addStretch()
        
        scroll_area.setWidget(self.content_widget)
        layout.addWidget(scroll_area)
    
    def set_tasks(self, tasks: List[Task]):
        """设置任务列表"""
        self._tasks = tasks
        
        # 清空现有任务
        while self.content_layout.count() > 0:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加新任务
        for task in self._tasks:
            task_item = TaskItem(task)
            task_item.clicked.connect(self.task_clicked.emit)
            task_item.clicked.connect(self.task_double_clicked.emit)
            self.content_layout.addWidget(task_item)
        
        self.content_layout.addStretch()
    
    def add_task(self, task: Task):
        """添加单个任务"""
        self._tasks.append(task)
        
        task_item = TaskItem(task)
        task_item.clicked.connect(self.task_clicked.emit)
        task_item.clicked.connect(self.task_double_clicked.emit)
        
        # 插入到拉伸之前
        self.content_layout.insertWidget(self.content_layout.count() - 1, task_item)


# 示例数据生成
def create_sample_tasks() -> List[Task]:
    """创建示例任务数据"""
    return [
        Task(
            id="1",
            title="完成用户认证模块",
            description="实现用户登录、注册、密码找回等功能",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            assignee="张三",
            due_date="2026-05-15",
            tags=["后端", "认证"],
            progress=65,
            children=[
                Task(
                    id="1-1",
                    title="设计数据库表结构",
                    status=TaskStatus.DONE,
                    priority=TaskPriority.HIGH,
                    progress=100
                ),
                Task(
                    id="1-2",
                    title="实现JWT token生成",
                    status=TaskStatus.IN_PROGRESS,
                    priority=TaskPriority.HIGH,
                    progress=50
                ),
                Task(
                    id="1-3",
                    title="密码加密存储",
                    status=TaskStatus.TODO,
                    priority=TaskPriority.MEDIUM
                )
            ]
        ),
        Task(
            id="2",
            title="优化首页性能",
            description="减少首屏加载时间，优化图片加载",
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            assignee="李四",
            due_date="2026-05-20",
            tags=["前端", "性能"],
            children=[
                Task(
                    id="2-1",
                    title="图片懒加载",
                    status=TaskStatus.TODO,
                    priority=TaskPriority.LOW
                ),
                Task(
                    id="2-2",
                    title="代码分割",
                    status=TaskStatus.TODO,
                    priority=TaskPriority.MEDIUM
                )
            ]
        ),
        Task(
            id="3",
            title="编写API文档",
            status=TaskStatus.BLOCKED,
            priority=TaskPriority.LOW,
            assignee="王五",
            tags=["文档"]
        ),
        Task(
            id="4",
            title="部署到生产环境",
            description="配置CI/CD流程，部署到服务器",
            status=TaskStatus.TODO,
            priority=TaskPriority.CRITICAL,
            due_date="2026-05-30",
            tags=["DevOps"]
        )
    ]