"""
IDE聊天面板 - 针对项目代码库进行分析

功能特性：
1. 专门针对项目代码库进行分析
2. 支持代码文件分析和理解
3. 支持代码搜索和导航
4. 与通用聊天面板同步更新
5. 支持代码补全和建议
"""

import os
import ast
from typing import Optional, List, Dict, Any
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QLabel, QScrollArea, QFrame,
    QToolButton, QMenu, QSplitter, QTreeWidget,
    QTreeWidgetItem, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QTimer, QMimeData
from PyQt6.QtGui import QTextCursor, QDragEnterEvent, QDropEvent, QIcon

from business.nanochat_config import config
from presentation.components.markdown_renderer import MarkdownRenderer
from presentation.components.code_highlighter import CodeHighlighterWidget
from presentation.components.command_palette import CommandPalette


class CodeAnalyzer:
    """代码分析器 - 分析项目代码结构"""
    
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.files = []
        self.analyze_project()
    
    def analyze_project(self):
        """分析项目结构"""
        if not os.path.exists(self.project_path):
            return
        
        for root, dirs, files in os.walk(self.project_path):
            # 排除隐藏目录和虚拟环境
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'venv', '.venv']]
            
            for file in files:
                # 只关注代码文件
                if file.endswith(('.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css')):
                    self.files.append(os.path.relpath(os.path.join(root, file), self.project_path))
    
    def get_files_by_type(self, extension: str) -> List[str]:
        """按类型获取文件"""
        return [f for f in self.files if f.endswith(extension)]
    
    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """分析单个文件"""
        full_path = os.path.join(self.project_path, file_path)
        
        if not os.path.exists(full_path):
            return {"error": "文件不存在"}
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            result = {
                "path": file_path,
                "lines": len(content.splitlines()),
                "size": os.path.getsize(full_path)
            }
            
            if file_path.endswith('.py'):
                result.update(self._analyze_python_file(content))
            
            return result
        
        except Exception as e:
            return {"error": str(e)}
    
    def _analyze_python_file(self, content: str) -> Dict[str, Any]:
        """分析Python文件"""
        try:
            tree = ast.parse(content)
            
            classes = []
            functions = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append({
                        "name": node.name,
                        "line": node.lineno,
                        "docstring": ast.get_docstring(node)
                    })
                elif isinstance(node, ast.FunctionDef):
                    functions.append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": [arg.arg for arg in node.args.args],
                        "docstring": ast.get_docstring(node)
                    })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imports.append(f"{node.module}.{alias.name}")
            
            return {
                "classes": classes,
                "functions": functions,
                "imports": imports
            }
        
        except SyntaxError:
            return {}


