# -*- coding: utf-8 -*-
"""
分层上下文金字塔 - Layered Context Pyramid
==========================================

核心设计理念：按需加载，用多少加载多少

层级结构：
| 层级 | 内容 | Token预算 | 用途 |
|------|------|-----------|------|
| L1 | 文件概览 | 64 | 快速定位 |
| L2 | 符号索引 | 256 | 精确查找 |
| L3 | 相关代码 | 1024 | 理解上下文 |
| L4 | 完整实现 | 4096 | 深度修改 |
| L5 | 全部代码 | 16K+ | 全局重构 |

核心原则："足够好" 而非 "完美"
- 等待30秒的AI → 被用户抛弃
- 3秒响应的AI → 用户体验更佳

Author: Hermes Desktop Team
Date: 2026-04-24
"""

from __future__ import annotations

import os
import re
import ast
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import hashlib

logger = __import__('logging').getLogger(__name__)


class ContextLevel(Enum):
    """上下文层级"""
    L1_FILE_OVERVIEW = 1    # 文件概览
    L2_SYMBOL_INDEX = 2     # 符号索引
    L3_RELATED_CODE = 3     # 相关代码
    L4_COMPLETE_IMPL = 4    # 完整实现
    L5_FULL_CODE = 5        # 全部代码


@dataclass
class TokenBudget:
    """Token 预算"""
    level: ContextLevel
    max_tokens: int
    
    # 典型中文的 token/char 比例约 1.5-2.0
    @property
    def max_chars(self) -> int:
        return int(self.max_tokens / 1.8)
    
    # 预留空间（Prompt 模板、角色设定等）
    RESERVED_RATIO = 0.2
    
    @property
    def available_chars(self) -> int:
        return int(self.max_chars * (1 - self.RESERVED_RATIO))


# 层级预算配置
LEVEL_BUDGETS = {
    ContextLevel.L1_FILE_OVERVIEW: TokenBudget(ContextLevel.L1_FILE_OVERVIEW, 64),
    ContextLevel.L2_SYMBOL_INDEX: TokenBudget(ContextLevel.L2_SYMBOL_INDEX, 256),
    ContextLevel.L3_RELATED_CODE: TokenBudget(ContextLevel.L3_RELATED_CODE, 1024),
    ContextLevel.L4_COMPLETE_IMPL: TokenBudget(ContextLevel.L4_COMPLETE_IMPL, 4096),
    ContextLevel.L5_FULL_CODE: TokenBudget(ContextLevel.L5_FULL_CODE, 16384),
}


@dataclass
class Symbol:
    """代码符号"""
    name: str
    kind: str                      # function, class, method, variable, etc.
    file_path: str
    line_start: int
    line_end: int
    signature: str                  # 签名
    docstring: str = ""             # 文档
    is_public: bool = True
    parent: str = ""                # 父符号（类名等）
    children: List[str] = field(default_factory=list)  # 子符号
    complexity: int = 1             # 圈复杂度
    references: List[str] = field(default_factory=list)  # 引用的符号


@dataclass
class FileIndex:
    """文件索引"""
    file_path: str
    language: str
    symbols: List[Symbol] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    dependencies: Set[str] = field(default_factory=set)  # 依赖的其他文件
    dependents: Set[str] = field(default_factory=set)    # 依赖此文件的文件
    
    @property
    def symbol_count(self) -> int:
        return len(self.symbols)
    
    @property
    def public_symbols(self) -> List[Symbol]:
        return [s for s in self.symbols if s.is_public]


@dataclass
class ProjectIndex:
    """项目索引"""
    root_path: str
    files: Dict[str, FileIndex] = field(default_factory=dict)
    symbol_map: Dict[str, Symbol] = field(default_factory=dict)  # name -> Symbol
    
    def get_symbol(self, name: str) -> Optional[Symbol]:
        """获取符号"""
        return self.symbol_map.get(name)
    
    def get_file(self, path: str) -> Optional[FileIndex]:
        """获取文件索引"""
        return self.files.get(path)
    
    def find_symbols(self, query: str) -> List[Symbol]:
        """模糊搜索符号"""
        query_lower = query.lower()
        return [
            s for s in self.symbol_map.values()
            if query_lower in s.name.lower()
        ]


