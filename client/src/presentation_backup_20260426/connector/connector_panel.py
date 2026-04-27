"""
P2P连接器 PyQt6 UI 面板

功能:
- 我的短ID展示
- 连接输入框
- 多通道通信 (文本/文件/语音/视频/直播)
- 联系人列表
- 在线状态
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                             QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
                             QPushButton, QLabel, QTabWidget,
                             QToolBar, QStatusBar, QMenu, QDialog,
                             QFileDialog, QMessageBox, QFrame,
                             QScrollArea, QProgressBar)

logger = logging.getLogger(__name__)


class ConnectorPanel(QWidget):
    """
    P2P连接器主面板
    
    布局:
    - 顶部: 我的ID + 连接输入
    - 左侧: 联系人列表
    - 右侧: 通信窗口 (文本/文件/语音/视频)
    """
    
    new_message_signal = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.hub = None  # ConnectorHub
        self.current_peer = None
        self.connections = {}  # peer_node_id -> connection_id
        
        self._init_ui()
        self._init_timer()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 顶部信息栏
        header = self._create_header()
        layout.addWidget(header)
        
        # 主内容区
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧: 联系人
        left_panel = self._create_contacts_panel()
        main_splitter.addWidget(left_panel)
        main_splitter.setStretchFactor(0, 1)
        
        # 右侧: 通信窗口
        right_panel = self._create_chat_panel()
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(1, 3)
        
        layout.addWidget(main_splitter)
        
        # 状态栏
        self.status_bar = QStatusBar()
        layout.addWidget(self.status_bar)
        self.status_bar.showMessage("未连接")
    
    def _create_header(self) -> QWidget:
        """创建顶部信息栏"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
                color: white;
                padding: 10px;
            }
        """)
        layout = QHBoxLayout(widget)
        
        # 我的ID
        id_label = QLabel("我的短ID:")
        id_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(id_label)
        
        self.my_id_label = QLabel("--------")
        self.my_id_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #00d4ff;
                letter-spacing: 2px;
            }
        """)
        layout.addWidget(self.my_id_label)
        
        # 复制按钮
        copy_btn = QPushButton("复制")
        copy_btn.clicked.connect(self._on_copy_id)
        layout.addWidget(copy_btn)
        
        layout.addStretch()
        
        # 连接输入
        connect_label = QLabel("连接ID:")
        layout.addWidget(connect_label)
        
        self.connect_input = QLineEdit()
        self.connect_input.setPlaceholderText("输入对方短ID...")
        self.connect_input.setFixedWidth(150)
        self.connect_input.returnPressed.connect(self._on_connect)
        layout.addWidget(self.connect_input)
        
        connect_btn = QPushButton("连接")
        connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #00d4ff;
                color: #1a1a2e;
                padding: 5px 15px;
                border-radius: 4px;
            }
        """)
        connect_btn.clicked.connect(self._on_connect)
        layout.addWidget(connect_btn)
        
        return widget
    
    def _create_contacts_panel(self) -> QWidget:
        """创建联系人面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 标题
        title = QLabel("联系人")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        layout.addWidget(title)
        
        # 在线节点
        online_label = QLabel("在线节点")
        online_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(online_label)
        
        self.online_list = QListWidget()
        self.online_list.itemDoubleClicked.connect(self._on_peer_double_clicked)
        self.online_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.online_list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.online_list)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._on_refresh)
        toolbar.addWidget(refresh_btn)
        
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._on_add_contact)
        toolbar.addWidget(add_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        return widget
    
    def _create_chat_panel(self) -> QWidget:
        """创建通信面板"""
        self.chat_stack = QTabWidget()
        
        # 文本聊天页
        text_page = self._create_text_page()
        self.chat_stack.addTab(text_page, "💬 文本")
        
        # 文件传输页
        file_page = self._create_file_page()
        self.chat_stack.addTab(file_page, "📎 文件")
        
        # 语音通话页
        voice_page = self._create_voice_page()
        self.chat_stack.addTab(voice_page, "🎙️ 语音")
        
        # 视频通话页
        video_page = self._create_video_page()
        self.chat_stack.addTab(video_page, "📹 视频")
        
        # 直播页
        live_page = self._create_live_page()
        self.chat_stack.addTab(live_page, "📺 直播")
        
        layout = QVBoxLayout()
        layout.addWidget(self.chat_stack)
        
        container = QWidget()
        container.setLayout(layout)
        return container
    
    def _create_text_page(self) -> QWidget:
        """创建文本聊天页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 聊天区域
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: none;
                padding: 10px;
            }
        """)
        layout.addWidget(self.chat_area)
        
        # 输入区
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-top: 1px solid #ddd;
                padding: 10px;
            }
        """)
        input_layout = QHBoxLayout(input_frame)
        
        self.chat_input = QTextEdit()
        self.chat_input.setPlaceholderText("输入消息...")
        self.chat_input.setMaximumHeight(100)
        input_layout.addWidget(self.chat_input)
        
        send_btn = QPushButton("发送")
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #00d4ff;
                color: white;
                padding: 10px 20px;
                border-radius: 4px;
            }
        """)
        send_btn.clicked.connect(self._on_send_message)
        input_layout.addWidget(send_btn)
        
        layout.addWidget(input_frame)
        
        return widget
    
    def _create_file_page(self) -> QWidget:
        """创建文件传输页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info = QLabel("选择文件发送给连接的联系人")
        info.setStyleSheet("color: #666; padding: 10px;")
        layout.addWidget(info)
        
        # 文件列表
        self.file_list = QListWidget()
        layout.addWidget(self.file_list)
        
        # 进度条
        self.file_progress = QProgressBar()
        self.file_progress.setVisible(False)
        layout.addWidget(self.file_progress)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        select_btn = QPushButton("选择文件")
        select_btn.clicked.connect(self._on_select_file)
        btn_layout.addWidget(select_btn)
        
        send_btn = QPushButton("发送")
        send_btn.clicked.connect(self._on_send_file)
        btn_layout.addWidget(send_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        
        return widget
    
    def _create_voice_page(self) -> QWidget:
        """创建语音通话页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addStretch()
        
        # 图标
        icon_label = QLabel("🎙️")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 64px;")
        layout.addWidget(icon_label)
        
        self.voice_status = QLabel("未连接")
        self.voice_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.voice_status.setStyleSheet("font-size: 18px; color: #666;")
        layout.addWidget(self.voice_status)
        
        # 通话时长
        self.voice_duration = QLabel("00:00:00")
        self.voice_duration.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.voice_duration.setStyleSheet("font-size: 32px; font-weight: bold;")
        self.voice_duration.setVisible(False)
        layout.addWidget(self.voice_duration)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.voice_call_btn = QPushButton("开始通话")
        self.voice_call_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 15px 40px;
                font-size: 16px;
                border-radius: 8px;
            }
        """)
        self.voice_call_btn.clicked.connect(self._on_voice_call)
        btn_layout.addWidget(self.voice_call_btn)
        
        self.voice_hangup_btn = QPushButton("挂断")
        self.voice_hangup_btn.setVisible(False)
        self.voice_hangup_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 15px 40px;
                font-size: 16px;
                border-radius: 8px;
            }
        """)
        self.voice_hangup_btn.clicked.connect(self._on_voice_hangup)
        btn_layout.addWidget(self.voice_hangup_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        
        return widget
    
    def _create_video_page(self) -> QWidget:
        """创建视频通话页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 视频预览
        preview_label = QLabel("[视频预览]")
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setStyleSheet("""
            QLabel {
                background-color: #333;
                color: #666;
                min-height: 300px;
                border-radius: 8px;
            }
        """)
        layout.addWidget(preview_label)
        
        # 状态
        self.video_status = QLabel("未连接")
        self.video_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.video_status)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.video_call_btn = QPushButton("开始视频通话")
        self.video_call_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 15px 40px;
                font-size: 16px;
                border-radius: 8px;
            }
        """)
        self.video_call_btn.clicked.connect(self._on_video_call)
        btn_layout.addWidget(self.video_call_btn)
        
        self.video_hangup_btn = QPushButton("挂断")
        self.video_hangup_btn.setVisible(False)
        self.video_hangup_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 15px 40px;
                font-size: 16px;
                border-radius: 8px;
            }
        """)
        self.video_hangup_btn.clicked.connect(self._on_video_hangup)
        btn_layout.addWidget(self.video_hangup_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return widget
    
    def _create_live_page(self) -> QWidget:
        """创建直播页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info = QLabel("创建直播推流, 分享给所有联系人")
        info.setStyleSheet("color: #666; padding: 10px;")
        layout.addWidget(info)
        
        # 直播预览
        preview_label = QLabel("[直播预览]")
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setStyleSheet("""
            QLabel {
                background-color: #222;
                color: #666;
                min-height: 250px;
                border-radius: 8px;
            }
        """)
        layout.addWidget(preview_label)
        
        # 观众数
        self.live_viewers = QLabel("观看人数: 0")
        self.live_viewers.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.live_viewers)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.live_start_btn = QPushButton("开始直播")
        self.live_start_btn.setStyleSheet("""
            QPushButton {
                background-color: #e91e63;
                color: white;
                padding: 15px 40px;
                font-size: 16px;
                border-radius: 8px;
            }
        """)
        self.live_start_btn.clicked.connect(self._on_live_start)
        btn_layout.addWidget(self.live_start_btn)
        
        self.live_stop_btn = QPushButton("停止直播")
        self.live_stop_btn.setVisible(False)
        self.live_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #9e9e9e;
                color: white;
                padding: 15px 40px;
                font-size: 16px;
                border-radius: 8px;
            }
        """)
        self.live_stop_btn.clicked.connect(self._on_live_stop)
        btn_layout.addWidget(self.live_stop_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        
        return widget
    
    def _init_timer(self):
        """初始化定时器"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._on_refresh)
        self.refresh_timer.start(10000)  # 10秒刷新
    
    # ========== 事件处理 ==========
    
    def set_hub(self, hub):
        """设置连接器核心"""
        self.hub = hub
        self._update_display()
    
    def _update_display(self):
        """更新显示"""
        if not self.hub:
            return
        
        status = self.hub.get_status()
        
        # 我的ID
        self.my_id_label.setText(status.get("short_id", "--------"))
        
        # 在线节点
        self.online_list.clear()
        peers = self.hub.get_online_peers()
        for peer in peers:
            item = QListWidgetItem()
            item.setText(f"{peer.display_name} ({peer.short_id})")
            item.setData(Qt.ItemDataRole.UserRole, peer.node_id)
            self.online_list.addItem(item)
        
        # 状态栏
        self.status_bar.showMessage(
            f"节点: {status.get('node_id', '')[:16]}... | "
            f"在线: {status.get('online_peers', 0)} | "
            f"连接: {status.get('connections', 0)}"
        )
    
    def _on_copy_id(self):
        """复制我的ID"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.my_id_label.text())
        
        self.status_bar.showMessage("短ID已复制到剪贴板")
    
    def _on_connect(self):
        """连接到对端"""
        short_id = self.connect_input.text().strip()
        if not short_id:
            return
        
        if not short_id.isdigit():
            QMessageBox.warning(self, "错误", "短ID必须是纯数字")
            return
        
        self.status_bar.showMessage(f"正在连接 {short_id}...")
        
        asyncio.create_task(self._connect_async(short_id))
    
    async def _connect_async(self, short_id: str):
        """异步连接"""
        try:
            connection_id = await self.hub.connect_to_peer(short_id)
            
            if connection_id:
                self.status_bar.showMessage(f"已连接到 {short_id}")
                self._on_refresh()
                
                # 切换到文本聊天
                self.chat_stack.setCurrentIndex(0)
            else:
                self.status_bar.showMessage(f"连接 {short_id} 失败")
                QMessageBox.warning(self, "连接失败", f"无法连接到 {short_id}\n请检查ID是否正确")
                
        except Exception as e:
            logger.error(f"Connect failed: {e}")
            self.status_bar.showMessage(f"连接异常: {e}")
    
    def _on_peer_double_clicked(self, item: QListWidgetItem):
        """双击节点"""
        node_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_peer = node_id
        
        # 连接并切换到聊天
        self.status_bar.showMessage(f"正在连接...")
        asyncio.create_task(self._connect_async(item.text().split("(")[1].split(")")[0]))
    
    def _on_context_menu(self, pos):
        """右键菜单"""
        menu = QMenu()
        
        view_action = menu.addAction("查看资料")
        message_action = menu.addAction("发消息")
        file_action = menu.addAction("发文件")
        delete_action = menu.addAction("删除联系人")
        
        action = menu.exec(self.online_list.mapToGlobal(pos))
        
        if action == message_action:
            self.chat_stack.setCurrentIndex(0)
        elif action == file_action:
            self._on_select_file()
    
    def _on_send_message(self):
        """发送消息"""
        text = self.chat_input.toPlainText().strip()
        if not text or not self.current_peer:
            return
        
        # 获取对方短ID
        peer_node_id = self.current_peer
        peer = self.hub.directory_service.get_profile(peer_node_id)
        if not peer:
            return
        
        asyncio.create_task(self._send_message_async(peer.short_id, text))
    
    async def _send_message_async(self, short_id: str, text: str):
        """异步发送消息"""
        try:
            msg_id = await self.hub.send_text(short_id, text)
            
            if msg_id:
                # 显示在聊天区
                self.chat_area.append(f"<span style='color: #00d4ff;'>我:</span> {text}")
                self.chat_input.clear()
            else:
                self.status_bar.showMessage("发送失败")
                
        except Exception as e:
            logger.error(f"Send message failed: {e}")
    
    def _on_select_file(self):
        """选择文件"""
        files, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        if files:
            self.selected_files = files
            self.file_list.clear()
            for f in files:
                from pathlib import Path
                self.file_list.addItem(Path(f).name)
    
    def _on_send_file(self):
        """发送文件"""
        if not hasattr(self, 'selected_files') or not self.selected_files:
            return
        
        if not self.current_peer:
            QMessageBox.warning(self, "请先连接")
            return
        
        # 获取对方短ID
        peer = self.hub.directory_service.get_profile(self.current_peer)
        if not peer:
            return
        
        self.file_progress.setVisible(True)
        self.file_progress.setValue(0)
        
        asyncio.create_task(self._send_file_async(peer.short_id, self.selected_files[0]))
    
    async def _send_file_async(self, short_id: str, file_path: str):
        """异步发送文件"""
        try:
            def update_progress(sent, total):
                pct = int(sent / total * 100)
                self.file_progress.setValue(pct)
            
            msg_id = await self.hub.send_file(short_id, file_path, update_progress)
            
            if msg_id:
                self.status_bar.showMessage("文件发送成功")
                self.file_progress.setVisible(False)
            else:
                self.status_bar.showMessage("文件发送失败")
                
        except Exception as e:
            logger.error(f"Send file failed: {e}")
            self.status_bar.showMessage(f"发送异常: {e}")
    
    def _on_voice_call(self):
        """开始语音通话"""
        if not self.current_peer:
            QMessageBox.warning(self, "请先连接")
            return
        
        self.voice_status.setText("通话中...")
        self.voice_call_btn.setVisible(False)
        self.voice_hangup_btn.setVisible(True)
        self.voice_duration.setVisible(True)
        
        # TODO: 实际启动语音通话
        self._start_voice_timer()
    
    def _on_voice_hangup(self):
        """挂断语音"""
        self.voice_status.setText("未连接")
        self.voice_call_btn.setVisible(True)
        self.voice_hangup_btn.setVisible(False)
        self.voice_duration.setVisible(False)
        self.voice_duration.setText("00:00:00")
    
    def _start_voice_timer(self):
        """语音通话计时器"""
        self.voice_seconds = 0
        self.voice_timer = QTimer()
        self.voice_timer.timeout.connect(self._update_voice_timer)
        self.voice_timer.start(1000)
    
    def _update_voice_timer(self):
        """更新语音计时"""
        self.voice_seconds += 1
        hours = self.voice_seconds // 3600
        minutes = (self.voice_seconds % 3600) // 60
        seconds = self.voice_seconds % 60
        self.voice_duration.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def _on_video_call(self):
        """开始视频通话"""
        if not self.current_peer:
            QMessageBox.warning(self, "请先连接")
            return
        
        self.video_status.setText("视频通话中...")
        self.video_call_btn.setVisible(False)
        self.video_hangup_btn.setVisible(True)
    
    def _on_video_hangup(self):
        """挂断视频"""
        self.video_status.setText("未连接")
        self.video_call_btn.setVisible(True)
        self.video_hangup_btn.setVisible(False)
    
    def _on_live_start(self):
        """开始直播"""
        self.live_start_btn.setVisible(False)
        self.live_stop_btn.setVisible(True)
        self.live_viewers.setText("观看人数: 1 (你)")
    
    def _on_live_stop(self):
        """停止直播"""
        self.live_start_btn.setVisible(True)
        self.live_stop_btn.setVisible(False)
        self.live_viewers.setText("观看人数: 0")
    
    def _on_refresh(self):
        """刷新"""
        self._update_display()
    
    def _on_add_contact(self):
        """添加联系人"""
        dialog = QDialog(self)
        dialog.setWindowTitle("添加联系人")
        layout = QVBoxLayout(dialog)
        
        id_input = QLineEdit()
        id_input.setPlaceholderText("对方短ID (纯数字)")
        layout.addWidget(QLabel("短ID:"))
        layout.addWidget(id_input)
        
        name_input = QLineEdit()
        name_input.setPlaceholderText("显示名称")
        layout.addWidget(QLabel("昵称:"))
        layout.addWidget(name_input)
        
        from PyQt6.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            short_id = id_input.text().strip()
            name = name_input.text().strip()
            
            if short_id and self.hub:
                self.hub.add_contact(short_id, name)
                self._on_refresh()
                QMessageBox.information(self, "成功", "联系人已添加")
