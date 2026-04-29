"""
聊天模块 - 集成UI描述符协议的智能对话面板

功能特性：
1. 支持输入框通过"/"命令调用各功能模块
2. 支持需求澄清的渐进式UI渲染，与用户交互
3. 支持查看技能和专家角色
4. AI返回消息以Markdown形式渲染，形式优美，重点突出
5. 集成UI描述符协议，支持动态UI组件生成
6. 文件/URL预览：图片、音频、视频、Office文档、MD、Wiki等
7. 向量数据库集成：存储和检索工具、技能、专家角色
8. 代码高亮渲染
9. 流式思考动画效果
10. 任务显示：支持子任务展开和详情查看
11. 文件拖拽支持
12. 语音输入和回放
13. 功能模块知识库集成
"""

import json
import re
import requests
import os
from typing import Optional, List, Dict, Any
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QLabel, QScrollArea, QFrame,
    QListWidget, QListWidgetItem, QToolButton, QMenu,
    QSizePolicy, QApplication, QSplitter, QFileDialog,
    QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QTimer, QPoint, QMimeData
from PyQt6.QtGui import QTextCursor, QFont, QColor, QIcon, QDragEnterEvent, QDropEvent

from client.src.business.nanochat_config import config
from client.src.business.vector_db_integration import get_tool_registry
from client.src.business.function_knowledge import get_knowledge_base, FunctionModule
from client.src.presentation.components.ui_descriptor import (
    UIResponse, UIComponent, ClarificationRequest, ControlType,
    UIDescriptorProtocol
)
from client.src.presentation.components.semantic_parser import SemanticParser
from client.src.presentation.components.control_factory import ControlFactory
from client.src.presentation.components.layout_engine import LayoutEngine
from client.src.presentation.components.markdown_renderer import MarkdownRenderer
from client.src.presentation.components.code_highlighter import CodeHighlighterWidget, CodeBlockRenderer
from client.src.presentation.components.file_previewer import FilePreviewer, URLPreviewer, preview_file_or_url
from client.src.presentation.components.streaming_thought import StreamingThoughtWidget, ThinkingIndicator, ToolCallAnimation
from client.src.presentation.components.command_palette import CommandPalette
from client.src.presentation.components.task_widget import Task, TaskItem, TaskDetailPanel, TaskListWidget, create_sample_tasks
from client.src.presentation.components.voice_input import VoiceInputWidget, VoiceMessageBubble


# ── 工作线程：Ollama API 调用 ───────────────────────────────────────────────

class OllamaWorker(QThread):
    """Ollama API 工作线程（支持流式响应）"""

    chunk_received = pyqtSignal(str)  # 收到一个文本块
    finished = pyqtSignal(str)         # 完成（完整响应）
    error = pyqtSignal(str)            # 错误
    tool_call = pyqtSignal(dict)       # 工具调用

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
                                
                                tool_calls = delta.get("tool_calls", [])
                                if tool_calls:
                                    for tool_call in tool_calls:
                                        self.tool_call.emit(tool_call)
                        except json.JSONDecodeError:
                            continue

            self.finished.emit(full_content)

        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._stop_requested = True


# ── 消息气泡 ─────────────────────────────────────────────────────────────────

