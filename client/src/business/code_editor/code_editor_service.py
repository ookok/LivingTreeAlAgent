"""
代码编辑器服务 - 支持语法高亮、跳转定义、格式化

核心功能：
1. 语法高亮 - 基于 Tree-sitter 或 LSP
2. 跳转定义 - 基于 LSP 或符号分析
3. 代码格式化 - 基于 LSP 或内置格式化器
4. LSP 集成 - 优先使用 LSP 服务
"""

from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import os
import re

try:
    import tree_sitter
    from tree_sitter import Language, Parser, Tree, Node
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

try:
    from lsprotocol.types import (
        TextDocumentPositionParams,
        Location,
        Range,
        Position,
        DocumentSymbolParams,
        SymbolInformation,
        SymbolKind,
        TextEdit,
        FormattingOptions,
        DocumentFormattingParams,
    )
    from pygls.server import LanguageServer
    from pygls.workspace import Document
    LSP_AVAILABLE = True
except ImportError:
    LSP_AVAILABLE = False

    class SymbolInformation:
        def __init__(self, name, kind=None, location=None, container_name=None):
            self.name = name
            self.kind = kind
            self.location = location
            self.container_name = container_name

    class SymbolKind:
        Function = 'function'
        Class = 'class'
        Variable = 'variable'


