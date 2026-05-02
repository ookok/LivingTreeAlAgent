"""
模式识别器 (Pattern Recognizer)

代码模式和反模式检测：
- 设计模式识别（单例、工厂、观察者、策略等）
- 反模式检测（God Object、Dead Code、Magic Numbers 等）
- 最佳实践违规检测
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PatternType(Enum):
    DESIGN_PATTERN = "design_pattern"
    ANTI_PATTERN = "anti_pattern"
    CODE_SMELL = "code_smell"
    BEST_PRACTICE = "best_practice"


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class CodePattern:
    pattern_id: str
    name: str
    pattern_type: PatternType
    description: str = ""
    severity: Severity = Severity.WARNING
    file_path: str = ""
    line: int = 0
    snippet: str = ""
    suggestion: str = ""


class PatternRecognizer:

    def __init__(self):
        self._patterns: Dict[str, CodePattern] = {}
        self._init_known_patterns()

    def _init_known_patterns(self):
        patterns = [
            CodePattern(
                pattern_id="god_object",
                name="God Object",
                pattern_type=PatternType.ANTI_PATTERN,
                description="类过大，承担了过多职责",
                severity=Severity.ERROR,
                suggestion="将大类拆分为多个单一职责的类"),
            CodePattern(
                pattern_id="long_method",
                name="Long Method",
                pattern_type=PatternType.CODE_SMELL,
                description="方法过长，超过 50 行",
                severity=Severity.WARNING,
                suggestion="提取子方法，减少方法长度"),
            CodePattern(
                pattern_id="too_many_params",
                name="Too Many Parameters",
                pattern_type=PatternType.CODE_SMELL,
                description="方法参数超过 5 个",
                severity=Severity.WARNING,
                suggestion="使用数据对象或参数对象封装参数"),
            CodePattern(
                pattern_id="magic_number",
                name="Magic Number",
                pattern_type=PatternType.CODE_SMELL,
                description="代码中使用了未命名的数值常量",
                severity=Severity.INFO,
                suggestion="将数值提取为命名常量"),
            CodePattern(
                pattern_id="dead_code",
                name="Dead Code",
                pattern_type=PatternType.CODE_SMELL,
                description="未被引用的代码或注释掉的代码",
                severity=Severity.INFO,
                suggestion="删除未使用的代码"),
            CodePattern(
                pattern_id="duplicate_code",
                name="Duplicate Code",
                pattern_type=PatternType.ANTI_PATTERN,
                description="重复的代码块",
                severity=Severity.WARNING,
                suggestion="提取公共方法，消除重复"),
        ]
        for p in patterns:
            self._patterns[p.pattern_id] = p

    def add_pattern(self, pattern: CodePattern):
        self._patterns[pattern.pattern_id] = pattern

    def analyze(self, source: str, file_path: str = "") -> List[CodePattern]:
        findings = []

        findings.extend(self._detect_long_methods(source, file_path))
        findings.extend(self._detect_magic_numbers(source, file_path))
        findings.extend(self._detect_too_many_params(source, file_path))

        return findings

    def _detect_long_methods(self, source: str,
                             file_path: str) -> List[CodePattern]:
        findings = []
        lines = source.splitlines()
        in_method = False
        method_start = 0
        method_name = ""
        indent_level = 0
        method_lines = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if (stripped.startswith("def ") or stripped.startswith("async def ")):
                in_method = True
                method_start = i
                method_lines = 1
                indent_level = len(line) - len(line.lstrip())
                match = re.search(r'def\s+(\w+)', stripped)
                method_name = match.group(1) if match else "unknown"
            elif in_method:
                if stripped and (len(line) - len(line.lstrip()) <= indent_level
                                and not stripped.startswith(('#', '@', '"""'))):
                    method_end = i - 1
                    if method_lines > 50:
                        findings.append(CodePattern(
                            pattern_id="long_method",
                            name="Long Method",
                            pattern_type=PatternType.CODE_SMELL,
                            description=f"方法 '{method_name}' 共 {method_lines} 行 > 50",
                            file_path=file_path,
                            line=method_start,
                            suggestion=self._patterns["long_method"].suggestion))
                    in_method = False
                else:
                    method_lines += 1

        return findings

    def _detect_magic_numbers(self, source: str,
                              file_path: str) -> List[CodePattern]:
        findings = []
        magic_pattern = re.compile(
            r'(?<![a-zA-Z_"\'])\b(\d{2,}|[2-9]\d+)(?![a-zA-Z_])')

        for i, line in enumerate(source.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith(('#', 'import', 'from', '"', "'")):
                continue
            matches = magic_pattern.findall(stripped)
            for match in matches:
                num = int(match)
                if num > 1 and num not in (2, 10, 60, 100, 1000):
                    findings.append(CodePattern(
                        pattern_id="magic_number",
                        name="Magic Number",
                        pattern_type=PatternType.CODE_SMELL,
                        description=f"Magic number '{num}' 在行 {i}",
                        file_path=file_path, line=i,
                        snippet=stripped,
                        suggestion=self._patterns["magic_number"].suggestion))

        return findings

    def _detect_too_many_params(self, source: str,
                                file_path: str) -> List[CodePattern]:
        findings = []
        param_pattern = re.compile(r'def\s+(\w+)\s*\((.*?)\)')

        for i, line in enumerate(source.splitlines(), 1):
            match = param_pattern.search(line)
            if match:
                method_name = match.group(1)
                params = [p.strip() for p in match.group(2).split(',')
                         if p.strip() and p.strip() != 'self']
                if len(params) > 5 and method_name != '__init__':
                    findings.append(CodePattern(
                        pattern_id="too_many_params",
                        name="Too Many Parameters",
                        pattern_type=PatternType.CODE_SMELL,
                        description=f"方法 '{method_name}' 有 {len(params)} 个参数",
                        file_path=file_path, line=i,
                        suggestion=self._patterns["too_many_params"].suggestion))

        return findings

    def get_available_patterns(self) -> List[CodePattern]:
        return list(self._patterns.values())


__all__ = [
    "PatternType", "Severity", "CodePattern",
    "PatternRecognizer",
]
