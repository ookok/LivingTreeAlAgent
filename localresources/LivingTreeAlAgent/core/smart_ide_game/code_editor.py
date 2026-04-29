"""
代码编辑器核心模块
提供多语言语法高亮、智能补全、代码导航等功能
"""
import re
import asyncio
from typing import Dict, List, Optional, Tuple, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import hashlib


class TokenType(Enum):
    """语法标记类型"""
    KEYWORD = "keyword"
    STRING = "string"
    NUMBER = "number"
    COMMENT = "comment"
    FUNCTION = "function"
    CLASS = "class"
    VARIABLE = "variable"
    OPERATOR = "operator"
    PUNCTUATION = "punctuation"
    TYPE = "type"
    DECORATOR = "decorator"
    REGEX = "regex"
    ERROR = "error"
    PLAIN = "plain"


@dataclass
class Token:
    """语法标记"""
    type: TokenType
    value: str
    start: int
    end: int
    line: int
    column: int


@dataclass
class CodePosition:
    """代码位置"""
    line: int
    column: int
    offset: int


@dataclass
class CodeRange:
    """代码范围"""
    start: CodePosition
    end: CodePosition


@dataclass
class CompletionItem:
    """补全项"""
    label: str
    kind: str  # function, method, class, variable, constant, keyword
    detail: str = ""
    documentation: str = ""
    insert_text: str = ""
    prefix: str = ""
    score: float = 0.0
    filter_text: str = ""
    priority: int = 0


@dataclass
class Diagnostic:
    """诊断信息"""
    severity: str  # error, warning, info, hint
    message: str
    range: CodeRange
    code: Optional[str] = None
    source: str = "editor"
    suggestions: List[str] = field(default_factory=list)


@dataclass
class Symbol:
    """代码符号"""
    name: str
    kind: str  # function, class, method, variable, constant
    location: CodeRange
    container_name: Optional[str] = None
    signature: Optional[str] = None
    documentation: str = ""
    visibility: str = "public"  # public, private, protected


@dataclass
class CodeDocument:
    """代码文档"""
    uri: str
    content: str
    language: str
    version: int = 1
    diagnostics: List[Diagnostic] = field(default_factory=list)
    symbols: List[Symbol] = field(default_factory=list)
    last_modified: datetime = field(default_factory=datetime.now)


