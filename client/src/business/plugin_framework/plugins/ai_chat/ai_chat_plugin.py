"""
AI聊天插件

提供与AI对话的功能
支持多模型、多会话
"""

import uuid
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QComboBox,
    QLabel, QScrollArea, QToolBar,
    QSizePolicy, QSpacerItem,
)
from PyQt6.QtGui import QFont, QColor, QTextCursor

from business.plugin_framework.base_plugin import (
    BasePlugin, PluginManifest, PluginType,
    ViewPreference, ViewMode
)
from business.plugin_framework.event_bus import Event


@dataclass
class ChatMessage:
    """聊天消息"""
    id: str
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float
    model: str = ""


class ChatSession:
    """聊天会话"""

    def __init__(self, session_id: str, title: str = "新会话"):
        self.id = session_id
        self.title = title
        self.messages: List[ChatMessage] = []
        self.created_at = time.time()
        self.updated_at = time.time()
        self.model: str = "qwen2.5:0.5b"

    def add_message(self, role: str, content: str, model: str = "") -> ChatMessage:
        msg = ChatMessage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=time.time(),
            model=model or self.model,
        )
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "model": m.model,
                }
                for m in self.messages
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatSession':
        session = cls(data["id"], data["title"])
        session.created_at = data.get("created_at", time.time())
        session.updated_at = data.get("updated_at", time.time())
        session.model = data.get("model", "qwen2.5:0.5b")
        for msg_data in data.get("messages", []):
            session.messages.append(ChatMessage(**msg_data))
        return session