class SymbolIndex:
    """
    符号索引 - O(1) 查找替代全文 grep
    
    提供快速符号查找，而非逐文件搜索。
    """
    
    def __init__(self):
        self.project_index: Optional[ProjectIndex] = None
        self._build_cache: Dict[str, Any] = {}
    
    def build_from_project(self, root_path: str, file_patterns: List[str] = None) -> ProjectIndex:
        """
        从项目构建索引
        
        Args:
            root_path: 项目根目录
            file_patterns: 匹配的文件模式，如 ['*.py']
        """
        if file_patterns is None:
            file_patterns = ['*.py']
        
        self.project_index = ProjectIndex(root_path=root_path)
        
        # 遍历文件
        for root, dirs, files in os.walk(root_path):
            # 跳过隐藏目录和虚拟环境
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules', 'venv', '.venv')]
            
            for filename in files:
                if any(filename.endswith(p[1:]) if p.startswith('*') else filename == p for p in file_patterns):
                    filepath = os.path.join(root, filename)
                    self._index_file(filepath)
        
        # 构建依赖关系
        self._build_dependencies()
        
        return self.project_index
    
    def _index_file(self, filepath: str):
        """索引单个文件"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()
        except Exception as e:
            logger.warning(f"无法读取文件 {filepath}: {e}")
            return
        
        # 根据语言选择索引器
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.py':
            self._index_python_file(filepath, code)
        else:
            self._index_generic_file(filepath, code)
    
    def _index_python_file(self, filepath: str, code: str):
        """索引 Python 文件"""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            self._index_generic_file(filepath, code)
            return
        
        file_index = FileIndex(
            file_path=filepath,
            language='python'
        )
        
        # 提取导入
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    file_index.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    file_index.imports.append(f"{module}.{alias.name}")
        
        # 提取符号
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                symbol = self._extract_function_symbol(node, filepath)
                file_index.symbols.append(symbol)
                self.project_index.symbol_map[symbol.name] = symbol
            elif isinstance(node, ast.ClassDef):
                class_symbol = self._extract_class_symbol(node, filepath)
                file_index.symbols.append(class_symbol)
                self.project_index.symbol_map[class_symbol.name] = class_symbol
                
                # 类的方法
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_symbol = self._extract_function_symbol(item, filepath, class_symbol.name)
                        file_index.symbols.append(method_symbol)
                        self.project_index.symbol_map[f"{class_symbol.name}.{method_symbol.name}"] = method_symbol
        
        self.project_index.files[filepath] = file_index
    
    def _extract_function_symbol(self, node, filepath: str, parent: str = "") -> Symbol:
        """提取函数符号"""
        name = node.name
        
        # 签名
        args = []
        for arg in node.args.args:
            annotation = ast.unparse(arg.annotation) if arg.annotation else ""
            args.append(f"{arg.arg}: {annotation}" if annotation else arg.arg)
        
        returns = ast.unparse(node.returns) if node.returns else ""
        signature = f"def {name}({', '.join(args)})" + (f" -> {returns}" if returns else "")
        
        # 文档
        docstring = ast.get_docstring(node) or ""
        
        # 复杂度
        complexity = 1
        for stmt in ast.walk(node):
            if isinstance(stmt, (ast.If, ast.For, ast.While)):
                complexity += 1
        
        return Symbol(
            name=name,
            kind='function' if not parent else 'method',
            file_path=filepath,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            signature=signature,
            docstring=docstring[:200] if docstring else "",
            is_public=not name.startswith('_'),
            parent=parent,
            complexity=complexity,
        )
    
    def _extract_class_symbol(self, node, filepath: str) -> Symbol:
        """提取类符号"""
        name = node.name
        
        # 基类
        bases = [ast.unparse(b) for b in node.bases]
        signature = f"class {name}" + (f"({', '.join(bases)})" if bases else "")
        
        # 文档
        docstring = ast.get_docstring(node) or ""
        
        # 公共方法
        public_methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not item.name.startswith('_'):
                    public_methods.append(item.name)
        
        body_summary = f"{len(public_methods)} public methods: {', '.join(public_methods[:5])}"
        
        return Symbol(
            name=name,
            kind='class',
            file_path=filepath,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            signature=signature,
            docstring=docstring[:200] if docstring else "",
            children=public_methods[:10],
        )
    
    def _index_generic_file(self, filepath: str, code: str):
        """通用文件索引"""
        # 简单的函数/类检测
        function_pattern = re.compile(r'^(?:def|function|func)\s+(\w+)', re.MULTILINE)
        class_pattern = re.compile(r'^(?:class|interface|struct)\s+(\w+)', re.MULTILINE)
        
        file_index = FileIndex(
            file_path=filepath,
            language='generic'
        )
        
        for match in function_pattern.finditer(code):
            line_num = code[:match.start()].count('\n') + 1
            symbol = Symbol(
                name=match.group(1),
                kind='function',
                file_path=filepath,
                line_start=line_num,
                line_end=line_num,
                signature=match.group(0),
            )
            file_index.symbols.append(symbol)
            self.project_index.symbol_map[symbol.name] = symbol
        
        for match in class_pattern.finditer(code):
            line_num = code[:match.start()].count('\n') + 1
            symbol = Symbol(
                name=match.group(1),
                kind='class',
                file_path=filepath,
                line_start=line_num,
                line_end=line_num,
                signature=match.group(0),
            )
            file_index.symbols.append(symbol)
            self.project_index.symbol_map[symbol.name] = symbol
        
        if file_index.symbols:
            self.project_index.files[filepath] = file_index
    
    def _build_dependencies(self):
        """构建文件依赖关系"""
        for filepath, file_index in self.project_index.files.items():
            # 简化：假设导入的模块对应同名的本地文件
            for imp in file_index.imports:
                module_path = imp.replace('.', '/')
                
                # 查找可能的本地文件
                possible_paths = [
                    f"{module_path}.py",
                    f"{module_path}/__init__.py",
                    os.path.join(os.path.dirname(filepath), f"{module_path.split('.')[-1]}.py"),
                ]
                
                for pp in possible_paths:
                    if pp in self.project_index.files:
                        file_index.dependencies.add(pp)
                        self.project_index.files[pp].dependents.add(filepath)


class LayeredContextBuilder:
    """
    分层上下文构建器
    
    根据任务复杂度动态选择上下文层级。
    """
    
    def __init__(self, project_index: Optional[ProjectIndex] = None):
        self.project_index = project_index
        self.symbol_index = SymbolIndex()
        self.code_signer = None  # 延迟导入
    
    def set_project_index(self, index: ProjectIndex):
        """设置项目索引"""
        self.project_index = index
    
    def build_context(
        self,
        query: str,
        intent_type: str = "general",
        target_file: Optional[str] = None,
    ) -> Tuple[str, ContextLevel]:
        """
        根据查询构建上下文
        
        Args:
            query: 用户查询
            intent_type: 意图类型
            target_file: 目标文件
        
        Returns:
            (context, level): 上下文内容和层级
        """
        if not self.project_index:
            return "", ContextLevel.L1_FILE_OVERVIEW
        
        # 分析查询复杂度
        level = self._select_level(intent_type, query)
        
        # 根据层级构建上下文
        if level == ContextLevel.L1_FILE_OVERVIEW:
            return self._build_l1_overview(target_file), level
        elif level == ContextLevel.L2_SYMBOL_INDEX:
            return self._build_l2_symbol_index(query), level
        elif level == ContextLevel.L3_RELATED_CODE:
            return self._build_l3_related_code(query, target_file), level
        elif level == ContextLevel.L4_COMPLETE_IMPL:
            return self._build_l4_complete_impl(target_file), level
        else:
            return self._build_l5_full_code(), level
    
    def _select_level(self, intent_type: str, query: str) -> ContextLevel:
        """选择上下文层级"""
        # 简单查询 → 低层级
        if any(kw in query for kw in ['查找', '搜索', '看看', '哪个', '哪里']):
            return ContextLevel.L2_SYMBOL_INDEX
        
        # 修改查询 → 中层级
        if any(kw in query for kw in ['修改', '添加', '删除', '更新', '改']):
            return ContextLevel.L3_RELATED_CODE
        
        # 生成/重构 → 高层级
        if any(kw in query for kw in ['生成', '创建', '重构', '重写', '实现']):
            return ContextLevel.L4_COMPLETE_IMPL
        
        # 意图类型映射
        intent_levels = {
            'greeting': ContextLevel.L1_FILE_OVERVIEW,
            'chitchat': ContextLevel.L1_FILE_OVERVIEW,
            'code_generation': ContextLevel.L3_RELATED_CODE,
            'code_modification': ContextLevel.L3_RELATED_CODE,
            'debugging': ContextLevel.L2_SYMBOL_INDEX,
            'code_review': ContextLevel.L4_COMPLETE_IMPL,
            'reasoning': ContextLevel.L2_SYMBOL_INDEX,
        }
        
        return intent_levels.get(intent_type, ContextLevel.L2_SYMBOL_INDEX)
    
    def _build_l1_overview(self, target_file: Optional[str] = None) -> str:
        """L1: 文件概览"""
        if not self.project_index:
            return ""
        
        lines = ["## 项目概览\n"]
        
        # 统计
        total_files = len(self.project_index.files)
        total_symbols = sum(f.symbol_count for f in self.project_index.files.values())
        
        lines.append(f"- 文件数: {total_files}")
        lines.append(f"- 符号数: {total_symbols}")
        lines.append("")
        
        # 主要目录结构
        dirs = set()
        for filepath in self.project_index.files:
            rel = os.path.relpath(filepath, self.project_index.root_path)
            parts = rel.split(os.sep)
            if len(parts) > 1:
                dirs.add(parts[0])
        
        if dirs:
            lines.append("### 主要模块")
            for d in sorted(dirs)[:10]:
                lines.append(f"- {d}/")
        
        return '\n'.join(lines)
    
    def _build_l2_symbol_index(self, query: str) -> str:
        """L2: 符号索引"""
        if not self.project_index:
            return ""
        
        lines = ["## 符号索引\n"]
        
        # 搜索相关符号
        symbols = self.symbol_index.project_index.find_symbols(query) if self.symbol_index.project_index else []
        
        if not symbols:
            # 全局索引
            query_lower = query.lower()
            for name, symbol in self.project_index.symbol_map.items():
                if query_lower in name.lower():
                    symbols.append(symbol)
        
        # 按文件分组
        by_file = defaultdict(list)
        for s in symbols:
            by_file[s.file_path].append(s)
        
        for filepath, syms in list(by_file.items())[:5]:
            rel_path = os.path.relpath(filepath, self.project_index.root_path)
            lines.append(f"### {rel_path}\n")
            for s in syms[:10]:
                prefix = "+" if s.is_public else "-"
                lines.append(f"{prefix} `{s.signature}`")
            lines.append("")
        
        return '\n'.join(lines)
    
    def _build_l3_related_code(self, query: str, target_file: Optional[str] = None) -> str:
        """L3: 相关代码"""
        if not self.project_index:
            return ""
        
        # 初始化代码签名器
        if not self.code_signer:
            from client.src.business.long_context.code_signer import CodeSigner
            self.code_signer = CodeSigner()
        
        lines = ["## 相关代码\n"]
        
        # 目标文件
        if target_file and target_file in self.project_index.files:
            file_index = self.project_index.files[target_file]
            
            try:
                with open(target_file, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                result = self.code_signer.signaturize(code)
                lines.append(f"### {os.path.basename(target_file)}\n")
                lines.append(result.signature_code)
            except Exception as e:
                lines.append(f"无法读取文件: {e}")
        else:
            # 搜索相关文件
            query_lower = query.lower()
            related_files = []
            
            for filepath, file_index in self.project_index.files.items():
                for symbol in file_index.symbols:
                    if query_lower in symbol.name.lower():
                        related_files.append(filepath)
                        break
            
            for filepath in related_files[:3]:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        code = f.read()
                    
                    result = self.code_signer.signaturize(code)
                    rel_path = os.path.relpath(filepath, self.project_index.root_path)
                    lines.append(f"### {rel_path}\n")
                    lines.append(result.signature_code)
                except Exception:
                    pass
        
        return '\n'.join(lines)
    
    def _build_l4_complete_impl(self, target_file: Optional[str] = None) -> str:
        """L4: 完整实现"""
        if not target_file or not self.project_index:
            return ""
        
        if target_file not in self.project_index.files:
            return ""
        
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # 完整代码（带行号）
            lines = ["## 完整实现\n"]
            lines.append(f"### {os.path.basename(target_file)}\n")
            
            for i, line in enumerate(code.splitlines(), 1):
                lines.append(f"{i:4d}: {line}")
            
            return '\n'.join(lines)
        except Exception as e:
            return f"无法读取文件: {e}"
    
    def _build_l5_full_code(self) -> str:
        """L5: 全部代码"""
        if not self.project_index:
            return ""
        
        lines = ["## 全部代码\n"]
        
        for filepath in sorted(self.project_index.files.keys()):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                rel_path = os.path.relpath(filepath, self.project_index.root_path)
                lines.append(f"\n### {rel_path}\n")
                lines.append("```" + os.path.splitext(filepath)[1][1:])
                lines.append(code)
                lines.append("```")
            except Exception:
                pass
        
        return '\n'.join(lines)
    
    def get_level_description(self, level: ContextLevel) -> str:
        """获取层级描述"""
        descriptions = {
            ContextLevel.L1_FILE_OVERVIEW: "L1 - 文件概览（~64 tokens）",
            ContextLevel.L2_SYMBOL_INDEX: "L2 - 符号索引（~256 tokens）",
            ContextLevel.L3_RELATED_CODE: "L3 - 相关代码（~1K tokens）",
            ContextLevel.L4_COMPLETE_IMPL: "L4 - 完整实现（~4K tokens）",
            ContextLevel.L5_FULL_CODE: "L5 - 全部代码（~16K tokens）",
        }
        return descriptions.get(level, "Unknown")


class IncrementalContextManager:
    """
    增量上下文管理器
    
    上下文累加，而非重置。持续追踪对话历史中的上下文。
    """
    
    def __init__(self, max_contexts: int = 20):
        self.max_contexts = max_contexts
        self.contexts: List[Dict[str, Any]] = []
        self.current_hash: str = ""
    
    def add_context(
        self,
        level: ContextLevel,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """添加上下文"""
        import hashlib
        
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        
        # 跳过重复
        if content_hash == self.current_hash:
            return
        
        context = {
            'level': level,
            'content': content,
            'hash': content_hash,
            'metadata': metadata or {},
        }
        
        self.contexts.append(context)
        
        # 限制数量
        if len(self.contexts) > self.max_contexts:
            self.contexts.pop(0)
        
        self.current_hash = content_hash
    
    def get_context_summary(self) -> str:
        """获取上下文摘要"""
        if not self.contexts:
            return ""
        
        lines = ["## 上下文历史\n"]
        
        for i, ctx in enumerate(self.contexts[-5:], 1):  # 最近5条
            level_name = ctx['level'].name
            preview = ctx['content'][:100].replace('\n', ' ')
            lines.append(f"{i}. [{level_name}] {preview}...")
        
        return '\n'.join(lines)
    
    def clear(self):
        """清空上下文"""
        self.contexts.clear()
        self.current_hash = ""


# 导出
__all__ = [
    'ContextLevel',
    'TokenBudget',
    'LEVEL_BUDGETS',
    'Symbol',
    'FileIndex',
    'ProjectIndex',
    'SymbolIndex',
    'LayeredContextBuilder',
    'IncrementalContextManager',
]
