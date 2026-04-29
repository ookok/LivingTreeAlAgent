"""
SmartEditor - 统一AI增强编辑器核心
================================

核心理念："一个编辑器，解决所有输入问题"

支持的编辑模式:
- plain: 纯文本
- markdown: Markdown编辑
- json: JSON配置
- yaml: YAML配置
- python: Python代码
- sql: SQL查询
- html: HTML
- chat: AI对话

特性:
- 上下文感知模式切换
- 多语法高亮支持
- AI智能补全
- 实时语法检查
"""

import re
import uuid
import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable, Awaitable, List, Dict, Any
from threading import Lock


class EditorMode(Enum):
    """编辑器模式"""
    PLAIN = "plain"           # 纯文本
    MARKDOWN = "markdown"      # Markdown
    JSON = "json"              # JSON
    YAML = "yaml"              # YAML
    PYTHON = "python"          # Python
    SQL = "sql"                # SQL
    HTML = "html"              # HTML
    CHAT = "chat"              # AI对话


@dataclass
class EditorConfig:
    """编辑器配置"""
    mode: EditorMode = EditorMode.PLAIN
    auto_detect_mode: bool = True           # 自动检测模式
    enable_ai_completion: bool = True       # AI补全
    enable_syntax_highlight: bool = True    # 语法高亮
    enable_line_numbers: bool = True        # 行号
    enable_word_wrap: bool = True           # 自动换行
    tab_size: int = 4                       # Tab大小
    show_whitespace: bool = False           # 显示空格
    auto_save: bool = True                  # 自动保存
    auto_save_interval: int = 30000         # 自动保存间隔(ms)
    max_undo_steps: int = 1000              # 最大撤销步数


@dataclass
class TextRange:
    """文本范围"""
    start_line: int
    start_col: int
    end_line: int
    end_col: int

    def to_slice(self, text: str) -> str:
        """获取范围内的文本"""
        lines = text.split('\n')
        if self.start_line == self.end_line:
            return lines[self.start_line][self.start_col:self.end_col]
        result = lines[self.start_line][self.start_col:]
        for i in range(self.start_line + 1, self.end_line):
            result += '\n' + lines[i]
        result += '\n' + lines[self.end_line][:self.end_col]
        return result