class SyntaxHighlighter:
    """语法高亮器"""

    # 各语言的关键词
    KEYWORDS: Dict[str, Set[str]] = {
        "python": {"if", "elif", "else", "for", "while", "try", "except", "finally",
                   "with", "def", "class", "return", "yield", "import", "from",
                   "as", "in", "is", "not", "and", "or", "True", "False", "None",
                   "lambda", "pass", "break", "continue", "raise", "assert", "del",
                   "global", "nonlocal", "async", "await", "match", "case"},
        "javascript": {"if", "else", "for", "while", "do", "switch", "case", "default",
                      "try", "catch", "finally", "throw", "return", "break", "continue",
                      "function", "const", "let", "var", "class", "extends", "new",
                      "this", "super", "import", "export", "from", "as", "async", "await",
                      "yield", "typeof", "instanceof", "in", "of", "delete", "void",
                      "true", "false", "null", "undefined", "static", "get", "set"},
        "java": {"if", "else", "for", "while", "do", "switch", "case", "default",
                 "try", "catch", "finally", "throw", "throws", "return", "break",
                 "continue", "class", "interface", "extends", "implements", "new",
                 "this", "super", "import", "package", "public", "private", "protected",
                 "static", "final", "abstract", "synchronized", "volatile", "native",
                 "void", "boolean", "byte", "char", "short", "int", "long", "float",
                 "double", "true", "false", "null", "instanceof", "enum", "assert"},
        "cpp": {"if", "else", "for", "while", "do", "switch", "case", "default",
                "try", "catch", "throw", "return", "break", "continue", "class",
                "struct", "union", "enum", "public", "private", "protected",
                "virtual", "override", "final", "static", "const", "volatile",
                "inline", "extern", "template", "typename", "namespace", "using",
                "new", "delete", "this", "nullptr", "true", "false", "void", "int",
                "float", "double", "char", "bool", "long", "short", "unsigned",
                "signed", "auto", "decltype", "sizeof", "alignof", "asm", "goto"},
        "go": {"if", "else", "for", "range", "switch", "case", "default", "select",
               "break", "continue", "return", "goto", "fallthrough", "func", "type",
               "struct", "interface", "map", "chan", "package", "import", "var",
               "const", "var", "defer", "go", "select", "make", "new", "len", "cap",
               "append", "copy", "delete", "panic", "recover", "true", "false", "nil"},
        "rust": {"if", "else", "match", "for", "while", "loop", "break", "continue",
                 "return", "fn", "let", "mut", "const", "static", "struct", "enum",
                 "impl", "trait", "type", "where", "pub", "mod", "use", "crate", "self",
                 "super", "unsafe", "async", "await", "move", "ref", "dyn", "as", "in",
                 "true", "false", "Some", "None", "Ok", "Err", "Self", "macro_rules"},
    }

    # 类型关键词
    TYPE_KEYWORDS: Dict[str, Set[str]] = {
        "python": {"int", "float", "str", "bool", "list", "dict", "set", "tuple",
                   "bytes", "object", "type", "Any", "Union", "Optional", "List",
                   "Dict", "Set", "Tuple", "Callable", "Iterable", "Iterator"},
        "javascript": {"Object", "Array", "String", "Number", "Boolean", "Function",
                       "Symbol", "Map", "Set", "WeakMap", "WeakSet", "Promise",
                       "Proxy", "Reflect", "Error", "Date", "RegExp", "JSON"},
        "java": {"String", "Integer", "Long", "Double", "Float", "Boolean", "Character",
                 "Object", "Class", "List", "ArrayList", "Map", "HashMap", "Set",
                 "HashSet", "Queue", "Stack", "Collection", "Iterable", "Serializable"},
    }

    # 字符串引号
    STRING_QUOTES: Dict[str, List[str]] = {
        "python": ['"', "'", '"""', "'''", 'f"', "f'", 'r"', "r'", 'b"', "b'"],
        "javascript": ['"', "'", '`', 'f"', "f'", 'b"', "b'", 'u"'],
        "java": ['"', "'", '`'],
    }

    # 注释格式
    COMMENT_FORMATS: Dict[str, Dict[str, Tuple[str, Optional[str]]]] = {
        "python": {"single": ("#", None), "multi": ('"""', '"""'), "doc": ("'''", "'''")},
        "javascript": {"single": ("//", None), "multi": ("/*", "*/"), "doc": ("/**", "*/")},
        "java": {"single": ("//", None), "multi": ("/*", "*/"), "doc": ("/**", "*/")},
        "cpp": {"single": ("//", None), "multi": ("/*", "*/"), "doc": ("/*!", "*/")},
        "go": {"single": ("//", None), "multi": ("/*", "*/"), "doc": ("//", None)},
        "rust": {"single": ("//", None), "multi": ("/*", "*/"), "doc": ("///", None)},
    }

    def __init__(self, language: str = "python"):
        self.language = language.lower()
        self.keywords = self.KEYWORDS.get(self.language, set())
        self.type_keywords = self.TYPE_KEYWORDS.get(self.language, set())
        self.string_quotes = self.STRING_QUOTES.get(self.language, ['"', "'"])
        self.comment_format = self.COMMENT_FORMATS.get(self.language, {})

    def tokenize(self, code: str) -> List[Token]:
        """将代码分词"""
        tokens = []
        lines = code.split('\n')

        for line_num, line in enumerate(lines):
            col = 0
            while col < len(line):
                char = line[col]

                # 跳过空白
                if char in ' \t':
                    col += 1
                    continue

                # 检查注释
                if self._is_comment_start(line, col):
                    comment_token = self._extract_comment(line, col, line_num)
                    if comment_token:
                        tokens.append(comment_token)
                        col = len(line)
                        continue

                # 检查字符串
                if char in '"\'':
                    string_token = self._extract_string(line, col, line_num)
                    if string_token:
                        tokens.append(string_token)
                        col = string_token.end
                        continue

                # 检查数字
                if char.isdigit() or (char == '.' and col + 1 < len(line) and line[col + 1].isdigit()):
                    num_token = self._extract_number(line, col, line_num)
                    if num_token:
                        tokens.append(num_token)
                        col = num_token.end
                        continue

                # 检查标识符和关键字
                if char.isalpha() or char == '_':
                    ident_token = self._extract_identifier(line, col, line_num)
                    tokens.append(ident_token)
                    col = ident_token.end
                    continue

                # 检查操作符
                if char in '!=<>+-*/%&|^~@':
                    op_token = self._extract_operator(line, col, line_num)
                    tokens.append(op_token)
                    col = op_token.end
                    continue

                # 检查标点
                if char in '()[]{}:;,.':
                    tokens.append(Token(
                        type=TokenType.PUNCTUATION,
                        value=char,
                        start=col,
                        end=col + 1,
                        line=line_num,
                        column=col
                    ))
                    col += 1
                    continue

                # 普通文本
                tokens.append(Token(
                    type=TokenType.PLAIN,
                    value=char,
                    start=col,
                    end=col + 1,
                    line=line_num,
                    column=col
                ))
                col += 1

        return tokens

    def _is_comment_start(self, line: str, col: int) -> bool:
        """检查是否为注释开始"""
        if not self.comment_format:
            return False

        single_comment = self.comment_format.get("single")
        if single_comment and line[col:].startswith(single_comment[0]):
            return True

        multi_comment = self.comment_format.get("multi")
        if multi_comment and line[col:].startswith(multi_comment[0]):
            return True

        return False

    def _extract_comment(self, line: str, col: int, line_num: int) -> Optional[Token]:
        """提取注释"""
        if not self.comment_format:
            return None

        single_comment = self.comment_format.get("single")
        if single_comment and line[col:].startswith(single_comment[0]):
            return Token(
                type=TokenType.COMMENT,
                value=line[col:],
                start=col,
                end=len(line),
                line=line_num,
                column=col
            )

        multi_comment = self.comment_format.get("multi")
        if multi_comment:
            if line[col:].startswith(multi_comment[0]):
                end_marker = multi_comment[1] or multi_comment[0]
                end = line.find(end_marker, col + len(multi_comment[0]))
                if end != -1:
                    end += len(end_marker)
                else:
                    end = len(line)
                return Token(
                    type=TokenType.COMMENT,
                    value=line[col:end],
                    start=col,
                    end=end,
                    line=line_num,
                    column=col
                )

        return None

    def _extract_string(self, line: str, col: int, line_num: int) -> Optional[Token]:
        """提取字符串"""
        char = line[col]

        # 检查三引号字符串
        for triple_quote in ['"""', "'''", '"""', "'''"]:
            if line[col:].startswith(triple_quote):
                end = line.find(triple_quote, col + len(triple_quote))
                if end != -1:
                    end += len(triple_quote)
                else:
                    end = len(line)
                return Token(
                    type=TokenType.STRING,
                    value=line[col:end],
                    start=col,
                    end=end,
                    line=line_num,
                    column=col
                )

        # 检查f-string, r-string等
        prefixes = ['f', 'r', 'b', 'fr', 'rf', 'br', 'rb']
        for prefix in prefixes:
            for quote in ['"', "'"]:
                if line[col:].startswith(f"{prefix}{quote}"):
                    end_quote = line.find(quote, col + len(prefix) + 1)
                    if end_quote != -1:
                        return Token(
                            type=TokenType.STRING,
                            value=line[col:end_quote + 1],
                            start=col,
                            end=end_quote + 1,
                            line=line_num,
                            column=col
                        )

        # 普通字符串
        if char in '"\'':
            end = col + 1
            while end < len(line):
                if line[end] == '\\' and end + 1 < len(line):
                    end += 2
                    continue
                if line[end] == char:
                    end += 1
                    break
                if line[end] in '\n':
                    break
                end += 1

            return Token(
                type=TokenType.STRING,
                value=line[col:end],
                start=col,
                end=end,
                line=line_num,
                column=col
            )

        return None

    def _extract_number(self, line: str, col: int, line_num: int) -> Optional[Token]:
        """提取数字"""
        start = col
        has_dot = False
        has_e = False
        has_hex = False
        has_bin = False

        # 检查前缀
        if line[col:].startswith('0x') or line[col:].startswith('0X'):
            has_hex = True
            col += 2
        elif line[col:].startswith('0b') or line[col:].startswith('0B'):
            has_bin = True
            col += 2

        while col < len(line):
            char = line[col]

            if has_hex:
                if char in '0123456789abcdefABCDEF':
                    col += 1
                elif char in 'uUlL':
                    col += 1
                    break
                else:
                    break
            elif has_bin:
                if char in '01':
                    col += 1
                elif char in 'uUlL':
                    col += 1
                    break
                else:
                    break
            else:
                if char.isdigit():
                    col += 1
                elif char == '.' and not has_dot and not has_e:
                    has_dot = True
                    col += 1
                elif char in 'eE' and not has_e:
                    has_e = True
                    col += 1
                    if col < len(line) and line[col] in '+-':
                        col += 1
                elif char in 'fFdDlL':
                    col += 1
                    break
                else:
                    break

        if col > start:
            return Token(
                type=TokenType.NUMBER,
                value=line[start:col],
                start=start,
                end=col,
                line=line_num,
                column=start
            )

        return None

    def _extract_identifier(self, line: str, col: int, line_num: int) -> Token:
        """提取标识符"""
        start = col
        while col < len(line) and (line[col].isalnum() or line[col] == '_'):
            col += 1

        value = line[start:col]

        # 确定标识符类型
        if value in self.keywords:
            token_type = TokenType.KEYWORD
        elif value in self.type_keywords:
            token_type = TokenType.TYPE
        elif value.startswith('@'):
            token_type = TokenType.DECORATOR
        else:
            # 假设函数名以大写字母开头或后跟括号
            next_char = line[col] if col < len(line) else ''
            if next_char == '(':
                token_type = TokenType.FUNCTION
            elif value[0].isupper() and value[0].isalpha():
                token_type = TokenType.CLASS
            else:
                token_type = TokenType.VARIABLE

        return Token(
            type=token_type,
            value=value,
            start=start,
            end=col,
            line=line_num,
            column=start
        )

    def _extract_operator(self, line: str, col: int, line_num: int) -> Token:
        """提取操作符"""
        compound_ops = {
            '==', '!=', '<=', '>=', '+=', '-=', '*=', '/=', '%=', '//', '**',
            '<<', '>>', '&&', '||', '->', '=>', '::', '??', '?.', '?:', '++', '--',
            '&=', '|=', '^=', '~=', '<<=', '>>=', '...', '===', '!==',
        }

        # 检查两字符操作符
        if col + 1 < len(line):
            two_char = line[col:col + 2]
            if two_char in compound_ops:
                return Token(
                    type=TokenType.OPERATOR,
                    value=two_char,
                    start=col,
                    end=col + 2,
                    line=line_num,
                    column=col
                )

        # 检查三字符操作符
        if col + 2 < len(line):
            three_char = line[col:col + 3]
            if three_char in compound_ops:
                return Token(
                    type=TokenType.OPERATOR,
                    value=three_char,
                    start=col,
                    end=col + 3,
                    line=line_num,
                    column=col
                )

        return Token(
            type=TokenType.OPERATOR,
            value=line[col],
            start=col,
            end=col + 1,
            line=line_num,
            column=col
        )


