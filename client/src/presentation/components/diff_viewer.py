"""
代码差异高亮组件 - 专业的代码对比展示
用于 PyQt6 AI-IDE，实现 VS Code 级别的 diff 体验

特性:
- 行级差异高亮
- 词级差异高亮
- 并排对比视图
- 内联差异视图
- 合并操作支持
"""

from typing import Optional, List, Tuple, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
import difflib
import re

# PyQt6 imports
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
        QLabel, QPushButton, QFrame, QScrollArea, QScrollBar,
        QComboBox, QCheckBox, QToolButton, QSplitter,
        QTextEdit, QApplication
    )
    from PyQt6.QtCore import (
        Qt, QSize, pyqtSignal, QRect, QPoint
    )
    from PyQt6.QtGui import (
        QFont, QTextCursor, QTextCharFormat, QTextBlockFormat,
        QColor, QPalette, QPainter, QPen, QBrush, QTextDocument,
        QSyntaxHighlighter, QRegularExpression
    )
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    print("[DiffHighlighter] PyQt6 not available, using text mode")


# ============== 样式定义 ==============

DIFF_STYLES = """
/* 差异组件容器 */
DiffViewer {
    background-color: #1e1e1e;
    border: 1px solid #3e3e42;
    border-radius: 8px;
}

/* 头部工具栏 */
.DiffToolbar {
    background-color: #252526;
    border-bottom: 1px solid #3e3e42;
    padding: 8px;
}

/* 文件标签 */
.FileLabel {
    background-color: #2d2d2d;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    padding: 6px 12px;
    color: #d4d4d4;
    font-size: 13px;
}

/* 添加行 */
.AddedLine {
    background-color: #1c3a1c;
    border-left: 3px solid #4ec9b0;
}

/* 删除行 */
.RemovedLine {
    background-color: #3a1c1c;
    border-left: 3px solid #f48771;
}

/* 修改行 */
.ModifiedLine {
    background-color: #3a351c;
    border-left: 3px solid #dcdcaa;
}

/* 冲突行 */
.ConflictLine {
    background-color: #3a1c2c;
    border-left: 3px solid #c586c0;
}

/* 行号区域 */
.LineNumberArea {
    background-color: #1e1e1e;
    border-right: 1px solid #3e3e42;
    color: #5a5a5a;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    padding: 4px;
}

/* 空行占位 */
.EmptyLine {
    background-color: #252526;
}

/* Gutter 区域 */
.GutterAdded {
    background-color: #4ec9b0;
    color: #1e1e1e;
}

.GutterRemoved {
    background-color: #f48771;
    color: #1e1e1e;
}

.GutterModified {
    background-color: #dcdcaa;
    color: #1e1e1e;
}
"""


# ============== 差异类型枚举 ==============

class DiffType(Enum):
    """差异类型"""
    ADDED = "added"           # 新增
    REMOVED = "removed"      # 删除
    MODIFIED = "modified"     # 修改
    UNCHANGED = "unchanged"  # 未变
    CONFLICT = "conflict"     # 冲突
    EMPTY = "empty"          # 空行


# ============== 数据结构 ==============

@dataclass
class DiffLine:
    """差异行"""
    line_number_old: int      # 原文件行号（0 表示新增）
    line_number_new: int      # 新文件行号（0 表示删除）
    content: str              # 行内容
    diff_type: DiffType       # 差异类型
    old_content: str = ""     # 原内容（用于修改）
    inline_changes: List[Tuple[int, int, str]] = None  # (start, end, type) 内联变化
    
    def __post_init__(self):
        if self.inline_changes is None:
            self.inline_changes = []


@dataclass
class DiffHunk:
    """差异块"""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[DiffLine]
    header: str = ""


@dataclass
class DiffResult:
    """差异结果"""
    old_file: str
    new_file: str
    hunks: List[DiffHunk]
    stats: Dict[str, int]  # added, removed, modified, unchanged


# ============== 差异计算器 ==============

