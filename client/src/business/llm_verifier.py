"""
LLM验证器 (LLM as a Verifier)
=============================

参考: llm-as-a-verifier.notion.site

实现LLM作为验证器的核心功能：
1. 代码验证 - 验证代码正确性、安全性
2. 逻辑验证 - 验证推理逻辑一致性
3. 内容验证 - 验证内容质量
4. 安全验证 - 检测安全漏洞
5. 输出验证 - 验证模型输出

核心特性：
- 多维度验证
- 自动修复建议
- 置信度评估
- 详细报告生成

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class VerificationType(Enum):
    """验证类型"""
    CODE = "code"                    # 代码验证
    LOGIC = "logic"                  # 逻辑验证
    CONTENT = "content"              # 内容验证
    SECURITY = "security"            # 安全验证
    OUTPUT = "output"                # 输出验证
    FORMAT = "format"                # 格式验证


class VerificationResult(Enum):
    """验证结果"""
    PASS = "pass"                    # 通过
    WARNING = "warning"              # 警告
    FAIL = "fail"                    # 失败
    ERROR = "error"                  # 错误


class SeverityLevel(Enum):
    """严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class VerificationIssue:
    """验证问题"""
    type: VerificationType
    result: VerificationResult
    severity: SeverityLevel
    message: str
    location: Optional[str] = None
    suggestion: Optional[str] = None
    confidence: float = 0.0


