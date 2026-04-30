"""
IM客户端插件

提供即时通讯功能
支持私聊、群聊、文件传输
"""

import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QDateTime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QToolBar,
    QLabel, QStackedWidget, QSplitter,
    QTreeWidget, QTreeWidgetItem, QMenu,
    QSystemTrayIcon, QInputDialog,
    QFileDialog, QScrollArea,
)
from PyQt6.QtGui import QAction, QIcon, QFont
from PyQt6.QtGui import QPainter, QColor

from business.plugin_framework.base_plugin import (
    BasePlugin, PluginManifest, PluginType,
    ViewPreference, ViewMode
)
from business.plugin_framework.event_bus import Event


@dataclass
class Contact:
    """联系人"""
    id: str
    name: str
    avatar: str = ""
    status: str = "offline"  # online, away, busy, offline
    last_seen: float = 0
    groups: List[str] = field(default_factory=list)


@dataclass
class Group:
    """群组"""
    id: str
    name: str
    members: List[str] = field(default_factory=list)
    avatar: str = ""


@dataclass
class Message:
    """消息"""
    id: str
    chat_type: str  # "private", "group"
    sender_id: str
    receiver_id: str  # 对方ID或群ID
    content: str
    timestamp: float
    status: str = "sent"  # sending, sent, delivered, read