class CodeNavigator:
    """代码导航器"""

    def __init__(self):
        self.documents: Dict[str, CodeDocument] = {}
        self.document_symbols: Dict[str, List[Symbol]] = {}

    def add_document(self, uri: str, content: str, language: str) -> CodeDocument:
        """添加文档"""
        doc = CodeDocument(uri=uri, content=content, language=language)
        self.documents[uri] = doc
        self._analyze_symbols(doc)
        return doc

    def _analyze_symbols(self, doc: CodeDocument) -> None:
        """分析文档中的符号"""
        symbols = []
        lines = doc.content.split('\n')

        for line_num, line in enumerate(lines):
            stripped = line.strip()

            # Python: 函数和类定义
            if doc.language == "python":
                if match := re.match(r'def\s+(\w+)\s*\((.*?)\)', stripped):
                    symbols.append(Symbol(
                        name=match.group(1),
                        kind="function",
                        location=CodeRange(
                            start=CodePosition(line_num, 0, 0),
                            end=CodePosition(line_num, len(line), 0)
                        ),
                        signature=match.group(2)
                    ))
                elif match := re.match(r'class\s+(\w+)(?:\([^)]+\))?:', stripped):
                    symbols.append(Symbol(
                        name=match.group(1),
                        kind="class",
                        location=CodeRange(
                            start=CodePosition(line_num, 0, 0),
                            end=CodePosition(line_num, len(line), 0)
                        )
                    ))
                elif match := re.match(r'@(\w+)', stripped):
                    symbols.append(Symbol(
                        name=match.group(1),
                        kind="decorator",
                        location=CodeRange(
                            start=CodePosition(line_num, 0, 0),
                            end=CodePosition(line_num, len(line), 0)
                        )
                    ))

            # JavaScript: 函数和类
            elif doc.language == "javascript":
                if match := re.match(r'(?:function|async\s+function)\s+(\w+)\s*\(', stripped):
                    symbols.append(Symbol(
                        name=match.group(1),
                        kind="function",
                        location=CodeRange(
                            start=CodePosition(line_num, 0, 0),
                            end=CodePosition(line_num, len(line), 0)
                        )
                    ))
                elif match := re.match(r'class\s+(\w+)', stripped):
                    symbols.append(Symbol(
                        name=match.group(1),
                        kind="class",
                        location=CodeRange(
                            start=CodePosition(line_num, 0, 0),
                            end=CodePosition(line_num, len(line), 0)
                        )
                    ))

            # Java: 方法和类
            elif doc.language == "java":
                if match := re.match(r'(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\((.*?)\)', stripped):
                    if match.group(1) not in {"if", "while", "for", "switch"}:
                        symbols.append(Symbol(
                            name=match.group(1),
                            kind="method",
                            location=CodeRange(
                                start=CodePosition(line_num, 0, 0),
                                end=CodePosition(line_num, len(line), 0)
                            ),
                            signature=match.group(2)
                        ))
                elif match := re.match(r'(?:public|private)?\s*class\s+(\w+)', stripped):
                    symbols.append(Symbol(
                        name=match.group(1),
                        kind="class",
                        location=CodeRange(
                            start=CodePosition(line_num, 0, 0),
                            end=CodePosition(line_num, len(line), 0)
                        )
                    ))

        doc.symbols = symbols
        self.document_symbols[doc.uri] = symbols

    def find_symbol(self, uri: str, name: str) -> Optional[Symbol]:
        """查找符号"""
        symbols = self.document_symbols.get(uri, [])
        for symbol in symbols:
            if symbol.name == name:
                return symbol
        return None

    def find_symbols_by_kind(self, uri: str, kind: str) -> List[Symbol]:
        """按类型查找符号"""
        symbols = self.document_symbols.get(uri, [])
        return [s for s in symbols if s.kind == kind]


