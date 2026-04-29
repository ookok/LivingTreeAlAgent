#!/usr/bin/env python3
"""
IDE 功能增强模块
整合智能代码补全、代码分析、项目管理功能
"""

import os
import re
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class Language(Enum):
    """编程语言"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"
    CSHARP = "csharp"
    GO = "go"
    RUST = "rust"
    UNKNOWN = "unknown"


@dataclass
class Completion:
    """代码补全项"""
    text: str
    display_text: str
    type: str  # keyword, function, class, variable, snippet
    score: float
    docstring: str = ""
    snippet: str = ""


@dataclass
class AnalysisIssue:
    """代码分析问题"""
    line: int
    column: int
    severity: str  # error, warning, info
    code: str
    message: str
    suggestion: str = ""


@dataclass
class ProjectFile:
    """项目文件"""
    path: str
    name: str
    language: Language
    size: int
    modified: datetime
    is_directory: bool = False


class IntelligentCodeCompleter:
    """
    智能代码补全器

    参考 Jedi 的实现，提供基于上下文的智能补全
    """

    def __init__(self):
        self._keywords: Dict[str, List[str]] = {
            "python": [
                "def", "class", "if", "elif", "else", "for", "while", "try",
                "except", "finally", "with", "as", "import", "from", "return",
                "yield", "raise", "pass", "break", "continue", "and", "or",
                "not", "in", "is", "True", "False", "None", "lambda", "assert",
                "async", "await", "global", "nonlocal"
            ],
            "javascript": [
                "function", "const", "let", "var", "if", "else", "for", "while",
                "return", "try", "catch", "finally", "throw", "class", "extends",
                "import", "export", "default", "async", "await", "true", "false",
                "null", "undefined", "new", "this", "super"
            ],
        }

        self._snippets: Dict[str, Dict[str, str]] = {
            "python": {
                "for": "for ${1:item} in ${2:iterable}:\n    ${3:pass}",
                "def": "def ${1:function_name}(${2:args}):\n    ${3:pass}",
                "class": "class ${1:ClassName}:\n    def __init__(self${2:, args}):\n        ${3:pass}",
                "if": "if ${1:condition}:\n    ${2:pass}",
                "try": "try:\n    ${1:pass}\nexcept ${2:Exception} as ${3:e}:\n    ${4:pass}",
                "with": "with ${1:context} as ${2:var}:\n    ${3:pass}",
            },
            "javascript": {
                "for": "for (let ${1:i} = 0; ${1:i} < ${2:length}; ${1:i}++) {\n    ${3:pass}\n}",
                "const": "const ${1:name} = ${2:value};",
                "function": "function ${1:name}(${2:args}) {\n    ${3:pass}\n}",
                "arrow": "const ${1:name} = (${2:args}) => {\n    ${3:pass}\n};",
                "if": "if (${1:condition}) {\n    ${2:pass}\n}",
                "try": "try {\n    ${1:pass}\n} catch (${2:error}) {\n    ${3:pass}\n}",
            },
        }

    def complete(
        self,
        code: str,
        cursor_pos: int,
        language: str = "python",
    ) -> List[Completion]:
        """获取代码补全"""
        completions = []

        prefix = self._extract_prefix(code, cursor_pos)
        context = code[:cursor_pos]

        if language not in self._keywords:
            language = "python"

        for keyword in self._keywords.get(language, []):
            if keyword.startswith(prefix):
                completions.append(Completion(
                    text=keyword,
                    display_text=keyword,
                    type="keyword",
                    score=0.9,
                ))

        for trigger, snippet in self._snippets.get(language, {}).items():
            if trigger.startswith(prefix):
                completions.append(Completion(
                    text=trigger,
                    display_text=f"{trigger}...",
                    type="snippet",
                    score=0.85,
                    snippet=snippet,
                ))

        variables = self._extract_variables(context, language)
        for var in variables:
            if var.startswith(prefix):
                completions.append(Completion(
                    text=var,
                    display_text=var,
                    type="variable",
                    score=0.7,
                ))

        functions = self._extract_functions(context, language)
        for func in functions:
            if func.startswith(prefix):
                completions.append(Completion(
                    text=func,
                    display_text=func,
                    type="function",
                    score=0.75,
                ))

        completions.sort(key=lambda x: x.score, reverse=True)
        return completions[:10]

    def _extract_prefix(self, code: str, cursor_pos: int) -> str:
        """提取当前前缀"""
        start = cursor_pos - 1
        while start >= 0 and code[start].isalnum() or code[start] == '_':
            start -= 1
        return code[start + 1:cursor_pos]

    def _extract_variables(self, code: str, language: str) -> Set[str]:
        """提取变量名"""
        variables = set()

        if language == "python":
            pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*='
            for match in re.finditer(pattern, code):
                var_name = match.group(1)
                if var_name not in ['if', 'else', 'for', 'while', 'class', 'def']:
                    variables.add(var_name)

        return variables

    def _extract_functions(self, code: str, language: str) -> Set[str]:
        """提取函数名"""
        functions = set()

        if language == "python":
            pattern = r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
            for match in re.finditer(pattern, code):
                functions.add(match.group(1))

        return functions


class CodeAnalyzer:
    """
    代码分析器

    参考 PyLint/Flake8 的实现
    """

    def __init__(self):
        self._rules: Dict[str, Dict[str, Any]] = {
            "python": {
                "E001": {
                    "message": "行太长 ({length} > {max_length})",
                    "severity": "warning",
                },
                "E002": {
                    "message": "缺少空格 around operator",
                    "severity": "info",
                },
                "E003": {
                    "message": "未使用的导入: {name}",
                    "severity": "warning",
                },
                "E004": {
                    "message": "缺少文档字符串",
                    "severity": "info",
                },
                "E005": {
                    "message": "函数/类名称不符合规范",
                    "severity": "info",
                },
            }
        }

    def analyze(self, code: str, language: str = "python") -> List[AnalysisIssue]:
        """分析代码"""
        issues = []

        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            if len(line) > 100:
                issues.append(AnalysisIssue(
                    line=i,
                    column=100,
                    severity="warning",
                    code="E001",
                    message=f"行太长 ({len(line)} > 100)",
                    suggestion="将长行拆分为多行"
                ))

            if re.search(r'[a-zA-Z_]\s*[+\-*/%]\s*[a-zA-Z_]', line):
                issues.append(AnalysisIssue(
                    line=i,
                    column=0,
                    severity="info",
                    code="E002",
                    message="缺少空格 around operator",
                    suggestion="添加空格提高可读性"
                ))

            if language == "python":
                if i == 1 and not line.startswith('"""') and not line.startswith("'''"):
                    if 'def ' in code or 'class ' in code:
                        issues.append(AnalysisIssue(
                            line=1,
                            column=0,
                            severity="info",
                            code="E004",
                            message="模块缺少文档字符串",
                            suggestion="添加模块级文档字符串"
                        ))

                func_pattern = r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
                for match in re.finditer(func_pattern, line):
                    func_name = match.group(1)
                    if not func_name.islower() and not func_name.startswith('_'):
                        issues.append(AnalysisIssue(
                            line=i,
                            column=match.start(),
                            severity="info",
                            code="E005",
                            message=f"函数名 '{func_name}' 应使用小写加下划线",
                            suggestion=f"重命名为 {func_name.lower()}"
                        ))

        return issues

    def get_code_metrics(self, code: str) -> Dict[str, Any]:
        """获取代码度量"""
        lines = code.split('\n')
        non_empty_lines = [l for l in lines if l.strip()]

        return {
            "total_lines": len(lines),
            "code_lines": len(non_empty_lines),
            "blank_lines": len(lines) - len(non_empty_lines),
            "avg_line_length": sum(len(l) for l in non_empty_lines) / max(len(non_empty_lines), 1),
            "max_line_length": max(len(l) for l in lines) if lines else 0,
        }


