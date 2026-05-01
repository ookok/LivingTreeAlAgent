"""
代码分析器 - 深度代码理解

核心功能：
1. 代码复杂度分析
2. 代码质量评估
3. 安全漏洞检测
4. 代码优化建议
5. 依赖关系分析
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
from pathlib import Path

from .code_parser import CodeParser, LanguageSupport, CodeStructure, SymbolInfo


class ComplexityLevel(Enum):
    """复杂度级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueSeverity(Enum):
    """问题严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class CodeIssue:
    """代码问题"""
    code: str
    message: str
    severity: IssueSeverity
    line: int
    column: int
    suggestion: Optional[str] = None


@dataclass
class ComplexityMetrics:
    """复杂度指标"""
    cyclomatic_complexity: int
    cognitive_complexity: int
    lines_of_code: int
    functions_count: int
    classes_count: int
    nesting_depth: int
    halstead_volume: float


@dataclass
class QualityReport:
    """质量报告"""
    complexity: ComplexityMetrics
    issues: List[CodeIssue]
    maintainability_score: float
    security_score: float
    overall_score: float


class CodeAnalyzer:
    """
    代码分析器 - 深度代码理解
    
    核心特性：
    1. 代码复杂度分析
    2. 代码质量评估
    3. 安全漏洞检测
    4. 代码优化建议
    """

    def __init__(self):
        self._parser = CodeParser()
        self._security_patterns = [
            (r'(password|secret|token|api[_-]key)\s*[=:]\s*["\'][^"\']*["\']', "hardcoded_secret", IssueSeverity.CRITICAL),
            (r'exec\s*\(', "exec_usage", IssueSeverity.ERROR),
            (r'eval\s*\(', "eval_usage", IssueSeverity.ERROR),
            (r'pickle\.load', "unsafe_deserialization", IssueSeverity.CRITICAL),
            (r'yaml\.load', "unsafe_deserialization", IssueSeverity.ERROR),
            (r'subprocess\.Popen\s*\(\s*["\']', "shell_injection", IssueSeverity.ERROR),
            (r'open\s*\(\s*[^)]*(\.\.\/|\.\.\\\\)', "path_traversal", IssueSeverity.ERROR),
            (r'(\bSELECT\b.*\bFROM\b.*\bWHERE\b.*)\s*=\s*["\'].*["\']', "sql_injection", IssueSeverity.CRITICAL),
        ]

    def analyze(self, code: str, language: Optional[LanguageSupport] = None) -> QualityReport:
        """分析代码质量"""
        lang = language or self._detect_language(code)
        
        # 解析代码结构
        structure = self._parser.parse(code, lang)
        
        # 计算复杂度指标
        complexity = self._calculate_complexity(code, structure)
        
        # 检测问题
        issues = []
        issues.extend(self._detect_security_issues(code))
        issues.extend(self._detect_code_smells(code, structure))
        issues.extend(self._detect_style_issues(code))
        
        # 计算评分
        maintainability = self._calculate_maintainability(complexity, issues)
        security = self._calculate_security_score(issues)
        overall = (maintainability + security) / 2
        
        return QualityReport(
            complexity=complexity,
            issues=issues,
            maintainability_score=maintainability,
            security_score=security,
            overall_score=overall
        )

    def _detect_language(self, code: str) -> LanguageSupport:
        """简单检测语言"""
        if code.strip().startswith('<?php'):
            return LanguageSupport.PYTHON  # 默认
        
        # 基于关键字检测
        keywords = {
            LanguageSupport.PYTHON: ['def', 'import', 'class', 'self', 'print('],
            LanguageSupport.JAVA: ['public', 'private', 'void', 'class', 'import'],
            LanguageSupport.JAVASCRIPT: ['const', 'let', 'var', 'function', 'import'],
            LanguageSupport.GO: ['func', 'package', 'import', 'var'],
            LanguageSupport.RUST: ['fn', 'let', 'use', 'struct', 'enum'],
            LanguageSupport.SQL: ['SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE']
        }
        
        for lang, kw_list in keywords.items():
            count = sum(1 for kw in kw_list if kw in code)
            if count >= 2:
                return lang
        
        return LanguageSupport.PYTHON

    def _calculate_complexity(self, code: str, structure: CodeStructure) -> ComplexityMetrics:
        """计算复杂度指标"""
        lines = code.split('\n')
        
        # 计算圈复杂度（简化版）
        cyclomatic = 1
        for line in lines:
            line = line.strip()
            if line.startswith('if') or line.startswith('elif'):
                cyclomatic += 1
            if '&&' in line or '||' in line or 'and' in line or 'or' in line:
                cyclomatic += line.count('&&') + line.count('||') + line.count(' and ') + line.count(' or ')
        
        # 计算认知复杂度
        cognitive = 0
        nesting = 0
        max_nesting = 0
        
        for line in lines:
            line = line.lstrip()
            indent = len(line) - len(line.lstrip())
            
            if 'if' in line or 'for' in line or 'while' in line:
                nesting += 1
                cognitive += nesting
                max_nesting = max(max_nesting, nesting)
            
            if line.strip() and not line.startswith(' ') and nesting > 0:
                nesting -= 1
        
        # Halstead体积（简化版）
        operators = ['+', '-', '*', '/', '=', '==', '!=', '<', '>', '<=', '>=', 'and', 'or', 'not']
        operands = re.findall(r'\b([a-zA-Z_]\w*)\b', code)
        
        unique_operators = len(set(op for op in operators if op in code))
        unique_operands = len(set(operands))
        
        halstead = 0
        if unique_operators > 0 and unique_operands > 0:
            halstead = (unique_operators + unique_operands) * len(lines) / 100
        
        return ComplexityMetrics(
            cyclomatic_complexity=cyclomatic,
            cognitive_complexity=cognitive,
            lines_of_code=len(lines),
            functions_count=len(structure.functions),
            classes_count=len(structure.classes),
            nesting_depth=max_nesting,
            halstead_volume=halstead
        )

    def _detect_security_issues(self, code: str) -> List[CodeIssue]:
        """检测安全问题"""
        issues = []
        lines = code.split('\n')
        
        for pattern, code_name, severity in self._security_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                issues.append(CodeIssue(
                    code=code_name,
                    message=self._get_issue_message(code_name),
                    severity=severity,
                    line=line_num,
                    column=0,
                    suggestion=self._get_fix_suggestion(code_name)
                ))
        
        return issues

    def _get_issue_message(self, code: str) -> str:
        """获取问题消息"""
        messages = {
            "hardcoded_secret": "发现硬编码的敏感信息",
            "exec_usage": "使用了危险的 exec() 函数",
            "eval_usage": "使用了危险的 eval() 函数",
            "unsafe_deserialization": "使用了不安全的反序列化方法",
            "shell_injection": "存在命令注入风险",
            "path_traversal": "存在路径遍历风险",
            "sql_injection": "存在SQL注入风险"
        }
        return messages.get(code, f"检测到安全问题: {code}")

    def _get_fix_suggestion(self, code: str) -> str:
        """获取修复建议"""
        suggestions = {
            "hardcoded_secret": "将敏感信息存储在环境变量或配置文件中",
            "exec_usage": "避免使用 exec()，考虑使用更安全的方法",
            "eval_usage": "避免使用 eval()，考虑使用 ast.literal_eval()",
            "unsafe_deserialization": "使用安全的序列化格式如 JSON",
            "shell_injection": "使用 subprocess.run() 的列表参数形式",
            "path_traversal": "对路径进行规范化和验证",
            "sql_injection": "使用参数化查询"
        }
        return suggestions.get(code, None)

    def _detect_code_smells(self, code: str, structure: CodeStructure) -> List[CodeIssue]:
        """检测代码异味"""
        issues = []
        lines = code.split('\n')
        
        # 检测过长的函数
        func_line_counts = {}
        current_func = None
        func_start = 0
        
        for i, line in enumerate(lines, 1):
            if line.strip().startswith('def ') or line.strip().startswith('function '):
                if current_func:
                    func_line_counts[current_func] = i - func_start
                current_func = line.split()[1].split('(')[0]
                func_start = i
        
        if current_func:
            func_line_counts[current_func] = len(lines) - func_start + 1
        
        for func, count in func_line_counts.items():
            if count > 100:
                issues.append(CodeIssue(
                    code="long_function",
                    message=f"函数 {func} 过长 ({count} 行)",
                    severity=IssueSeverity.WARNING,
                    line=func_start,
                    column=0,
                    suggestion="考虑将函数拆分为多个小函数"
                ))
        
        # 检测重复代码（简化版）
        line_counts = {}
        for i, line in enumerate(lines):
            stripped = line.strip()
            if len(stripped) > 20:
                line_counts[stripped] = line_counts.get(stripped, []) + [i + 1]
        
        for line_text, occurrences in line_counts.items():
            if len(occurrences) >= 5:
                issues.append(CodeIssue(
                    code="duplicate_code",
                    message=f"检测到重复代码模式",
                    severity=IssueSeverity.WARNING,
                    line=occurrences[0],
                    column=0,
                    suggestion="考虑提取为函数或使用循环"
                ))
        
        # 检测未使用的变量
        used_vars = set()
        defined_vars = set()
        
        for symbol in structure.symbols:
            if symbol.type == 'variable':
                defined_vars.add(symbol.name)
        
        # 简单的使用检测
        for var in defined_vars:
            if code.count(var) == 1:  # 只出现一次（定义时）
                issues.append(CodeIssue(
                    code="unused_variable",
                    message=f"变量 {var} 定义后未使用",
                    severity=IssueSeverity.INFO,
                    line=1,
                    column=0,
                    suggestion="删除未使用的变量或使用它"
                ))
        
        return issues

    def _detect_style_issues(self, code: str) -> List[CodeIssue]:
        """检测风格问题"""
        issues = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            # 检测过长的行
            if len(line) > 120:
                issues.append(CodeIssue(
                    code="long_line",
                    message=f"行过长 ({len(line)} 字符)",
                    severity=IssueSeverity.INFO,
                    line=i,
                    column=0,
                    suggestion="考虑拆分长行"
                ))
            
            # 检测尾随空格
            if line.rstrip() != line:
                issues.append(CodeIssue(
                    code="trailing_whitespace",
                    message="行尾有尾随空格",
                    severity=IssueSeverity.INFO,
                    line=i,
                    column=0,
                    suggestion="删除尾随空格"
                ))
        
        return issues

    def _calculate_maintainability(self, complexity: ComplexityMetrics, issues: List[CodeIssue]) -> float:
        """计算可维护性评分"""
        score = 100.0
        
        # 基于圈复杂度
        if complexity.cyclomatic_complexity > 10:
            score -= min(30, (complexity.cyclomatic_complexity - 10) * 3)
        
        # 基于嵌套深度
        if complexity.nesting_depth > 4:
            score -= min(20, (complexity.nesting_depth - 4) * 5)
        
        # 基于问题数量
        warning_count = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
        error_count = sum(1 for i in issues if i.severity in [IssueSeverity.ERROR, IssueSeverity.CRITICAL])
        
        score -= warning_count * 2
        score -= error_count * 5
        
        return max(0, min(100, score)) / 100

    def _calculate_security_score(self, issues: List[CodeIssue]) -> float:
        """计算安全评分"""
        score = 100.0
        
        for issue in issues:
            if issue.severity == IssueSeverity.CRITICAL:
                score -= 25
            elif issue.severity == IssueSeverity.ERROR:
                score -= 15
            elif issue.severity == IssueSeverity.WARNING:
                score -= 5
        
        return max(0, min(100, score)) / 100

    def get_complexity_level(self, complexity: ComplexityMetrics) -> ComplexityLevel:
        """获取复杂度级别"""
        if complexity.cyclomatic_complexity > 20 or complexity.cognitive_complexity > 30:
            return ComplexityLevel.CRITICAL
        elif complexity.cyclomatic_complexity > 10 or complexity.cognitive_complexity > 15:
            return ComplexityLevel.HIGH
        elif complexity.cyclomatic_complexity > 5 or complexity.cognitive_complexity > 8:
            return ComplexityLevel.MEDIUM
        else:
            return ComplexityLevel.LOW

    def generate_optimization_suggestions(self, code: str) -> List[str]:
        """生成优化建议"""
        report = self.analyze(code)
        suggestions = []
        
        for issue in report.issues:
            if issue.suggestion:
                suggestions.append(f"• {issue.suggestion}")
        
        if report.complexity.cyclomatic_complexity > 10:
            suggestions.append("• 考虑重构以降低圈复杂度")
        
        if report.maintainability_score < 0.7:
            suggestions.append("• 代码可维护性较低，建议进行重构")
        
        return suggestions


def get_code_analyzer() -> CodeAnalyzer:
    """获取代码分析器实例"""
    return CodeAnalyzer()