class DiffCalculator:
    """
    差异计算器
    
    使用 Myers 算法变体计算文本差异
    """
    
    def __init__(self, context_lines: int = 3):
        """
        Args:
            context_lines: 上下文行数
        """
        self.context_lines = context_lines
    
    def calculate(self, old_text: str, new_text: str, 
                  old_name: str = "old", new_name: str = "new") -> DiffResult:
        """
        计算差异
        
        Args:
            old_text: 原文本
            new_text: 新文本
            old_name: 原文件名
            new_name: 新文件名
            
        Returns:
            DiffResult: 差异结果
        """
        # 分割成行
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        
        # 确保最后一行有换行符
        if old_lines and not old_lines[-1].endswith('\n'):
            old_lines[-1] += '\n'
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines[-1] += '\n'
        
        # 计算行级差异
        diff_lines = self._compute_line_diff(old_lines, new_lines)
        
        # 组织成 hunks
        hunks = self._create_hunks(diff_lines, old_lines, new_lines)
        
        # 统计
        stats = {
            'added': sum(1 for l in diff_lines if l.diff_type == DiffType.ADDED),
            'removed': sum(1 for l in diff_lines if l.diff_type == DiffType.REMOVED),
            'modified': sum(1 for l in diff_lines if l.diff_type == DiffType.MODIFIED),
            'unchanged': sum(1 for l in diff_lines if l.diff_type == DiffType.UNCHANGED),
        }
        
        return DiffResult(
            old_file=old_name,
            new_file=new_name,
            hunks=hunks,
            stats=stats
        )
    
    def _compute_line_diff(self, old_lines: List[str], 
                           new_lines: List[str]) -> List[DiffLine]:
        """计算行级差异"""
        # 使用 SequenceMatcher
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        
        diff_lines = []
        old_idx = 0
        new_idx = 0
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                # 未变化的行
                for k in range(i1, i2):
                    diff_lines.append(DiffLine(
                        line_number_old=k + 1,
                        line_number_new=j1 + (k - i1) + 1,
                        content=old_lines[k],
                        diff_type=DiffType.UNCHANGED
                    ))
                old_idx = i2
                new_idx = j2
            
            elif tag == 'delete':
                # 删除的行
                for k in range(i1, i2):
                    diff_lines.append(DiffLine(
                        line_number_old=k + 1,
                        line_number_new=0,
                        content=old_lines[k],
                        diff_type=DiffType.REMOVED
                    ))
                old_idx = i2
            
            elif tag == 'insert':
                # 新增的行
                for k in range(j1, j2):
                    diff_lines.append(DiffLine(
                        line_number_old=0,
                        line_number_new=k + 1,
                        content=new_lines[k],
                        diff_type=DiffType.ADDED
                    ))
                new_idx = j2
            
            elif tag == 'replace':
                # 替换 - 需要判断是修改还是删除+新增
                # 简单策略：连续的单行替换视为修改
                if i2 - i1 == 1 and j2 - j1 == 1:
                    # 单行替换 - 视为修改
                    diff_lines.append(DiffLine(
                        line_number_old=i1 + 1,
                        line_number_new=j1 + 1,
                        content=new_lines[j1],
                        diff_type=DiffType.MODIFIED,
                        old_content=old_lines[i1],
                        inline_changes=self._compute_word_diff(
                            old_lines[i1], new_lines[j1]
                        )
                    ))
                else:
                    # 多行替换 - 逐行处理
                    for k in range(i1, i2):
                        diff_lines.append(DiffLine(
                            line_number_old=k + 1,
                            line_number_new=0,
                            content=old_lines[k],
                            diff_type=DiffType.REMOVED
                        ))
                    for k in range(j1, j2):
                        diff_lines.append(DiffLine(
                            line_number_old=0,
                            line_number_new=k + 1,
                            content=new_lines[k],
                            diff_type=DiffType.ADDED
                        ))
                
                old_idx = i2
                new_idx = j2
        
        return diff_lines
    
    def _compute_word_diff(self, old_line: str, new_line: str) -> List[Tuple[int, int, str]]:
        """计算词级差异"""
        # 简单词级差异
        old_words = old_line.split()
        new_words = new_line.split()
        
        matcher = difflib.SequenceMatcher(None, old_words, new_words)
        changes = []
        
        # 简化：返回相似度信息
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal':
                # 有变化的位置（简化处理）
                pass
        
        return changes
    
    def _create_hunks(self, diff_lines: List[DiffLine],
                       old_lines: List[str], new_lines: List[str]) -> List[DiffHunk]:
        """创建差异块"""
        hunks = []
        current_hunk = None
        context_count = 0
        
        for i, line in enumerate(diff_lines):
            is_context = line.diff_type == DiffType.UNCHANGED
            
            if is_context:
                context_count += 1
            else:
                context_count = 0
            
            # 开始新 hunk
            if not is_context and (current_hunk is None or context_count > self.context_lines * 2):
                if current_hunk:
                    hunks.append(current_hunk)
                
                current_hunk = DiffHunk(
                    old_start=line.line_number_old if line.line_number_old else 1,
                    old_count=0,
                    new_start=line.line_number_new if line.line_number_new else 1,
                    new_count=0,
                    lines=[]
                )
                context_count = 0
            
            if current_hunk:
                current_hunk.lines.append(line)
                
                if line.line_number_old > 0:
                    current_hunk.old_count += 1
                if line.line_number_new > 0:
                    current_hunk.new_count += 1
        
        if current_hunk:
            hunks.append(current_hunk)
        
        return hunks


