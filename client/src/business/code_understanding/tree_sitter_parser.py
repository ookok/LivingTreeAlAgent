"""
代码解析器 - 基于 Tree-sitter 的语法分析

核心功能：
1. 支持多种编程语言（50+）
2. 精确语法树解析
3. 代码结构提取
4. 符号分析
5. 增量更新支持
"""

from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import os
import sys

try:
    import tree_sitter
    from tree_sitter import Language, Parser, Tree, Node
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


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
    PHP = "php"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    DART = "dart"
    RUBY = "ruby"
    PERL = "perl"
    LUA = "lua"
    SHELL = "bash"
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    MARKDOWN = "markdown"
    CMAKE = "cmake"
    MAKEFILE = "make"
    XML = "xml"


@dataclass
class SymbolInfo:
    """符号信息"""
    name: str
    type: str
    line: int
    column: int
    end_line: int
    end_column: int
    scope: Optional[str] = None
    docstring: Optional[str] = None
    modifiers: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    parameters: List[str] = field(default_factory=list)


@dataclass
class CodeStructure:
    """代码结构"""
    language: LanguageSupport
    symbols: List[SymbolInfo]
    imports: List[str]
    classes: List[SymbolInfo]
    functions: List[SymbolInfo]
    variables: List[SymbolInfo]
    errors: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SyntaxNode:
    """语法树节点"""
    type: str
    value: Optional[str]
    line: int
    column: int
    end_line: int
    end_column: int
    children: List['SyntaxNode'] = field(default_factory=list)
    parent: Optional['SyntaxNode'] = None


