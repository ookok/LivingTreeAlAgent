"""上下文侧边栏面板 - 主题追踪、历史关联、智能推荐"""

from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QColor

class ContextPanel(QFrame):
    """上下文侧边栏面板"""
    
    action_triggered = pyqtSignal(str)
    topic_selected = pyqtSignal(str)
    history_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        self.setFixedWidth(280)
        self.setStyleSheet("""
            QFrame {
                background: #f9fafb;
                border-left: 1px solid #e5e7eb;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)
        
        self._topic_section = self._create_topic_section()
        layout.addWidget(self._topic_section)
        
        self._history_section = self._create_history_section()
        layout.addWidget(self._history_section)
        
        self._actions_section = self._create_actions_section()
        layout.addWidget(self._actions_section)
        
        layout.addStretch()
    
    def _create_topic_section(self):
        """创建主题追踪区域"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setSpacing(8)
        
        header = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(QIcon("icons/topic.png").pixmap(16, 16))
        header.addWidget(icon_label)
        header.addWidget(QLabel("当前主题"))
        header.addStretch()
        layout.addLayout(header)
        
        self._topic_list = QListWidget()
        self._topic_list.setStyleSheet("""
            QListWidget {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background: #eff6ff;
            }
        """)
        self._topic_list.itemClicked.connect(lambda item: self.topic_selected.emit(item.text()))
        layout.addWidget(self._topic_list)
        
        return section
    
    def _create_history_section(self):
        """创建历史关联区域"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setSpacing(8)
        
        header = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(QIcon("icons/history.png").pixmap(16, 16))
        header.addWidget(icon_label)
        header.addWidget(QLabel("相关历史"))
        header.addStretch()
        layout.addLayout(header)
        
        self._history_list = QListWidget()
        self._history_list.setMaximumHeight(120)
        self._history_list.setStyleSheet("""
            QListWidget {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 4px 8px;
                font-size: 12px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background: #eff6ff;
            }
        """)
        self._history_list.itemClicked.connect(lambda item: self.history_selected.emit(item.text()))
        layout.addWidget(self._history_list)
        
        return section
    
    def _create_actions_section(self):
        """创建推荐操作区域"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setSpacing(8)
        
        header = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(QIcon("icons/action.png").pixmap(16, 16))
        header.addWidget(icon_label)
        header.addWidget(QLabel("快捷操作"))
        header.addStretch()
        layout.addLayout(header)
        
        self._actions_layout = QVBoxLayout()
        self._actions_layout.setSpacing(4)
        layout.addLayout(self._actions_layout)
        
        return section
    
    def set_topics(self, topics):
        """设置主题列表"""
        self._topic_list.clear()
        for topic in topics:
            item = QListWidgetItem(topic)
            self._topic_list.addItem(item)
    
    def set_history(self, history_items):
        """设置历史列表"""
        self._history_list.clear()
        for item in history_items:
            list_item = QListWidgetItem(item)
            self._history_list.addItem(list_item)
    
    def add_action_button(self, action_name, icon_name, callback=None):
        """添加操作按钮"""
        btn = QPushButton(action_name)
        btn.setIcon(QIcon(f"icons/{icon_name}.png"))
        btn.setStyleSheet("""
            QPushButton {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 8px 12px;
                text-align: left;
            }
            QPushButton:hover {
                background: #f3f4f6;
            }
        """)
        btn.clicked.connect(lambda: self.action_triggered.emit(action_name))
        if callback:
            btn.clicked.connect(callback)
        self._actions_layout.addWidget(btn)