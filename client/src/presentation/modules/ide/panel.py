"""
Intelligent IDE Panel - Chat-Driven Development Environment (v3)
=================================================================
OpenCode + Serena 集成的智能编码 IDE

v3 强化：
- CodeTool v3 集成（自动写/测/修/发布流水线）
- SerenaAdapter 集成（LSP 诊断、符号导航、精准编辑）
- 流水线可视化面板
- Serena 连接状态指示器
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
    QProgressBar, QStatusBar, QFrame, QTextBrowser,
    QGroupBox, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QKeySequence, QShortcut, QColor

from client.src.business.ide_agent import IDEAgent
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
    pipeline_step = pyqtSignal(str, str, bool) # (step_name, detail, success) CodeTool 流水线步骤

    def __init__(self, agent, message, context=None):
        super().__init__()
        self.agent = agent
        self.message = message
        self.context = context or {}
        self._stop_requested = False

    def run(self):
        """执行AI聊天处理（流式输出）"""
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

            # CodeTool 流水线结果
            if response.get('type') == 'pipeline_result':
                steps = response.get('steps', [])
                for step in steps:
                    self.pipeline_step.emit(
                        step.get('name', ''),
                        step.get('detail', ''),
                        step.get('success', False),
                    )

            # 完成
            self.finished.emit(full_content or response.get('message', ''))

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.error_occurred.emit(f"{str(e)}\n\n{error_detail}")

    def stop(self):
        """停止处理"""
        self._stop_requested = True


class CodeExecutionThread(QThread):
    """后台线程执行代码（支持实时输出）"""
    output_line = pyqtSignal(str)           # 逐行输出
    error_line = pyqtSignal(str)            # 逐行错误
    finished = pyqtSignal(dict)             # 执行完成（结果字典）
    error_occurred = pyqtSignal(str)        # 错误

    def __init__(self, agent, code, language):
        super().__init__()
        self.agent = agent
        self.code = code
        self.language = language
        self._stop_requested = False

    def run(self):
        """执行代码"""
        try:
            # 定义回调函数
            def on_output_line(line: str):
                if self._stop_requested:
                    return
                self.output_line.emit(line)

            def on_error_line(line: str):
                if self._stop_requested:
                    return
                self.error_line.emit(line)

            def on_finished(result):
                if self._stop_requested:
                    return
                # 转换 ExecutionResult 为字典
                result_dict = {
                    "status": result.status.value,
                    "output": result.output,
                    "error": result.error,
                    "exit_code": result.exit_code,
                    "execution_time_ms": result.execution_time_ms,
                    "memory_usage_mb": result.memory_usage_mb,
                }
                self.finished.emit(result_dict)

            # 调用 agent.execute_code（传递回调）
            callbacks = {
                'on_output_line': on_output_line,
                'on_error_line': on_error_line,
                'on_finished': on_finished,
            }

            result = self.agent.execute_code(
                self.code,
                self.language,
                callbacks=callbacks,
            )

            # 如果没有触发回调，手动触发
            if result:
                self.finished.emit(result)

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.error_occurred.emit(f"{str(e)}\n\n{error_detail}")

    def stop(self):
        """停止执行"""
        self._stop_requested = True


class CodeEditorWidget(QWidget):
    """增强的代码编辑器组件（带语法高亮和代码补全）"""

    file_saved = pyqtSignal(str)  # 文件保存信号 (file_path)

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
        if not code.strip():
            return
        # 通过父面板发送请求到聊天
        parent = self.parent()
        if parent and hasattr(parent, 'chat_widget'):
            parent.chat_widget.append_message('user', f'解释当前编辑器中的代码')
            parent.handle_user_message(f'解释以下代码：\n```\n{code[:500]}\n```')

    def ai_debug(self):
        """AI调试代码"""
        code = self.get_content()
        if not code.strip():
            return
        parent = self.parent()
        if parent and hasattr(parent, 'chat_widget'):
            parent.chat_widget.append_message('user', f'调试当前编辑器中的代码')
            parent.handle_user_message(f'调试以下代码，找出错误：\n```\n{code[:500]}\n```')

    def ai_optimize(self):
        """AI优化代码"""
        code = self.get_content()
        if not code.strip():
            return
        parent = self.parent()
        if parent and hasattr(parent, 'chat_widget'):
            parent.chat_widget.append_message('user', f'优化当前编辑器中的代码')
            parent.handle_user_message(f'优化以下代码的性能和可读性：\n```\n{code[:500]}\n```')
    
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
            self.file_saved.emit(self.current_file)
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
    
    def _on_corrections_found(self, corrections: list):
        """
        检测到错别字时的处理
        
        Args:
            corrections: 错别字列表 [{"original":, "corrected":, ...}]
        """
        if corrections:
            print(f"[IDE拼写检查] 发现 {len(corrections)} 个疑似错别字")
        else:
            print("[IDE拼写检查] 未发现错别字")
    
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


class SerenaStatusBar(QFrame):
    """Serena 连接状态指示器"""

    status_changed = pyqtSignal(str)  # 状态变更信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = 'offline'
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #F44336; font-size: 14px;")
        layout.addWidget(self.status_dot)

        self.status_label = QLabel("Serena: 离线")
        self.status_label.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        self.diagnostic_label = QLabel("")
        self.diagnostic_label.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self.diagnostic_label)

        self.setStyleSheet("QFrame { background: #2d2d30; border-top: 1px solid #3e3e42; }")
        self.setMaximumHeight(28)

    def update_status(self, status: str, diagnostics_count: int = 0):
        """更新状态显示"""
        self._status = status
        colors = {
            'online': ('#4CAF50', 'Serena: 在线'),
            'offline': ('#F44336', 'Serena: 离线'),
            'fallback': ('#FF9800', 'Serena: AST Fallback'),
        }
        color, text = colors.get(status, ('#999', f'Serena: {status}'))
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")

        if diagnostics_count > 0:
            self.diagnostic_label.setText(f"⚠ {diagnostics_count} 个诊断")
            self.diagnostic_label.setStyleSheet("color: #FF9800; font-size: 11px;")
        else:
            self.diagnostic_label.setText("✓ 无诊断问题")
            self.diagnostic_label.setStyleSheet("color: #4CAF50; font-size: 11px;")

        self.status_changed.emit(status)


class SymbolNavigatorWidget(QWidget):
    """符号导航面板（基于 Serena 符号查找）"""

    symbol_requested = pyqtSignal(str, int)  # (symbol_name, line_number) 跳转到符号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # 工具栏
        toolbar = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setFixedHeight(28)
        self.refresh_btn.clicked.connect(self._on_refresh)
        toolbar.addWidget(self.refresh_btn)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("过滤符号...")
        self.filter_edit.setMaximumWidth(150)
        self.filter_edit.textChanged.connect(self._on_filter)
        toolbar.addWidget(self.filter_edit)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 符号树
        self.symbol_tree = QTreeWidget()
        self.symbol_tree.setHeaderLabels(["符号", "类型", "行"])
        self.symbol_tree.setColumnWidth(0, 200)
        self.symbol_tree.setColumnWidth(1, 80)
        self.symbol_tree.itemDoubleClicked.connect(self._on_symbol_double_clicked)
        self.symbol_tree.setStyleSheet("""
            QTreeWidget {
                background: #1e1e1e;
                color: #d4d4d4;
                border: none;
                font-size: 12px;
            }
            QTreeWidget::item:selected {
                background: #264f78;
            }
        """)
        layout.addWidget(self.symbol_tree)

        # 状态标签
        self.status_label = QLabel("打开文件后自动加载符号")
        self.status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.status_label)

    def load_symbols(self, symbols: list):
        """加载符号列表"""
        self.symbol_tree.clear()
        kind_icons = {
            'class': '📦', 'function': '⚡', 'method': '🔧',
            'variable': '📌', 'module': '📁',
        }
        for sym in symbols:
            name = sym.get('name', '')
            kind = sym.get('kind', '')
            line = sym.get('line_start', 0)
            icon = kind_icons.get(kind, '📄')
            item = QTreeWidgetItem([f"{icon} {name}", kind, str(line)])
            item.setData(0, Qt.ItemDataRole.UserRole, sym)
            self.symbol_tree.addTopLevelItem(item)
        self.status_label.setText(f"共 {len(symbols)} 个符号")

    def _on_refresh(self):
        """刷新符号列表"""
        self.symbol_tree.clear()
        self.status_label.setText("等待加载...")

    def _on_filter(self, text: str):
        """过滤符号"""
        text_lower = text.lower()
        for i in range(self.symbol_tree.topLevelItemCount()):
            item = self.symbol_tree.topLevelItem(i)
            name = item.text(0).lower()
            item.setHidden(text_lower not in name)

    def _on_symbol_double_clicked(self, item: QTreeWidgetItem, column: int):
        """双击符号跳转"""
        sym = item.data(0, Qt.ItemDataRole.UserRole)
        if sym:
            self.symbol_requested.emit(sym.get('name', ''), sym.get('line_start', 0))


class CodeToolPipelineWidget(QWidget):
    """CodeTool 流水线可视化面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 标题
        title = QLabel("⚙️ CodeTool v3 自动化流水线")
        title.setStyleSheet("color: #d4d4d4; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # 流水线步骤
        steps_layout = QVBoxLayout()
        steps_layout.setSpacing(4)

        step_configs = [
            ('write', '✏️ 自动写 (Auto-Write)', 'LLM 规划 → Serena 精准写入'),
            ('test', '🧪 自动测 (Auto-Test)', 'pytest 执行 → 错误分析 → 自动修复'),
            ('fix', '🔧 自动修 (Auto-Fix)', 'LSP 诊断 → LLM 修复 → 原子替换'),
            ('publish', '🚀 自动发布 (Auto-Publish)', 'git add/commit/push → CI/CD'),
        ]

        for step_id, name, desc in step_configs:
            step_widget = self._create_step_widget(step_id, name, desc)
            self._steps[step_id] = step_widget
            steps_layout.addWidget(step_widget)

        layout.addLayout(steps_layout)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #3e3e42;")
        layout.addWidget(line)

        # 操作按钮
        btn_layout = QHBoxLayout()

        self.scan_btn = QPushButton("📊 扫描项目")
        self.scan_btn.clicked.connect(lambda: self._emit_action('scan'))
        self.scan_btn.setStyleSheet(self._btn_style("#0e639c"))
        btn_layout.addWidget(self.scan_btn)

        self.plan_btn = QPushButton("📋 规划代码")
        self.plan_btn.clicked.connect(lambda: self._emit_action('plan'))
        self.plan_btn.setStyleSheet(self._btn_style("#0e639c"))
        btn_layout.addWidget(self.plan_btn)

        self.full_pipeline_btn = QPushButton("⚡ 全流水线")
        self.full_pipeline_btn.clicked.connect(lambda: self._emit_action('full_pipeline'))
        self.full_pipeline_btn.setStyleSheet(self._btn_style("#4CAF50"))
        btn_layout.addWidget(self.full_pipeline_btn)

        layout.addLayout(btn_layout)

        # 日志区域
        log_label = QLabel("📜 执行日志")
        log_label.setStyleSheet("color: #999; font-size: 11px; margin-top: 8px;")
        layout.addWidget(log_label)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(200)
        self.log_view.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                font-family: Consolas;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.log_view)

        layout.addStretch()

    def _create_step_widget(self, step_id: str, name: str, desc: str) -> QFrame:
        """创建单个步骤组件"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #2d2d30;
                border: 1px solid #3e3e42;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        header = QHBoxLayout()
        status_label = QLabel("⬜")
        status_label.setStyleSheet("font-size: 14px;")
        header.addWidget(status_label)

        name_label = QLabel(name)
        name_label.setStyleSheet("color: #d4d4d4; font-size: 13px; font-weight: bold;")
        header.addWidget(name_label)
        header.addStretch()
        layout.addLayout(header)

        desc_label = QLabel(desc)
        desc_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(desc_label)

        # 存储引用
        frame.status_label = status_label
        frame.desc_label = desc_label
        frame.step_id = step_id

        return frame

    def _btn_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {color}cc;
            }}
        """

    def set_step_status(self, step_id: str, status: str, detail: str = ""):
        """更新步骤状态"""
        widget = self._steps.get(step_id)
        if not widget:
            return

        status_map = {
            'pending': ('⬜', '#888'),
            'running': ('🔄', '#FF9800'),
            'success': ('✅', '#4CAF50'),
            'error': ('❌', '#F44336'),
        }
        icon, color = status_map.get(status, ('⬜', '#888'))
        widget.status_label.setText(icon)
        widget.status_label.setStyleSheet(f"font-size: 14px;")

        if detail:
            widget.desc_label.setText(detail)
            widget.desc_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def append_log(self, message: str):
        """追加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{timestamp}] {message}")
        # 自动滚动
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_pipeline(self):
        """重置流水线状态"""
        for step_id in self._steps:
            self.set_step_status(step_id, 'pending')
        self.log_view.clear()

    def _emit_action(self, action: str):
        """发射操作信号（由父面板处理）"""
        if hasattr(self.parent(), f'on_pipeline_{action}'):
            getattr(self.parent(), f'on_pipeline_{action}')()


class IntelligentIDEPanel(QWidget):
    """
    智能IDE面板 - Chat-Driven Development Environment (v3)

    v3 强化：
    - CodeTool 流水线 Tab（Auto-Write/Test/Fix/Publish）
    - Serena 状态指示器
    - 符号导航面板
    - LSP 实时诊断

    布局：
    - 默认显示：聊天框（左侧或全屏）
    - 代码编辑器：作为tab页
    - 符号导航、流水线、项目浏览器、搜索、测试、Git：作为tab页
    """

    def __init__(self, parent=None, project_path=None):
        super().__init__(parent)
        self.project_path = project_path or os.getcwd()
        self.ide_agent = IDEAgent()
        self.ide_service = IntelligentIDEService()
        self.worker_thread = None
        self._diagnostics_timer = None
        self.init_ui()
        self._init_serena_diagnostics()

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

        # 右侧：标签页界面（代码编辑器 + 工具）
        self.right_tabs = QTabWidget()
        self.right_tabs.setTabPosition(QTabWidget.TabPosition.North)

        # Tab 1: 代码编辑器
        self.code_editor = CodeEditorWidget(self)
        self.code_editor.file_saved.connect(self._on_file_saved)
        self.right_tabs.addTab(self.code_editor, "📝 代码编辑器")

        # Tab 2: 符号导航（v3: Serena）
        self.symbol_navigator = SymbolNavigatorWidget()
        self.symbol_navigator.symbol_requested.connect(self._jump_to_symbol)
        self.right_tabs.addTab(self.symbol_navigator, "🧭 符号导航")

        # Tab 3: CodeTool 流水线（v3）
        self.pipeline_widget = CodeToolPipelineWidget()
        self.right_tabs.addTab(self.pipeline_widget, "⚙️ 流水线")

        # Tab 4: 项目浏览器
        self.project_browser = ProjectBrowser(self.project_path)
        self.project_browser.file_opened.connect(self.open_file_in_editor)
        self.right_tabs.addTab(self.project_browser, "📂 项目浏览器")

        # Tab 5: 全局搜索
        self.global_search = GlobalSearchWidget()
        self.global_search.file_opened.connect(self.open_file_in_editor)
        self.right_tabs.addTab(self.global_search, "🔍 全局搜索")

        # Tab 6: 测试集成
        self.test_integration = TestIntegrationWidget()
        self.right_tabs.addTab(self.test_integration, "🧪 测试")

        # Tab 7: Git集成
        self.git_integration = GitIntegrationWidget(self.project_path)
        self.right_tabs.addTab(self.git_integration, "🔧 Git")

        self.main_splitter.addWidget(self.right_tabs)

        # 设置分割器比例（聊天框占2/3，右侧占1/3）
        self.main_splitter.setStretchFactor(0, 2)
        self.main_splitter.setStretchFactor(1, 1)

        layout.addWidget(self.main_splitter)

        # Serena 状态栏（v3）
        self.serena_status_bar = SerenaStatusBar()
        layout.addWidget(self.serena_status_bar)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪 - 输入需求，我会自动生成代码")
        layout.addWidget(self.status_bar)

        self.setLayout(layout)

        # 连接运行代码信号
        self.chat_widget.run_code_requested.connect(self.run_current_code)

        # 添加欢迎消息
        self.add_welcome_message()

    def _init_serena_diagnostics(self):
        """初始化 Serena 诊断定时器"""
        serena_status = self.ide_agent.get_serena_status()
        self.serena_status_bar.update_status(serena_status)

        # 定时诊断（每 10 秒检查当前文件）
        self._diagnostics_timer = QTimer(self)
        self._diagnostics_timer.timeout.connect(self._run_diagnostics)
        self._diagnostics_timer.start(10000)

    def _run_diagnostics(self):
        """后台定时运行 LSP 诊断"""
        if not self.code_editor.current_file:
            return

        try:
            diagnostics = self.ide_agent.get_serena_diagnostics(
                self.code_editor.current_file
            )
            error_count = sum(1 for d in diagnostics if d.get('severity') == 'error')
            warning_count = sum(1 for d in diagnostics if d.get('severity') == 'warning')
            self.serena_status_bar.update_status(
                self.ide_agent.get_serena_status(),
                error_count + warning_count
            )
        except Exception:
            pass  # 静默失败，不影响 UI

    def _on_file_saved(self, file_path: str):
        """文件保存后触发诊断和符号刷新"""
        # 触发诊断
        QTimer.singleShot(500, self._run_diagnostics)

        # 刷新符号导航
        QTimer.singleShot(800, self._refresh_symbols)

    def _refresh_symbols(self):
        """刷新符号导航面板"""
        if not self.code_editor.current_file:
            return

        symbols = self.ide_agent.get_file_symbols(self.code_editor.current_file)
        self.symbol_navigator.load_symbols(symbols)

        # 如果在符号导航 tab，自动切换
        if self.right_tabs.currentWidget() == self.symbol_navigator:
            pass  # 已经在符号导航页面

    def _jump_to_symbol(self, symbol_name: str, line_number: int):
        """跳转到指定行"""
        if line_number > 0:
            cursor = self.code_editor.editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.MoveAnchor,
                line_number - 1
            )
            self.code_editor.editor.setTextCursor(cursor)
            self.code_editor.editor.setFocus()
            self.right_tabs.setCurrentWidget(self.code_editor)

    def add_welcome_message(self):
        """添加欢迎消息"""
        welcome_msg = """
