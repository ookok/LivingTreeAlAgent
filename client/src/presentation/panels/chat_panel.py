"""
聊天面板 — 中央主区域

负责：
  · 流式渲染 Markdown 消息（用 QTextBrowser + HTML 近似）
  · 工具调用状态块
  · 审批卡片
  · 消息输入框 + 发送/停止按钮
"""

import json
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QPushButton, QTextEdit, QFrame, QSizePolicy,
)
from PyQt6.QtGui import QKeyEvent, QTextCursor


# ── 工具调用状态块 ────────────────────────────────────────────────────

class ToolBlock(QFrame):
    def __init__(self, tool_name: str, args_str: str, parent=None):
        super().__init__(parent)
        self.tool_name = tool_name
        self.setObjectName("ToolBlock")
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        # 标题行
        header = QHBoxLayout()
        self.spinner = QLabel("⏳")
        self.name_lbl = QLabel(f"🔧  {tool_name}")
        self.name_lbl.setObjectName("ToolName")
        self.status_lbl = QLabel("运行中…")
        self.status_lbl.setStyleSheet("color:#f59e0b; font-size:11px;")
        header.addWidget(self.spinner)
        header.addWidget(self.name_lbl)
        header.addStretch()
        header.addWidget(self.status_lbl)
        layout.addLayout(header)

        # 参数
        if args_str and args_str != "{}":
            try:
                pretty = json.dumps(json.loads(args_str), ensure_ascii=False, indent=2)
            except Exception:
                pretty = args_str
            args_lbl = QLabel(pretty[:300])
            args_lbl.setObjectName("ToolArgs")
            args_lbl.setWordWrap(True)
            layout.addWidget(args_lbl)

        self.result_lbl = QLabel()
        self.result_lbl.setObjectName("ToolResult")
        self.result_lbl.setWordWrap(True)
        self.result_lbl.hide()
        layout.addWidget(self.result_lbl)

    def set_finished(self, result: str, success: bool):
        if success:
            self.spinner.setText("✅")
            self.status_lbl.setText("完成")
            self.status_lbl.setStyleSheet("color:#22c55e; font-size:11px;")
            self.setObjectName("ToolBlockSuccess")
        else:
            self.spinner.setText("❌")
            self.status_lbl.setText("失败")
            self.status_lbl.setStyleSheet("color:#ef4444; font-size:11px;")
            self.setObjectName("ToolBlockError")
        if result:
            self.result_lbl.setText(result[:300])
            self.result_lbl.show()
        self.setStyle(self.style())  # 刷新 QSS


# ── 审批卡片 ─────────────────────────────────────────────────────────