class CompletionEngine:
    """代码补全引擎"""

    def __init__(self):
        self.builtins: Dict[str, List[CompletionItem]] = {}
        self.project_items: List[CompletionItem] = []
        self.snippet_items: List[CompletionItem] = []
        self._init_builtins()

    def _init_builtins(self):
        """初始化内置补全项"""
        # Python 内置
        self.builtins["python"] = [
            CompletionItem(label="print", kind="function", detail="print(*objects, sep=' ', end='\\n')"),
            CompletionItem(label="len", kind="function", detail="len(s) -> int"),
            CompletionItem(label="range", kind="function", detail="range(stop) / range(start, stop[, step])"),
            CompletionItem(label="str", kind="class", detail="str(object='') -> str"),
            CompletionItem(label="int", kind="class", detail="int(x=0) -> int"),
            CompletionItem(label="list", kind="class", detail="list() -> new empty list"),
            CompletionItem(label="dict", kind="class", detail="dict() -> new empty dictionary"),
            CompletionItem(label="set", kind="class", detail="set() -> new empty set"),
            CompletionItem(label="tuple", kind="class", detail="tuple() -> empty tuple"),
            CompletionItem(label="open", kind="function", detail="open(file, mode='r', ...)"),
            CompletionItem(label="input", kind="function", detail="input([prompt]) -> str"),
            CompletionItem(label="type", kind="type", detail="type(object) -> the object's type"),
            CompletionItem(label="isinstance", kind="function", detail="isinstance(object, class-or-tuple) -> bool"),
            CompletionItem(label="map", kind="function", detail="map(func, *iterables)"),
            CompletionItem(label="filter", kind="function", detail="filter(function, iterable)"),
            CompletionItem(label="enumerate", kind="function", detail="enumerate(iterable, start=0)"),
            CompletionItem(label="zip", kind="function", detail="zip(*iterables, strict=False)"),
            CompletionItem(label="sorted", kind="function", detail="sorted(iterable, *, key=None, reverse=False)"),
            CompletionItem(label="sum", kind="function", detail="sum(iterable, /, start=0)"),
            CompletionItem(label="min", kind="function", detail="min(iterable, *[, default=obj, key=func])"),
            CompletionItem(label="max", kind="function", detail="max(iterable, *[, default=obj, key=func])"),
            CompletionItem(label="abs", kind="function", detail="abs(x) -> the absolute value of x"),
            CompletionItem(label="round", kind="function", detail="round(number[, ndigits])"),
            CompletionItem(label="any", kind="function", detail="any(iterable) -> bool"),
            CompletionItem(label="all", kind="function", detail="all(iterable) -> bool"),
            CompletionItem(label="None", kind="constant", detail="the null object"),
            CompletionItem(label="True", kind="constant", detail="True value"),
            CompletionItem(label="False", kind="constant", detail="False value"),
        ]

        # JavaScript 内置
        self.builtins["javascript"] = [
            CompletionItem(label="console", kind="object", detail="console object"),
            CompletionItem(label="console.log", kind="method", detail="console.log(...data)"),
            CompletionItem(label="Math", kind="object", detail="Math object"),
            CompletionItem(label="Math.floor", kind="method", detail="Math.floor(x)"),
            CompletionItem(label="Math.random", kind="method", detail="Math.random() -> number"),
            CompletionItem(label="JSON", kind="object", detail="JSON object"),
            CompletionItem(label="JSON.stringify", kind="method", detail="JSON.stringify(value)"),
            CompletionItem(label="JSON.parse", kind="method", detail="JSON.parse(text)"),
            CompletionItem(label="Array", kind="class", detail="Array object"),
            CompletionItem(label="Object", kind="class", detail="Object constructor"),
            CompletionItem(label="Promise", kind="class", detail="Promise constructor"),
            CompletionItem(label="fetch", kind="function", detail="fetch(input, init) -> Promise"),
            CompletionItem(label="setTimeout", kind="function", detail="setTimeout(fn, delay, ...args)"),
            CompletionItem(label="setInterval", kind="function", detail="setInterval(fn, delay, ...args)"),
        ]

    def add_project_items(self, items: List[CompletionItem]) -> None:
        """添加项目补全项"""
        self.project_items.extend(items)

    def add_snippet(self, label: str, code: str, description: str = "") -> None:
        """添加代码片段"""
        self.snippet_items.append(CompletionItem(
            label=label,
            kind="snippet",
            detail=description,
            insert_text=code
        ))

    def get_completions(
        self,
        code: str,
        position: CodePosition,
        language: str,
        context: Optional[str] = None
    ) -> List[CompletionItem]:
        """获取补全项"""
        # 获取当前单词
        current_word = self._get_current_word(code, position)
        prefix = current_word.lower()

        completions = []

        # 添加内置补全
        builtins = self.builtins.get(language, [])
        for item in builtins:
            if prefix in item.label.lower():
                item.prefix = current_word
                item.score = len(prefix) / len(item.label) * 100
                completions.append(item)

        # 添加项目补全
        for item in self.project_items:
            if prefix in item.label.lower():
                item.prefix = current_word
                item.score = len(prefix) / len(item.label) * 80
                completions.append(item)

        # 添加代码片段
        for item in self.snippet_items:
            if prefix in item.label.lower():
                item.prefix = current_word
                item.score = len(prefix) / len(item.label) * 60
                completions.append(item)

        # 按分数排序
        completions.sort(key=lambda x: (-x.score, x.priority))

        return completions[:20]  # 限制返回数量

    def _get_current_word(self, code: str, position: CodePosition) -> str:
        """获取当前单词"""
        lines = code.split('\n')
        if position.line >= len(lines):
            return ""

        line = lines[position.line]
        if position.column >= len(line):
            return ""

        # 向后查找
        end = position.column
        while end < len(line) and (line[end].isalnum() or line[end] in '_$'):
            end += 1

        # 向前查找
        start = position.column
        while start > 0 and (line[start - 1].isalnum() or line[start - 1] in '_$'):
            start -= 1

        return line[start:end]


