"""
问题检测器 - 检测和诊断系统问题
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import re
import traceback
import time


class ProblemSeverity(Enum):
    """问题严重性"""
    CRITICAL = "critical"    # 致命问题
    HIGH = "high"          # 高优先级
    MEDIUM = "medium"      # 中优先级
    LOW = "low"            # 低优先级
    INFO = "info"          # 信息


class ProblemCategory(Enum):
    """问题类别"""
    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    IMPORT_ERROR = "import_error"
    LOGIC_ERROR = "logic_error"
    PERFORMANCE = "performance"
    MEMORY_LEAK = "memory_leak"
    UI_BUG = "ui_bug"
    CONFIG_ERROR = "config_error"
    UNKNOWN = "unknown"


@dataclass
class ProblemReport:
    """问题报告"""
    problem_id: str
    category: ProblemCategory
    severity: ProblemSeverity
    title: str
    description: str
    location: Optional[Dict[str, Any]] = None
    traceback: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class ProblemDetector:
    """
    问题检测器
    
    功能：
    1. 语法错误检测
    2. 运行时错误分析
    3. 性能问题识别
    4. 根因分析
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.reports: List[ProblemReport] = []
        
    def detect_from_exception(self, exception: Exception,
                            context: Optional[Dict[str, Any]] = None) -> ProblemReport:
        """
        从异常检测问题
        
        Args:
            exception: 异常对象
            context: 上下文信息
            
        Returns:
            ProblemReport: 问题报告
        """
        category = self._categorize_exception(exception)
        severity = self._assess_severity(exception, category)
        
        # 获取traceback
        tb = traceback.format_exc()
        
        report = ProblemReport(
            problem_id=self._generate_problem_id(),
            category=category,
            severity=severity,
            title=f"{category.value}: {str(exception)}",
            description=self._generate_description(exception, category),
            traceback=tb,
            suggestions=self._generate_suggestions(exception, category),
            metadata=context or {}
        )
        
        self.reports.append(report)
        return report
    
    def detect_from_code(self, code: str, 
                        file_path: Optional[str] = None) -> List[ProblemReport]:
        """检测代码中的问题"""
        reports = []
        
        # 语法检查
        syntax_reports = self._check_syntax(code, file_path)
        reports.extend(syntax_reports)
        
        # 常见问题模式检测
        pattern_reports = self._check_patterns(code, file_path)
        reports.extend(pattern_reports)
        
        self.reports.extend(reports)
        return reports
    
    def _categorize_exception(self, exception: Exception) -> ProblemCategory:
        """分类异常"""
        exception_type = type(exception).__name__
        
        category_mapping = {
            'SyntaxError': ProblemCategory.SYNTAX_ERROR,
            'IndentationError': ProblemCategory.SYNTAX_ERROR,
            'TabError': ProblemCategory.SYNTAX_ERROR,
            'ImportError': ProblemCategory.IMPORT_ERROR,
            'ModuleNotFoundError': ProblemCategory.IMPORT_ERROR,
            'AttributeError': ProblemCategory.RUNTIME_ERROR,
            'TypeError': ProblemCategory.RUNTIME_ERROR,
            'ValueError': ProblemCategory.RUNTIME_ERROR,
            'KeyError': ProblemCategory.RUNTIME_ERROR,
            'IndexError': ProblemCategory.RUNTIME_ERROR,
            'MemoryError': ProblemCategory.MEMORY_LEAK,
            'RecursionError': ProblemCategory.PERFORMANCE,
            'TimeoutError': ProblemCategory.PERFORMANCE,
        }
        
        return category_mapping.get(exception_type, ProblemCategory.UNKNOWN)
    
    def _assess_severity(self, exception: Exception, 
                        category: ProblemCategory) -> ProblemSeverity:
        """评估严重性"""
        if category == ProblemCategory.SYNTAX_ERROR:
            return ProblemSeverity.HIGH
        elif category == ProblemCategory.IMPORT_ERROR:
            return ProblemSeverity.HIGH
        elif category == ProblemCategory.MEMORY_LEAK:
            return ProblemSeverity.CRITICAL
        elif category == ProblemCategory.PERFORMANCE:
            return ProblemSeverity.MEDIUM
        else:
            return ProblemSeverity.MEDIUM
    
    def _generate_description(self, exception: Exception,
                            category: ProblemCategory) -> str:
        """生成问题描述"""
        if category == ProblemCategory.SYNTAX_ERROR:
            return f"语法错误: {str(exception)}"
        elif category == ProblemCategory.IMPORT_ERROR:
            return f"导入错误: {str(exception)}"
        elif category == ProblemCategory.RUNTIME_ERROR:
            return f"运行时错误: {str(exception)}"
        elif category == ProblemCategory.MEMORY_LEAK:
            return f"内存问题: {str(exception)}"
        else:
            return f"未知问题: {str(exception)}"
    
    def _generate_suggestions(self, exception: Exception,
                            category: ProblemCategory) -> List[str]:
        """生成修复建议"""
        suggestions = []
        
        if category == ProblemCategory.SYNTAX_ERROR:
            suggestions.append("检查代码缩进是否正确")
            suggestions.append("确保括号、引号配对正确")
            suggestions.append("检查关键字拼写")
            
        elif category == ProblemCategory.IMPORT_ERROR:
            suggestions.append("确认模块已安装")
            suggestions.append("检查模块路径是否正确")
            suggestions.append("使用 pip install 安装缺失模块")
            
        elif category == ProblemCategory.RUNTIME_ERROR:
            suggestions.append("添加错误处理代码")
            suggestions.append("检查变量是否正确初始化")
            suggestions.append("验证输入参数的有效性")
            
        elif category == ProblemCategory.MEMORY_LEAK:
            suggestions.append("检查是否有未关闭的资源")
            suggestions.append("使用弱引用替代强引用")
            suggestions.append("考虑使用生成器替代列表"
)
            
        return suggestions
    
    def _check_syntax(self, code: str, 
                      file_path: Optional[str] = None) -> List[ProblemReport]:
        """检查语法错误"""
        reports = []
        
        try:
            compile(code, file_path or '<string>', 'exec')
        except SyntaxError as e:
            reports.append(ProblemReport(
                problem_id=self._generate_problem_id(),
                category=ProblemCategory.SYNTAX_ERROR,
                severity=ProblemSeverity.HIGH,
                title=f"Syntax Error at line {e.lineno}",
                description=str(e),
                location={
                    'file': file_path,
                    'line': e.lineno,
                    'offset': e.offset
                },
                suggestions=["修复语法错误"]
            ))
            
        return reports
    
    def _check_patterns(self, code: str,
                       file_path: Optional[str] = None) -> List[ProblemReport]:
        """检查常见问题模式"""
        reports = []
        
        # 检测无限循环风险
        if re.search(r'while\s+True', code):
            if 'break' not in code:
                reports.append(ProblemReport(
                    problem_id=self._generate_problem_id(),
                    category=ProblemCategory.PERFORMANCE,
                    severity=ProblemSeverity.MEDIUM,
                    title="Potential Infinite Loop",
                    description="检测到 while True 但未找到 break 语句",
                    suggestions=["添加退出条件或 break 语句"]
                ))
                
        # 检测未使用的变量
        unused_vars = re.findall(r'^(\w+)\s*=', code, re.MULTILINE)
        # 简化检测
        
        return reports
    
    def _generate_problem_id(self) -> str:
        """生成问题ID"""
        import hashlib
        return hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    
    def get_summary(self) -> Dict[str, Any]:
        """获取问题汇总"""
        if not self.reports:
            return {'total': 0, 'by_severity': {}, 'by_category': {}}
            
        by_severity = {}
        by_category = {}
        
        for report in self.reports:
            # 按严重性统计
            severity = report.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1
            
            # 按类别统计
            category = report.category.value
            by_category[category] = by_category.get(category, 0) + 1
            
        return {
            'total': len(self.reports),
            'by_severity': by_severity,
            'by_category': by_category,
            'critical': len([r for r in self.reports if r.severity == ProblemSeverity.CRITICAL])
        }