class AIChatPlugin(BasePlugin):
    """
    AI聊天插件

    提供：
    - 多会话管理
    - AI对话
    - 对话历史
    - 上下文管理
    """

    # 信号定义
    message_sent = pyqtSignal(str)  # session_id
    message_received = pyqtSignal(str, str)  # session_id, content
    session_changed = pyqtSignal(str)  # session_id

    def __init__(self, manifest: PluginManifest, framework):
        super().__init__(manifest, framework)
        self._sessions: Dict[str, ChatSession] = {}
        self._current_session_id: Optional[str] = None
        self._is_typing = False
        self._quick_commands: Dict[str, str] = {
            "/help": "显示帮助信息",
            "/clear": "清空当前会话",
            "/model": "切换模型",
            "/export": "导出对话记录",
        }

        # 注册事件
        self.register_event_handler("kb_reference", self._on_kb_reference)
        self.register_event_handler("im_message", self._on_im_message)

    def on_init(self) -> None:
        """初始化"""
        self.log_info("AI聊天插件初始化")

        # 创建默认会话
        self._create_new_session()

    def on_create_widget(self) -> QWidget:
        """创建主Widget"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 顶部：会话选择
        top_bar = self._create_top_bar()
        main_layout.addWidget(top_bar)

        # 中间：消息区域
        self._message_area = QScrollArea()
        self._message_area.setWidgetResizable(True)
        self._message_widget = QWidget()
        self._message_layout = QVBoxLayout(self._message_widget)
        self._message_layout.addStretch()
        self._message_area.setWidget(self._message_widget)
        main_layout.addWidget(self._message_area)

        # 底部：输入区域
        input_panel = self._create_input_panel()
        main_layout.addWidget(input_panel)

        return widget

    def _create_top_bar(self) -> QWidget:
        """创建顶部栏"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 会话列表
        self._session_list = QListWidget()
        self._session_list.currentRowChanged.connect(self._on_session_changed)
        layout.addWidget(self._session_list, 1)

        # 新建按钮
        new_btn = QPushButton("+ 新会话")
        new_btn.clicked.connect(self._on_new_session)
        layout.addWidget(new_btn)

        # 模型选择
        self._model_combo = QComboBox()
        self._model_combo.addItems([
            "qwen2.5:0.5b",
            "qwen2.5:1.5b",
            "llama3.2:1b",
            "mistral:7b",
        ])
        self._model_combo.currentTextChanged.connect(self._on_model_changed)
        layout.addWidget(QLabel("模型:"))
        layout.addWidget(self._model_combo)

        return widget

    def _create_input_panel(self) -> QWidget:
        """创建输入面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 快捷命令提示
        cmd_layout = QHBoxLayout()
        for cmd in self._quick_commands.keys():
            cmd_btn = QPushButton(cmd)
            cmd_btn.setMaximumWidth(80)
            cmd_btn.clicked.connect(lambda checked, c=cmd: self._on_quick_command(c))
            cmd_layout.addWidget(cmd_btn)
        cmd_layout.addStretch()
        layout.addLayout(cmd_layout)

        # 输入框
        input_layout = QHBoxLayout()
        self._input_box = QTextEdit()
        self._input_box.setMaximumHeight(80)
        self._input_box.setPlaceholderText("输入消息... (Ctrl+Enter 发送)")
        input_layout.addWidget(self._input_box, 1)

        # 发送按钮
        self._send_btn = QPushButton("发送")
        self._send_btn.clicked.connect(self._on_send_message)
        self._send_btn.setMinimumWidth(60)
        input_layout.addWidget(self._send_btn)

        layout.addLayout(input_layout)

        return widget

    def _create_message_bubble(self, message: ChatMessage) -> QWidget:
        """创建消息气泡"""
        bubble = QWidget()
        layout = QHBoxLayout(bubble)
        layout.setContentsMargins(8, 4, 8, 4)

        is_user = message.role == "user"

        # 头像
        avatar = QLabel("U" if is_user else "A")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            f"background-color: {'#5a5aff' if is_user else '#00d4aa'};"
            "color: white; border-radius: 16px; font-weight: bold;"
        )

        # 消息内容
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # 元信息
        meta_layout = QHBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)
        role_label = QLabel("你" if is_user else "AI")
        role_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        time_label = QLabel(time.strftime("%H:%M", time.localtime(message.timestamp)))
        time_label.setStyleSheet("color: #666; font-size: 11px;")
        meta_layout.addWidget(role_label)
        meta_layout.addStretch()
        meta_layout.addWidget(time_label)
        content_layout.addLayout(meta_layout)

        # 消息文本
        msg_label = QLabel(message.content)
        msg_label.setWordWrap(True)
        msg_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content_layout.addWidget(msg_label)

        # 布局
        if is_user:
            layout.addStretch()
            layout.addWidget(content_widget, 1)
            layout.addWidget(avatar)
        else:
            layout.addWidget(avatar)
            layout.addWidget(content_widget, 1)
            layout.addStretch()

        bubble.setStyleSheet(
            "QWidget { background-color: transparent; }"
            f"QWidget {{ background-color: {'#252550' if is_user else '#1e1e1e'}; "
            f"border-radius: 8px; padding: 8px; }}"
        )

        return bubble

    def _create_new_session(self) -> ChatSession:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session = ChatSession(session_id, f"会话 {len(self._sessions) + 1}")
        self._sessions[session_id] = session
        self._update_session_list()
        self._current_session_id = session_id
        return session

    def _update_session_list(self) -> None:
        """更新会话列表"""
        self._session_list.clear()
        for session in self._sessions.values():
            self._session_list.addItem(session.title)

    def _load_session(self, session_id: str) -> None:
        """加载会话"""
        if session_id not in self._sessions:
            return

        self._current_session_id = session_id
        session = self._sessions[session_id]

        # 清空消息显示
        while self._message_layout.count() > 1:
            item = self._message_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 加载消息
        for message in session.messages:
            bubble = self._create_message_bubble(message)
            self._message_layout.insertWidget(self._message_layout.count() - 1, bubble)

        # 滚动到底部
        QTimer.singleShot(10, self._scroll_to_bottom)

        self.session_changed.emit(session_id)

    def _scroll_to_bottom(self) -> None:
        """滚动到底部"""
        scroll_bar = self._message_area.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def _on_send_message(self) -> None:
        """发送消息"""
        content = self._input_box.toPlainText().strip()
        if not content or not self._current_session_id:
            return

        session = self._sessions[self._current_session_id]

        # 添加用户消息
        session.add_message("user", content)
        bubble = self._create_message_bubble(session.messages[-1])
        self._message_layout.insertWidget(self._message_layout.count() - 1, bubble)

        self._input_box.clear()
        self._scroll_to_bottom()
        self.message_sent.emit(self._current_session_id)

        # 模拟AI响应（实际应该调用LLM）
        self._generate_response(content)

    def _generate_response(self, user_input: str) -> None:
        """生成AI响应"""
        self._is_typing = True

        # 模拟思考
        session = self._sessions[self._current_session_id]
        response = self._get_ai_response(user_input, session)

        session.add_message("assistant", response)
        bubble = self._create_message_bubble(session.messages[-1])
        self._message_layout.insertWidget(self._message_layout.count() - 1, bubble)

        self._is_typing = False
        self._scroll_to_bottom()
        self.message_received.emit(self._current_session_id, response)

    def _get_ai_response(self, user_input: str, session: ChatSession) -> str:
        """获取AI响应（简化实现）"""
        # 检查快捷命令
        if user_input.startswith("/"):
            return self._handle_command(user_input)

        # 构建上下文
        context = "\n".join([
            f"{m.role}: {m.content}"
            for m in session.messages[-5:]
        ])

        # 简化响应（实际应该调用LLM）
        responses = [
            f"我理解了。你说的是：{user_input[:50]}...\n\n让我思考一下这个问题。",
            f"这是一个有趣的话题。关于「{user_input[:30]}」，我的看法是...",
            f"好的，我收到了你的消息。\n\n基于我们的对话，我建议你考虑以下几点...",
        ]
        return responses[len(session.messages) % len(responses)]

    def _handle_command(self, cmd: str) -> str:
        """处理快捷命令"""
        if cmd == "/help":
            return "可用命令：\n" + "\n".join(
                f"{k}: {v}" for k, v in self._quick_commands.items()
            )
        elif cmd == "/clear":
            self._load_session(self._current_session_id)
            return "会话已清空"
        elif cmd == "/model":
            return f"当前模型: {self._model_combo.currentText()}"
        elif cmd == "/export":
            return self._export_conversation()
        return "未知命令"

    def _export_conversation(self) -> str:
        """导出会话"""
        if not self._current_session_id:
            return "没有活动会话"

        session = self._sessions[self._current_session_id]
        lines = [f"# {session.title}\n"]
        for msg in session.messages:
            lines.append(f"**{msg.role}**: {msg.content}\n")
        return "\n".join(lines)

    def _on_quick_command(self, cmd: str) -> None:
        """执行快捷命令"""
        if cmd == "/clear" and self._current_session_id:
            # 清空消息
            session = self._sessions[self._current_session_id]
            session.messages.clear()
            self._load_session(self._current_session_id)
        else:
            self._input_box.setPlainText(cmd + " ")

    def _on_new_session(self) -> None:
        """新建会话"""
        session = self._create_new_session()
        self._load_session(session.id)

    def _on_session_changed(self, index: int) -> None:
        """会话切换"""
        if index < 0:
            return
        session_ids = list(self._sessions.keys())
        if index < len(session_ids):
            self._load_session(session_ids[index])

    def _on_model_changed(self, model: str) -> None:
        """模型切换"""
        if self._current_session_id:
            session = self._sessions[self._current_session_id]
            session.model = model
            self.log_info(f"切换模型: {model}")

    def _on_kb_reference(self, data: Dict[str, Any]) -> None:
        """处理知识库引用"""
        content = data.get("content", "")
        if content:
            self._input_box.setPlainText(f"参考知识库内容：\n{content}\n\n")
            self.log_info("收到知识库引用")

    def _on_im_message(self, data: Dict[str, Any]) -> None:
        """处理IM消息"""
        message = data.get("message", "")
        sender = data.get("sender", "")
        if message:
            self._input_box.setPlainText(f"来自 {sender} 的消息：\n{message}\n\n")
            self.log_info(f"收到IM消息 from {sender}")

    def on_activate(self) -> None:
        """激活"""
        self.log_info("AI聊天插件激活")

    def on_deactivate(self) -> None:
        """停用"""
        # 保存当前会话
        self._state["current_session"] = self._current_session_id
        self._state["sessions"] = [
            s.to_dict() for s in self._sessions.values()
        ]
        self.log_info("AI聊天插件停用")

    def on_save_state(self) -> Dict[str, Any]:
        """保存状态"""
        return {
            "current_session": self._current_session_id,
            "sessions": [s.to_dict() for s in self._sessions.values()],
        }

    def on_load_state(self, state: Dict[str, Any]) -> None:
        """加载状态"""
        self._sessions.clear()
        for session_data in state.get("sessions", []):
            session = ChatSession.from_dict(session_data)
            self._sessions[session.id] = session

        self._update_session_list()

        if state.get("current_session"):
            self._load_session(state["current_session"])


# 插件清单
MANIFEST = PluginManifest(
    id="ai_chat",
    name="AI聊天",
    version="1.0.0",
    author="LivingTree Team",
    description="与AI对话，支持多会话、多模型切换",
    plugin_type=PluginType.CHAT,
    view_preference=ViewPreference(
        preferred_mode=ViewMode.DOCKABLE,
        dock_area="right",
        default_width=350,
        default_height=500,
        min_width=280,
        min_height=200,
    ),
    icon=":/icons/chat.svg",
    lazy_load=True,
)
