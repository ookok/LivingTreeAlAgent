"""
群组聊天窗口 - Group Chat Window

支持：
- 群组聊天
- 局域网用户自动发现
- 虚拟会议
- 文件同步
- 语音消息
"""

import sys
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent/client')

from typing import List, Dict, Optional, Any
from pathlib import Path
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QScrollArea, QFrame,
    QToolButton, QSplitter, QListWidget, QListWidgetItem,
    QMenu, QDialog, QGridLayout, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from client.src.business.function_knowledge import get_knowledge_base
from client.src.presentation.framework.minimal_ui_framework import (
    ColorScheme, Spacing, MinimalCard, UIComponentFactory
)
from client.src.presentation.components.voice_input import VoiceInputWidget
from client.src.presentation.components.loading_animation import LoadingSpinner, AnimationType


class LANUserDiscovery:
    """局域网用户发现"""
    
    def __init__(self):
        self._users = []
        self._discovering = False
    
    def start_discovery(self):
        """开始发现局域网用户"""
        self._discovering = True
        self._simulate_users()
    
    def stop_discovery(self):
        """停止发现"""
        self._discovering = False
    
    def _simulate_users(self):
        """模拟局域网用户"""
        self._users = [
            {"id": 1, "name": "张三", "online": True, "ip": "192.168.1.101"},
            {"id": 2, "name": "李四", "online": True, "ip": "192.168.1.102"},
            {"id": 3, "name": "王五", "online": False, "ip": "192.168.1.103"},
            {"id": 4, "name": "赵六", "online": True, "ip": "192.168.1.104"},
        ]
    
    def get_users(self) -> List[Dict]:
        """获取发现的用户"""
        return self._users


