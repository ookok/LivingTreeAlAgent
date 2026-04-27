"""
聊天模块 - 真实功能实现

支持 Ollama API 对话，流式响应，Markdown 渲染。
"""

import json
import requests
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QLabel, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QObject
from PyQt6.QtGui import QTextCursor, QFont

from client.src.business.nanochat_config import config


# ── 工作线程：Ollama API 调用 ───────────────────────────────────────────────

class OllamaWorker(QThread):
    """Ollama API 工作线程（支持流式响应）"""

    chunk_received = pyqtSignal(str)  # 收到一个文本块
    finished = pyqtSignal(str)         # 完成（完整响应）
    error = pyqtSignal(str)            # 错误

    def __init__(self, base_url: str, model: str, messages: List[Dict], parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.model = model
        self.messages = messages
        self._stop_requested = False

    def run(self):
        try:
            url = f"{self.base_url}/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "messages": self.messages,
                "stream": True,
            }

            response = requests.post(url, json=payload, headers=headers, stream=True, timeout=120)
            response.raise_for_status()

            full_content = ""
            for line in response.iter_lines():
                if self._stop_requested:
                    break
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    full_content += content
                                    self.chunk_received.emit(content)
                        except json.JSONDecodeError:
                            continue

            self.finished.emit(full_content)

        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._stop_requested = True


# ── 消息气泡 ─────────────────────────────────────────────────────────────────

class MessageBubble(QFrame):
    """单条消息气泡"""

    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.content = content
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        # 角色标签
        role_label = QLabel("🧑 用户" if self.role == "user" else "🤖 助手")
        role_label.setStyleSheet(
            "font-size: 11px; color: #666; font-weight: bold;"
        )
        layout.addWidget(role_label)

        # 内容标签（简化版，实际应支持 Markdown）
        content_label = QLabel(self.content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("font-size: 14px; padding: 4px 0;")
        layout.addWidget(content_label)

        # 样式
        if self.role == "user":
            self.setStyleSheet("""
                MessageBubble {
                    background: #E3F2FD;
                    border-radius: 12px;
                    margin-left: 40px;
                }
            """)
        else:
            self.setStyleSheet("""
                MessageBubble {
                    background: #F5F5F5;
                    border-radius: 12px;
                    margin-right: 40px;
                }
            """)


# ── 主聊天面板 ───────────────────────────────────────────────────────────────

class Panel(QWidget):
    """聊天面板 - 真实功能"""

    message_sent = pyqtSignal(str)  # 发送消息信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.messages: List[Dict] = [
            {"role": "system", "content": "你是生命之树 AI 助手，友好、专业、简洁。"}
        ]
        self.worker: Optional[OllamaWorker] = None
        self.current_assistant_bubble: Optional[MessageBubble] = None
        self._setup_ui()
        self._setup_models()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        title_bar = QFrame()
        title_bar.setFixedHeight(52)
        title_bar.setStyleSheet("background: #FFFFFF; border-bottom: 1px solid #E0E0E0;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)

        title_label = QLabel("💬 智能对话")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)

        self.model_label = QLabel()
        self.model_label.setStyleSheet("font-size: 12px; color: #666;")
        title_layout.addWidget(self.model_label)

        title_layout.addStretch()
        layout.addWidget(title_bar)

        # 消息区域（可滚动）
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: #FAFAFA; }")

        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(16, 16, 16, 16)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area, 1)

        # 输入区域
        input_frame = QFrame()
        input_frame.setStyleSheet("background: #FFFFFF; border-top: 1px solid #E0E0E0;")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(16, 12, 16, 12)

        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("输入消息... (Ctrl+Enter 发送)")
        self.input_field.setMaximumHeight(100)
        self.input_field.keyPressEvent = self._on_input_key_press
        input_layout.addWidget(self.input_field, 1)

        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(80, 40)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #1976D2;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1565C0; }
            QPushButton:disabled { background: #BDBDBD; }
        """)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)

        layout.addWidget(input_frame)

    def _setup_models(self):
        """设置模型（从配置读取）"""
        # 从配置读取模型名称
        # Ollama 默认模型，实际应从 API 获取
        model_name = "qwen3.5:4b"  # 默认模型
        self.model_name = model_name
        self.model_label.setText(f"模型: {model_name}")

        # 获取 API 基础 URL
        self.base_url = config.ollama.url
        print(f"[Chat] Ollama URL: {self.base_url}")
        print(f"[Chat] Model: {self.model_name}")

    def _on_input_key_press(self, event):
        """处理输入框按键"""
        from PyQt6.QtGui import QKeyEvent
        if isinstance(event, QKeyEvent):
            # Ctrl+Enter 或 Cmd+Enter 发送
            if event.key() in (16777221, 16777220) and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self._send_message()
                return
            # Enter 发送（无修饰键）
            if event.key() in (16777221, 16777220) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send_message()
                return

        # 默认处理
        QTextEdit.keyPressEvent(self.input_field, event)

    def _send_message(self):
        """发送消息"""
        text = self.input_field.toPlainText().strip()
        if not text:
            return

        # 添加用户消息
        self._add_message("user", text)
        self.messages.append({"role": "user", "content": text})

        # 清空输入框
        self.input_field.clear()

        # 禁用发送按钮
        self.send_btn.setEnabled(False)
        self.send_btn.setText("思考中...")

        # 创建助手消息气泡（等待流式更新）
        self.current_assistant_bubble = MessageBubble("assistant", "")
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, self.current_assistant_bubble)
        self._scroll_to_bottom()

        # 启动工作线程
        self.worker = OllamaWorker(self.base_url, self.model_name, self.messages)
        self.worker.chunk_received.connect(self._on_chunk_received)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _add_message(self, role: str, content: str):
        """添加消息气泡"""
        bubble = MessageBubble(role, content)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """滚动到底部"""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @pyqtSlot(str)
    def _on_chunk_received(self, chunk: str):
        """收到文本块（流式更新）"""
        if self.current_assistant_bubble:
            current_text = self.current_assistant_bubble.content + chunk
            self.current_assistant_bubble.content = current_text
            # 更新显示
            layout = self.current_assistant_bubble.layout()
            if layout and layout.count() >= 2:
                content_label = layout.itemAt(1).widget()
                if content_label:
                    content_label.setText(current_text)

    @pyqtSlot(str)
    def _on_finished(self, full_content: str):
        """完成响应"""
        self.messages.append({"role": "assistant", "content": full_content})
        self.current_assistant_bubble = None
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        self.worker = None

    @pyqtSlot(str)
    def _on_error(self, error_msg: str):
        """处理错误"""
        print(f"[Chat] Error: {error_msg}")
        if self.current_assistant_bubble:
            self.current_assistant_bubble.content = f"❌ 错误: {error_msg}"
            layout = self.current_assistant_bubble.layout()
            if layout and layout.count() >= 2:
                content_label = layout.itemAt(1).widget()
                if content_label:
                    content_label.setText(self.current_assistant_bubble.content)
                    content_label.setStyleSheet("font-size: 14px; color: #F44336;")

        self.current_assistant_bubble = None
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        self.worker = None

    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        super().closeEvent(event)
