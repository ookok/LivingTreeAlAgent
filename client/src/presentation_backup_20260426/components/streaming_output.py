"""
流式输出组件 - 实时展示 AI 思考和生成过程
用于 PyQt6 AI-IDE，实现零延迟的 AI 响应界面

特性:
- 流式文本输出（逐字/逐词/逐行）
- 打字机效果
- Markdown 渲染
- 代码块高亮
- 思考过程展示
"""

import time
import re
import threading
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

# PyQt6 imports
try:
    from PyQt6.QtWidgets import (
        QWidget, QTextEdit, QTextBrowser, QVBoxLayout, 
        QLabel, QApplication, QSizePolicy
    )
    from PyQt6.QtCore import (
        Qt, QTimer, QObject, pyqtSignal, pyqtSlot, QThread,
        QRegularExpression
    )
    from PyQt6.QtGui import (
        QTextCursor, QTextCharFormat, QColor, QFont,
        QSyntaxHighlighter, QTextDocument, QPalette
    )
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    print("[StreamingOutput] PyQt6 not available, using text mode")


# ============== 样式定义 ==============

DEFAULT_STYLES = """
/* 主容器 */
StreamingOutputWidget {
    background-color: #1e1e1e;
    border: 1px solid #3e3e42;
    border-radius: 8px;
    padding: 10px;
}

/* 思考过程区域 */
.ThinkingArea {
    background-color: #252526;
    border: 1px solid #3e3e42;
    border-radius: 6px;
    padding: 12px;
    margin-bottom: 10px;
}

/* 主内容区域 */
.MainContent {
    background-color: #1e1e1e;
    border: 1px solid #3e3e42;
    border-radius: 6px;
    padding: 12px;
}

/* 状态指示器 */
.StatusIndicator {
    background-color: #007acc;
    border-radius: 4px;
    padding: 4px 12px;
    color: white;
    font-weight: bold;
}

/* 代码块 */
.CodeBlock {
    background-color: #1a1a1a;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    padding: 10px;
    font-family: 'Consolas', 'Monaco', monospace;
}

/* 错误提示 */
.ErrorText {
    color: #f48771;
    font-weight: bold;
}

/* 成功提示 */
.SuccessText {
    color: #89d185;
    font-weight: bold;
}

/* 警告提示 */
.WarningText {
    color: #dcdcaa;
}
"""


# ============== 流式类型枚举 ==============

class StreamingType(Enum):
    """流式输出类型"""
    THINKING = "thinking"      # AI 思考过程
    CODE = "code"            # 代码生成
    TEXT = "text"            # 普通文本
    MARKDOWN = "markdown"    # Markdown 渲染
    ERROR = "error"          # 错误信息
    SUCCESS = "success"      # 成功信息
    STEP = "step"            # 执行步骤


# ============== 数据结构 ==============

@dataclass
class StreamChunk:
    """流式数据块"""
    content: str
    type: StreamingType = StreamingType.TEXT
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ThinkingStep:
    """思考步骤"""
    step: int
    label: str
    icon: str
    status: str  # pending, active, completed, failed
    message: str = ""
    duration: float = 0.0


# ============== Markdown 高亮器 ==============