class Linter:
    """代码检查器"""

    def __init__(self):
        self.rules: Dict[str, List[Callable]] = {}
        self._init_rules()

    def _init_rules(self):
        """初始化检查规则"""
        # Python 规则
        self.rules["python"] = [
            self._check_trailing_whitespace,
            self._check_missing_docstring,
        ]

        # JavaScript 规则
        self.rules["javascript"] = [
            self._check_console_log,
        ]

    def lint(self, code: str, language: str) -> List[Diagnostic]:
        """检查代码"""
        diagnostics = []
        rules = self.rules.get(language, [])

        for rule in rules:
            try:
                diags = rule(code)
                diagnostics.extend(diags)
            except Exception:
                pass

        return diagnostics

    def _check_trailing_whitespace(self, code: str) -> List[Diagnostic]:
        """检查尾随空白"""
        diagnostics = []
        lines = code.split('\n')

        for line_num, line in enumerate(lines):
            if line.rstrip() != line:
                diagnostics.append(Diagnostic(
                    severity="hint",
                    message="Trailing whitespace",
                    range=CodeRange(
                        start=CodePosition(line_num, len(line.rstrip()), 0),
                        end=CodePosition(line_num, len(line), 0)
                    ),
                    source="linter",
                    suggestions=["Remove trailing whitespace"]
                ))

        return diagnostics

    def _check_missing_docstring(self, code: str) -> List[Diagnostic]:
        """检查缺失文档字符串"""
        return []

    def _check_console_log(self, code: str) -> List[Diagnostic]:
        """检查console.log（生产环境提示）"""
        diagnostics = []
        lines = code.split('\n')

        for line_num, line in enumerate(lines):
            if 'console.log' in line and 'debug' not in line.lower():
                diagnostics.append(Diagnostic(
                    severity="warning",
                    message="Unexpected console.log",
                    range=CodeRange(
                        start=CodePosition(line_num, 0, 0),
                        end=CodePosition(line_num, len(line), 0)
                    ),
                    source="linter",
                    suggestions=["Remove console.log or use a proper logging mechanism"]
                ))

        return diagnostics


