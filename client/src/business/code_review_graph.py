"""
代码审查图谱 (Code Review Graph)
==============================

参考 code-review-graph 项目理念，构建代码质量图谱：
1. 代码依赖分析
2. 复杂度分析
3. 安全漏洞检测
4. 代码风格评估
5. 性能问题识别

核心特性：
- 构建代码依赖图谱
- 多维度质量评估
- 可视化分析结果
- 智能修复建议

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import ast
import asyncio
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = __import__('logging').getLogger(__name__)


class IssueSeverity(Enum):
    """问题严重程度"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueType(Enum):
    """问题类型"""
    SECURITY = "security"
    PERFORMANCE = "performance"
    COMPLEXITY = "complexity"
    STYLE = "style"
    BUG = "bug"
    MAINTAINABILITY = "maintainability"


@dataclass
class CodeIssue:
    """代码问题"""
    issue_type: IssueType
    severity: IssueSeverity
    message: str
    line_number: int
    column: int = 0
    code_snippet: str = ""
    suggestion: str = ""


@dataclass
class ComplexityMetrics:
    """复杂度指标"""
    cyclomatic_complexity: int = 0
    cognitive_complexity: int = 0
    lines_of_code: int = 0
    functions_count: int = 0
    classes_count: int = 0
    avg_function_length: float = 0.0


@dataclass
class DependencyNode:
    """依赖节点"""
    name: str
    type: str  # function, class, variable, module
    line_number: int
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)


@dataclass
class ReviewResult:
    """审查结果"""
    file_path: str
    issues: List[CodeIssue] = field(default_factory=list)
    complexity: ComplexityMetrics = field(default_factory=ComplexityMetrics)
    dependencies: List[DependencyNode] = field(default_factory=list)
    overall_score: float = 0.0


