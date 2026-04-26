"""
Intelligent IDE Panel - Chat-Driven Development Environment
默认显示聊天框，AI根据用户输入生成/修改代码，代码编辑器作为tab页
"""
import os
import re
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QLineEdit, QPushButton, QLabel,
    QTabWidget, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox, QComboBox,
    QListWidget, QListWidgetItem, QInputDialog,
    QProgressBar, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QKeySequence, QShortcut

from client.src.business.ide_agent import IntelligentIDEAagent
from client.src.business.ide_service import IntelligentIDEService
from client.src.presentation.widgets.project_browser import ProjectBrowser
from client.src.presentation.widgets.global_search import GlobalSearchWidget
from client.src.presentation.widgets.test_integration import TestIntegrationWidget
from client.src.presentation.widgets.git_integration import GitIntegrationWidget
from client.src.presentation.widgets.syntax_highlighter import get_highlighter
from client.src.presentation.widgets.code_completer import get_completer


class ChatMessageThread(QThread):
    """后台线程处理AI聊天请求（支持流式输出）"""
    chunk_received = pyqtSignal(str)           # 收到一个文本块
    thinking_received = pyqtSignal(str)         # 收到推理内容
    finished = pyqtSignal(str)                 # 完成（完整响应）
    error_occurred = pyqtSignal(str)           # 错误
    code_generated = pyqtSignal(str, str)      # (file_path, code)
    tool_start = pyqtSignal(str, str)          # 工具开始（名称，参数）
    tool_result = pyqtSignal(str, str, bool)   # 工具结果（名称，结果，成功）
    
    def __init__(self, agent, message, context=None):
        super().__init__()
        self.agent = agent
        self.message = message
        self.context = context or {}
        self._stop_requested = False
    
    def run(self):
        try:
            full_content = ""
            thinking_content = ""
            
            # 定义回调函数
            def on_stream_delta(delta: str):
                nonlocal full_content
                if self._stop_requested:
                    return
                full_content += delta
                self.chunk_received.emit(delta)
            
            def on_thinking(delta: str):
                nonlocal thinking_content
                thinking_content += delta
                self.thinking_received.emit(delta)
            
            def on_tool_start(name: str, params: str):
                if self._stop_requested:
                    return
                self.tool_start.emit(name, params)
            
            def on_tool_result(name: str, result: str, success: bool):
                if self._stop_requested:
                    return
                self.tool_result.emit(name, result, success)
            
            # 调用AI agent处理用户请求
            callbacks = {
                'on_stream_delta': on_stream_delta,
                'on_thinking': on_thinking,
                'on_tool_start': on_tool_start,
                'on_tool_result': on_tool_result,
            }
            
            response = self.agent.process_chat_message(
                self.message,
                self.context,
                callbacks=callbacks,
            )
            
            # 检查是否需要生成/修改代码
            if response.get('type') == 'code_generation':
                file_path = response.get('file_path', '')
                code = response.get('code', '')
                self.code_generated.emit(file_path, code)
            
            # 完成
            self.finished.emit(full_content or response.get('message', ''))
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.error_occurred.emit(f"{str(e)}\n\n{error_detail}")
    
    def stop(self):
        """停止处理"""
        self._stop_requested = True