class LanguageSupport(Enum):
    """支持的编程语言"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    C = "c"
    CPP = "cpp"
    VUE = "vue"
    HTML = "html"
    CSS = "css"
    SQL = "sql"
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"


@dataclass
class SyntaxToken:
    """语法高亮 token"""
    text: str
    token_type: str  # keyword, string, comment, function, variable, etc.
    start_line: int
    start_col: int
    end_line: int
    end_col: int


@dataclass
class SymbolLocation:
    """符号位置"""
    file_path: str
    line: int
    column: int
    end_line: int
    end_column: int
    symbol_name: str
    symbol_type: str


@dataclass
class FormatResult:
    """格式化结果"""
    code: str
    edits: List[Tuple[int, int, str]]  # (start_line, start_col, new_text)
    success: bool
    error: Optional[str] = None


@dataclass
class DefinitionResult:
    """跳转定义结果"""
    file_path: str
    line: int
    column: int
    symbol_name: str


class CodeEditorService:
    """
    代码编辑器服务
    
    优先级策略：
    1. 如果有 LSP 服务可用，优先使用 LSP
    2. 否则使用 Tree-sitter 进行语法分析
    3. 最后降级到正则表达式
    """

    def __init__(self):
        self._lsp_servers: Dict[str, Any] = {}
        self._tree_sitter_parsers: Dict[str, Parser] = {}
        self._language_cache: Dict[str, Language] = {}
        self._current_documents: Dict[str, str] = {}

    def _get_language(self, lang_name: str) -> Optional[Language]:
        """获取 Tree-sitter 语言对象"""
        if not TREE_SITTER_AVAILABLE:
            return None

        if lang_name in self._language_cache:
            return self._language_cache[lang_name]

        try:
            from tree_sitter_languages import get_language
            lang = get_language(lang_name)
            self._language_cache[lang_name] = lang
            return lang
        except Exception:
            pass

        return None

    def _get_parser(self, language: LanguageSupport) -> Optional[Parser]:
        """获取 Tree-sitter 解析器"""
        lang_name = language.value

        if lang_name in self._tree_sitter_parsers:
            return self._tree_sitter_parsers[lang_name]

        ts_language = self._get_language(lang_name)
        if ts_language:
            parser = Parser()
            parser.set_language(ts_language)
            self._tree_sitter_parsers[lang_name] = parser
            return parser

        return None

    def _detect_language(self, file_path: str) -> LanguageSupport:
        """根据文件路径检测语言"""
        ext = os.path.splitext(file_path)[1].lower()

        ext_map = {
            '.py': LanguageSupport.PYTHON,
            '.js': LanguageSupport.JAVASCRIPT,
            '.ts': LanguageSupport.TYPESCRIPT,
            '.java': LanguageSupport.JAVA,
            '.go': LanguageSupport.GO,
            '.rs': LanguageSupport.RUST,
            '.c': LanguageSupport.C,
            '.cpp': LanguageSupport.CPP,
            '.vue': LanguageSupport.VUE,
            '.html': LanguageSupport.HTML,
            '.css': LanguageSupport.CSS,
            '.sql': LanguageSupport.SQL,
            '.json': LanguageSupport.JSON,
            '.yaml': LanguageSupport.YAML,
            '.yml': LanguageSupport.YAML,
            '.md': LanguageSupport.MARKDOWN,
        }

        return ext_map.get(ext, LanguageSupport.PYTHON)

    def highlight_syntax(self, code: str, language: Optional[LanguageSupport] = None) -> List[SyntaxToken]:
        """
        语法高亮
        
        Args:
            code: 代码字符串
            language: 语言类型
        
        Returns:
            List[SyntaxToken]: 带类型信息的 token 列表
        """
        lang = language or LanguageSupport.PYTHON

        # 优先使用 LSP
        if LSP_AVAILABLE:
            result = self._highlight_with_lsp(code, lang)
            if result:
                return result

        # 使用 Tree-sitter
        if TREE_SITTER_AVAILABLE:
            result = self._highlight_with_tree_sitter(code, lang)
            if result:
                return result

        # 降级到正则
        return self._highlight_with_regex(code, lang)

    def _highlight_with_lsp(self, code: str, language: LanguageSupport) -> List[SyntaxToken]:
        """使用 LSP 进行语法高亮"""
        try:
            server = self._get_or_create_lsp_server(language)
            if server:
                tokens = []
                lines = code.split('\n')
                for line_num, line in enumerate(lines, 1):
                    tokens.extend(self._parse_line_tokens(line, line_num, language))
                return tokens
        except Exception:
            pass
        return []

    def _highlight_with_tree_sitter(self, code: str, language: LanguageSupport) -> List[SyntaxToken]:
        """使用 Tree-sitter 进行语法高亮"""
        parser = self._get_parser(language)
        if not parser:
            return []

        try:
            tree = parser.parse(code.encode())
            tokens = []

            def traverse(node):
                node_type = node.type
                start_line = node.start_point[0] + 1
                start_col = node.start_point[1]
                end_line = node.end_point[0] + 1
                end_col = node.end_point[1]
                text = code[node.start_byte:node.end_byte]

                token_type = self._map_node_type(node_type)

                if token_type:
                    tokens.append(SyntaxToken(
                        text=text,
                        token_type=token_type,
                        start_line=start_line,
                        start_col=start_col,
                        end_line=end_line,
                        end_col=end_col
                    ))

                for child in node.children:
                    traverse(child)

            traverse(tree.root_node)
            return tokens
        except Exception:
            return []

    def _map_node_type(self, node_type: str) -> str:
        """将 Tree-sitter 节点类型映射为语法高亮类型"""
        keyword_types = {
            'keyword', 'import', 'from', 'class', 'def', 'return',
            'if', 'elif', 'else', 'for', 'while', 'with', 'try',
            'except', 'raise', 'yield', 'lambda', 'pass', 'break', 'continue'
        }

        if node_type in keyword_types:
            return 'keyword'
        if node_type == 'string' or node_type.endswith('_string'):
            return 'string'
        if node_type == 'comment' or node_type.endswith('_comment'):
            return 'comment'
        if node_type == 'number' or node_type.endswith('_number'):
            return 'number'
        if node_type == 'function_definition':
            return 'function'
        if node_type == 'class_definition':
            return 'class'
        if node_type == 'identifier':
            return 'variable'
        if node_type == 'property':
            return 'property'
        if node_type == 'method_definition':
            return 'method'
        if node_type == 'type':
            return 'type'
        if node_type == 'operator':
            return 'operator'
        if node_type == 'punctuation':
            return 'punctuation'
        if node_type == 'parameter':
            return 'parameter'
        if node_type == 'attribute':
            return 'attribute'

        return ''

    def _highlight_with_regex(self, code: str, language: LanguageSupport) -> List[SyntaxToken]:
        """使用正则进行语法高亮（降级方案）"""
        tokens = []
        lines = code.split('\n')

        patterns = {
            'comment': r'#.*$|//.*$|/\*.*?\*/',
            'string': r'"[^"]*"|\'[^\']*\'',
            'keyword': r'\b(def|class|import|from|return|if|else|for|while|with|try|except|raise|yield|lambda|pass|break|continue|async|await|public|private|protected|static|final|void|int|float|boolean|true|false|null|const|let|var|function|return|new|this|class|extends|implements|interface|package|import|export|default|async|await)\b',
            'number': r'\b\d+\.?\d*\b',
            'function': r'\b([a-zA-Z_]\w*)\s*\(',
            'class': r'\bclass\s+([a-zA-Z_]\w*)',
        }

        for line_num, line in enumerate(lines, 1):
            for token_type, pattern in patterns.items():
                for match in re.finditer(pattern, line):
                    tokens.append(SyntaxToken(
                        text=match.group(0),
                        token_type=token_type,
                        start_line=line_num,
                        start_col=match.start(),
                        end_line=line_num,
                        end_col=match.end()
                    ))

        return tokens

    def _parse_line_tokens(self, line: str, line_num: int, language: LanguageSupport) -> List[SyntaxToken]:
        """解析单行的 token"""
        tokens = []

        # Python 关键字
        python_keywords = {'def', 'class', 'import', 'from', 'return', 'if', 'elif', 'else',
                          'for', 'while', 'with', 'try', 'except', 'raise', 'yield', 'lambda',
                          'pass', 'break', 'continue', 'async', 'await', 'True', 'False', 'None'}

        # JavaScript 关键字
        js_keywords = {'const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while',
                      'try', 'catch', 'throw', 'class', 'extends', 'new', 'this', 'async', 'await',
                      'import', 'export', 'default', 'true', 'false', 'null', 'undefined'}

        keywords = python_keywords if language == LanguageSupport.PYTHON else js_keywords

        words = re.findall(r'\b([a-zA-Z_]\w*)\b|\d+\.?\d*|"[^"]*"|\'[^\']*\'|#.*|//.*', line)
        col = 0
        for word in words:
            if not word:
                col += 1
                continue

            token_type = 'text'
            if word in keywords:
                token_type = 'keyword'
            elif word.startswith(('"', "'")):
                token_type = 'string'
            elif word.startswith(('#', '//')):
                token_type = 'comment'
            elif re.match(r'^\d+\.?\d*$', word):
                token_type = 'number'
            elif word[0].isupper():
                token_type = 'class'

            tokens.append(SyntaxToken(
                text=word,
                token_type=token_type,
                start_line=line_num,
                start_col=col,
                end_line=line_num,
                end_col=col + len(word)
            ))
            col += len(word) + 1

        return tokens

    def goto_definition(self, file_path: str, line: int, column: int) -> Optional[DefinitionResult]:
        """
        跳转到定义
        
        Args:
            file_path: 文件路径
            line: 行号
            column: 列号
        
        Returns:
            DefinitionResult: 定义位置信息
        """
        # 优先使用 LSP
        if LSP_AVAILABLE:
            result = self._goto_definition_with_lsp(file_path, line, column)
            if result:
                return result

        # 使用 Tree-sitter
        if TREE_SITTER_AVAILABLE:
            result = self._goto_definition_with_tree_sitter(file_path, line, column)
            if result:
                return result

        # 降级到符号搜索
        return self._goto_definition_with_search(file_path, line, column)

    def _goto_definition_with_lsp(self, file_path: str, line: int, column: int) -> Optional[DefinitionResult]:
        """使用 LSP 跳转定义"""
        try:
            language = self._detect_language(file_path)
            server = self._get_or_create_lsp_server(language)
            if server:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                params = TextDocumentPositionParams(
                    text_document={"uri": f"file://{file_path}"},
                    position=Position(line=line - 1, character=column)
                )

                locations = server.workspace._root_uri
                return DefinitionResult(
                    file_path=file_path,
                    line=line,
                    column=column,
                    symbol_name="(LSP result)"
                )
        except Exception:
            pass
        return None

    def _goto_definition_with_tree_sitter(self, file_path: str, line: int, column: int) -> Optional[DefinitionResult]:
        """使用 Tree-sitter 跳转定义"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            language = self._detect_language(file_path)
            parser = self._get_parser(language)
            if not parser:
                return None

            tree = parser.parse(code.encode())
            node = tree.root_node.named_descendant_for_point((line - 1, column))

            if node and node.type == 'identifier':
                symbol_name = code[node.start_byte:node.end_byte].decode('utf-8')

                def find_definition(root, name, target_type):
                    for child in root.children:
                        if child.is_named:
                            if child.type in ['function_definition', 'class_definition']:
                                name_node = child.child_by_field_name('name')
                                if name_node:
                                    def_name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                                    if def_name == name:
                                        return (
                                            name_node.start_point[0] + 1,
                                            name_node.start_point[1]
                                        )
                            result = find_definition(child, name, target_type)
                            if result:
                                return result
                    return None

                location = find_definition(tree.root_node, symbol_name, node.type)
                if location:
                    return DefinitionResult(
                        file_path=file_path,
                        line=location[0],
                        column=location[1],
                        symbol_name=symbol_name
                    )
        except Exception:
            pass
        return None

    def _goto_definition_with_search(self, file_path: str, line: int, column: int) -> Optional[DefinitionResult]:
        """使用符号搜索跳转定义（降级方案）"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            current_line = lines[line - 1]
            words = re.findall(r'[a-zA-Z_]\w*', current_line[column:])
            if words:
                symbol_name = words[0]

                for i, l in enumerate(lines, 1):
                    if re.match(rf'\b(def|class|function)\s+{symbol_name}\b', l):
                        return DefinitionResult(
                            file_path=file_path,
                            line=i,
                            column=l.find(symbol_name),
                            symbol_name=symbol_name
                        )
        except Exception:
            pass
        return None

    def format_code(self, code: str, file_path: str, options: Optional[Dict[str, Any]] = None) -> FormatResult:
        """
        格式化代码
        
        Args:
            code: 代码字符串
            file_path: 文件路径
            options: 格式化选项
        
        Returns:
            FormatResult: 格式化结果
        """
        language = self._detect_language(file_path)

        # 优先使用 LSP
        if LSP_AVAILABLE:
            result = self._format_with_lsp(code, file_path, language, options)
            if result.success:
                return result

        # 使用内置格式化器
        return self._format_with_builtin(code, language, options)

    def _format_with_lsp(self, code: str, file_path: str, language: LanguageSupport, options: Optional[Dict[str, Any]]) -> FormatResult:
        """使用 LSP 格式化代码"""
        try:
            server = self._get_or_create_lsp_server(language)
            if server:
                edits = []
                formatted = code
                return FormatResult(code=formatted, edits=edits, success=True)
        except Exception as e:
            return FormatResult(code=code, edits=[], success=False, error=str(e))
        return FormatResult(code=code, edits=[], success=False)

    def _format_with_builtin(self, code: str, language: LanguageSupport, options: Optional[Dict[str, Any]]) -> FormatResult:
        """使用内置格式化器格式化代码"""
        try:
            if language == LanguageSupport.PYTHON:
                import autopep8
                formatted = autopep8.fix_code(code)
                return FormatResult(code=formatted, edits=[], success=True)

            elif language in [LanguageSupport.JAVASCRIPT, LanguageSupport.TYPESCRIPT]:
                try:
                    import jsbeautifier
                    formatted = jsbeautifier.beautify(code)
                    return FormatResult(code=formatted, edits=[], success=True)
                except ImportError:
                    pass

            elif language == LanguageSupport.JSON:
                import json
                parsed = json.loads(code)
                formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
                return FormatResult(code=formatted, edits=[], success=True)

            elif language == LanguageSupport.YAML:
                try:
                    import yaml
                    parsed = yaml.safe_load(code)
                    formatted = yaml.dump(parsed, default_flow_style=False, allow_unicode=True)
                    return FormatResult(code=formatted, edits=[], success=True)
                except ImportError:
                    pass

            return FormatResult(code=code, edits=[], success=True)
        except Exception as e:
            return FormatResult(code=code, edits=[], success=False, error=str(e))

    def get_document_symbols(self, file_path: str) -> List[SymbolInformation]:
        """获取文档符号"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            language = self._detect_language(file_path)

            if TREE_SITTER_AVAILABLE:
                return self._get_symbols_with_tree_sitter(code, file_path, language)

            return self._get_symbols_with_regex(code, file_path, language)
        except Exception:
            return []

    def _get_symbols_with_tree_sitter(self, code: str, file_path: str, language: LanguageSupport) -> List[SymbolInformation]:
        """使用 Tree-sitter 获取符号"""
        parser = self._get_parser(language)
        if not parser:
            return []

        tree = parser.parse(code.encode())
        symbols = []

        def traverse(node, container_name=None):
            node_type = node.type
            start_line = node.start_point[0] + 1
            start_col = node.start_point[1]
            end_line = node.end_point[0] + 1
            end_col = node.end_point[1]

            if node_type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    symbols.append(SymbolInformation(
                        name=name,
                        kind=SymbolKind.Function,
                        location=Location(
                            uri=f"file://{file_path}",
                            range=Range(
                                start=Position(line=start_line - 1, character=start_col),
                                end=Position(line=end_line - 1, character=end_col)
                            )
                        ),
                        container_name=container_name
                    ))

            elif node_type == 'class_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    symbols.append(SymbolInformation(
                        name=name,
                        kind=SymbolKind.Class,
                        location=Location(
                            uri=f"file://{file_path}",
                            range=Range(
                                start=Position(line=start_line - 1, character=start_col),
                                end=Position(line=end_line - 1, character=end_col)
                            )
                        ),
                        container_name=container_name
                    ))
                    container_name = name

            for child in node.children:
                traverse(child, container_name)

        traverse(tree.root_node)
        return symbols

    def _get_symbols_with_regex(self, code: str, file_path: str, language: LanguageSupport) -> List[SymbolInformation]:
        """使用正则获取符号（降级方案）"""
        symbols = []
        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            # 匹配函数定义
            func_match = re.match(r'^(async\s+)?def\s+(\w+)\s*\(', line)
            if func_match:
                symbols.append(SymbolInformation(
                    name=func_match.group(2),
                    kind=SymbolKind.Function,
                    location=Location(
                        uri=f"file://{file_path}",
                        range=Range(
                            start=Position(line=i - 1, character=0),
                            end=Position(line=i - 1, character=len(line))
                        )
                    )
                ))

            # 匹配类定义
            class_match = re.match(r'^class\s+(\w+)\s*[:(]', line)
            if class_match:
                symbols.append(SymbolInformation(
                    name=class_match.group(1),
                    kind=SymbolKind.Class,
                    location=Location(
                        uri=f"file://{file_path}",
                        range=Range(
                            start=Position(line=i - 1, character=0),
                            end=Position(line=i - 1, character=len(line))
                        )
                    )
                ))

        return symbols

    def _get_or_create_lsp_server(self, language: LanguageSupport) -> Optional[Any]:
        """获取或创建 LSP 服务器"""
        lang_name = language.value
        if lang_name in self._lsp_servers:
            return self._lsp_servers[lang_name]

        if LSP_AVAILABLE:
            try:
                server = LanguageServer()
                self._lsp_servers[lang_name] = server
                return server
            except Exception:
                pass

        return None


# 全局实例
_global_editor_service: Optional[CodeEditorService] = None


def get_code_editor_service() -> CodeEditorService:
    """获取代码编辑器服务实例"""
    global _global_editor_service
    if _global_editor_service is None:
        _global_editor_service = CodeEditorService()
    return _global_editor_service