class CodeFormatter:
    """代码格式化器"""

    def format(self, code: str, language: str, options: Optional[Dict] = None) -> str:
        """格式化代码"""
        options = options or {}

        if language == "python":
            return self._format_python(code, options)
        elif language in ["javascript", "typescript"]:
            return self._format_javascript(code, options)
        else:
            return code

    def _format_python(self, code: str, options: Dict) -> str:
        """格式化Python代码（简化实现）"""
        lines = code.split('\n')
        formatted_lines = []
        indent_level = 0
        indent_size = options.get('tab_size', 4)

        for line in lines:
            stripped = line.strip()
            formatted_lines.append(' ' * indent_level * indent_size + stripped)

            # 简单的缩进检测
            if stripped.endswith(':') and not stripped.startswith('#'):
                indent_level += 1
            elif stripped.startswith('def ') or stripped.startswith('class '):
                indent_level += 1

        return '\n'.join(formatted_lines)

    def _format_javascript(self, code: str, options: Dict) -> str:
        """格式化JavaScript代码（简化实现）"""
        lines = code.split('\n')
        formatted_lines = []
        indent_level = 0
        indent_size = options.get('tab_size', 2)

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('}'):
                indent_level = max(0, indent_level - 1)

            formatted_lines.append(' ' * indent_level * indent_size + stripped)

            if stripped.endswith('{'):
                indent_level += 1

        return '\n'.join(formatted_lines)