class IMClientPlugin(BasePlugin):
    """
    IM客户端插件

    提供：
    - 联系人管理
    - 私聊和群聊
    - 消息状态追踪
    - 文件传输（模拟）
    """

    # 信号定义
    message_received = pyqtSignal(str, str)  # from_user_id, content
    contact_status_changed = pyqtSignal(str, str)  # contact_id, status
    unread_changed = pyqtSignal(int)

    def __init__(self, manifest: PluginManifest, framework):
        super().__init__(manifest, framework)
        self._contacts: Dict[str, Contact] = {}
        self._groups: Dict[str, Group] = {}
        self._conversations: Dict[str, List[Message]] = {}  # chat_key -> messages
        self._current_chat: Optional[str] = None
        self._unread_count: Dict[str, int] = {}  # chat_key -> unread count
        self._total_unread = 0

        # 注册事件
        self.register_event_handler("chat.share", self._on_chat_share)
        self.register_event_handler("kb.link", self._on_kb_link)

    def on_init(self) -> None:
        """初始化"""
        self.log_info("IM客户端插件初始化")

        # 加载示例数据
        self._load_sample_data()

    def on_create_widget(self) -> QWidget:
        """创建主Widget"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 左侧：联系人/群组列表
        left_panel = self._create_contact_panel()
        layout.addWidget(left_panel, 1)

        # 右侧：聊天区域
        right_panel = self._create_chat_panel()
        layout.addWidget(right_panel, 3)

        return widget

    def _create_contact_panel(self) -> QWidget:
        """创建联系人面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 搜索框
        search_layout = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索联系人...")
        self._search_input.textChanged.connect(self._on_search_contact)
        search_layout.addWidget(self._search_input)
        layout.addLayout(search_layout)

        # 标签切换
        self._tab_widget = QWidget()
        tab_layout = QHBoxLayout(self._tab_widget)
        tab_layout.setContentsMargins(0, 4, 0, 4)
        self._contact_tab_btn = QPushButton("联系人")
        self._contact_tab_btn.setCheckable(True)
        self._contact_tab_btn.setChecked(True)
        self._contact_tab_btn.clicked.connect(lambda: self._switch_tab("contacts"))
        self._group_tab_btn = QPushButton("群组")
        self._group_tab_btn.setCheckable(True)
        self._group_tab_btn.clicked.connect(lambda: self._switch_tab("groups"))
        tab_layout.addWidget(self._contact_tab_btn)
        tab_layout.addWidget(self._group_tab_btn)
        self._tab_widget.stack = QStackedWidget()
        layout.addWidget(self._tab_widget)

        # 联系人列表
        self._contact_list = QListWidget()
        self._contact_list.itemClicked.connect(self._on_contact_clicked)
        self._contact_list.itemDoubleClicked.connect(self._on_contact_double_clicked)
        layout.addWidget(self._contact_list)

        # 群组列表
        self._group_list = QListWidget()
        self._group_list.itemClicked.connect(self._on_group_clicked)
        self._group_list.itemDoubleClicked.connect(self._on_group_double_clicked)
        self._group_list.setVisible(False)
        layout.addWidget(self._group_list)

        # 底部操作
        bottom_layout = QHBoxLayout()
        add_contact_btn = QPushButton("+")
        add_contact_btn.clicked.connect(self._on_add_contact)
        bottom_layout.addWidget(add_contact_btn)
        bottom_layout.addStretch()
        layout.addLayout(bottom_layout)

        self._populate_contacts()

        return widget

    def _create_chat_panel(self) -> QWidget:
        """创建聊天面板"""
        self._chat_widget = QWidget()
        layout = QVBoxLayout(self._chat_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 聊天头部
        self._chat_header = QWidget()
        header_layout = QHBoxLayout(self._chat_header)
        self._chat_title = QLabel("选择聊天")
        self._chat_status = QLabel("")
        header_layout.addWidget(self._chat_title, 1)
        header_layout.addWidget(self._chat_status)
        self._chat_info_btn = QPushButton("详情")
        self._chat_info_btn.setVisible(False)
        header_layout.addWidget(self._chat_info_btn)
        layout.addWidget(self._chat_header)

        # 消息区域
        self._message_area = QScrollArea()
        self._message_area.setWidgetResizable(True)
        self._message_widget = QWidget()
        self._message_layout = QVBoxLayout(self._message_widget)
        self._message_layout.addStretch()
        self._message_area.setWidget(self._message_widget)
        layout.addWidget(self._message_area)

        # 输入区域
        input_panel = self._create_input_panel()
        layout.addWidget(input_panel)

        return self._chat_widget

    def _create_input_panel(self) -> QWidget:
        """创建输入面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QToolBar()
        file_action = QPyAction("📎", self)
        file_action.triggered.connect(self._on_send_file)
        toolbar.addAction(file_action)
        emoji_action = QPyAction("😀", self)
        toolbar.addAction(emoji_action)
        kb_action = QPyAction("📚", self)
        kb_action.triggered.connect(self._on_insert_kb)
        toolbar.addAction(kb_action)
        layout.addLayout(toolbar)

        # 输入框
        input_layout = QHBoxLayout()
        self._chat_input = QTextEdit()
        self._chat_input.setMaximumHeight(80)
        self._chat_input.setPlaceholderText("输入消息...")
        input_layout.addWidget(self._chat_input, 1)

        # 发送按钮
        self._send_btn = QPushButton("发送")
        self._send_btn.clicked.connect(self._on_send_message)
        input_layout.addWidget(self._send_btn)

        layout.addLayout(input_layout)

        return widget

    def _load_sample_data(self) -> None:
        """加载示例数据"""
        # 联系人
        contacts = [
            Contact("c1", "Alice", status="online"),
            Contact("c2", "Bob", status="away"),
            Contact("c3", "Charlie", status="offline"),
            Contact("c4", "David", status="online"),
        ]
        for c in contacts:
            self._contacts[c.id] = c

        # 群组
        groups = [
            Group("g1", "开发团队", members=["c1", "c2", "c3"]),
            Group("g2", "产品讨论", members=["c1", "c4"]),
        ]
        for g in groups:
            self._groups[g.id] = g

        # 示例消息
        self._conversations["private_c1"] = [
            Message("m1", "private", "c1", "c1", "你好！", time.time() - 3600),
            Message("m2", "private", "me", "c1", "你好 Alice", time.time() - 3500),
            Message("m3", "private", "c1", "c1", "有空讨论下项目吗？", time.time() - 3400),
        ]

    def _populate_contacts(self) -> None:
        """填充联系人列表"""
        self._contact_list.clear()
        for contact in self._contacts.values():
            item = QListWidgetItem()
            item.setText(f"{contact.name} ({contact.status})")
            item.setData(Qt.ItemDataRole.UserRole, contact.id)

            # 设置颜色
            if contact.status == "online":
                item.setForeground(QColor("#4caf50"))
            elif contact.status == "away":
                item.setForeground(QColor("#ff9800"))
            else:
                item.setForeground(QColor("#a0a0a0"))

            self._contact_list.addItem(item)

    def _populate_groups(self) -> None:
        """填充群组列表"""
        self._group_list.clear()
        for group in self._groups.values():
            item = QListWidgetItem()
            item.setText(f"{group.name} ({len(group.members)}人)")
            item.setData(Qt.ItemDataRole.UserRole, group.id)
            self._group_list.addItem(item)

    def _switch_tab(self, tab: str) -> None:
        """切换标签"""
        if tab == "contacts":
            self._contact_list.setVisible(True)
            self._group_list.setVisible(False)
            self._contact_tab_btn.setChecked(True)
            self._group_tab_btn.setChecked(False)
        else:
            self._contact_list.setVisible(False)
            self._group_list.setVisible(True)
            self._contact_tab_btn.setChecked(False)
            self._group_tab_btn.setChecked(True)

    def _get_chat_key(self, chat_type: str, peer_id: str) -> str:
        """获取聊天键"""
        if chat_type == "private":
            return f"private_{peer_id}"
        else:
            return f"group_{peer_id}"

    def _load_conversation(self, chat_type: str, peer_id: str) -> None:
        """加载会话"""
        chat_key = self._get_chat_key(chat_type, peer_id)
        self._current_chat = chat_key

        # 清除未读
        if chat_key in self._unread_count:
            old_unread = self._unread_count.get(chat_key, 0)
            if old_unread > 0:
                self._unread_count[chat_key] = 0
                self._total_unread -= old_unread
                self.unread_changed.emit(self._total_unread)

        # 更新标题
        if chat_type == "private":
            contact = self._contacts.get(peer_id)
            self._chat_title.setText(contact.name if contact else "私聊")
            self._chat_status.setText(contact.status if contact else "")
        else:
            group = self._groups.get(peer_id)
            self._chat_title.setText(group.name if group else "群聊")
            self._chat_status.setText(f"{len(group.members)}人" if group else "")

        self._chat_info_btn.setVisible(True)

        # 清空并加载消息
        while self._message_layout.count() > 1:
            item = self._message_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        messages = self._conversations.get(chat_key, [])
        for msg in messages:
            self._add_message_widget(msg)

        # 滚动到底部
        QTimer.singleShot(10, self._scroll_to_bottom)

    def _add_message_widget(self, message: Message) -> None:
        """添加消息组件"""
        bubble = QWidget()
        layout = QHBoxLayout(bubble)
        layout.setContentsMargins(8, 4, 8, 4)

        is_me = message.sender_id == "me"

        # 头像
        avatar = QLabel(message.sender_id[0].upper() if message.sender_id != "me" else "M")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            f"background-color: {'#5a5aff' if is_me else '#00d4aa'};"
            "color: white; border-radius: 16px; font-weight: bold;"
        )

        # 消息内容
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # 元信息
        meta_layout = QHBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)
        sender_label = QLabel("我" if is_me else self._contacts.get(message.sender_id, Contact("", "Unknown")).name)
        sender_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        time_label = QLabel(time.strftime("%H:%M", time.localtime(message.timestamp)))
        time_label.setStyleSheet("color: #666; font-size: 11px;")
        meta_layout.addWidget(sender_label)
        meta_layout.addStretch()
        meta_layout.addWidget(time_label)
        content_layout.addLayout(meta_layout)

        # 消息文本
        msg_label = QLabel(message.content)
        msg_label.setWordWrap(True)
        msg_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content_layout.addWidget(msg_label)

        # 布局
        if is_me:
            layout.addStretch()
            layout.addWidget(content_widget, 1)
            layout.addWidget(avatar)
        else:
            layout.addWidget(avatar)
            layout.addWidget(content_widget, 1)
            layout.addStretch()

        bubble.setStyleSheet(
            "QWidget { background-color: transparent; }"
            f"QWidget {{ background-color: {'#252550' if is_me else '#1e1e1e'}; "
            "border-radius: 8px; padding: 8px; }}"
        )

        self._message_layout.insertWidget(self._message_layout.count() - 1, bubble)

    def _scroll_to_bottom(self) -> None:
        """滚动到底部"""
        scroll_bar = self._message_area.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def _on_contact_clicked(self, item: QListWidgetItem) -> None:
        """联系人点击"""
        contact_id = item.data(Qt.ItemDataRole.UserRole)
        self._load_conversation("private", contact_id)

    def _on_contact_double_clicked(self, item: QListWidgetItem) -> None:
        """联系人双击"""
        pass  # 可以打开独立窗口

    def _on_group_clicked(self, item: QListWidgetItem) -> None:
        """群组点击"""
        group_id = item.data(Qt.ItemDataRole.UserRole)
        self._load_conversation("group", group_id)

    def _on_group_double_clicked(self, item: QListWidgetItem) -> None:
        """群组双击"""
        pass  # 可以打开独立窗口

    def _on_search_contact(self, text: str) -> None:
        """搜索联系人"""
        for i in range(self._contact_list.count()):
            item = self._contact_list.item(i)
            contact_id = item.data(Qt.ItemDataRole.UserRole)
            contact = self._contacts.get(contact_id)
            if contact:
                item.setHidden(text.lower() not in contact.name.lower())

    def _on_send_message(self) -> None:
        """发送消息"""
        content = self._chat_input.toPlainText().strip()
        if not content or not self._current_chat:
            return

        # 解析当前聊天
        parts = self._current_chat.split("_", 1)
        chat_type = parts[0]
        peer_id = parts[1] if len(parts) > 1 else ""

        # 创建消息
        message = Message(
            id=str(uuid.uuid4()),
            chat_type=chat_type,
            sender_id="me",
            receiver_id=peer_id,
            content=content,
            timestamp=time.time(),
            status="sent"
        )

        # 保存消息
        if self._current_chat not in self._conversations:
            self._conversations[self._current_chat] = []
        self._conversations[self._current_chat].append(message)

        # 显示消息
        self._add_message_widget(message)
        self._chat_input.clear()
        self._scroll_to_bottom()

        # 发布事件（供其他插件使用）
        self.framework.event_bus.publish(Event(
            type="im_message_sent",
            data={
                "chat_type": chat_type,
                "receiver_id": peer_id,
                "content": content,
            },
            source=self.plugin_id,
        ))

    def _on_add_contact(self) -> None:
        """添加联系人"""
        name, ok = QInputDialog.getText(self.widget, "添加联系人", "联系人名称:")
        if ok and name:
            contact_id = str(uuid.uuid4())
            contact = Contact(contact_id, name)
            self._contacts[contact_id] = contact
            self._populate_contacts()

    def _on_send_file(self) -> None:
        """发送文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.widget, "选择文件", "", "所有文件 (*.*)"
        )
        if file_path:
            self._chat_input.append(f"[文件] {file_path.split('/')[-1]}")

    def _on_insert_kb(self) -> None:
        """插入知识库内容"""
        # 可以触发知识库选择对话框
        self.log_info("插入知识库内容")

    def _on_chat_share(self, data: Dict[str, Any]) -> None:
        """处理聊天分享"""
        content = data.get("content", "")
        if content and self._current_chat:
            self._chat_input.append(content)

    def _on_kb_link(self, data: Dict[str, Any]) -> None:
        """处理知识库链接"""
        link = data.get("link", "")
        title = data.get("title", "")
        if link:
            self._chat_input.append(f"[{title}]({link})")

    def on_activate(self) -> None:
        """激活"""
        self.log_info("IM客户端插件激活")

    def on_deactivate(self) -> None:
        """停用"""
        self._state["conversations"] = {
            k: [
                {
                    "id": m.id,
                    "chat_type": m.chat_type,
                    "sender_id": m.sender_id,
                    "receiver_id": m.receiver_id,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "status": m.status,
                }
                for m in messages
            ]
            for k, messages in self._conversations.items()
        }
        self.log_info("IM客户端插件停用")

    def on_save_state(self) -> Dict[str, Any]:
        """保存状态"""
        return {
            "conversations": self._state.get("conversations", {}),
            "contacts": [
                {
                    "id": c.id,
                    "name": c.name,
                    "status": c.status,
                }
                for c in self._contacts.values()
            ],
            "groups": [
                {
                    "id": g.id,
                    "name": g.name,
                    "members": g.members,
                }
                for g in self._groups.values()
            ],
        }


# 插件清单
MANIFEST = PluginManifest(
    id="im_client",
    name="IM客户端",
    version="1.0.0",
    author="Hermes Team",
    description="即时通讯，支持私聊、群聊、文件传输",
    plugin_type=PluginType.COMMUNICATION,
    view_preference=ViewPreference(
        preferred_mode=ViewMode.STANDALONE,
        default_width=800,
        default_height=600,
        min_width=400,
        min_height=300,
    ),
    icon=":/icons/im.svg",
    lazy_load=True,
    single_instance=False,  # 允许多实例
)
