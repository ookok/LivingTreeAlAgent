"""
AI 驱动智能 IDE 面板（Trae Solo 模式）
=====================================

设计理念：
- 对话式编程：用户通过自然语言描述需求，AI 完成代码实现
- 实时知识库：将代码项目库作为上下文感知的知识库
- 任务管理：跟踪开发任务进度和成果
- 减少手动代码编辑，重在交互过程和成果输出

核心功能：
1. AI 对话编程界面
2. 项目库实时知识检索
3. 任务/成果展示
4. 文件预览（只读为主）
5. 一键应用到项目

Author: Hermes Desktop Team
Date: 2026-04-22
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QUrl
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QSplitter, QTreeWidget, QTreeWidgetItem,
    QListWidget, QListWidgetItem, QFrame, QTabWidget,
    QGroupBox, QScrollArea, QStackedWidget, QProgressBar,
    QMessageBox, QFileDialog, QComboBox, QSizePolicy,
    QTextBrowser,
)
from PyQt6.QtGui import QFont, QColor, QTextCursor, QIcon

logger = logging.getLogger(__name__)

# 样式常量
STYLE_CHAT_INPUT = """
    QLineEdit {
        padding: 12px 16px;
        border: 2px solid #e0e0e0;
        border-radius: 24px;
        font-size: 14px;
        background: white;
    }
    QLineEdit:focus {
        border: 2px solid #6366F1;
    }
"""

STYLE_PRIMARY_BTN = """
    QPushButton {
        background: #6366F1;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton:hover {
        background: #4F46E5;
    }
    QPushButton:pressed {
        background: #4338CA;
    }
    QPushButton:disabled {
        background: #A5B4FC;
    }
