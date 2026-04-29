"""
Editor Window - PyQt编辑器窗口
==============================

统一AI增强编辑器的PyQt UI实现

特性:
- 多模式支持 (plain/markdown/json/yaml/python/sql/html/chat)
- AI操作工具栏
- 智能补全下拉
- 语法高亮
- 主题切换
- 响应式布局
"""

import asyncio
from typing import Optional, List, Dict, Any, Callable

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
        QLabel, QComboBox, QToolBar, QStatusBar, QMenu, QMenuBar,
        QSplitter, QFrame, QSizePolicy, QScrollArea, QCheckBox,
        QListWidget, QListWidgetItem, QDialog, QDialogButtonBox,
        QLineEdit, QTextBrowser, QCompleter, QShortcut, QKeySequenceEdit,
        QGradientStops
    )
    from PyQt6.QtCore import (
        Qt, QTimer, pyqtSignal, pyqtSlot, QSize, QRect,
        QSortFilterProxyModel, QStringListModel, QRegExp, QPoint
    )
    from PyQt6.QtGui import (
        QFont, QColor, QTextCharFormat, QTextCursor, QAction,
        QPalette, QKeySequence, QTextDocument, QSyntaxHighlighter,
        QRegularExpressionValidator, QIcon, QPixmap, QPainter,
        QPen, QBrush, QLinearGradient
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt6 not available, editor UI will not be functional")

import re
from .editor_core import SmartEditor, EditorMode, EditorConfig
from .ai_operations import AIOperationType, AIOperationResult, sync_get_ai_operator
from .context_engine import ContextEngine, get_context_engine, ContextType
from .completion_engine import CompletionEngine, CompletionItem, CompletionKind, get_completion_engine
from .theme_layout import ThemeSystem, LayoutManager, ThemeType, LayoutType, get_theme_system, get_layout_manager


class SyntaxHighlighterRules:
    """语法高亮规则"""

    @staticmethod
    def get_highlighting_rules(mode: EditorMode, theme: str = 'dark') -> List[tuple]:
        """获取高亮规则"""
        dark_colors = {
            'keyword': '#569CD6',
            'string': '#CE9178',
            'comment': '#6A9955',
            'number': '#B5CEA8',
            'function': '#DCDCAA',
            'type': '#4EC9B0',
            'heading': '#569CD6',
            'bold': '#FFFFFF',
            'italic': '#808080',
            'link': '#4EC9B0',
            'code': '#CE9178',
            'list': '#DCDCAA',
            'key': '#9CDCFE',
            'literal': '#569CD6',
            'tag': '#569CD6',
            'user': '#4EC9B0',
            'ai': '#DCDCAA',
        }

        light_colors = {
            'keyword': '#0000FF',
            'string': '#A31515',
            'comment': '#008000',
            'number': '#098658',
            'function': '#795E26',
            'type': '#267F99',
            'heading': '#0000FF',
            'bold': '#000000',
            'italic': '#795E26',
            'link': '#0066CC',
            'code': '#A31515',
            'list': '#795E26',
            'key': '#0010A0',
            'literal': '#0000FF',
            'tag': '#800000',
            'user': '#267F99',
            'ai': '#795E26',
        }

        colors = dark_colors if theme == 'dark' else light_colors

        rules = {
            EditorMode.PYTHON: [
                (r'#[^\n]*', 'comment'),
                (r'"""[\s\S]*?"""', 'string'),
                (r"'''[\s\S]*?'''", 'string'),
                (r'"[^"]*"', 'string'),
                (r"'[^']*'", 'string'),
                (r'\b(def|class|if|elif|else|for|while|try|except|finally|'
                 r'with|as|import|from|return|yield|break|continue|pass|'
                 r'raise|assert|lambda|and|or|not|in|is|True|False|None|'
                 r'self|async|await)\b', 'keyword'),
                (r'\b(int|str|float|bool|list|dict|set|tuple|bytes|type|object)\b', 'type'),
                (r'\b\d+\.?\d*\b', 'number'),
            ],
            EditorMode.MARKDOWN: [
                (r'^#+\s.*', 'heading'),
                (r'\*\*.*?\*\*', 'bold'),
                (r'\*.*?\*', 'italic'),
                (r'\[.*?\]\(.*?\)', 'link'),
                (r'`[^`]+`', 'code'),
                (r'```[\s\S]*?```', 'code'),
                (r'^\s*[-*+]\s', 'list'),
            ],
            EditorMode.JSON: [
                (r'"[^"]*"\s*:', 'key'),
                (r':\s*"[^"]*"', 'string'),
                (r':\s*\d+\.?\d*', 'number'),
                (r':\s*(true|false|null)', 'literal'),
            ],
            EditorMode.YAML: [
                (r'^[\w-]+:', 'key'),
                (r':\s*\|', 'literal'),
                (r':\s*>', 'literal'),
                (r'^\s*-\s', 'list'),
                (r'#.*$', 'comment'),
            ],
            EditorMode.SQL: [
                (r'--.*$', 'comment'),
                (r'/\*[\s\S]*?\*/', 'comment'),
                (r"'[^']*'", 'string'),
                (r'\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AND|OR|'
                 r'NOT|IN|IS|NULL|AS|ORDER|BY|GROUP|HAVING|LIMIT|OFFSET|'
                 r'INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|INDEX|'
                 r'DROP|ALTER|ADD|COLUMN|PRIMARY|KEY|FOREIGN|REFERENCES|'
                 r'UNIQUE|DEFAULT|CHECK|CONSTRAINT)\b', 'keyword'),
                (r'\b(int|varchar|text|datetime|timestamp|boolean|decimal|float|double|bigint)\b', 'type'),
                (r'\b\d+\.?\d*\b', 'number'),
            ],
            EditorMode.HTML: [
                (r'<!--[\s\S]*?-->', 'comment'),
                (r'<[^/][^>]*>', 'tag'),
                (r'</[^>]+>', 'tag'),
                (r'"[^"]*"', 'string'),
                (r"'[^']*'", 'string'),
            ],
        }

        result = rules.get(mode, [])
        return [(pattern, colors.get(name, '#FFFFFF')) for pattern, name in result]


if PYQT_AVAILABLE:
    class PythonSyntaxHighlighter(QSyntaxHighlighter):
        """Python语法高亮器"""

        def __init__(self, parent=None, theme: str = 'dark'):
            super().__init__(parent)
            self.theme = theme
            self.rules = SyntaxHighlighterRules.get_highlighting_rules(EditorMode.PYTHON, theme)

        def set_theme(self, theme: str):
            self.theme = theme
            self.rules = SyntaxHighlighterRules.get_highlighting_rules(EditorMode.PYTHON, theme)
            self.rehighlight()

        def highlightBlock(self, text: str):
            for pattern, color in self.rules:
                expression = QRegularExpression(pattern)
                it = expression.globalMatch(text)
                while it.hasNext():
                    match = it.next()
                    for i in range(match.capturedLength()):
                        self.setFormat(match.capturedStart() + i, 1, QColor(color))


    class MarkdownSyntaxHighlighter(QSyntaxHighlighter):
        """Markdown语法高亮器"""

        def __init__(self, parent=None, theme: str = 'dark'):
            super().__init__(parent)
            self.theme = theme
            self.rules = SyntaxHighlighterRules.get_highlighting_rules(EditorMode.MARKDOWN, theme)

        def highlightBlock(self, text: str):
            for pattern, color in self.rules:
                expression = QRegularExpression(pattern)
                it = expression.globalMatch(text)
                while it.hasNext():
                    match = it.next()
                    for i in range(match.capturedLength()):
                        self.setFormat(match.capturedStart() + i, 1, QColor(color))


    class CompletionListModel(QStringListModel):
        """补全列表模型"""

        def __init__(self, items: List[CompletionItem] = None):
            super().__init__()
            self._items = items or []
            if items:
                self.setStringList([item.label for item in items])

        def get_item(self, index: int) -> Optional[CompletionItem]:
            if 0 <= index < len(self._items):
                return self._items[index]
            return None


    class SmartEditorWidget(QFrame):
        """
        智能编辑器控件

        统一的AI增强编辑器UI组件
        """

        # 信号
        content_changed = pyqtSignal(str)
        mode_changed = pyqtSignal(str)
        cursor_position_changed = pyqtSignal(int, int)  # line, column

        # AI操作信号
        ai_operation_requested = pyqtSignal(AIOperationType, str)  # type, selected_text
        ai_operation_completed = pyqtSignal(AIOperationType, str)  # type, result

        def __init__(
            self,
            mode: EditorMode = EditorMode.PLAIN,
            theme: str = 'dark',
            show_ai_panel: bool = True,
            parent=None
        ):
            super().__init__(parent)

            # 核心组件
            self.editor = SmartEditor(EditorConfig(mode=mode))
            self.context_engine = get_context_engine()
            self.completion_engine = get_completion_engine()
            self.theme_system = get_theme_system()
            self.layout_manager = get_layout_manager()

            # UI状态
            self._show_ai_panel = show_ai_panel
            self._theme = theme
            self._current_completions: List[CompletionItem] = []
            self._completer_visible = False

            # 初始化UI
            self._init_ui()
            self._init_shortcuts()
            self._apply_theme()

            # 绑定事件
            self._bind_events()

            # AI操作符
            self._ai_operator = None

        def _init_ui(self):
            """初始化UI"""
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            # 主布局
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)

            # 菜单栏
            self._create_menu_bar()

            # 工具栏
            self._create_toolbar()

            # 内容区域
            content_widget = QWidget()
            content_layout = QHBoxLayout(content_widget)
            content_layout.setContentsMargins(0, 0, 0, 0)
            content_layout.setSpacing(0)

            # 编辑器区域
            editor_container = QWidget()
            editor_layout = QVBoxLayout(editor_container)
            editor_layout.setContentsMargins(0, 0, 0, 0)

            # 工具条（模式选择等）
            toolbar_layout = QHBoxLayout()
            toolbar_layout.setContentsMargins(8, 4, 8, 4)

            self.mode_combo = QComboBox()
            for m in EditorMode:
                self.mode_combo.addItem(m.value, m)
            self.mode_combo.setCurrentText(self.editor.mode.value)
            self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

            self.theme_combo = QComboBox()
            self.theme_combo.addItems(['dark', 'light', 'nature'])
            self.theme_combo.setCurrentText(self._theme)
            self.theme_combo.currentTextChanged.connect(self._on_theme_changed)

            toolbar_layout.addWidget(QLabel("模式:"))
            toolbar_layout.addWidget(self.mode_combo)
            toolbar_layout.addSpacing(16)
            toolbar_layout.addWidget(QLabel("主题:"))
            toolbar_layout.addWidget(self.theme_combo)
            toolbar_layout.addStretch()

            editor_layout.addLayout(toolbar_layout)

            # 编辑区域（行号 + 文本）
            edit_area = QHBoxLayout()
            edit_area.setContentsMargins(0, 0, 0, 0)

            # 行号区域
            self.line_numbers = QLabel("1")
            self.line_numbers.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.line_numbers.setStyleSheet("""
                background: #252526;
                color: #858585;
                padding: 8px 12px;
                border-right: 1px solid #3c3c3c;
                font-family: Consolas, monospace;
            """)

            # 文本编辑区
            self.text_edit = QTextEdit()
            self.text_edit.setFont(QFont("Consolas", 14))
            self.text_edit.setStyleSheet("""
                QTextEdit {
                    background: #1e1e1e;
                    color: #d4d4d4;
                    border: none;
                    padding: 8px;
                    selection-background-color: #264f78;
                }
            """)
            self.text_edit.textChanged.connect(self._on_text_changed)
            self.text_edit.cursorPositionChanged.connect(self._on_cursor_changed)

            # 补全下拉
            self.completion_list = QListWidget()
            self.completion_list.setWindowFlags(Qt.WindowType.ToolTip)
            self.completion_list.itemClicked.connect(self._on_completion_selected)
            self.completion_list.hide()

            edit_area.addWidget(self.line_numbers)
            edit_area.addWidget(self.text_edit, 1)

            editor_layout.addLayout(edit_area)

            # AI面板
            if self._show_ai_panel:
                self.ai_panel = self._create_ai_panel()
                content_layout.addWidget(editor_container, 1)
                content_layout.addWidget(self.ai_panel)
            else:
                content_layout.addWidget(editor_container, 1)

            main_layout.addWidget(content_widget)

            # 状态栏
            self.status_bar = QStatusBar()
            self.status_bar.setStyleSheet("""
                background: #252526;
                color: #858585;
                border-top: 1px solid #3c3c3c;
            """)
            self._update_status_bar()
            main_layout.addWidget(self.status_bar)

        def _create_menu_bar(self):
            """创建菜单栏"""
            # 简化处理，不创建实际菜单栏
            pass

        def _create_toolbar(self):
            """创建AI操作工具栏"""
            pass

        def _create_ai_panel(self) -> QWidget:
            """创建AI面板"""
            panel = QFrame()
            panel.setStyleSheet("""
                background: #252526;
                border-left: 1px solid #3c3c3c;
            """)
            panel.setMaximumWidth(350)

            layout = QVBoxLayout(panel)

            # 标题
            header = QLabel("AI 助手")
            header.setStyleSheet("""
                color: #d4d4d4;
                font-size: 14px;
                font-weight: bold;
                padding: 12px;
                border-bottom: 1px solid #3c3c3c;
            """)
            layout.addWidget(header)

            # AI操作按钮
            operations_layout = QVBoxLayout()
            operations_layout.setContentsMargins(8, 8, 8, 8)
            operations_layout.setSpacing(4)

            operations = [
                ("📏 格式化", AIOperationType.FORMAT),
                ("✨ 简化", AIOperationType.SIMPLIFY),
                ("📝 扩写", AIOperationType.EXPAND),
                ("🌍 翻译", AIOperationType.TRANSLATE),
                ("💡 解释", AIOperationType.EXPLAIN),
                ("🔧 修复", AIOperationType.FIX),
                ("⚡ 优化", AIOperationType.OPTIMIZE),
                ("📄 总结", AIOperationType.SUMMARIZE),
            ]

            for label, op_type in operations:
                btn = QPushButton(label)
                btn.setStyleSheet("""
                    QPushButton {
                        background: #3c3c3c;
                        color: #d4d4d4;
                        border: 1px solid #4c4c4c;
                        border-radius: 4px;
                        padding: 8px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        background: #4c4c4c;
                        border-color: #007acc;
                    }
                """)
                btn.clicked.connect(lambda checked, t=op_type: self._request_ai_operation(t))
                operations_layout.addWidget(btn)

            layout.addLayout(operations_layout)

            # 结果区域
            result_header = QLabel("操作结果")
            result_header.setStyleSheet("""
                color: #d4d4d4;
                font-size: 12px;
                padding: 8px 12px;
                border-top: 1px solid #3c3c3c;
            """)
            layout.addWidget(result_header)

            self.ai_result = QTextBrowser()
            self.ai_result.setStyleSheet("""
                QTextBrowser {
                    background: #1e1e1e;
                    color: #d4d4d4;
                    border: none;
                    padding: 8px;
                }
            """)
            layout.addWidget(self.ai_result, 1)

            layout.addStretch()

            return panel

        def _init_shortcuts(self):
            """初始化快捷键"""
            # Ctrl+1~8: AI操作
            for i, op_type in enumerate([
                AIOperationType.FORMAT, AIOperationType.SIMPLIFY,
                AIOperationType.EXPAND, AIOperationType.TRANSLATE,
                AIOperationType.EXPLAIN, AIOperationType.FIX,
                AIOperationType.OPTIMIZE, AIOperationType.SUMMARIZE
            ], 1):
                shortcut = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
                shortcut.activated.connect(lambda t=op_type: self._request_ai_operation(t))

            # Ctrl+S: 保存
            save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
            save_shortcut.activated.connect(self._on_save)

            # Ctrl+Z: 撤销
            undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
            undo_shortcut.activated.connect(self._on_undo)

            # Ctrl+Y: 重做
            redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self)
            redo_shortcut.activated.connect(self._on_redo)

        def _bind_events(self):
            """绑定事件"""
            self.editor.on_content_change(self._handle_content_change)
            self.editor.on_mode_change(self._handle_mode_change)
            self.editor.on_cursor_change(self._handle_cursor_change)

        def _apply_theme(self):
            """应用主题"""
            styles = {
                'dark': {
                    'frame': """
                        QFrame {
                            background: #1e1e1e;
                            color: #d4d4d4;
                        }
                    """,
                    'text_edit': """
                        QTextEdit {
                            background: #1e1e1e;
                            color: #d4d4d4;
                            border: none;
                        }
                    """,
                },
                'light': {
                    'frame': """
                        QFrame {
                            background: #ffffff;
                            color: #333333;
                        }
                    """,
                    'text_edit': """
                        QTextEdit {
                            background: #ffffff;
                            color: #333333;
                            border: none;
                        }
                    """,
                },
                'nature': {
                    'frame': """
                        QFrame {
                            background: #1a2f1a;
                            color: #c8e6c8;
                        }
                    """,
                    'text_edit': """
                        QTextEdit {
                            background: #1a2f1a;
                            color: #c8e6c8;
                            border: none;
                        }
                    """,
                }
            }

            theme_styles = styles.get(self._theme, styles['dark'])
            self.setStyleSheet(theme_styles['frame'])
            self.text_edit.setStyleSheet(theme_styles['text_edit'])

        def _update_status_bar(self):
            """更新状态栏"""
            mode_text = self.editor.mode.value.upper()
            line, col = self._get_cursor_line_col()
            self.status_bar.showMessage(f"模式: {mode_text} | 行: {line}, 列: {col} | Ctrl+1-8: AI操作")

        def _get_cursor_line_col(self) -> tuple:
            """获取光标行号和列号"""
            cursor = self.text_edit.textCursor()
            return cursor.blockNumber() + 1, cursor.columnNumber() + 1

        def _on_text_changed(self):
            """文本变化处理"""
            self.editor.content = self.text_edit.toPlainText()
            self._update_line_numbers()
            self._update_status_bar()

        def _on_cursor_changed(self):
            """光标变化处理"""
            self._update_status_bar()

            # 更新上下文
            ctx = self.context_engine.analyze(
                self.editor.content,
                self.editor.cursor_pos
            )

            # 检查是否需要显示补全
            self._check_completion()

        def _update_line_numbers(self):
            """更新行号"""
            lines = self.text_edit.toPlainText().split('\n')
            line_text = '\n'.join(str(i) for i in range(1, len(lines) + 1))
            self.line_numbers.setText(line_text)

        def _on_mode_changed(self, index: int):
            """模式变化"""
            mode = self.mode_combo.currentData()
            if isinstance(mode, EditorMode):
                self.editor.set_mode(mode)
                self._update_status_bar()

        def _on_theme_changed(self, theme: str):
            """主题变化"""
            self._theme = theme
            self._apply_theme()

        def _handle_content_change(self, new_content: str, old_content: str):
            """处理内容变化"""
            if self.text_edit.toPlainText() != new_content:
                self.text_edit.setPlainText(new_content)
            self.content_changed.emit(new_content)

        def _handle_mode_change(self, mode: EditorMode):
            """处理模式变化"""
            self.mode_changed.emit(mode.value)

        def _handle_cursor_change(self, pos: int):
            """处理光标变化"""
            line, col = self._get_cursor_line_col()
            self.cursor_position_changed.emit(line, col)

        async def _request_ai_operation(self, operation: AIOperationType):
            """请求AI操作"""
            cursor = self.text_edit.textCursor()
            selected_text = cursor.selectedText()

            if not selected_text:
                # 使用整个文档
                selected_text = self.text_edit.toPlainText()

            if not selected_text:
                self.ai_result.setHtml("<span style='color: #ff9800;'>请先输入或选中要处理的内容</span>")
                return

            # 显示加载状态
            self.ai_result.setHtml("<span style='color: #858585;'>正在处理...</span>")

            try:
                # 获取AI操作符
                if self._ai_operator is None:
                    self._ai_operator = sync_get_ai_operator()

                # 执行操作
                result = await self._ai_operator.execute(
                    operation,
                    selected_text,
                    {'mode': self.editor.mode.value}
                )

                # 显示结果
                if result.success:
                    self.ai_result.setPlainText(result.result_text)
                    self.ai_operation_completed.emit(operation, result.result_text)
                else:
                    self.ai_result.setHtml(f"<span style='color: #f44336;'>{result.message}</span>")

            except Exception as e:
                self.ai_result.setHtml(f"<span style='color: #f44336;'>操作失败: {str(e)}</span>")

        def _check_completion(self):
            """检查是否需要显示补全"""
            cursor = self.text_edit.textCursor()
            text_before_cursor = self.text_edit.toPlainText()[:cursor.position()]

            # 提取光标前的单词
            words = text_before_cursor.split()
            if not words:
                return

            prefix = words[-1] if words else ""

            if len(prefix) < 2:
                self.completion_list.hide()
                return

            # 获取补全
            completions = self.completion_engine.get_word_completions(prefix)

            if completions:
                self._show_completions(completions)
            else:
                self.completion_list.hide()

        def _show_completions(self, completions: List[CompletionItem]):
            """显示补全列表"""
            self._current_completions = completions
            self.completion_list.clear()

            for item in completions:
                self.completion_list.addItem(item.label)

            # 定位到光标位置
            cursor_rect = self.text_edit.cursorRect()
            self.completion_list.move(cursor_rect.bottomLeft())
            self.completion_list.setFixedWidth(250)
            self.completion_list.show()
            self._completer_visible = True

        def _on_completion_selected(self, item: QListWidgetItem):
            """选择补全项"""
            index = self.completion_list.currentRow()
            if 0 <= index < len(self._current_completions):
                completion = self._current_completions[index]

                # 插入补全文本
                cursor = self.text_edit.textCursor()
                text_before = self.text_edit.toPlainText()[:cursor.position()]

                # 找到当前单词的起始位置
                words = text_before.split()
                if words:
                    word_start = len(text_before) - len(words[-1])
                    cursor.setPosition(word_start)
                    cursor.setPosition(cursor.position() + len(words[-1]), QTextCursor.MoveMode.KeepAnchor)
                    cursor.insertText(completion.text)

                    # 学习用户选择
                    self.completion_engine.learn_from_completion(
                        words[-1],
                        completion.label
                    )

            self.completion_list.hide()
            self._completer_visible = False

        def _on_save(self):
            """保存"""
            # 触发保存事件
            pass

        def _on_undo(self):
            """撤销"""
            if self.editor.undo():
                self.text_edit.setPlainText(self.editor.content)

        def _on_redo(self):
            """重做"""
            if self.editor.redo():
                self.text_edit.setPlainText(self.editor.content)

        # 公开API
        def get_content(self) -> str:
            """获取内容"""
            return self.text_edit.toPlainText()

        def set_content(self, content: str):
            """设置内容"""
            self.text_edit.setPlainText(content)
            self.editor.content = content

        def get_mode(self) -> EditorMode:
            """获取模式"""
            return self.editor.mode

        def set_mode(self, mode: EditorMode):
            """设置模式"""
            self.editor.set_mode(mode)
            self.mode_combo.setCurrentText(mode.value)

        def set_ai_operator(self, operator):
            """设置AI操作符"""
            self._ai_operator = operator
            self.editor.set_ai_operator(operator)


    class EditorWindow(QFrame):
        """
        编辑器窗口

        完整的编辑器窗口，支持多标签页
        """

        def __init__(
            self,
            mode: EditorMode = EditorMode.PLAIN,
            theme: str = 'dark',
            parent=None
        ):
            super().__init__(parent)

            self._theme = theme
            self._init_ui()

            # 默认创建一个编辑器
            self.add_editor(mode)

        def _init_ui(self):
            """初始化UI"""
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)

            # 创建编辑器
            self.editor_widget = SmartEditorWidget(
                mode=mode,
                theme=self._theme,
                show_ai_panel=True
            )

            layout.addWidget(self.editor_widget)

        def add_editor(self, mode: EditorMode = EditorMode.PLAIN) -> SmartEditorWidget:
            """添加编辑器标签"""
            return self.editor_widget

        def get_current_editor(self) -> Optional[SmartEditorWidget]:
            """获取当前编辑器"""
            return self.editor_widget


else:
    # PyQt6 不可用时的占位符
    class SmartEditorWidget:
        """占位类"""
        def __init__(self, *args, **kwargs):
            raise RuntimeError("PyQt6 is not available")

    class EditorWindow:
        """占位类"""
        def __init__(self, *args, **kwargs):
            raise RuntimeError("PyQt6 is not available")