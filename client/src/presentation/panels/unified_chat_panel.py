"""
统一聊天面板 - 整合原有业务逻辑和现代化UI设计

结合:
1. chat_hub.py - 统一聊天核心调度器
2. chat_panel.py - 原有聊天面板UI
3. 新设计的现代化组件
"""

import json
import time
import asyncio
from typing import Optional, Dict, Any, List
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QPushButton, QTextEdit, QFrame, QSizePolicy,
    QToolButton, QSplitter, QScrollBar, QProgressBar
)
from PyQt6.QtGui import QKeyEvent, QTextCursor

# 导入业务逻辑
try:
    from business.unified_chat.chat_hub import get_chat_hub, ChatHub
    from business.unified_chat.models import (
        UnifiedMessage, MessageType, MessageStatus
    )
    from business.smart_config_detector import get_config_detector
except ImportError:
    from src.business.unified_chat.chat_hub import get_chat_hub, ChatHub
    from src.business.unified_chat.models import (
        UnifiedMessage, MessageType, MessageStatus
    )
    from src.business.smart_config_detector import get_config_detector

# 导入新的现代化组件
from ..components.smart_message_bubble import MessageBubble as ModernMessageBubble
from ..components.context_panel import ContextPanel
from ..components.smart_input_field import SmartInputField
from ..components.modern_dialogs import ConfirmationDialog, ToastNotification
from ..components.inline_config_card import InlineConfigCard
from ..components.config_sprite import ConfigSprite
from ..components.config_success_banner import ConfigSuccessBanner


class ToolBlock(QFrame):
    """工具调用状态块"""
    
    def __init__(self, tool_name: str, args_str: str, parent=None):
        super().__init__(parent)
        self.tool_name = tool_name
        self.setObjectName("ToolBlock")
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

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
        self.setStyle(self.style())


class ApprovalCard(QFrame):
    """审批卡片"""
    
    approved = pyqtSignal(str, bool)

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
        for i in reversed(range(self.layout().count())):
            w = self.layout().itemAt(i).widget()
            if w:
                w.hide()
        result = QLabel("✅ 已允许" if ok else "❌ 已拒绝")
        result.setStyleSheet("color:#888; font-size:12px;")
        self.layout().addWidget(result)


