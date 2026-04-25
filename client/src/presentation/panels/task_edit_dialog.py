"""
任务编辑对话框
支持修改任务标题、描述、优先级等配置
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QPushButton, QGroupBox, QFormLayout,
    QDialogButtonBox, QMessageBox
)
from PyQt6.QtGui import QFont

from client.src.business.enhanced_task import Task, TaskPriority


class TaskEditDialog(QDialog):
    """
    任务编辑对话框
    
    功能：
    - 编辑任务标题
    - 编辑任务描述
    - 修改优先级
    - 查看任务状态
    """
    
    # 信号
    saved = pyqtSignal(dict)  # 发射保存的配置
    
    def __init__(self, task: Task = None, parent=None):
        super().__init__(parent)
        self.task = task
        self._setup_ui()
        
        if task:
            self._load_task(task)
    
    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("编辑任务" if self.task else "新建任务")
        self.setMinimumWidth(450)
        self.setStyleSheet("""
            QDialog {
                background: #f8fafc;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #475569;
            }
            QLineEdit, QTextEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
                background: white;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #3b82f6;
            }
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
                background: white;
            }
            QPushButton {
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton[primary="true"] {
                background: #3b82f6;
                color: white;
            }
            QPushButton[primary="true"]:hover {
                background: #2563eb;
            }
            QPushButton[secondary="true"] {
                background: #e2e8f0;
                color: #475569;
            }
            QPushButton[secondary="true"]:hover {
                background: #cbd5e1;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 任务信息组
        info_group = QGroupBox("任务信息")
        info_layout = QFormLayout()
        info_layout.setSpacing(12)
        
        # 任务ID（只读）
        self._id_label = QLabel("-")
        self._id_label.setStyleSheet("color: #64748b; font-family: monospace;")
        
        # 标题
        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("输入任务标题...")
        
        # 描述
        self._desc_input = QTextEdit()
        self._desc_input.setPlaceholderText("输入任务描述（可选）...")
        self._desc_input.setMaximumHeight(100)
        
        info_layout.addRow("任务ID:", self._id_label)
        info_layout.addRow("标题:", self._title_input)
        info_layout.addRow("描述:", self._desc_input)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # 设置组
        settings_group = QGroupBox("任务设置")
        settings_layout = QFormLayout()
        settings_layout.setSpacing(12)
        
        # 优先级
        self._priority_combo = QComboBox()
        self._priority_combo.addItem("🔽 低", TaskPriority.LOW)
        self._priority_combo.addItem("📋 普通", TaskPriority.NORMAL)
        self._priority_combo.addItem("🔼 高", TaskPriority.HIGH)
        self._priority_combo.addItem("🚨 紧急", TaskPriority.URGENT)
        
        settings_layout.addRow("优先级:", self._priority_combo)
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # 状态信息（只读）
        self._status_label = QLabel("-")
        self._progress_label = QLabel("-")
        
        status_group = QGroupBox("当前状态")
        status_layout = QFormLayout()
        status_layout.setSpacing(12)
        status_layout.addRow("状态:", self._status_label)
        status_layout.addRow("进度:", self._progress_label)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setProperty("secondary", True)
        self._cancel_btn.clicked.connect(self.reject)
        
        self._save_btn = QPushButton("保存")
        self._save_btn.setProperty("primary", True)
        self._save_btn.clicked.connect(self._on_save)
        
        btn_layout.addWidget(self._cancel_btn)
        btn_layout.addWidget(self._save_btn)
        layout.addLayout(btn_layout)
    
    def _load_task(self, task: Task):
        """加载任务数据"""
        self._id_label.setText(task.id)
        self._title_input.setText(task.config.title)
        self._desc_input.setText(task.config.description)
        
        # 设置优先级
        for i in range(self._priority_combo.count()):
            if self._priority_combo.itemData(i) == task.priority:
                self._priority_combo.setCurrentIndex(i)
                break
        
        # 状态信息
        self._status_label.setText(task.state_text)
        self._progress_label.setText(f"{task.progress:.1f}%")
        
        # 根据状态禁用控件
        if not task.is_editable:
            self._title_input.setEnabled(False)
            self._desc_input.setEnabled(False)
            self._priority_combo.setEnabled(False)
            self._save_btn.setEnabled(False)
            self._status_label.setText(f"{task.state_text}（不可编辑）")
    
    def _on_save(self):
        """保存"""
        title = self._title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "请输入任务标题")
            return
        
        config = {
            "title": title,
            "description": self._desc_input.toPlainText().strip(),
            "priority": self._priority_combo.currentData(),
        }
        
        self.saved.emit(config)
        self.accept()
    
    def get_config(self) -> dict:
        """获取配置"""
        return {
            "title": self._title_input.text().strip(),
            "description": self._desc_input.toPlainText().strip(),
            "priority": self._priority_combo.currentData(),
        }


class TaskBatchEditDialog(QDialog):
    """批量编辑对话框"""
    
    def __init__(self, task_count: int, parent=None):
        super().__init__(parent)
        self.task_count = task_count
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle(f"批量编辑 ({self.task_count} 个任务)")
        self.setMinimumWidth(400)
        self.setStyleSheet("""
            QDialog {
                background: #f8fafc;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #475569;
            }
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
            }
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
            }
            QPushButton {
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 提示
        tip = QLabel(f"将修改选中的 {self.task_count} 个任务")
        tip.setStyleSheet("color: #64748b; padding: 8px; background: #f1f5f9; border-radius: 6px;")
        layout.addWidget(tip)
        
        # 操作组
        action_group = QGroupBox("批量操作")
        action_layout = QVBoxLayout()
        action_layout.setSpacing(8)
        
        # 优先级
        priority_layout = QHBoxLayout()
        priority_layout.addWidget(QLabel("设置优先级为:"))
        
        self._priority_combo = QComboBox()
        self._priority_combo.addItem("保持不变", None)
        self._priority_combo.addItem("🔽 低", TaskPriority.LOW)
        self._priority_combo.addItem("📋 普通", TaskPriority.NORMAL)
        self._priority_combo.addItem("🔼 高", TaskPriority.HIGH)
        self._priority_combo.addItem("🚨 紧急", TaskPriority.URGENT)
        
        priority_layout.addWidget(self._priority_combo, 1)
        action_layout.addLayout(priority_layout)
        
        action_group.setLayout(action_layout)
        layout.addWidget(action_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("background: #e2e8f0; color: #475569;")
        cancel_btn.clicked.connect(self.reject)
        
        apply_btn = QPushButton("应用")
        apply_btn.setStyleSheet("background: #3b82f6; color: white;")
        apply_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(apply_btn)
        layout.addLayout(btn_layout)
    
    def get_priority(self) -> TaskPriority:
        """获取设置的优先级"""
        return self._priority_combo.currentData()


class TaskCancelConfirmDialog(QDialog):
    """取消确认对话框"""
    
    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("确认取消")
        self.setMinimumWidth(350)
        self.setStyleSheet("""
            QDialog {
                background: #f8fafc;
            }
            QLabel {
                color: #1f2937;
            }
            QPushButton {
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 图标
        icon = QLabel("⚠️")
        icon.setFont(QFont("Segoe UI", 36))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        
        # 标题
        title = QLabel("确认取消任务")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 任务信息
        info = QLabel(f"任务: {self.task.title}")
        info.setStyleSheet("color: #64748b;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)
        
        # 进度信息
        if self.task.status.value == "running":
            progress_info = QLabel(f"当前进度: {self.task.progress:.1f}%")
            progress_info.setStyleSheet("color: #f59e0b;")
            progress_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(progress_info)
        
        # 警告
        warning = QLabel("⚠️ 正在执行的任务可能无法完全取消")
        warning.setStyleSheet("color: #ef4444; font-size: 12px;")
        warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(warning)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        no_btn = QPushButton("不取消")
        no_btn.setStyleSheet("background: #e2e8f0; color: #475569;")
        no_btn.clicked.connect(self.reject)
        
        yes_btn = QPushButton("确认取消")
        yes_btn.setStyleSheet("background: #ef4444; color: white;")
        yes_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(no_btn)
        btn_layout.addWidget(yes_btn)
        layout.addLayout(btn_layout)
