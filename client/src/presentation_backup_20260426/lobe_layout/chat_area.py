"""
聊天工作区组件 (ChatAreaWidget)

Lobe 风格的中央聊天区域
"""

from __future__ import annotations

import time
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel,
    QTextEdit, QPushButton, QFrame,
    QScrollArea, QSizePolicy, QApplication
)
from PyQt6.QtGui import QFont, QColor, QPalette, QPainter, QLinearGradient, QBrush

from .lobe_models import ChatMessage, LobeSession


class ChatBubbleWidget(QFrame):
    """聊天气泡组件"""

    def __init__(self, message: ChatMessage, parent=None):
        super().__init__(parent)
        self.message = message
        self._setup_ui()

    def _setup_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # 角色标签和时间
        header_layout = QHBoxLayout()

        role_label = QLabel("👤" if self.message.role == "user" else "🤖")
        role_label.setFont(QFont("Microsoft YaHei", 9))
        role_label.setStyleSheet("color: #666;")

        time_label = QLabel(time.strftime("%H:%M", time.localtime(self.message.timestamp)))
        time_label.setFont(QFont("Microsoft YaHei", 8))
        time_label.setStyleSheet("color: #999;")

        header_layout.addWidget(role_label)
        header_layout.addStretch()
        header_layout.addWidget(time_label)

        layout.addLayout(header_layout)

        # 消息内容
        content_label = QLabel(self.message.content)
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.RichText)
        content_label.setFont(QFont("Microsoft YaHei", 10))

        # 根据角色设置样式
        if self.message.role == "user":
            content_label.setStyleSheet("""
                background: #e3f2fd;
                border-radius: 12px;
                padding: 8px 12px;
            """)
        else:
            content_label.setStyleSheet("""
                background: #f5f5f5;
                border-radius: 12px;
                padding: 8px 12px;
            """)

        layout.addWidget(content_label)

        # 状态指示（如果正在发送）
        if self.message.status == "sending":
            status_label = QLabel("⏳ 发送中...")
            status_label.setStyleSheet("color: #1976d2; font-size: 9px;")
            layout.addWidget(status_label)

        # 使用的技能标签
        if self.message.skill_used:
            skills_layout = QHBoxLayout()
            skills_layout.addStretch()
            for skill in self.message.skill_used:
                skill_tag = QLabel(f"🔧 {skill}")
                skill_tag.setStyleSheet("""
                    background: #fff3e0;
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-size: 9px;
                    color: #e65100;
                """)
                skills_layout.addWidget(skill_tag)
            layout.addLayout(skills_layout)