class ProjectManager:
    """
    项目管理器

    参考 GitPython 的实现
    """

    def __init__(self, project_root: str):
        self.project_root = project_root
        self._files: Dict[str, ProjectFile] = {}
        self._git_status: Dict[str, str] = {}
        self._last_scan = None

    def scan_project(self) -> List[ProjectFile]:
        """扫描项目文件"""
        self._files.clear()

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'venv']]

            for file in files:
                if file.startswith('.'):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.project_root)

                stat = os.stat(full_path)
                language = self._detect_language(file)

                self._files[rel_path] = ProjectFile(
                    path=rel_path,
                    name=file,
                    language=language,
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime),
                )

        self._last_scan = datetime.now()
        return list(self._files.values())

    def _detect_language(self, filename: str) -> Language:
        """检测语言"""
        ext_map = {
            '.py': Language.PYTHON,
            '.js': Language.JAVASCRIPT,
            '.ts': Language.TYPESCRIPT,
            '.java': Language.JAVA,
            '.cpp': Language.CPP,
            '.c': Language.CPP,
            '.go': Language.GO,
            '.rs': Language.RUST,
        }

        _, ext = os.path.splitext(filename)
        return ext_map.get(ext.lower(), Language.UNKNOWN)

    def get_file(self, path: str) -> Optional[ProjectFile]:
        """获取文件信息"""
        return self._files.get(path)

    def search_files(self, query: str, language: Language = None) -> List[ProjectFile]:
        """搜索文件"""
        results = []
        query_lower = query.lower()

        for file in self._files.values():
            if language and file.language != language:
                continue
            if query_lower in file.name.lower():
                results.append(file)

        return results

    def get_git_status(self) -> Dict[str, str]:
        """获取 Git 状态"""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if not line:
                        continue
                    status = line[:2]
                    path = line[3:].strip()
                    self._git_status[path] = status

        except Exception as e:
            print(f"Git status error: {e}")

        return self._git_status

    def git_add(self, path: str) -> bool:
        """Git 添加文件"""
        try:
            result = subprocess.run(
                ["git", "add", path],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def git_commit(self, message: str) -> bool:
        """Git 提交"""
        try:
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取项目统计"""
        language_counts = defaultdict(int)
        total_size = 0

        for file in self._files.values():
            language_counts[file.language.value] += 1
            total_size += file.size

        return {
            "total_files": len(self._files),
            "total_size": total_size,
            "by_language": dict(language_counts),
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
        }


class IDEEnhancer:
    """
    IDE 增强器

    整合代码补全、代码分析、项目管理功能
    """

    def __init__(self, project_root: str = None):
        self.completer = IntelligentCodeCompleter()
        self.analyzer = CodeAnalyzer()
        self.project_manager = ProjectManager(project_root) if project_root else None

    def complete(self, code: str, cursor_pos: int, language: str = "python") -> List[Completion]:
        """智能补全"""
        return self.completer.complete(code, cursor_pos, language)

    def analyze(self, code: str, language: str = "python") -> List[AnalysisIssue]:
        """代码分析"""
        return self.analyzer.analyze(code, language)

    def get_metrics(self, code: str) -> Dict[str, Any]:
        """获取代码度量"""
        return self.analyzer.get_code_metrics(code)

    def scan_project(self) -> List[ProjectFile]:
        """扫描项目"""
        if self.project_manager:
            return self.project_manager.scan_project()
        return []

    def get_project_stats(self) -> Dict[str, Any]:
        """获取项目统计"""
        if self.project_manager:
            return self.project_manager.get_stats()
        return {}


def test_ide_enhancer():
    """测试 IDE 增强器"""
    print("=== 测试 IDE 功能增强 ===")

    enhancer = IDEEnhancer()

    print("\n1. 测试智能代码补全")
    code = """
def hello_world():
    print("Hello")

x = 10
y = 20
result = x + y
"""
    completions = enhancer.complete(code, len(code), "python")
    print(f"  找到 {len(completions)} 个补全项:")
    for c in completions[:5]:
        print(f"    - {c.text} ({c.type})")

    print("\n2. 测试代码分析")
    test_code = """
def MyFunction():
    x=1+2
    some_very_long_line_that_exceeds_one_hundred_characters_in_length_and_should_be_split_into_multiple_lines_for_better_readability
    import os
"""
    issues = enhancer.analyze(test_code)
    print(f"  发现 {len(issues)} 个问题:")
    for issue in issues:
        print(f"    [{issue.severity}] {issue.code}: {issue.message} (行 {issue.line})")

    print("\n3. 测试代码度量")
    metrics = enhancer.get_metrics(test_code)
    print(f"  总行数: {metrics['total_lines']}")
    print(f"  代码行数: {metrics['code_lines']}")
    print(f"  平均行长度: {metrics['avg_line_length']:.1f}")

    print("\n4. 测试项目扫描")
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        enhancer.project_manager = ProjectManager(tmpdir)

        with open(os.path.join(tmpdir, "test.py"), "w") as f:
            f.write("print('hello')")

        files = enhancer.scan_project()
        print(f"  扫描到 {len(files)} 个文件")
        for f in files:
            print(f"    - {f.name} ({f.language.value})")

        stats = enhancer.get_project_stats()
        print(f"  项目统计: {stats}")

    print("\nIDE 功能增强测试完成！")


if __name__ == "__main__":
    test_ide_enhancer()