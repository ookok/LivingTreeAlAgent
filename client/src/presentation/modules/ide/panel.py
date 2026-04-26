"""
Intelligent IDE Panel - Chat-Driven Development Environment
默认显示聊天框，AI根据用户输入生成/修改代码，代码编辑器作为tab页
"""
import os
import json
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
    """后台线程处理AI聊天请求"""
    message_received = pyqtSignal(str, str)  # (role, content)
    code_generated = pyqtSignal(str, str)   # (file_path, code)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, agent, message, context=None):
        super().__init__()
        self.agent = agent
        self.message = message
        self.context = context or {}
    
    def run(self):
        try:
            # 调用AI agent处理用户请求
            response = self.agent.process_chat_message(self.message, self.context)
            
            # 检查是否需要生成/修改代码
            if response.get('type') == 'code_generation':
                file_path = response.get('file_path', '')
                code = response.get('code', '')
                self.code_generated.emit(file_path, code)
            
            self.message_received.emit('assistant', response.get('message', ''))
        except Exception as e:
            self.error_occurred.emit(str(e))


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


class ChatWidget(QWidget):
    """聊天界面组件"""
    
    message_sent = pyqtSignal(str)  # 发送消息信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.message_history = []
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 聊天历史显示区域
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont('Microsoft YaHei', 11))
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                padding: 10px;
            }
        """)
        layout.addWidget(self.chat_display, 1)
        
        # 输入区域
        input_layout = QHBoxLayout()
        
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
    
    def append_message(self, role, content):
        """添加消息到聊天历史"""
        self.message_history.append({'role': role, 'content': content})
        
        # 格式化显示
        if role == 'user':
            prefix = '<p style="color: #569cd6;"><b>👤 你：</b></p>'
            color = '#d4d4d4'
        else:
            prefix = '<p style="color: #4ec9b0;"><b>🤖 助手：</b></p>'
            color = '#d4d4d4'
        
        formatted_content = content.replace('\n', '<br>')
        message_html = f'{prefix}<p style="color: {color}; margin-left: 20px;">{formatted_content}</p><hr style="border-color: #3e3e42;">'
        
        self.chat_display.append(message_html)
        
        # 滚动到底部
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def append_code(self, file_path, code):
        """添加生成的代码到聊天历史"""
        code_html = f'''
        <p style="color: #4ec9b0;"><b>🤖 助手：</b></p>
        <p style="color: #d4d4d4; margin-left: 20px;">
            已生成代码：<b>{file_path}</b>
        </p>
        <pre style="background-color: #252526; color: #d4d4d4; padding: 10px; border-radius: 5px; overflow-x: auto;">{code}</pre>
        <hr style="border-color: #3e3e42;">
        '''
        self.chat_display.append(code_html)
        
        # 滚动到底部
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


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
        
        # 后台线程处理AI请求
        self.worker_thread = ChatMessageThread(
            self.ide_agent,
            message,
            context={'project_path': self.project_path}
        )
        self.worker_thread.message_received.connect(self.handle_ai_response)
        self.worker_thread.code_generated.connect(self.handle_code_generation)
        self.worker_thread.error_occurred.connect(self.handle_error)
        self.worker_thread.finished.connect(self.on_process_finished)
        self.worker_thread.start()
    
    def handle_ai_response(self, role, content):
        """处理AI响应"""
        self.chat_widget.append_message(role, content)
    
    def handle_code_generation(self, file_path, code):
        """处理代码生成"""
        # 在聊天界面显示代码
        self.chat_widget.append_code(file_path, code)
        
        # 在代码编辑器中显示
        self.code_editor.set_content(code)
        self.code_editor.current_file = file_path
        
        # 切换到代码编辑器tab
        self.right_tabs.setCurrentWidget(self.code_editor)
    
    def handle_error(self, error_msg):
        """处理错误"""
        self.chat_widget.append_message('assistant', f"❌ 出错了：{error_msg}")
        self.status_bar.showMessage("处理失败")
    
    def on_process_finished(self):
        """处理完成"""
        self.status_bar.showMessage("就绪")
        self.worker_thread = None
    
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
