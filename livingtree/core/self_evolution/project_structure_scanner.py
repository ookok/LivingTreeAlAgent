"""
ProjectStructureScanner - 项目结构自动扫描器

自动扫描项目代码结构，提取：
1. 模块/文件树
2. 类定义及其继承关系
3. 函数/方法签名
4. 依赖关系（import 分析）
5. 模块间调用图
6. 代码质量指标（行数、复杂度、TODO/FIXME 统计）
7. 现有工具注册情况（ToolRegistry 扫描）

Author: LivingTreeAI
Date: 2026-04-29
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from loguru import logger


class ScanDepth(Enum):
    """扫描深度"""
    SHALLOW = "shallow"      # 仅文件名 + 一级目录
    MEDIUM = "medium"        # 文件名 + AST 类/函数定义
    DEEP = "deep"            # 完整 AST + 依赖 + 调用关系


@dataclass
class ModuleInfo:
    """模块信息"""
    path: str
    name: str
    relative_path: str
    file_size: int
    line_count: int
    language: str = "python"
    classes: List[Dict[str, Any]] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[Dict[str, str]] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    todos: List[str] = field(default_factory=list)
    fixmes: List[str] = field(default_factory=list)
    complexity_score: float = 0.0


@dataclass
class ClassInfo:
    """类信息"""
    name: str
    module_path: str
    bases: List[str]
    methods: List[Dict[str, Any]]
    docstring: str = ""
    line_start: int = 0
    line_end: int = 0
    decorators: List[str] = field(default_factory=list)


@dataclass
class FunctionInfo:
    """函数信息"""
    name: str
    module_path: str
    args: List[str]
    returns: str = ""
    docstring: str = ""
    is_async: bool = False
    decorators: List[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0


@dataclass
class DependencyInfo:
    """依赖信息"""
    source_module: str
    target_module: str
    import_type: str  # local, stdlib, third_party
    items: List[str]  # 导入的具体名称


@dataclass
class ScanResult:
    """扫描结果"""
    project_root: str
    total_files: int = 0
    total_lines: int = 0
    total_classes: int = 0
    total_functions: int = 0
    modules: Dict[str, ModuleInfo] = field(default_factory=dict)
    classes: Dict[str, ClassInfo] = field(default_factory=dict)
    functions: Dict[str, FunctionInfo] = field(default_factory=dict)
    dependencies: List[DependencyInfo] = field(default_factory=list)
    todo_count: int = 0
    fixme_count: int = 0
    registered_tools: List[str] = field(default_factory=list)
    directory_tree: Dict[str, Any] = field(default_factory=dict)
    complexity_summary: Dict[str, float] = field(default_factory=dict)
    scan_duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转为字典"""
        return {
            "project_root": self.project_root,
            "total_files": self.total_files,
            "total_lines": self.total_lines,
            "total_classes": self.total_classes,
            "total_functions": self.total_functions,
            "todo_count": self.todo_count,
            "fixme_count": self.fixme_count,
            "registered_tools": self.registered_tools,
            "modules": {
                k: {
                    "path": v.path,
                    "name": v.name,
                    "line_count": v.line_count,
                    "classes": v.classes,
                    "functions": v.functions,
                    "imports": v.imports,
                    "todos": v.todos,
                    "fixmes": v.fixmes,
                }
                for k, v in self.modules.items()
            },
            "scan_duration_ms": self.scan_duration_ms,
        }


