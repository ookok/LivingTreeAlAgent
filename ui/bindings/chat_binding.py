# -*- coding: utf-8 -*-
"""
Chat Binding - 聊天面板与业务逻辑绑定

将 PyDracula UI 聊天组件与 ChatHub 连接
"""

from typing import Optional, Callable
import asyncio

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QWidget, QTextEdit, QLineEdit, QPushButton


class ChatBinding(QObject):
    """
    聊天面板业务逻辑绑定

    Signals:
        message_received: 收到新消息
        message_sent: 消息已发送
        typing_indicator: 对方正在输入
        connection_status: 连接状态变更
    """

    message_received = Signal(dict)  # {'role': 'user'|'assistant', 'content': str, 'timestamp': float}
    message_sent = Signal(dict)
    typing_indicator = Signal(bool)
    connection_status = Signal(str)  # 'connected'|'disconnected'|'connecting'

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._parent = parent
        self._chat_hub = None
        self._ui_callback = None
        self._initialized = False

        # UI 组件引用
        self._input_widget: Optional[QLineEdit] = None
        self._output_widget: Optional[QTextEdit] = None
        self._send_button: Optional[QPushButton] = None

        # 会话状态
        self._current_session_id: Optional[str] = None
        self._message_history: list = []

    def initialize(self):
        """初始化聊天绑定"""
        if self._initialized:
            return

        try:
            # 延迟导入 ChatHub
            from client.src.business.unified_chat.chat_hub import ChatHub
            self._chat_hub = ChatHub.get_chat_hub()

            # 注册 UI 回调
            self._ui_callback = self._on_chat_hub_event
            self._chat_hub.add_ui_callback(self._ui_callback)

            self._initialized = True
            self.connection_status.emit('connected')
        except Exception as e:
            print(f"[ChatBinding] Initialize error: {e}")
            self.connection_status.emit('disconnected')

    def bind_ui(self, input_widget: QLineEdit, output_widget: QTextEdit, send_button: QPushButton):
        """
        绑定 UI 组件

        Args:
            input_widget: 消息输入框
            output_widget: 消息显示区
            send_button: 发送按钮
        """
        self._input_widget = input_widget
        self._output_widget = output_widget
        self._send_button = send_button

        # 连接信号
        if send_button:
            send_button.clicked.connect(self._on_send_clicked)

        if input_widget:
            input_widget.returnPressed.connect(self._on_send_clicked)

    def _on_chat_hub_event(self, event: str, data):
        """处理 ChatHub 事件"""
        if event == 'message_received':
            self._handle_incoming_message(data)
        elif event == 'typing_indicator':
            self.typing_indicator.emit(data)
        elif event == 'status_changed':
            self.connection_status.emit(data.get('status', 'unknown'))

    def _handle_incoming_message(self, message_data: dict):
        """处理收到的消息"""
        role = message_data.get('role', 'assistant')
        content = message_data.get('content', '')

        self.message_received.emit({
            'role': role,
            'content': content,
            'timestamp': message_data.get('timestamp', 0)
        })

    @Slot()
    def _on_send_clicked(self):
        """发送按钮点击处理"""
        if not self._input_widget:
            return

        text = self._input_widget.text().strip()
        if not text:
            return

        # 清空输入
        self._input_widget.clear()

        # 发送消息
        self.send_message(text)

    def send_message(self, text: str):
        """
        发送消息

        Args:
            text: 消息内容
        """
        if not text.strip():
            return

        # 添加到历史
        msg_data = {
            'role': 'user',
            'content': text,
            'timestamp': asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
        }
        self._message_history.append(msg_data)
        self.message_sent.emit(msg_data)

        # 更新 UI
        self._append_to_output('user', text)

        # 通过 ChatHub 发送
        if self._chat_hub:
            try:
                # 异步发送
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._async_send_message(text))
                else:
                    asyncio.run(self._async_send_message(text))
            except Exception as e:
                self._append_to_output('system', f'发送失败: {e}')

    async def _async_send_message(self, text: str):
        """异步发送消息"""
        try:
            if self._chat_hub:
                await self._chat_hub.send_text_message(
                    text,
                    session_id=self._current_session_id
                )
        except Exception as e:
            print(f"[ChatBinding] Send error: {e}")

    def _append_to_output(self, role: str, content: str):
        """追加消息到输出区域"""
        if not self._output_widget:
            return

        # 格式化消息
        if role == 'user':
            prefix = "👤 You"
            color = "#4CAF50"  # 绿色
        elif role == 'assistant':
            prefix = "🤖 AI"
            color = "#2196F3"  # 蓝色
        else:
            prefix = "ℹ️ System"
            color = "#9E9E9E"  # 灰色

        html = f'''
        <div style="margin: 8px 0;">
            <span style="color: {color}; font-weight: bold;">{prefix}:</span>
            <span style="color: #E0E0E0;">{self._escape_html(content)}</span>
        </div>
        '''

        self._output_widget.append(html)

    @staticmethod
    def _escape_html(text: str) -> str:
        """转义 HTML 特殊字符"""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;')
                .replace('\n', '<br>'))

    def load_conversation(self, session_id: str):
        """加载会话历史"""
        self._current_session_id = session_id

        if self._chat_hub and self._chat_hub.session_manager:
            messages = self._chat_hub.session_manager.get_session_messages(session_id)
            if messages:
                self._message_history = messages
                # 更新 UI
                if self._output_widget:
                    self._output_widget.clear()
                    for msg in messages:
                        self._append_to_output(msg.get('role', 'user'), msg.get('content', ''))

    def clear_history(self):
        """清空聊天历史"""
        self._message_history.clear()
        if self._output_widget:
            self._output_widget.clear()

    def get_message_history(self) -> list:
        """获取消息历史"""
        return self._message_history.copy()

    def cleanup(self):
        """清理资源"""
        if self._chat_hub and self._ui_callback:
            self._chat_hub.remove_ui_callback(self._ui_callback)

        # 断开信号
        if self._send_button:
            try:
                self._send_button.clicked.disconnect()
            except:
                pass

        self._initialized = False