class MarkdownHighlighter(QSyntaxHighlighter):
    """Markdown 语法高亮器"""
    
    # 颜色定义
    COLORS = {
        'heading': '#569cd6',      # 蓝色
        'bold': '#dcdcaa',          # 黄色
        'italic': '#ce9178',         # 橙色
        'code': '#4ec9b0',          # 青色
        'link': '#4ec9b0',          # 青色
        'list': '#d7ba7d',          # 金色
        'quote': '#6a9955',         # 绿色
        'hr': '#3e3e42',            # 灰色
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._highlighting_rules = []
        self._setup_rules()
    
    def _setup_rules(self):
        """设置高亮规则"""
        # 标题 (# ## ###)
        heading_fmt = QTextCharFormat()
        heading_fmt.setForeground(QColor(self.COLORS['heading']))
        heading_fmt.setFontWeight(QFont.Weight.Bold)
        self._highlighting_rules.append((r'^#{1,6}\s+.+$', heading_fmt))
        
        # 粗体 (**text** 或 __text__)
        bold_fmt = QTextCharFormat()
        bold_fmt.setFontWeight(QFont.Weight.Bold)
        bold_fmt.setForeground(QColor(self.COLORS['bold']))
        self._highlighting_rules.append((r'\*\*.+?\*\*', bold_fmt))
        self._highlighting_rules.append((r'__.+?__', bold_fmt))
        
        # 斜体 (*text* 或 _text_)
        italic_fmt = QTextCharFormat()
        italic_fmt.setFontStyle(QTextCharFormat.Style.StyleItalic)
        italic_fmt.setForeground(QColor(self.COLORS['italic']))
        self._highlighting_rules.append((r'\*.+?\*', italic_fmt))
        self._highlighting_rules.append((r'_.+?_', italic_fmt))
        
        # 行内代码 (`code`)
        code_fmt = QTextCharFormat()
        code_fmt.setFontFamily('Consolas')
        code_fmt.setForeground(QColor(self.COLORS['code']))
        self._highlighting_rules.append((r'`[^`]+`', code_fmt))
        
        # 链接 [text](url)
        link_fmt = QTextCharFormat()
        link_fmt.setForeground(QColor(self.COLORS['link']))
        self._highlighting_rules.append((r'\[.+\]\(.+\)', link_fmt))
        
        # 列表 (- 或 1.)
        list_fmt = QTextCharFormat()
        list_fmt.setForeground(QColor(self.COLORS['list']))
        self._highlighting_rules.append((r'^[\-\*]\s+.+$', list_fmt))
        self._highlighting_rules.append((r'^\d+\.\s+.+$', list_fmt))
        
        # 引用 >
        quote_fmt = QTextCharFormat()
        quote_fmt.setForeground(QColor(self.COLORS['quote']))
        self._highlighting_rules.append((r'^>\s+.+$', quote_fmt))
    
    def highlightBlock(self, text: str):
        """高亮一个文本块"""
        for pattern, fmt in self._highlighting_rules:
            try:
                regex = QRegularExpression(pattern)
                iterator = regex.globalMatch(text)
                while iterator.hasNext():
                    match = iterator.next()
                    self.setFormat(match.capturedStart(), 
                                   match.capturedLength(), 
                                   fmt)
            except Exception:
                pass


# ============== 代码块高亮器 ==============

class CodeBlockHighlighter(QSyntaxHighlighter):
    """代码块语法高亮器"""
    
    # Python 关键字颜色
    KEYWORD_COLOR = QColor('#569cd6')
    STRING_COLOR = QColor('#ce9178')
    COMMENT_COLOR = QColor('#6a9955')
    NUMBER_COLOR = QColor('#b5cea8')
    FUNCTION_COLOR = QColor('#dcdcaa')
    CLASS_COLOR = QColor('#4ec9b0')
    
    def __init__(self, parent=None, language='python'):
        super().__init__(parent)
        self.language = language
        self._setup_keywords()
    
    def _setup_keywords(self):
        """设置语言关键字"""
        self.keywords = {
            'python': [
                'and', 'as', 'assert', 'async', 'await', 'break',
                'class', 'continue', 'def', 'del', 'elif', 'else',
                'except', 'finally', 'for', 'from', 'global', 'if',
                'import', 'in', 'is', 'lambda', 'None', 'nonlocal',
                'not', 'or', 'pass', 'raise', 'return', 'True', 'False',
                'try', 'while', 'with', 'yield'
            ],
            'javascript': [
                'async', 'await', 'break', 'case', 'catch', 'class',
                'const', 'continue', 'debugger', 'default', 'delete',
                'do', 'else', 'export', 'extends', 'false', 'finally',
                'for', 'function', 'if', 'import', 'in', 'instanceof',
                'let', 'new', 'null', 'return', 'static', 'super',
                'switch', 'this', 'throw', 'true', 'try', 'typeof',
                'undefined', 'var', 'void', 'while', 'with', 'yield'
            ]
        }
    
    def highlightBlock(self, text: str):
        """高亮代码块"""
        # 字符串
        string_fmt = QTextCharFormat()
        string_fmt.setForeground(self.STRING_COLOR)
        self._highlight_string(text, string_fmt, '"')
        self._highlight_string(text, string_fmt, "'")
        
        # 注释
        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(self.COMMENT_COLOR)
        self._highlight_pattern(text, r'#.*$', comment_fmt)
        self._highlight_pattern(text, r'//.*$', comment_fmt)
        
        # 数字
        number_fmt = QTextCharFormat()
        number_fmt.setForeground(self.NUMBER_COLOR)
        self._highlight_pattern(text, r'\b\d+\.?\d*\b', number_fmt)
        
        # 关键字
        keyword_fmt = QTextCharFormat()
        keyword_fmt.setForeground(self.KEYWORD_COLOR)
        if self.language in self.keywords:
            for kw in self.keywords[self.language]:
                self._highlight_pattern(text, rf'\b{kw}\b', keyword_fmt)
        
        # 函数调用
        func_fmt = QTextCharFormat()
        func_fmt.setForeground(self.FUNCTION_COLOR)
        self._highlight_pattern(text, r'\b\w+(?=\()', func_fmt)
    
    def _highlight_string(self, text, fmt, quote):
        """高亮字符串"""
        pattern = rf'{quote}[^{quote}]*{quote}'
        self._highlight_pattern(text, pattern, fmt)
    
    def _highlight_pattern(self, text, pattern, fmt):
        """根据正则表达式高亮"""
        try:
            regex = QRegularExpression(pattern)
            iterator = regex.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(),
                               match.capturedLength(),
                               fmt)
        except Exception:
            pass