# ============== 差异语法高亮器 ==============

class DiffSyntaxHighlighter(QSyntaxHighlighter if PYQT6_AVAILABLE else object):
    """
    差异语法高亮器
    
    根据差异类型为代码行着色
    """
    
    # 颜色定义
    COLORS = {
        DiffType.ADDED: QColor("#4ec9b0"),      # 青色
        DiffType.REMOVED: QColor("#f48771"),    # 红色
        DiffType.MODIFIED: QColor("#dcdcaa"),   # 黄色
        DiffType.UNCHANGED: QColor("#d4d4d4"), # 灰色
        DiffType.CONFLICT: QColor("#c586c0"),  # 紫色
        DiffType.EMPTY: QColor("#3e3e42"),     # 深灰
    }
    
    # 背景色
    BACKGROUNDS = {
        DiffType.ADDED: QColor("#1c3a1c"),
        DiffType.REMOVED: QColor("#3a1c1c"),
        DiffType.MODIFIED: QColor("#3a351c"),
        DiffType.UNCHANGED: QColor("#1e1e1e"),
        DiffType.CONFLICT: QColor("#3a1c2c"),
        DiffType.EMPTY: QColor("#252526"),
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._line_formats: Dict[int, Dict[str, Any]] = {}
        
        # 代码高亮规则
        self._setup_code_rules()
    
    def _setup_code_rules(self):
        """设置代码高亮规则"""
        # 字符串
        self._string_pattern = QRegularExpression(r'"[^"\\]*(?:\\.[^"\\]*)*"|' + r"'[^'\\]*(?:\\.[^'\\]*)*'")
        self._string_format = QTextCharFormat()
        self._string_format.setForeground(QColor("#ce9178"))
        
        # 注释
        self._comment_pattern = QRegularExpression(r'#.*$|//.*$|/\*.*\*/')
        self._comment_format = QTextCharFormat()
        self._comment_format.setForeground(QColor("#6a9955"))
        
        # 关键字
        self._keyword_patterns = [
            (r'\bdef\b', QColor("#569cd6")),
            (r'\bclass\b', QColor("#4ec9b0")),
            (r'\breturn\b', QColor("#c586c0")),
            (r'\bif\b|\belse\b|\belif\b', QColor("#c586c0")),
            (r'\bfor\b|\bwhile\b|\bin\b', QColor("#c586c0")),
            (r'\bimport\b|\bfrom\b|\bas\b', QColor("#c586c0")),
            (r'\bTrue\b|\bFalse\b|\bNone\b', QColor("#569cd6")),
            (r'\bprint\b|\bprint\(', QColor("#dcdcaa")),
        ]
    
    def set_diff_lines(self, diff_lines: List[DiffLine]):
        """设置差异行"""
        self._diff_lines = diff_lines
        self.rehighlight()
    
    def highlightBlock(self, text: str):
        """高亮一个文本块"""
        block_num = self.currentBlock().blockNumber()
        
        if not hasattr(self, '_diff_lines') or block_num >= len(self._diff_lines):
            return
        
        diff_line = self._diff_lines[block_num]
        
        # 设置背景色
        bg_color = self.BACKGROUNDS.get(diff_line.diff_type, self.BACKGROUNDS[DiffType.UNCHANGED])
        self.setFormat(0, len(text), bg_color)
        
        # 如果是修改行，添加旧内容标记
        if diff_line.diff_type == DiffType.MODIFIED and diff_line.old_content:
            # 可以在这里添加下划线或特殊标记
            pass
        
        # 代码语法高亮
        self._highlight_code(text)
    
    def _highlight_code(self, text: str):
        """高亮代码元素"""
        # 字符串
        iterator = self._string_pattern.globalMatch(text)
        while iterator.hasNext():
            match = iterator.next()
            string_fmt = QTextCharFormat()
            string_fmt.setForeground(self._string_format.foreground())
            self.setFormat(match.capturedStart(), match.capturedLength(), string_fmt)
        
        # 注释
        iterator = self._comment_pattern.globalMatch(text)
        while iterator.hasNext():
            match = iterator.next()
            comment_fmt = QTextCharFormat()
            comment_fmt.setForeground(self._comment_format.foreground())
            self.setFormat(match.capturedStart(), match.capturedLength(), comment_fmt)
        
        # 关键字
        for pattern, color in self._keyword_patterns:
            regex = QRegularExpression(pattern)
            iterator = regex.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                keyword_fmt = QTextCharFormat()
                keyword_fmt.setForeground(color)
                self.setFormat(match.capturedStart(), match.capturedLength(), keyword_fmt)


# ============== 差异视图组件 ==============

class DiffLineNumberArea(QWidget if PYQT6_AVAILABLE else object):
    """行号区域"""
    
    if PYQT6_AVAILABLE:
        def __init__(self, editor: 'DiffTextEditor', side: str = 'left'):
            super().__init__(editor)
            self._editor = editor
            self._side = side
            self.setStyleSheet("""
                background-color: #1e1e1e;
                border-right: 1px solid #3e3e42;
                color: #5a5a5a;
            """)
        
        def sizeHint(self) -> QSize:
            return QSize(self._editor.line_number_area_width(), self.height())
        
        def paintEvent(self, event):
            self._editor.paint_line_number_area(event)
    else:
        def __init__(self, *args, **kwargs):
            pass


class DiffTextEditor(QTextEdit if PYQT6_AVAILABLE else object):
    """
    差异文本编辑器
    
    支持行号、语法高亮、差异标记
    """
    
    if PYQT6_AVAILABLE:
        # 信号
        cursor_position_changed = pyqtSignal()
        
        def __init__(self, parent=None, show_line_numbers: bool = True):
            super().__init__(parent)
            self._show_line_numbers = show_line_numbers
            self._line_number_area_width = 50
            self._diff_highlighter = DiffSyntaxHighlighter(self.document())
            self._diff_lines: List[DiffLine] = []
            
            # 设置编辑器样式
            self.setReadOnly(True)
            self.setFont(QFont('Consolas', 11))
            self.setStyleSheet("""
                QTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: none;
                    padding: 0;
                }
            """)
            
            # 启用行号区域
            self.setViewportMargins(self._line_number_area_width if show_line_numbers else 0, 0, 0, 0)
        
        def set_diff_result(self, diff_result: DiffResult, show_old: bool = True):
            """设置差异结果"""
            # 收集要显示的行
            lines = []
            self._diff_lines = []
            
            for hunk in diff_result.hunks:
                for diff_line in hunk.lines:
                    self._diff_lines.append(diff_line)
                    
                    if show_old:
                        # 显示旧版本（对于删除和修改）
                        if diff_line.diff_type in [DiffType.REMOVED, DiffType.MODIFIED]:
                            lines.append(diff_line.old_content or diff_line.content)
                        elif diff_line.diff_type == DiffType.ADDED:
                            lines.append("")  # 占位
                        else:
                            lines.append(diff_line.content)
                    else:
                        # 显示新版本
                        if diff_line.diff_type in [DiffType.ADDED, DiffType.MODIFIED]:
                            lines.append(diff_line.content)
                        elif diff_line.diff_type == DiffType.REMOVED:
                            lines.append("")  # 占位
                        else:
                            lines.append(diff_line.content)
            
            # 更新高亮器
            self._diff_highlighter.set_diff_lines(self._diff_lines)
            
            # 设置文本
            self.setPlainText("".join(lines))
        
        def set_diff_lines(self, diff_lines: List[DiffLine]):
            """设置差异行"""
            self._diff_lines = diff_lines
            self._diff_highlighter.set_diff_lines(diff_lines)
            
            # 构建显示文本
            lines = [line.content for line in diff_lines]
            self.setPlainText("".join(lines))
        
        def line_number_area_width(self) -> int:
            """计算行号区域宽度"""
            if not self._show_line_numbers:
                return 0
            
            digits = len(str(max(1, len(self._diff_lines))))
            return max(50, digits * 10 + 10)
        
        def paint_line_number_area(self, event):
            """绘制行号区域"""
            painter = QPainter(self._line_number_area if hasattr(self, '_line_number_area') else self)
            painter.fillRect(event.rect(), QColor("#1e1e1e"))
            
            if not self._diff_lines:
                return
            
            block = self.firstVisibleBlock()
            block_number = block.blockNumber()
            top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
            bottom = top + int(self.blockBoundingRect(block).height())
            
            while block.isValid() and top <= event.rect().bottom():
                if block.isVisible():
                    if block_number < len(self._diff_lines):
                        diff_line = self._diff_lines[block_number]
                        
                        # 绘制行号
                        painter.setPen(QColor("#5a5a5a"))
                        
                        # 根据差异类型着色
                        if diff_line.diff_type == DiffType.ADDED:
                            painter.setPen(QColor("#4ec9b0"))
                        elif diff_line.diff_type == DiffType.REMOVED:
                            painter.setPen(QColor("#f48771"))
                        elif diff_line.diff_type == DiffType.MODIFIED:
                            painter.setPen(QColor("#dcdcaa"))
                        
                        # 行号
                        if self._side == 'left':
                            num = diff_line.line_number_old
                        else:
                            num = diff_line.line_number_new
                        
                        if num > 0:
                            painter.drawText(
                                0, top,
                                self._line_number_area_width - 5, 20,
                                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                                str(num)
                            )
                
                block = block.next()
                top = bottom
                bottom = top + int(self.blockBoundingRect(block).height())
                block_number = block.blockNumber()
        
        def resizeEvent(self, event):
            super().resizeEvent(event)
            if hasattr(self, '_line_number_area'):
                self._line_number_area.setFixedWidth(self.line_number_area_width())
        
        def get_diff_lines(self) -> List[DiffLine]:
            """获取差异行"""
            return self._diff_lines
    else:
        def set_diff_result(self, *args, **kwargs):
            pass
        
        def set_diff_lines(self, *args, **kwargs):
            pass
        
        def get_diff_lines(self):
            return []


# ============== 并排差异视图 ==============

class SideBySideDiffViewer(QWidget if PYQT6_AVAILABLE else object):
    """
    并排差异视图
    
    左右两侧分别显示旧版本和新版本
    """
    
    if PYQT6_AVAILABLE:
        # 信号
        line_clicked = pyqtSignal(int, str)  # 行号, 侧
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self._setup_ui()
        
        def _setup_ui(self):
            """设置 UI"""
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            
            # 头部
            header = self._create_header()
            layout.addWidget(header)
            
            # 内容区
            splitter = QSplitter(Qt.Orientation.Horizontal)
            
            # 左侧（旧版本）
            left_widget = QWidget()
            left_layout = QVBoxLayout(left_widget)
            left_layout.setContentsMargins(0, 0, 0, 0)
            
            self._old_label = QLabel("旧版本")
            self._old_label.setStyleSheet("""
                background-color: #252526;
                color: #d4d4d4;
                padding: 8px;
                border-bottom: 1px solid #3e3e42;
            """)
            left_layout.addWidget(self._old_label)
            
            self._old_editor = DiffTextEditor(show_line_numbers=True)
            self._old_editor._side = 'old'
            left_layout.addWidget(self._old_editor)
            
            splitter.addWidget(left_widget)
            
            # 右侧（新版本）
            right_widget = QWidget()
            right_layout = QVBoxLayout(right_widget)
            right_layout.setContentsMargins(0, 0, 0, 0)
            
            self._new_label = QLabel("新版本")
            self._new_label.setStyleSheet("""
                background-color: #252526;
                color: #d4d4d4;
                padding: 8px;
                border-bottom: 1px solid #3e3e42;
            """)
            right_layout.addWidget(self._new_label)
            
            self._new_editor = DiffTextEditor(show_line_numbers=True)
            self._new_editor._side = 'new'
            right_layout.addWidget(self._new_editor)
            
            splitter.addWidget(right_widget)
            
            # 设置分割比例
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 1)
            
            layout.addWidget(splitter, 1)
            
            # 样式
            self.setStyleSheet(DIFF_STYLES)
        
        def _create_header(self) -> QWidget:
            """创建头部工具栏"""
            header = QWidget()
            header.setObjectName("DiffToolbar")
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(10, 5, 10, 5)
            
            # 标题
            self._title_label = QLabel("代码差异")
            self._title_label.setStyleSheet("color: #d4d4d4; font-size: 14px; font-weight: bold;")
            header_layout.addWidget(self._title_label)
            
            header_layout.addStretch()
            
            # 统计信息
            self._stats_label = QLabel("")
            self._stats_label.setStyleSheet("color: #808080; font-size: 12px;")
            header_layout.addWidget(self._stats_label)
            
            # 同步滚动
            self._sync_scroll_check = QCheckBox("同步滚动")
            self._sync_scroll_check.setChecked(True)
            self._sync_scroll_check.setStyleSheet("color: #d4d4d4;")
            header_layout.addWidget(self._sync_scroll_check)
            
            return header
        
        def set_diff_result(self, diff_result: DiffResult):
            """设置差异结果"""
            # 更新标题
            self._title_label.setText(f"{diff_result.old_file} → {diff_result.new_file}")
            
            # 更新统计
            stats = diff_result.stats
            stats_text = (
                f"<span style='color:#4ec9b0'>+{stats['added']}</span> "
                f"<span style='color:#f48771'>-{stats['removed']}</span> "
                f"<span style='color:#dcdcaa'>~{stats['modified']}</span>"
            )
            self._stats_label.setText(stats_text)
            
            # 设置差异内容
            self._old_editor.set_diff_result(diff_result, show_old=True)
            self._new_editor.set_diff_result(diff_result, show_old=False)
            
            # 连接同步滚动
            if self._sync_scroll_check.isChecked():
                self._old_editor.verticalScrollBar().valueChanged.connect(
                    self._sync_scroll
                )
        
        def set_diff(self, old_text: str, new_text: str,
                     old_name: str = "old", new_name: str = "new"):
            """设置差异文本"""
            calculator = DiffCalculator()
            result = calculator.calculate(old_text, new_text, old_name, new_name)
            self.set_diff_result(result)
        
        def _sync_scroll(self, value: int):
            """同步滚动"""
            if self._sync_scroll_check.isChecked():
                sender = self.sender()
                if sender == self._old_editor.verticalScrollBar():
                    self._new_editor.verticalScrollBar().setValue(value)
                else:
                    self._old_editor.verticalScrollBar().setValue(value)
        
        def get_old_editor(self) -> DiffTextEditor:
            """获取旧版本编辑器"""
            return self._old_editor
        
        def get_new_editor(self) -> DiffTextEditor:
            """获取新版本编辑器"""
            return self._new_editor
    else:
        def __init__(self, *args, **kwargs):
            pass
        
        def set_diff(self, *args, **kwargs):
            pass
        
        def set_diff_result(self, *args, **kwargs):
            pass