class CodeReviewGraph:
    """
    代码审查图谱
    
    功能：
    1. 静态代码分析
    2. 复杂度评估
    3. 安全漏洞检测
    4. 代码风格检查
    5. 依赖图谱构建
    """
    
    def __init__(self):
        # 安全敏感函数/模式
        self._security_patterns = {
            "hardcoded_secret": re.compile(
                r'(secret|key|token|password|api[_-]?key)\s*[=:]\s*["\'].*["\']',
                re.IGNORECASE
            ),
            "exec_usage": re.compile(r'\b(exec|eval|compile)\s*\('),
            "sql_string": re.compile(r'\bSELECT\s+.*FROM\s+', re.IGNORECASE),
            "pickle_load": re.compile(r'\b(pickle|marshal)\s*\.\s*(load|loads)\s*\('),
        }
        
        # 性能问题模式
        self._performance_patterns = {
            "list_append_in_loop": re.compile(r'for\s+.*in.*:\s*\n\s*.*\.append\('),
            "global_variable_access": re.compile(r'\bglobal\s+\w+'),
        }
        
        # 风格问题模式
        self._style_patterns = {
            "long_line": re.compile(r'^.{' + str(120) + ',}$'),
            "trailing_whitespace": re.compile(r'\s+$'),
            "missing_docstring": re.compile(r'\b(def|class)\s+\w+\s*:'),
        }
    
    async def analyze(self, code: str, file_path: str = "") -> Dict[str, Any]:
        """
        分析代码（主入口）
        
        Args:
            code: 代码内容
            file_path: 文件路径
            
        Returns:
            分析结果
        """
        result = ReviewResult(file_path=file_path)
        
        # 并行执行各项分析
        tasks = [
            self._analyze_complexity(code),
            self._detect_security_issues(code),
            self._detect_performance_issues(code),
            self._detect_style_issues(code),
            self._build_dependency_graph(code),
        ]
        
        results = await asyncio.gather(*tasks)
        
        result.complexity = results[0]
        result.issues.extend(results[1])
        result.issues.extend(results[2])
        result.issues.extend(results[3])
        result.dependencies = results[4]
        
        # 计算整体评分
        result.overall_score = self._calculate_overall_score(result)
        
        return {
            "file_path": file_path,
            "issues": [self._issue_to_dict(issue) for issue in result.issues],
            "complexity": {
                "cyclomatic_complexity": result.complexity.cyclomatic_complexity,
                "cognitive_complexity": result.complexity.cognitive_complexity,
                "lines_of_code": result.complexity.lines_of_code,
                "functions_count": result.complexity.functions_count,
                "classes_count": result.complexity.classes_count,
                "avg_function_length": result.complexity.avg_function_length,
            },
            "dependencies": [self._node_to_dict(node) for node in result.dependencies],
            "overall_score": result.overall_score,
            "summary": self._generate_summary(result),
        }
    
    async def _analyze_complexity(self, code: str) -> ComplexityMetrics:
        """分析代码复杂度"""
        metrics = ComplexityMetrics()
        
        try:
            tree = ast.parse(code)
            lines = code.split('\n')
            metrics.lines_of_code = len([l for l in lines if l.strip()])
            
            # 计算圈复杂度和认知复杂度
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    metrics.functions_count += 1
                    metrics.cyclomatic_complexity += self._calculate_cyclomatic_complexity(node)
                    metrics.cognitive_complexity += self._calculate_cognitive_complexity(node)
                elif isinstance(node, ast.ClassDef):
                    metrics.classes_count += 1
            
            # 计算平均函数长度
            if metrics.functions_count > 0:
                metrics.avg_function_length = metrics.lines_of_code / metrics.functions_count
            
        except SyntaxError:
            pass
        
        return metrics
    
    def _calculate_cyclomatic_complexity(self, node: ast.FunctionDef) -> int:
        """计算圈复杂度"""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.Try)):
                complexity += 1
            elif isinstance(child, ast.IfExp):
                complexity += 1
        return complexity
    
    def _calculate_cognitive_complexity(self, node: ast.FunctionDef) -> int:
        """计算认知复杂度"""
        complexity = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.Try)):
                complexity += 1
            elif isinstance(child, ast.IfExp):
                complexity += 1
        return complexity
    
    async def _detect_security_issues(self, code: str) -> List[CodeIssue]:
        """检测安全问题"""
        issues = []
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, start=1):
            for pattern_name, pattern in self._security_patterns.items():
                if pattern.search(line):
                    severity = IssueSeverity.CRITICAL if pattern_name == "hardcoded_secret" else IssueSeverity.HIGH
                    issues.append(CodeIssue(
                        issue_type=IssueType.SECURITY,
                        severity=severity,
                        message=self._get_security_message(pattern_name),
                        line_number=line_num,
                        code_snippet=line.strip(),
                        suggestion=self._get_security_suggestion(pattern_name),
                    ))
        
        return issues
    
    def _get_security_message(self, pattern_name: str) -> str:
        """获取安全问题消息"""
        messages = {
            "hardcoded_secret": "检测到硬编码的敏感信息",
            "exec_usage": "检测到危险的执行函数调用",
            "sql_string": "检测到可能的SQL注入风险",
            "pickle_load": "检测到不安全的反序列化操作",
        }
        return messages.get(pattern_name, "检测到安全问题")
    
    def _get_security_suggestion(self, pattern_name: str) -> str:
        """获取安全建议"""
        suggestions = {
            "hardcoded_secret": "建议将敏感信息存储在环境变量或配置文件中",
            "exec_usage": "建议避免使用 exec/eval，改用更安全的方式",
            "sql_string": "建议使用参数化查询防止SQL注入",
            "pickle_load": "建议使用安全的序列化格式如JSON",
        }
        return suggestions.get(pattern_name, "")
    
    async def _detect_performance_issues(self, code: str) -> List[CodeIssue]:
        """检测性能问题"""
        issues = []
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, start=1):
            for pattern_name, pattern in self._performance_patterns.items():
                if pattern.search(line):
                    issues.append(CodeIssue(
                        issue_type=IssueType.PERFORMANCE,
                        severity=IssueSeverity.MEDIUM,
                        message=self._get_performance_message(pattern_name),
                        line_number=line_num,
                        code_snippet=line.strip(),
                        suggestion=self._get_performance_suggestion(pattern_name),
                    ))
        
        return issues
    
    def _get_performance_message(self, pattern_name: str) -> str:
        """获取性能问题消息"""
        messages = {
            "list_append_in_loop": "检测到循环内的列表追加操作",
            "global_variable_access": "检测到频繁的全局变量访问",
        }
        return messages.get(pattern_name, "检测到性能问题")
    
    def _get_performance_suggestion(self, pattern_name: str) -> str:
        """获取性能建议"""
        suggestions = {
            "list_append_in_loop": "建议预先计算列表大小或使用列表推导式",
            "global_variable_access": "建议将全局变量赋值给局部变量后使用",
        }
        return suggestions.get(pattern_name, "")
    
    async def _detect_style_issues(self, code: str) -> List[CodeIssue]:
        """检测代码风格问题"""
        issues = []
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, start=1):
            # 检测行长
            if len(line) > 120:
                issues.append(CodeIssue(
                    issue_type=IssueType.STYLE,
                    severity=IssueSeverity.LOW,
                    message="代码行过长（超过120字符）",
                    line_number=line_num,
                    code_snippet=line[:50] + "..." if len(line) > 50 else line,
                    suggestion="建议将长行拆分为多行",
                ))
            
            # 检测尾随空格
            if self._style_patterns["trailing_whitespace"].search(line):
                issues.append(CodeIssue(
                    issue_type=IssueType.STYLE,
                    severity=IssueSeverity.INFO,
                    message="检测到尾随空格",
                    line_number=line_num,
                    suggestion="建议删除尾随空格",
                ))
        
        return issues
    
    async def _build_dependency_graph(self, code: str) -> List[DependencyNode]:
        """构建依赖图谱"""
        nodes = []
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    dependencies = []
                    for child in ast.walk(node):
                        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                            dependencies.append(child.id)
                    
                    nodes.append(DependencyNode(
                        name=node.name,
                        type="function",
                        line_number=node.lineno,
                        dependencies=list(set(dependencies)),
                    ))
                
                elif isinstance(node, ast.ClassDef):
                    nodes.append(DependencyNode(
                        name=node.name,
                        type="class",
                        line_number=node.lineno,
                    ))
                
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        nodes.append(DependencyNode(
                            name=alias.name,
                            type="module",
                            line_number=node.lineno,
                        ))
                
                elif isinstance(node, ast.ImportFrom):
                    module_name = node.module or ""
                    for alias in node.names:
                        full_name = f"{module_name}.{alias.name}" if module_name else alias.name
                        nodes.append(DependencyNode(
                            name=full_name,
                            type="module",
                            line_number=node.lineno,
                        ))
            
            # 计算依赖关系
            for node in nodes:
                for other in nodes:
                    if node != other and node.name in other.dependencies:
                        node.dependents.append(other.name)
        
        except SyntaxError:
            pass
        
        return nodes
    
    def _calculate_overall_score(self, result: ReviewResult) -> float:
        """计算整体评分"""
        score = 100.0
        
        # 基于复杂度扣分
        if result.complexity.cyclomatic_complexity > 15:
            score -= (result.complexity.cyclomatic_complexity - 15) * 2
        if result.complexity.cognitive_complexity > 20:
            score -= (result.complexity.cognitive_complexity - 20) * 1.5
        
        # 基于问题扣分
        for issue in result.issues:
            if issue.severity == IssueSeverity.CRITICAL:
                score -= 20
            elif issue.severity == IssueSeverity.HIGH:
                score -= 10
            elif issue.severity == IssueSeverity.MEDIUM:
                score -= 5
            elif issue.severity == IssueSeverity.LOW:
                score -= 2
        
        return max(0.0, min(100.0, score))
    
    def _generate_summary(self, result: ReviewResult) -> Dict[str, Any]:
        """生成摘要"""
        critical_count = sum(1 for i in result.issues if i.severity == IssueSeverity.CRITICAL)
        high_count = sum(1 for i in result.issues if i.severity == IssueSeverity.HIGH)
        medium_count = sum(1 for i in result.issues if i.severity == IssueSeverity.MEDIUM)
        low_count = sum(1 for i in result.issues if i.severity == IssueSeverity.LOW)
        
        return {
            "total_issues": len(result.issues),
            "critical_issues": critical_count,
            "high_issues": high_count,
            "medium_issues": medium_count,
            "low_issues": low_count,
            "complexity_level": self._get_complexity_level(result.complexity),
            "recommendation": self._get_recommendation(result),
        }
    
    def _get_complexity_level(self, metrics: ComplexityMetrics) -> str:
        """获取复杂度级别"""
        if metrics.cyclomatic_complexity > 20:
            return "高"
        elif metrics.cyclomatic_complexity > 10:
            return "中"
        else:
            return "低"
    
    def _get_recommendation(self, result: ReviewResult) -> str:
        """获取建议"""
        if result.overall_score >= 90:
            return "代码质量优秀，无需修改"
        elif result.overall_score >= 70:
            return "代码质量良好，建议修复发现的问题"
        elif result.overall_score >= 50:
            return "代码需要改进，建议重构关键部分"
        else:
            return "代码质量较差，建议全面审查和重构"
    
    def _issue_to_dict(self, issue: CodeIssue) -> Dict[str, Any]:
        """将问题转换为字典"""
        return {
            "type": issue.issue_type.value,
            "severity": issue.severity.value,
            "message": issue.message,
            "line_number": issue.line_number,
            "column": issue.column,
            "code_snippet": issue.code_snippet,
            "suggestion": issue.suggestion,
        }
    
    def _node_to_dict(self, node: DependencyNode) -> Dict[str, Any]:
        """将节点转换为字典"""
        return {
            "name": node.name,
            "type": node.type,
            "line_number": node.line_number,
            "dependencies": node.dependencies,
            "dependents": node.dependents,
        }


# 便捷函数
def create_code_review_graph() -> CodeReviewGraph:
    """创建代码审查图谱实例"""
    return CodeReviewGraph()


__all__ = [
    "IssueSeverity",
    "IssueType",
    "CodeIssue",
    "ComplexityMetrics",
    "DependencyNode",
    "ReviewResult",
    "CodeReviewGraph",
    "create_code_review_graph",
]