class CodeEditorWidget(QWidget):
    """增强的代码编辑器组件（带语法高亮和代码补全）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 编辑器工具栏
        toolbar = QHBoxLayout()
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(['Python', 'JavaScript', 'TypeScript', 'HTML', 'CSS', 'Markdown', 'JSON', 'YAML'])
        self.language_combo.currentTextChanged.connect(self.change_language)
        toolbar.addWidget(QLabel("语言:"))
        toolbar.addWidget(self.language_combo)
        toolbar.addStretch()
        
        self.cursor_label = QLabel("行 1, 列 1")
        toolbar.addWidget(self.cursor_label)
        
        layout.addLayout(toolbar)
        
        # 代码编辑器（使用QTextEdit + 语法高亮 + 代码补全）
        self.editor = QTextEdit()
        self.editor.setFont(QFont('Consolas', 12))
        self.editor.setAcceptRichText(False)
        self.editor.cursorPositionChanged.connect(self.update_cursor_position)
        
        # 语法高亮器
        self.highlighter = None
        self.update_highlighter('Python')
        
        # 代码补全器
        self.completer = None
        self.update_completer('Python')
        
        layout.addWidget(self.editor)
        
        # 按钮栏
        btn_layout = QHBoxLayout()
        
        self.run_btn = QPushButton("▶ 运行")
        self.run_btn.clicked.connect(self.run_code)
        btn_layout.addWidget(self.run_btn)
        
        self.ai_explain_btn = QPushButton("🤖 解释")
        self.ai_explain_btn.clicked.connect(self.ai_explain)
        btn_layout.addWidget(self.ai_explain_btn)
        
        self.ai_debug_btn = QPushButton("🔧 调试")
        self.ai_debug_btn.clicked.connect(self.ai_debug)
        btn_layout.addWidget(self.ai_debug_btn)
        
        self.ai_optimize_btn = QPushButton("⚡ 优化")
        self.ai_optimize_btn.clicked.connect(self.ai_optimize)
        btn_layout.addWidget(self.ai_optimize_btn)
        
        btn_layout.addStretch()
        
        self.save_btn = QPushButton("💾 保存")
        self.save_btn.clicked.connect(self.save_file)
        btn_layout.addWidget(self.save_btn)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def change_language(self, language):
        """切换语言（触发语法高亮更新）"""
        self.update_highlighter(language)
        self.update_completer(language)
    
    def update_highlighter(self, language):
        """更新语法高亮器"""
        if self.highlighter:
            # 移除旧的高亮器
            self.highlighter.setDocument(None)
        
        # 获取新的高亮器
        self.highlighter = get_highlighter(language, self.editor)
        if self.highlighter:
            self.highlighter.setDocument(self.editor.document())
    
    def update_completer(self, language):
        """更新代码补全器"""
        self.completer = get_completer(language, self.editor)
        if self.completer:
            self.completer.setWidget(self.editor)
    
    def update_cursor_position(self):
        """更新光标位置显示"""
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        self.cursor_label.setText(f"行 {line}, 列 {column}")
    
    def set_content(self, content):
        """设置编辑器内容"""
        self.editor.setPlainText(content)
    
    def get_content(self):
        """获取编辑器内容"""
        return self.editor.toPlainText()
    
    def run_code(self):
        """运行代码"""
        code = self.get_content()
        # TODO: 调用 ide_service 执行代码
        print(f"运行代码:\n{code}")
    
    def ai_explain(self):
        """AI解释代码"""
        code = self.get_content()
        # TODO: 调用 ide_agent 解释代码
        print(f"AI解释代码")
    
    def ai_debug(self):
        """AI调试代码"""
        code = self.get_content()
        # TODO: 调用 ide_agent 调试代码
        print(f"AI调试代码")
    
    def ai_optimize(self):
        """AI优化代码"""
        code = self.get_content()
        # TODO: 调用 ide_agent 优化代码
        print(f"AI优化代码")
    
    def save_file(self):
        """保存文件"""
        if not self.current_file:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存文件", "", "All Files (*)"
            )
            if file_path:
                self.current_file = file_path
            else:
                return
        
        try:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(self.get_content())
            QMessageBox.information(self, "成功", f"文件已保存: {self.current_file}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
    
    def open_file(self, file_path):
        """打开文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.set_content(content)
            self.current_file = file_path
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开失败: {str(e)}")