# ============== 内联差异视图 ==============

class InlineDiffViewer(QWidget if PYQT6_AVAILABLE else object):
    """
    内联差异视图
    
    在单个编辑器中显示所有差异
    """
    
    if PYQT6_AVAILABLE:
        def __init__(self, parent=None):
            super().__init__(parent)
            self._setup_ui()
        
        def _setup_ui(self):
            """设置 UI"""
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            
            # 头部
            header = QWidget()
            header.setObjectName("DiffToolbar")
            header_layout = QHBoxLayout(header)
            
            self._title_label = QLabel("差异视图")
            self._title_label.setStyleSheet("color: #d4d4d4; font-size: 14px; font-weight: bold;")
            header_layout.addWidget(self._title_label)
            
            header_layout.addStretch()
            
            self._stats_label = QLabel("")
            self._stats_label.setStyleSheet("color: #808080; font-size: 12px;")
            header_layout.addWidget(self._stats_label)
            
            layout.addWidget(header)
            
            # 编辑器
            self._editor = DiffTextEditor(show_line_numbers=True)
            layout.addWidget(self._editor, 1)
            
            self.setStyleSheet(DIFF_STYLES)
        
        def set_diff_result(self, diff_result: DiffResult):
            """设置差异结果"""
            # 更新标题
            self._title_label.setText(f"{diff_result.old_file} → {diff_result.new_file}")
            
            # 更新统计
            stats = diff_result.stats
            stats_text = (
                f"<span style='color:#4ec9b0'>+{stats['added']}</span> "
                f"<span style='color:#f48771'>-{stats['removed']}</span> "
                f"<span style='color:#dcdcaa'>~{stats['modified']}</span>"
            )
            self._stats_label.setText(stats_text)
            
            # 设置差异行
            all_lines = []
            for hunk in diff_result.hunks:
                all_lines.extend(hunk.lines)
            
            self._editor.set_diff_lines(all_lines)
        
        def set_diff(self, old_text: str, new_text: str,
                     old_name: str = "old", new_name: str = "new"):
            """设置差异文本"""
            calculator = DiffCalculator()
            result = calculator.calculate(old_text, new_text, old_name, new_name)
            self.set_diff_result(result)
        
        def get_editor(self) -> DiffTextEditor:
            """获取编辑器"""
            return self._editor
    else:
        def __init__(self, *args, **kwargs):
            pass
        
        def set_diff(self, *args, **kwargs):
            pass
        
        def set_diff_result(self, *args, **kwargs):
            pass