# ============== 流式输出引擎 ==============

class StreamingEngine(QObject):
    """流式输出引擎 - 处理文本流"""
    
    # 信号定义
    chunk_ready = pyqtSignal(str, str)  # content, type
    stream_started = pyqtSignal()
    stream_finished = pyqtSignal()
    step_changed = pyqtSignal(int, str, str)  # step, status, message
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent=None, chunk_delay: float = 0.01):
        super().__init__(parent)
        self.chunk_delay = chunk_delay  # 字符延迟（秒）
        self._running = False
        self._buffer = ""
        self._chunks: List[StreamChunk] = []
        self._steps: List[ThinkingStep] = []
        self._current_step = 0
        self._lock = threading.Lock()
    
    def start_stream(self):
        """开始流式输出"""
        self._running = True
        self._buffer = ""
        self._chunks.clear()
        self.stream_started.emit()
    
    def end_stream(self):
        """结束流式输出"""
        self._running = False
        self.stream_finished.emit()
    
    def add_chunk(self, content: str, chunk_type: StreamingType = StreamingType.TEXT):
        """添加一个数据块"""
        with self._lock:
            chunk = StreamChunk(content=content, type=chunk_type)
            self._chunks.append(chunk)
            self.chunk_ready.emit(content, chunk_type.value)
    
    def add_step(self, label: str, icon: str = "🔄") -> int:
        """添加思考步骤"""
        step = ThinkingStep(
            step=len(self._steps) + 1,
            label=label,
            icon=icon,
            status="pending"
        )
        self._steps.append(step)
        return step.step
    
    def activate_step(self, step_num: int, message: str = ""):
        """激活步骤"""
        if step_num <= len(self._steps):
            step = self._steps[step_num - 1]
            step.status = "active"
            step.message = message
            self.step_changed.emit(step_num, "active", message)
    
    def complete_step(self, step_num: int, message: str = ""):
        """完成步骤"""
        if step_num <= len(self._steps):
            step = self._steps[step_num - 1]
            step.status = "completed"
            step.message = message
            self.step_changed.emit(step_num, "completed", message)
    
    def fail_step(self, step_num: int, error: str):
        """步骤失败"""
        if step_num <= len(self._steps):
            step = self._steps[step_num - 1]
            step.status = "failed"
            step.message = error
            self.step_changed.emit(step_num, "failed", error)
            self.error_occurred.emit(error)
    
    @property
    def steps(self) -> List[ThinkingStep]:
        return self._steps.copy()