class TreeSitterParser:
    """
    基于 Tree-sitter 的代码解析器
    """

    _language_cache: Dict[str, Language] = {}
    _parser_cache: Dict[str, Parser] = {}

    def __init__(self, language: Optional[LanguageSupport] = None):
        self._language = language
        self._parser = None
        self._current_tree = None
        self._current_code = ""

    def _load_language(self, lang_name: str) -> Optional[Language]:
        """加载语言定义"""
        if not TREE_SITTER_AVAILABLE:
            return None

        if lang_name in TreeSitterParser._language_cache:
            return TreeSitterParser._language_cache[lang_name]

        base_dir = Path(__file__).parent.parent.parent.parent.parent
        lib_path = base_dir / f"tree-sitter-{lang_name}.so"

        if lib_path.exists():
            try:
                lang = Language(str(lib_path))
                TreeSitterParser._language_cache[lang_name] = lang
                return lang
            except Exception:
                pass

        try:
            from tree_sitter_languages import get_language
            lang = get_language(lang_name)
            TreeSitterParser._language_cache[lang_name] = lang
            return lang
        except Exception:
            pass

        return None

    def _get_parser(self, language: LanguageSupport) -> Optional[Parser]:
        """获取或缓存解析器"""
        if not TREE_SITTER_AVAILABLE:
            return None

        lang_name = language.value

        if lang_name in TreeSitterParser._parser_cache:
            return TreeSitterParser._parser_cache[lang_name]

        ts_language = self._load_language(lang_name)
        if ts_language:
            parser = Parser()
            parser.set_language(ts_language)
            TreeSitterParser._parser_cache[lang_name] = parser
            return parser

        return None

    def is_available(self) -> bool:
        """检查 Tree-sitter 是否可用"""
        return TREE_SITTER_AVAILABLE

    def detect_language(self, file_path: str) -> LanguageSupport:
        """根据文件路径检测语言"""
        ext = Path(file_path).suffix.lower()

        ext_map = {
            '.py': LanguageSupport.PYTHON,
            '.js': LanguageSupport.JAVASCRIPT,
            '.ts': LanguageSupport.TYPESCRIPT,
            '.java': LanguageSupport.JAVA,
            '.go': LanguageSupport.GO,
            '.rs': LanguageSupport.RUST,
            '.c': LanguageSupport.C,
            '.cpp': LanguageSupport.CPP,
            '.cxx': LanguageSupport.CPP,
            '.vue': LanguageSupport.VUE,
            '.html': LanguageSupport.HTML,
            '.css': LanguageSupport.CSS,
            '.sql': LanguageSupport.SQL,
            '.php': LanguageSupport.PHP,
            '.swift': LanguageSupport.SWIFT,
            '.kt': LanguageSupport.KOTLIN,
            '.dart': LanguageSupport.DART,
            '.rb': LanguageSupport.RUBY,
            '.pl': LanguageSupport.PERL,
            '.lua': LanguageSupport.LUA,
            '.sh': LanguageSupport.SHELL,
            '.json': LanguageSupport.JSON,
            '.yaml': LanguageSupport.YAML,
            '.yml': LanguageSupport.YAML,
            '.toml': LanguageSupport.TOML,
            '.md': LanguageSupport.MARKDOWN,
            '.cmake': LanguageSupport.CMAKE,
            'makefile': LanguageSupport.MAKEFILE,
            '.xml': LanguageSupport.XML,
        }

        return ext_map.get(ext, LanguageSupport.PYTHON)

    def parse(self, code: str, language: Optional[LanguageSupport] = None) -> CodeStructure:
        """解析代码"""
        lang = language or self._language or LanguageSupport.PYTHON
        self._current_code = code

        if not TREE_SITTER_AVAILABLE:
            return self._fallback_parse(code, lang)

        parser = self._get_parser(lang)
        if not parser:
            return self._fallback_parse(code, lang)

        try:
            tree = parser.parse(code.encode())
            self._current_tree = tree
            return self._extract_structure(tree, lang, code)
        except Exception as e:
            return CodeStructure(
                language=lang,
                symbols=[],
                imports=[],
                classes=[],
                functions=[],
                variables=[],
                errors=[{"error": str(e)}]
            )

    def _fallback_parse(self, code: str, language: LanguageSupport) -> CodeStructure:
        """降级到正则解析"""
        from .code_parser import CodeParser
        parser = CodeParser(language)
        result = parser.parse(code)
        if hasattr(result, 'errors'):
            result.errors.append({"warning": "使用降级解析器"})
        else:
            result = CodeStructure(
                language=language,
                symbols=result.symbols,
                imports=result.imports,
                classes=result.classes,
                functions=result.functions,
                variables=result.variables,
                errors=[{"warning": "使用降级解析器"}]
            )
        return result

    def update(self, code: str, start_byte: int, old_end_byte: int, new_end_byte: int) -> Optional[CodeStructure]:
        """增量更新解析"""
        if not TREE_SITTER_AVAILABLE:
            return self.parse(code)

        if self._current_tree is None:
            return self.parse(code)

        try:
            self._current_tree.edit(start_byte=start_byte, old_end_byte=old_end_byte, new_end_byte=new_end_byte)
            lang = self._language or LanguageSupport.PYTHON
            parser = self._get_parser(lang)
            if not parser:
                return None

            new_tree = parser.parse(code.encode(), self._current_tree)
            self._current_tree = new_tree
            self._current_code = code
            return self._extract_structure(new_tree, lang, code)
        except Exception:
            return None

    def _extract_structure(self, tree, language: LanguageSupport, code: str) -> CodeStructure:
        """从语法树提取代码结构"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []
        errors = []

        root_node = tree.root_node

        if root_node.has_error:
            errors.append({"type": "syntax_error", "message": "语法错误"})

        if language == LanguageSupport.PYTHON:
            symbols, imports, classes, functions, variables = self._extract_python(root_node, code)
        elif language in [LanguageSupport.JAVASCRIPT, LanguageSupport.TYPESCRIPT]:
            symbols, imports, classes, functions, variables = self._extract_js(root_node, code)
        elif language == LanguageSupport.JAVA:
            symbols, imports, classes, functions, variables = self._extract_java(root_node, code)
        elif language == LanguageSupport.GO:
            symbols, imports, classes, functions, variables = self._extract_go(root_node, code)
        elif language == LanguageSupport.RUST:
            symbols, imports, classes, functions, variables = self._extract_rust(root_node, code)
        elif language in [LanguageSupport.C, LanguageSupport.CPP]:
            symbols, imports, classes, functions, variables = self._extract_c(root_node, code)
        else:
            symbols, imports, classes, functions, variables = self._extract_generic(root_node, code)

        return CodeStructure(
            language=language,
            symbols=symbols,
            imports=imports,
            classes=classes,
            functions=functions,
            variables=variables,
            errors=errors
        )

    def _extract_python(self, node, code) -> Tuple[List[SymbolInfo], ...]:
        """提取 Python 代码结构"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []

        def traverse(node, parent_scope=None):
            node_type = node.type
            start_line = node.start_point[0] + 1
            start_col = node.start_point[1]
            end_line = node.end_point[0] + 1
            end_col = node.end_point[1]
            name = None

            if node_type == 'import_statement':
                for child in node.children:
                    if child.type == 'dotted_name':
                        name = code[child.start_byte:child.end_byte].decode('utf-8')
                        imports.append(name)
                        break

            elif node_type == 'import_from_statement':
                for child in node.children:
                    if child.type == 'dotted_name':
                        name = code[child.start_byte:child.end_byte].decode('utf-8')
                        imports.append(name)
                        break

            elif node_type == 'class_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='class',
                        line=start_line,
                        column=start_col,
                        end_line=end_line,
                        end_column=end_col,
                        scope=parent_scope
                    )
                    symbols.append(symbol)
                    classes.append(symbol)
                    current_scope = name
            else:
                current_scope = parent_scope

            if node_type == 'function_definition' or node_type == 'async_function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    func_type = 'async_function' if node_type == 'async_function_definition' else 'function'
                    params = self._extract_params(node, code)
                    symbol = SymbolInfo(
                        name=name,
                        type=func_type,
                        line=start_line,
                        column=start_col,
                        end_line=end_line,
                        end_column=end_col,
                        scope=parent_scope,
                        parameters=params
                    )
                    symbols.append(symbol)
                    functions.append(symbol)

            elif node_type == 'assignment':
                left_node = node.child_by_field_name('left')
                if left_node and left_node.type == 'identifier':
                    name = code[left_node.start_byte:left_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='variable',
                        line=start_line,
                        column=start_col,
                        end_line=end_line,
                        end_column=end_col,
                        scope=parent_scope
                    )
                    symbols.append(symbol)
                    variables.append(symbol)

            for child in node.children:
                traverse(child, current_scope)

        traverse(node)
        return symbols, imports, classes, functions, variables

    def _extract_js(self, node, code) -> Tuple[List[SymbolInfo], ...]:
        """提取 JavaScript/TypeScript 代码结构"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []

        def traverse(node, parent_scope=None):
            node_type = node.type
            start_line = node.start_point[0] + 1
            start_col = node.start_point[1]
            end_line = node.end_point[0] + 1
            end_col = node.end_point[1]
            name = None

            if node_type == 'import_statement':
                for child in node.children:
                    if child.type == 'import_clause':
                        for grandchild in child.children:
                            if grandchild.type == 'identifier':
                                name = code[grandchild.start_byte:grandchild.end_byte].decode('utf-8')
                                imports.append(name)
                                break

            elif node_type == 'class_declaration' or node_type == 'class_expression':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='class',
                        line=start_line,
                        column=start_col,
                        end_line=end_line,
                        end_column=end_col,
                        scope=parent_scope
                    )
                    symbols.append(symbol)
                    classes.append(symbol)
                    current_scope = name
            else:
                current_scope = parent_scope

            if node_type == 'function_declaration' or node_type == 'function_expression':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    params = self._extract_params(node, code)
                    symbol = SymbolInfo(
                        name=name,
                        type='function',
                        line=start_line,
                        column=start_col,
                        end_line=end_line,
                        end_column=end_col,
                        scope=parent_scope,
                        parameters=params
                    )
                    symbols.append(symbol)
                    functions.append(symbol)

            elif node_type == 'arrow_function':
                name_node = node.parent
                if name_node and name_node.type == 'variable_declarator':
                    id_node = name_node.child_by_field_name('id')
                    if id_node:
                        name = code[id_node.start_byte:id_node.end_byte].decode('utf-8')
                        symbol = SymbolInfo(
                            name=name,
                            type='function',
                            line=start_line,
                            column=start_col,
                            end_line=end_line,
                            end_column=end_col,
                            scope=parent_scope
                        )
                        symbols.append(symbol)
                        functions.append(symbol)

            elif node_type == 'variable_declarator':
                id_node = node.child_by_field_name('id')
                if id_node:
                    name = code[id_node.start_byte:id_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='variable',
                        line=start_line,
                        column=start_col,
                        end_line=end_line,
                        end_column=end_col,
                        scope=parent_scope
                    )
                    symbols.append(symbol)
                    variables.append(symbol)

            for child in node.children:
                traverse(child, current_scope)

        traverse(node)
        return symbols, imports, classes, functions, variables

    def _extract_java(self, node, code) -> Tuple[List[SymbolInfo], ...]:
        """提取 Java 代码结构"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []

        def traverse(node, parent_scope=None):
            node_type = node.type
            start_line = node.start_point[0] + 1

            if node_type == 'import_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    imports.append(name)

            elif node_type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='class',
                        line=start_line,
                        column=node.start_point[1],
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                        scope=parent_scope
                    )
                    symbols.append(symbol)
                    classes.append(symbol)
                    parent_scope = name

            elif node_type == 'method_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    params = self._extract_params(node, code)
                    symbol = SymbolInfo(
                        name=name,
                        type='method',
                        line=start_line,
                        column=node.start_point[1],
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                        scope=parent_scope,
                        parameters=params
                    )
                    symbols.append(symbol)
                    functions.append(symbol)

            for child in node.children:
                traverse(child, parent_scope)

        traverse(node)
        return symbols, imports, classes, functions, variables

    def _extract_go(self, node, code) -> Tuple[List[SymbolInfo], ...]:
        """提取 Go 代码结构"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []

        def traverse(node, parent_scope=None):
            node_type = node.type
            start_line = node.start_point[0] + 1

            if node_type == 'import_declaration':
                imports.append('go')

            elif node_type == 'function_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='function',
                        line=start_line,
                        column=node.start_point[1],
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                        scope=parent_scope
                    )
                    symbols.append(symbol)
                    functions.append(symbol)

            elif node_type == 'method_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    receiver_node = node.child_by_field_name('receiver')
                    receiver = ""
                    if receiver_node:
                        receiver = code[receiver_node.start_byte:receiver_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='method',
                        line=start_line,
                        column=node.start_point[1],
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                        scope=receiver
                    )
                    symbols.append(symbol)
                    functions.append(symbol)

            elif node_type == 'type_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='struct',
                        line=start_line,
                        column=node.start_point[1],
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                        scope=parent_scope
                    )
                    symbols.append(symbol)
                    classes.append(symbol)

            for child in node.children:
                traverse(child, parent_scope)

        traverse(node)
        return symbols, imports, classes, functions, variables

    def _extract_rust(self, node, code) -> Tuple[List[SymbolInfo], ...]:
        """提取 Rust 代码结构"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []

        def traverse(node, parent_scope=None):
            node_type = node.type
            start_line = node.start_point[0] + 1

            if node_type == 'use_declaration':
                path_node = node.child_by_field_name('path')
                if path_node:
                    name = code[path_node.start_byte:path_node.end_byte].decode('utf-8')
                    imports.append(name)

            elif node_type == 'function_item':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='function',
                        line=start_line,
                        column=node.start_point[1],
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                        scope=parent_scope
                    )
                    symbols.append(symbol)
                    functions.append(symbol)

            elif node_type == 'struct_item':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='struct',
                        line=start_line,
                        column=node.start_point[1],
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                        scope=parent_scope
                    )
                    symbols.append(symbol)
                    classes.append(symbol)

            elif node_type == 'enum_item':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='enum',
                        line=start_line,
                        column=node.start_point[1],
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                        scope=parent_scope
                    )
                    symbols.append(symbol)
                    classes.append(symbol)

            for child in node.children:
                traverse(child, parent_scope)

        traverse(node)
        return symbols, imports, classes, functions, variables

    def _extract_c(self, node, code) -> Tuple[List[SymbolInfo], ...]:
        """提取 C/C++ 代码结构"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []

        def traverse(node, parent_scope=None):
            node_type = node.type
            start_line = node.start_point[0] + 1

            if node_type == 'preproc_include':
                path_node = node.child_by_field_name('path')
                if path_node:
                    imports.append(code[path_node.start_byte:path_node.end_byte].decode('utf-8'))

            elif node_type == 'function_definition':
                declarator = node.child_by_field_name('declarator')
                if declarator:
                    name_node = declarator.child_by_field_name('declarator')
                    if not name_node:
                        name_node = declarator
                    if name_node.type == 'identifier':
                        name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                        symbol = SymbolInfo(
                            name=name,
                            type='function',
                            line=start_line,
                            column=node.start_point[1],
                            end_line=node.end_point[0] + 1,
                            end_column=node.end_point[1],
                            scope=parent_scope
                        )
                        symbols.append(symbol)
                        functions.append(symbol)

            elif node_type == 'class_specifier':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='class',
                        line=start_line,
                        column=node.start_point[1],
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                        scope=parent_scope
                    )
                    symbols.append(symbol)
                    classes.append(symbol)

            for child in node.children:
                traverse(child, parent_scope)

        traverse(node)
        return symbols, imports, classes, functions, variables

    def _extract_generic(self, node, code) -> Tuple[List[SymbolInfo], ...]:
        """通用提取器"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []

        def traverse(node, parent_scope=None):
            node_type = node.type
            start_line = node.start_point[0] + 1

            if node_type in ['function', 'method', 'func', 'fn']:
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='function',
                        line=start_line,
                        column=node.start_point[1],
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                        scope=parent_scope
                    )
                    symbols.append(symbol)
                    functions.append(symbol)

            elif node_type in ['class', 'struct', 'interface']:
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    symbol = SymbolInfo(
                        name=name,
                        type='class',
                        line=start_line,
                        column=node.start_point[1],
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                        scope=parent_scope
                    )
                    symbols.append(symbol)
                    classes.append(symbol)

            for child in node.children:
                traverse(child, parent_scope)

        traverse(node)
        return symbols, imports, classes, functions, variables

    def _extract_params(self, node, code) -> List[str]:
        """提取函数参数"""
        params = []
        params_node = node.child_by_field_name('parameters')
        if params_node:
            for child in params_node.children:
                if child.type == 'identifier':
                    params.append(code[child.start_byte:child.end_byte].decode('utf-8'))
                elif child.type == 'pattern':
                    for grandchild in child.children:
                        if grandchild.type == 'identifier':
                            params.append(code[grandchild.start_byte:grandchild.end_byte].decode('utf-8'))
        return params

    def build_syntax_tree(self, code: str, language: Optional[LanguageSupport] = None) -> SyntaxNode:
        """构建语法树"""
        if not TREE_SITTER_AVAILABLE:
            return SyntaxNode(type='program', value=None, line=1, column=0, end_line=1, end_column=0)

        lang = language or self._language or LanguageSupport.PYTHON
        parser = self._get_parser(lang)
        if not parser:
            return SyntaxNode(type='program', value=None, line=1, column=0, end_line=1, end_column=0)

        tree = parser.parse(code.encode())

        def build_node(ts_node, parent=None) -> SyntaxNode:
            node = SyntaxNode(
                type=ts_node.type,
                value=code[ts_node.start_byte:ts_node.end_byte].decode('utf-8') if ts_node.is_leaf else None,
                line=ts_node.start_point[0] + 1,
                column=ts_node.start_point[1],
                end_line=ts_node.end_point[0] + 1,
                end_column=ts_node.end_point[1],
                parent=parent,
                children=[]
            )

            for child in ts_node.children:
                node.children.append(build_node(child, node))

            return node

        return build_node(tree.root_node)

    def query(self, code: str, query_pattern: str, language: Optional[LanguageSupport] = None) -> List[Dict[str, Any]]:
        """执行语法查询"""
        if not TREE_SITTER_AVAILABLE:
            return []

        lang = language or self._language or LanguageSupport.PYTHON
        parser = self._get_parser(lang)
        if not parser:
            return []

        tree = parser.parse(code.encode())

        try:
            ts_language = self._load_language(lang.value)
            if not ts_language:
                return []

            query = ts_language.query(query_pattern)
            matches = query.matches(tree.root_node)

            results = []
            for match in matches:
                captures = {}
                for capture in match.captures:
                    node = capture.node
                    captures[capture.name] = {
                        'type': node.type,
                        'value': code[node.start_byte:node.end_byte].decode('utf-8'),
                        'line': node.start_point[0] + 1,
                        'column': node.start_point[1],
                        'end_line': node.end_point[0] + 1,
                        'end_column': node.end_point[1]
                    }
                results.append(captures)

            return results
        except Exception:
            return []


def get_tree_sitter_parser(language: Optional[LanguageSupport] = None) -> TreeSitterParser:
    """获取 Tree-sitter 解析器实例"""
    return TreeSitterParser(language)