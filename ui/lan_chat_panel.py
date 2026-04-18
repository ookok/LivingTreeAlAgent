# -*- coding: utf-8 -*-
"""
LAN Chat 面板 - PyQt6 局域网聊天 UI
=====================================

功能：
- UDP广播发现局域网内的用户
- TCP点对点消息传输
- AI自动回复
- 消息历史记录

Author: Hermes Desktop Team
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QComboBox, QTabWidget, QGroupBox,
    QScrollArea, QFrame, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QStatusBar, QMenuBar, QMenu,
    QToolButton, QStackedWidget, QFormLayout, QSpinBox,
    QCheckBox, QMessageBox, QSplitter
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QIcon, QAction, QColor, QPalette, QPainter, QPen

import asyncio
import json
import time
from datetime import datetime
from typing import Optional, Dict, List

from core.lan_chat import (
    LANUser, LANChatManager, UserStatus,
    DISCOVERY_PORT, CHAT_PORT
)


# ==================== 用户列表项 ====================

class UserListItem(QFrame):
    """用户列表项"""

    def __init__(self, user: LANUser, parent=None):
        super().__init__(parent)
        self.user = user
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # 状态指示
        self.status_indicator = QLabel("⚫" if self.user.status == UserStatus.ONLINE else "⚪")
        self.status_indicator.setFont(QFont("Segoe UI Emoji", 12))
        layout.addWidget(self.status_indicator)

        # 用户信息
        info_layout = QVBoxLayout()
        
        self.name_label = QLabel(self.user.name)
        self.name_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        info_layout.addWidget(self.name_label)
        
        self.ip_label = QLabel(f"{self.user.ip_address}:{self.user.port}")
        self.ip_label.setFont(QFont("Consolas", 9))
        self.ip_label.setStyleSheet("color: #888;")
        info_layout.addWidget(self.ip_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()

        # 在线状态
        self.status_label = QLabel(self._get_status_text())
        self.status_label.setFont(QFont("Microsoft YaHei", 9))
        self._update_status_label()
        layout.addWidget(self.status_label)

    def _get_status_text(self) -> str:
        status_map = {
            UserStatus.ONLINE: "🟢 在线",
            UserStatus.OFFLINE: "⚪ 离线",
            UserStatus.AWAY: "🟡 离开"
        }
        return status_map.get(self.user.status, "⚪ 未知")

    def _update_status_label(self):
        colors = {
            UserStatus.ONLINE: "#2ecc71",
            UserStatus.OFFLINE: "#95a5a6",
            UserStatus.AWAY: "#f39c12"
        }
        color = colors.get(self.user.status, "#95a5a6")
        self.status_label.setStyleSheet(f"color: {color};")

    def _update_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            UserListItem {
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
            }
            UserListItem:hover {
                border-color: #1890ff;
            }
        """)

    def update_user(self, user: LANUser):
        self.user = user
        self.name_label.setText(user.name)
        self.ip_label.setText(f"{user.ip_address}:{user.port}")
        self.status_label.setText(self._get_status_text())
        self._update_status_label()
        status_color = "#2ecc71" if user.status == UserStatus.ONLINE else "#95a5a6"
        self.status_indicator.setStyleSheet(f"color: {status_color};")


# ==================== 消息气泡 ====================