# ============== 流式输出文本浏览器 ==============

class StreamingTextBrowser(QTextBrowser if PYQT6_AVAILABLE else QObject):
    """支持流式输出的文本浏览器"""
    
    if PYQT6_AVAILABLE:
        # 信号
        typing_finished = pyqtSignal()
        
        def __init__(self, parent=None, typing_speed: int = 30):
            """
            Args:
                parent: 父控件
                typing_speed: 打字速度（字符/秒）
            """
            super().__init__(parent)
            self.typing_speed = typing_speed  # 默认 30 字符/秒
            self._typing_timer = QTimer(self)
            self._pending_text = ""
            self._current_index = 0
            self._highlighter = None
            
            self._typing_timer.timeout.connect(self._on_typing_tick)
            
            # 基础设置
            self.setOpenExternalLinks(True)
            self.setAcceptRichText(True)
            
            # 字体设置
            font = QFont('Consolas')
            font.setPointSize(10)
            self.setFont(font)
            
            # 样式
            self.setStyleSheet("""
                QTextBrowser {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: none;
                    padding: 10px;
                }
            """)
        
        def set_markdown_mode(self, enabled: bool = True):
            """设置 Markdown 模式"""
            if enabled and self._highlighter is None:
                self._highlighter = MarkdownHighlighter(self.document())
            elif not enabled and self._highlighter:
                self._highlighter.setDocument(None)
                self._highlighter = None
        
        def set_code_mode(self, language: str = 'python'):
            """设置代码高亮模式"""
            if self._highlighter:
                self._highlighter.setDocument(None)
            self._highlighter = CodeBlockHighlighter(self.document(), language)
        
        def stream_text(self, text: str, chunk_size: int = 1):
            """
            流式显示文本（打字机效果）
            
            Args:
                text: 要显示的文本
                chunk_size: 每次显示的字符数
            """
            self._pending_text = text
            self._current_index = 0
            
            # 计算延迟（毫秒）
            if self.typing_speed > 0:
                delay = int(1000 / (self.typing_speed * chunk_size))
                delay = max(10, min(delay, 100))  # 限制在 10-100ms
            else:
                delay = 0  # 即时显示
            
            self._typing_timer.start(delay)
        
        def _on_typing_tick(self):
            """打字机效果定时器回调"""
            if self._current_index < len(self._pending_text):
                # 追加文本
                chunk = self._pending_text[self._current_index:self._current_index + 1]
                self._append_html(self._escape_html(chunk))
                self._current_index += 1
            else:
                self._typing_timer.stop()
                self.typing_finished.emit()
        
        def append_stream(self, text: str, stream_type: StreamingType = StreamingType.TEXT):
            """
            流式追加文本
            
            Args:
                text: 要追加的文本
                stream_type: 文本类型
            """
            # 根据类型设置颜色
            color_map = {
                StreamingType.THINKING: '#6a9955',
                StreamingType.CODE: '#ce9178',
                StreamingType.ERROR: '#f48771',
                StreamingType.SUCCESS: '#89d185',
                StreamingType.WARNING: '#dcdcaa',
                StreamingType.STEP: '#569cd6',
            }
            
            color = color_map.get(stream_type, '#d4d4d4')
            
            if stream_type == StreamingType.MARKDOWN:
                self._append_html(self._render_markdown(text))
            else:
                escaped = self._escape_html(text)
                self._append_html(f'<span style="color: {color};">{escaped}</span>')
        
        def _append_html(self, html: str):
            """追加 HTML 内容"""
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertHtml(html)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
        
        def _escape_html(self, text: str) -> str:
            """转义 HTML 特殊字符"""
            return (text
                    .replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                    .replace("'", '&#39;')
                    .replace('\n', '<br/>')
                    .replace('  ', '&nbsp;&nbsp;'))
        
        def _render_markdown(self, text: str) -> str:
            """简单的 Markdown 渲染"""
            # 标题
            text = re.sub(r'^### (.+)$', r'<h3 style="color:#569cd6">\1</h3>', text, flags=re.MULTILINE)
            text = re.sub(r'^## (.+)$', r'<h2 style="color:#569cd6">\1</h2>', text, flags=re.MULTILINE)
            text = re.sub(r'^# (.+)$', r'<h1 style="color:#569cd6">\1</h1>', text, flags=re.MULTILINE)
            
            # 粗体
            text = re.sub(r'\*\*(.+?)\*\*', r'<b style="color:#dcdcaa">\1</b>', text)
            
            # 斜体
            text = re.sub(r'\*(.+?)\*', r'<i style="color:#ce9178">\1</i>', text)
            
            # 行内代码
            text = re.sub(r'`([^`]+)`', r'<code style="background:#2d2d2d;color:#4ec9b0">\1</code>', text)
            
            # 换行
            text = text.replace('\n', '<br/>')
            
            return text
        
        def append_code_block(self, code: str, language: str = 'python'):
            """追加代码块"""
            # 设置代码高亮
            self._highlighter = CodeBlockHighlighter(self.document(), language)
            
            # 添加代码块标签
            self._append_html('<pre style="background:#1a1a1a;border:1px solid #3e3e42;border-radius:4px;padding:10px;margin:10px 0;"><code>')
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertPlainText(code)
            self._append_html('</code></pre>')
        
        def clear_content(self):
            """清空内容"""
            self.clear()
        
        def get_content(self) -> str:
            """获取纯文本内容"""
            return self.toPlainText()
    else:
        # 无 PyQt6 时的降级实现
        def __init__(self, *args, **kwargs):
            pass
        
        def stream_text(self, text: str, **kwargs):
            print(text, end='', flush=True)
        
        def append_stream(self, text: str, **kwargs):
            print(text, end='', flush=True)
        
        def clear_content(self):
            pass