"""

STYLE_SECONDARY_BTN = """
    QPushButton {
        background: white;
        color: #6366F1;
        border: 2px solid #6366F1;
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton:hover {
        background: #EEF2FF;
    }
"""

STYLE_CARD = """
    QFrame {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
    }
"""

STYLE_CHAT_BUBBLE_USER = """
    QLabel {
        background: #6366F1;
        color: white;
        border-radius: 16px;
        padding: 12px 16px;
    }
"""

STYLE_CHAT_BUBBLE_AI = """
    QLabel {
        background: #F3F4F6;
        color: #1F2937;
        border-radius: 16px;
        padding: 12px 16px;
    }
"""

STYLE_CODE_BLOCK = """
    QTextEdit {
        background: #1E1E2E;
        color: #CDD6F4;
        border: none;
        border-radius: 8px;
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        font-size: 13px;
        padding: 12px;
    }
"""

STYLE_FILE_TREE = """
    QTreeWidget {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        background: white;
    }
    QTreeWidget::item {
        padding: 6px 8px;
    }
    QTreeWidget::item:selected {
        background: #EEF2FF;
        color: #6366F1;
    }
"""


class AIDrivenIDEPanel(QWidget):
    """
    AI 驱动智能 IDE 面板（Trae Solo 模式）
    
    以对话为核心的开发模式：
    - 用户描述需求
    - AI 分析项目上下文
    - AI 生成代码/修改
    - 用户审核并应用
    """

    # 信号
    task_completed = pyqtSignal(dict)
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_state()
        self._init_ui()
        self._load_sample_project()

    def _init_state(self):
        """初始化状态"""
        # 项目状态
        self.project_path: Optional[str] = None
        self.project_files: Dict[str, Any] = {}
        self.file_contents: Dict[str, str] = {}

        # 对话状态
        self.chat_history: List[Dict] = []
        self.current_task: Optional[Dict] = None
        self.pending_changes: List[Dict] = []

        # 知识库状态
        self.knowledge_base: Dict[str, Any] = {}
        self.context_chunks: List[Dict] = []

        # 任务状态
        self.tasks: List[Dict] = []
        self.completed_tasks: List[Dict] = []

        # AI 模块（延迟加载）
        self.context_preprocessor = None
        self.knowledge_graph = None
        self.ollama_client = None

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部工具栏
        self._setup_toolbar(layout)

        # 主内容区（三栏布局）
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：项目知识库
        left_panel = self._create_knowledge_panel()
        main_splitter.addWidget(left_panel)

        # 中间：AI 对话区
        center_panel = self._create_chat_panel()
        main_splitter.addWidget(center_panel)

        # 右侧：任务/成果区
        right_panel = self._create_task_panel()
        main_splitter.addWidget(right_panel)

        # 设置比例
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)
        main_splitter.setStretchFactor(2, 1)

        layout.addWidget(main_splitter)

        # 底部状态栏
        self._setup_status_bar(layout)

    def _setup_toolbar(self, parent_layout: QVBoxLayout):
        """设置顶部工具栏"""
        toolbar = QFrame()
        toolbar.setStyleSheet("background: white; border-bottom: 1px solid #e5e7eb;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 10, 16, 10)
        toolbar_layout.setSpacing(12)

        # 标题
        title = QLabel("🚀 AI IDE (Solo Mode)")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        toolbar_layout.addWidget(title)

        toolbar_layout.addSpacing(20)

        # 打开项目
        open_btn = QPushButton("📂 打开项目")
        open_btn.setStyleSheet(STYLE_SECONDARY_BTN)
        open_btn.clicked.connect(self._on_open_project)
        toolbar_layout.addWidget(open_btn)

        # 新建任务
        new_task_btn = QPushButton("✨ 新建任务")
        new_task_btn.setStyleSheet(STYLE_PRIMARY_BTN)
        new_task_btn.clicked.connect(self._on_new_task)
        toolbar_layout.addWidget(new_task_btn)

        toolbar_layout.addStretch()

        # 项目信息
        self.project_info_label = QLabel("未打开项目")
        self.project_info_label.setStyleSheet("font-size: 13px; color: #6B7280;")
        toolbar_layout.addWidget(self.project_info_label)

        parent_layout.addWidget(toolbar)

    def _create_knowledge_panel(self) -> QWidget:
        """创建项目知识库面板（左侧）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 知识库标题
        title = QLabel("📚 项目知识库")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 知识库搜索
        search_input = QLineEdit()
        search_input.setPlaceholderText("🔍 搜索项目知识...")
        search_input.setStyleSheet(STYLE_CHAT_INPUT)
        search_input.returnPressed.connect(self._on_knowledge_search)
        layout.addWidget(search_input)
        self.knowledge_search_input = search_input

        # 文件树
        file_tree = QTreeWidget()
        file_tree.setHeaderLabels(["名称", "类型"])
        file_tree.setStyleSheet(STYLE_FILE_TREE)
        file_tree.setColumnWidth(0, 180)
        file_tree.itemClicked.connect(self._on_file_selected)
        layout.addWidget(file_tree)
        self.file_tree = file_tree

        # 知识库摘要
        summary_group = QGroupBox("📊 项目摘要")
        summary_layout = QVBoxLayout()
        self.project_summary = QTextBrowser()
        self.project_summary.setStyleSheet("""
            QTextBrowser {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 8px;
                background: white;
            }
        """)
        self.project_summary.setReadOnly(True)
        summary_layout.addWidget(self.project_summary)
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        return widget

    def _create_chat_panel(self) -> QWidget:
        """创建 AI 对话面板（中间）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 对话标题
        title = QLabel("💬 AI 对话编程")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 对话历史区
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                background: #F9FAFB;
            }
        """)

        self.chat_content = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.setSpacing(12)
        self.chat_layout.addStretch()
        self.chat_scroll.setWidget(self.chat_content)
        layout.addWidget(self.chat_scroll)

        # 输入区
        input_frame = QFrame()
        input_frame.setStyleSheet(STYLE_CARD)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 8, 12, 8)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("描述你的需求，例如：帮我添加用户登录功能...")
        self.chat_input.setStyleSheet(STYLE_CHAT_INPUT)
        self.chat_input.returnPressed.connect(self._on_send_message)
        input_layout.addWidget(self.chat_input)

        send_btn = QPushButton("发送")
        send_btn.setStyleSheet(STYLE_PRIMARY_BTN)
        send_btn.clicked.connect(self._on_send_message)
        input_layout.addWidget(send_btn)

        layout.addWidget(input_frame)

        # 快捷操作
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)

        quick_actions = [
            ("📝 分析项目", self._on_analyze_project),
            ("🔧 重构代码", self._on_refactor_request),
            ("🧪 生成测试", self._on_generate_tests),
            ("📖 生成文档", self._on_generate_docs),
        ]

        for text, callback in quick_actions:
            btn = QPushButton(text)
            btn.setStyleSheet("""
                QPushButton {
                    background: #F3F4F6;
                    color: #374151;
                    border: 1px solid #E5E7EB;
                    border-radius: 16px;
                    padding: 6px 12px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: #E5E7EB;
                }
            """)
            btn.clicked.connect(callback)
            quick_layout.addWidget(btn)

        quick_layout.addStretch()
        layout.addLayout(quick_layout)

        return widget

    def _create_task_panel(self) -> QWidget:
        """创建任务/成果面板（右侧）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 任务标题
        title = QLabel("📋 任务与成果")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 任务选项卡
        self.task_tabs = QTabWidget()
        self.task_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
            }
            QTabBar::tab {
                padding: 8px 12px;
                background: #F3F4F6;
                border-radius: 4px 4px 0 0;
            }
            QTabBar::tab:selected {
                background: white;
                font-weight: bold;
            }
        """)

        # 当前任务
        self.current_task_tab = self._create_current_task_tab()
        self.task_tabs.addTab(self.current_task_tab, "🔄 当前")

        # 待审核更改
        self.pending_changes_tab = self._create_pending_changes_tab()
        self.task_tabs.addTab(self.pending_changes_tab, "📝 待审核")

        # 历史成果
        self.completed_tasks_tab = self._create_completed_tasks_tab()
        self.task_tabs.addTab(self.completed_tasks_tab, "✅ 历史")

        layout.addWidget(self.task_tabs)

        return widget

    def _create_current_task_tab(self) -> QWidget:
        """创建当前任务标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        self.current_task_label = QLabel("暂无进行中的任务")
        self.current_task_label.setStyleSheet("""
            QLabel {
                padding: 20px;
                color: #9CA3AF;
                font-size: 14px;
                text-align: center;
            }
        """)
        self.current_task_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.current_task_label)

        return widget

    def _create_pending_changes_tab(self) -> QWidget:
        """创建待审核更改标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 更改列表
        self.changes_list = QListWidget()
        self.changes_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                background: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #F3F4F6;
            }
        """)
        self.changes_list.itemClicked.connect(self._on_change_selected)
        layout.addWidget(self.changes_list)

        # 操作按钮
        btn_layout = QHBoxLayout()
        apply_all_btn = QPushButton("✅ 全部应用")
        apply_all_btn.setStyleSheet(STYLE_PRIMARY_BTN)
        apply_all_btn.clicked.connect(self._on_apply_all_changes)
        btn_layout.addWidget(apply_all_btn)

        reject_all_btn = QPushButton("❌ 全部拒绝")
        reject_all_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #EF4444;
                border: 2px solid #EF4444;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #FEF2F2;
            }
        """)
        reject_all_btn.clicked.connect(self._on_reject_all_changes)
        btn_layout.addWidget(reject_all_btn)

        layout.addLayout(btn_layout)

        return widget

    def _create_completed_tasks_tab(self) -> QWidget:
        """创建历史成果标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.completed_list = QListWidget()
        self.completed_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                background: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #F3F4F6;
            }
        """)
        layout.addWidget(self.completed_list)

        return widget

    def _setup_status_bar(self, parent_layout: QVBoxLayout):
        """设置底部状态栏"""
        status_frame = QFrame()
        status_frame.setStyleSheet("background: #F9FAFB; border-top: 1px solid #e5e7eb;")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(16, 6, 16, 6)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("font-size: 12px; color: #6B7280;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.context_label = QLabel("上下文: 0 tokens")
        status_layout.addWidget(self.context_label)

        self.task_count_label = QLabel("任务: 0")
        status_layout.addWidget(self.task_count_label)

        parent_layout.addWidget(status_frame)

    # ─── 事件处理 ──────────────────────────────────

    def _on_open_project(self):
        """打开项目"""
        project_path = QFileDialog.getExistingDirectory(self, "选择项目目录")
        if not project_path:
            return

        self.project_path = project_path
        self._scan_project(project_path)
        self._set_status(f"✅ 已打开项目: {Path(project_path).name}")

    def _on_send_message(self):
        """发送消息给 AI"""
        message = self.chat_input.text().strip()
        if not message:
            return

        # 显示用户消息
        self._add_chat_message("user", message)

        # 清空输入框
        self.chat_input.clear()

        # 异步处理 AI 响应
        self._set_status("🤖 AI 正在思考...")
        QTimer.singleShot(100, lambda: self._process_ai_response(message))

    def _on_knowledge_search(self):
        """搜索项目知识"""
        query = self.knowledge_search_input.text().strip()
        if not query:
            return

        self._set_status(f"🔍 搜索项目知识: {query}")
        # 实现知识搜索
        results = self._search_knowledge_base(query)
        self._show_knowledge_results(results)

    def _on_file_selected(self, item: QTreeWidgetItem, column: int):
        """选择文件"""
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if file_path:
            self._show_file_preview(file_path)
            self.file_selected.emit(file_path)

    def _on_new_task(self):
        """新建任务"""
        self._set_status("✨ 请描述你的任务需求...")
        self.chat_input.setFocus()

    def _on_analyze_project(self):
        """分析项目"""
        self._add_chat_message("user", "请帮我分析这个项目的结构和架构")
        self._set_status("🔍 AI 正在分析项目...")
        QTimer.singleShot(100, lambda: self._analyze_project_impl())

    def _on_refactor_request(self):
        """重构代码请求"""
        self._add_chat_message("user", "帮我找出可以重构的代码部分")
        self._set_status("🔧 AI 正在分析重构点...")

    def _on_generate_tests(self):
        """生成测试"""
        self._add_chat_message("user", "帮我为当前项目生成测试用例")
        self._set_status("🧪 AI 正在生成测试...")

    def _on_generate_docs(self):
        """生成文档"""
        self._add_chat_message("user", "帮我生成项目文档")
        self._set_status("📖 AI 正在生成文档...")

    def _on_change_selected(self, item: QListWidgetItem):
        """选择待审核更改"""
        change_id = item.data(Qt.ItemDataRole.UserRole)
        if change_id:
            self._show_change_preview(change_id)

    def _on_apply_all_changes(self):
        """应用所有更改"""
        if not self.pending_changes:
            QMessageBox.information(self, "提示", "没有待审核的更改")
            return

        QMessageBox.question(
            self,
            "确认应用",
            f"确定要应用 {len(self.pending_changes)} 个更改吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        # 应用更改
        for change in self.pending_changes:
            self._apply_change(change)

        self.pending_changes.clear()
        self.changes_list.clear()
        self._set_status("✅ 所有更改已应用")

    def _on_reject_all_changes(self):
        """拒绝所有更改"""
        self.pending_changes.clear()
        self.changes_list.clear()
        self._set_status("❌ 已拒绝所有更改")

    # ─── 核心功能实现 ──────────────────────────────────

    def _scan_project(self, project_path: str):
        """扫描项目文件"""
        self.project_files.clear()
        self.file_tree.clear()

        path = Path(project_path)

        # 忽略的文件/目录
        ignore_patterns = {
            '.git', '__pycache__', '.venv', 'node_modules',
            '.DS_Store', '*.pyc', '*.pyo'
        }

        def should_ignore(p: Path) -> bool:
            for pattern in ignore_patterns:
                if pattern in p.name or p.name.endswith(pattern):
                    return True
            return False

        def scan_dir(dir_path: Path, parent_item: Optional[QTreeWidgetItem] = None):
            for item_path in sorted(dir_path.iterdir()):
                if should_ignore(item_path):
                    continue

                if item_path.is_dir():
                    dir_item = QTreeWidgetItem([item_path.name, "📁 目录"])
                    dir_item.setData(0, Qt.ItemDataRole.UserRole, str(item_path))
                    if parent_item:
                        parent_item.addChild(dir_item)
                    else:
                        self.file_tree.addTopLevelItem(dir_item)
                    dir_item.setExpanded(True)
                    scan_dir(item_path, dir_item)
                else:
                    file_item = QTreeWidgetItem([item_path.name, "📄 文件"])
                    file_item.setData(0, Qt.ItemDataRole.UserRole, str(item_path))
                    if parent_item:
                        parent_item.addChild(file_item)
                    else:
                        self.file_tree.addTopLevelItem(file_item)

                    # 统计文件
                    ext = item_path.suffix
                    if ext not in self.project_files:
                        self.project_files[ext] = []
                    self.project_files[ext].append(str(item_path))

        scan_dir(path)

        # 更新项目信息
        total_files = sum(len(files) for files in self.project_files.values())
        self.project_info_label.setText(f"📂 {path.name} | {total_files} 个文件")

        # 生成项目摘要
        self._generate_project_summary()

    def _generate_project_summary(self):
        """生成项目摘要"""
        if not self.project_files:
            return

        summary = "## 项目结构\n\n"
        for ext, files in self.project_files.items():
            summary += f"- **{ext or '无扩展名'}**: {len(files)} 个文件\n"

        summary += f"\n## 统计\n- 总文件数: {sum(len(f) for f in self.project_files.values())}\n"
        summary += f"- 文件类型: {len(self.project_files)} 种\n"

        self.project_summary.setMarkdown(summary)

    def _add_chat_message(self, role: str, content: str, is_code: bool = False):
        """添加对话消息"""
        if role == "user":
            label = QLabel(content)
            label.setStyleSheet("""
                QLabel {
                    background: #6366F1;
                    color: white;
                    border-radius: 16px;
                    padding: 12px 16px;
                    font-size: 14px;
                }
            """)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        else:
            if is_code:
                # 代码块
                text_edit = QTextEdit()
                text_edit.setReadOnly(True)
                text_edit.setStyleSheet(STYLE_CODE_BLOCK)
                text_edit.setPlainText(content)
                text_edit.setMaximumHeight(300)
                self.chat_layout.insertWidget(self.chat_layout.count() - 1, text_edit)
                self.chat_scroll.verticalScrollBar().setValue(
                    self.chat_scroll.verticalScrollBar().maximum()
                )
                return
            else:
                label = QLabel(content)
                label.setStyleSheet("""
                    QLabel {
                        background: white;
                        color: #1F2937;
                        border: 1px solid #E5E7EB;
                        border-radius: 16px;
                        padding: 12px 16px;
                        font-size: 14px;
                    }
                """)
                label.setWordWrap(True)

        self.chat_layout.insertWidget(self.chat_layout.count() - 1, label)

        # 滚动到底部
        self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        )

        # 记录历史
        self.chat_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

    async def _process_ai_response(self, user_message: str):
        """处理 AI 响应（异步）"""
        try:
            # 构建上下文
            context = self._build_context(user_message)

            # 调用 AI（模拟，实际需要集成 Ollama）
            response = await self._call_ai(user_message, context)

            # 显示 AI 响应
            self._add_chat_message("assistant", response)

            # 如果有代码更改，添加到待审核列表
            changes = self._extract_changes(response)
            for change in changes:
                self.pending_changes.append(change)
                self._add_change_to_list(change)

            self._set_status("✅ AI 响应完成")

        except Exception as e:
            logger.error(f"AI 响应失败: {e}")
            self._add_chat_message("assistant", f"抱歉，处理请求时出错: {str(e)}")
            self._set_status(f"❌ 错误: {e}")

    def _build_context(self, user_message: str) -> Dict[str, Any]:
        """构建 AI 上下文"""
        context = {
            "project_path": self.project_path,
            "project_files": self.project_files,
            "chat_history": self.chat_history[-5:],  # 最近 5 条对话
            "user_message": user_message,
        }

        # 如果有上下文预处理器，使用它优化
        if self.context_preprocessor:
            # TODO: 集成 context_preprocessor
            pass

        return context

    async def _call_ai(self, user_message: str, context: Dict[str, Any]) -> str:
        """调用 AI 生成响应"""
        # 模拟 AI 响应（实际需要集成 Ollama）
        await asyncio.sleep(1)  # 模拟延迟

        # 根据消息内容生成不同类型的响应
        if "分析" in user_message or "结构" in user_message:
            return self._generate_analysis_response(context)
        elif "登录" in user_message or "功能" in user_message:
            return self._generate_feature_response(context)
        elif "测试" in user_message:
            return self._generate_test_response(context)
        else:
            return f"我已理解你的需求。基于当前项目结构，我将为你生成相应代码。\n\n**项目上下文:**\n- 项目路径: {self.project_path or '未指定'}\n- 文件类型: {len(self.project_files)} 种\n\n请确认是否继续？"

    def _generate_analysis_response(self, context: Dict) -> str:
        """生成分析响应"""
        return f"""## 项目分析

根据扫描结果，你的项目包含以下特点：

**文件分布:**
{chr(10).join(f"- `{ext}`: {len(files)} 个文件" for ext, files in list(self.project_files.items())[:5])}

**建议:**
1. 项目结构清晰，模块划分合理
2. 建议添加更多单元测试
3. 考虑添加 CI/CD 配置

需要我帮你做进一步分析吗？"""

    def _generate_feature_response(self, context: Dict) -> str:
        """生成功能实现响应"""
        return """## 功能实现方案

我已为你设计了用户登录功能：

**实现步骤:**
1. 创建登录页面组件
2. 添加认证 API 调用
3. 实现路由保护
4. 添加状态管理

**核心代码:**
```python
# auth_service.py
class AuthService:
    async def login(self, username: str, password: str):
        # 实现登录逻辑
        pass
```

是否让我生成完整代码并添加到项目中？"""

    def _generate_test_response(self, context: Dict) -> str:
        """生成测试响应"""
        return """## 测试生成方案

我将为项目生成测试用例：

**测试覆盖:**
1. 单元测试：核心业务逻辑
2. 集成测试：API 调用
3. E2E 测试：用户流程

**示例测试:**
```python
def test_login_success():
    result = auth_service.login("admin", "password")
    assert result.success == True
```

是否继续生成？"""

    def _extract_changes(self, response: str) -> List[Dict]:
        """从 AI 响应中提取代码更改"""
        changes = []

        # 简单的代码块提取
        import re
        code_blocks = re.findall(r'```(\w+)?\n(.*?)```', response, re.DOTALL)

        for i, (lang, code) in enumerate(code_blocks):
            changes.append({
                "id": f"change_{i}",
                "type": "new_file" if "创建" in response or "new" in response.lower() else "modify",
                "file_path": f"new_file_{i}.{lang or 'py'}",
                "content": code,
                "description": f"AI 生成的代码 ({lang or 'unknown'})",
                "status": "pending",
            })

        return changes

    def _add_change_to_list(self, change: Dict):
        """添加更改到待审核列表"""
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, change["id"])

        status_icon = "🟡" if change["status"] == "pending" else "✅"
        item.setText(f"{status_icon} {change['description']}")
        item.setToolTip(f"文件: {change['file_path']}\n\n{change['content'][:200]}")

        self.changes_list.addItem(item)

    def _show_file_preview(self, file_path: str):
        """显示文件预览"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 在对话区显示
            self._add_chat_message("assistant", f"## 文件预览: {Path(file_path).name}\n\n```{Path(file_path).suffix[1:]}\n{content[:1000]}\n```", is_code=True)

        except Exception as e:
            self._set_status(f"❌ 无法预览文件: {e}")

    def _show_change_preview(self, change_id: str):
        """显示更改预览"""
        change = next((c for c in self.pending_changes if c["id"] == change_id), None)
        if change:
            self._add_chat_message(
                "assistant",
                f"## 更改预览: {change['file_path']}\n\n```{change['content']}\n```",
                is_code=True
            )

    def _apply_change(self, change: Dict):
        """应用更改到项目"""
        if not self.project_path:
            QMessageBox.warning(self, "警告", "请先打开项目")
            return

        try:
            file_path = Path(self.project_path) / change["file_path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(change["content"])

            change["status"] = "applied"
            self._set_status(f"✅ 已应用: {change['file_path']}")

        except Exception as e:
            logger.error(f"应用更改失败: {e}")
            self._set_status(f"❌ 应用失败: {e}")

    def _search_knowledge_base(self, query: str) -> List[Dict]:
        """搜索知识库"""
        # 简单搜索实现
        results = []
        query_lower = query.lower()

        for ext, files in self.project_files.items():
            for file_path in files:
                if query_lower in file_path.lower():
                    results.append({
                        "type": "file",
                        "path": file_path,
                        "score": 10.0,
                    })

        return results

    def _show_knowledge_results(self, results: List[Dict]):
        """显示知识搜索结果"""
        if not results:
            self._add_chat_message("assistant", "未找到相关知识内容")
            return

        result_text = "## 搜索结果\n\n"
        for r in results[:10]:
            result_text += f"- `{r['path']}` (相关度: {r['score']:.1f})\n"

        self._add_chat_message("assistant", result_text)

    def _analyze_project_impl(self):
        """分析项目实现"""
        if not self.project_path:
            self._add_chat_message("assistant", "请先打开一个项目")
            return

        analysis = f"""## 项目分析报告

