"""
代码高亮渲染组件 - 支持语法高亮

功能特性：
1. 支持多种编程语言的语法高亮
2. 支持代码折叠
3. 支持行号显示
4. 支持代码复制
5. 支持语法主题切换

支持的语言：
- Python, JavaScript, TypeScript, Java, C++, C#, Go, Rust
- HTML, CSS, XML, JSON, YAML, TOML
- SQL, Shell, Markdown, Dockerfile
"""

import re
from typing import Optional, Dict, List
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLabel, QPushButton, QFrame, QScrollArea,
    QSizePolicy, QToolButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat, QBrush


class SyntaxHighlighter:
    """
    语法高亮器 - 基于正则表达式的语法高亮
    
    支持多种编程语言的语法着色。
    """
    
    def __init__(self, language: str = "python"):
        self._language = language.lower()
        self._patterns = self._get_patterns()
    
    def _get_patterns(self) -> List[Dict[str, str]]:
        """获取语言特定的语法模式"""
        patterns = {
            "python": [
                {"pattern": r"\b(True|False|None)\b", "color": "#eab308"},
                {"pattern": r"\b(def|class|import|from|return|if|elif|else|for|while|in|and|or|not|try|except|finally|raise|yield|lambda|with|as|pass|break|continue|del|global|nonlocal|assert|async|await)\b", "color": "#9333ea"},
                {"pattern": r"\b(int|str|float|bool|list|dict|tuple|set|type|object|callable|isinstance|issubclass|len|range|enumerate|zip|map|filter|sorted|reversed|sum|min|max|abs|round|pow|divmod|chr|ord|hex|oct|bin|id|hash|print|input|open|close|read|write|append|extend|insert|remove|pop|clear|keys|values|items|get|setdefault|update|copy|deepcopy|join|split|strip|replace|upper|lower|capitalize|title|startswith|endswith|find|index|count|format|encode|decode|splitlines|isalpha|isdigit|isalnum|isspace|isupper|islower|istitle|isnumeric|isdecimal|isidentifier)\b", "color": "#22d3ee"},
                {"pattern": r"#.*$", "color": "#6b7280"},
                {"pattern": r"'{3}[\s\S]*?'{3}|\"{3}[\s\S]*?\"{3}", "color": "#22c55e"},
                {"pattern": r"'[^']*'|\"[^\"]*\"", "color": "#22c55e"},
                {"pattern": r"\b(\d+\.?\d*)\b", "color": "#f97316"},
                {"pattern": r"\b(@\w+)\b", "color": "#a855f7"},
                {"pattern": r"\b(__\w+__)\b", "color": "#7c3aed"},
            ],
            "javascript": [
                {"pattern": r"\b(true|false|null|undefined|NaN|Infinity)\b", "color": "#eab308"},
                {"pattern": r"\b(var|let|const|function|return|if|else|for|while|do|switch|case|break|continue|throw|try|catch|finally|class|extends|constructor|super|new|this|import|export|default|from|async|await|yield|generator|typeof|instanceof|delete|void|instanceof)\b", "color": "#9333ea"},
                {"pattern": r"\b(console|log|warn|error|info|debug|alert|prompt|confirm|setTimeout|setInterval|clearTimeout|clearInterval|parseInt|parseFloat|Number|String|Boolean|Array|Object|Function|Date|RegExp|JSON|Math|Promise|fetch|map|filter|reduce|forEach|find|findIndex|includes|indexOf|slice|splice|push|pop|shift|unshift|concat|join|split|reverse|sort|toString|valueOf|toLocaleString|isNaN|isFinite|encodeURI|decodeURI|encodeURIComponent|decodeURIComponent)\b", "color": "#22d3ee"},
                {"pattern": r"//.*$", "color": "#6b7280"},
                {"pattern": r"/\*[\s\S]*?\*/", "color": "#6b7280"},
                {"pattern": r"'[^']*'|\"[^\"]*\"", "color": "#22c55e"},
                {"pattern": r"`[^`]*`", "color": "#22c55e"},
                {"pattern": r"\b(\d+\.?\d*)\b", "color": "#f97316"},
                {"pattern": r"\b(\w+)\s*:", "color": "#a855f7"},
            ],
            "typescript": [
                {"pattern": r"\b(true|false|null|undefined|NaN|Infinity)\b", "color": "#eab308"},
                {"pattern": r"\b(var|let|const|function|return|if|else|for|while|do|switch|case|break|continue|throw|try|catch|finally|class|extends|constructor|super|new|this|import|export|default|from|async|await|yield|interface|type|enum|namespace|module|declare|abstract|private|protected|public|readonly|static|override|implements|instanceof|typeof|delete|void|any|never|unknown|boolean|number|string|symbol|object|array|tuple|function|promise|map|set|weakmap|weakset)\b", "color": "#9333ea"},
                {"pattern": r"//.*$", "color": "#6b7280"},
                {"pattern": r"/\*[\s\S]*?\*/", "color": "#6b7280"},
                {"pattern": r"'[^']*'|\"[^\"]*\"", "color": "#22c55e"},
                {"pattern": r"`[^`]*`", "color": "#22c55e"},
                {"pattern": r"\b(\d+\.?\d*)\b", "color": "#f97316"},
                {"pattern": r"\b(\w+)\s*:", "color": "#a855f7"},
            ],
            "html": [
                {"pattern": r"<!--[\s\S]*?-->", "color": "#6b7280"},
                {"pattern": r"<(\/?\w+)([^>]*)>", "color": "#9333ea"},
                {"pattern": r"(\w+)\s*=\s*['\"]([^'\"]*)['\"]", "color": "#22c55e"},
                {"pattern": r"(href|src|class|id|style|title|alt|width|height|type|name|value|placeholder|data-\w+)", "color": "#f97316"},
                {"pattern": r"<!\[CDATA\[.*?]]>", "color": "#6b7280"},
            ],
            "css": [
                {"pattern": r"/\*[\s\S]*?\*/", "color": "#6b7280"},
                {"pattern": r"(\*|body|html|div|span|p|a|img|ul|ol|li|table|tr|td|th|form|input|button|select|textarea|h[1-6]|header|footer|nav|section|article|aside|main|figure|figcaption|mark|time|small|strong|em|i|b|u|s|del|ins|sub|sup|q|blockquote|cite|code|pre|hr|br|wbr|canvas|svg|video|audio|source|iframe|embed|object|param|map|area|base|link|meta|script|noscript|style|title|head|body|html)", "color": "#9333ea"},
                {"pattern": r"(\{|\}|\:|\;|,)", "color": "#64748b"},
                {"pattern": r"#[0-9a-fA-F]{3,8}", "color": "#f97316"},
                {"pattern": r"rgb\([^)]+\)|rgba\([^)]+\)|hsl\([^)]+\)|hsla\([^)]+\)", "color": "#f97316"},
                {"pattern": r"\b(px|em|rem|%|vh|vw|vmin|vmax|deg|rad|turn|s|ms|Hz|kHz|dpi|dpcm|dppx)\b", "color": "#22d3ee"},
                {"pattern": r"\b(none|auto|inherit|initial|unset|block|inline|inline-block|flex|grid|absolute|relative|fixed|static|hidden|visible|center|left|right|top|bottom|justify|align|padding|margin|border|background|color|font|text|display|position|overflow|float|clear|z-index|width|height|min-width|min-height|max-width|max-height|box-sizing|content-box|border-box|border-radius|box-shadow|text-shadow|opacity|cursor|pointer-events|transform|transition|animation)\b", "color": "#22c55e"},
                {"pattern": r"('[^']*'|\"[^\"]*\")", "color": "#a855f7"},
            ],
            "json": [
                {"pattern": r"//.*$", "color": "#6b7280"},
                {"pattern": r"/\*[\s\S]*?\*/", "color": "#6b7280"},
                {"pattern": r"\"([^\"]*)\":", "color": "#9333ea"},
                {"pattern": r":\s*\"([^\"]*)\"", "color": "#22c55e"},
                {"pattern": r":\s*(\d+\.?\d*)", "color": "#f97316"},
                {"pattern": r":\s*(true|false|null)", "color": "#eab308"},
            ],
            "sql": [
                {"pattern": r"--.*$", "color": "#6b7280"},
                {"pattern": r"/\*[\s\S]*?\*/", "color": "#6b7280"},
                {"pattern": r"\b(SELECT|FROM|WHERE|AND|OR|NOT|IN|LIKE|BETWEEN|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AS|ORDER|BY|GROUP|HAVING|LIMIT|OFFSET|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|DROP|ALTER|ADD|COLUMN|INDEX|VIEW|TRIGGER|PROCEDURE|FUNCTION|IF|ELSE|CASE|WHEN|THEN|END|UNION|ALL|DISTINCT|COUNT|SUM|AVG|MIN|MAX|COALESCE|NULLIF|CAST|CONVERT|SUBSTRING|LEFT|RIGHT|LENGTH|UPPER|LOWER|TRIM|REPLACE|DATE|NOW|CURRENT_DATE|CURRENT_TIME|TIMESTAMP|PRIMARY|KEY|FOREIGN|REFERENCES|DEFAULT|NOT|NULL|CHECK|UNIQUE|AUTO_INCREMENT)\b", "color": "#9333ea"},
                {"pattern": r"'[^']*'", "color": "#22c55e"},
                {"pattern": r"\b(\d+\.?\d*)\b", "color": "#f97316"},
            ],
            "bash": [
                {"pattern": r"#.*$", "color": "#6b7280"},
                {"pattern": r"\b(if|then|else|elif|fi|case|esac|for|do|done|while|until|function|return|exit|export|source|cd|ls|pwd|cp|mv|rm|mkdir|rmdir|chmod|chown|cat|head|tail|grep|sed|awk|cut|sort|uniq|wc|find|xargs|echo|printf|read|set|unset|declare|local|readonly|alias|unalias|history|help|man|which|whereis|whoami|date|cal|sleep|wait|kill|ps|top|df|du|mount|umount|tar|gzip|gunzip|zip|unzip|ssh|scp|rsync|curl|wget|git|npm|pip|python|node|java|gcc|make|cmake)\b", "color": "#9333ea"},
                {"pattern": r"\$(\w+)", "color": "#22d3ee"},
                {"pattern": r"'[^']*'|\"[^\"]*\"", "color": "#22c55e"},
                {"pattern": r"\b(\d+)\b", "color": "#f97316"},
                {"pattern": r"(\||&&|;;|\<|\>|\>>|\<\<|\&\&|\|\|)", "color": "#64748b"},
            ],
            "markdown": [
                {"pattern": r"^#{1,6}\s+.*$", "color": "#9333ea"},
                {"pattern": r"\*\*(.+?)\*\*", "color": "#eab308"},
                {"pattern": r"\*(.+?)\*", "color": "#22d3ee"},
                {"pattern": r"`([^`]+)`", "color": "#f97316"},
                {"pattern": r"```[\s\S]*?```", "color": "#6b7280"},
                {"pattern": r"\[([^\]]+)\]\(([^)]+)\)", "color": "#22c55e"},
                {"pattern": r"^[-*+]\s+.*$", "color": "#a855f7"},
                {"pattern": r"^\d+\.\s+.*$", "color": "#a855f7"},
                {"pattern": r">.*$", "color": "#64748b"},
            ],
        }
        
        return patterns.get(self._language, patterns["python"])
    
    def highlight(self, text: str) -> str:
        """
        对文本进行语法高亮
        
        Args:
            text: 源代码文本
            
        Returns:
            HTML格式的高亮文本
        """
        # 转义HTML特殊字符
        html = text.replace('&', '&amp;')
        html = html.replace('<', '&lt;')
        html = html.replace('>', '&gt;')
        
        # 应用语法高亮模式
        for pattern_info in self._patterns:
            pattern = pattern_info["pattern"]
            color = pattern_info["color"]
            
            # 匹配并替换
            html = re.sub(pattern, f'<span style="color: {color};">\\g<0></span>', html)
        
        # 添加行号和背景
        lines = html.split('\n')
        numbered_lines = []
        
        for i, line in enumerate(lines, 1):
            line_num = f'<span style="color: #6b7280; width: 40px; display: inline-block; text-align: right; padding-right: 12px; user-select: none;">{i}</span>'
            numbered_lines.append(f'<div>{line_num}{line}</div>')
        
        return '\n'.join(numbered_lines)