class ApprovalCard(QFrame):
    approved = pyqtSignal(str, bool)   # (task_id, approved)

    def __init__(self, task_id: str, tool_name: str, args_str: str, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.setObjectName("ApprovalCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        title = QLabel(f"⚠️  工具调用审批：{tool_name}")
        title.setObjectName("ApprovalTitle")
        layout.addWidget(title)

        try:
            pretty = json.dumps(json.loads(args_str), ensure_ascii=False, indent=2)
        except Exception:
            pretty = args_str
        args_lbl = QLabel(pretty[:400])
        args_lbl.setWordWrap(True)
        args_lbl.setStyleSheet("color:#aaa; font-size:12px; font-family: Consolas;")
        layout.addWidget(args_lbl)

        btns = QHBoxLayout()
        allow_btn = QPushButton("✓  允许")
        allow_btn.setObjectName("AllowButton")
        allow_btn.clicked.connect(lambda: self._respond(True))
        reject_btn = QPushButton("✗  拒绝")
        reject_btn.setObjectName("RejectButton")
        reject_btn.clicked.connect(lambda: self._respond(False))
        btns.addWidget(allow_btn)
        btns.addWidget(reject_btn)
        btns.addStretch()
        layout.addLayout(btns)

    def _respond(self, ok: bool):
        self.approved.emit(self.task_id, ok)
        # 替换为结果标签
        for i in reversed(range(self.layout().count())):
            w = self.layout().itemAt(i).widget()
            if w:
                w.hide()
        result = QLabel("✅ 已允许" if ok else "❌ 已拒绝")
        result.setStyleSheet("color:#888; font-size:12px;")
        self.layout().addWidget(result)


# ── 消息气泡 ─────────────────────────────────────────────────────────

class MessageBubble(QLabel):
    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setOpenExternalLinks(True)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if is_user:
            self.setStyleSheet(
                "background-color:#252550; border-radius:10px;"
                "padding:10px 14px; color:#e8e8e8;"
            )
        else:
            self.setStyleSheet("padding:4px 0; color:#e0e0e0;")
        self.setText(self._md_to_html(text))

    def append_text(self, delta: str):
        """追加流式 token（直接操作纯文本后重新渲染）"""
        self._raw = getattr(self, "_raw", "") + delta
        self.setText(self._md_to_html(self._raw))

    @staticmethod
    def _md_to_html(text: str) -> str:
        """极简 Markdown → HTML 转换（无外部依赖）"""
        import re, html as html_mod
        # 转义 HTML 特殊字符
        text = html_mod.escape(text)
        # 代码块
        text = re.sub(r'```(\w*)\n(.*?)```', lambda m:
            f'<pre style="background:#151515;padding:10px;border-radius:6px;'
            f'font-family:Consolas,monospace;font-size:12px;color:#ccc;'
            f'overflow-x:auto;white-space:pre-wrap;">{m.group(2)}</pre>',
            text, flags=re.DOTALL)
        # 行内代码
        text = re.sub(r'`([^`]+)`',
            r'<code style="background:#252525;padding:2px 5px;border-radius:3px;'
            r'font-family:Consolas,monospace;font-size:12px;color:#a0a0ff;">\1</code>',
            text)
        # 粗体
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        # 斜体
        text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
        # 标题
        text = re.sub(r'^### (.+)$', r'<h3 style="color:#a0a0ff;">\1</h3>', text, flags=re.M)
        text = re.sub(r'^## (.+)$',  r'<h2 style="color:#a0a0ff;">\1</h2>', text, flags=re.M)
        text = re.sub(r'^# (.+)$',   r'<h1 style="color:#c0c0ff;">\1</h1>', text, flags=re.M)
        # 换行
        text = text.replace('\n', '<br>')
        return text


# ── 聊天面板主体 ──────────────────────────────────────────────────────

class ChatPanel(QWidget):
    """
    信号
    ----
    send_requested(text: str)
    stop_requested()
    approval_responded(task_id: str, approved: bool)
    """

    send_requested     = pyqtSignal(str)
    stop_requested     = pyqtSignal()
    approval_responded = pyqtSignal(str, bool)
    switch_to_writing  = pyqtSignal(str)  # 切换到写作模式

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatPanel")
        self._current_assistant_bubble: MessageBubble | None = None
        self._active_tool_blocks: dict[str, ToolBlock] = {}  # tool_name -> block
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 标题栏 ────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet("background:#1a1a1a; border-bottom:1px solid #252525;")
        header.setFixedHeight(48)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 16, 0)
        self.title_lbl = QLabel("Hermes Agent")
        self.title_lbl.setObjectName("ChatTitle")
        h_layout.addWidget(self.title_lbl)
        h_layout.addStretch()
        # 当前模型标签
        self.model_lbl = QLabel()
        self.model_lbl.setStyleSheet("color:#555; font-size:11px;")
        h_layout.addWidget(self.model_lbl)
        root.addWidget(header)

        # ── 消息滚动区 ────────────────────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setObjectName("ChatScrollArea")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.msg_container = QWidget()
        self.msg_container.setObjectName("MessageContainer")
        self.msg_layout = QVBoxLayout(self.msg_container)
        self.msg_layout.setContentsMargins(20, 16, 20, 16)
        self.msg_layout.setSpacing(12)
        self.msg_layout.addStretch()

        # 欢迎占位
        self._welcome = QLabel(
            "向 Hermes 发送消息开始对话\n\n"
            "Hermes 可以帮你编写代码、分析文件、搜索网络…"
        )
        self._welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._welcome.setStyleSheet("color:#444; font-size:14px; padding:40px;")
        self._welcome.setWordWrap(True)
        self.msg_layout.addWidget(self._welcome)
        self.msg_layout.addStretch()

        self.scroll.setWidget(self.msg_container)
        root.addWidget(self.scroll, 1)

        # ── 输入区 ────────────────────────────────────────────────────
        input_area = QWidget()
        input_area.setObjectName("InputArea")
        input_area.setFixedHeight(110)
        ia_layout = QVBoxLayout(input_area)
        ia_layout.setContentsMargins(16, 10, 16, 12)
        ia_layout.setSpacing(8)

        # 文本框 + 按钮
        row = QHBoxLayout()
        row.setSpacing(8)

        self.input_box = _EnterTextEdit()
        self.input_box.setObjectName("MessageInput")
        self.input_box.setPlaceholderText("发送消息（Enter 发送，Shift+Enter 换行）")
        self.input_box.setFixedHeight(60)
        self.input_box.enter_pressed.connect(self._on_send)
        row.addWidget(self.input_box)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)
        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("SendButton")
        self.send_btn.setFixedWidth(72)
        self.send_btn.clicked.connect(self._on_send)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("StopButton")
        self.stop_btn.setFixedWidth(72)
        self.stop_btn.hide()
        self.stop_btn.clicked.connect(self.stop_requested)
        btn_col.addWidget(self.send_btn)
        btn_col.addWidget(self.stop_btn)
        btn_col.addStretch()
        row.addLayout(btn_col)

        ia_layout.addLayout(row)
        root.addWidget(input_area)

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def set_title(self, title: str):
        self.title_lbl.setText(title)

    def set_model_label(self, model: str):
        self.model_lbl.setText(model)

    def set_running(self, running: bool):
        self.send_btn.setVisible(not running)
        self.stop_btn.setVisible(running)
        self.input_box.setEnabled(not running)

    def add_user_message(self, text: str):
        self._hide_welcome()
        bubble = MessageBubble(text, is_user=True)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(bubble)
        self.msg_layout.insertLayout(self.msg_layout.count() - 1, row)
        self._current_assistant_bubble = None
        self._scroll_to_bottom()

    def begin_assistant_message(self):
        """开始一条新的助手消息（流式写入用）"""
        self._hide_welcome()
        bubble = MessageBubble("", is_user=False)
        bubble._raw = ""
        row = QHBoxLayout()
        row.addWidget(bubble)
        row.addStretch()
        self.msg_layout.insertLayout(self.msg_layout.count() - 1, row)
        self._current_assistant_bubble = bubble

    def append_token(self, token: str):
        """向当前助手气泡追加流式 token"""
        if self._current_assistant_bubble is None:
            self.begin_assistant_message()
        self._current_assistant_bubble.append_text(token)
        self._scroll_to_bottom()

    def add_tool_block(self, tool_name: str, args_str: str) -> ToolBlock:
        """插入工具调用块，返回引用以便后续更新"""
        self._hide_welcome()
        block = ToolBlock(tool_name, args_str)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, block)
        self._active_tool_blocks[tool_name] = block
        self._scroll_to_bottom()
        return block

    def finish_tool_block(self, tool_name: str, result: str, success: bool):
        block = self._active_tool_blocks.pop(tool_name, None)
        if block:
            block.set_finished(result, success)

    def add_approval_card(self, task_id: str, tool_name: str, args_str: str):
        card = ApprovalCard(task_id, tool_name, args_str)
        card.approved.connect(self.approval_responded)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, card)
        self._scroll_to_bottom()

    def clear_messages(self):
        # 清除所有动态插入的 item（保留最后两个 stretch）
        while self.msg_layout.count() > 2:
            item = self.msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
        self._welcome.show()
        self._current_assistant_bubble = None
        self._active_tool_blocks.clear()

    def add_error_message(self, text: str):
        lbl = QLabel(f"⚠️  {text}")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            "color:#ef4444; background:#2a0000; border:1px solid #7f1d1d;"
            "border-radius:6px; padding:10px 14px;"
        )
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, lbl)
        self._scroll_to_bottom()

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _on_send(self):
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        self.input_box.clear()
        self.send_requested.emit(text)

    def _scroll_to_bottom(self):
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def _hide_welcome(self):
        if self._welcome.isVisible():
            self._welcome.hide()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


# ── Enter 键支持的文本框 ──────────────────────────────────────────────

class _EnterTextEdit(QTextEdit):
    enter_pressed = pyqtSignal()

    def keyPressEvent(self, e: QKeyEvent):
        if (e.key() == Qt.Key.Key_Return and
                e.modifiers() == Qt.KeyboardModifier.NoModifier):
            self.enter_pressed.emit()
        else:
            super().keyPressEvent(e)