class GroupChatWindow(QWidget):
    """群组聊天窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lan_discovery = LANUserDiscovery()
        self._current_group = None
        self._groups = self._load_groups()
        self._messages = {}
        self._setup_ui()
    
    def _load_groups(self) -> List[Dict]:
        """加载群组列表"""
        return [
            {"id": 1, "name": "研发团队", "members": ["张三", "李四", "王五"], "unread": 3},
            {"id": 2, "name": "项目讨论", "members": ["张三", "赵六"], "unread": 0},
            {"id": 3, "name": "周末聚会", "members": ["李四", "王五"], "unread": 1},
            {"id": 4, "name": "技术分享", "members": ["张三", "李四", "王五", "赵六"], "unread": 0},
        ]
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #FAFAFA;
                font-family: 'Segoe UI', 'PingFang SC', sans-serif;
            }
        """)
        
        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 左侧面板 - 联系人/群组列表
        left_panel = QFrame()
        left_panel.setFixedWidth(280)
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-right: 1px solid #E5E7EB;
            }
        """)
        
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 左侧标题栏
        left_title = QFrame()
        left_title.setFixedHeight(56)
        left_title_layout = QHBoxLayout(left_title)
        left_title_layout.setContentsMargins(16, 0, 16, 0)
        
        title_label = UIComponentFactory.create_label(
            left_title, "💬 聊天", ColorScheme.TEXT_PRIMARY, 16
        )
        left_title_layout.addWidget(title_label)
        
        left_title_layout.addStretch()
        
        # 刷新按钮
        refresh_btn = QToolButton()
        refresh_btn.setText("🔄")
        refresh_btn.setToolTip("刷新联系人")
        refresh_btn.clicked.connect(self._refresh_contacts)
        left_title_layout.addWidget(refresh_btn)
        
        left_layout.addWidget(left_title)
        
        # 标签页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabWidget::tab {
                background-color: #FFFFFF;
                padding: 8px 16px;
                border-radius: 4px;
                margin-right: 4px;
            }
            QTabWidget::tab:selected {
                background-color: #E0F2FE;
            }
        """)
        
        # 群组标签
        groups_tab = QWidget()
        groups_layout = QVBoxLayout(groups_tab)
        
        self.groups_list = QListWidget()
        self.groups_list.setStyleSheet("""
            QListWidget {
                border: none;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #F3F4F6;
            }
            QListWidget::item:hover {
                background-color: #F9FAFB;
            }
        """)
        self.groups_list.itemClicked.connect(self._on_group_selected)
        
        for group in self._groups:
            item = QListWidgetItem(group["name"])
            if group["unread"] > 0:
                item.setToolTip(f"{group['unread']} 条未读消息")
            self.groups_list.addItem(item)
        
        groups_layout.addWidget(self.groups_list)
        tabs.addTab(groups_tab, "👥 群组")
        
        # 联系人标签
        contacts_tab = QWidget()
        contacts_layout = QVBoxLayout(contacts_tab)
        
        self.contacts_list = QListWidget()
        self.contacts_list.setStyleSheet("""
            QListWidget {
                border: none;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #F3F4F6;
            }
        """)
        contacts_layout.addWidget(self.contacts_list)
        
        # 局域网用户
        self.lan_btn = UIComponentFactory.create_button(
            contacts_tab, "🌐 扫描局域网", variant="secondary", size="sm"
        )
        self.lan_btn.clicked.connect(self._scan_lan)
        contacts_layout.addWidget(self.lan_btn)
        
        tabs.addTab(contacts_tab, "👤 联系人")
        
        left_layout.addWidget(tabs)
        main_layout.addWidget(left_panel)
        
        # 右侧面板 - 聊天区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 聊天标题栏
        chat_title = QFrame()
        chat_title.setFixedHeight(56)
        chat_title.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-bottom: 1px solid #E5E7EB;
            }
        """)
        
        chat_title_layout = QHBoxLayout(chat_title)
        chat_title_layout.setContentsMargins(16, 0, 16, 0)
        
        self.group_name_label = UIComponentFactory.create_label(
            chat_title, "选择一个群组开始聊天", ColorScheme.TEXT_PRIMARY, 16
        )
        chat_title_layout.addWidget(self.group_name_label)
        
        chat_title_layout.addStretch()
        
        # 会议按钮
        self.meeting_btn = UIComponentFactory.create_button(
            chat_title, "📹 开始会议", variant="primary", size="sm"
        )
        self.meeting_btn.clicked.connect(self._start_meeting)
        chat_title_layout.addWidget(self.meeting_btn)
        
        # 文件同步按钮
        sync_btn = QToolButton()
        sync_btn.setText("📁")
        sync_btn.setToolTip("文件同步")
        sync_btn.clicked.connect(self._sync_files)
        chat_title_layout.addWidget(sync_btn)
        
        # 更多按钮
        more_btn = QToolButton()
        more_btn.setText("⋮")
        chat_title_layout.addWidget(more_btn)
        
        right_layout.addWidget(chat_title)
        
        # 聊天区域
        self.chat_area = ChatArea()
        right_layout.addWidget(self.chat_area, 1)
        
        # 输入区域
        self.input_area = GroupChatInput()
        self.input_area.message_sent.connect(self._send_message)
        self.input_area.file_dropped.connect(self._on_files_dropped)
        
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-top: 1px solid #E5E7EB;
            }
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.addWidget(self.input_area)
        
        right_layout.addWidget(input_frame)
        
        main_layout.addWidget(right_panel, 1)
    
    def _on_group_selected(self, item: QListWidgetItem):
        """群组选中处理"""
        group_name = item.text()
        self.group_name_label.setText(group_name)
        self._current_group = group_name
        
        # 加载历史消息
        self._load_messages()
    
    def _load_messages(self):
        """加载消息"""
        sample_messages = [
            {"role": "system", "content": f"欢迎来到 {self._current_group} 群组"},
            {"role": "user", "content": "大家好！今天的会议几点开始？"},
            {"role": "assistant", "content": "下午2点开始，在会议室A"},
            {"role": "user", "content": "收到，谢谢！"},
        ]
        
        for msg in sample_messages:
            self.chat_area.add_message(msg["role"], msg["content"])
    
    def _send_message(self, text: str):
        """发送消息"""
        if text.startswith("/"):
            help_info = get_knowledge_base().get_command_help(text)
            if help_info:
                self.chat_area.add_message("assistant", help_info)
            else:
                all_commands = get_knowledge_base().format_all_command_help()
                self.chat_area.add_message("assistant", all_commands)
        else:
            self.chat_area.add_message("user", text)
            
            loading_frame = self.chat_area.add_loading_indicator()
            QTimer.singleShot(1500, lambda: self._simulate_response(loading_frame))
    
    def _simulate_response(self, loading_frame):
        """模拟回复"""
        self.chat_area.remove_loading_indicator(loading_frame)
        self.chat_area.add_message("assistant", "收到！我来处理...")
    
    def _on_files_dropped(self, files: List[str]):
        """文件拖放处理"""
        for file_path in files[:3]:
            if os.path.isfile(file_path):
                ext = Path(file_path).suffix.lower()
                if ext in ['.png', '.jpg', '.jpeg', '.gif']:
                    self.chat_area.add_message("user", f"📷 图片: {Path(file_path).name}")
                else:
                    self.chat_area.add_message("user", f"📄 文件: {Path(file_path).name}")
            elif os.path.isdir(file_path):
                self.chat_area.add_message("user", f"📂 文件夹: {Path(file_path).name}")
    
    def _scan_lan(self):
        """扫描局域网"""
        self._lan_discovery.start_discovery()
        users = self._lan_discovery.get_users()
        
        self.contacts_list.clear()
        for user in users:
            status = "●" if user["online"] else "○"
            color = "#10B981" if user["online"] else "#9CA3AF"
            item = QListWidgetItem(f"{status} {user['name']}")
            item.setToolTip(f"IP: {user['ip']}")
            self.contacts_list.addItem(item)
        
        self.lan_btn.setText("✅ 已扫描")
        QTimer.singleShot(3000, lambda: self.lan_btn.setText("🌐 扫描局域网"))
    
    def _start_meeting(self):
        """开始虚拟会议"""
        dialog = MeetingDialog(self)
        dialog.exec()
    
    def _sync_files(self):
        """文件同步"""
        dialog = FileSyncDialog(self)
        dialog.exec()
    
    def _refresh_contacts(self):
        """刷新联系人"""
        self._scan_lan()


class ChatArea(QWidget):
    """聊天区域"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #FAFAFA;
            }
        """)
        
        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(16, 16, 16, 16)
        self.messages_layout.addStretch()
        
        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area, 1)
    
    def add_message(self, role: str, content: str):
        bubble = MessageBubble(role, content)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        self._scroll_to_bottom()
    
    def add_loading_indicator(self):
        loading_frame = QFrame()
        loading_layout = QHBoxLayout(loading_frame)
        loading_layout.setContentsMargins(0, 16, 0, 16)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        spinner = LoadingSpinner()
        spinner.set_size(32)
        spinner.set_animation_type(AnimationType.SPINNER)
        
        loading_layout.addWidget(spinner)
        
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, loading_frame)
        self._scroll_to_bottom()
        
        return loading_frame
    
    def remove_loading_indicator(self, frame: QFrame):
        if frame:
            frame.deleteLater()
    
    def _scroll_to_bottom(self):
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))


class MessageBubble(QFrame):
    """消息气泡"""
    
    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.content = content
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        role_label = UIComponentFactory.create_label(
            self, "🧑 用户" if self.role == "user" else "🤖 助手",
            ColorScheme.TEXT_SECONDARY, 11
        )
        layout.addWidget(role_label)
        
        content_label = UIComponentFactory.create_label(
            self, self.content, ColorScheme.TEXT_PRIMARY, 14
        )
        content_label.setWordWrap(True)
        layout.addWidget(content_label)
        
        if self.role == "user":
            self.setStyleSheet("""
                QFrame {
                    background-color: #3B82F6;
                    border-radius: 16px;
                    margin-left: 40px;
                }
                QLabel {
                    color: white;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #FFFFFF;
                    border: 1px solid #E5E7EB;
                    border-radius: 16px;
                    margin-right: 40px;
                }
            """)


class GroupChatInput(QWidget):
    """群组聊天输入"""
    
    message_sent = pyqtSignal(str)
    file_dropped = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(Spacing.MD)
        
        # 文件拖拽
        self.drop_zone = QFrame()
        self.drop_zone.setFixedSize(44, 44)
        self.drop_zone.setStyleSheet("""
            QFrame {
                background-color: #FAFAFA;
                border: 2px dashed #E5E7EB;
                border-radius: 12px;
            }
        """)
        
        drop_layout = QVBoxLayout(self.drop_zone)
        drop_label = QLabel("📁")
        drop_label.setStyleSheet("font-size: 20px;")
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(drop_label)
        
        self.drop_zone.setAcceptDrops(True)
        self.drop_zone.dragEnterEvent = self._on_drag_enter
        self.drop_zone.dragLeaveEvent = self._on_drag_leave
        self.drop_zone.dropEvent = self._on_drop
        
        layout.addWidget(self.drop_zone)
        
        # 命令按钮
        cmd_btn = UIComponentFactory.create_button(
            self, "/", variant="secondary", size="sm"
        )
        cmd_btn.setFixedSize(44, 44)
        layout.addWidget(cmd_btn)
        
        # 输入框
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("输入消息...")
        self.input_field.setMaximumHeight(100)
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
                padding: 10px 16px;
                font-size: 14px;
            }
        """)
        self.input_field.keyPressEvent = self._on_key_press
        layout.addWidget(self.input_field, 1)
        
        # 语音输入
        self.voice_input = VoiceInputWidget()
        self.voice_input.setFixedSize(44, 44)
        layout.addWidget(self.voice_input)
        
        # 发送按钮
        self.send_btn = UIComponentFactory.create_button(
            self, "发送", variant="primary", size="md"
        )
        self.send_btn.clicked.connect(self._send_message)
        layout.addWidget(self.send_btn)
    
    def _on_key_press(self, event):
        from PyQt6.QtGui import QKeyEvent
        
        if isinstance(event, QKeyEvent):
            if event.key() in (16777221, 16777220) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send_message()
                return
        
        QTextEdit.keyPressEvent(self.input_field, event)
    
    def _send_message(self):
        text = self.input_field.toPlainText().strip()
        if text:
            self.message_sent.emit(text)
            self.input_field.clear()
    
    def _on_drag_enter(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_zone.setStyleSheet("""
                QFrame {
                    background-color: rgba(59, 130, 246, 0.1);
                    border: 2px dashed #3B82F6;
                    border-radius: 12px;
                }
            """)
    
    def _on_drag_leave(self, event: QDragEnterEvent):
        self.drop_zone.setStyleSheet("""
            QFrame {
                background-color: #FAFAFA;
                border: 2px dashed #E5E7EB;
                border-radius: 12px;
            }
        """)
    
    def _on_drop(self, event: QDropEvent):
        self.drop_zone.setStyleSheet("""
            QFrame {
                background-color: #FAFAFA;
                border: 2px dashed #E5E7EB;
                border-radius: 12px;
            }
        """)
        
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            files = [url.toLocalFile() for url in mime_data.urls() if url.isLocalFile()]
            if files:
                self.file_dropped.emit(files)
        
        event.acceptProposedAction()


class MeetingDialog(QDialog):
    """虚拟会议对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📹 虚拟会议")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # 会议信息
        info_card = MinimalCard()
        info_layout = info_card.layout()
        
        title_label = UIComponentFactory.create_label(
            info_card, "会议进行中", ColorScheme.TEXT_PRIMARY, 16
        )
        info_layout.addWidget(title_label)
        
        participants = ["张三", "李四", "王五"]
        for participant in participants:
            p_label = QLabel(f"● {participant}")
            p_label.setStyleSheet("font-size: 14px; color: #10B981;")
            info_layout.addWidget(p_label)
        
        layout.addWidget(info_card)
        
        # 视频区域
        video_frame = QFrame()
        video_frame.setStyleSheet("""
            QFrame {
                background-color: #1F2937;
                border-radius: 8px;
            }
        """)
        video_frame.setFixedHeight(200)
        
        video_layout = QVBoxLayout(video_frame)
        video_label = QLabel("🎥 视频会议区域")
        video_label.setStyleSheet("color: white; font-size: 16px;")
        video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        video_layout.addWidget(video_label)
        
        layout.addWidget(video_frame)
        
        # 控制按钮
        controls_layout = QHBoxLayout()
        
        mic_btn = UIComponentFactory.create_button(
            self, "🔇 静音", variant="secondary", size="sm"
        )
        controls_layout.addWidget(mic_btn)
        
        video_btn = UIComponentFactory.create_button(
            self, "📹 关闭摄像头", variant="secondary", size="sm"
        )
        controls_layout.addWidget(video_btn)
        
        screen_btn = UIComponentFactory.create_button(
            self, "🖥️ 屏幕共享", variant="secondary", size="sm"
        )
        controls_layout.addWidget(screen_btn)
        
        end_btn = UIComponentFactory.create_button(
            self, "🚪 结束会议", variant="error", size="sm"
        )
        end_btn.clicked.connect(self.close)
        controls_layout.addWidget(end_btn)
        
        layout.addLayout(controls_layout)


class FileSyncDialog(QDialog):
    """文件同步对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📁 文件同步")
        self.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(self)
        
        title_label = UIComponentFactory.create_label(
            self, "正在同步文件...", ColorScheme.TEXT_PRIMARY, 16
        )
        layout.addWidget(title_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                height: 8px;
                border-radius: 4px;
                background-color: #E5E7EB;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 同步列表
        sync_list = QListWidget()
        sync_list.addItems(["文档1.pdf", "图片2.jpg", "数据3.csv"])
        layout.addWidget(sync_list)
        
        # 模拟进度
        self._progress = 0
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_progress)
        self._timer.start(500)
    
    def _update_progress(self):
        self._progress += 10
        self.progress_bar.setValue(self._progress)
        
        if self._progress >= 100:
            self._timer.stop()


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    window = GroupChatWindow()
    window.setWindowTitle("群组聊天")
    window.resize(1000, 700)
    window.show()
    
    sys.exit(app.exec())