**基本信息:**
- 项目路径: `{self.project_path}`
- 文件类型: {len(self.project_files)} 种
- 总文件数: {sum(len(f) for f in self.project_files.values())}

**文件分布:**
{chr(10).join(f"- `{ext}`: {len(files)} 个文件" for ext, files in list(self.project_files.items())[:10])}

**建议:**
1. 保持当前架构清晰
2. 添加必要的测试覆盖
3. 考虑文档化核心模块"""

        self._add_chat_message("assistant", analysis)
        self._set_status("✅ 项目分析完成")

    # ─── UI 辅助方法 ──────────────────────────────────

    def _set_status(self, message: str):
        """设置状态栏消息"""
        self.status_label.setText(message)

    def _load_sample_project(self):
        """加载示例项目数据"""
        # 预填充一些示例数据，方便演示
        self._add_chat_message(
            "assistant",
            "👋 欢迎使用 AI IDE (Solo Mode)！\n\n"
            "我是一个 AI 编程助手，可以帮你：\n\n"
            "1. 📂 **打开项目** - 加载代码项目库\n"
            "2. 💬 **对话编程** - 描述需求，我来实现\n"
            "3. 📚 **知识检索** - 搜索项目中的知识\n"
            "4. ✅ **任务管理** - 跟踪任务和成果\n\n"
            "请先打开一个项目，或者直接告诉我你的需求！"
        )

    # ─── AI 模块初始化 ──────────────────────────────────

    def init_ai_modules(self):
        """初始化 AI 模块"""
        try:
            # 导入上下文预处理器
            from client.src.business.context_preprocessor import ContextPreprocessor
            self.context_preprocessor = ContextPreprocessor()

            logger.info("[AIDrivenIDE] AI 模块初始化成功")
        except ImportError as e:
            logger.warning(f"[AIDrivenIDE] AI 模块导入失败: {e}")
        except Exception as e:
            logger.error(f"[AIDrivenIDE] AI 模块初始化失败: {e}")

