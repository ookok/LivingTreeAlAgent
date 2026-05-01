"""
代码质量分析器 - 分析代码质量并提供重构建议
"""

import ast
import os
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class QualityMetrics:
    """质量指标"""
    file_path: str
    total_lines: int
    blank_lines: int
    comment_lines: int
    function_count: int
    class_count: int
    cyclomatic_complexity: int
    halstead_volume: float
    maintainability_index: float
    code_duplication: float
    longest_function: int
    average_function_length: float

@dataclass
class RefactoringSuggestion:
    """重构建议"""
    file_path: str
    line_number: int
    severity: str  # low, medium, high, critical
    category: str  # complexity, duplication, naming, security, performance
    description: str
    suggestion: str

class QualityAnalyzer:
    """代码质量分析器"""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
    
    def analyze_file(self, file_path: str) -> QualityMetrics:
        """分析单个文件质量"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            tree = ast.parse(content)
            
            metrics = self._calculate_metrics(lines, tree, content)
            return metrics
        except Exception as e:
            print(f"分析文件失败 {file_path}: {e}")
            return None
    
    def _calculate_metrics(self, lines: List[str], tree: ast.AST, content: str) -> QualityMetrics:
        """计算质量指标"""
        total_lines = len(lines)
        blank_lines = sum(1 for line in lines if line.strip() == "")
        comment_lines = sum(1 for line in lines if line.strip().startswith('#'))
        
        function_count = 0
        class_count = 0
        total_function_length = 0
        longest_function = 0
        cyclomatic_complexity = 1
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                function_count += 1
                func_length = node.end_lineno - node.lineno + 1
                total_function_length += func_length
                longest_function = max(longest_function, func_length)
                cyclomatic_complexity += self._count_complexity(node)
            elif isinstance(node, ast.ClassDef):
                class_count += 1
        
        avg_func_length = total_function_length / function_count if function_count > 0 else 0
        
        halstead = self._calculate_halstead(tree)
        mi = self._calculate_maintainability(total_lines, comment_lines, cyclomatic_complexity, halstead)
        duplication = self._calculate_duplication(lines)
        
        return QualityMetrics(
            file_path=str(self.repo_path / "dummy.py"),
            total_lines=total_lines,
            blank_lines=blank_lines,
            comment_lines=comment_lines,
            function_count=function_count,
            class_count=class_count,
            cyclomatic_complexity=cyclomatic_complexity,
            halstead_volume=halstead,
            maintainability_index=mi,
            code_duplication=duplication,
            longest_function=longest_function,
            average_function_length=avg_func_length
        )
    
    def _count_complexity(self, node) -> int:
        """计算节点圈复杂度"""
        count = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.IfExp)):
                count += 1
            elif isinstance(child, ast.Try):
                count += len(child.handlers)
        return count
    
    def _calculate_halstead(self, tree) -> float:
        """计算Halstead体积"""
        operators = set()
        operands = set()
        operator_count = 0
        operand_count = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.operator):
                operators.add(type(node).__name__)
                operator_count += 1
            elif isinstance(node, ast.Constant):
                operands.add(str(node.value))
                operand_count += 1
            elif isinstance(node, ast.Name):
                operands.add(node.id)
                operand_count += 1
        
        if len(operators) == 0 or len(operands) == 0:
            return 0
        
        vocabulary = len(operators) + len(operands)
        volume = (operator_count + operand_count) * (vocabulary).bit_length()
        return volume
    
    def _calculate_maintainability(self, total_lines: int, comment_lines: int, complexity: int, halstead: float) -> float:
        """计算可维护性指数"""
        if total_lines == 0:
            return 0
        
        comment_ratio = comment_lines / total_lines
        mi = max(0, 171 - 5.2 * (halstead / total_lines) - 0.23 * complexity - 16.2 * comment_ratio)
        return mi
    
    def _calculate_duplication(self, lines: List[str]) -> float:
        """计算代码重复率"""
        stripped_lines = [line.strip() for line in lines if line.strip()]
        unique_lines = set(stripped_lines)
        return 1 - (len(unique_lines) / len(stripped_lines)) if stripped_lines else 0
    
    def analyze_project(self) -> Dict[str, QualityMetrics]:
        """分析整个项目"""
        results = {}
        
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules']]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    metrics = self.analyze_file(file_path)
                    if metrics:
                        results[file_path] = metrics
        
        return results
    
    def get_refactoring_suggestions(self, file_path: str) -> List[RefactoringSuggestion]:
        """获取重构建议"""
        suggestions = []
        metrics = self.analyze_file(file_path)
        
        if not metrics:
            return suggestions
        
        # 复杂度问题
        if metrics.cyclomatic_complexity > 15:
            suggestions.append(RefactoringSuggestion(
                file_path=file_path,
                line_number=1,
                severity='high',
                category='complexity',
                description=f"文件圈复杂度过高 ({metrics.cyclomatic_complexity})",
                suggestion="建议拆分函数，降低单个函数复杂度"
            ))
        
        # 重复代码问题
        if metrics.code_duplication > 0.3:
            suggestions.append(RefactoringSuggestion(
                file_path=file_path,
                line_number=1,
                severity='medium',
                category='duplication',
                description=f"代码重复率较高 ({metrics.code_duplication:.1%})",
                suggestion="建议抽取公共代码为函数或类"
            ))
        
        # 函数过长问题
        if metrics.average_function_length > 50:
            suggestions.append(RefactoringSuggestion(
                file_path=file_path,
                line_number=1,
                severity='medium',
                category='complexity',
                description=f"平均函数长度过长 ({metrics.average_function_length:.1f}行)",
                suggestion="建议拆分过长的函数"
            ))
        
        # 可维护性问题
        if metrics.maintainability_index < 65:
            suggestions.append(RefactoringSuggestion(
                file_path=file_path,
                line_number=1,
                severity='high',
                category='complexity',
                description=f"可维护性指数较低 ({metrics.maintainability_index:.1f})",
                suggestion="建议增加注释，降低复杂度"
            ))
        
        # 检查命名规范
        suggestions.extend(self._check_naming_conventions(file_path))
        
        # 检查潜在安全问题
        suggestions.extend(self._check_security_issues(file_path))
        
        return suggestions
    
    def _check_naming_conventions(self, file_path: str) -> List[RefactoringSuggestion]:
        """检查命名规范"""
        suggestions = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not node.name.islower() or '_' not in node.name and len(node.name) > 1:
                        suggestions.append(RefactoringSuggestion(
                            file_path=file_path,
                            line_number=node.lineno,
                            severity='low',
                            category='naming',
                            description=f"函数 '{node.name}' 命名不符合 snake_case 规范",
                            suggestion="建议使用 snake_case 命名规范"
                        ))
                
                elif isinstance(node, ast.ClassDef):
                    if not node.name[0].isupper():
                        suggestions.append(RefactoringSuggestion(
                            file_path=file_path,
                            line_number=node.lineno,
                            severity='low',
                            category='naming',
                            description=f"类 '{node.name}' 命名不符合 PascalCase 规范",
                            suggestion="建议使用 PascalCase 命名规范"
                        ))
        
        except Exception as e:
            pass
        
        return suggestions
    
    def _check_security_issues(self, file_path: str) -> List[RefactoringSuggestion]:
        """检查安全问题"""
        suggestions = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检测潜在的安全问题
            security_patterns = [
                (r'eval\(', 'eval函数使用', 'high'),
                (r'exec\(', 'exec函数使用', 'high'),
                (r'os\.system\(', 'os.system调用', 'medium'),
                (r'subprocess\.Popen\(', 'subprocess调用', 'medium'),
                (r'pickle\.load', 'pickle反序列化', 'high'),
                (r'__reduce__', 'pickle魔术方法', 'high')
            ]
            
            for pattern, desc, severity in security_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    line_num = content.count('\n', 0, match.start()) + 1
                    suggestions.append(RefactoringSuggestion(
                        file_path=file_path,
                        line_number=line_num,
                        severity=severity,
                        category='security',
                        description=f"检测到 {desc}",
                        suggestion="请确认此代码是否安全，避免使用危险函数"
                    ))
        
        except Exception as e:
            pass
        
        return suggestions
    
    def get_project_quality_summary(self) -> Dict[str, Any]:
        """获取项目质量汇总"""
        all_metrics = self.analyze_project()
        
        if not all_metrics:
            return {}
        
        avg_complexity = sum(m.cyclomatic_complexity for m in all_metrics.values()) / len(all_metrics)
        avg_maintainability = sum(m.maintainability_index for m in all_metrics.values()) / len(all_metrics)
        avg_duplication = sum(m.code_duplication for m in all_metrics.values()) / len(all_metrics)
        
        return {
            'total_files': len(all_metrics),
            'average_complexity': avg_complexity,
            'average_maintainability': avg_maintainability,
            'average_duplication': avg_duplication,
            'high_risk_files': sum(1 for m in all_metrics.values() if m.cyclomatic_complexity > 15),
            'low_maintainability_files': sum(1 for m in all_metrics.values() if m.maintainability_index < 65)
        }