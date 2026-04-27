"""
Smart Editor Panel - 智能编辑器面板
=================================

集成到 main_window.py 的智能编辑器UI面板

功能:
- 作为标签页集成到主窗口
- 支持多种编辑模式
- AI操作工具栏
- 主题切换
"""

import asyncio
from typing import Optional

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
        QLabel, QComboBox, QToolBar, QStatusBar, QMenu,
        QSplitter, QFrame, QSizePolicy, QScrollArea, QCheckBox,
        QTabWidget, QTextEdit, QLineEdit, QListWidget
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QSize
    from PyQt6.QtGui import QFont, QAction, QKeySequence
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

from ..core.smart_editor import (
    SmartEditor,
    EditorMode,
    EditorConfig,
    AIOperationType,
    sync_get_ai_operator,
    get_context_engine,
    get_completion_engine,
    get_theme_system,
)


# 全局变量用于在异步环境中使用
import_qp = '''
try:
    from PyQt6.QtWidgets import QMessageBox
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
'''


class SmartEditorPanel(QFrame):
    """
    智能编辑器面板

    作为标签页集成到主窗口
    """

    # 信号
    content_changed = pyqtSignal(str)
    mode_changed = pyqtSignal(str)

    def __init__(
        self,
        mode: EditorMode = EditorMode.PLAIN,
        theme: str = 'dark',
        parent=None
    ):
        super().__init__(parent)

        self._theme = theme
        self._editor_mode = mode
        self._ai_operator = None

        # 初始化核心组件
        self.editor = SmartEditor(EditorConfig(mode=mode))
        self.context_engine = get_context_engine()
        self.completion_engine = get_completion_engine()
        self.theme_system = get_theme_system()

        # 初始化UI
        self._init_ui()
        self._bind_events()

        # 加载AI操作符
        QTimer.singleShot(100, self._load_ai_operator)

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # 主编辑区域
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 编辑区
        editor_area = self._create_editor_area()
        content_layout.addWidget(editor_area, 1)

        # AI面板（可选）
        self.ai_panel = self._create_ai_panel()
        content_layout.addWidget(self.ai_panel)

        layout.addWidget(content_widget, 1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: #252526;
                color: #858585;
                border-top: 1px solid #3c3c3c;
            }
        """)
        self._update_status()
        layout.addWidget(self.status_bar)

    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background: #252526;
                border-bottom: 1px solid #3c3c3c;
                spacing: 4px;
                padding: 4px;
            }
            QToolBar::separator {
                background: #3c3c3c;
                width: 1px;
                margin: 4px;
            }
        """)

        # 模式选择
        mode_label = QLabel("模式:")
        mode_label.setStyleSheet("color: #d4d4d4;")
        toolbar.addWidget(mode_label)

        self.mode_combo = QComboBox()
        self.mode_combo.setStyleSheet("""
            QComboBox {
                background: #3c3c3c;
                color: #d4d4d4;
                border: 1px solid #4c4c4c;
                border-radius: 3px;
                padding: 4px 8px;
                min-width: 100px;
            }
            QComboBox:hover {
                border-color: #007acc;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        for m in EditorMode:
            self.mode_combo.addItem(m.value.upper(), m)
        self.mode_combo.setCurrentText(self._editor_mode.value.upper())
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        toolbar.addWidget(self.mode_combo)

        toolbar.addSeparator()

        # 主题切换
        theme_label = QLabel("主题:")
        theme_label.setStyleSheet("color: #d4d4d4;")
        toolbar.addWidget(theme_label)

        self.theme_combo = QComboBox()
        self.theme_combo.setStyleSheet(self.mode_combo.styleSheet())
        self.theme_combo.addItems(['dark', 'light', 'nature'])
        self.theme_combo.setCurrentText(self._theme)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        toolbar.addWidget(self.theme_combo)

        toolbar.addSeparator()

        # AI操作按钮组
        ai_operations = [
            ("📏 格式化", "Ctrl+1", AIOperationType.FORMAT),
            ("✨ 简化", "Ctrl+2", AIOperationType.SIMPLIFY),
            ("📝 扩写", "Ctrl+3", AIOperationType.EXPAND),
            ("🌍 翻译", "Ctrl+4", AIOperationType.TRANSLATE),
            ("💡 解释", "Ctrl+5", AIOperationType.EXPLAIN),
            ("🔧 修复", "Ctrl+6", AIOperationType.FIX),
            ("⚡ 优化", "Ctrl+7", AIOperationType.OPTIMIZE),
            ("📄 总结", "Ctrl+8", AIOperationType.SUMMARIZE),
        ]

        for label, shortcut, op_type in ai_operations:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #d4d4d4;
                    border: 1px solid #3c3c3c;
                    border-radius: 3px;
                    padding: 4px 8px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: #3c3c3c;
                    border-color: #007acc;
                }
                QPushButton:pressed {
                    background: #4c4c4c;
                }
            """)
            btn.clicked.connect(lambda checked, t=op_type: self._request_ai_operation(t))
            toolbar.addWidget(btn)

        toolbar.addStretch()

        return toolbar

    def _create_editor_area(self) -> QWidget:
        """创建编辑区域"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 编辑区容器
        edit_container = QWidget()
        edit_layout = QHBoxLayout(edit_container)
        edit_layout.setContentsMargins(0, 0, 0, 0)

        # 行号
        self.line_numbers = QLabel("1")
        self.line_numbers.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.line_numbers.setStyleSheet("""
            background: #1e1e1e;
            color: #858585;
            padding: 8px 12px;
            border: none;
            border-right: 1px solid #3c3c3c;
            font-family: Consolas, monospace;
            font-size: 14px;
        """)
        self.line_numbers.setFixedWidth(60)

        # 文本编辑
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
            QTextEdit:focus {
                border: 1px solid #007acc;
            }
        """)
        self.text_edit.textChanged.connect(self._on_text_changed)
        self.text_edit.cursorPositionChanged.connect(self._on_cursor_changed)

        edit_layout.addWidget(self.line_numbers)
        edit_layout.addWidget(self.text_edit, 1)

        layout.addWidget(edit_container, 1)

        return container

    def _create_ai_panel(self) -> QWidget:
        """创建AI面板"""
        panel = QFrame()
        panel.setFixedWidth(300)
        panel.setStyleSheet("""
            background: #252526;
            border-left: 1px solid #3c3c3c;
        """)

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

        # 上下文信息
        context_label = QLabel("当前上下文:")
        context_label.setStyleSheet("color: #858585; padding: 8px;")
        layout.addWidget(context_label)

        self.context_info = QLabel("等待分析...")
        self.context_info.setStyleSheet("""
            color: #d4d4d4;
            padding: 0 8px 8px;
            font-size: 12px;
        """)
        layout.addWidget(self.context_info)

        # 建议操作
        suggest_label = QLabel("建议操作:")
        suggest_label.setStyleSheet("color: #858585; padding: 8px;")
        layout.addWidget(suggest_label)

        self.suggestion_list = QListWidget()
        self.suggestion_list.setStyleSheet("""
            QListWidget {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 3px;
            }
            QListWidget::item:hover {
                background: #3c3c3c;
            }
            QListWidget::item:selected {
                background: #007acc;
            }
        """)
        self.suggestion_list.itemClicked.connect(self._on_suggestion_clicked)
        layout.addWidget(self.suggestion_list, 1)

        # 结果区域
        result_label = QLabel("操作结果:")
        result_label.setStyleSheet("color: #858585; padding: 8px;")
        layout.addWidget(result_label)

        self.ai_result = QTextEdit()
        self.ai_result.setMaximumHeight(150)
        self.ai_result.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        self.ai_result.setReadOnly(True)
        layout.addWidget(self.ai_result)

        return panel

    def _bind_events(self):
        """绑定事件"""
        self.editor.on_content_change(self._handle_content_change)
        self.editor.on_mode_change(self._handle_mode_change)

    def _load_ai_operator(self):
        """加载AI操作符"""
        try:
            self._ai_operator = sync_get_ai_operator()
        except Exception as e:
            print(f"Failed to load AI operator: {e}")

    def _on_mode_changed(self, index: int):
        """模式变化"""
        mode = self.mode_combo.currentData()
        if isinstance(mode, EditorMode):
            self._editor_mode = mode
            self.editor.set_mode(mode)
            self._update_context()

    def _on_theme_changed(self, theme: str):
        """主题变化"""
            self._theme = theme
            self._apply_theme()

    def _apply_theme(self):
        """应用主题"""
        if self._theme == 'dark':
            bg_primary = "#1e1e1e"
            bg_secondary = "#252526"
            text_primary = "#d4d4d4"
            border = "#3c3c3c"
        elif self._theme == 'light':
            bg_primary = "#ffffff"
            bg_secondary = "#f3f3f3"
            text_primary = "#333333"
            border = "#d4d4d4"
        else:  # nature
            bg_primary = "#1a2f1a"
            bg_secondary = "#243524"
            text_primary = "#c8e6c8"
            border = "#3a5a3a"

        self.setStyleSheet(f"""
            QFrame {{
                background: {bg_primary};
                color: {text_primary};
            }}
        """)

    def _on_text_changed(self):
        """文本变化"""
        content = self.text_edit.toPlainText()
        self.editor.content = content
        self._update_line_numbers()
        self._update_status()
        self._update_context()
        self.content_changed.emit(content)

    def _on_cursor_changed(self):
        """光标变化"""
        self._update_status()

    def _update_line_numbers(self):
        """更新行号"""
        lines = self.text_edit.toPlainText().split('\n')
        self.line_numbers.setText('\n'.join(str(i) for i in range(1, len(lines) + 1)))

    def _update_status(self):
        """更新状态栏"""
        line, col = self._get_cursor_pos()
        self.status_bar.showMessage(
            f"模式: {self._editor_mode.value.upper()} | "
            f"行: {line}, 列: {col} | "
            f"字符: {len(self.text_edit.toPlainText())}"
        )

    def _update_context(self):
        """更新上下文信息"""
        ctx = self.context_engine.analyze(
            self.text_edit.toPlainText(),
            self.text_edit.textCursor().position()
        )

        # 更新上下文信息显示
        ctx_text = f"类型: {ctx.context_type.value}\n"
        ctx_text += f"语言: {ctx.language or '无'}\n"
        ctx_text += f"意图: {', '.join(ctx.user_intent) or '未知'}"
        self.context_info.setText(ctx_text)

        # 更新建议操作
        self.suggestion_list.clear()
        for tool in ctx.suggested_tools[:5]:
            self.suggestion_list.addItem(f"• {tool}")

    def _get_cursor_pos(self) -> tuple:
        """获取光标位置"""
        cursor = self.text_edit.textCursor()
        return cursor.blockNumber() + 1, cursor.columnNumber() + 1

    def _handle_content_change(self, new_content: str, old_content: str):
        """处理内容变化"""
        if self.text_edit.toPlainText() != new_content:
            self.text_edit.setPlainText(new_content)

    def _handle_mode_change(self, mode: EditorMode):
        """处理模式变化"""
        self.mode_combo.setCurrentText(mode.value)
        self.mode_changed.emit(mode.value)

    async def _request_ai_operation(self, operation: AIOperationType):
        """请求AI操作"""
        cursor = self.text_edit.textCursor()
        selected_text = cursor.selectedText()

        if not selected_text:
            selected_text = self.text_edit.toPlainText()

        if not selected_text:
            self.ai_result.setHtml("<span style='color: #ff9800;'>请先输入或选中要处理的内容</span>")
            return

        self.ai_result.setHtml("<span style='color: #858585;'>正在处理...</span>")

        try:
            if self._ai_operator is None:
                self._ai_operator = sync_get_ai_operator()

            result = await self._ai_operator.execute(
                operation,
                selected_text,
                {'mode': self.editor.mode.value}
            )

            if result.success:
                self.ai_result.setPlainText(result.result_text)
                # 可选：将结果替换到编辑器
                # cursor.insertText(result.result_text)
            else:
                self.ai_result.setHtml(f"<span style='color: #f44336;'>{result.message}</span>")

        except Exception as e:
            self.ai_result.setHtml(f"<span style='color: #f44336;'>操作失败: {str(e)}</span>")

    def _on_suggestion_clicked(self, item):
        """点击建议项"""
        suggestion = item.text().lstrip('• ')
        # 映射建议到操作类型
        op_map = {
            'format': AIOperationType.FORMAT,
            'validate': AIOperationType.FIX,
            'beautify': AIOperationType.FORMAT,
            'simplify': AIOperationType.SIMPLIFY,
            'expand': AIOperationType.EXPAND,
            'translate': AIOperationType.TRANSLATE,
            'explain': AIOperationType.EXPLAIN,
            'fix': AIOperationType.FIX,
            'optimize': AIOperationType.OPTIMIZE,
            'summarize': AIOperationType.SUMMARIZE,
        }

        op_type = op_map.get(suggestion.lower())
        if op_type:
            asyncio.ensure_future(self._request_ai_operation(op_type))

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
        return self._editor_mode

    def set_mode(self, mode: EditorMode):
        """设置模式"""
        self.editor.set_mode(mode)
        self.mode_combo.setCurrentText(mode.value)

    def set_theme(self, theme: str):
        """设置主题"""
        self._theme = theme
        self.theme_combo.setCurrentText(theme)
        self._apply_theme()