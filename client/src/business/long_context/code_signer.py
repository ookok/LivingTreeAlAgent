# -*- coding: utf-8 -*-
"""
代码签名化模块 - Code Signer
============================

核心设计理念：用 1% 的 Token 传递 99% 的意图

代码签名化 = 保留函数签名 + 目的 + 依赖，丢弃实现细节

压缩策略：
| 内容类型 | 保留比例 | 压缩比 | 说明 |
|---------|---------|--------|------|
| 函数签名 | 100% | 1:1 | def xxx(args) -> Type |
| 类型定义 | 100% | 1:1 | class/interface/enum |
| 导入声明 | 100% | 1:1 | import/from ... |
| 变量声明 | 80% | 1.2:1 | 类型化的变量 |
| 文档字符串 | 30% | 3:1 | docstring（保留摘要） |
| 实现逻辑 | 5% | 20:1 | 函数体 → 摘要 |
| 注释 | 0% | ∞ | 完全删除 |
| 空白 | 0% | ∞ | 删除 |

Author: Hermes Desktop Team
Date: 2026-04-24
"""

from __future__ import annotations

import re
import ast
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json

logger = __import__('logging').getLogger(__name__)


class CodeElementType(Enum):
    """代码元素类型"""
    FUNCTION = "function"          # 函数/方法
    CLASS = "class"                # 类
    INTERFACE = "interface"        # 接口
    ENUM = "enum"                  # 枚举
    VARIABLE = "variable"          # 变量
    CONSTANT = "constant"          # 常量
    IMPORT = "import"              # 导入
    TYPE_ALIAS = "type_alias"      # 类型别名
    DECORATOR = "decorator"        # 装饰器
    COMMENT = "comment"            # 注释
    BLANK = "blank"                # 空白


@dataclass
class CodeElement:
    """代码元素"""
    element_type: CodeElementType
    name: str
    signature: str                    # 签名（保留）
    docstring: str                    # 文档（可压缩）
    body_summary: str                 # 函数体摘要
    dependencies: List[str] = field(default_factory=list)  # 依赖
    decorators: List[str] = field(default_factory=list)    # 装饰器
    return_type: str = ""             # 返回类型
    parameters: List[str] = field(default_factory=list)   # 参数
    line_start: int = 0
    line_end: int = 0
    complexity: int = 1               # 圈复杂度
    is_public: bool = True            # 是否公开API


@dataclass
class SignatureResult:
    """签名化结果"""
    original_code: str
    signature_code: str
    original_lines: int
    signature_lines: int
    original_size: int
    signature_size: int
    elements: List[CodeElement]
    compression_ratio: float
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    
    @property
    def saved_ratio(self) -> float:
        """节省比例"""
        return 1 - self.compression_ratio
    
    @property
    def summary(self) -> Dict[str, Any]:
        """摘要"""
        return {
            "compression_ratio": f"{self.compression_ratio:.1%}",
            "saved_ratio": f"{self.saved_ratio:.1%}",
            "lines_saved": self.original_lines - self.signature_lines,
            "size_saved": self.original_size - self.signature_size,
            "elements": len(self.elements),
            "functions": sum(1 for e in self.elements if e.element_type == CodeElementType.FUNCTION),
            "classes": sum(1 for e in self.elements if e.element_type == CodeElementType.CLASS),
        }


