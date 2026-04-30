"""
P2P广播发现与通信系统 - PyQt6 UI面板
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QFrame, QScrollArea, QComboBox,
    QGroupBox, QCheckBox, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from .business.models import SystemConfig
from .business.p2p_broadcast import (
    P2PBroadcastSystem, DeviceInfo, ChatMessage, Conversation,
    DeviceStatus, BroadcastCategory
)

logger = logging.getLogger(__name__)


class P2PBroadcastPanel(QWidget):
    """P2P广播发现与通信系统面板"""
    
    def __init__(self, config: SystemConfig = None, parent=None):
        super().__init__(parent)
        
        self.config = config or SystemConfig()
        self.system: Optional[P2PBroadcastSystem] = None
        self.current_conv_id: Optional[str] = None
        
        self._init_ui()
        self._init_system()
    
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_discovery_tab(), "发现设备")
        self.tabs.addTab(self._create_chat_tab(), "聊天")
        self.tabs.addTab(self._create_broadcast_tab(), "广播")
        self.tabs.addTab(self._create_friends_tab(), "好友")
        self.tabs.addTab(self._create_settings_tab(), "设置")
        
        main_layout.addWidget(self.tabs)
        
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("P2P系统未启动")
        main_layout.addWidget(self.status_bar)
    
    def _create_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #f5f5f5; padding: 5px;")
        layout = QHBoxLayout(toolbar)
        
        self.start_btn = QPushButton("启动")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.start_btn.clicked.connect(self._toggle_system)
        
        self.status_label = QLabel("状态: 未启动")
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._refresh_devices)
        
        layout.addWidget(self.start_btn)
        layout.addWidget(self.status_label)
        layout.addWidget(self.refresh_btn)
        layout.addStretch()
        
        return toolbar
    
    def _create_discovery_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索设备...")
        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self._search_devices)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)
        layout.addLayout(search_layout)
        
        self.device_list = QListWidget()
        layout.addWidget(self.device_list)
        
        btn_layout = QHBoxLayout()
        self.add_friend_btn = QPushButton("添加好友")
        self.add_friend_btn.clicked.connect(self._add_friend)
        self.chat_btn = QPushButton("发起聊天")
        self.chat_btn.clicked.connect(self._start_chat)
        btn_layout.addWidget(self.add_friend_btn)
        btn_layout.addWidget(self.chat_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return widget
    
    def _create_chat_tab(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        left_panel = QFrame()
        left_panel.setMaximumWidth(200)
        left_layout = QVBoxLayout(left_panel)
        
        left_layout.addWidget(QLabel("会话列表"))
        self.conv_list = QListWidget()
        self.conv_list.itemClicked.connect(self._select_conversation)
        left_layout.addWidget(self.conv_list)
        
        layout.addWidget(left_panel)
        
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        
        self.chat_header = QLabel("选择会话开始聊天")
        self.chat_header.setStyleSheet("font-weight: bold; padding: 5px;")
        right_layout.addWidget(self.chat_header)
        
        self.chat_area = QScrollArea()
        self.chat_area.setWidgetResizable(True)
        self.chat_content = QWidget()
        self.chat_content_layout = QVBoxLayout(self.chat_content)
        self.chat_content_layout.addStretch()
        self.chat_area.setWidget(self.chat_content)
        right_layout.addWidget(self.chat_area)
        
        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("输入消息...")
        self.chat_input.returnPressed.connect(self._send_message)
        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.chat_input)
        input_layout.addWidget(self.send_btn)
        right_layout.addLayout(input_layout)
        
        layout.addWidget(right_panel)
        
        return widget
    
    def _create_broadcast_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("发送广播")
        group_layout = QVBoxLayout(group)
        
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("分类:"))
        self.broadcast_category = QComboBox()
        for cat in BroadcastCategory:
            self.broadcast_category.addItem(cat.value, cat)
        category_layout.addWidget(self.broadcast_category)
        category_layout.addStretch()
        group_layout.addLayout(category_layout)
        
        self.broadcast_input = QLineEdit()
        self.broadcast_input.setPlaceholderText("输入广播内容...")
        group_layout.addWidget(self.broadcast_input)
        
        broadcast_btn_layout = QHBoxLayout()
        self.broadcast_send_btn = QPushButton("发送广播")
        self.broadcast_send_btn.clicked.connect(self._send_broadcast)
        broadcast_btn_layout.addWidget(self.broadcast_send_btn)
        broadcast_btn_layout.addStretch()
        group_layout.addLayout(broadcast_btn_layout)
        
        layout.addWidget(group)
        
        layout.addWidget(QLabel("收到的广播"))
        self.broadcast_list = QListWidget()
        layout.addWidget(self.broadcast_list)
        
        return widget
    
    def _create_friends_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.friends_list = QTableWidget()
        self.friends_list.setColumnCount(4)
        self.friends_list.setHorizontalHeaderLabels(["用户名", "设备名", "IP", "状态"])
        self.friends_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.friends_list)
        
        return widget
    
    def _create_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        basic_group = QGroupBox("基本设置")
        basic_layout = QVBoxLayout(basic_group)
        
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("用户名:"))
        self.user_name_input = QLineEdit()
        self.user_name_input.setText(self.config.user_name)
        name_layout.addWidget(self.user_name_input)
        basic_layout.addLayout(name_layout)
        
        layout.addWidget(basic_group)
        
        network_group = QGroupBox("网络设置")
        network_layout = QVBoxLayout(network_group)
        
        self.ai_reply_check = QCheckBox("启用AI自动回复")
        self.ai_reply_check.setChecked(True)
        network_layout.addWidget(self.ai_reply_check)
        
        self.broadcast_enabled_check = QCheckBox("启用广播发现")
        self.broadcast_enabled_check.setChecked(self.config.broadcast_enabled)
        network_layout.addWidget(self.broadcast_enabled_check)
        
        layout.addWidget(network_group)
        
        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)
        
        layout.addStretch()
        
        return widget
    
    def _init_system(self):
        self.system = P2PBroadcastSystem(self.config)
        self.system.device_discovered.connect(self._on_device_found)
        self.system.device_left.connect(self._on_device_left)
        self.system.message_received.connect(self._on_message_received)
        self.system.broadcast_received.connect(self._on_broadcast_received)
        self.system.connection_status_changed.connect(self._on_status_changed)
    
    def _toggle_system(self):
        if self.system.is_running:
            self.system.stop()
            self.start_btn.setText("启动")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
            """)
        else:
            self.system.start()
            self.start_btn.setText("停止")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
            """)
    
    def _refresh_devices(self):
        if not self.system:
            return
        
        self.device_list.clear()
        
        for device in self.system.get_online_devices():
            status_icon = "O" if device.is_online() else "X"
            friend_icon = "*" if device.is_friend else ""
            self.device_list.addItem(f"[{status_icon}] {device.user_name} ({device.device_name}) {friend_icon}")
        
        self.status_bar.showMessage(f"在线设备: {len(self.system.get_online_devices())}")
    
    def _search_devices(self):
        keyword = self.search_input.text().lower()
        if not keyword:
            self._refresh_devices()
            return
        
        self.device_list.clear()
        
        for device in self.system.get_devices():
            if keyword in device.user_name.lower() or keyword in device.device_name.lower():
                self.device_list.addItem(f"{device.user_name} ({device.device_name})")
    
    def _add_friend(self):
        current_item = self.device_list.currentItem()
        if not current_item:
            return
        
        self.status_bar.showMessage("好友已添加")
    
    def _start_chat(self):
        self.tabs.setCurrentIndex(1)
    
    def _select_conversation(self, item):
        self.chat_header.setText(f"与 {item.text()} 的对话")
    
    def _send_message(self):
        content = self.chat_input.text().strip()
        if content:
            self.chat_input.clear()
    
    def _send_broadcast(self):
        content = self.broadcast_input.text().strip()
        if content and self.system:
            self.system.send_broadcast(content)
            self.broadcast_input.clear()
            self.status_bar.showMessage("广播已发送")
    
    def _save_settings(self):
        self.config.user_name = self.user_name_input.text()
        
        if self.system:
            self.system.config = self.config
            self.system.save_config()
        
        self.status_bar.showMessage("设置已保存")
    
    def _on_device_found(self, device: DeviceInfo):
        self._refresh_devices()
    
    def _on_device_left(self, device_id: str):
        self._refresh_devices()
    
    def _on_message_received(self, conv_id: str, message: ChatMessage):
        self.status_bar.showMessage(f"新消息 from {message.sender_name}")
    
    def _on_broadcast_received(self, broadcast):
        sender = broadcast.sender.user_name if broadcast.sender else "Unknown"
        self.broadcast_list.addItem(f"[{sender}]: {broadcast.content[:50]}")
    
    def _on_status_changed(self, is_running: bool):
        status = "运行中" if is_running else "已停止"
        self.status_label.setText(f"状态: {status}")
        self.status_bar.showMessage(f"P2P系统{status}")


__all__ = [
    "P2PBroadcastPanel",
]