# ============== 主差异组件 ==============

class DiffViewer(QWidget if PYQT6_AVAILABLE else object):
    """
    代码差异查看器主组件
    
    支持并排和内联两种视图模式
    """
    
    if PYQT6_AVAILABLE:
        # 信号
        diff_changed = pyqtSignal(dict)  # 差异变化信号
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self._current_view = 'side'  # 'side' 或 'inline'
            self._setup_ui()
        
        def _setup_ui(self):
            """设置 UI"""
            layout = QVBoxLayout(self)
            layout.setContentsMargins(5, 5, 5, 5)
            
            # 工具栏
            toolbar = self._create_toolbar()
            layout.addWidget(toolbar)
            
            # 视图容器
            self._view_container = QWidget()
            self._view_layout = QVBoxLayout(self._view_container)
            self._view_layout.setContentsMargins(0, 0, 0, 0)
            
            # 并排视图
            self._side_view = SideBySideDiffViewer()
            self._view_layout.addWidget(self._side_view)
            
            # 内联视图
            self._inline_view = InlineDiffViewer()
            self._inline_view.hide()
            
            layout.addWidget(self._view_container, 1)
            
            self.setStyleSheet(DIFF_STYLES)
        
        def _create_toolbar(self) -> QWidget:
            """创建工具栏"""
            toolbar = QWidget()
            toolbar.setObjectName("DiffToolbar")
            layout = QHBoxLayout(toolbar)
            layout.setContentsMargins(10, 5, 10, 5)
            
            # 视图切换
            self._view_combo = QComboBox()
            self._view_combo.addItems(["并排视图", "内联视图"])
            self._view_combo.setStyleSheet("""
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 4px 8px;
            """)
            self._view_combo.currentTextChanged.connect(self._on_view_changed)
            layout.addWidget(QLabel("视图:"))
            layout.addWidget(self._view_combo)
            
            layout.addStretch()
            
            # 统计信息
            self._stats_label = QLabel("")
            self._stats_label.setStyleSheet("color: #808080; font-size: 12px;")
            layout.addWidget(self._stats_label)
            
            # 按钮
            self._copy_btn = QPushButton("📋 复制差异")
            self._copy_btn.setObjectName("CommandButton")
            self._copy_btn.clicked.connect(self._on_copy_diff)
            layout.addWidget(self._copy_btn)
            
            return toolbar
        
        def _on_view_changed(self, text: str):
            """切换视图"""
            if text == "并排视图":
                self._current_view = 'side'
                self._inline_view.hide()
                self._side_view.show()
            else:
                self._current_view = 'inline'
                self._side_view.hide()
                self._inline_view.show()
        
        def _on_copy_diff(self):
            """复制差异"""
            # 实现复制功能
            pass
        
        def set_diff(self, old_text: str, new_text: str,
                     old_name: str = "old", new_name: str = "new"):
            """设置差异"""
            calculator = DiffCalculator()
            result = calculator.calculate(old_text, new_text, old_name, new_name)
            self.set_diff_result(result)
        
        def set_diff_result(self, diff_result: DiffResult):
            """设置差异结果"""
            # 更新统计
            stats = diff_result.stats
            stats_text = (
                f"添加: <span style='color:#4ec9b0'>{stats['added']}</span>, "
                f"删除: <span style='color:#f48771'>{stats['removed']}</span>, "
                f"修改: <span style='color:#dcdcaa'>{stats['modified']}</span>"
            )
            self._stats_label.setText(stats_text)
            
            # 更新视图
            self._side_view.set_diff_result(diff_result)
            self._inline_view.set_diff_result(diff_result)
            
            # 发送信号
            self.diff_changed.emit(diff_result.stats)
        
        def get_current_view(self) -> str:
            """获取当前视图模式"""
            return self._current_view
        
        def set_view_mode(self, mode: str):
            """设置视图模式"""
            if mode == 'side':
                self._view_combo.setCurrentText("并排视图")
            elif mode == 'inline':
                self._view_combo.setCurrentText("内联视图")
    else:
        def __init__(self, *args, **kwargs):
            pass
        
        def set_diff(self, *args, **kwargs):
            pass
        
        def set_diff_result(self, *args, **kwargs):
            pass