class IDEPanel(QWidget):
    """IDE聊天面板 - 针对代码库分析"""
    
    message_sent = pyqtSignal(str)
    file_selected = pyqtSignal(str)
    
    def __init__(self, project_path: str = "", parent=None):
        super().__init__(parent)
        self.project_path = project_path
        self.code_analyzer = CodeAnalyzer(project_path)
        self.messages: List[Dict] = [
            {"role": "system", "content": f"你是代码分析助手，正在分析项目: {project_path}"}
        ]
        
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 主分割器
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：文件树
        self.file_tree_panel = QFrame()
        self.file_tree_panel.setFixedWidth(250)
        self._setup_file_tree()
        self.splitter.addWidget(self.file_tree_panel)
        
        # 右侧：聊天区域
        chat_container = QWidget()
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题栏
        title_bar = QFrame()
        title_bar.setFixedHeight(52)
        title_bar.setStyleSheet("background: #2d2d44; border-bottom: 1px solid #3d3d54;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)
        
        title_label = QLabel("💻 IDE 代码分析")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        title_layout.addWidget(title_label)
        
        # 项目选择按钮
        self.project_btn = QToolButton()
        self.project_btn.setText("📂 选择项目")
        self.project_btn.setStyleSheet("""
            QToolButton {
                color: #93c5fd;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
        """)
        self.project_btn.clicked.connect(self._select_project)
        title_layout.addWidget(self.project_btn)
        
        title_layout.addStretch()
        chat_layout.addWidget(title_bar)
        
        # 消息区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: #1e293b; }")
        
        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(16, 16, 16, 16)
        self.messages_layout.addStretch()
        
        self.scroll_area.setWidget(self.messages_container)
        chat_layout.addWidget(self.scroll_area, 1)
        
        # 输入区域
        input_frame = QFrame()
        input_frame.setStyleSheet("background: #2d2d44; border-top: 1px solid #3d3d54;")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(16, 12, 16, 12)
        
        # 文件拖拽区域
        self.drop_zone = QFrame()
        self.drop_zone.setFixedWidth(40)
        self.drop_zone.setStyleSheet("""
            QFrame {
                background-color: #3d3d54;
                border: 2px dashed #475569;
                border-radius: 8px;
            }
        """)
        drop_label = QLabel("📁")
        drop_label.setStyleSheet("font-size: 20px;")
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        drop_layout = QVBoxLayout(self.drop_zone)
        drop_layout.addWidget(drop_label)
        
        # 启用拖拽
        self.drop_zone.setAcceptDrops(True)
        self.drop_zone.dragEnterEvent = self._on_drag_enter
        self.drop_zone.dropEvent = self._on_drop
        
        input_layout.addWidget(self.drop_zone)
        
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("输入代码分析问题... (输入 / 查看命令)")
        self.input_field.setMaximumHeight(100)
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: #1e293b;
                color: #e2e8f0;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }
        """)
        self.input_field.keyPressEvent = self._on_input_key_press
        input_layout.addWidget(self.input_field, 1)
        
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(80, 40)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:disabled { background: #475569; }
        """)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)
        
        chat_layout.addWidget(input_frame)
        
        self.splitter.addWidget(chat_container)
        layout.addWidget(self.splitter)
    
    def _setup_file_tree(self):
        """设置文件树"""
        layout = QVBoxLayout(self.file_tree_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题
        title_label = QLabel("📁 项目文件")
        title_label.setStyleSheet("""
            QLabel {
                background-color: #3d3d54;
                color: white;
                padding: 8px 12px;
                font-weight: bold;
            }
        """)
        layout.addWidget(title_label)
        
        # 文件树
        self.file_tree = QTreeWidget()
        self.file_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #2d2d44;
                color: #e2e8f0;
                border: none;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:hover {
                background-color: #3d3d54;
            }
            QTreeWidget::branch:open {
                image: url(:/icons/arrow_down.png);
            }
            QTreeWidget::branch:closed {
                image: url(:/icons/arrow_right.png);
            }
        """)
        self.file_tree.setHeaderHidden(True)
        self.file_tree.itemDoubleClicked.connect(self._on_file_double_clicked)
        
        layout.addWidget(self.file_tree)
        
        # 加载文件
        self._load_files()
    
    def _load_files(self):
        """加载文件到树"""
        self.file_tree.clear()
        
        if not self.code_analyzer.files:
            return
        
        # 按目录组织文件
        file_tree = {}
        
        for file in self.code_analyzer.files:
            parts = file.split(os.sep)
            current = file_tree
            
            for i, part in enumerate(parts):
                if part not in current:
                    current[part] = {} if i < len(parts) - 1 else None
                current = current[part]
        
        # 添加到树
        def add_items(parent, tree_dict, path=""):
            for name, children in sorted(tree_dict.items()):
                full_path = os.path.join(path, name) if path else name
                
                item = QTreeWidgetItem(parent)
                item.setText(0, name)
                
                # 设置图标
                if children is None:
                    # 文件
                    ext = os.path.splitext(name)[1]
                    icons = {'.py': '🐍', '.js': '📜', '.ts': '📘', '.html': '🌐', '.css': '🎨'}
                    item.setText(0, f"{icons.get(ext, '📄')} {name}")
                else:
                    # 目录
                    item.setText(0, f"📁 {name}")
                    add_items(item, children, full_path)
        
        add_items(self.file_tree.invisibleRootItem(), file_tree)
    
    def _select_project(self):
        """选择项目目录"""
        path = QFileDialog.getExistingDirectory(self, "选择项目目录")
        if path:
            self.project_path = path
            self.code_analyzer = CodeAnalyzer(path)
            self._load_files()
            self._add_system_message(f"已切换到项目: {path}")
    
    def _on_file_double_clicked(self, item: QTreeWidgetItem, column: int):
        """双击文件"""
        # 获取文件路径
        path_parts = []
        current = item
        while current:
            path_parts.insert(0, current.text(0).replace('🐍 ', '').replace('📜 ', '').replace('📘 ', '').replace('🌐 ', '').replace('🎨 ', '').replace('📄 ', '').replace('📁 ', ''))
            current = current.parent()
        
        file_path = os.path.join(*path_parts)
        
        # 分析文件并显示
        analysis = self.code_analyzer.analyze_file(file_path)
        self._show_file_analysis(file_path, analysis)
    
    def _show_file_analysis(self, file_path: str, analysis: Dict[str, Any]):
        """显示文件分析结果"""
        if "error" in analysis:
            self._add_system_message(f"❌ {analysis['error']}")
            return
        
        content = f"## 文件分析: `{file_path}`\n\n"
        content += f"- **行数**: {analysis.get('lines', 0)}\n"
        content += f"- **大小**: {self._format_size(analysis.get('size', 0))}\n"
        
        if "classes" in analysis and analysis["classes"]:
            content += f"\n### 类 ({len(analysis['classes'])}个)\n"
            for cls in analysis["classes"]:
                content += f"- `{cls['name']}` (第{cls['line']}行)\n"
        
        if "functions" in analysis and analysis["functions"]:
            content += f"\n### 函数 ({len(analysis['functions'])}个)\n"
            for func in analysis["functions"]:
                args = ", ".join(func["args"])
                content += f"- `{func['name']}({args})` (第{func['line']}行)\n"
        
        if "imports" in analysis and analysis["imports"]:
            content += f"\n### 导入\n"
            for imp in analysis["imports"][:10]:
                content += f"- `{imp}`\n"
        
        self._add_message("assistant", content)
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
    
    def _on_drag_enter(self, event: QDragEnterEvent):
        """拖拽进入"""
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
    
    def _on_drop(self, event: QDropEvent):
        """放置文件"""
        mime_data = event.mimeData()
        
        if mime_data.hasUrls():
            for url in mime_data.urls():
                file_path = url.toLocalFile()
                if os.path.isfile(file_path):
                    self._handle_dropped_file(file_path)
        
        event.acceptProposedAction()
    
    def _handle_dropped_file(self, file_path: str):
        """处理拖放的文件"""
        if file_path.endswith('.py'):
            # 分析Python文件
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self._add_message("user", f"分析文件: `{os.path.basename(file_path)}`")
            
            # 显示代码
            self._add_code_content(content, "python")
    
    def _add_code_content(self, code: str, language: str):
        """添加代码内容"""
        # 创建代码高亮控件
        code_widget = CodeHighlighterWidget()
        code_widget.set_code(code)
        code_widget.set_language(language)
        
        # 添加到消息区域
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, code_widget)
        self._scroll_to_bottom()
    
    def _on_input_key_press(self, event):
        """处理输入框按键"""
        from PyQt6.QtGui import QKeyEvent
        if isinstance(event, QKeyEvent):
            if event.key() in (16777221, 16777220) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send_message()
                return
        
        QTextEdit.keyPressEvent(self.input_field, event)
    
    def _send_message(self):
        """发送消息"""
        text = self.input_field.toPlainText().strip()
        if not text:
            return
        
        self._add_message("user", text)
        self.messages.append({"role": "user", "content": text})
        self.input_field.clear()
        
        # 简单模拟AI响应（实际应调用LLM）
        QTimer.singleShot(1000, lambda: self._simulate_response(text))
    
    def _simulate_response(self, query: str):
        """模拟AI响应"""
        # 根据查询类型生成响应
        if "分析" in query or "代码" in query or "函数" in query:
            response = f"我来帮你分析这个代码问题。\n\n**分析要点：**\n\n1. 需要理解代码的整体结构\n2. 识别关键函数和类\n3. 分析潜在问题和优化建议\n\n**建议步骤：**\n- 先查看文件结构\n- 理解核心逻辑\n- 识别改进空间"
        elif "bug" in query or "错误" in query:
            response = "让我帮你查找潜在的bug。常见的Python错误包括：\n\n- 索引越界\n- 类型错误\n- 未定义变量\n- 逻辑错误\n\n请提供具体的代码或错误信息。"
        elif "优化" in query or "性能" in query:
            response = "性能优化建议：\n\n1. **减少循环次数** - 使用列表推导式代替显式循环\n2. **使用高效数据结构** - 字典查找比列表更快\n3. **避免重复计算** - 缓存中间结果\n4. **使用内置函数** - 如 map(), filter(), sum() 等"
        else:
            response = f"收到你的请求：`{query}`\n\n我可以帮你分析项目代码、查找bug、提供优化建议等。\n\n**可用命令：**\n- `/analyze <文件>` - 分析文件\n- `/search <关键词>` - 搜索代码\n- `/explain <代码片段>` - 解释代码"
        
        self._add_message("assistant", response)
    
    def _add_message(self, role: str, content: str):
        """添加消息"""
        # 创建消息气泡
        bubble = QFrame()
        bubble.setStyleSheet("""
            QFrame {
                background-color: #3d3d54;
                border-radius: 12px;
                padding: 12px;
                margin: 8px 0;
            }
        """)
        
        layout = QVBoxLayout(bubble)
        
        # 角色标签
        role_label = QLabel("🧑 用户" if role == "user" else "🤖 代码助手")
        role_label.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: bold;")
        layout.addWidget(role_label)
        
        # 内容
        renderer = MarkdownRenderer()
        content_widget = renderer.render(content)
        layout.addWidget(content_widget)
        
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        self._scroll_to_bottom()
    
    def _add_system_message(self, content: str):
        """添加系统消息"""
        label = QLabel(content)
        label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #94a3b8;
                text-align: center;
                padding: 8px;
                background-color: #3d3d54;
                border-radius: 4px;
                margin: 4px 0;
            }
        """)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, label)
        self._scroll_to_bottom()
    
    def _scroll_to_bottom(self):
        """滚动到底部"""
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))
    
    def sync_with_main_panel(self, message: str):
        """与主聊天面板同步消息"""
        self._add_message("user", f"同步消息: {message}")