class ThinkingWidget(QFrame):
    """推理过程显示组件（可折叠）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = True
        self.thinking_text = ""
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        
        # 标题栏
        self.header = QFrame()
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.toggle_btn = QPushButton("▶")
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.setStyleSheet("border: none; font-size: 10px;")
        self.toggle_btn.clicked.connect(self._toggle)
        header_layout.addWidget(self.toggle_btn)
        
        label = QLabel("🤔 推理过程")
        label.setStyleSheet("color: #FF9800; font-size: 12px; font-weight: bold;")
        header_layout.addWidget(label)
        
        header_layout.addStretch()
        layout.addWidget(self.header)
        
        # 内容区域
        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        self.content_text.setMaximumHeight(200)
        self.content_text.setStyleSheet("""
            QTextEdit {
                font-size: 12px;
                background: #FFF8E1;
                border: 1px solid #FFE082;
                border-radius: 4px;
            }
        """)
        self.content_text.setVisible(not self._collapsed)
        layout.addWidget(self.content_text)
    
    def _toggle(self):
        """切换折叠状态"""
        self._collapsed = not self._collapsed
        self.toggle_btn.setText("▼" if not self._collapsed else "▶")
        self.content_text.setVisible(not self._collapsed)
    
    def append_text(self, text: str):
        """追加推理文本"""
        self.thinking_text += text
        self.content_text.append(text)
    
    def set_text(self, text: str):
        """设置推理文本"""
        self.thinking_text = text
        self.content_text.setPlainText(text)


class ToolCallWidget(QFrame):
    """工具调用显示组件（可折叠）"""
    
    def __init__(self, tool_name: str, parent=None):
        super().__init__(parent)
        self.tool_name = tool_name
        self._collapsed = True
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        
        # 标题栏
        self.header = QFrame()
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.toggle_btn = QPushButton("▶")
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.setStyleSheet("border: none; font-size: 10px;")
        self.toggle_btn.clicked.connect(self._toggle)
        header_layout.addWidget(self.toggle_btn)
        
        self.label = QLabel(f"🔧 {self.tool_name}")
        self.label.setStyleSheet("color: #4CAF50; font-size: 12px; font-weight: bold;")
        header_layout.addWidget(self.label)
        
        header_layout.addStretch()
        layout.addWidget(self.header)
        
        # 内容区域
        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        self.content_text.setMaximumHeight(150)
        self.content_text.setStyleSheet("""
            QTextEdit {
                font-size: 11px;
                background: #f0f0f0;
                border: 1px solid #eee;
                border-radius: 4px;
            }
        """)
        self.content_text.setVisible(not self._collapsed)
        layout.addWidget(self.content_text)
    
    def _toggle(self):
        """切换折叠状态"""
        self._collapsed = not self._collapsed
        self.toggle_btn.setText("▼" if not self._collapsed else "▶")
        self.content_text.setVisible(not self._collapsed)
    
    def set_result(self, result: str, success: bool):
        """设置工具执行结果"""
        status_icon = "✓" if success else "✗"
        status_color = "#4CAF50" if success else "#F44336"
        self.label.setText(f"{status_icon} {self.tool_name}")
        self.label.setStyleSheet(f"color: {status_color}; font-size: 12px; font-weight: bold;")
        self.content_text.setPlainText(result[:500])


class MessageBubble(QFrame):
    """单条消息气泡（支持 Markdown 渲染和流式输出）"""
    
    def __init__(self, role: str, content: str = "", parent=None):
        super().__init__(parent)
        self.role = role
        self.content = content
        self.thinking_widget = None
        self.tool_widgets = []
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        # 角色标签
        role_label = QLabel("👤 用户" if self.role == "user" else "🤖 助手")
        role_label.setStyleSheet("font-size: 11px; color: #666; font-weight: bold;")
        layout.addWidget(role_label)
        
        # 内容显示
        if self.role == "user":
            self.content_label = QLabel(self.content)
            self.content_label.setWordWrap(True)
            self.content_label.setStyleSheet("font-size: 14px; padding: 4px 0;")
            layout.addWidget(self.content_label)
        else:
            self.content_view = QTextEdit()
            self.content_view.setReadOnly(True)
            self.content_view.setMaximumHeight(600)
            self.content_view.setMinimumHeight(50)
            self._update_content_display()
            layout.addWidget(self.content_view)
        
        # 推理过程容器
        self.thinking_container = QWidget()
        self.thinking_layout = QVBoxLayout(self.thinking_container)
        self.thinking_layout.setContentsMargins(0, 4, 0, 4)
        self.thinking_container.setVisible(False)
        layout.addWidget(self.thinking_container)
        
        # 工具调用容器
        self.tools_container = QWidget()
        self.tools_layout = QVBoxLayout(self.tools_container)
        self.tools_layout.setContentsMargins(0, 4, 0, 4)
        self.tools_container.setVisible(False)
        layout.addWidget(self.tools_container)
        
        # 时间戳
        time_label = QLabel(datetime.now().strftime("%H:%M"))
        time_label.setStyleSheet("font-size: 10px; color: #999;")
        layout.addWidget(time_label)
        
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
    
    def _update_content_display(self):
        """更新内容显示（渲染 Markdown）"""
        if hasattr(self, 'content_view'):
            html = self._render_markdown(self.content)
            self.content_view.setHtml(html)
            
            # 自适应高度
            document = self.content_view.document()
            height = int(document.size().height()) + 20
            self.content_view.setMaximumHeight(min(height, 600))
    
    def _render_markdown(self, text: str) -> str:
        """简单的 Markdown 渲染（代码块高亮）"""
        # 处理代码块
        text = re.sub(
            r'```(\w*)\n(.*?)```',
            r'<pre style="background: #282c34; color: #abb2bf; padding: 12px; border-radius: 8px; overflow-x: auto;"><code>\2</code></pre>',
            text,
            flags=re.DOTALL
        )
        
        # 处理行内代码
        text = re.sub(r'`([^`]+)`', r'<code style="background: #f5f5f5; padding: 2px 6px; border-radius: 4px;">\1</code>', text)
        
        # 处理加粗
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        
        # 处理换行
        text = text.replace('\n', '<br>')
        
        return text
    
    def update_content(self, new_content: str):
        """更新消息内容（用于流式输出）"""
        self.content = new_content
        if hasattr(self, 'content_view'):
            self._update_content_display()
    
    def append_thinking(self, text: str):
        """追加推理过程"""
        self.thinking_container.setVisible(True)
        
        if not self.thinking_widget:
            self.thinking_widget = ThinkingWidget()
            self.thinking_layout.addWidget(self.thinking_widget)
        
        self.thinking_widget.append_text(text)
    
    def set_thinking(self, text: str):
        """设置推理过程"""
        self.thinking_container.setVisible(True)
        
        if not self.thinking_widget:
            self.thinking_widget = ThinkingWidget()
            self.thinking_layout.addWidget(self.thinking_widget)
        
        self.thinking_widget.set_text(text)
    
    def add_tool_call(self, tool_name: str, result: str = "", success: bool = True):
        """添加工具调用显示"""
        self.tools_container.setVisible(True)
        
        tool_widget = ToolCallWidget(tool_name)
        if result:
            tool_widget.set_result(result, success)
        
        self.tool_widgets.append(tool_widget)
        self.tools_layout.addWidget(tool_widget)


class ChatWidget(QWidget):
    """聊天界面组件（支持流式输出、思考过程、工具调用）"""
    
    message_sent = pyqtSignal(str)  # 发送消息信号
    run_code_requested = pyqtSignal(str, str)  # 请求运行代码（代码，语言）
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.message_history = []
        self.current_assistant_bubble = None  # 当前助手消息气泡（用于流式输出）
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 聊天历史显示区域（使用 QScrollArea + 动态布局）
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
        """)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.addStretch()
        
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area, 1)
        
        # 输入区域
        input_layout = QHBoxLayout()
        
        # 运行代码按钮（在输入区域左侧）
        self.run_code_btn = QPushButton("▶ 运行代码")
        self.run_code_btn.setFixedSize(100, 40)
        self.run_code_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        self.run_code_btn.clicked.connect(self.run_current_code)
        input_layout.addWidget(self.run_code_btn)
        
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(100)
        self.message_input.setPlaceholderText("输入你的需求，我会自动生成/修改代码...\n\n示例：\n- 创建一个用户登录模块\n- 修改homepage.py，添加深色模式切换按钮\n- 帮我优化这段代码的速度")
        self.message_input.setStyleSheet("""
            QTextEdit {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3e3e42;
                border-radius: 5px;
                padding: 8px;
            }
        """)
        
        # Ctrl+Enter 发送
        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.message_input)
        shortcut.activated.connect(self.send_message)
        
        input_layout.addWidget(self.message_input, 1)
        
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(80, 40)
        self.send_btn.clicked.connect(self.send_message)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        input_layout.addWidget(self.send_btn)
        
        # 运行代码按钮（在发送按钮右侧）
        self.run_code_btn = QPushButton("▶ 运行")
        self.run_code_btn.setFixedSize(80, 40)
        self.run_code_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        self.run_code_btn.clicked.connect(self.run_current_code)
        input_layout.addWidget(self.run_code_btn)
        
        layout.addLayout(input_layout)
        
        # 快捷提示
        hint_label = QLabel("💡 提示：Ctrl+Enter 发送消息 | 输入具体需求，我会自动生成代码")
        hint_label.setStyleSheet("color: #858585; font-size: 11px;")
        layout.addWidget(hint_label)
        
        self.setLayout(layout)
    
    def send_message(self):
        """发送消息"""
        message = self.message_input.toPlainText().strip()
        if not message:
            return
        
        # 显示用户消息
        self.append_message('user', message)
        
        # 清空输入框
        self.message_input.clear()
        
        # 发送信号
        self.message_sent.emit(message)
    
    def run_current_code(self):
        """请求运行代码（发射信号，由 IntelligentIDEPanel 处理）"""
        self.run_code_requested.emit("", "")  # 参数由 IntelligentIDEPanel 从编辑器获取
    
    def append_message(self, role: str, content: str = ""):
        """添加消息到聊天历史"""
        self.message_history.append({'role': role, 'content': content})
        
        # 创建消息气泡
        bubble = MessageBubble(role, content)
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, bubble)
        
        # 如果是助手消息，保存引用（用于流式输出）
        if role == 'assistant':
            self.current_assistant_bubble = bubble
        
        # 滚动到底部
        self.scroll_to_bottom()
    
    def append_stream_chunk(self, chunk: str):
        """追加流式输出内容"""
        if not self.current_assistant_bubble:
            # 创建新的助手消息
            self.append_message('assistant', chunk)
        else:
            # 更新现有消息
            current_content = self.current_assistant_bubble.content
            self.current_assistant_bubble.update_content(current_content + chunk)
    
    def append_thinking(self, text: str):
        """追加推理过程"""
        if self.current_assistant_bubble:
            self.current_assistant_bubble.append_thinking(text)
            self.scroll_to_bottom()
    
    def set_thinking(self, text: str):
        """设置推理过程"""
        if self.current_assistant_bubble:
            self.current_assistant_bubble.set_thinking(text)
            self.scroll_to_bottom()
    
    def add_tool_call(self, tool_name: str, result: str = "", success: bool = True):
        """添加工具调用显示"""
        if self.current_assistant_bubble:
            self.current_assistant_bubble.add_tool_call(tool_name, result, success)
            self.scroll_to_bottom()
    
    def finalize_message(self):
        """完成当前消息（重置 current_assistant_bubble）"""
        self.current_assistant_bubble = None
    
    def scroll_to_bottom(self):
        """滚动到底部"""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def append_code_result(self, file_path: str, code: str, execution_result: str = ""):
        """添加生成的代码到聊天历史"""
        bubble = MessageBubble('assistant')
        bubble.update_content(f"已生成代码：**{file_path}**\n\n```python\n{code}\n```")
        
        if execution_result:
            bubble.update_content(bubble.content + f"\n\n**执行结果：**\n```\n{execution_result}\n```")
        
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, bubble)
        self.message_history.append({'role': 'assistant', 'content': bubble.content})
        self.scroll_to_bottom()