class CodeEditorCore:
    """代码编辑器核心"""

    def __init__(self):
        self.highlighter = SyntaxHighlighter()
        self.navigator = CodeNavigator()
        self.completion_engine = CompletionEngine()
        self.linter = Linter()
        self.formatter = CodeFormatter()
        self.documents: Dict[str, CodeDocument] = {}
        self.active_document: Optional[str] = None

    async def open_document(self, uri: str, content: str, language: str) -> CodeDocument:
        """打开文档"""
        doc = self.navigator.add_document(uri, content, language)
        self.documents[uri] = doc
        self.active_document = uri

        # 运行lint检查
        doc.diagnostics = self.linter.lint(content, language)

        return doc

    def get_tokens(self, uri: str) -> List[Token]:
        """获取语法标记"""
        doc = self.documents.get(uri)
        if not doc:
            return []

        self.highlighter.language = doc.language
        return self.highlighter.tokenize(doc.content)

    def get_completions(
        self,
        uri: str,
        position: CodePosition,
        context: Optional[str] = None
    ) -> List[CompletionItem]:
        """获取补全项"""
        doc = self.documents.get(uri)
        if not doc:
            return []

        return self.completion_engine.get_completions(
            doc.content,
            position,
            doc.language,
            context
        )

    def get_diagnostics(self, uri: str) -> List[Diagnostic]:
        """获取诊断信息"""
        doc = self.documents.get(uri)
        if not doc:
            return []
        return doc.diagnostics

    async def reformat_document(self, uri: str, options: Optional[Dict] = None) -> str:
        """重新格式化文档"""
        doc = self.documents.get(uri)
        if not doc:
            return ""

        formatted = self.formatter.format(doc.content, doc.language, options)
        doc.content = formatted
        doc.version += 1
        doc.last_modified = datetime.now()

        return formatted

    def find_symbols(self, uri: str, kind: Optional[str] = None) -> List[Symbol]:
        """查找符号"""
        if kind:
            return self.navigator.find_symbols_by_kind(uri, kind)
        return self.navigator.document_symbols.get(uri, [])

    def add_snippet(self, label: str, code: str, description: str = "") -> None:
        """添加代码片段"""
        self.completion_engine.add_snippet(label, code, description)

    def get_editor_stats(self) -> Dict[str, Any]:
        """获取编辑器统计"""
        return {
            "open_documents": len(self.documents),
            "total_diagnostics": sum(len(d.diagnostics) for d in self.documents.values()),
            "active_document": self.active_document,
        }