@dataclass
class EditOperation:
    """编辑操作"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    op_type: str = "insert"  # insert, delete, replace
    position: int = 0
    text: str = ""
    timestamp: float = 0
    undone: bool = False


class SyntaxHighlighter:
    """语法高亮规则"""

    # 各模式的语法规则
    RULES: Dict[EditorMode, List[tuple]] = {
        EditorMode.PLAIN: [],

        EditorMode.MARKDOWN: [
            (r'^#+\s.*', 'heading'),
            (r'\*\*.*?\*\*', 'bold'),
            (r'\*.*?\*', 'italic'),
            (r'\[.*?\]\(.*?\)', 'link'),
            (r'`.*?`', 'code'),
            (r'```[\s\S]*?```', 'code_block'),
            (r'^\s*[-*+]\s', 'list'),
            (r'^\s*\d+\.\s', 'list'),
        ],

        EditorMode.JSON: [
            (r'"[^"]*"\s*:', 'key'),
            (r':\s*"[^"]*"', 'string'),
            (r':\s*\d+\.?\d*', 'number'),
            (r':\s*(true|false|null)', 'literal'),
        ],

        EditorMode.YAML: [
            (r'^[\w-]+:', 'key'),
            (r':\s*\|', 'block'),
            (r':\s*>', 'block'),
            (r'^\s*-\s', 'list'),
            (r'#.*$', 'comment'),
        ],

        EditorMode.PYTHON: [
            (r'#[^\n]*', 'comment'),
            (r'"""[\s\S]*?"""', 'string'),
            (r"'''[\s\S]*?'''", 'string'),
            (r'"[^"]*"', 'string'),
            (r"'[^']*'", 'string'),
            (r'\b(def|class|if|elif|else|for|while|try|except|finally|with|as|import|from|return|yield|break|continue|pass|raise|assert|lambda|and|or|not|in|is|True|False|None|self|async|await)\b', 'keyword'),
            (r'\b(int|str|float|bool|list|dict|set|tuple|bytes|type|object)\b', 'type'),
            (r'\b\d+\.?\d*\b', 'number'),
        ],

        EditorMode.SQL: [
            (r'--.*$', 'comment'),
            (r'/\*[\s\S]*?\*/', 'comment'),
            (r"'[^']*'", 'string'),
            (r'\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AND|OR|NOT|IN|IS|NULL|AS|ORDER|BY|GROUP|HAVING|LIMIT|OFFSET|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|INDEX|DROP|ALTER|ADD|COLUMN|PRIMARY|KEY|FOREIGN|REFERENCES|UNIQUE|DEFAULT|CHECK|CONSTRAINT)\b', 'keyword'),
            (r'\b(int|varchar|text|datetime|timestamp|boolean|decimal|float|double|bigint|smallint)\b', 'type'),
            (r'\b\d+\.?\d*\b', 'number'),
        ],

        EditorMode.HTML: [
            (r'<!--[\s\S]*?-->', 'comment'),
            (r'<[^/][^>]*>', 'tag'),
            (r'</[^>]+>', 'tag'),
            (r'"[^"]*"', 'string'),
            (r"'[^']*'", 'string'),
        ],

        EditorMode.CHAT: [
            (r'^用户:', 'user'),
            (r'^AI:', 'ai'),
            (r'\[.*?\]', 'bracket'),
        ],
    }

    # 语法高亮颜色主题
    COLOR_THEME = {
        'dark': {
            'heading': '#569CD6',
            'bold': '#FFFFFF',
            'italic': '#808080',
            'link': '#4EC9B0',
            'code': '#CE9178',
            'code_block': '#CE9178',
            'list': '#DCDCAA',
            'key': '#9CDCFE',
            'string': '#CE9178',
            'number': '#B5CEA8',
            'literal': '#569CD6',
            'comment': '#6A9955',
            'keyword': '#569CD6',
            'type': '#4EC9B0',
            'tag': '#569CD6',
            'user': '#4EC9B0',
            'ai': '#DCDCAA',
            'bracket': '#C586C0',
        },
        'light': {
            'heading': '#0000FF',
            'bold': '#000000',
            'italic': '#795E26',
            'link': '#0066CC',
            'code': '#A31515',
            'code_block': '#A31515',
            'list': '#795E26',
            'key': '#0010A0',
            'string': '#A31515',
            'number': '#098658',
            'literal': '#0000FF',
            'comment': '#008000',
            'keyword': '#0000FF',
            'type': '#267F99',
            'tag': '#800000',
            'user': '#267F99',
            'ai': '#795E26',
            'bracket': '#AF00DB',
        }
    }

    @classmethod
    def get_color(cls, mode: EditorMode, token_type: str, theme: str = 'dark') -> Optional[str]:
        """获取token类型的颜色"""
        return cls.COLOR_THEME.get(theme, {}).get(token_type)


class UndoManager:
    """撤销管理器"""

    def __init__(self, max_steps: int = 1000):
        self.max_steps = max_steps
        self.undo_stack: List[EditOperation] = []
        self.redo_stack: List[EditOperation] = []
        self.lock = Lock()

    def add_operation(self, op: EditOperation):
        """添加操作到撤销栈"""
        with self.lock:
            self.undo_stack.append(op)
            self.redo_stack.clear()  # 新操作清除重做栈
            if len(self.undo_stack) > self.max_steps:
                self.undo_stack.pop(0)

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def undo(self) -> Optional[EditOperation]:
        """撤销"""
        with self.lock:
            if not self.undo_stack:
                return None
            op = self.undo_stack.pop()
            op.undone = True
            self.redo_stack.append(op)
            return op

    def redo(self) -> Optional[EditOperation]:
        """重做"""
        with self.lock:
            if not self.redo_stack:
                return None
            op = self.redo_stack.pop()
            op.undone = False
            self.undo_stack.append(op)
            return op


class SmartEditor:
    """
    统一AI增强编辑器核心类

    特性:
    - 多模式支持 (plain/markdown/json/yaml/python/sql/html/chat)
    - 上下文感知模式自动切换
    - AI智能补全
    - 实时语法高亮
    - 撤销/重做
    - 自动保存
    """

    # 模式检测启发式规则
    MODE_HINTS = {
        'json': [r'^\s*\{', r'^\s*\[', r'"[^"]+"\s*:\s*'],
        'yaml': [r'^\w+:\s*$', r'^\s*-\s+\w+', r'^\s*\|\s*$', r'^\s*>\s*$'],
        'markdown': [r'^#+\s', r'^\*\*', r'^\[\w+\]\(', r'^```', r'^\s*[-*+]\s'],
        'python': [r'\bdef\s+\w+', r'\bclass\s+\w+', r'\bimport\s+\w+', r'\bfrom\s+\w+\s+import'],
        'sql': [r'\bSELECT\b', r'\bFROM\b', r'\bWHERE\b', r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b'],
        'html': [r'<\w+>', r'</\w+>', r'<!DOCTYPE', r'<html'],
    }

    def __init__(self, config: Optional[EditorConfig] = None):
        self.config = config or EditorConfig()
        self.mode = self.config.mode

        # 文本内容
        self._content: str = ""
        self._cursor_pos: int = 0

        # 撤销/重做
        self._undo_manager = UndoManager(self.config.max_undo_steps)

        # 事件回调
        self._on_content_change: Optional[Callable] = None
        self._on_mode_change: Optional[Callable] = None
        self._on_cursor_change: Optional[Callable] = None

        # 锁
        self._lock = Lock()

        # AI操作处理器
        self._ai_operator = None

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str):
        with self._lock:
            old_content = self._content
            self._content = value
            if old_content != value and self._on_content_change:
                self._on_content_change(value, old_content)

            # 自动检测模式
            if self.config.auto_detect_mode:
                new_mode = self.detect_mode(value)
                if new_mode != self.mode:
                    self.mode = new_mode
                    if self._on_mode_change:
                        self._on_mode_change(new_mode)

    @property
    def cursor_pos(self) -> int:
        return self._cursor_pos

    @cursor_pos.setter
    def cursor_pos(self, value: int):
        with self._lock:
            self._cursor_pos = value
            if self._on_cursor_change:
                self._on_cursor_change(value)

    def detect_mode(self, text: str) -> EditorMode:
        """
        根据内容自动检测编辑模式

        检测优先级:
        1. 明确语法特征 (如 { 开头为 JSON)
        2. 文件结构模式 (如 def/class 为 Python)
        3. 默认为纯文本
        """
        if not text.strip():
            return self.config.mode  # 保持默认模式

        # 精确匹配
        text_stripped = text.strip()

        if text_stripped.startswith('{') or text_stripped.startswith('['):
            # 可能是JSON
            try:
                import json
                json.loads(text)
                return EditorMode.JSON
            except:
                pass

        # 模式匹配
        for mode, patterns in self.MODE_HINTS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.MULTILINE):
                    return EditorMode(mode)

        return EditorMode.PLAIN

    def set_mode(self, mode: EditorMode | str):
        """设置编辑模式"""
        if isinstance(mode, str):
            mode = EditorMode(mode)
        if mode != self.mode:
            self.mode = mode
            if self._on_mode_change:
                self._on_mode_change(mode)

    def get_syntax_highlights(self, theme: str = 'dark') -> List[Dict[str, Any]]:
        """
        获取当前内容的语法高亮信息

        返回格式:
        [
            {'start': 0, 'end': 5, 'color': '#569CD6', 'type': 'keyword'},
            ...
        ]
        """
        highlights = []
        rules = SyntaxHighlighter.RULES.get(self.mode, [])

        for pattern, token_type in rules:
            for match in re.finditer(pattern, self._content, re.MULTILINE):
                color = SyntaxHighlighter.get_color(self.mode, token_type, theme)
                if color:
                    highlights.append({
                        'start': match.start(),
                        'end': match.end(),
                        'color': color,
                        'type': token_type,
                        'text': match.group()
                    })

        return highlights

    def insert_text(self, text: str, pos: Optional[int] = None) -> EditOperation:
        """插入文本"""
        if pos is None:
            pos = self._cursor_pos

        op = EditOperation(
            op_type='insert',
            position=pos,
            text=text,
            timestamp=asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
        )

        with self._lock:
            new_content = self._content[:pos] + text + self._content[pos:]
            self.content = new_content
            self._cursor_pos = pos + len(text)

        self._undo_manager.add_operation(op)
        return op

    def delete_text(self, length: int, pos: Optional[int] = None) -> EditOperation:
        """删除文本"""
        if pos is None:
            pos = self._cursor_pos

        op = EditOperation(
            op_type='delete',
            position=pos,
            text=self._content[pos:pos + length],
            timestamp=asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
        )

        with self._lock:
            new_content = self._content[:pos] + self._content[pos + length:]
            self.content = new_content
            self._cursor_pos = pos

        self._undo_manager.add_operation(op)
        return op

    def replace_text(self, text: str, range_start: int, range_end: int) -> EditOperation:
        """替换文本"""
        op = EditOperation(
            op_type='replace',
            position=range_start,
            text=text,
            timestamp=asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
        )

        with self._lock:
            new_content = self._content[:range_start] + text + self._content[range_end:]
            self.content = new_content
            self._cursor_pos = range_start + len(text)

        self._undo_manager.add_operation(op)
        return op

    def undo(self) -> bool:
        """撤销"""
        op = self._undo_manager.undo()
        if not op:
            return False

        if op.op_type == 'insert':
            with self._lock:
                new_content = self._content[:op.position] + self._content[op.position + len(op.text):]
                self.content = new_content
                self._cursor_pos = op.position
        elif op.op_type == 'delete':
            with self._lock:
                new_content = self._content[:op.position] + op.text + self._content[op.position:]
                self.content = new_content
                self._cursor_pos = op.position + len(op.text)
        elif op.op_type == 'replace':
            # 复杂的替换操作需要更多上下文
            pass

        return True

    def redo(self) -> bool:
        """重做"""
        op = self._undo_manager.redo()
        if not op:
            return False

        if op.op_type == 'insert':
            with self._lock:
                new_content = self._content[:op.position] + op.text + self._content[op.position:]
                self.content = new_content
                self._cursor_pos = op.position + len(op.text)
        elif op.op_type == 'delete':
            with self._lock:
                new_content = self._content[:op.position] + self._content[op.position + len(op.text):]
                self.content = new_content
                self._cursor_pos = op.position

        return True

    def get_word_at_cursor(self) -> str:
        """获取光标处的单词"""
        if not self._content or self._cursor_pos > len(self._content):
            return ""

        # 向前查找单词边界
        start = self._cursor_pos
        while start > 0 and self._content[start - 1].isalnum():
            start -= 1

        # 向后查找单词边界
        end = self._cursor_pos
        while end < len(self._content) and self._content[end].isalnum():
            end += 1

        return self._content[start:end]

    def get_current_line(self) -> str:
        """获取光标所在的行"""
        lines = self._content.split('\n')
        line_num = self._content[:self._cursor_pos].count('\n')
        if 0 <= line_num < len(lines):
            return lines[line_num]
        return ""

    def get_context_before_cursor(self, chars: int = 100) -> str:
        """获取光标前N个字符的上下文"""
        start = max(0, self._cursor_pos - chars)
        return self._content[start:self._cursor_pos]

    def get_context_after_cursor(self, chars: int = 100) -> str:
        """获取光标后N个字符的上下文"""
        end = min(len(self._content), self._cursor_pos + chars)
        return self._content[self._cursor_pos:end]

    # 事件绑定
    def on_content_change(self, callback: Callable):
        """内容变化回调"""
        self._on_content_change = callback

    def on_mode_change(self, callback: Callable):
        """模式变化回调"""
        self._on_mode_change = callback

    def on_cursor_change(self, callback: Callable):
        """光标变化回调"""
        self._on_cursor_change = callback

    def set_ai_operator(self, operator):
        """设置AI操作处理器"""
        self._ai_operator = operator

    # 快捷操作
    def format_as_json(self) -> str:
        """格式化JSON"""
        try:
            import json
            obj = json.loads(self._content)
            return json.dumps(obj, indent=2, ensure_ascii=False)
        except:
            return self._content

    def format_as_markdown_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """生成Markdown表格"""
        if not headers or not rows:
            return ""

        lines = []
        # 表头
        lines.append('| ' + ' | '.join(headers) + ' |')
        # 分隔线
        lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        # 数据行
        for row in rows:
            lines.append('| ' + ' | '.join(str(cell) for cell in row) + ' |')

        return '\n'.join(lines)

    def to_html(self) -> str:
        """将当前内容转换为HTML"""
        if self.mode == EditorMode.MARKDOWN:
            return self._markdown_to_html(self._content)
        elif self.mode == EditorMode.HTML:
            return self._content
        else:
            # 纯文本转HTML
            return '<pre>' + self._content.replace('<', '&lt;').replace('>', '&gt;') + '</pre>'

    def _markdown_to_html(self, text: str) -> str:
        """Markdown转HTML基本转换"""
        html = text
        # 标题
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        # 粗体
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        # 斜体
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        # 链接
        html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', html)
        # 代码
        html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
        # 段落
        html = re.sub(r'\n\n', r'</p><p>', html)
        return '<p>' + html + '</p>'


# 全局编辑器实例
_global_editor: Optional[SmartEditor] = None
_editor_lock = Lock()


def get_editor(config: Optional[EditorConfig] = None) -> SmartEditor:
    """获取全局编辑器实例"""
    global _global_editor
    with _editor_lock:
        if _global_editor is None:
            _global_editor = SmartEditor(config)
        return _global_editor