class MessageBubble(QFrame):
    """单条消息气泡（支持Markdown渲染和代码高亮）"""

    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.content = content
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        role_label = QLabel("🧑 用户" if self.role == "user" else "🤖 助手")
        role_label.setStyleSheet(
            "font-size: 11px; color: #666; font-weight: bold;"
        )
        layout.addWidget(role_label)

        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        renderer = MarkdownRenderer()
        content_widget = renderer.render(self.content)
        content_layout.addWidget(content_widget)

        code_widget = self._extract_and_render_code(self.content)
        if code_widget:
            content_layout.addWidget(code_widget)

        file_url_widgets = self._extract_and_render_files(self.content)
        for widget in file_url_widgets:
            content_layout.addWidget(widget)

        task_widget = self._extract_and_render_tasks(self.content)
        if task_widget:
            content_layout.addWidget(task_widget)

        layout.addWidget(content_container)

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

    def _extract_and_render_code(self, content: str) -> Optional[QWidget]:
        match = re.search(r'```(\w*)\s*\n([\s\S]*?)```', content)
        if match:
            language = match.group(1) or "python"
            code = match.group(2)
            code_widget = CodeHighlighterWidget()
            code_widget.set_code(code)
            code_widget.set_language(language)
            return code_widget
        return None

    def _extract_and_render_files(self, content: str) -> List[QWidget]:
        widgets = []
        
        file_pattern = r'([a-zA-Z]:[\\/][^\s]+|/[^\s]+|\./[^\s]+|\.\./[^\s]+)'
        file_matches = re.findall(file_pattern, content)
        
        for file_path in file_matches[:3]:
            if Path(file_path).exists():
                # 检查是否为图片
                ext = Path(file_path).suffix.lower()
                image_exts = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp', '.webp']
                
                if ext in image_exts:
                    # 直接展示图片
                    label = QLabel()
                    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    from PyQt6.QtGui import QPixmap
                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                        max_size = QSize(400, 300)
                        pixmap = pixmap.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio)
                        label.setPixmap(pixmap)
                    else:
                        label.setText("❌ 无法加载图片")
                    widgets.append(label)
                else:
                    # 其他文件显示文件名和预览按钮
                    file_frame = QFrame()
                    file_frame.setStyleSheet("background-color: #f1f5f9; border-radius: 8px; padding: 8px;")
                    file_layout = QHBoxLayout(file_frame)
                    
                    file_label = QLabel(f"📄 {Path(file_path).name}")
                    file_label.setStyleSheet("font-size: 13px; color: #334155;")
                    file_layout.addWidget(file_label)
                    
                    preview_btn = QPushButton("预览")
                    preview_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #2563eb;
                            color: white;
                            border: none;
                            border-radius: 4px;
                            padding: 4px 12px;
                            font-size: 12px;
                        }
                    """)
                    preview_btn.clicked.connect(lambda: self._preview_file(file_path))
                    file_layout.addWidget(preview_btn)
                    
                    widgets.append(file_frame)
        
        url_pattern = r'https?://[^\s]+'
        url_matches = re.findall(url_pattern, content)
        
        for url in url_matches[:3]:
            previewer = URLPreviewer()
            previewer.preview_url(url)
            previewer.setMaximumHeight(300)
            widgets.append(previewer)
        
        return widgets

    def _preview_file(self, file_path: str):
        """预览文件"""
        previewer = FilePreviewer()
        previewer.preview_file(file_path)
        
        # 创建对话框显示预览
        from PyQt6.QtWidgets import QDialog
        dialog = QDialog()
        dialog.setWindowTitle(f"预览: {Path(file_path).name}")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(previewer)
        
        dialog.exec()

    def _extract_and_render_tasks(self, content: str) -> Optional[QWidget]:
        """检查是否包含任务列表并渲染"""
        if "任务" in content or "task" in content.lower():
            tasks = create_sample_tasks()
            task_list = TaskListWidget(tasks)
            return task_list
        return None


class UIComponentBubble(QFrame):
    """UI组件消息气泡（渲染动态UI组件）"""

    def __init__(self, response: UIResponse, parent=None):
        super().__init__(parent)
        self.response = response
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        role_label = QLabel("🤖 助手")
        role_label.setStyleSheet(
            "font-size: 11px; color: #666; font-weight: bold;"
        )
        layout.addWidget(role_label)

        if self.response.content:
            renderer = MarkdownRenderer()
            content_widget = renderer.render(self.response.content)
            layout.addWidget(content_widget)

            code_widget = self._extract_and_render_code(self.response.content)
            if code_widget:
                layout.addWidget(code_widget)

            file_url_widgets = self._extract_and_render_files(self.response.content)
            for widget in file_url_widgets:
                layout.addWidget(widget)

        if self.response.components:
            factory = ControlFactory()
            layout_engine = LayoutEngine()
            
            for component in self.response.components:
                widget = factory.create_widget(component, self)
                if widget:
                    layout.addWidget(widget)

        if self.response.clarifications:
            for clarification in self.response.clarifications:
                clar_widget = self._create_clarification_widget(clarification)
                layout.addWidget(clar_widget)

        self.setStyleSheet("""
            UIComponentBubble {
                background: #F5F5F5;
                border-radius: 12px;
                margin-right: 40px;
            }
        """)

    def _extract_and_render_code(self, content: str) -> Optional[QWidget]:
        match = re.search(r'```(\w*)\s*\n([\s\S]*?)```', content)
        if match:
            language = match.group(1) or "python"
            code = match.group(2)
            code_widget = CodeHighlighterWidget()
            code_widget.set_code(code)
            code_widget.set_language(language)
            return code_widget
        return None

    def _extract_and_render_files(self, content: str) -> List[QWidget]:
        widgets = []
        
        file_pattern = r'([a-zA-Z]:[\\/][^\s]+|/[^\s]+|\./[^\s]+|\.\./[^\s]+)'
        file_matches = re.findall(file_pattern, content)
        
        for file_path in file_matches[:3]:
            if Path(file_path).exists():
                ext = Path(file_path).suffix.lower()
                image_exts = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp', '.webp']
                
                if ext in image_exts:
                    label = QLabel()
                    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    from PyQt6.QtGui import QPixmap
                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                        max_size = QSize(400, 300)
                        pixmap = pixmap.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio)
                        label.setPixmap(pixmap)
                    else:
                        label.setText("❌ 无法加载图片")
                    widgets.append(label)
                else:
                    file_frame = QFrame()
                    file_frame.setStyleSheet("background-color: #f1f5f9; border-radius: 8px; padding: 8px;")
                    file_layout = QHBoxLayout(file_frame)
                    
                    file_label = QLabel(f"📄 {Path(file_path).name}")
                    file_layout.addWidget(file_label)
                    
                    preview_btn = QPushButton("预览")
                    preview_btn.clicked.connect(lambda: self._preview_file(file_path))
                    file_layout.addWidget(preview_btn)
                    
                    widgets.append(file_frame)
        
        url_pattern = r'https?://[^\s]+'
        url_matches = re.findall(url_pattern, content)
        
        for url in url_matches[:3]:
            previewer = URLPreviewer()
            previewer.preview_url(url)
            previewer.setMaximumHeight(300)
            widgets.append(previewer)
        
        return widgets

    def _preview_file(self, file_path: str):
        previewer = FilePreviewer()
        previewer.preview_file(file_path)
        
        from PyQt6.QtWidgets import QDialog
        dialog = QDialog()
        dialog.setWindowTitle(f"预览: {Path(file_path).name}")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(previewer)
        
        dialog.exec()

    def _create_clarification_widget(self, clarification: ClarificationRequest) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)

        question_label = QLabel(clarification.question)
        question_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 500;
            color: #1e40af;
            background-color: #dbeafe;
            padding: 8px 12px;
            border-radius: 8px;
        """)
        layout.addWidget(question_label)

        options_layout = QHBoxLayout()
        options_layout.setSpacing(8)

        for opt in clarification.options:
            btn = QPushButton(opt.label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: white;
                    border: none;
                    border-radius: 20px;
                    padding: 6px 16px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
            """)
            btn.clicked.connect(lambda checked, opt=opt: self._on_clarification_selected(opt))
            options_layout.addWidget(btn)

        layout.addLayout(options_layout)

        return container

    def _on_clarification_selected(self, option: Dict[str, Any]):
        print(f"澄清选择: {option}")
        if hasattr(self.parent(), 'send_clarification_response'):
            self.parent().send_clarification_response(option)


# ── 命令建议下拉框 ──────────────────────────────────────────────────────────

class CommandSuggestionPopup(QFrame):
    """命令建议下拉框"""

    command_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.command_list = QListWidget()
        self.command_list.setStyleSheet("""
            QListWidget {
                border: none;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
            }
            QListWidget::item:selected {
                background-color: #bbdefb;
            }
        """)
        self.command_list.itemClicked.connect(self._on_item_clicked)
        self.layout.addWidget(self.command_list)

    def show_suggestions(self, suggestions: List[Dict[str, Any]], position: QPoint):
        self.command_list.clear()

        for suggestion in suggestions:
            shortcut = suggestion.get("shortcut", "")
            name = suggestion.get("name", "")
            description = suggestion.get("description", "")

            item = QListWidgetItem(f"{shortcut} - {name}")
            item.setToolTip(description)
            self.command_list.addItem(item)

        self.adjustSize()
        self.move(position)
        self.show()

    def _on_item_clicked(self, item: QListWidgetItem):
        text = item.text()
        if " - " in text:
            shortcut = text.split(" - ")[0]
            self.command_selected.emit(shortcut)
        self.hide()


# ── 工具/技能/专家面板 ───────────────────────────────────────────────────────

class ToolSkillPanel(QWidget):
    """工具/技能/专家展示面板"""

    tool_selected = pyqtSignal(dict)
    skill_selected = pyqtSignal(dict)
    expert_selected = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._registry = get_tool_registry()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabWidget::tab {
                background-color: #f5f5f5;
                padding: 8px 16px;
                border-radius: 4px 4px 0 0;
                margin-right: 4px;
            }
            QTabWidget::tab:selected {
                background-color: #ffffff;
            }
        """)

        self.tools_tab = QWidget()
        self._setup_tools_tab()
        self.tab_widget.addTab(self.tools_tab, "🛠️ 工具")

        self.skills_tab = QWidget()
        self._setup_skills_tab()
        self.tab_widget.addTab(self.skills_tab, "🧠 技能")

        self.experts_tab = QWidget()
        self._setup_experts_tab()
        self.tab_widget.addTab(self.experts_tab, "👤 专家")

        layout.addWidget(self.tab_widget)

    def _setup_tools_tab(self):
        layout = QVBoxLayout(self.tools_tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.tools_list = QListWidget()
        self.tools_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
            }
        """)
        self.tools_list.itemClicked.connect(self._on_tool_clicked)
        layout.addWidget(self.tools_list)

        self._load_tools()

    def _setup_skills_tab(self):
        layout = QVBoxLayout(self.skills_tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.skills_list = QListWidget()
        self.skills_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
            }
        """)
        self.skills_list.itemClicked.connect(self._on_skill_clicked)
        layout.addWidget(self.skills_list)

        self._load_skills()

    def _setup_experts_tab(self):
        layout = QVBoxLayout(self.experts_tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.experts_list = QListWidget()
        self.experts_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
            }
        """)
        self.experts_list.itemClicked.connect(self._on_expert_clicked)
        layout.addWidget(self.experts_list)

        self._load_experts()

    def _load_tools(self):
        tools = self._registry.get_all_tools()
        self.tools_list.clear()
        
        for tool in tools:
            item = QListWidgetItem(f"🔧 {tool.name}")
            item.setToolTip(tool.description)
            item.setData(Qt.ItemDataRole.UserRole, tool)
            self.tools_list.addItem(item)

    def _load_skills(self):
        skills = self._registry.get_all_skills()
        self.skills_list.clear()
        
        for skill in skills:
            item = QListWidgetItem(f"✨ {skill.name}")
            item.setToolTip(skill.description)
            item.setData(Qt.ItemDataRole.UserRole, skill)
            self.skills_list.addItem(item)

    def _load_experts(self):
        experts = self._registry.get_all_experts()
        self.experts_list.clear()
        
        for expert in experts:
            item = QListWidgetItem(f"👤 {expert.name}")
            item.setToolTip(expert.description)
            item.setData(Qt.ItemDataRole.UserRole, expert)
            self.experts_list.addItem(item)

    def _on_tool_clicked(self, item: QListWidgetItem):
        tool = item.data(Qt.ItemDataRole.UserRole)
        if tool:
            self.tool_selected.emit(tool.to_dict())

    def _on_skill_clicked(self, item: QListWidgetItem):
        skill = item.data(Qt.ItemDataRole.UserRole)
        if skill:
            self.skill_selected.emit(skill.to_dict())

    def _on_expert_clicked(self, item: QListWidgetItem):
        expert = item.data(Qt.ItemDataRole.UserRole)
        if expert:
            self.expert_selected.emit(expert.to_dict())

    def refresh(self):
        self._load_tools()
        self._load_skills()
        self._load_experts()


# ── 主聊天面板 ───────────────────────────────────────────────────────────────

class Panel(QWidget):
    """聊天面板 - 集成UI描述符协议"""

    message_sent = pyqtSignal(str)
    file_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.messages: List[Dict] = [
            {"role": "system", "content": "你是生命之树 AI 助手，友好、专业、简洁。支持通过斜杠命令调用工具。"}
        ]
        self.worker: Optional[OllamaWorker] = None
        self.current_assistant_bubble: Optional[MessageBubble] = None
        self.current_ui_bubble: Optional[UIComponentBubble] = None
        self.current_thinking_widget: Optional[StreamingThoughtWidget] = None
        self.command_popup: Optional[CommandSuggestionPopup] = None
        
        self.command_palette = CommandPalette()
        self.semantic_parser = SemanticParser()
        self.tool_registry = get_tool_registry()
        self.knowledge_base = get_knowledge_base()
        
        self._init_default_data()
        self._setup_ui()
        self._setup_models()

    def _init_default_data(self):
        """初始化默认工具、技能、专家数据"""
        tools = [
            {"name": "网络搜索", "description": "使用搜索引擎搜索互联网信息", "keywords": ["搜索", "网络", "信息"]},
            {"name": "文件读取", "description": "读取本地文件内容", "keywords": ["文件", "读取", "内容"]},
            {"name": "文件写入", "description": "将内容写入本地文件", "keywords": ["文件", "写入", "保存"]},
            {"name": "代码执行", "description": "执行Python代码并返回结果", "keywords": ["代码", "执行", "Python"]},
            {"name": "数据分析", "description": "分析数据并生成图表", "keywords": ["数据", "分析", "图表"]},
        ]
        
        for tool in tools:
            self.tool_registry.register_tool(**tool)
        
        skills = [
            {"name": "自然语言处理", "description": "文本分析、情感分析、实体识别", "keywords": ["NLP", "文本", "分析"]},
            {"name": "机器学习", "description": "模型训练、预测、评估", "keywords": ["ML", "模型", "训练"]},
            {"name": "数据可视化", "description": "创建图表和数据展示", "keywords": ["图表", "可视化", "数据"]},
            {"name": "文档写作", "description": "撰写技术文档和报告", "keywords": ["文档", "写作", "报告"]},
        ]
        
        for skill in skills:
            self.tool_registry.register_skill(**skill)
        
        experts = [
            {"name": "Python编程专家", "description": "精通Python编程和数据分析", "keywords": ["Python", "编程", "数据"]},
            {"name": "前端开发专家", "description": "精通JavaScript、React、Vue", "keywords": ["前端", "JavaScript", "React"]},
            {"name": "数据科学家", "description": "机器学习和数据分析专家", "keywords": ["数据科学", "ML", "AI"]},
            {"name": "技术写作专家", "description": "专业技术文档撰写", "keywords": ["技术写作", "文档", "报告"]},
        ]
        
        for expert in experts:
            self.tool_registry.register_expert(**expert)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        chat_container = QWidget()
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)

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

        self.command_menu_btn = QToolButton()
        self.command_menu_btn.setText("⚙️")
        self.command_menu_btn.setToolTip("命令菜单")
        self.command_menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._setup_command_menu()
        title_layout.addWidget(self.command_menu_btn)

        self.tool_panel_btn = QToolButton()
        self.tool_panel_btn.setText("📦")
        self.tool_panel_btn.setToolTip("工具面板")
        self.tool_panel_btn.clicked.connect(self._toggle_tool_panel)
        title_layout.addWidget(self.tool_panel_btn)

        title_layout.addStretch()
        chat_layout.addWidget(title_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: #FAFAFA; }")

        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(16, 16, 16, 16)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.messages_container)
        chat_layout.addWidget(self.scroll_area, 1)

        input_frame = QFrame()
        input_frame.setStyleSheet("background: #FFFFFF; border-top: 1px solid #E0E0E0;")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(16, 12, 16, 12)

        # 文件拖拽区域
        self.drop_zone = QFrame()
        self.drop_zone.setFixedWidth(40)
        self.drop_zone.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 8px;
            }
            QFrame.drag-over {
                border-color: #2563eb;
                background-color: #e0f2fe;
            }
        """)
        drop_label = QLabel("📁")
        drop_label.setStyleSheet("font-size: 20px;")
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        drop_layout = QVBoxLayout(self.drop_zone)
        drop_layout.addWidget(drop_label)
        
        self.drop_zone.setAcceptDrops(True)
        self.drop_zone.dragEnterEvent = self._on_drag_enter
        self.drop_zone.dragLeaveEvent = self._on_drag_leave
        self.drop_zone.dropEvent = self._on_drop
        
        input_layout.addWidget(self.drop_zone)

        self.command_btn = QToolButton()
        self.command_btn.setText("/")
        self.command_btn.setStyleSheet("""
            QToolButton {
                background-color: #e0e0e0;
                color: #666;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: #d0d0d0;
            }
        """)
        self.command_btn.clicked.connect(self._show_command_palette)
        input_layout.addWidget(self.command_btn)

        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("输入消息... (输入 / 查看命令)")
        self.input_field.setMaximumHeight(100)
        self.input_field.keyPressEvent = self._on_input_key_press
        self.input_field.textChanged.connect(self._on_input_text_changed)
        input_layout.addWidget(self.input_field, 1)

        # 语音输入按钮
        self.voice_input = VoiceInputWidget()
        self.voice_input.voice_finished.connect(self._on_voice_finished)
        input_layout.addWidget(self.voice_input)

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

        chat_layout.addWidget(input_frame)

        self.splitter.addWidget(chat_container)

        self.tool_panel = ToolSkillPanel()
        self.tool_panel.setFixedWidth(280)
        self.tool_panel.hide()
        self.tool_panel.tool_selected.connect(self._on_tool_selected)
        self.tool_panel.skill_selected.connect(self._on_skill_selected)
        self.tool_panel.expert_selected.connect(self._on_expert_selected)
        self.splitter.addWidget(self.tool_panel)

        self.command_popup = CommandSuggestionPopup(self)
        self.command_popup.command_selected.connect(self._on_command_selected)

    def _setup_command_menu(self):
        menu = QMenu()

        tools_menu = menu.addMenu("🛠️ 工具")
        tools_menu.addAction("搜索", self._show_search_tool)
        tools_menu.addAction("分析", self._show_analyze_tool)
        tools_menu.addAction("报告", self._show_report_tool)

        skills_menu = menu.addMenu("🧠 技能")
        skills_menu.addAction("查看所有技能", self._show_all_skills)

        experts_menu = menu.addMenu("👤 专家角色")
        experts_menu.addAction("数据分析专家", lambda: self._select_expert("data_analyst"))
        experts_menu.addAction("编程专家", lambda: self._select_expert("programming"))
        experts_menu.addAction("写作专家", lambda: self._select_expert("writing"))

        menu.addSeparator()
        menu.addAction("📋 命令历史", self._show_command_history)
        menu.addAction("📁 选择文件", self._select_file)
        menu.addAction("📂 选择文件夹", self._select_folder)

        self.command_menu_btn.setMenu(menu)

    def _setup_models(self):
        model_name = "qwen3.5:4b"
        self.model_name = model_name
        self.model_label.setText(f"模型: {model_name}")

        self.base_url = config.ollama.url
        print(f"[Chat] Ollama URL: {self.base_url}")
        print(f"[Chat] Model: {self.model_name}")

    def _toggle_tool_panel(self):
        if self.tool_panel.isVisible():
            self.tool_panel.hide()
            self.tool_panel_btn.setToolTip("显示工具面板")
        else:
            self.tool_panel.show()
            self.tool_panel_btn.setToolTip("隐藏工具面板")

    def _on_drag_enter(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_zone.setStyleSheet("""
                QFrame {
                    background-color: #e0f2fe;
                    border: 2px dashed #2563eb;
                    border-radius: 8px;
                }
            """)

    def _on_drag_leave(self, event: QDragEnterEvent):
        self.drop_zone.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 8px;
            }
        """)

    def _on_drop(self, event: QDropEvent):
        self.drop_zone.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 8px;
            }
        """)

        mime_data = event.mimeData()
        
        if mime_data.hasUrls():
            files = []
            for url in mime_data.urls():
                file_path = url.toLocalFile()
                if os.path.exists(file_path):
                    files.append(file_path)
            
            if files:
                self._handle_dropped_files(files)
                self.file_dropped.emit(files)
        
        event.acceptProposedAction()

    def _handle_dropped_files(self, files: List[str]):
        """处理拖放的文件"""
        for file_path in files[:3]:  # 最多处理3个文件
            if os.path.isfile(file_path):
                ext = Path(file_path).suffix.lower()
                image_exts = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp', '.webp']
                
                if ext in image_exts:
                    # 直接展示图片
                    self._add_image_message(file_path)
                else:
                    # 其他文件显示文件名
                    self._add_file_message(file_path)
            elif os.path.isdir(file_path):
                self._add_folder_message(file_path)

    def _add_image_message(self, file_path: str):
        """添加图片消息"""
        bubble = QFrame()
        bubble.setStyleSheet("""
            QFrame {
                background: #E3F2FD;
                border-radius: 12px;
                margin-left: 40px;
                padding: 8px;
            }
        """)
        
        layout = QVBoxLayout(bubble)
        
        role_label = QLabel("🧑 用户")
        role_label.setStyleSheet("font-size: 11px; color: #666; font-weight: bold;")
        layout.addWidget(role_label)
        
        from PyQt6.QtGui import QPixmap
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            max_size = QSize(400, 300)
            pixmap = pixmap.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio)
            label.setPixmap(pixmap)
        else:
            label.setText("❌ 无法加载图片")
        layout.addWidget(label)
        
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def _add_file_message(self, file_path: str):
        """添加文件消息"""
        file_name = Path(file_path).name
        self._add_message("user", f"📄 文件: `{file_name}`")
        
        # 添加文件预览按钮
        preview_btn = QPushButton(f"预览 {file_name}")
        preview_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                margin-left: 40px;
                margin-bottom: 8px;
            }
        """)
        preview_btn.clicked.connect(lambda: self._preview_file(file_path))
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, preview_btn)
        self._scroll_to_bottom()

    def _add_folder_message(self, folder_path: str):
        """添加文件夹消息"""
        folder_name = Path(folder_path).name
        self._add_message("user", f"📂 文件夹: `{folder_name}`")
        
        # 列出文件夹内容
        try:
            files = os.listdir(folder_path)[:10]
            content = "文件夹内容:\n" + "\n".join([f"- {f}" for f in files])
            self._add_message("assistant", content)
        except Exception as e:
            self._add_system_message(f"无法读取文件夹: {e}")

    def _select_file(self):
        """选择文件"""
        files, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        if files:
            self._handle_dropped_files(files)

    def _select_folder(self):
        """选择文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            self._handle_dropped_files([folder])

    def _preview_file(self, file_path: str):
        """预览文件"""
        previewer = FilePreviewer()
        previewer.preview_file(file_path)
        
        from PyQt6.QtWidgets import QDialog
        dialog = QDialog()
        dialog.setWindowTitle(f"预览: {Path(file_path).name}")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(previewer)
        
        dialog.exec()

    def _on_input_key_press(self, event):
        from PyQt6.QtGui import QKeyEvent
        if isinstance(event, QKeyEvent):
            if event.key() in (16777221, 16777220) and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self._send_message()
                return
            if event.key() in (16777221, 16777220) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send_message()
                return
            if event.key() == 16777216 and self.command_popup and self.command_popup.isVisible():
                self.command_popup.hide()
                return

        QTextEdit.keyPressEvent(self.input_field, event)

    def _on_input_text_changed(self):
        text = self.input_field.toPlainText().strip()

        if text.startswith("/"):
            # 使用知识库获取命令建议
            suggestions = self.knowledge_base.suggest_commands(text)
            if suggestions:
                suggestion_list = []
                for cmd in suggestions:
                    help_info = self.knowledge_base.get_command_help(cmd)
                    description = ""
                    if help_info:
                        # 提取描述
                        lines = help_info.split("\n")
                        for line in lines:
                            if line.startswith("**描述**:"):
                                description = line.replace("**描述**:", "").strip()
                                break
                    
                    suggestion_list.append({
                        "shortcut": cmd,
                        "name": cmd,
                        "description": description
                    })
                
                cursor_rect = self.input_field.cursorRect()
                global_pos = self.input_field.mapToGlobal(cursor_rect.bottomLeft())
                self.command_popup.show_suggestions(suggestion_list, global_pos)
            else:
                self.command_popup.hide()
        else:
            # 检查是否需要推荐功能模块
            module = self.knowledge_base.recommend_module(text)
            if module:
                self._suggest_module(module)
        
        # 保持下拉框显示（如果有建议）
        if text.startswith("/") and suggestions:
            pass
        else:
            self.command_popup.hide()

    def _suggest_module(self, module: FunctionModule):
        """推荐功能模块"""
        pass  # 在输入框下方显示建议

    def _send_message(self):
        text = self.input_field.toPlainText().strip()
        if not text:
            return

        # 检查是否是命令
        if text.startswith("/"):
            # 提取命令部分
            cmd_parts = text.split()
            cmd = cmd_parts[0]
            has_params = len(cmd_parts) > 1

            # 如果没有参数，显示命令帮助
            if not has_params:
                help_info = self.knowledge_base.get_command_help(cmd)
                if help_info:
                    self._add_message("assistant", help_info)
                    self.input_field.clear()
                    return
                else:
                    # 如果没有找到命令帮助，显示所有可用命令
                    all_commands = self.knowledge_base.format_all_command_help()
                    self._add_message("assistant", all_commands)
                    self.input_field.clear()
                    return

        parsed_command = self.command_palette.parse_command(text)
        if parsed_command:
            result = self.command_palette.execute_command(text)
            if result:
                self._add_system_message(f"执行命令: {text}")
                self._add_system_message(f"结果: {result}")
            self.input_field.clear()
            return

        # 检查是否匹配功能模块
        module = self.knowledge_base.recommend_module(text)
        if module:
            self._add_system_message(f"📢 检测到您可能想使用「{module.name}」模块")
            if module.commands:
                self._add_system_message(f"您可以使用命令: {', '.join(module.commands)}")

        self._add_message("user", text)
        self.messages.append({"role": "user", "content": text})
        self.input_field.clear()

        self.send_btn.setEnabled(False)
        self.send_btn.setText("思考中...")

        self._show_thinking()

        self.worker = OllamaWorker(self.base_url, self.model_name, self.messages)
        self.worker.chunk_received.connect(self._on_chunk_received)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.tool_call.connect(self._on_tool_call)
        self.worker.start()

    def _show_thinking(self):
        if self.current_thinking_widget:
            self.current_thinking_widget.deleteLater()
        
        self.current_thinking_widget = StreamingThoughtWidget()
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, self.current_thinking_widget)
        self.current_thinking_widget.add_thought("正在分析用户请求...")
        self._scroll_to_bottom()

    def _add_message(self, role: str, content: str):
        bubble = MessageBubble(role, content)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def _add_system_message(self, content: str):
        label = QLabel(f"📢 {content}")
        label.setStyleSheet("""
            font-size: 12px;
            color: #666;
            text-align: center;
            padding: 8px;
            background-color: #f5f5f5;
            border-radius: 4px;
            margin: 4px 0;
        """)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, label)
        self._scroll_to_bottom()

    def _add_ui_component_bubble(self, response: UIResponse):
        bubble = UIComponentBubble(response)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    @pyqtSlot(str)
    def _on_chunk_received(self, chunk: str):
        if self.current_thinking_widget:
            self.current_thinking_widget.add_thought(f"正在生成响应...")

    @pyqtSlot(str)
    def _on_finished(self, full_content: str):
        if self.current_thinking_widget:
            self.current_thinking_widget.deleteLater()
            self.current_thinking_widget = None

        response = self.semantic_parser.parse(full_content)

        if response.components or response.clarifications:
            self._add_ui_component_bubble(response)
        else:
            self._add_message("assistant", full_content)

        self.messages.append({"role": "assistant", "content": full_content})
        self.current_assistant_bubble = None
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        self.worker = None

    @pyqtSlot(str)
    def _on_error(self, error_msg: str):
        print(f"[Chat] Error: {error_msg}")
        
        if self.current_thinking_widget:
            self.current_thinking_widget.deleteLater()
            self.current_thinking_widget = None

        self._add_system_message(f"错误: {error_msg}")

        self.current_assistant_bubble = None
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        self.worker = None

    @pyqtSlot(dict)
    def _on_tool_call(self, tool_call: Dict):
        if self.current_thinking_widget:
            tool_name = tool_call.get("function", {}).get("name", "未知工具")
            params = tool_call.get("function", {}).get("arguments", {})
            self.current_thinking_widget.add_thought(f"正在调用工具: {tool_name}")
            self.current_thinking_widget.add_tool_call(tool_name, params)

    @pyqtSlot(str)
    def _on_voice_finished(self, text: str):
        """语音转文字完成"""
        self.input_field.setPlainText(text)

    def _show_command_palette(self):
        self.input_field.insertPlainText("/")
        self.input_field.setFocus()

    def _on_command_selected(self, command: str):
        self.input_field.setPlainText(command + " ")
        self.input_field.setFocus()

    def _show_search_tool(self):
        self._add_system_message("打开搜索工具...")

    def _show_analyze_tool(self):
        self._add_system_message("打开分析工具...")

    def _show_report_tool(self):
        self._add_system_message("打开报告工具...")

    def _show_all_skills(self):
        skills = self.tool_registry.get_all_skills()
        
        content = "## 可用技能\n\n"
        for skill in skills:
            content += f"- **{skill.name}**: {skill.description}\n"
        
        self._add_message("assistant", content)

    def _select_expert(self, expert_type: str):
        experts = {
            "data_analyst": "数据分析专家",
            "programming": "编程专家",
            "writing": "写作专家"
        }
        expert_name = experts.get(expert_type, "专家")
        self._add_system_message(f"已切换到 {expert_name} 角色")

    def _show_command_history(self):
        history = self.command_palette.get_command_history()
        if history:
            content = "## 命令历史\n\n"
            for cmd in history[:10]:
                content += f"- `{cmd}`\n"
            self._add_message("assistant", content)
        else:
            self._add_system_message("暂无命令历史")

    def _on_tool_selected(self, tool: Dict):
        content = f"## 选择工具\n\n**{tool['name']}**\n\n{tool['description']}"
        self._add_message("assistant", content)
        
        self.input_field.setPlainText(f"/tool {tool['name']} ")
        self.input_field.setFocus()

    def _on_skill_selected(self, skill: Dict):
        content = f"## 选择技能\n\n**{skill['name']}**\n\n{skill['description']}"
        self._add_message("assistant", content)

    def _on_expert_selected(self, expert: Dict):
        content = f"## 选择专家\n\n**{expert['name']}**\n\n{expert['description']}"
        self._add_message("assistant", content)
        self._add_system_message(f"已切换到 {expert['name']} 角色")

    def send_clarification_response(self, option: Dict[str, Any]):
        response_text = f"我选择: {option.get('label', option.get('value'))}"
        self._send_message_text(response_text)

    def _send_message_text(self, text: str):
        self.input_field.setPlainText(text)
        self._send_message()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        super().closeEvent(event)