class StatusFlowBar(QWidget):
    """状态流条组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps = []
        self._current_step = -1
        self._setup_ui()

    def _setup_ui(self):
        """初始化UI"""
        self.setMaximumHeight(32)
        self.setMinimumHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(8)

        self.step_labels: list[QLabel] = []
        self.step_icons = [
            ("⚡", "本地路由"),
            ("🌐", "P2P/搜索"),
            ("🧠", "AI推理"),
            ("✍️", "生成中"),
            ("✅", "完成"),
        ]

        for icon, label in self.step_icons:
            step_layout = QHBoxLayout()
            step_layout.setSpacing(4)

            icon_label = QLabel(icon)
            icon_label.setFont(QFont("Microsoft YaHei", 10))
            step_layout.addWidget(icon_label)

            text_label = QLabel(label)
            text_label.setFont(QFont("Microsoft YaHei", 9))
            text_label.setStyleSheet("color: #999;")
            step_layout.addWidget(text_label)

            # 分隔符
            if icon != self.step_icons[-1][0]:
                sep = QLabel("›")
                sep.setStyleSheet("color: #ccc;")
                step_layout.addWidget(sep)

            step_layout.addStretch()

            self.step_labels.append(text_label)
            layout.addLayout(step_layout)

        # Token 计数器
        layout.addStretch()
        self.token_label = QLabel("Tokens: 0")
        self.token_label.setFont(QFont("Consolas", 9))
        self.token_label.setStyleSheet("color: #666;")
        layout.addWidget(self.token_label)

        # 模型信息
        self.model_label = QLabel("Model: --")
        self.model_label.setFont(QFont("Microsoft YaHei", 9))
        self.model_label.setStyleSheet("color: #999;")
        layout.addWidget(self.model_label)

    def set_step_status(self, step_index: int, status: str):
        """
        设置步骤状态

        Args:
            step_index: 步骤索引
            status: idle/running/success/error
        """
        if step_index < 0 or step_index >= len(self.step_labels):
            return

        label = self.step_labels[step_index]

        if status == "running":
            label.setStyleSheet("color: #1976d2; font-weight: bold;")
        elif status == "success":
            label.setStyleSheet("color: #388e3c;")
        elif status == "error":
            label.setStyleSheet("color: #d32f2f;")
        else:
            label.setStyleSheet("color: #999;")

    def set_all_idle(self):
        """设置所有步骤为空闲"""
        for label in self.step_labels:
            label.setStyleSheet("color: #999;")

    def set_flow(self, steps: list[str]):
        """
        设置当前流程

        Args:
            steps: 当前经过的步骤列表，如 ["local", "p2p", "ai", "done"]
        """
        step_map = {
            "local": 0,
            "p2p": 1,
            "search": 1,
            "ai": 2,
            "thinking": 2,
            "writing": 3,
            "done": 4,
            "success": 4,
        }

        self.set_all_idle()
        for step in steps:
            idx = step_map.get(step, -1)
            if idx >= 0:
                self.set_step_status(idx, "running")
                self._current_step = idx

        # 最后一步标记为成功
        if steps:
            last_step = steps[-1]
            last_idx = step_map.get(last_step, -1)
            if last_idx >= 0 and last_step in ("done", "success"):
                self.set_step_status(last_idx, "success")

    def update_tokens(self, count: int, model: str = ""):
        """更新 Token 计数"""
        self.token_label.setText(f"Tokens: {count}")
        if model:
            self.model_label.setText(f"Model: {model}")


class ChatAreaWidget(QWidget):
    """
    聊天工作区组件

    功能：
    - 消息列表展示
    - 输入框
    - 状态流条
    - Token 计数
    """

    # 信号
    send_message = pyqtSignal(str)  # 发送消息
    message_added = pyqtSignal(ChatMessage)  # 消息添加

    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages: list[ChatMessage] = []
        self._setup_ui()

    def _setup_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 消息列表（可滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("border: none; background: transparent;")

        self.message_container = QWidget()
        self.message_layout = QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(16, 16, 16, 16)
        self.message_layout.setSpacing(12)
        self.message_layout.addStretch()

        scroll.setWidget(self.message_container)
        layout.addWidget(scroll, stretch=1)

        # 状态流条
        self.status_flow = StatusFlowBar()
        self.status_flow.setStyleSheet("""
            background: #fafafa;
            border-top: 1px solid #e0e0e0;
        """)
        layout.addWidget(self.status_flow)

        # 输入区
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            background: #fff;
            border-top: 1px solid #e0e0e0;
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(16, 12, 16, 12)
        input_layout.setSpacing(8)

        # 输入框
        self.input_text = QTextEdit()
        self.input_text.setMaximumHeight(100)
        self.input_text.setPlaceholderText("输入消息... (Shift+Enter 换行，Enter 发送)")
        self.input_text.setFont(QFont("Microsoft YaHei", 11))
        self.input_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px 12px;
                background: #fff;
            }
            QTextEdit:focus {
                border-color: #1976d2;
            }
        """)
        self.input_text.setAcceptRichText(False)
        input_layout.addWidget(self.input_text)

        # 发送按钮行
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(80, 32)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #1976d2;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1565c0;
            }
            QPushButton:disabled {
                background: #bdbdbd;
            }
        """)
        self.send_btn.clicked.connect(self._on_send)
        btn_layout.addWidget(self.send_btn)

        input_layout.addLayout(btn_layout)
        layout.addWidget(input_frame)

        # 设置消息发送快捷键
        self.input_text.installEventFilter(self)

    def eventFilter(self, obj, event):
        """事件过滤器，处理键盘事件"""
        if obj == self.input_text and event.type() == 36:  # Enter key
            if not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._on_send()
                return True
        return super().eventFilter(obj, event)

    def _on_send(self):
        """发送消息"""
        content = self.input_text.toPlainText().strip()
        if not content:
            return

        self.send_message.emit(content)
        self.input_text.clear()

    def add_message(self, message: ChatMessage):
        """添加消息"""
        self._messages.append(message)

        # 创建气泡
        bubble = ChatBubbleWidget(message)

        # 插入到布局（倒数第二的位置，-1 是 stretch）
        self.message_layout.insertWidget(
            self.message_layout.count() - 1,
            bubble
        )

        self.message_added.emit(message)

        # 滚动到底部
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        """滚动到底部"""
        scroll = self.findChild(QScrollArea)
        if scroll:
            scroll.verticalScrollBar().setValue(
                scroll.verticalScrollBar().maximum()
            )

    def clear_messages(self):
        """清空消息"""
        self._messages.clear()

        # 移除所有气泡
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()

    def set_session(self, session: LobeSession):
        """设置会话"""
        self.clear_messages()

        # 加载历史消息
        for msg in session.messages:
            self.add_message(msg)

        # 显示系统提示
        if session.config and session.config.system_prompt:
            sys_msg = ChatMessage(
                role="system",
                content=f"📋 {session.config.system_prompt}"
            )
            self.add_message(sys_msg)

    def set_status_flow(self, steps: list[str]):
        """设置状态流"""
        self.status_flow.set_flow(steps)

    def update_tokens(self, count: int, model: str = ""):
        """更新 Token 计数"""
        self.status_flow.update_tokens(count, model)

    def get_input_text(self) -> str:
        """获取输入文本"""
        return self.input_text.toPlainText()