class UnifiedChatPanel(QWidget):
    """
    统一聊天面板 - 整合原有业务逻辑和现代化UI设计
    
    信号:
        send_requested(text: str)
        stop_requested()
        approval_responded(task_id: str, approved: bool)
        config_hint_requested(link_path: str)
        switch_to_writing(content: str)
        config_completed(config_type: str, config_data: dict)
    """

    send_requested = pyqtSignal(str)
    stop_requested = pyqtSignal()
    approval_responded = pyqtSignal(str, bool)
    config_hint_requested = pyqtSignal(str)
    switch_to_writing = pyqtSignal(str)
    config_completed = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UnifiedChatPanel")
        
        # 业务逻辑层
        self._chat_hub = get_chat_hub()
        self._chat_hub.add_ui_callback(self._on_chat_event)
        
        # 配置检测系统
        self._config_detector = get_config_detector()
        
        # UI状态
        self._current_assistant_bubble = None
        self._active_tool_blocks: dict[str, ToolBlock] = {}
        self._config_banner = None
        self._config_manager = None
        self._active_config_cards: dict[str, InlineConfigCard] = {}
        
        # 配置精灵
        self._config_sprite = None
        
        # 需求澄清引导
        self._clarifier = None
        self._clarify_card = None
        self._pending_clarify = False
        
        # 任务分解系统
        self._task_decompose_manager = None
        self._task_decompose_visible = False
        
        # 消息缓存
        self._message_bubbles = []
        
        self._build_ui()
        self._init_clarifier()
        self._init_config_sprite()

    def _build_ui(self):
        """构建现代化UI"""
        # 主布局 - 聊天区域 + 上下文面板
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: #e5e7eb;
                width: 2px;
            }
        """)
        
        # 聊天区域
        chat_area = QWidget()
        chat_layout = QVBoxLayout(chat_area)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)
        
        # 标题栏
        header = QWidget()
        header.setStyleSheet("""
            background:#1e293b;
            border-bottom:1px solid #334155;
        """)
        header.setFixedHeight(56)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 16, 0)
        
        self.title_lbl = QLabel("💬 Hermes Assistant")
        self.title_lbl.setStyleSheet("""
            color: #f1f5f9;
            font-size: 16px;
            font-weight: 600;
        """)
        h_layout.addWidget(self.title_lbl)
        h_layout.addStretch()
        
        self.model_lbl = QLabel()
        self.model_lbl.setStyleSheet("""
            color: #64748b;
            font-size: 12px;
            background: #0f172a;
            padding: 4px 12px;
            border-radius: 12px;
        """)
        h_layout.addWidget(self.model_lbl)
        chat_layout.addWidget(header)
        
        # 消息滚动区
        self.scroll = QScrollArea()
        self.scroll.setObjectName("ChatScrollArea")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea {
                background: #ffffff;
                border: none;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background-color: #cbd5e1;
                border-radius: 4px;
                min-height: 40px;
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
            color: #64748b;
            font-size: 15px;
            padding: 60px 40px;
            background: transparent;
        """)
        self._welcome.setWordWrap(True)
        self.msg_layout.addWidget(self._welcome)
        self.msg_layout.addStretch()
        
        self.scroll.setWidget(self.msg_container)
        chat_layout.addWidget(self.scroll, 1)
        
        # 任务分解面板
        self.task_decompose_panel = None
        try:
            from .task_decompose_panel import TaskDecomposePanel
            self.task_decompose_panel = TaskDecomposePanel()
            self.task_decompose_panel.hide()
            chat_layout.addWidget(self.task_decompose_panel)
        except ImportError:
            self.task_decompose_panel = None
        
        # 输入区
        input_area = QWidget()
        input_area.setObjectName("InputArea")
        input_area.setFixedHeight(120)
        input_area.setStyleSheet("""
            QWidget#InputArea {
                background: #f8fafc;
                border-top: 1px solid #e2e8f0;
            }
        """)
        ia_layout = QVBoxLayout(input_area)
        ia_layout.setContentsMargins(16, 12, 16, 16)
        ia_layout.setSpacing(10)
        
        # 使用新的智能输入框
        self.input_field = SmartInputField()
        self.input_field.send_message.connect(self._on_send)
        ia_layout.addWidget(self.input_field)
        
        chat_layout.addWidget(input_area)
        
        splitter.addWidget(chat_area)
        
        # 上下文面板
        self.context_panel = ContextPanel()
        self.context_panel.action_triggered.connect(self._on_context_action)
        splitter.addWidget(self.context_panel)
        
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(splitter)

    def _init_clarifier(self):
        """初始化需求澄清器"""
        try:
            from business.conversational_clarifier import get_conversational_clarifier
            self._clarifier = get_conversational_clarifier()
        except ImportError:
            self._clarifier = None

    def _init_config_sprite(self):
        """初始化配置精灵"""
        self._config_sprite = ConfigSprite()

    def _on_chat_event(self, event: str, data: Any):
        """处理聊天事件"""
        if event == "message_received":
            self._on_message_received(data)
        elif event == "message_sent":
            self._on_message_sent(data)
        elif event == "status_changed":
            self._on_status_changed(data)

    def _on_message_received(self, message: UnifiedMessage):
        """处理收到的消息"""
        if message.type == MessageType.TEXT:
            self.add_assistant_message(message.content)
        elif message.type in [MessageType.IMAGE, MessageType.FILE]:
            self.add_file_message(message)

    def _on_message_sent(self, message: UnifiedMessage):
        """处理发送的消息"""
        if message.type == MessageType.TEXT:
            self.add_user_message(message.content)

    def _on_status_changed(self, status_info: Dict[str, str]):
        """处理状态变化"""
        self.model_lbl.setText(status_info.get("model", "Unknown"))

    def _on_send(self, text: str):
        """发送消息"""
        if not text.strip():
            return
        
        # 检测配置需求
        asyncio.create_task(self._detect_and_guide_config(text))
        
        # 调用业务逻辑发送消息
        asyncio.create_task(self._chat_hub.send_text_message(
            session_id="default",
            text=text
        ))
        
        # 本地显示用户消息
        self.add_user_message(text)
    
    async def _detect_and_guide_config(self, message: str):
        """检测消息中的配置需求并引导用户配置"""
        detected_configs = await self._config_detector.detect_config_needs(message)
        
        for config_info in detected_configs:
            config_key = config_info["key"]
            
            # 检查是否已配置
            if self._is_configured(config_key):
                continue
            
            # 显示配置精灵提示
            if self._config_sprite:
                hint_msg = f"需要配置 {config_info['name']} 才能使用此功能哦！"
                self._config_sprite.show_hint(hint_msg)
            
            # 显示内联配置卡片
            self._show_inline_config_card(config_key)

    def _on_context_action(self, action_name: str):
        """处理上下文面板操作"""
        if action_name == "搜索":
            self.input_field.set_placeholder("输入搜索内容...")
        elif action_name == "代码生成":
            self.input_field.set_placeholder("描述你想要生成的代码...")
        elif action_name == "文件处理":
            self.input_field.set_placeholder("描述文件处理需求...")

    def set_title(self, title: str):
        """设置标题"""
        self.title_lbl.setText(title)

    def set_model_label(self, model: str):
        """设置模型标签"""
        self.model_lbl.setText(model)

    def add_user_message(self, text: str):
        """添加用户消息"""
        self._hide_welcome()
        bubble = ModernMessageBubble()
        bubble.set_message(text, "user", 1.0)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(bubble)
        self.msg_layout.insertLayout(self.msg_layout.count() - 1, row)
        self._current_assistant_bubble = None
        self._scroll_to_bottom()

        self._record_and_check_clarify("user", text)

    def add_assistant_message(self, text: str):
        """添加助手消息"""
        self._hide_welcome()
        bubble = ModernMessageBubble()
        bubble.set_message(text, "ai", 0.95)
        row = QHBoxLayout()
        row.addWidget(bubble)
        row.addStretch()
        self.msg_layout.insertLayout(self.msg_layout.count() - 1, row)
        self._scroll_to_bottom()

        if self._clarifier:
            self._clarifier.record_interaction("assistant", text)

    def add_file_message(self, message: UnifiedMessage):
        """添加文件消息"""
        self._hide_welcome()
        
        if message.type == MessageType.IMAGE:
            from ..components.file_operations import ImageMessageBubble
            bubble = ImageMessageBubble()
            bubble.set_image(message.meta.path, message.content)
        else:
            bubble = ModernMessageBubble()
            bubble.set_message(message.content, "ai", 0.9)
        
        row = QHBoxLayout()
        row.addWidget(bubble)
        row.addStretch()
        self.msg_layout.insertLayout(self.msg_layout.count() - 1, row)
        self._scroll_to_bottom()

    def begin_assistant_message(self):
        """开始流式助手消息"""
        self._hide_welcome()
        bubble = ModernMessageBubble()
        bubble.set_message("", "ai", 0.95)
        bubble.start_typing_animation()
        row = QHBoxLayout()
        row.addWidget(bubble)
        row.addStretch()
        self.msg_layout.insertLayout(self.msg_layout.count() - 1, row)
        self._current_assistant_bubble = bubble

    def append_token(self, token: str):
        """追加流式token"""
        if self._current_assistant_bubble is None:
            self.begin_assistant_message()
        self._current_assistant_bubble.stop_typing_animation()
        current_text = self._current_assistant_bubble._content_label.text()
        self._current_assistant_bubble.set_message(current_text + token, "ai", 0.95)
        self._scroll_to_bottom()

    def add_tool_block(self, tool_name: str, args_str: str) -> ToolBlock:
        """添加工具调用块"""
        self._hide_welcome()
        block = ToolBlock(tool_name, args_str)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, block)
        self._active_tool_blocks[tool_name] = block
        self._scroll_to_bottom()
        return block

    def finish_tool_block(self, tool_name: str, result: str, success: bool):
        """完成工具调用"""
        block = self._active_tool_blocks.pop(tool_name, None)
        if block:
            block.set_finished(result, success)

    def add_approval_card(self, task_id: str, tool_name: str, args_str: str):
        """添加审批卡片"""
        card = ApprovalCard(task_id, tool_name, args_str)
        card.approved.connect(self.approval_responded)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, card)
        self._scroll_to_bottom()

    def clear_messages(self):
        """清除所有消息"""
        while self.msg_layout.count() > 2:
            item = self.msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
        self._welcome.show()
        self._current_assistant_bubble = None
        self._active_tool_blocks.clear()

    def show_agent_loading(self, message="Hermes Agent 正在处理..."):
        """显示加载状态"""
        self._hide_welcome()
        
        for i in reversed(range(self.agent_status_layout.count())):
            widget = self.agent_status_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        loading_panel = QWidget()
        loading_panel.setStyleSheet("""
            background: #f1f5f9;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px 16px;
        """)
        loading_layout = QHBoxLayout(loading_panel)
        loading_layout.setSpacing(12)
        
        spinner = QLabel("⏳")
        spinner.setStyleSheet("font-size: 14px;")
        
        status_text = QLabel(message)
        status_text.setStyleSheet("color: #64748b; font-size: 14px;")
        
        loading_layout.addWidget(spinner)
        loading_layout.addWidget(status_text)
        loading_layout.addStretch()
        
        self.agent_status_layout.addWidget(loading_panel)
        self._scroll_to_bottom()
        
        return loading_panel

    def clear_agent_status(self):
        """清除Agent状态"""
        for i in reversed(range(self.agent_status_layout.count())):
            widget = self.agent_status_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

    def add_error_message(self, text: str, check_config: bool = True):
        """添加错误消息"""
        lbl = QLabel(f"⚠️  {text}")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            "color:#dc2626; background:#fef2f2; border:1px solid #fca5a5;"
            "border-radius:6px; padding:10px 14px;"
        )
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, lbl)
        self._scroll_to_bottom()

    def _record_and_check_clarify(self, role: str, content: str):
        """记录交互并检查是否需要引导"""
        if not self._clarifier:
            return
        
        self._clarifier.record_interaction(role, content)
        
        if role == "user" and self._clarifier.should_prompt():
            QTimer.singleShot(500, self._show_clarify_prompt)

    def _show_clarify_prompt(self):
        """显示需求澄清引导卡片"""
        if not self._clarifier or self._clarify_card:
            return
        
        prompt = self._clarifier.get_prompt()
        
        try:
            from .clarification_card import ClarificationCard
            self._clarify_card = ClarificationCard(
                message=prompt.message,
                options=prompt.options
            )
            self._clarify_card.option_selected.connect(self._on_clarify_option)
            self._clarify_card.dismissed.connect(self._on_clarify_dismissed)
            
            self.msg_layout.insertWidget(self.msg_layout.count() - 1, self._clarify_card)
            self._scroll_to_bottom()
        except ImportError:
            pass

    def _on_clarify_option(self, option: str):
        """处理澄清选项"""
        if not self._clarifier:
            return
        
        self._clarify_card = None
        self._clarifier.on_user_response(option)
        
        if option in ["1", "好，帮我梳理需求", "是", "好"]:
            self._pending_clarify = True
            self._show_clarify_progress()
        elif option in ["3", "以后再说"]:
            self._show_disable_notice()

    def _show_clarify_progress(self):
        """显示头脑风暴进度"""
        lbl = QLabel(
            "🎯 已进入需求澄清模式，正在准备提问...\n"
            "请稍候，我会逐步引导你明确需求。"
        )
        lbl.setStyleSheet("""
            color: #3b82f6;
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 13px;
        """)
        lbl.setWordWrap(True)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, lbl)
        self._scroll_to_bottom()

    def _show_disable_notice(self):
        """显示禁用提示"""
        lbl = QLabel(
            "💡 需求澄清引导已临时关闭。\n"
            "你可以在「🎯 头脑风暴」面板中重新启用。"
        )
        lbl.setStyleSheet("""
            color: #64748b;
            background: #f1f5f9;
            border-radius: 6px;
            padding: 10px 14px;
            font-size: 12px;
        """)
        lbl.setWordWrap(True)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, lbl)
        self._scroll_to_bottom()

    def _on_clarify_dismissed(self):
        """关闭引导卡片"""
        self._clarify_card = None

    def _scroll_to_bottom(self):
        """滚动到底部"""
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def _hide_welcome(self):
        """隐藏欢迎信息"""
        if self._welcome.isVisible():
            self._welcome.hide()

    @staticmethod
    def _clear_layout(layout):
        """清除布局"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def focus_input(self):
        """聚焦输入框"""
        self.input_field.focus()
    
    def _is_configured(self, config_key: str) -> bool:
        """检查配置是否已完成"""
        if self._config_manager:
            return self._config_manager.has_config(config_key)
        
        # 简单检查 - 在实际应用中应该从配置存储中检查
        return False
    
    def _show_inline_config_card(self, config_type: str):
        """显示内联配置卡片"""
        if config_type in self._active_config_cards:
            return
        
        config_card = InlineConfigCard(config_type)
        config_card.config_completed.connect(self._on_config_completed)
        config_card.config_skipped.connect(self._on_config_skipped)
        
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, config_card)
        self._active_config_cards[config_type] = config_card
        self._scroll_to_bottom()
    
    def _on_config_completed(self, config_type: str, config_data: dict):
        """处理配置完成"""
        # 隐藏配置精灵
        if self._config_sprite:
            self._config_sprite.hide()
        
        # 移除配置卡片
        if config_type in self._active_config_cards:
            card = self._active_config_cards.pop(config_type)
            card.deleteLater()
        
        # 显示成功横幅
        banner = ConfigSuccessBanner(config_type)
        banner.test_requested.connect(self._on_config_test)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, banner)
        
        # 保存配置
        if self._config_manager:
            self._config_manager.save(config_type, config_data)
        
        # 发送配置完成信号
        self.config_completed.emit(config_type, config_data)
        
        self._scroll_to_bottom()
    
    def _on_config_skipped(self, config_type: str):
        """处理配置跳过"""
        # 隐藏配置精灵
        if self._config_sprite:
            self._config_sprite.hide()
        
        # 移除配置卡片
        if config_type in self._active_config_cards:
            card = self._active_config_cards.pop(config_type)
            card.deleteLater()
        
        self._scroll_to_bottom()
    
    def _on_config_test(self, config_type: str):
        """测试配置"""
        # 显示测试进度
        loading = self.show_agent_loading(f"正在测试 {self._get_config_name(config_type)}...")
        
        # 模拟测试
        QTimer.singleShot(2000, lambda: self._on_config_test_completed(config_type, loading))
    
    def _on_config_test_completed(self, config_type: str, loading_widget):
        """配置测试完成"""
        loading_widget.deleteLater()
        
        # 显示测试结果
        result_lbl = QLabel(f"✅ {self._get_config_name(config_type)} 配置测试成功！")
        result_lbl.setStyleSheet("""
            color: #10b981;
            background: #ecfdf5;
            border: 1px solid #10b981;
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 13px;
        """)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, result_lbl)
        self._scroll_to_bottom()
    
    def _get_config_name(self, config_key: str) -> str:
        """获取配置名称"""
        names = {
            "openai": "OpenAI API",
            "ollama": "Ollama",
            "browser": "浏览器自动化",
            "wecom": "企业微信",
            "wechat": "微信",
            "mcp": "MCP工具",
            "search": "智能搜索",
            "github": "GitHub"
        }
        return names.get(config_key, config_key)


import asyncio