你好！我是你的 AI 编程助手 (v3)。

🎯 我可以帮你：
• **生成代码** — 创建新模块、类、函数
• **修改代码** — 精准修改现有文件（Serena 符号级编辑）
• **自动测试** — 运行测试 → 自动修复失败（最多 3 轮）
• **自动修复** — LSP 诊断 → LLM 修复 → 原子替换
• **自动发布** — git add/commit/push → CI/CD
• **代码规划** — LLM 生成结构化实施计划
• **项目扫描** — 分析项目结构（文件/类/函数统计）

🔧 v3 新增：
• CodeTool 流水线：右侧 ⚙️ 流水线 Tab
• 符号导航：右侧 🧭 符号导航 Tab（Serena LSP）
• 实时诊断：底部状态栏

💡 示例指令：
• "创建一个用户认证模块"
• "测试这个项目"
• "修复所有代码错误"
• "帮我规划重构数据库模块"
• "扫描项目结构"
        """
        self.chat_widget.append_message('assistant', welcome_msg.strip())

    # ── 消息处理 ──

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
        self.worker_thread.pipeline_step.connect(self.handle_pipeline_step)
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
        self.pipeline_widget.append_log(f"▶ {name}: {params[:80]}")

    def handle_tool_result(self, name: str, result: str, success: bool):
        """处理工具结果"""
        # 更新聊天中的工具调用
        if self.chat_widget.current_assistant_bubble and self.chat_widget.current_assistant_bubble.tool_widgets:
            tool_widget = self.chat_widget.current_assistant_bubble.tool_widgets[-1]
            tool_widget.set_result(result, success)

        # 更新流水线日志
        icon = "✅" if success else "❌"
        self.pipeline_widget.append_log(f"{icon} {name}: {result[:100]}")

    def handle_pipeline_step(self, step_name: str, detail: str, success: bool):
        """处理流水线步骤"""
        step_id = step_name.lower().replace('codetool.', '').replace('.', '_')
        status = 'success' if success else 'error'
        self.pipeline_widget.set_step_status(step_id, status, detail)

    def handle_finished(self, full_content: str):
        """处理完成"""
        self.chat_widget.finalize_message()
        self.status_bar.showMessage("就绪")

    def handle_error(self, error_msg):
        """处理错误"""
        self.chat_widget.append_stream_chunk(f"\n\n❌ 出错了：{error_msg}")
        self.status_bar.showMessage("处理失败")
        self.pipeline_widget.append_log(f"❌ 错误: {error_msg[:100]}")
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

        # 刷新符号导航
        QTimer.singleShot(500, self._refresh_symbols)

    # ── 流水线操作 ──

    def on_pipeline_scan(self):
        """扫描项目"""
        self.pipeline_widget.clear_pipeline()
        self.pipeline_widget.set_step_status('write', 'running', '正在扫描...')
        self.status_bar.showMessage("正在扫描项目...")

        self.worker_thread = ChatMessageThread(
            self.ide_agent, "扫描项目结构",
            context={'project_path': self.project_path}
        )
        self.worker_thread.tool_start.connect(self.handle_tool_start)
        self.worker_thread.tool_result.connect(self.handle_tool_result)
        self.worker_thread.finished.connect(self.handle_finished)
        self.worker_thread.error_occurred.connect(self.handle_error)
        self.worker_thread.start()

    def on_pipeline_plan(self):
        """规划代码"""
        self.pipeline_widget.clear_pipeline()
        self.status_bar.showMessage("正在规划...")

        instruction, ok = QInputDialog.getText(
            self, "代码规划", "输入规划指令：",
            text="分析当前项目并生成重构计划"
        )
        if ok and instruction:
            self.worker_thread = ChatMessageThread(
                self.ide_agent, instruction,
                context={'project_path': self.project_path}
            )
            self.worker_thread.chunk_received.connect(self.handle_stream_chunk)
            self.worker_thread.tool_start.connect(self.handle_tool_start)
            self.worker_thread.tool_result.connect(self.handle_tool_result)
            self.worker_thread.finished.connect(self.handle_finished)
            self.worker_thread.error_occurred.connect(self.handle_error)
            self.worker_thread.start()

    def on_pipeline_full_pipeline(self):
        """执行全流水线：Write → Test → Fix → Publish"""
        self.pipeline_widget.clear_pipeline()
        self.pipeline_widget.append_log("🚀 启动全流水线: Write → Test → Fix → Publish")
        self.chat_widget.append_message('assistant', '🚀 启动全流水线...\n')

        instruction, ok = QInputDialog.getText(
            self, "全流水线", "输入开发指令：",
            text=""
        )
        if ok and instruction:
            self.status_bar.showMessage("全流水线执行中...")
            # 使用 CodeTool 直接执行
            if self.ide_agent._ensure_code_tool():
                try:
                    # Step 1: Write
                    self.pipeline_widget.set_step_status('write', 'running', '正在生成代码...')
                    result = self.ide_agent._code_tool.execute(
                        action='write', instruction=instruction,
                        project_path=self.project_path
                    )
                    if result.success:
                        self.pipeline_widget.set_step_status(
                            'write', 'success',
                            f"完成 ({len(result.data.get('files_created', []))} 文件)"
                        )
                    else:
                        self.pipeline_widget.set_step_status('write', 'error', result.error)

                    # Step 2: Test
                    self.pipeline_widget.set_step_status('test', 'running', '正在运行测试...')
                    result = self.ide_agent._code_tool.execute(
                        action='test', project_path=self.project_path
                    )
                    if result.success:
                        data = result.data
                        self.pipeline_widget.set_step_status(
                            'test', 'success',
                            f"通过 {data.get('tests_passed', 0)}/{data.get('tests_total', 0)}"
                        )
                    else:
                        self.pipeline_widget.set_step_status('test', 'error', result.error)

                    # Step 3: Fix
                    self.pipeline_widget.set_step_status('fix', 'running', '正在修复...')
                    result = self.ide_agent._code_tool.execute(
                        action='fix', project_path=self.project_path
                    )
                    if result.success:
                        self.pipeline_widget.set_step_status(
                            'fix', 'success',
                            f"修复 {len(result.data.get('files_fixed', []))} 文件"
                        )
                    else:
                        self.pipeline_widget.set_step_status('fix', 'error', result.error)

                    self.pipeline_widget.append_log("✅ 流水线执行完成")
                    self.status_bar.showMessage("流水线执行完成")
                    self.chat_widget.append_stream_chunk("\n✅ 流水线执行完成！查看右侧 ⚙️ 流水线 Tab 了解详情。")
                    self.chat_widget.finalize_message()

                except Exception as e:
                    self.pipeline_widget.append_log(f"❌ 流水线失败: {e}")
                    self.chat_widget.append_stream_chunk(f"\n❌ 流水线失败: {e}")
                    self.chat_widget.finalize_message()
            else:
                self.chat_widget.append_stream_chunk("\n❌ CodeTool v3 不可用")
                self.chat_widget.finalize_message()

    # ── 代码执行 ──

    def run_current_code(self):
        """运行当前编辑器中的代码（支持实时输出）"""
        code = self.code_editor.get_content()
        if not code:
            QMessageBox.warning(self, "警告", "编辑器中没有代码！")
            return

        language = self.code_editor.language_combo.currentText()
        self.chat_widget.append_message('assistant', f"正在运行 {language} 代码...\n")
        self.status_bar.showMessage("正在运行代码...")

        self.worker_thread = CodeExecutionThread(
            self.ide_agent, code, language,
        )
        self.worker_thread.output_line.connect(self.handle_code_output_line)
        self.worker_thread.error_line.connect(self.handle_code_error_line)
        self.worker_thread.finished.connect(self.handle_code_execution_finished)
        self.worker_thread.error_occurred.connect(self.handle_code_error)
        self.worker_thread.start()

    def handle_code_output_line(self, line: str):
        self.chat_widget.append_stream_chunk(line)

    def handle_code_error_line(self, line: str):
        self.chat_widget.append_stream_chunk(f"❌ {line}")

    def handle_code_execution_finished(self, result: dict):
        output = result.get('output', '')
        error = result.get('error', '')
        exit_code = result.get('exit_code', 0)
        execution_time_ms = result.get('execution_time_ms', 0)

        result_text = ""
        if output:
            result_text += f"\n\n**输出：**\n```\n{output}\n```\n\n"
        if error:
            result_text += f"\n\n**错误：**\n```\n{error}\n```\n\n"
        result_text += f"\n退出码：{exit_code}"
        result_text += f"\n执行时间：{execution_time_ms:.2f} ms"

        self.chat_widget.append_stream_chunk(result_text)
        self.chat_widget.finalize_message()
        self.status_bar.showMessage("就绪")
        self.worker_thread = None

    def handle_code_error(self, error_msg):
        self.chat_widget.append_stream_chunk(f"\n\n❌ 运行失败：{error_msg}")
        self.chat_widget.finalize_message()
        self.status_bar.showMessage("运行失败")
        self.worker_thread = None

    # ── 文件操作 ──

    def open_file_in_editor(self, file_path):
        """在编辑器中打开文件"""
        self.code_editor.open_file(file_path)
        self.right_tabs.setCurrentWidget(self.code_editor)

        # 刷新符号导航
        QTimer.singleShot(300, self._refresh_symbols)

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
    window.setWindowTitle("LivingTree AI - 智能IDE v3")
    window.resize(1400, 900)
    window.show()
    sys.exit(app.exec())
