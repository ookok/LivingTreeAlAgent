"""
审计者Agent - 核心实现

实现红队验证、一致性检查、法规引用检查等功能。
"""
import ast
import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional

from .blacklist_manager import BlacklistManager

logger = logging.getLogger(__name__)


class AuditIssueType(Enum):
    """审计问题类型"""
    NUMERICAL_INCONSISTENCY = "numerical_inconsistency"  # 数值不一致
    EXPIRED_REGULATION = "expired_regulation"            # 过期法规
    CODE_ERROR = "code_error"                            # 代码错误
    LOGIC_CONTRADICTION = "logic_contradiction"          # 逻辑矛盾
    MISSING_REQUIREMENT = "missing_requirement"          # 缺少必要内容
    FORMAT_ERROR = "format_error"                        # 格式错误
    SECURITY_VULNERABILITY = "security_vulnerability"    # 安全漏洞


class IssueSeverity(Enum):
    """问题严重程度"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class AuditIssue:
    """审计问题"""
    id: str
    issue_type: AuditIssueType
    severity: IssueSeverity
    message: str
    location: Optional[str] = None
    expected_value: Optional[Any] = None
    actual_value: Optional[Any] = None
    suggestion: Optional[str] = None


@dataclass
class AuditResult:
    """审计结果"""
    success: bool
    issues: List[AuditIssue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    code_execution_result: Optional[str] = None
    
    @property
    def critical_issues(self) -> List[AuditIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.CRITICAL]
    
    @property
    def high_issues(self) -> List[AuditIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.HIGH]


class AuditorAgent:
    """
    审计者Agent
    
    核心能力：
    1. 审计报告与代码的一致性
    2. 检查法规引用是否过期
    3. 执行代码验证逻辑正确性
    4. 将问题模式记录到黑名单
    """
    
    def __init__(self):
        self.blacklist_manager = BlacklistManager()
        
        # 已知法规数据库（简化版）
        self.known_regulations = {
            "GB 3095-2012": {"name": "环境空气质量标准", "status": "valid", "updated": "2012"},
            "GB 3838-2002": {"name": "地表水环境质量标准", "status": "valid", "updated": "2002"},
            "GB 8978-1996": {"name": "污水综合排放标准", "status": "expired", "updated": "1996"},
            "GB 18918-2002": {"name": "城镇污水处理厂污染物排放标准", "status": "valid", "updated": "2002"},
            "HJ 2.1-2018": {"name": "环境影响评价技术导则 总纲", "status": "valid", "updated": "2018"},
        }
    
    def audit_report(self, report_content: str, code_content: Optional[str] = None) -> AuditResult:
        """
        审计报告
        
        Args:
            report_content: 报告内容
            code_content: 相关代码（可选）
        
        Returns:
            AuditResult
        """
        issues = []
        warnings = []
        
        # 1. 检查法规引用
        regulation_issues = self._audit_regulations(report_content)
        issues.extend(regulation_issues)
        
        # 2. 提取报告中的数值
        report_values = self._extract_numeric_values(report_content)
        
        # 3. 如果有代码，执行并检查一致性
        code_execution_result = None
        if code_content:
            # 检查代码语法
            syntax_issues = self._audit_code_syntax(code_content)
            issues.extend(syntax_issues)
            
            # 执行代码
            exec_result = self._execute_code(code_content)
            code_execution_result = exec_result["output"]
            
            if exec_result["success"]:
                # 比较报告数值与代码结果
                consistency_issues = self._check_numeric_consistency(report_values, exec_result["values"])
                issues.extend(consistency_issues)
            else:
                issues.append(AuditIssue(
                    id=f"code_exec_{len(issues)}",
                    issue_type=AuditIssueType.CODE_ERROR,
                    severity=IssueSeverity.HIGH,
                    message=f"代码执行失败: {exec_result['error']}"
                ))
        
        # 4. 检查黑名单模式
        blocked_patterns = self.blacklist_manager.get_blocked_patterns(report_content)
        for pattern in blocked_patterns:
            issues.append(AuditIssue(
                id=f"blacklist_{len(issues)}",
                issue_type=AuditIssueType.LOGIC_CONTRADICTION,
                severity=self._map_severity(pattern.severity),
                message=f"检测到黑名单模式: {pattern.description}",
                suggestion=pattern.fix_suggestion
            ))
        
        # 5. 将严重问题添加到黑名单
        for issue in issues:
            if issue.severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH]:
                self._add_to_blacklist(issue)
        
        # 检查是否有严重问题
        has_critical = any(i.severity == IssueSeverity.CRITICAL for i in issues)
        has_high = any(i.severity == IssueSeverity.HIGH for i in issues)
        
        return AuditResult(
            success=not (has_critical or has_high),
            issues=issues,
            warnings=warnings,
            code_execution_result=code_execution_result
        )
    
    def _audit_regulations(self, content: str) -> List[AuditIssue]:
        """检查法规引用"""
        import re
        
        issues = []
        
        # 匹配法规编号模式
        patterns = [
            r"GB\s*[T/]?\s*\d+-\d+",
            r"HJ\s*\d+-\d+",
            r"GBZ\s*\d+-\d+"
        ]
        
        found_regulations = []
        for pattern in patterns:
            found_regulations.extend(re.findall(pattern, content))
        
        for regulation in found_regulations:
            regulation_norm = regulation.replace(" ", "").replace("/", "")
            
            if regulation_norm in self.known_regulations:
                info = self.known_regulations[regulation_norm]
                if info["status"] == "expired":
                    issues.append(AuditIssue(
                        id=f"reg_{len(issues)}",
                        issue_type=AuditIssueType.EXPIRED_REGULATION,
                        severity=IssueSeverity.HIGH,
                        message=f"检测到过期法规引用: {regulation} ({info['name']})",
                        suggestion=f"建议使用最新版本"
                    ))
            else:
                issues.append(AuditIssue(
                    id=f"reg_{len(issues)}",
                    issue_type=AuditIssueType.MISSING_REQUIREMENT,
                    severity=IssueSeverity.MEDIUM,
                    message=f"无法验证法规有效性: {regulation}",
                    suggestion="请确认法规编号正确"
                ))
        
        return issues
    
    def _extract_numeric_values(self, content: str) -> Dict[str, float]:
        """从文本中提取数值"""
        import re
        
        values = {}
        
        # 匹配"排放量: 100 t/a"这种模式
        patterns = [
            r"(排放量|排放浓度|处理效率|投资|净现值|NPV|IRR|回收期)\s*[：:]\s*([\d.]+)",
            r"([\d.]+)\s*(t/a|万元|%|mg/m³|年)"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    key = match[0]
                    try:
                        value = float(match[1])
                        values[key] = value
                    except ValueError:
                        pass
        
        return values
    
    def _audit_code_syntax(self, code: str) -> List[AuditIssue]:
        """检查代码语法"""
        issues = []
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(AuditIssue(
                id=f"syntax_{len(issues)}",
                issue_type=AuditIssueType.CODE_ERROR,
                severity=IssueSeverity.HIGH,
                message=f"代码语法错误: {e.msg} 在第 {e.lineno} 行"
            ))
        
        return issues
    
    def _execute_code(self, code: str) -> Dict[str, Any]:
        """执行代码并获取结果"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name
        
        try:
            result = subprocess.run(
                ["python", temp_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # 尝试提取输出中的数值
                values = {}
                for line in result.stdout.split("\n"):
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        try:
                            values[key] = float(parts[1].strip())
                        except ValueError:
                            pass
                
                return {
                    "success": True,
                    "output": result.stdout,
                    "values": values
                }
            else:
                return {
                    "success": False,
                    "output": result.stdout,
                    "error": result.stderr
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "代码执行超时"
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def _check_numeric_consistency(self, report_values: Dict[str, float], code_values: Dict[str, float]) -> List[AuditIssue]:
        """检查数值一致性"""
        issues = []
        
        for key, report_value in report_values.items():
            if key in code_values:
                code_value = code_values[key]
                # 允许5%的误差
                if abs(report_value - code_value) / max(report_value, code_value, 1) > 0.05:
                    issues.append(AuditIssue(
                        id=f"consistency_{len(issues)}",
                        issue_type=AuditIssueType.NUMERICAL_INCONSISTENCY,
                        severity=IssueSeverity.CRITICAL,
                        message=f"数值不一致: {key}",
                        expected_value=report_value,
                        actual_value=code_value,
                        suggestion=f"报告值 {report_value} 与代码计算值 {code_value} 不符，请检查"
                    ))
        
        return issues
    
    def _add_to_blacklist(self, issue: AuditIssue):
        """将严重问题添加到黑名单"""
        pattern = issue.message[:50]
        self.blacklist_manager.add_pattern(
            pattern=pattern,
            description=issue.message,
            category=issue.issue_type.value,
            severity=issue.severity.value,
            fix_suggestion=issue.suggestion
        )
    
    def _map_severity(self, severity_str: str) -> IssueSeverity:
        """映射严重程度"""
        mapping = {
            "critical": IssueSeverity.CRITICAL,
            "high": IssueSeverity.HIGH,
            "medium": IssueSeverity.MEDIUM,
            "low": IssueSeverity.LOW,
        }
        return mapping.get(severity_str, IssueSeverity.MEDIUM)


# 单例模式
_auditor_agent = None


def get_auditor_agent() -> AuditorAgent:
    """获取审计者Agent单例"""
    global _auditor_agent
    if _auditor_agent is None:
        _auditor_agent = AuditorAgent()
    return _auditor_agent