# ============== 思考过程面板 ==============

class ThinkingPanel(QWidget if PYQT6_AVAILABLE else QObject):
    """思考过程展示面板"""
    
    if PYQT6_AVAILABLE:
        step_clicked = pyqtSignal(int)  # 步骤点击信号
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self._steps: List[ThinkingStep] = []
            self._setup_ui()
        
        def _setup_ui(self):
            """设置 UI"""
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            
            # 标题
            title = QLabel("💭 思考过程")
            title.setStyleSheet("""
                QLabel {
                    color: #d4d4d4;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 5px;
                }
            """)
            layout.addWidget(title)
            
            # 步骤列表容器
            self._steps_widget = QWidget()
            self._steps_layout = QVBoxLayout(self._steps_widget)
            self._steps_layout.setContentsMargins(10, 5, 10, 5)
            self._steps_layout.setSpacing(6)
            self._steps_layout.addStretch()
            
            layout.addWidget(self._steps_widget)
            
            # 样式
            self.setStyleSheet("""
                ThinkingPanel {
                    background-color: #252526;
                    border: 1px solid #3e3e42;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
        
        def add_step(self, label: str, icon: str = "🔄") -> 'ThinkingPanel':
            """链式添加步骤"""
            step_widget = _StepWidget(len(self._steps) + 1, label, icon)
            step_widget.clicked.connect(lambda: self.step_clicked.emit(step_widget.step_num))
            self._steps_layout.insertWidget(len(self._steps), step_widget)
            self._steps.append(step_widget)
            return self
        
        def set_step_active(self, step_num: int, message: str = ""):
            """设置步骤为激活状态"""
            if 0 < step_num <= len(self._steps):
                self._steps[step_num - 1].set_active(message)
        
        def set_step_completed(self, step_num: int, message: str = ""):
            """设置步骤为完成状态"""
            if 0 < step_num <= len(self._steps):
                self._steps[step_num - 1].set_completed(message)
        
        def set_step_failed(self, step_num: int, error: str):
            """设置步骤为失败状态"""
            if 0 < step_num <= len(self._steps):
                self._steps[step_num - 1].set_failed(error)
        
        def clear_steps(self):
            """清空所有步骤"""
            for step in self._steps:
                step.setParent(None)
                step.deleteLater()
            self._steps.clear()
    else:
        def add_step(self, label: str, icon: str = "🔄"):
            print(f"{icon} {label}")
            return self
        
        def set_step_active(self, step_num: int, message: str = ""):
            print(f"  → {message}")
        
        def set_step_completed(self, step_num: int, message: str = ""):
            print(f"  ✓ {message}")
        
        def set_step_failed(self, step_num: int, error: str):
            print(f"  ✗ {error}")


class _StepWidget(QWidget if PYQT6_AVAILABLE else QObject):
    """步骤小部件（内部类）"""
    
    if PYQT6_AVAILABLE:
        clicked = pyqtSignal()
        
        STYLE_TEMPLATES = {
            'pending': """
                QWidget#step {
                    background-color: #2d2d2d;
                    border-left: 3px solid #3e3e42;
                    border-radius: 4px;
                    padding: 8px;
                }
            """,
            'active': """
                QWidget#step {
                    background-color: #1a3a5c;
                    border-left: 3px solid #007acc;
                    border-radius: 4px;
                    padding: 8px;
                }
            """,
            'completed': """
                QWidget#step {
                    background-color: #1a3a2c;
                    border-left: 3px solid #89d185;
                    border-radius: 4px;
                    padding: 8px;
                }
            """,
            'failed': """
                QWidget#step {
                    background-color: #3a1a1a;
                    border-left: 3px solid #f48771;
                    border-radius: 4px;
                    padding: 8px;
                }
            """
        }
        
        def __init__(self, step_num: int, label: str, icon: str = "🔄"):
            super().__init__()
            self.step_num = step_num
            self._label = label
            self._icon = icon
            self._message = ""
            self._status = "pending"
            self._setup_ui()
        
        def _setup_ui(self):
            """设置 UI"""
            self.setObjectName("step")
            self.setStyleSheet(self.STYLE_TEMPLATES['pending'])
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            
            layout = QVBoxLayout(self)
            layout.setContentsMargins(10, 6, 10, 6)
            layout.setSpacing(2)
            
            # 标题行
            title_layout = QHBoxLayout()
            
            # 步骤编号
            num_label = QLabel(f"{self.step_num}.")
            num_label.setStyleSheet("color: #808080; font-size: 12px;")
            
            # 图标
            icon_label = QLabel(self._icon)
            icon_label.setStyleSheet("font-size: 14px;")
            
            # 标签
            label_widget = QLabel(self._label)
            label_widget.setStyleSheet("color: #d4d4d4; font-size: 13px; font-weight: bold;")
            
            title_layout.addWidget(num_label)
            title_layout.addWidget(icon_label)
            title_layout.addWidget(label_widget)
            title_layout.addStretch()
            
            # 消息行（可选）
            self._message_label = QLabel()
            self._message_label.setStyleSheet("color: #808080; font-size: 11px; padding-left: 24px;")
            self._message_label.setWordWrap(True)
            self._message_label.hide()
            
            layout.addLayout(title_layout)
            layout.addWidget(self._message_label)
        
        def set_active(self, message: str = ""):
            """设置为激活状态"""
            self._status = "active"
            self._message = message
            self.setStyleSheet(self.STYLE_TEMPLATES['active'])
            if message:
                self._message_label.setText(f"⟳ {message}")
                self._message_label.show()
            else:
                self._message_label.hide()
        
        def set_completed(self, message: str = ""):
            """设置为完成状态"""
            self._status = "completed"
            self._message = message
            self.setStyleSheet(self.STYLE_TEMPLATES['completed'])
            if message:
                self._message_label.setText(f"✓ {message}")
                self._message_label.show()
            else:
                self._message_label.hide()
        
        def set_failed(self, error: str):
            """设置为失败状态"""
            self._status = "failed"
            self._message = error
            self.setStyleSheet(self.STYLE_TEMPLATES['failed'])
            self._message_label.setText(f"✗ {error}")
            self._message_label.show()
        
        def mousePressEvent(self, event):
            """鼠标点击"""
            if event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit()


# ============== 流式输出主组件 ==============

class StreamingOutputWidget(QWidget if PYQT6_AVAILABLE else QObject):
    """
    流式输出主组件
    
    集成流式文本、思考过程、代码高亮等功能
    """
    
    if PYQT6_AVAILABLE:
        # 信号
        stream_started = pyqtSignal()
        stream_finished = pyqtSignal()
        step_clicked = pyqtSignal(int)
        error_occurred = pyqtSignal(str)
        
        def __init__(self, parent=None):
            super().__init__(parent)
            
            # 创建流式引擎
            self._engine = StreamingEngine(self)
            self._engine.stream_started.connect(self.stream_started)
            self._engine.stream_finished.connect(self._on_stream_finished)
            self._engine.step_changed.connect(self._on_step_changed)
            self._engine.error_occurred.connect(self.error_occurred)
            
            self._setup_ui()
            self._connect_signals()
        
        def _setup_ui(self):
            """设置 UI"""
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(10)
            
            # 思考过程面板
            self._thinking_panel = ThinkingPanel()
            self._thinking_panel.step_clicked.connect(self.step_clicked)
            main_layout.addWidget(self._thinking_panel, 1)
            
            # 流式输出区域
            self._output_browser = StreamingTextBrowser()
            main_layout.addWidget(self._output_browser, 3)
            
            # 样式
            self.setStyleSheet(DEFAULT_STYLES)
        
        def _connect_signals(self):
            """连接信号"""
            self._engine.chunk_ready.connect(self._on_chunk_ready)
        
        def _on_chunk_ready(self, content: str, chunk_type: str):
            """处理新的数据块"""
            stype = StreamingType(chunk_type)
            self._output_browser.append_stream(content, stype)
        
        def _on_stream_finished(self):
            """流式输出完成"""
            self.stream_finished.emit()
        
        def _on_step_changed(self, step: int, status: str, message: str):
            """步骤状态变化"""
            if status == "active":
                self._thinking_panel.set_step_active(step, message)
            elif status == "completed":
                self._thinking_panel.set_step_completed(step, message)
            elif status == "failed":
                self._thinking_panel.set_step_failed(step, message)
        
        # ========== 公共 API ==========
        
        def start_stream(self):
            """开始流式输出"""
            self._thinking_panel.clear_steps()
            self._output_browser.clear_content()
            self._engine.start_stream()
        
        def end_stream(self):
            """结束流式输出"""
            self._engine.end_stream()
        
        def add_step(self, label: str, icon: str = "🔄") -> int:
            """添加思考步骤"""
            self._thinking_panel.add_step(label, icon)
            return self._engine.add_step(label, icon)
        
        def activate_step(self, step_num: int, message: str = ""):
            """激活步骤"""
            self._engine.activate_step(step_num, message)
        
        def complete_step(self, step_num: int, message: str = ""):
            """完成步骤"""
            self._engine.complete_step(step_num, message)
        
        def fail_step(self, step_num: int, error: str):
            """步骤失败"""
            self._engine.fail_step(step_num, error)
        
        def append_text(self, text: str, stream_type: StreamingType = StreamingType.TEXT):
            """追加文本"""
            self._engine.add_chunk(text, stream_type)
        
        def append_code(self, code: str, language: str = 'python'):
            """追加代码块"""
            self._output_browser.append_code_block(code, language)
        
        def stream_markdown(self, markdown: str):
            """流式渲染 Markdown"""
            self._output_browser.set_markdown_mode(True)
            self._engine.add_chunk(markdown, StreamingType.MARKDOWN)
        
        def set_typing_speed(self, chars_per_second: int):
            """设置打字速度"""
            self._output_browser.typing_speed = chars_per_second
        
        def clear(self):
            """清空所有内容"""
            self._thinking_panel.clear_steps()
            self._output_browser.clear_content()
        
        @property
        def engine(self) -> StreamingEngine:
            """获取流式引擎"""
            return self._engine
        
        @property
        def thinking_panel(self) -> ThinkingPanel:
            """获取思考面板"""
            return self._thinking_panel
        
        @property
        def output_browser(self) -> StreamingTextBrowser:
            """获取输出浏览器"""
            return self._output_browser
    else:
        def __getattr__(self, name):
            """无 PyQt6 时的空实现"""
            return lambda *args, **kwargs: self
        
        @property
        def engine(self):
            return None
        
        @property
        def thinking_panel(self):
            return self
        
        @property
        def output_browser(self):
            return self


# ============== 便捷函数 ==============

def create_streaming_widget(parent=None) -> StreamingOutputWidget:
    """创建流式输出组件"""
    return StreamingOutputWidget(parent)


def markdown_to_html(markdown: str) -> str:
    """简单的 Markdown 转 HTML"""
    html = markdown
    
    # 标题
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    
    # 粗体
    html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html)
    
    # 斜体
    html = re.sub(r'\*(.+?)\*', r'<i>\1</i>', html)
    
    # 代码
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
    
    # 链接
    html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', html)
    
    return html


# ============== 单元测试 ==============

if __name__ == "__main__" and PYQT6_AVAILABLE:
    import sys
    
    app = QApplication(sys.argv)
    
    # 创建流式输出组件
    widget = StreamingOutputWidget()
    widget.resize(800, 600)
    
    # 模拟流式输出
    widget.start_stream()
    
    # 添加步骤
    widget.add_step("分析需求", "🔍")
    widget.add_step("搜索知识库", "📚")
    widget.add_step("生成代码", "💻")
    widget.add_step("质量检查", "✓")
    
    # 模拟执行
    QTimer.singleShot(100, lambda: widget.activate_step(1, "正在理解用户需求..."))
    QTimer.singleShot(500, lambda: widget.complete_step(1, "需求分析完成"))
    QTimer.singleShot(600, lambda: widget.activate_step(2, "检索相关文档..."))
    QTimer.singleShot(1000, lambda: widget.complete_step(2, "找到 5 篇相关文档"))
    QTimer.singleShot(1100, lambda: widget.activate_step(3, "生成实现代码..."))
    QTimer.singleShot(1500, lambda: widget.append_text("def hello():\n    print('Hello, World!')\n", StreamingType.CODE))
    QTimer.singleShot(2000, lambda: widget.complete_step(3, "代码生成完成"))
    QTimer.singleShot(2100, lambda: widget.activate_step(4, "检查代码质量..."))
    QTimer.singleShot(2500, lambda: widget.complete_step(4, "质量检查通过"))
    QTimer.singleShot(2600, lambda: widget.end_stream())
    
    widget.show()
    sys.exit(app.exec())