class IntelligentIDEPanel(QWidget):
    """
    智能IDE面板 - 聊天驱动的开发环境
    
    布局：
    - 默认显示：聊天框（左侧或全屏）
    - 代码编辑器：作为tab页
    - 其他工具：作为tab页（项目浏览器、搜索、测试、Git、部署）
    """
    
    def __init__(self, parent=None, project_path=None):
        super().__init__(parent)
        self.project_path = project_path or os.getcwd()
        self.ide_agent = IntelligentIDEAagent()
        self.ide_service = IntelligentIDEService()
        self.worker_thread = None
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建主分割器
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：聊天界面（默认显示）
        self.chat_widget = ChatWidget()
        self.chat_widget.message_sent.connect(self.handle_user_message)
        self.main_splitter.addWidget(self.chat_widget)
        
        # 右侧：标签页界面（代码编辑器 + 其他工具）
        self.right_tabs = QTabWidget()
        self.right_tabs.setTabPosition(QTabWidget.TabPosition.North)
        
        # Tab 1: 代码编辑器
        self.code_editor = CodeEditorWidget()
        self.right_tabs.addTab(self.code_editor, "📝 代码编辑器")
        
        # Tab 2: 项目浏览器
        self.project_browser = ProjectBrowser(self.project_path)
        self.project_browser.file_opened.connect(self.open_file_in_editor)
        self.right_tabs.addTab(self.project_browser, "📂 项目浏览器")
        
        # Tab 3: 全局搜索
        self.global_search = GlobalSearchWidget()
        self.global_search.file_opened.connect(self.open_file_in_editor)
        self.right_tabs.addTab(self.global_search, "🔍 全局搜索")
        
        # Tab 4: 测试集成
        self.test_integration = TestIntegrationWidget()
        self.right_tabs.addTab(self.test_integration, "🧪 测试")
        
        # Tab 5: Git集成
        self.git_integration = GitIntegrationWidget(self.project_path)
        self.right_tabs.addTab(self.git_integration, "🔧 Git")
        
        # Tab 6: 部署管理
        # self.deployment_widget = DeploymentWidget()
        # self.right_tabs.addTab(self.deployment_widget, "🚀 部署")
        
        self.main_splitter.addWidget(self.right_tabs)
        
        # 设置分割器比例（聊天框占2/3，右侧占1/3）
        self.main_splitter.setStretchFactor(0, 2)
        self.main_splitter.setStretchFactor(1, 1)
        
        layout.addWidget(self.main_splitter)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪 - 输入需求，我会自动生成代码")
        layout.addWidget(self.status_bar)
        
        self.setLayout(layout)
        
        # 连接运行代码信号
        self.chat_widget.run_code_requested.connect(self.run_current_code)
        
        # 添加欢迎消息
        self.add_welcome_message()
    
    def add_welcome_message(self):
        """添加欢迎消息"""
        welcome_msg = """
你好！我是你的 AI 编程助手。

🎯 我可以帮你：
• 生成新代码（输入：创建一个用户登录模块）
• 修改现有代码（输入：修改 homepage.py，添加深色模式）
• 优化代码性能（输入：优化这段代码的运行速度）
• 解释代码逻辑（输入：解释一下这段代码的逻辑）
• 调试代码错误（输入：这段代码报错了，帮我看看）

💡 提示：
• Ctrl+Enter 发送消息
• 生成的代码会在右侧编辑器显示
• 你可以直接在编辑器修改代码
        """
        self.chat_widget.append_message('assistant', welcome_msg.strip())
    
    def handle_user_message(self, message):
        """处理用户发送的消息"""
        self.status_bar.showMessage("正在处理...")
        
        # 创建助手消息气泡（用于流式输出）
        self.chat_widget.append_message('assistant')
        
        # 后台线程处理AI请求
        self.worker_thread = ChatMessageThread(
            self.ide_agent,
            message,
            context={'project_path': self.project_path}
        )
        self.worker_thread.chunk_received.connect(self.handle_stream_chunk)
        self.worker_thread.thinking_received.connect(self.handle_thinking)
        self.worker_thread.tool_start.connect(self.handle_tool_start)
        self.worker_thread.tool_result.connect(self.handle_tool_result)
        self.worker_thread.finished.connect(self.handle_finished)
        self.worker_thread.error_occurred.connect(self.handle_error)
        self.worker_thread.code_generated.connect(self.handle_code_generation)
        self.worker_thread.start()
    
    def handle_stream_chunk(self, chunk: str):
        """处理流式输出块"""
        self.chat_widget.append_stream_chunk(chunk)
    
    def handle_thinking(self, text: str):
        """处理推理过程"""
        self.chat_widget.append_thinking(text)
    
    def handle_tool_start(self, name: str, params: str):
        """处理工具开始"""
        self.chat_widget.add_tool_call(name, params, True)
    
    def handle_tool_result(self, name: str, result: str, success: bool):
        """处理工具结果"""
        # 找到最后一个工具调用，更新结果
        if self.chat_widget.current_assistant_bubble and self.chat_widget.current_assistant_bubble.tool_widgets:
            tool_widget = self.chat_widget.current_assistant_bubble.tool_widgets[-1]
            tool_widget.set_result(result, success)
    
    def handle_finished(self, full_content: str):
        """处理完成"""
        self.chat_widget.finalize_message()
        self.status_bar.showMessage("就绪")
    
    def handle_error(self, error_msg):
        """处理错误"""
        self.chat_widget.append_stream_chunk(f"\n\n❌ 出错了：{error_msg}")
        self.status_bar.showMessage("处理失败")
        self.worker_thread = None
    
    def handle_code_generation(self, file_path, code):
        """处理代码生成"""
        # 在聊天界面显示代码
        self.chat_widget.append_code_result(file_path, code)
        
        # 在代码编辑器中显示
        self.code_editor.set_content(code)
        self.code_editor.current_file = file_path
        
        # 切换到代码编辑器tab
        self.right_tabs.setCurrentWidget(self.code_editor)
    
    def run_current_code(self):
        """运行当前编辑器中的代码"""
        # 获取代码
        code = self.code_editor.get_content()
        if not code:
            QMessageBox.warning(self, "警告", "编辑器中没有代码！")
            return
        
        # 获取语言
        language = self.code_editor.language_combo.currentText()
        
        # 显示运行中消息
        self.chat_widget.append_message('assistant', f"正在运行 {language} 代码...\n")
        
        # 后台线程运行代码
        self.status_bar.showMessage("正在运行代码...")
        
        # TODO: 使用线程运行代码，实时显示结果
        # 目前先简单运行
        try:
            result = self.ide_service.execute_code(code, language)
            
            # 显示结果
            output = result.get('output', '')
            error = result.get('error', '')
            exit_code = result.get('exit_code', 0)
            
            result_text = ""
            if output:
                result_text += f"**输出：**\n```\n{output}\n```\n\n"
            if error:
                result_text += f"**错误：**\n```\n{error}\n```\n\n"
            result_text += f"退出码：{exit_code}"
            
            self.chat_widget.append_code_result("运行结果", code, output if output else error)
            
            self.status_bar.showMessage("代码运行完成")
        except Exception as e:
            self.chat_widget.append_message('assistant', f"❌ 运行失败：{str(e)}")
            self.status_bar.showMessage("代码运行失败")
    
    def open_file_in_editor(self, file_path):
        """在编辑器中打开文件"""
        self.code_editor.open_file(file_path)
        self.right_tabs.setCurrentWidget(self.code_editor)
    
    def set_project_path(self, path):
        """设置项目路径"""
        self.project_path = path
        self.project_browser.set_root_path(path)
        self.git_integration.set_project_path(path)


if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = IntelligentIDEPanel()
    window.setWindowTitle("LivingTree AI - 智能IDE")
    window.resize(1400, 900)
    window.show()
    sys.exit(app.exec())