@dataclass
class VerificationReport:
    """验证报告"""
    verification_type: VerificationType
    overall_result: VerificationResult
    issues: List[VerificationIssue] = field(default_factory=list)
    confidence: float = 0.0
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMVerifier:
    """
    LLM验证器
    
    功能：
    1. 代码验证 - 检查代码语法、逻辑、安全性
    2. 逻辑验证 - 验证推理过程的一致性
    3. 内容验证 - 验证内容准确性和完整性
    4. 安全验证 - 检测安全漏洞
    5. 输出验证 - 验证模型输出质量
    """
    
    def __init__(self):
        # 验证规则
        self._code_rules = [
            self._check_syntax,
            self._check_best_practices,
            self._check_security_vulnerabilities,
            self._check_performance,
        ]
        
        self._logic_rules = [
            self._check_consistency,
            self._check_validity,
            self._check_completeness,
        ]
        
        self._content_rules = [
            self._check_accuracy,
            self._check_relevance,
            self._check_objectivity,
        ]
        
        self._security_rules = [
            self._check_injection,
            self._check_sensitive_data,
            self._check_access_control,
        ]
    
    def verify_code(self, code: str, language: str = "python") -> VerificationReport:
        """
        验证代码
        
        Args:
            code: 代码内容
            language: 编程语言
            
        Returns:
            验证报告
        """
        issues = []
        
        for rule in self._code_rules:
            issues.extend(rule(code, language))
        
        # 确定总体结果
        overall_result = self._determine_overall_result(issues)
        confidence = self._calculate_confidence(issues)
        
        return VerificationReport(
            verification_type=VerificationType.CODE,
            overall_result=overall_result,
            issues=issues,
            confidence=confidence,
        )
    
    def verify_logic(self, reasoning: str, conclusion: str) -> VerificationReport:
        """
        验证逻辑
        
        Args:
            reasoning: 推理过程
            conclusion: 结论
            
        Returns:
            验证报告
        """
        issues = []
        
        for rule in self._logic_rules:
            issues.extend(rule(reasoning, conclusion))
        
        overall_result = self._determine_overall_result(issues)
        confidence = self._calculate_confidence(issues)
        
        return VerificationReport(
            verification_type=VerificationType.LOGIC,
            overall_result=overall_result,
            issues=issues,
            confidence=confidence,
        )
    
    def verify_content(self, content: str, context: Optional[str] = None) -> VerificationReport:
        """
        验证内容
        
        Args:
            content: 内容
            context: 上下文
            
        Returns:
            验证报告
        """
        issues = []
        
        for rule in self._content_rules:
            issues.extend(rule(content, context))
        
        overall_result = self._determine_overall_result(issues)
        confidence = self._calculate_confidence(issues)
        
        return VerificationReport(
            verification_type=VerificationType.CONTENT,
            overall_result=overall_result,
            issues=issues,
            confidence=confidence,
        )
    
    def verify_security(self, content: str, context: Optional[str] = None) -> VerificationReport:
        """
        安全验证
        
        Args:
            content: 待验证内容
            context: 上下文
            
        Returns:
            验证报告
        """
        issues = []
        
        for rule in self._security_rules:
            issues.extend(rule(content, context))
        
        overall_result = self._determine_overall_result(issues)
        confidence = self._calculate_confidence(issues)
        
        return VerificationReport(
            verification_type=VerificationType.SECURITY,
            overall_result=overall_result,
            issues=issues,
            confidence=confidence,
        )
    
    def verify_output(self, output: str, expected: Optional[str] = None) -> VerificationReport:
        """
        验证输出
        
        Args:
            output: 实际输出
            expected: 期望输出
            
        Returns:
            验证报告
        """
        issues = []
        
        # 检查输出是否为空
        if not output or output.strip() == "":
            issues.append(VerificationIssue(
                type=VerificationType.OUTPUT,
                result=VerificationResult.FAIL,
                severity=SeverityLevel.HIGH,
                message="输出为空",
                suggestion="请确保生成了有效的输出内容",
                confidence=0.95,
            ))
        
        # 检查输出格式
        if not self._check_output_format(output):
            issues.append(VerificationIssue(
                type=VerificationType.FORMAT,
                result=VerificationResult.WARNING,
                severity=SeverityLevel.LOW,
                message="输出格式可能不符合预期",
                suggestion="请检查输出格式是否符合要求",
                confidence=0.7,
            ))
        
        # 检查与预期的匹配度
        if expected:
            similarity = self._calculate_similarity(output, expected)
            if similarity < 0.5:
                issues.append(VerificationIssue(
                    type=VerificationType.OUTPUT,
                    result=VerificationResult.WARNING,
                    severity=SeverityLevel.MEDIUM,
                    message=f"输出与预期不符（相似度: {similarity:.2f}）",
                    suggestion="请检查输出内容是否符合预期",
                    confidence=0.8,
                ))
        
        overall_result = self._determine_overall_result(issues)
        confidence = self._calculate_confidence(issues)
        
        return VerificationReport(
            verification_type=VerificationType.OUTPUT,
            overall_result=overall_result,
            issues=issues,
            confidence=confidence,
        )
    
    # ============ 代码验证规则 ============
    
    def _check_syntax(self, code: str, language: str) -> List[VerificationIssue]:
        """检查语法"""
        issues = []
        
        if language.lower() == "python":
            try:
                import ast
                ast.parse(code)
            except SyntaxError as e:
                issues.append(VerificationIssue(
                    type=VerificationType.CODE,
                    result=VerificationResult.FAIL,
                    severity=SeverityLevel.CRITICAL,
                    message=f"语法错误: {e.msg}",
                    location=f"行 {e.lineno}",
                    suggestion="请修复语法错误",
                    confidence=1.0,
                ))
        
        return issues
    
    def _check_best_practices(self, code: str, language: str) -> List[VerificationIssue]:
        """检查最佳实践"""
        issues = []
        
        # 检查过长的行
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append(VerificationIssue(
                    type=VerificationType.CODE,
                    result=VerificationResult.WARNING,
                    severity=SeverityLevel.LOW,
                    message=f"第 {i} 行超过120个字符",
                    suggestion="请缩短行长度以提高可读性",
                    confidence=0.8,
                ))
        
        # 检查重复代码
        if code.count("print(") > 10:
            issues.append(VerificationIssue(
                type=VerificationType.CODE,
                result=VerificationResult.WARNING,
                severity=SeverityLevel.LOW,
                message="存在大量print语句",
                suggestion="考虑使用logging模块替代print",
                confidence=0.7,
            ))
        
        return issues
    
    def _check_security_vulnerabilities(self, code: str, language: str) -> List[VerificationIssue]:
        """检查安全漏洞"""
        issues = []
        
        # 检测SQL注入风险
        sql_patterns = ["%s", "format(", "f\"", "\\+"]
        if any(pattern in code for pattern in sql_patterns):
            if "SELECT" in code.upper() or "INSERT" in code.upper():
                issues.append(VerificationIssue(
                    type=VerificationType.SECURITY,
                    result=VerificationResult.WARNING,
                    severity=SeverityLevel.HIGH,
                    message="检测到潜在的SQL注入风险",
                    suggestion="请使用参数化查询",
                    confidence=0.85,
                ))
        
        # 检测硬编码密钥
        if "api_key" in code.lower() or "secret" in code.lower():
            if any(char in code for char in ["\"", "'", "="]):
                issues.append(VerificationIssue(
                    type=VerificationType.SECURITY,
                    result=VerificationResult.FAIL,
                    severity=SeverityLevel.CRITICAL,
                    message="检测到硬编码的敏感信息",
                    suggestion="请使用环境变量或配置文件存储敏感信息",
                    confidence=0.9,
                ))
        
        return issues
    
    def _check_performance(self, code: str, language: str) -> List[VerificationIssue]:
        """检查性能问题"""
        issues = []
        
        # 检测嵌套循环
        lines = code.split('\n')
        nesting_level = 0
        for i, line in enumerate(lines, 1):
            indent = len(line) - len(line.lstrip())
            if indent > nesting_level * 4:
                nesting_level += 1
                if nesting_level > 3:
                    issues.append(VerificationIssue(
                        type=VerificationType.CODE,
                        result=VerificationResult.WARNING,
                        severity=SeverityLevel.MEDIUM,
                        message=f"第 {i} 行嵌套层级过深",
                        suggestion="考虑重构代码减少嵌套",
                        confidence=0.75,
                    ))
            elif indent < nesting_level * 4:
                nesting_level = max(0, nesting_level - 1)
        
        return issues
    
    # ============ 逻辑验证规则 ============
    
    def _check_consistency(self, reasoning: str, conclusion: str) -> List[VerificationIssue]:
        """检查逻辑一致性"""
        issues = []
        
        # 检查推理和结论是否相关
        reasoning_lower = reasoning.lower()
        conclusion_lower = conclusion.lower()
        
        # 检查关键词匹配
        reasoning_words = set(reasoning_lower.split())
        conclusion_words = set(conclusion_lower.split())
        
        if len(reasoning_words & conclusion_words) < 2:
            issues.append(VerificationIssue(
                type=VerificationType.LOGIC,
                result=VerificationResult.WARNING,
                severity=SeverityLevel.MEDIUM,
                message="推理过程与结论缺乏关联",
                suggestion="请确保推理过程能够支持结论",
                confidence=0.7,
            ))
        
        return issues
    
    def _check_validity(self, reasoning: str, conclusion: str) -> List[VerificationIssue]:
        """检查逻辑有效性"""
        issues = []
        
        # 检测常见逻辑谬误
        fallacies = [
            ("因为", "所以"),
            ("所有", "都"),
            ("如果", "那么"),
        ]
        
        for premise, conclusion_marker in fallacies:
            if premise in reasoning and conclusion_marker in conclusion:
                # 简单检查是否有实际的逻辑连接
                if reasoning.count(premise) > conclusion.count(conclusion_marker):
                    issues.append(VerificationIssue(
                        type=VerificationType.LOGIC,
                        result=VerificationResult.WARNING,
                        severity=SeverityLevel.LOW,
                        message="逻辑推理可能不完整",
                        suggestion="请确保所有前提都能支持结论",
                        confidence=0.6,
                    ))
        
        return issues
    
    def _check_completeness(self, reasoning: str, conclusion: str) -> List[VerificationIssue]:
        """检查逻辑完整性"""
        issues = []
        
        # 检查是否有足够的推理步骤
        reasoning_steps = reasoning.count(".") + reasoning.count(";") + reasoning.count("\n")
        
        if reasoning_steps < 2:
            issues.append(VerificationIssue(
                type=VerificationType.LOGIC,
                result=VerificationResult.WARNING,
                severity=SeverityLevel.LOW,
                message="推理过程可能过于简略",
                suggestion="请提供更详细的推理步骤",
                confidence=0.65,
            ))
        
        return issues
    
    # ============ 内容验证规则 ============
    
    def _check_accuracy(self, content: str, context: Optional[str]) -> List[VerificationIssue]:
        """检查内容准确性"""
        issues = []
        
        # 检测矛盾表述
        contradictions = [
            ("不是", "而是"),
            ("不可能", "可能"),
            ("没有", "有"),
        ]
        
        for negation, affirmation in contradictions:
            if negation in content and affirmation in content:
                issues.append(VerificationIssue(
                    type=VerificationType.CONTENT,
                    result=VerificationResult.WARNING,
                    severity=SeverityLevel.MEDIUM,
                    message="内容可能存在矛盾",
                    suggestion="请检查内容的一致性",
                    confidence=0.7,
                ))
        
        return issues
    
    def _check_relevance(self, content: str, context: Optional[str]) -> List[VerificationIssue]:
        """检查内容相关性"""
        issues = []
        
        if context:
            context_words = set(context.lower().split())
            content_words = set(content.lower().split())
            
            if len(content_words & context_words) == 0:
                issues.append(VerificationIssue(
                    type=VerificationType.CONTENT,
                    result=VerificationResult.WARNING,
                    severity=SeverityLevel.MEDIUM,
                    message="内容与上下文无关",
                    suggestion="请确保内容与上下文相关",
                    confidence=0.75,
                ))
        
        return issues
    
    def _check_objectivity(self, content: str, context: Optional[str]) -> List[VerificationIssue]:
        """检查内容客观性"""
        issues = []
        
        # 检测主观表述
        subjective_words = ["我认为", "我觉得", "应该", "必须"]
        
        for word in subjective_words:
            if word in content:
                issues.append(VerificationIssue(
                    type=VerificationType.CONTENT,
                    result=VerificationResult.WARNING,
                    severity=SeverityLevel.LOW,
                    message="内容包含主观表述",
                    suggestion="考虑使用更客观的表述方式",
                    confidence=0.6,
                ))
                break
        
        return issues
    
    # ============ 安全验证规则 ============
    
    def _check_injection(self, content: str, context: Optional[str]) -> List[VerificationIssue]:
        """检查注入攻击"""
        issues = []
        
        injection_patterns = [
            "<script",
            "javascript:",
            "eval(",
            "exec(",
            "system(",
            "subprocess",
        ]
        
        for pattern in injection_patterns:
            if pattern.lower() in content.lower():
                issues.append(VerificationIssue(
                    type=VerificationType.SECURITY,
                    result=VerificationResult.FAIL,
                    severity=SeverityLevel.CRITICAL,
                    message=f"检测到潜在的注入攻击: {pattern}",
                    suggestion="请过滤或转义危险内容",
                    confidence=0.95,
                ))
        
        return issues
    
    def _check_sensitive_data(self, content: str, context: Optional[str]) -> List[VerificationIssue]:
        """检查敏感数据"""
        issues = []
        
        sensitive_patterns = [
            r"\b\d{11}\b",  # 手机号
            r"\b\d{18}\b",  # 身份证号
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # 邮箱
            r"\b\d{4}-\d{4}-\d{4}-\d{4}\b",  # 信用卡号
        ]
        
        for pattern in sensitive_patterns:
            if __import__('re').search(pattern, content):
                issues.append(VerificationIssue(
                    type=VerificationType.SECURITY,
                    result=VerificationResult.WARNING,
                    severity=SeverityLevel.HIGH,
                    message="检测到潜在的敏感数据",
                    suggestion="请确保敏感数据已被适当处理",
                    confidence=0.8,
                ))
        
        return issues
    
    def _check_access_control(self, content: str, context: Optional[str]) -> List[VerificationIssue]:
        """检查访问控制"""
        issues = []
        
        # 检测潜在的权限问题
        if "admin" in content.lower() or "root" in content.lower():
            if "password" in content.lower() or "token" in content.lower():
                issues.append(VerificationIssue(
                    type=VerificationType.SECURITY,
                    result=VerificationResult.FAIL,
                    severity=SeverityLevel.CRITICAL,
                    message="检测到管理员凭证相关内容",
                    suggestion="请确保管理员凭证安全",
                    confidence=0.9,
                ))
        
        return issues
    
    # ============ 辅助方法 ============
    
    def _check_output_format(self, output: str) -> bool:
        """检查输出格式"""
        # 简单检查：输出应该有合理的结构
        return len(output) > 10
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        return len(words1 & words2) / len(words1 | words2)
    
    def _determine_overall_result(self, issues: List[VerificationIssue]) -> VerificationResult:
        """确定总体验证结果"""
        if any(issue.result == VerificationResult.FAIL for issue in issues):
            return VerificationResult.FAIL
        if any(issue.result == VerificationResult.ERROR for issue in issues):
            return VerificationResult.ERROR
        if any(issue.result == VerificationResult.WARNING for issue in issues):
            return VerificationResult.WARNING
        return VerificationResult.PASS
    
    def _calculate_confidence(self, issues: List[VerificationIssue]) -> float:
        """计算验证置信度"""
        if not issues:
            return 0.95
        
        total_confidence = sum(issue.confidence for issue in issues)
        return 1.0 - (total_confidence / len(issues) * 0.1)
    
    def generate_report(self, report: VerificationReport) -> str:
        """生成可读的验证报告"""
        lines = [f"验证报告 - {report.verification_type.value}"]
        lines.append("=" * 50)
        lines.append(f"总体结果: {report.overall_result.value}")
        lines.append(f"置信度: {report.confidence:.2f}")
        lines.append("")
        
        if report.issues:
            lines.append("问题列表:")
            for i, issue in enumerate(report.issues, 1):
                lines.append(f"{i}. [{issue.severity.value}] {issue.message}")
                if issue.location:
                    lines.append(f"     位置: {issue.location}")
                if issue.suggestion:
                    lines.append(f"     建议: {issue.suggestion}")
                lines.append("")
        
        return "\n".join(lines)


# 便捷函数
def create_llm_verifier() -> LLMVerifier:
    """创建LLM验证器"""
    return LLMVerifier()


__all__ = [
    "VerificationType",
    "VerificationResult",
    "SeverityLevel",
    "VerificationIssue",
    "VerificationReport",
    "LLMVerifier",
    "create_llm_verifier",
]