class MessageBubble(QFrame):
    """消息气泡"""

    def __init__(self, text: str, is_mine: bool, timestamp: float, parent=None):
        super().__init__(parent)
        self.text = text
        self.is_mine = is_mine
        self.timestamp = timestamp
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # 时间和状态
        time_layout = QHBoxLayout()
        
        time_label = QLabel(datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S"))
        time_label.setFont(QFont("Microsoft YaHei", 8))
        time_label.setStyleSheet("color: #888;")
        
        if self.is_mine:
            time_layout.addStretch()
        
        time_layout.addWidget(time_label)
        
        if not self.is_mine:
            time_layout.addStretch()
        
        layout.addLayout(time_layout)

        # 消息内容
        message_layout = QHBoxLayout()
        
        if not self.is_mine:
            message_layout.addStretch()
        
        self.text_label = QLabel(self.text)
        self.text_label.setWordWrap(True)
        self.text_label.setFont(QFont("Microsoft YaHei", 10))
        
        bubble_layout = QHBoxLayout()
        bubble_layout.addWidget(self.text_label)
        
        bubble_frame = QFrame()
        bubble_frame.setLayout(bubble_layout)
        
        message_layout.addWidget(bubble_frame)
        
        layout.addLayout(message_layout)

    def _update_style(self):
        bg_color = "#e6f7ff" if self.is_mine else "#f5f5f5"
        align = "right" if self.is_mine else "left"
        
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            MessageBubble {{
                background-color: transparent;
            }}
            QLabel {{
                background-color: {bg_color};
                border-radius: 12px;
                padding: 8px 12px;
            }}
        """)


# ==================== LAN Chat Panel ====================

class LANChatPanel(QWidget):
    """局域网聊天面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化 LAN Chat 管理器
        self.manager = LANChatManager()
        
        # 绑定回调
        self.manager.on_user_discovered = self._on_user_discovered
        self.manager.on_user_left = self._on_user_left
        self.manager.on_message_received = self._on_message_received
        
        # 当前选中的用户
        self.current_user: Optional[LANUser] = None
        
        self._setup_ui()
        self._start_discovery()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧：用户列表
        left_panel = QFrame()
        left_panel.setMaximumWidth(250)
        left_panel.setStyleSheet("background-color: #f5f5f5;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(12)

        # 用户列表标题
        title_label = QLabel("👥 局域网用户")
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        left_layout.addWidget(title_label)

        # 用户列表
        self.user_list = QListWidget()
        self.user_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                background-color: #fff;
                border-radius: 6px;
                margin-bottom: 6px;
            }
        """)
        self.user_list.itemClicked.connect(self._on_user_selected)
        left_layout.addWidget(self.user_list)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新用户")
        refresh_btn.clicked.connect(self._start_discovery)
        left_layout.addWidget(refresh_btn)

        main_layout.addWidget(left_panel)

        # 右侧：聊天区域
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12)

        # 聊天标题
        self.chat_title = QLabel("💬 选择一个用户开始聊天")
        self.chat_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        right_layout.addWidget(self.chat_title)

        # 消息列表
        self.message_list = QScrollArea()
        self.message_list.setWidgetResizable(True)
        self.message_list.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #fff;
            }
        """)
        
        self.message_container = QWidget()
        self.message_layout = QVBoxLayout(self.message_container)
        self.message_layout.setSpacing(8)
        self.message_layout.addStretch()
        
        self.message_list.setWidget(self.message_container)
        right_layout.addWidget(self.message_list, 1)

        # 输入区域
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(80)
        self.message_input.setPlaceholderText("输入消息...")
        self.message_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px;
                background-color: #fff;
            }
        """)
        input_layout.addWidget(self.message_input)

        # 发送按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        send_btn = QPushButton("📤 发送")
        send_btn.setFont(QFont("Microsoft YaHei", 10))
        send_btn.clicked.connect(self._on_send_message)
        btn_layout.addWidget(send_btn)
        
        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setFont(QFont("Microsoft YaHei", 10))
        clear_btn.clicked.connect(self._on_clear_messages)
        btn_layout.addWidget(clear_btn)
        
        input_layout.addLayout(btn_layout)
        right_layout.addWidget(input_frame)

        main_layout.addWidget(right_panel, 1)

    def _start_discovery(self):
        """开始发现用户"""
        self.manager.start_discovery()
        
        # 刷新用户列表
        self._refresh_user_list()

    def _refresh_user_list(self):
        """刷新用户列表"""
        self.user_list.clear()
        
        for user in self.manager.get_online_users():
            item = QListWidgetItem()
            item.setSizeHint(QSize(200, 60))
            self.user_list.addItem(item)
            
            widget = UserListItem(user)
            self.user_list.setItemWidget(item, widget)

    def _on_user_selected(self, item: QListWidgetItem):
        """选择用户"""
        widget = self.user_list.itemWidget(item)
        if widget:
            self.current_user = widget.user
            self.chat_title.setText(f"💬 {self.current_user.name}")
            self._load_messages()

    def _load_messages(self):
        """加载消息历史"""
        # 清空现有消息
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if self.current_user:
            messages = self.manager.get_message_history(self.current_user.id)
            for msg in messages:
                is_mine = msg.get("is_mine", False)
                bubble = MessageBubble(msg["text"], is_mine, msg["timestamp"])
                self.message_layout.insertWidget(self.message_layout.count() - 1, bubble)

    def _on_send_message(self):
        """发送消息"""
        if not self.current_user:
            return
        
        text = self.message_input.toPlainText().strip()
        if not text:
            return
        
        # 发送消息
        success = self.manager.send_message(
            self.current_user.id,
            text
        )
        
        if success:
            # 添加消息气泡
            bubble = MessageBubble(text, True, time.time())
            self.message_layout.insertWidget(self.message_layout.count() - 1, bubble)
            
            # 清空输入
            self.message_input.clear()
            
            # 滚动到底部
            scrollbar = self.message_list.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _on_clear_messages(self):
        """清空消息"""
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_user_discovered(self, user: LANUser):
        """发现新用户"""
        self._refresh_user_list()

    def _on_user_left(self, user_id: str):
        """用户离开"""
        if self.current_user and self.current_user.id == user_id:
            self.current_user = None
            self.chat_title.setText("💬 选择一个用户开始聊天")
        self._refresh_user_list()

    def _on_message_received(self, user_id: str, message: str):
        """收到消息"""
        if self.current_user and self.current_user.id == user_id:
            bubble = MessageBubble(message, False, time.time())
            self.message_layout.insertWidget(self.message_layout.count() - 1, bubble)
            
            # 滚动到底部
            scrollbar = self.message_list.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
        self._refresh_user_list()

    def closeEvent(self, event):
        """关闭时停止发现"""
        self.manager.stop_discovery()
        super().closeEvent(event)


# ==================== 导出 ====================

__all__ = ['LANChatPanel', 'UserListItem', 'MessageBubble']
