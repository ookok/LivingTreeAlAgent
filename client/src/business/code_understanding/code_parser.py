"""
代码解析器 - 基于 Tree-sitter 的语法分析

核心功能：
1. 支持多种编程语言
2. 语法树解析
3. 代码结构提取
4. 符号分析
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
from pathlib import Path


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


@dataclass
class SymbolInfo:
    """符号信息"""
    name: str
    type: str  # function, class, variable, method, etc.
    line: int
    column: int
    end_line: int
    end_column: int
    scope: Optional[str] = None
    docstring: Optional[str] = None


@dataclass
class CodeStructure:
    """代码结构"""
    language: LanguageSupport
    symbols: List[SymbolInfo]
    imports: List[str]
    classes: List[SymbolInfo]
    functions: List[SymbolInfo]
    variables: List[SymbolInfo]


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


class CodeParser:
    """
    代码解析器 - 基于正则和启发式分析的轻量级实现
    
    核心特性：
    1. 多语言支持
    2. 符号提取
    3. 代码结构分析
    4. 语法树构建
    """

    def __init__(self, language: Optional[LanguageSupport] = None):
        self._language = language
        self._parsers = {
            LanguageSupport.PYTHON: self._parse_python,
            LanguageSupport.JAVASCRIPT: self._parse_javascript,
            LanguageSupport.TYPESCRIPT: self._parse_typescript,
            LanguageSupport.JAVA: self._parse_java,
            LanguageSupport.GO: self._parse_go,
            LanguageSupport.RUST: self._parse_rust,
            LanguageSupport.C: self._parse_c,
            LanguageSupport.CPP: self._parse_cpp,
            LanguageSupport.VUE: self._parse_vue,
            LanguageSupport.HTML: self._parse_html,
            LanguageSupport.CSS: self._parse_css,
            LanguageSupport.SQL: self._parse_sql
        }

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
            '.sql': LanguageSupport.SQL
        }
        
        return ext_map.get(ext, LanguageSupport.PYTHON)

    def parse(self, code: str, language: Optional[LanguageSupport] = None) -> CodeStructure:
        """解析代码"""
        lang = language or self._language or LanguageSupport.PYTHON
        
        parser = self._parsers.get(lang)
        if parser:
            return parser(code)
        
        return self._parse_generic(code)

    def _parse_python(self, code: str) -> CodeStructure:
        """解析Python代码"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []
        
        lines = code.split('\n')
        current_scope = None
        indent_level = 0
        
        for i, line in enumerate(lines, 1):
            # 检测导入
            import_match = re.match(r'^(from\s+\w+\s+)?import\s+(\w+)', line)
            if import_match:
                imports.append(import_match.group(2))
                continue
            
            # 检测类定义
            class_match = re.match(r'^class\s+(\w+)\s*[:(]', line)
            if class_match:
                name = class_match.group(1)
                symbol = SymbolInfo(
                    name=name,
                    type='class',
                    line=i,
                    column=line.index('class'),
                    end_line=i,
                    end_column=len(line),
                    scope=None
                )
                symbols.append(symbol)
                classes.append(symbol)
                current_scope = name
                indent_level = len(line) - len(line.lstrip())
                continue
            
            # 检测函数定义
            func_match = re.match(r'^(async\s+)?def\s+(\w+)\s*\(', line)
            if func_match:
                name = func_match.group(2)
                symbol = SymbolInfo(
                    name=name,
                    type='function' if not func_match.group(1) else 'async_function',
                    line=i,
                    column=line.index('def'),
                    end_line=i,
                    end_column=len(line),
                    scope=current_scope
                )
                symbols.append(symbol)
                functions.append(symbol)
                continue
            
            # 检测变量定义（简化版）
            var_match = re.match(r'^(\w+)\s*=', line)
            if var_match and not re.match(r'^(class|def|import|from|return|if|elif|else|for|while|with|try|except|raise|yield|lambda)', line):
                name = var_match.group(1)
                symbol = SymbolInfo(
                    name=name,
                    type='variable',
                    line=i,
                    column=0,
                    end_line=i,
                    end_column=len(line),
                    scope=current_scope
                )
                symbols.append(symbol)
                variables.append(symbol)
        
        return CodeStructure(
            language=LanguageSupport.PYTHON,
            symbols=symbols,
            imports=imports,
            classes=classes,
            functions=functions,
            variables=variables
        )

    def _parse_javascript(self, code: str) -> CodeStructure:
        """解析JavaScript代码"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []
        
        lines = code.split('\n')
        current_scope = None
        
        for i, line in enumerate(lines, 1):
            # 检测导入
            import_match = re.match(r'^(import|export)\s+\w+', line)
            if import_match:
                imports.append(line.split()[1])
                continue
            
            # 检测类定义
            class_match = re.match(r'^class\s+(\w+)', line)
            if class_match:
                name = class_match.group(1)
                symbol = SymbolInfo(
                    name=name,
                    type='class',
                    line=i,
                    column=line.index('class'),
                    end_line=i,
                    end_column=len(line)
                )
                symbols.append(symbol)
                classes.append(symbol)
                current_scope = name
                continue
            
            # 检测函数定义
            func_match = re.match(r'^(async\s+)?function\s+(\w+)\s*\(', line)
            if func_match:
                name = func_match.group(2)
                symbol = SymbolInfo(
                    name=name,
                    type='function',
                    line=i,
                    column=line.index('function'),
                    end_line=i,
                    end_column=len(line),
                    scope=current_scope
                )
                symbols.append(symbol)
                functions.append(symbol)
                continue
            
            # 检测箭头函数和变量声明
            arrow_match = re.match(r'^(const|let|var)\s+(\w+)\s*=', line)
            if arrow_match:
                name = arrow_match.group(2)
                symbol = SymbolInfo(
                    name=name,
                    type='variable',
                    line=i,
                    column=0,
                    end_line=i,
                    end_column=len(line),
                    scope=current_scope
                )
                symbols.append(symbol)
                variables.append(symbol)
        
        return CodeStructure(
            language=LanguageSupport.JAVASCRIPT,
            symbols=symbols,
            imports=imports,
            classes=classes,
            functions=functions,
            variables=variables
        )

    def _parse_typescript(self, code: str) -> CodeStructure:
        """解析TypeScript代码"""
        # TypeScript 与 JavaScript 类似，增加类型信息处理
        result = self._parse_javascript(code)
        result.language = LanguageSupport.TYPESCRIPT
        return result

    def _parse_java(self, code: str) -> CodeStructure:
        """解析Java代码"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []
        
        lines = code.split('\n')
        current_scope = None
        
        for i, line in enumerate(lines, 1):
            # 检测导入
            import_match = re.match(r'^import\s+(\w+)', line)
            if import_match:
                imports.append(import_match.group(1))
                continue
            
            # 检测类定义
            class_match = re.match(r'^(public\s+)?class\s+(\w+)', line)
            if class_match:
                name = class_match.group(2)
                symbol = SymbolInfo(
                    name=name,
                    type='class',
                    line=i,
                    column=line.index('class'),
                    end_line=i,
                    end_column=len(line)
                )
                symbols.append(symbol)
                classes.append(symbol)
                current_scope = name
                continue
            
            # 检测方法定义
            method_match = re.match(r'^(public|private|protected)\s+(\w+)\s+(\w+)\s*\(', line)
            if method_match:
                name = method_match.group(3)
                symbol = SymbolInfo(
                    name=name,
                    type='method',
                    line=i,
                    column=0,
                    end_line=i,
                    end_column=len(line),
                    scope=current_scope
                )
                symbols.append(symbol)
                functions.append(symbol)
                continue
        
        return CodeStructure(
            language=LanguageSupport.JAVA,
            symbols=symbols,
            imports=imports,
            classes=classes,
            functions=functions,
            variables=variables
        )

    def _parse_go(self, code: str) -> CodeStructure:
        """解析Go代码"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []
        
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            # 检测导入
            if line.startswith('import'):
                imports.append('go')
                continue
            
            # 检测函数定义
            func_match = re.match(r'^func\s+(\w+)\s*\(', line)
            if func_match:
                name = func_match.group(1)
                symbol = SymbolInfo(
                    name=name,
                    type='function',
                    line=i,
                    column=line.index('func'),
                    end_line=i,
                    end_column=len(line)
                )
                symbols.append(symbol)
                functions.append(symbol)
                continue
            
            # 检测方法定义
            method_match = re.match(r'^func\s+\(\w+\s+\*?(\w+)\)\s+(\w+)\s*\(', line)
            if method_match:
                name = method_match.group(2)
                symbol = SymbolInfo(
                    name=name,
                    type='method',
                    line=i,
                    column=line.index('func'),
                    end_line=i,
                    end_column=len(line),
                    scope=method_match.group(1)
                )
                symbols.append(symbol)
                functions.append(symbol)
                continue
        
        return CodeStructure(
            language=LanguageSupport.GO,
            symbols=symbols,
            imports=imports,
            classes=classes,
            functions=functions,
            variables=variables
        )

    def _parse_rust(self, code: str) -> CodeStructure:
        """解析Rust代码"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []
        
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            # 检测导入
            if line.startswith('use '):
                imports.append(line.split()[1])
                continue
            
            # 检测函数定义
            func_match = re.match(r'^fn\s+(\w+)\s*\(', line)
            if func_match:
                name = func_match.group(1)
                symbol = SymbolInfo(
                    name=name,
                    type='function',
                    line=i,
                    column=line.index('fn'),
                    end_line=i,
                    end_column=len(line)
                )
                symbols.append(symbol)
                functions.append(symbol)
                continue
            
            # 检测结构体
            struct_match = re.match(r'^struct\s+(\w+)', line)
            if struct_match:
                name = struct_match.group(1)
                symbol = SymbolInfo(
                    name=name,
                    type='struct',
                    line=i,
                    column=line.index('struct'),
                    end_line=i,
                    end_column=len(line)
                )
                symbols.append(symbol)
                classes.append(symbol)
                continue
            
            # 检测枚举
            enum_match = re.match(r'^enum\s+(\w+)', line)
            if enum_match:
                name = enum_match.group(1)
                symbol = SymbolInfo(
                    name=name,
                    type='enum',
                    line=i,
                    column=line.index('enum'),
                    end_line=i,
                    end_column=len(line)
                )
                symbols.append(symbol)
                classes.append(symbol)
                continue
        
        return CodeStructure(
            language=LanguageSupport.RUST,
            symbols=symbols,
            imports=imports,
            classes=classes,
            functions=functions,
            variables=variables
        )

    def _parse_c(self, code: str) -> CodeStructure:
        """解析C代码"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []
        
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            # 检测包含
            if line.startswith('#include'):
                imports.append(line.split()[1])
                continue
            
            # 检测函数定义
            func_match = re.match(r'^(\w+\s+)*(\w+)\s*\(', line)
            if func_match and not line.strip().startswith('//'):
                name = func_match.group(2)
                if name not in ['if', 'while', 'for', 'return', 'switch', 'case']:
                    symbol = SymbolInfo(
                        name=name,
                        type='function',
                        line=i,
                        column=0,
                        end_line=i,
                        end_column=len(line)
                    )
                    symbols.append(symbol)
                    functions.append(symbol)
        
        return CodeStructure(
            language=LanguageSupport.C,
            symbols=symbols,
            imports=imports,
            classes=classes,
            functions=functions,
            variables=variables
        )

    def _parse_cpp(self, code: str) -> CodeStructure:
        """解析C++代码"""
        result = self._parse_c(code)
        
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            # 检测类定义
            class_match = re.match(r'^class\s+(\w+)', line)
            if class_match:
                name = class_match.group(1)
                symbol = SymbolInfo(
                    name=name,
                    type='class',
                    line=i,
                    column=line.index('class'),
                    end_line=i,
                    end_column=len(line)
                )
                result.symbols.append(symbol)
                result.classes.append(symbol)
        
        result.language = LanguageSupport.CPP
        return result

    def _parse_vue(self, code: str) -> CodeStructure:
        """解析Vue代码"""
        symbols = []
        imports = []
        classes = []
        functions = []
        variables = []
        
        # 提取script部分
        script_match = re.search(r'<script[^>]*>(.*?)</script>', code, re.DOTALL)
        if script_match:
            script_content = script_match.group(1)
            js_result = self._parse_javascript(script_content)
            symbols.extend(js_result.symbols)
            imports.extend(js_result.imports)
            classes.extend(js_result.classes)
            functions.extend(js_result.functions)
            variables.extend(js_result.variables)
        
        return CodeStructure(
            language=LanguageSupport.VUE,
            symbols=symbols,
            imports=imports,
            classes=classes,
            functions=functions,
            variables=variables
        )

    def _parse_html(self, code: str) -> CodeStructure:
        """解析HTML代码"""
        symbols = []
        tags = re.findall(r'<(\w+)[^>]*>', code)
        
        for tag in tags:
            if tag not in ['html', 'head', 'body', 'div', 'span']:
                symbol = SymbolInfo(
                    name=tag,
                    type='html_tag',
                    line=1,
                    column=0,
                    end_line=1,
                    end_column=0
                )
                symbols.append(symbol)
        
        return CodeStructure(
            language=LanguageSupport.HTML,
            symbols=symbols,
            imports=[],
            classes=[],
            functions=[],
            variables=[]
        )

    def _parse_css(self, code: str) -> CodeStructure:
        """解析CSS代码"""
        symbols = []
        selectors = re.findall(r'^([^{]+)\s*{', code, re.MULTILINE)
        
        for selector in selectors:
            selector = selector.strip()
            if selector and not selector.startswith('/*'):
                symbol = SymbolInfo(
                    name=selector,
                    type='css_selector',
                    line=1,
                    column=0,
                    end_line=1,
                    end_column=0
                )
                symbols.append(symbol)
        
        return CodeStructure(
            language=LanguageSupport.CSS,
            symbols=symbols,
            imports=[],
            classes=[],
            functions=[],
            variables=[]
        )

    def _parse_sql(self, code: str) -> CodeStructure:
        """解析SQL代码"""
        symbols = []
        tables = []
        
        # 检测表名
        table_patterns = [
            r'FROM\s+(\w+)',
            r'INTO\s+(\w+)',
            r'CREATE\s+TABLE\s+(\w+)',
            r'ALTER\s+TABLE\s+(\w+)',
            r'DROP\s+TABLE\s+(\w+)',
            r'UPDATE\s+(\w+)'
        ]
        
        for pattern in table_patterns:
            matches = re.findall(pattern, code, re.IGNORECASE)
            for table in matches:
                if table not in tables:
                    tables.append(table)
                    symbol = SymbolInfo(
                        name=table,
                        type='table',
                        line=1,
                        column=0,
                        end_line=1,
                        end_column=0
                    )
                    symbols.append(symbol)
        
        return CodeStructure(
            language=LanguageSupport.SQL,
            symbols=symbols,
            imports=[],
            classes=[],
            functions=[],
            variables=[]
        )

    def _parse_generic(self, code: str) -> CodeStructure:
        """通用解析器"""
        symbols = []
        
        # 简单的标识符检测
        identifiers = re.findall(r'\b([a-zA-Z_]\w*)\b', code)
        
        for name in identifiers[:50]:
            if len(name) > 2:
                symbol = SymbolInfo(
                    name=name,
                    type='identifier',
                    line=1,
                    column=0,
                    end_line=1,
                    end_column=0
                )
                symbols.append(symbol)
        
        return CodeStructure(
            language=LanguageSupport.PYTHON,
            symbols=symbols,
            imports=[],
            classes=[],
            functions=[],
            variables=[]
        )

    def extract_docstring(self, code: str, line_number: int) -> Optional[str]:
        """提取指定行附近的文档字符串"""
        lines = code.split('\n')
        
        # 向上查找文档字符串
        for i in range(max(0, line_number - 10), line_number):
            if i < len(lines):
                line = lines[i]
                if '"""' in line or "'''" in line:
                    # 尝试提取多行文档字符串
                    start = i
                    end = i
                    quote_type = '"""' if '"""' in line else "'''"
                    
                    if line.count(quote_type) >= 2:
                        return line.split(quote_type)[1].strip()
                    
                    # 查找结束
                    for j in range(i + 1, min(len(lines), i + 20)):
                        if quote_type in lines[j]:
                            end = j
                            break
                    
                    docstring = '\n'.join(lines[start:end + 1])
                    return docstring.split(quote_type)[1].strip()
        
        return None

    def build_syntax_tree(self, code: str) -> SyntaxNode:
        """构建简化的语法树"""
        lines = code.split('\n')
        root = SyntaxNode(
            type='program',
            value=None,
            line=1,
            column=0,
            end_line=len(lines),
            end_column=0
        )
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            
            if line.startswith('def ') or line.startswith('class '):
                node_type = 'function' if line.startswith('def') else 'class'
                name = line.split()[1].split('(')[0] if 'def' in line else line.split()[1].split(':')[0]
                
                child = SyntaxNode(
                    type=node_type,
                    value=name,
                    line=i,
                    column=0,
                    end_line=i,
                    end_column=len(line)
                )
                root.children.append(child)
        
        return root


def get_code_parser(language: Optional[LanguageSupport] = None) -> CodeParser:
    """获取代码解析器实例"""
    return CodeParser(language)