class ProjectStructureScanner:
    """
    项目结构自动扫描器

    功能：
    1. 递归扫描项目目录，构建文件树
    2. 解析 Python AST，提取类/函数/依赖
    3. 分析 TODO/FIXME 标记
    4. 计算代码复杂度
    5. 扫描已注册工具

    用法：
        scanner = ProjectStructureScanner(project_root)
        result = scanner.scan(depth=ScanDepth.DEEP)
    """

    # 需要跳过的目录
    SKIP_DIRS = {
        "__pycache__", ".git", ".idea", ".vscode", "node_modules",
        "venv", ".venv", "env", ".env", "dist", "build", ".eggs",
        "*.egg-info", ".tox", ".mypy_cache", ".pytest_cache",
        ".workbuddy", ".livingtree", ".github",
    }

    # 需要跳过的文件模式
    SKIP_PATTERNS = {
        "*.pyc", "*.pyo", "*.egg-info", "*.so", "*.dll",
        "*.dylib", "*.whl", ".DS_Store", "Thumbs.db",
    }

    # 支持的源代码文件扩展名
    SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs"}

    def __init__(self, project_root: str):
        self._root = Path(project_root).resolve()
        self._logger = logger.bind(component="ProjectStructureScanner")
        self._modules: Dict[str, ModuleInfo] = {}
        self._classes: Dict[str, ClassInfo] = {}
        self._functions: Dict[str, FunctionInfo] = {}
        self._dependencies: List[DependencyInfo] = []
        self._registered_tools: List[str] = []

    def scan(
        self,
        depth: ScanDepth = ScanDepth.MEDIUM,
        include_dirs: Optional[List[str]] = None,
        exclude_dirs: Optional[List[str]] = None,
        max_files: int = 5000,
    ) -> ScanResult:
        """
        执行项目扫描

        Args:
            depth: 扫描深度
            include_dirs: 仅扫描这些子目录（None = 全部）
            exclude_dirs: 排除这些子目录
            max_files: 最大文件数

        Returns:
            ScanResult
        """
        import time
        start = time.time()
        self._logger.info(f"开始扫描项目: {self._root}")

        # 1. 收集文件
        py_files = self._collect_files(include_dirs, exclude_dirs, max_files)
        self._logger.info(f"收集到 {len(py_files)} 个 Python 文件")

        # 2. 构建目录树
        dir_tree = self._build_directory_tree(include_dirs, exclude_dirs)

        # 3. 逐文件解析
        for fpath in py_files:
            try:
                if depth in (ScanDepth.MEDIUM, ScanDepth.DEEP):
                    self._parse_python_file(fpath)
                else:
                    self._parse_shallow(fpath)
            except Exception as e:
                self._logger.warning(f"解析失败 {fpath}: {e}")

        # 4. 扫描已注册工具
        self._scan_registered_tools()

        # 5. 计算复杂度
        complexity = self._compute_complexity_summary()

        # 6. 统计
        total_lines = sum(m.line_count for m in self._modules.values())
        total_classes = len(self._classes)
        total_functions = len(self._functions)
        todo_count = sum(len(m.todos) for m in self._modules.values())
        fixme_count = sum(len(m.fixmes) for m in self._modules.values())

        duration = (time.time() - start) * 1000
        self._logger.info(
            f"扫描完成: {len(self._modules)} 文件, {total_lines} 行, "
            f"{total_classes} 类, {total_functions} 函数, "
            f"{todo_count} TODO, {fixme_count} FIXME, 耗时 {duration:.0f}ms"
        )

        return ScanResult(
            project_root=str(self._root),
            total_files=len(self._modules),
            total_lines=total_lines,
            total_classes=total_classes,
            total_functions=total_functions,
            modules=self._modules,
            classes=self._classes,
            functions=self._functions,
            dependencies=self._dependencies,
            todo_count=todo_count,
            fixme_count=fixme_count,
            registered_tools=self._registered_tools,
            directory_tree=dir_tree,
            complexity_summary=complexity,
            scan_duration_ms=duration,
        )

    def _collect_files(
        self,
        include_dirs: Optional[List[str]],
        exclude_dirs: Optional[List[str]],
        max_files: int,
    ) -> List[Path]:
        """收集需要扫描的 Python 文件"""
        skip_dirs = set(self.SKIP_DIRS)
        if exclude_dirs:
            skip_dirs.update(exclude_dirs)

        files = []
        for root, dirs, filenames in os.walk(self._root):
            rel = Path(root).relative_to(self._root)
            parts = set(rel.parts)

            # 跳过目录
            if parts & skip_dirs:
                dirs.clear()
                continue

            # 仅扫描指定目录
            if include_dirs and not any(str(rel).startswith(d) for d in include_dirs):
                continue

            for fn in filenames:
                if fn.endswith(".py"):
                    fpath = Path(root) / fn
                    if fpath.stat().st_size > 0:
                        files.append(fpath)
                        if len(files) >= max_files:
                            return files

        return files

    def _build_directory_tree(
        self,
        include_dirs: Optional[List[str]],
        exclude_dirs: Optional[List[str]],
    ) -> Dict[str, Any]:
        """构建目录树结构"""
        skip_dirs = set(self.SKIP_DIRS)
        if exclude_dirs:
            skip_dirs.update(exclude_dirs)

        def _build(path: Path) -> Dict[str, Any]:
            items = {}
            try:
                for child in sorted(path.iterdir()):
                    name = child.name
                    if name.startswith('.') and name not in {".livingtree"}:
                        continue
                    if name in skip_dirs:
                        continue
                    if child.is_dir():
                        items[name] = _build(child)
            except PermissionError:
                pass
            return items

        return _build(self._root)

    def _parse_shallow(self, fpath: Path):
        """浅层解析：仅文件名+行数"""
        rel = fpath.relative_to(self._root)
        content = fpath.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()

        module = ModuleInfo(
            path=str(fpath),
            name=fpath.stem,
            relative_path=str(rel),
            file_size=fpath.stat().st_size,
            line_count=len(lines),
        )
        self._modules[str(rel)] = module

    def _parse_python_file(self, fpath: Path):
        """深度解析 Python 文件（AST）"""
        rel = fpath.relative_to(self._root)
        content = fpath.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()

        module = ModuleInfo(
            path=str(fpath),
            name=fpath.stem,
            relative_path=str(rel),
            file_size=fpath.stat().st_size,
            line_count=len(lines),
        )

        # 提取 TODO / FIXME
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if "# TODO" in stripped or "# todo" in stripped:
                module.todos.append(f"L{i}: {stripped}")
            if "# FIXME" in stripped or "# fixme" in stripped:
                module.fixmes.append(f"L{i}: {stripped}")

        # AST 解析
        try:
            tree = ast.parse(content, filename=str(fpath))
        except SyntaxError:
            self._logger.warning(f"AST 解析失败（语法错误）: {rel}")
            self._modules[str(rel)] = module
            return

        for node in ast.walk(tree):
            # 提取 import
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_type = self._classify_import(alias.name)
                    module.imports.append({
                        "module": alias.name,
                        "alias": alias.asname or alias.name,
                        "type": import_type,
                    })
                    self._dependencies.append(DependencyInfo(
                        source_module=str(rel),
                        target_module=alias.name,
                        import_type=import_type,
                        items=[alias.asname or alias.name],
                    ))

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    import_type = self._classify_import(node.module)
                    for alias in (node.names or []):
                        module.imports.append({
                            "module": node.module,
                            "name": alias.name,
                            "alias": alias.asname or alias.name,
                            "type": import_type,
                        })
                    self._dependencies.append(DependencyInfo(
                        source_module=str(rel),
                        target_module=node.module,
                        import_type=import_type,
                        items=[a.name for a in (node.names or [])],
                    ))

            # 提取类定义
            elif isinstance(node, ast.ClassDef):
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(ast.unparse(base))

                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(self._extract_function_info(item, str(rel)))

                docstring = ast.get_docstring(node) or ""
                decorators = [ast.unparse(d) for d in node.decorator_list]

                class_info = ClassInfo(
                    name=node.name,
                    module_path=str(rel),
                    bases=bases,
                    methods=methods,
                    docstring=docstring,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    decorators=decorators,
                )
                key = f"{str(rel)}::{node.name}"
                self._classes[key] = class_info

                module.classes.append({
                    "name": node.name,
                    "bases": bases,
                    "method_count": len(methods),
                    "docstring": docstring[:100] if docstring else "",
                    "line": node.lineno,
                })

            # 提取顶层函数
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if isinstance(ast.parse(""), ast.Module):  # 确认是顶层
                    # 只处理直接子节点（非嵌套在类中）
                    if hasattr(node, 'col_offset') and node.col_offset == 0:
                        func_info = self._extract_function_info(node, str(rel))
                        key = f"{str(rel)}::{node.name}"
                        self._functions[key] = func_info
                        module.functions.append({
                            "name": node.name,
                            "args": func_info.args,
                            "is_async": func_info.is_async,
                            "line": node.lineno,
                        })

        self._modules[str(rel)] = module

    def _extract_function_info(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, module_path: str
    ) -> FunctionInfo:
        """提取函数信息"""
        args = []
        returns = ""
        decorators = []

        for arg in node.args.args:
            args.append(arg.arg)
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")

        if node.returns:
            try:
                returns = ast.unparse(node.returns)
            except Exception:
                returns = str(node.returns)

        decorators = [ast.unparse(d) for d in node.decorator_list]
        docstring = ast.get_docstring(node) or ""

        return FunctionInfo(
            name=node.name,
            module_path=module_path,
            args=args,
            returns=returns,
            docstring=docstring,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            decorators=decorators,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
        )

    def _classify_import(self, module_name: str) -> str:
        """分类 import：local / stdlib / third_party"""
        if module_name.startswith("client.") or module_name.startswith("."):
            return "local"
        try:
            import importlib.util
            if importlib.util.find_spec(module_name.split(".")[0]) is not None:
                return "stdlib"
        except Exception:
            pass
        return "third_party"

    def _scan_registered_tools(self):
        """扫描 ToolRegistry 中已注册的工具"""
        try:
            from business.tools.tool_registry import ToolRegistry
            registry = ToolRegistry.get_instance()
            tools = registry.list_tools()
            self._registered_tools = [t.name for t in tools]
            self._logger.info(f"已注册工具: {len(self._registered_tools)} 个")
        except Exception as e:
            self._logger.warning(f"扫描 ToolRegistry 失败: {e}")

    def _compute_complexity_summary(self) -> Dict[str, float]:
        """计算复杂度摘要"""
        summary = {
            "avg_lines_per_file": 0.0,
            "avg_classes_per_file": 0.0,
            "avg_functions_per_file": 0.0,
            "total_complexity": 0.0,
        }
        if not self._modules:
            return summary

        n = len(self._modules)
        total_lines = sum(m.line_count for m in self._modules.values())
        total_classes = sum(len(m.classes) for m in self._modules.values())
        total_functions = sum(len(m.functions) for m in self._modules.values())

        summary["avg_lines_per_file"] = round(total_lines / n, 1)
        summary["avg_classes_per_file"] = round(total_classes / n, 2)
        summary["avg_functions_per_file"] = round(total_functions / n, 2)

        # 简单圈复杂度估算：分支数
        total_branches = 0
        for fpath, module in self._modules.items():
            content = Path(module.path).read_text(encoding="utf-8", errors="ignore")
            total_branches += content.count(" if ") + content.count(" elif ") + \
                content.count(" for ") + content.count(" while ") + \
                content.count(" and ") + content.count(" or ")

        summary["total_complexity"] = float(total_branches)
        return summary

    def get_module_summary(self) -> str:
        """获取模块摘要文本（用于 LLM 上下文）"""
        if not self._modules:
            return "无模块信息"

        lines = [f"项目: {self._root.name}"]
        lines.append(f"文件: {len(self._modules)} | 行数: {sum(m.line_count for m in self._modules.values())}")
        lines.append(f"类: {len(self._classes)} | 函数: {len(self._functions)}")
        lines.append(f"TODO: {sum(len(m.todos) for m in self._modules.values())} | "
                     f"FIXME: {sum(len(m.fixmes) for m in self._modules.values())}")
        lines.append(f"已注册工具: {len(self._registered_tools)}")
        lines.append("")

        # 按目录分组显示
        dir_modules: Dict[str, List[str]] = defaultdict(list)
        for rel, module in self._modules.items():
            parts = Path(rel).parts
            dir_key = "/".join(parts[:2]) if len(parts) >= 2 else parts[0] if parts else "."
            dir_modules[dir_key].append(rel)

        lines.append("=== 目录结构 ===")
        for d in sorted(dir_modules.keys()):
            files = dir_modules[d]
            total_lines = sum(self._modules[f].line_count for f in files)
            lines.append(f"  {d}/ ({len(files)} 文件, {total_lines} 行)")

        lines.append("")
        lines.append("=== 核心类 ===")
        for key, cls in sorted(self._classes.items()):
            method_count = len(cls.methods)
            lines.append(f"  {cls.name} ({cls.module_path}) - {method_count} 方法")

        lines.append("")
        lines.append("=== 已注册工具 ===")
        for tool_name in self._registered_tools:
            lines.append(f"  - {tool_name}")

        return "\n".join(lines)

    def find_classes_by_base(self, base_class: str) -> List[ClassInfo]:
        """查找所有继承自指定基类的类"""
        results = []
        for cls in self._classes.values():
            if base_class in cls.bases:
                results.append(cls)
        return results

    def find_classes_by_decorator(self, decorator: str) -> List[ClassInfo]:
        """查找使用指定装饰器的类"""
        results = []
        for cls in self._classes.values():
            for d in cls.decorators:
                if decorator in d:
                    results.append(cls)
                    break
        return results

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """获取模块间依赖图"""
        graph: Dict[str, List[str]] = defaultdict(set)
        for dep in self._dependencies:
            if dep.import_type == "local":
                graph[dep.source_module].add(dep.target_module)
        return {k: sorted(v) for k, v in graph.items()}