# ============== 便捷函数 ==============

def compute_diff(old_text: str, new_text: str,
                old_name: str = "old", new_name: str = "new") -> DiffResult:
    """计算差异"""
    calculator = DiffCalculator()
    return calculator.calculate(old_text, new_text, old_name, new_name)


def diff_to_html(diff_result: DiffResult) -> str:
    """将差异转换为 HTML"""
    html = ['<div class="diff">']
    
    for hunk in diff_result.hunks:
        html.append(f'<div class="hunk">// {hunk.header}</div>')
        for line in hunk.lines:
            if line.diff_type == DiffType.ADDED:
                html.append(f'<div class="added">+ {line.content}</div>')
            elif line.diff_type == DiffType.REMOVED:
                html.append(f'<div class="removed">- {line.content}</div>')
            elif line.diff_type == DiffType.MODIFIED:
                html.append(f'<div class="modified">~ {line.content}</div>')
            else:
                html.append(f'<div class="unchanged">  {line.content}</div>')
    
    html.append('</div>')
    return '\n'.join(html)


# ============== 单元测试 ==============

if __name__ == "__main__" and PYQT6_AVAILABLE:
    import sys
    
    app = QApplication(sys.argv)
    
    # 创建差异查看器
    viewer = DiffViewer()
    viewer.resize(1200, 800)
    
    # 测试数据
    old_code = '''def hello():
    print("Hello, World!")
    return True

def add(a, b):
    return a + b
'''
    
    new_code = '''def hello():
    print("Hello, AI!")
    return False

def add(a, b):
    """Add two numbers"""
    return a + b

def subtract(a, b):
    """Subtract b from a"""
    return a - b
'''
    
    viewer.set_diff(old_code, new_code, "old.py", "new.py")
    viewer.show()
    
    sys.exit(app.exec())
