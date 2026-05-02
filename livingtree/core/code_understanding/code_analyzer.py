"""
代码分析器 (Code Analyzer)

基于 AST 的代码结构和质量分析：
- 函数/类/模块提取
- 代码复杂度评估（圈复杂度）
- 依赖关系分析
- 代码质量评分
"""

import ast
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class CodeQuality(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    NEEDS_IMPROVEMENT = "needs_improvement"
    POOR = "poor"


@dataclass
class FunctionInfo:
    name: str
    line_start: int
    line_end: int
    args: List[str] = field(default_factory=list)
    docstring: str = ""
    complexity: int = 0
    dependencies: Set[str] = field(default_factory=set)


@dataclass
class ClassInfo:
    name: str
    line_start: int
    line_end: int
    methods: List[FunctionInfo] = field(default_factory=list)
    bases: List[str] = field(default_factory=list)
    docstring: str = ""


@dataclass
class ImportInfo:
    module: str
    names: List[str] = field(default_factory=list)
    is_from: bool = False


@dataclass
class CodeAnalysis:
    file_path: str
    language: str = "python"
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    imports: List[ImportInfo] = field(default_factory=list)
    loc: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    quality: CodeQuality = CodeQuality.GOOD
    issues: List[str] = field(default_factory=list)

    @property
    def total_functions(self) -> int:
        method_count = sum(len(c.methods) for c in self.classes)
        return len(self.functions) + method_count

    @property
    def average_complexity(self) -> float:
        all_funcs = list(self.functions)
        for cls in self.classes:
            all_funcs.extend(cls.methods)
        if not all_funcs:
            return 0.0
        return sum(f.complexity for f in all_funcs) / len(all_funcs)

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "language": self.language,
            "loc": self.loc,
            "functions": len(self.functions),
            "classes": len(self.classes),
            "total_funcs": self.total_functions,
            "avg_complexity": round(self.average_complexity, 2),
            "quality": self.quality.value,
            "issues_count": len(self.issues),
            "issues": self.issues[:10],
        }


class CodeAnalyzer:

    SUPPORTED_LANGUAGES = {"python": ".py", "javascript": ".js",
                           "typescript": ".ts", "java": ".java"}

    def analyze_file(self, file_path: str) -> CodeAnalysis:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
        return self.analyze_source(source, file_path)

    def analyze_source(self, source: str,
                       file_path: str = "<string>") -> CodeAnalysis:
        analysis = CodeAnalysis(file_path=file_path)
        analysis.loc = len(source.splitlines())

        try:
            tree = ast.parse(source)
            analysis.functions = self._extract_functions(tree)
            analysis.classes = self._extract_classes(tree)
            analysis.imports = self._extract_imports(tree)

            all_funcs = list(analysis.functions)
            for cls in analysis.classes:
                all_funcs.extend(cls.methods)

            avg_complexity = (sum(f.complexity for f in all_funcs)
                            / max(len(all_funcs), 1))

            if avg_complexity > 20:
                analysis.quality = CodeQuality.POOR
                analysis.issues.append(
                    f"平均圈复杂度 {avg_complexity:.1f} > 20")
            elif avg_complexity > 10:
                analysis.quality = CodeQuality.NEEDS_IMPROVEMENT
                analysis.issues.append(
                    f"平均圈复杂度 {avg_complexity:.1f} > 10")
            elif avg_complexity > 5:
                analysis.quality = CodeQuality.GOOD
            else:
                analysis.quality = CodeQuality.EXCELLENT

            for func in all_funcs:
                if func.complexity > 10:
                    analysis.issues.append(
                        f"函数 '{func.name}' 圈复杂度 {func.complexity} > 10")

            if analysis.loc > 1000:
                analysis.quality = CodeQuality.NEEDS_IMPROVEMENT
                analysis.issues.append(f"文件过大: {analysis.loc} 行 > 1000")

        except SyntaxError as e:
            logger.error(f"语法错误: {file_path}: {e}")
            analysis.quality = CodeQuality.POOR
            analysis.issues.append(f"语法错误: {str(e)}")
        except Exception as e:
            logger.error(f"分析失败: {file_path}: {e}")
            analysis.quality = CodeQuality.NEEDS_IMPROVEMENT
            analysis.issues.append(f"分析异常: {str(e)}")

        return analysis

    def _extract_functions(self, tree: ast.AST) -> List[FunctionInfo]:
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func = FunctionInfo(
                    name=node.name,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    args=[arg.arg for arg in node.args.args],
                    docstring=ast.get_docstring(node) or "",
                    complexity=self._calculate_complexity(node),
                    dependencies=self._extract_function_calls(node))
                functions.append(func)
        return functions

    def _extract_classes(self, tree: ast.AST) -> List[ClassInfo]:
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                cls = ClassInfo(
                    name=node.name,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    bases=[self._get_name(b) for b in node.bases],
                    docstring=ast.get_docstring(node) or "")

                for child in node.body:
                    if isinstance(child, (ast.FunctionDef,
                                         ast.AsyncFunctionDef)):
                        method = FunctionInfo(
                            name=child.name,
                            line_start=child.lineno,
                            line_end=child.end_lineno or child.lineno,
                            args=[arg.arg for arg in child.args.args],
                            docstring=ast.get_docstring(child) or "",
                            complexity=self._calculate_complexity(child),
                            dependencies=self._extract_function_calls(child))
                        cls.methods.append(method)
                classes.append(cls)
        return classes

    def _extract_imports(self, tree: ast.AST) -> List[ImportInfo]:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportInfo(
                        module=alias.name,
                        names=[alias.asname or alias.name]))
            elif isinstance(node, ast.ImportFrom):
                imports.append(ImportInfo(
                    module=node.module or "",
                    names=[alias.name for alias in node.names],
                    is_from=True))
        return imports

    def _calculate_complexity(self, node: ast.AST) -> int:
        complexity = 1
        branching_nodes = (ast.If, ast.For, ast.While, ast.ExceptHandler,
                          ast.And, ast.Or, ast.Try, ast.With,
                          ast.AsyncFor, ast.AsyncWith)
        for child in ast.walk(node):
            if isinstance(child, branching_nodes):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def _extract_function_calls(self, node: ast.AST) -> Set[str]:
        calls = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = self._get_name(child.func)
                if name:
                    calls.add(name)
            elif isinstance(child, ast.Attribute):
                name = self._get_name(child)
                if name:
                    calls.add(name)
        return calls

    def _get_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_name(node.func)
        return ""

    def compare(self, analysis1: CodeAnalysis,
                analysis2: CodeAnalysis) -> Dict[str, Any]:
        return {
            "loc_diff": analysis2.loc - analysis1.loc,
            "func_diff": analysis2.total_functions - analysis1.total_functions,
            "quality1": analysis1.quality.value,
            "quality2": analysis2.quality.value,
            "complexity1": round(analysis1.average_complexity, 2),
            "complexity2": round(analysis2.average_complexity, 2),
        }


__all__ = [
    "CodeQuality", "FunctionInfo", "ClassInfo", "ImportInfo",
    "CodeAnalysis", "CodeAnalyzer",
]