class PythonSignatureExtractor:
    """Python 代码签名提取器"""
    
    # 保留关键字
    KEYWORDS = {
        'def', 'class', 'return', 'if', 'else', 'elif', 'for', 'while', 'try',
        'except', 'finally', 'with', 'as', 'import', 'from', 'raise', 'pass',
        'break', 'continue', 'and', 'or', 'not', 'in', 'is', 'lambda', 'yield',
        'global', 'nonlocal', 'assert', 'del', 'async', 'await'
    }
    
    # 简单函数体关键词（这些函数体可以高度压缩）
    TRIVIAL_PATTERNS = [
        r'^\s*return\s+None\s*$',
        r'^\s*pass\s*$',
        r'^\s*...\s*$',
        r'^\s*return\s+\w+\s*$',
        r'^\s*raise\s+NotImplementedError\s*$',
        r'^\s*raise\s+NotImplementedError\(.*\)\s*$',
    ]
    
    def __init__(self):
        self.elements: List[CodeElement] = []
        self.imports: List[str] = []
        self.exports: List[str] = []
        self._current_scope: List[str] = []
    
    def extract(self, code: str) -> SignatureResult:
        """提取签名"""
        try:
            tree = ast.parse(code)
            self._process_tree(tree)
            signature_code = self._generate_signature()
            
            original_lines = len(code.splitlines())
            signature_lines = len(signature_code.splitlines())
            
            return SignatureResult(
                original_code=code,
                signature_code=signature_code,
                original_lines=original_lines,
                signature_lines=signature_lines,
                original_size=len(code),
                signature_size=len(signature_code),
                elements=self.elements,
                compression_ratio=len(signature_code) / len(code) if code else 1.0,
                imports=self.imports,
                exports=self.exports,
            )
        except SyntaxError as e:
            logger.warning(f"Python 语法解析失败: {e}")
            return self._fallback_extract(code)
    
    def _process_tree(self, tree: ast.AST):
        """处理 AST"""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports.append(f"import {alias.name}" + 
                        (f" as {alias.asname}" if alias.asname else ""))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    self.imports.append(f"from {module} import {alias.name}" +
                        (f" as {alias.asname}" if alias.asname else ""))
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                self._process_function(node)
            elif isinstance(node, ast.ClassDef):
                self._process_class(node)
    
    def _process_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> CodeElement:
        """处理函数"""
        name = node.name
        
        # 提取签名
        args = self._format_args(node.args)
        returns = self._format_returns(node.returns)
        signature = f"def {name}({args})" + (f" -> {returns}" if returns else "")
        
        # 提取装饰器
        decorators = []
        for dec in node.decorator_list:
            dec_str = ast.unparse(dec)
            decorators.append(dec_str)
            if dec_str == 'property':
                signature = f"@property\n    {signature}"
        
        # 提取文档
        docstring = ast.get_docstring(node) or ""
        doc_summary = self._summarize_docstring(docstring)
        
        # 生成函数体摘要
        body_summary = self._summarize_body(node)
        
        # 计算复杂度（简化版）
        complexity = self._estimate_complexity(node)
        
        # 提取依赖
        dependencies = self._extract_dependencies(node)
        
        # 判断是否公开
        is_public = not name.startswith('_')
        
        # 检查参数类型提示
        params = []
        for arg in node.args.args:
            param_type = ""
            if arg.annotation:
                param_type = ast.unparse(arg.annotation)
            param_name = arg.arg
            if param_type:
                params.append(f"{param_name}: {param_type}")
            else:
                params.append(param_name)
        
        element = CodeElement(
            element_type=CodeElementType.FUNCTION,
            name=name,
            signature=signature,
            docstring=doc_summary,
            body_summary=body_summary,
            dependencies=dependencies,
            decorators=decorators,
            return_type=returns,
            parameters=params,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            complexity=complexity,
            is_public=is_public,
        )
        
        self.elements.append(element)
        return element
    
    def _process_class(self, node: ast.ClassDef) -> CodeElement:
        """处理类"""
        name = node.name
        
        # 基类
        bases = [ast.unparse(base) for base in node.bases]
        for base in node.decorator_list:
            bases.append(ast.unparse(base))
        
        signature = f"class {name}" + (f"({', '.join(bases)})" if bases else "")
        
        # 提取文档
        docstring = ast.get_docstring(node) or ""
        doc_summary = self._summarize_docstring(docstring)
        
        # 处理类的方法
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not item.name.startswith('_') or item.name in ('__init__', '__str__', '__repr__'):
                    m = self._process_function(item)
                    methods.append(m)
        
        # 类摘要
        body_summary = f"包含 {len(methods)} 个方法: " + ", ".join([m.name for m in methods[:5]])
        if len(methods) > 5:
            body_summary += f" 等"
        
        # 提取类属性
        attributes = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                attr_type = ast.unparse(item.annotation) if item.annotation else ""
                attributes.append(f"{item.target.id}: {attr_type}" if attr_type else item.target.id)
        
        # 装饰器
        decorators = [ast.unparse(dec) for dec in node.decorator_list]
        
        is_public = not name.startswith('_')
        
        element = CodeElement(
            element_type=CodeElementType.CLASS,
            name=name,
            signature=signature,
            docstring=doc_summary,
            body_summary=body_summary,
            dependencies=[],  # 类暂不提取依赖
            decorators=decorators,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            is_public=is_public,
        )
        
        self.elements.append(element)
        
        # 处理完类后，还要把方法加到全局列表
        for m in methods:
            if m not in self.elements:
                self.elements.append(m)
        
        return element
    
    def _format_args(self, args: ast.arguments) -> str:
        """格式化参数"""
        parts = []
        
        # 普通参数
        for arg in args.args:
            annotation = ast.unparse(arg.annotation) if arg.annotation else ""
            name = arg.arg
            if annotation:
                parts.append(f"{name}: {annotation}")
            else:
                parts.append(name)
        
        # *args
        if args.vararg:
            annotation = ast.unparse(args.vararg.annotation) if args.vararg.annotation else ""
            parts.append(f"*{args.vararg.arg}" + (f": {annotation}" if annotation else ""))
        
        # **kwargs
        if args.kwarg:
            annotation = ast.unparse(args.kwarg.annotation) if args.kwarg.annotation else ""
            parts.append(f"**{args.kwarg.arg}" + (f": {annotation}" if annotation else ""))
        
        return ", ".join(parts)
    
    def _format_returns(self, returns: Optional[ast.AST]) -> str:
        """格式化返回类型"""
        if returns:
            return ast.unparse(returns)
        return ""
    
    def _summarize_docstring(self, docstring: str) -> str:
        """摘要化文档字符串"""
        if not docstring:
            return ""
        
        lines = [l.strip() for l in docstring.split('\n') if l.strip()]
        if not lines:
            return ""
        
        # 保留第一段（通常是摘要）
        summary = lines[0]
        
        # 如果有 Args 或 Returns，说明用途
        has_details = any('Args:' in l or 'Returns:' in l or 'Raises:' in l 
                         for l in lines[1:5])
        if has_details:
            summary += " [详细文档见原文]"
        
        return summary[:200]  # 限制长度
    
    def _summarize_body(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """生成函数体摘要"""
        # 检查是否简单函数
        body_text = '\n'.join(ast.unparse(stmt) for stmt in node.body if not isinstance(stmt, (ast.Pass, ast.Constant)))
        
        for pattern in self.TRIVIAL_PATTERNS:
            if re.match(pattern, body_text.strip()):
                return "[简单实现]"
        
        # 统计关键操作
        operations = []
        
        # 循环
        loops = sum(1 for stmt in ast.walk(node) if isinstance(stmt, (ast.For, ast.While)))
        if loops > 0:
            operations.append(f"{loops}个循环")
        
        # 条件
        ifs = sum(1 for stmt in ast.walk(node) if isinstance(stmt, ast.If))
        if ifs > 0:
            operations.append(f"{ifs}个条件")
        
        # 异常
        try_blocks = sum(1 for stmt in ast.walk(node) if isinstance(stmt, ast.Try))
        if try_blocks > 0:
            operations.append("异常处理")
        
        # 返回
        returns = sum(1 for stmt in ast.walk(node) if isinstance(stmt, ast.Return))
        if returns > 0:
            operations.append("有返回")
        
        # yield
        yields = sum(1 for stmt in ast.walk(node) if isinstance(stmt, (ast.Yield, ast.YieldFrom)))
        if yields > 0:
            operations.append("生成器")
        
        if operations:
            return "[逻辑: " + ", ".join(operations) + "]"
        
        return "[有实现]"
    
    def _estimate_complexity(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        """估计圈复杂度"""
        complexity = 1
        
        for stmt in ast.walk(node):
            if isinstance(stmt, (ast.If, ast.While, ast.For)):
                complexity += 1
            elif isinstance(stmt, ast.BoolOp):
                complexity += len(stmt.values) - 1
        
        return complexity
    
    def _extract_dependencies(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
        """提取依赖"""
        deps = set()
        
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Call):
                if isinstance(stmt.func, ast.Name):
                    deps.add(stmt.func.id)
                elif isinstance(stmt.func, ast.Attribute):
                    deps.add(stmt.func.attr)
        
        return list(deps)[:10]  # 限制数量
    
    def _generate_signature(self) -> str:
        """生成签名代码"""
        lines = []
        
        # 导入
        for imp in self.imports:
            lines.append(imp)
        
        if self.imports:
            lines.append("")
        
        # 元素
        for elem in self.elements:
            if elem.element_type == CodeElementType.CLASS:
                # 类
                if elem.docstring:
                    lines.append(f'\"\"\"{elem.docstring}\"\"\"')
                if elem.decorators:
                    for dec in elem.decorators:
                        lines.append(f"@{dec}")
                lines.append(elem.signature)
                lines.append(f'    """摘要: {elem.body_summary}"""')
            elif elem.element_type == CodeElementType.FUNCTION:
                # 函数
                if elem.docstring:
                    lines.append(f'\"\"\"{elem.docstring}\"\"\"')
                if elem.decorators:
                    for dec in elem.decorators:
                        lines.append(f"@{dec}")
                lines.append(f"    {elem.signature}")
                if elem.body_summary and elem.body_summary != "[简单实现]":
                    lines.append(f'    """摘要: {elem.body_summary}"""')
                lines.append("    ...")
        
        return '\n'.join(lines)
    
    def _fallback_extract(self, code: str) -> SignatureResult:
        """回退提取（语法错误时）"""
        # 简单的正则提取
        functions = re.findall(r'def (\w+)\s*\([^)]*\)(?:\s*->\s*[^:]+)?:', code)
        classes = re.findall(r'class (\w+)(?:\([^)]*\))?:', code)
        imports = re.findall(r'^(?:from\s+[\w.]+\s+)?import\s+.+$', code, re.MULTILINE)
        
        signature_lines = []
        for imp in imports:
            signature_lines.append(imp)
        signature_lines.append("")
        
        for cls in classes:
            signature_lines.append(f"class {cls}:")
            signature_lines.append("    ...")
        signature_lines.append("")
        
        for func in functions:
            signature_lines.append(f"def {func}(...): ...")
        
        signature_code = '\n'.join(signature_lines)
        
        return SignatureResult(
            original_code=code,
            signature_code=signature_code,
            original_lines=len(code.splitlines()),
            signature_lines=len(signature_code.splitlines()),
            original_size=len(code),
            signature_size=len(signature_code),
            elements=[],
            compression_ratio=len(signature_code) / len(code) if code else 1.0,
            imports=imports,
            exports=classes,
        )


class CodeSigner:
    """
    代码签名化器
    
    将代码文件转换为签名表示，大幅减少 token 消耗。
    """
    
    def __init__(self, 
                 preserve_imports: bool = True,
                 preserve_types: bool = True,
                 preserve_public_only: bool = False,
                 preserve_private_threshold: int = 50):
        """
        Args:
            preserve_imports: 保留导入语句
            preserve_types: 保留类型定义
            preserve_public_only: 只保留公开 API
            preserve_private_threshold: 私有函数超过此行数才保留
        """
        self.preserve_imports = preserve_imports
        self.preserve_types = preserve_types
        self.preserve_public_only = preserve_public_only
        self.preserve_private_threshold = preserve_private_threshold
        self.extractors: Dict[str, PythonSignatureExtractor] = {}
    
    def signaturize(self, code: str, language: str = "python") -> SignatureResult:
        """
        签名化代码
        
        Args:
            code: 原始代码
            language: 编程语言
        
        Returns:
            SignatureResult: 签名化结果
        """
        if language.lower() == "python":
            extractor = PythonSignatureExtractor()
            return extractor.extract(code)
        else:
            # 暂时只支持 Python
            logger.warning(f"暂不支持 {language} 的签名化")
            return self._plain_signaturize(code)
    
    def _plain_signaturize(self, code: str) -> SignatureResult:
        """纯文本签名化"""
        lines = code.split('\n')
        signature_lines = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('#'):
                continue  # 跳过注释
            if stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            
            # 保留函数/类定义
            if re.match(r'^(def|class|async def)\s+\w+', stripped):
                signature_lines.append(line)
            # 保留导入
            elif re.match(r'^(from|import)\s+', stripped):
                signature_lines.append(line)
            
            signature_lines.append("...")
        
        signature_code = '\n'.join(signature_lines)
        
        return SignatureResult(
            original_code=code,
            signature_code=signature_code,
            original_lines=len(lines),
            signature_lines=len(signature_lines),
            original_size=len(code),
            signature_size=len(signature_code),
            elements=[],
            compression_ratio=len(signature_code) / len(code) if code else 1.0,
        )
    
    def batch_signaturize(self, files: Dict[str, str]) -> Dict[str, SignatureResult]:
        """
        批量签名化
        
        Args:
            files: {文件名: 代码内容}
        
        Returns:
            {文件名: 签名结果}
        """
        results = {}
        
        for filename, code in files.items():
            ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''
            language = self._ext_to_language(ext)
            results[filename] = self.signaturize(code, language)
        
        return results
    
    def _ext_to_language(self, ext: str) -> str:
        """扩展名转语言"""
        mapping = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'java': 'java',
            'go': 'go',
            'rs': 'rust',
            'cpp': 'cpp',
            'c': 'c',
            'h': 'c',
            'hpp': 'cpp',
        }
        return mapping.get(ext.lower(), 'unknown')
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "preserve_imports": self.preserve_imports,
            "preserve_types": self.preserve_types,
            "preserve_public_only": self.preserve_public_only,
        }


def signaturize_code(code: str, language: str = "python") -> SignatureResult:
    """
    便捷签名化函数
    
    Args:
        code: 原始代码
        language: 编程语言
    
    Returns:
        SignatureResult: 签名化结果
    """
    signer = CodeSigner()
    return signer.signaturize(code, language)