class CodeHighlighterWidget(QWidget):
    """
    代码高亮显示控件
    
    功能：
    1. 语法高亮显示
    2. 行号显示
    3. 代码复制
    4. 语言选择
    5. 代码折叠
    """
    
    code_copied = pyqtSignal()
    language_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_language = "python"
        self._code = ""
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # 顶部工具栏
        self.toolbar = QFrame()
        self.toolbar.setStyleSheet("background-color: #1e293b; padding: 8px;")
        self.toolbar_layout = QHBoxLayout(self.toolbar)
        self.toolbar_layout.setContentsMargins(8, 4, 8, 4)
        self.toolbar_layout.setSpacing(8)
        
        # 语言选择
        self.lang_button = QToolButton()
        self.lang_button.setText(self._current_language.upper())
        self.lang_button.setStyleSheet("""
            QToolButton {
                background-color: #334155;
                color: #e2e8f0;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: #475569;
            }
        """)
        self.lang_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._setup_lang_menu()
        self.toolbar_layout.addWidget(self.lang_button)
        
        self.toolbar_layout.addStretch()
        
        # 复制按钮
        self.copy_button = QToolButton()
        self.copy_button.setText("📋")
        self.copy_button.setToolTip("复制代码")
        self.copy_button.clicked.connect(self._copy_code)
        self.toolbar_layout.addWidget(self.copy_button)
        
        # 折叠按钮
        self.fold_button = QToolButton()
        self.fold_button.setText("📖")
        self.fold_button.setToolTip("折叠代码")
        self.fold_button.clicked.connect(self._toggle_fold)
        self.toolbar_layout.addWidget(self.fold_button)
        
        self.layout.addWidget(self.toolbar)
        
        # 代码显示区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")
        self.layout.addWidget(self.scroll_area, 1)
        
        # 代码容器
        self.code_container = QFrame()
        self.code_container.setStyleSheet("background-color: #0f172a;")
        self.code_layout = QHBoxLayout(self.code_container)
        self.code_layout.setContentsMargins(0, 0, 0, 0)
        
        # 行号区域
        self.line_numbers = QTextEdit()
        self.line_numbers.setReadOnly(True)
        self.line_numbers.setFixedWidth(50)
        self.line_numbers.setStyleSheet("""
            QTextEdit {
                background-color: #1e293b;
                color: #64748b;
                font-family: monospace;
                font-size: 13px;
                border: none;
                padding: 12px 4px;
                text-align: right;
            }
        """)
        self.code_layout.addWidget(self.line_numbers)
        
        # 代码编辑区域
        self.code_edit = QTextEdit()
        self.code_edit.setReadOnly(True)
        self.code_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0f172a;
                color: #e2e8f0;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 13px;
                border: none;
                padding: 12px;
                line-height: 1.5;
            }
        """)
        self.code_layout.addWidget(self.code_edit)
        
        self.scroll_area.setWidget(self.code_container)
        
        # 是否折叠
        self._is_folded = False
    
    def _setup_lang_menu(self):
        """设置语言菜单"""
        from PyQt6.QtWidgets import QMenu
        
        menu = QMenu()
        
        languages = [
            ("Python", "python"),
            ("JavaScript", "javascript"),
            ("TypeScript", "typescript"),
            ("Java", "java"),
            ("C++", "cpp"),
            ("C#", "csharp"),
            ("Go", "go"),
            ("Rust", "rust"),
            ("HTML", "html"),
            ("CSS", "css"),
            ("JSON", "json"),
            ("SQL", "sql"),
            ("Bash", "bash"),
            ("Markdown", "markdown"),
        ]
        
        for name, code in languages:
            action = menu.addAction(name)
            action.triggered.connect(lambda checked, code=code: self.set_language(code))
        
        self.lang_button.setMenu(menu)
    
    def set_code(self, code: str):
        """设置代码内容"""
        self._code = code
        self._update_display()
    
    def set_language(self, language: str):
        """设置语言"""
        self._current_language = language.lower()
        self.lang_button.setText(self._current_language.upper())
        self.language_changed.emit(language)
        self._update_display()
    
    def _update_display(self):
        """更新显示"""
        if not self._code:
            return
        
        # 更新行号
        line_count = len(self._code.split('\n'))
        line_numbers_text = '\n'.join(str(i) for i in range(1, line_count + 1))
        self.line_numbers.setPlainText(line_numbers_text)
        
        # 应用语法高亮
        highlighter = SyntaxHighlighter(self._current_language)
        highlighted_html = highlighter.highlight(self._code)
        
        # 设置HTML内容
        self.code_edit.setHtml(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; line-height: 1.5; }}
                </style>
            </head>
            <body>
                {highlighted_html}
            </body>
            </html>
        """)
    
    def _copy_code(self):
        """复制代码到剪贴板"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self._code)
        self.code_copied.emit()
        
        # 临时更改按钮图标表示复制成功
        self.copy_button.setText("✓")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.copy_button.setText("📋"))
    
    def _toggle_fold(self):
        """切换代码折叠状态"""
        self._is_folded = not self._is_folded
        
        if self._is_folded:
            # 折叠状态：只显示前几行
            lines = self._code.split('\n')
            if len(lines) > 10:
                folded_code = '\n'.join(lines[:5]) + f'\n... ({len(lines) - 5} 行省略)'
                self.code_edit.setPlainText(folded_code)
            self.fold_button.setText("📗")
            self.fold_button.setToolTip("展开代码")
        else:
            # 展开状态
            self._update_display()
            self.fold_button.setText("📖")
            self.fold_button.setToolTip("折叠代码")
    
    def get_code(self) -> str:
        """获取代码内容"""
        return self._code
    
    def set_read_only(self, read_only: bool):
        """设置是否只读"""
        self.code_edit.setReadOnly(read_only)


class CodeBlockRenderer:
    """
    代码块渲染器 - 将代码块转换为Qt控件
    
    支持从Markdown代码块中提取代码并渲染。
    """
    
    def __init__(self):
        pass
    
    def render(self, code: str, language: str = "python", parent=None) -> QWidget:
        """
        渲染代码块
        
        Args:
            code: 代码文本
            language: 编程语言
            parent: 父控件
            
        Returns:
            代码高亮控件
        """
        widget = CodeHighlighterWidget(parent)
        widget.set_code(code)
        widget.set_language(language)
        return widget
    
    def render_markdown_code_block(self, markdown_text: str, parent=None) -> Optional[QWidget]:
        """
        从Markdown文本中提取并渲染代码块
        
        Args:
            markdown_text: Markdown文本
            parent: 父控件
            
        Returns:
            代码高亮控件（如果找到代码块）
        """
        # 匹配代码块
        import re
        match = re.search(r'```(\w*)\s*\n([\s\S]*?)```', markdown_text)
        
        if match:
            language = match.group(1) or "python"
            code = match.group(2)
            return self.render(code, language, parent)
        
        return None


# 全局函数
def highlight_code(code: str, language: str = "python") -> str:
    """
    对代码进行语法高亮，返回HTML
    
    Args:
        code: 源代码
        language: 编程语言
        
    Returns:
        HTML格式的高亮文本
    """
    highlighter = SyntaxHighlighter(language)
    return highlighter.highlight(code)