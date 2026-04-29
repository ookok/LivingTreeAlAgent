"""
聊天面板 — 中央主区域

负责：
  · 流式渲染 Markdown 消息（用 QTextBrowser + HTML 近似）
  · 工具调用状态块
  · 审批卡片
  · 消息输入框 + 发送/停止按钮
  · 配置缺失检测与提示
  · 主动需求澄清引导 (ConversationalClarifier)
"""

import json
import time
from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QPushButton, QTextEdit, QFrame, QSizePolicy,
)
from PyQt6.QtGui import QKeyEvent, QTextCursor


# ── 配置提示横幅 ────────────────────────────────────────────────────

def _create_config_hint_banner(parent) -> tuple:
    """
    创建配置提示横幅及其管理器

    Returns:
        (banner, manager)
    """
    try:
        from ui.config_hint_banner import ConfigHintBanner, ConfigHintManager
        banner = ConfigHintBanner(parent)
        manager = ConfigHintManager(banner)
        return banner, manager
    except ImportError:
        return None, None


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
    config_hint_requested(link_path: str) - 用户点击了配置链接
    switch_to_writing(content: str) - 请求切换到写作模式
    """

    send_requested     = pyqtSignal(str)
    stop_requested     = pyqtSignal()
    approval_responded = pyqtSignal(str, bool)
    config_hint_requested = pyqtSignal(str)  # link_path
    switch_to_writing = pyqtSignal(str)  # content - 请求切换到写作模式

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatPanel")
        self._current_assistant_bubble: MessageBubble | None = None
        self._active_tool_blocks: dict[str, ToolBlock] = {}  # tool_name -> block
        self._config_banner = None
        self._config_manager = None

        # 需求澄清引导
        self._clarifier = None
        self._clarify_card: Optional['ClarificationCard'] = None
        self._pending_clarify = False

        self._build_ui()
        self._init_clarifier()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 标题栏 ────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet("""
            background:#0F172A;
            border-bottom:1px solid #1E293B;
        """)
        header.setFixedHeight(56)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 16, 0)
        self.title_lbl = QLabel("💬 Hermes Assistant")
        self.title_lbl.setObjectName("ChatTitle")
        self.title_lbl.setStyleSheet("""
            color: #F1F5F9;
            font-size: 16px;
            font-weight: 600;
        """)
        h_layout.addWidget(self.title_lbl)
        h_layout.addStretch()
        # 当前模型标签
        self.model_lbl = QLabel()
        self.model_lbl.setStyleSheet("""
            color: #64748B;
            font-size: 12px;
            background: #1E293B;
            padding: 4px 12px;
            border-radius: 12px;
        """)
        h_layout.addWidget(self.model_lbl)
        root.addWidget(header)

        # ── 消息滚动区 ────────────────────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setObjectName("ChatScrollArea")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea {
                background: #0F172A;
                border: none;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background-color: #334155;
                border-radius: 4px;
                min-height: 40px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #475569;
            }
        """)

        self.msg_container = QWidget()
        self.msg_container.setObjectName("MessageContainer")
        self.msg_layout = QVBoxLayout(self.msg_container)
        self.msg_layout.setContentsMargins(24, 20, 24, 20)
        self.msg_layout.setSpacing(16)
        
        # Agent状态显示区域
        self.agent_status_area = QWidget()
        self.agent_status_layout = QVBoxLayout(self.agent_status_area)
        self.agent_status_layout.setSpacing(8)
        self.msg_layout.addWidget(self.agent_status_area)
        
        # 欢迎占位
        self._welcome = QLabel(
            "向 Hermes 发送消息开始对话\n\n"
            "Hermes 可以帮你编写代码、分析文件、搜索网络…"
        )
        self._welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._welcome.setStyleSheet("""
            color: #64748B;
            font-size: 15px;
            padding: 60px 40px;
            background: transparent;
        """)
        self._welcome.setWordWrap(True)
        self.msg_layout.addWidget(self._welcome)
        self.msg_layout.addStretch()

        self.scroll.setWidget(self.msg_container)
        root.addWidget(self.scroll, 1)

        # ── 配置提示横幅 ──────────────────────────────────────────────
        self._config_banner, self._config_manager = _create_config_hint_banner(self)
        if self._config_banner:
            self._config_banner.config_clicked.connect(self.config_hint_requested)
            root.addWidget(self._config_banner)

        # ── 输入区 ────────────────────────────────────────────────────
        input_area = QWidget()
        input_area.setObjectName("InputArea")
        input_area.setFixedHeight(120)
        input_area.setStyleSheet("""
            QWidget#InputArea {
                background: #1E293B;
                border-top: 1px solid #334155;
            }
        """)
        ia_layout = QVBoxLayout(input_area)
        ia_layout.setContentsMargins(16, 12, 16, 16)
        ia_layout.setSpacing(10)

        # 文本框 + 按钮
        row = QHBoxLayout()
        row.setSpacing(12)

        self.input_box = _EnterTextEdit()
        self.input_box.setObjectName("MessageInput")
        self.input_box.setPlaceholderText("输入消息... (Enter 发送，Shift+Enter 换行)")
        self.input_box.setFixedHeight(64)
        self.input_box.setStyleSheet("""
            QTextEdit {
                background: #0F172A;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 12px 16px;
                color: #F1F5F9;
                font-size: 14px;
            }
            QTextEdit:focus {
                border-color: #3B82F6;
                outline: none;
            }
            QTextEdit::placeholder {
                color: #64748B;
            }
        """)
        self.input_box.enter_pressed.connect(self._on_send)
        row.addWidget(self.input_box)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(8)
        btn_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # 垂直居中对齐
        
        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("SendButton")
        self.send_btn.setFixedWidth(80)
        self.send_btn.setFixedHeight(36)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
        """)
        self.send_btn.clicked.connect(self._on_send)
        
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("StopButton")
        self.stop_btn.setFixedWidth(80)
        self.stop_btn.setFixedHeight(36)
        self.stop_btn.hide()
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #DC2626;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_requested)
        
        btn_col.addWidget(self.send_btn)
        btn_col.addWidget(self.stop_btn)
        row.addLayout(btn_col)

        ia_layout.addLayout(row)
        root.addWidget(input_area)

    def show_agent_loading(self, message="Hermes Agent 正在处理..."):
        """显示Agent加载过程"""
        self._hide_welcome()
        
        # 清除之前的状态
        for i in reversed(range(self.agent_status_layout.count())):
            widget = self.agent_status_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 创建加载状态面板
        loading_panel = QWidget()
        loading_panel.setStyleSheet("""
            background: #1E293B;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 12px 16px;
        """)
        loading_layout = QHBoxLayout(loading_panel)
        loading_layout.setSpacing(12)
        
        # 加载动画
        spinner = QLabel("⏳")
        spinner.setStyleSheet("font-size: 14px;")
        
        # 状态文本
        status_text = QLabel(message)
        status_text.setStyleSheet("color: #94A3B8; font-size: 14px;")
        
        loading_layout.addWidget(spinner)
        loading_layout.addWidget(status_text)
        loading_layout.addStretch()
        
        self.agent_status_layout.addWidget(loading_panel)
        self._scroll_to_bottom()
        
        return loading_panel

    def show_model_inference(self, model_name, prompt="正在调用模型..."):
        """显示模型调用过程"""
        self._hide_welcome()
        
        # 清除之前的状态
        for i in reversed(range(self.agent_status_layout.count())):
            widget = self.agent_status_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 创建模型调用面板
        inference_panel = QWidget()
        inference_panel.setStyleSheet("""
            background: #1E293B;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 12px 16px;
        """)
        inference_layout = QVBoxLayout(inference_panel)
        inference_layout.setSpacing(8)
        
        # 模型信息
        model_info = QLabel(f"🤖 模型: {model_name}")
        model_info.setStyleSheet("color: #3B82F6; font-size: 14px; font-weight: 500;")
        
        # 调用状态
        status_layout = QHBoxLayout()
        status_layout.setSpacing(8)
        
        spinner = QLabel("🔄")
        spinner.setStyleSheet("font-size: 14px;")
        
        status_text = QLabel(prompt)
        status_text.setStyleSheet("color: #94A3B8; font-size: 13px;")
        
        status_layout.addWidget(spinner)
        status_layout.addWidget(status_text)
        status_layout.addStretch()
        
        inference_layout.addWidget(model_info)
        inference_layout.addLayout(status_layout)
        
        self.agent_status_layout.addWidget(inference_panel)
        self._scroll_to_bottom()
        
        return inference_panel

    def clear_agent_status(self):
        """清除Agent状态显示"""
        for i in reversed(range(self.agent_status_layout.count())):
            widget = self.agent_status_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

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

        # 记录交互并检查是否需要引导
        self._record_and_check_clarify("user", text)

    # ------------------------------------------------------------------
    # 需求澄清引导
    # ------------------------------------------------------------------

    def _init_clarifier(self):
        """初始化需求澄清器"""
        try:
            from core.conversational_clarifier import get_conversational_clarifier
            self._clarifier = get_conversational_clarifier()
        except ImportError:
            self._clarifier = None

    def _record_and_check_clarify(self, role: str, content: str):
        """记录交互并检查是否需要引导"""
        if not self._clarifier:
            return

        # 记录交互
        self._clarifier.record_interaction(role, content)

        # 检查是否应该触发引导
        if role == "user" and self._clarifier.should_prompt():
            # 延迟显示，让消息先渲染
            QTimer.singleShot(500, self._show_clarify_prompt)

    def _show_clarify_prompt(self):
        """显示需求澄清引导卡片"""
        if not self._clarifier or self._clarify_card:
            return

        prompt = self._clarifier.get_prompt()

        # 创建引导卡片
        from ui.clarification_card import ClarificationCard
        self._clarify_card = ClarificationCard(
            message=prompt.message,
            options=prompt.options
        )
        self._clarify_card.option_selected.connect(self._on_clarify_option)
        self._clarify_card.dismissed.connect(self._on_clarify_dismissed)

        # 插入到消息区域
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, self._clarify_card)
        self._scroll_to_bottom()

    def _on_clarify_option(self, option: str):
        """处理用户选择的澄清选项"""
        if not self._clarifier:
            return

        self._clarify_card = None
        self._clarifier.on_user_response(option)

        # 根据选项处理
        if option in ["1", "好，帮我梳理需求", "是", "好"]:
            # 用户同意，启动头脑风暴
            self._pending_clarify = True
            # 在聊天区域显示提示
            self._show_clarify_progress()
        elif option in ["2", "不用，继续当前话题"]:
            # 用户拒绝，暂时不显示
            pass
        elif option in ["3", "以后再说"]:
            # 用户选择关闭，禁用
            self._show_disable_notice()

    def _on_clarify_dismissed(self):
        """用户关闭了引导卡片"""
        self._clarify_card = None

    def _show_clarify_progress(self):
        """显示头脑风暴进行中的提示"""
        lbl = QLabel(
            "🎯 已进入需求澄清模式，正在准备提问...\n"
            "请稍候，我会逐步引导你明确需求。"
        )
        lbl.setStyleSheet("""
            color: #60a5fa;
            background: #1e3a5f;
            border: 1px solid #3b82f6;
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 13px;
        """)
        lbl.setWordWrap(True)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, lbl)
        self._scroll_to_bottom()

        # 发出信号，让主窗口打开头脑风暴面板
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1000, lambda: self.window().show_brainstorm_panel())

    def _show_disable_notice(self):
        """显示已禁用提示"""
        lbl = QLabel(
            "💡 需求澄清引导已临时关闭。\n"
            "你可以在「🎯 头脑风暴」面板中重新启用。"
        )
        lbl.setStyleSheet("""
            color: #9ca3af;
            background: #2a2a2a;
            border-radius: 6px;
            padding: 10px 14px;
            font-size: 12px;
        """)
        lbl.setWordWrap(True)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, lbl)
        self._scroll_to_bottom()

    def add_assistant_message(self, text: str):
        """添加助手消息（完整文本）"""
        self._hide_welcome()
        bubble = MessageBubble(text, is_user=False)
        row = QHBoxLayout()
        row.addWidget(bubble)
        row.addStretch()
        self.msg_layout.insertLayout(self.msg_layout.count() - 1, row)
        self._scroll_to_bottom()

        # 记录助手消息
        if self._clarifier:
            self._clarifier.record_interaction("assistant", text)

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
        # 清除配置提示
        if self._config_manager:
            self._config_manager.clear()

    def show_initialization_progress(self, steps):
        """显示Hermes Agent初始化过程"""
        self._hide_welcome()
        
        # 创建初始化进度面板
        init_panel = QWidget()
        init_panel.setStyleSheet("""
            background: #1E293B;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 20px;
        """)
        init_layout = QVBoxLayout(init_panel)
        
        # 标题
        title = QLabel("🧠 Hermes Agent 初始化")
        title.setStyleSheet("""
            color: #3B82F6;
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 16px;
        """)
        init_layout.addWidget(title)
        
        # 进度条
        progress_bar = QProgressBar()
        progress_bar.setMaximum(len(steps))
        progress_bar.setStyleSheet("""
            QProgressBar {
                background: #0F172A;
                border: 1px solid #334155;
                border-radius: 6px;
                height: 8px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #3B82F6;
                border-radius: 4px;
            }
        """)
        init_layout.addWidget(progress_bar)
        
        # 状态标签
        status_label = QLabel("正在初始化...")
        status_label.setStyleSheet("""
            color: #94A3B8;
            font-size: 14px;
            margin-top: 12px;
        """)
        init_layout.addWidget(status_label)
        
        # 步骤列表
        steps_widget = QWidget()
        steps_layout = QVBoxLayout(steps_widget)
        steps_layout.setSpacing(8)
        
        step_labels = []
        for step in steps:
            step_label = QLabel(f"⏳ {step}")
            step_label.setStyleSheet("color: #64748B; font-size: 13px;")
            steps_layout.addWidget(step_label)
            step_labels.append(step_label)
        
        init_layout.addWidget(steps_widget)
        
        # 插入到消息容器
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, init_panel)
        self._scroll_to_bottom()
        
        # 模拟初始化过程
        def update_progress(index=0):
            if index < len(steps):
                step = steps[index]
                progress_bar.setValue(index + 1)
                status_label.setText(f"正在 {step}...")
                step_labels[index].setText(f"✅ {step}")
                step_labels[index].setStyleSheet("color: #10B981; font-size: 13px;")
                
                # 继续下一个步骤
                QTimer.singleShot(800, lambda: update_progress(index + 1))
            else:
                # 初始化完成
                status_label.setText("初始化完成！")
                status_label.setStyleSheet("color: #10B981; font-size: 14px; font-weight: 500;")
                
                # 2秒后移除初始化面板
                QTimer.singleShot(2000, lambda: init_panel.deleteLater())
        
        # 开始初始化动画
        QTimer.singleShot(100, lambda: update_progress(0))

    def add_error_message(self, text: str, check_config: bool = True):
        """
        添加错误消息

        Args:
            text: 错误文本
            check_config: 是否检测配置缺失并显示提示（默认 True）
        """
        lbl = QLabel(f"⚠️  {text}")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            "color:#ef4444; background:#2a0000; border:1px solid #7f1d1d;"
            "border-radius:6px; padding:10px 14px;"
        )
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, lbl)
        self._scroll_to_bottom()

        # 检测配置缺失并显示提示
        if check_config and self._config_manager:
            self._config_manager.check_and_show(text)

    def check_config_from_result(self, result_text: str):
        """
        检测结果文本中的配置缺失并显示提示

        用于在 Agent 执行完成后检测结果中是否包含配置缺失信息

        Args:
            result_text: 结果文本
        """
        if self._config_manager:
            self._config_manager.check_and_show(result_text)

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
