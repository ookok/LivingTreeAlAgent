"""
Security Auditor - 安全审计器
==============================

脚本安全审计，检查代码中的潜在安全风险。

审计规则:
- 禁止的危险操作（exec, eval, subprocess等）
- 限制的文件访问
- 限制的网络访问
- 路径遍历检测
"""

import re
from typing import Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


class SecurityLevel(Enum):
    """安全级别"""
    CRITICAL = "critical"    # 严重风险
    HIGH = "high"            # 高风险
    MEDIUM = "medium"        # 中风险
    LOW = "low"              # 低风险
    INFO = "info"            # 信息


@dataclass
class SecurityRule:
    """安全规则"""
    name: str
    pattern: str  # 正则表达式
    level: SecurityLevel
    description: str
    suggestion: str = ""
    severity_score: int = 0  # 风险分数

    def __post_init__(self):
        if isinstance(self.level, str):
            self.level = SecurityLevel(self.level)


@dataclass
class Violation:
    """违规项"""
    rule: SecurityRule
    matches: list = field(default_factory=list)
    line_numbers: list = field(default_factory=list)
    code_snippet: str = ""


@dataclass
class AuditResult:
    """审计结果"""
    safe: bool
    risk_score: int  # 0-100
    violations: list[Violation] = field(default_factory=list)
    warnings: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "safe": self.safe,
            "risk_score": self.risk_score,
            "violations": [
                {
                    "rule": v.rule.name,
                    "level": v.rule.level.value,
                    "matches": v.matches,
                    "line_numbers": v.line_numbers,
                    "description": v.rule.description,
                    "suggestion": v.rule.suggestion,
                }
                for v in self.violations
            ],
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "metadata": self.metadata,
        }


class SecurityAuditor:
    """安全审计器"""

    # 内置安全规则
    DEFAULT_RULES = [
        # ===== 严重风险 =====
        SecurityRule(
            name="dangerous_exec",
            pattern=r"exec\s*\(",
            level=SecurityLevel.CRITICAL,
            description="使用exec()执行动态代码",
            suggestion="使用更安全的替代方案，如AST解析或预定义的函数映射",
            severity_score=100,
        ),
        SecurityRule(
            name="dangerous_eval",
            pattern=r"eval\s*\(",
            level=SecurityLevel.CRITICAL,
            description="使用eval()执行动态代码",
            suggestion="使用更安全的替代方案",
            severity_score=100,
        ),
        SecurityRule(
            name="dynamic_import",
            pattern=r"__import__\s*\(",
            level=SecurityLevel.CRITICAL,
            description="使用__import__()动态导入",
            suggestion="使用importlib.import_module()替代",
            severity_score=90,
        ),
        SecurityRule(
            name="code_compile",
            pattern=r"compile\s*\(",
            level=SecurityLevel.CRITICAL,
            description="使用compile()动态编译代码",
            suggestion="避免动态编译代码",
            severity_score=85,
        ),
        SecurityRule(
            name="settrace",
            pattern=r"sys\.settrace|settrace\s*\(",
            level=SecurityLevel.CRITICAL,
            description="使用sys.settrace设置调试追踪",
            suggestion="移除调试追踪代码",
            severity_score=80,
        ),

        # ===== 高风险 =====
        SecurityRule(
            name="subprocess_call",
            pattern=r"subprocess\.",
            level=SecurityLevel.HIGH,
            description="使用subprocess模块",
            suggestion="subprocess可能允许执行任意系统命令，使用前请确保输入已被验证",
            severity_score=75,
        ),
        SecurityRule(
            name="os_system",
            pattern=r"os\.system\s*\(",
            level=SecurityLevel.HIGH,
            description="使用os.system()执行系统命令",
            suggestion="使用subprocess模块替代，并限制命令参数",
            severity_score=75,
        ),
        SecurityRule(
            name="os_popen",
            pattern=r"os\.popen\s*\(",
            level=SecurityLevel.HIGH,
            description="使用os.popen()执行系统命令",
            suggestion="使用subprocess模块替代",
            severity_score=70,
        ),
        SecurityRule(
            name="pty_spawn",
            pattern=r"pty\.spawn",
            level=SecurityLevel.HIGH,
            description="使用pty.spawn()创建伪终端",
            suggestion="避免创建伪终端，这可能带来安全风险",
            severity_score=70,
        ),
        SecurityRule(
            name="file_write",
            pattern=r"open\s*\([^)]*['\"]w['\"]",
            level=SecurityLevel.HIGH,
            description="以写入模式打开文件",
            suggestion="确保文件路径已验证，避免写入系统关键目录",
            severity_score=60,
        ),
        SecurityRule(
            name="file_append",
            pattern=r"open\s*\([^)]*['\"]a['\"]",
            level=SecurityLevel.HIGH,
            description="以追加模式打开文件",
            suggestion="确保文件路径已验证",
            severity_score=55,
        ),

        # ===== 中风险 =====
        SecurityRule(
            name="path_traversal",
            pattern=r"\.\.[/\\]",
            level=SecurityLevel.MEDIUM,
            description="检测到路径遍历模式(..)",
            suggestion="路径遍历可能导致访问未授权的文件，确保路径已规范化",
            severity_score=50,
        ),
        SecurityRule(
            name="network_request",
            pattern=r"(urllib|httpx|requests|aiohttp)\.",
            level=SecurityLevel.MEDIUM,
            description="发起网络请求",
            suggestion="确保请求的URL已被验证，避免请求未知来源",
            severity_score=45,
        ),
        SecurityRule(
            name="socket_connection",
            pattern=r"socket\.(socket|connect)",
            level=SecurityLevel.MEDIUM,
            description="建立网络连接",
            suggestion="确保连接目标已被验证",
            severity_score=50,
        ),
        SecurityRule(
            name="serialization",
            pattern=r"(pickle|marshal|shelve)\.(load|dump|loads|dumps)",
            level=SecurityLevel.MEDIUM,
            description="使用不安全的序列化",
            suggestion="pickle和marshal可能执行任意代码，使用json替代",
            severity_score=45,
        ),

        # ===== 低风险 =====
        SecurityRule(
            name="dynamic_code",
            pattern=r"(globals|locals)\s*\(",
            level=SecurityLevel.LOW,
            description="访问全局或局部变量字典",
            suggestion="直接访问变量而非通过字典",
            severity_score=20,
        ),
        SecurityRule(
            name="attribute_access",
            pattern=r"setattr\s*\(",
            level=SecurityLevel.LOW,
            description="使用setattr动态设置属性",
            suggestion="直接设置对象属性而非使用setattr",
            severity_score=15,
        ),
        SecurityRule(
            name="del_attribute",
            pattern=r"delattr\s*\(",
            level=SecurityLevel.LOW,
            description="使用delattr删除属性",
            suggestion="直接删除对象属性而非使用delattr",
            severity_score=10,
        ),
    ]

    def __init__(self):
        self.rules: list[SecurityRule] = []
        self.custom_rules: list[SecurityRule] = []
        self._load_default_rules()

    def _load_default_rules(self):
        """加载默认规则"""
        self.rules = self.DEFAULT_RULES.copy()

    def add_rule(self, rule: SecurityRule):
        """添加自定义规则"""
        self.custom_rules.append(rule)

    def remove_rule(self, rule_name: str) -> bool:
        """移除规则"""
        for i, rule in enumerate(self.custom_rules):
            if rule.name == rule_name:
                self.custom_rules.pop(i)
                return True
        return False

    def audit(self, code: str) -> AuditResult:
        """
        审计代码

        Args:
            code: 要审计的代码

        Returns:
            AuditResult: 审计结果
        """
        violations = []
        warnings = []
        total_risk_score = 0

        lines = code.split("\n")

        # 检查所有规则
        for rule in self.rules + self.custom_rules:
            violation = self._check_rule(code, rule, lines)
            if violation:
                violations.append(violation)
                total_risk_score += rule.severity_score

        # 生成建议
        suggestions = self._generate_suggestions(violations)

        # 判断是否安全
        safe = total_risk_score < 50 and not any(
            v.rule.level in (SecurityLevel.CRITICAL, SecurityLevel.HIGH)
            for v in violations
        )

        # 限制风险分数在0-100
        risk_score = min(100, total_risk_score)

        return AuditResult(
            safe=safe,
            risk_score=risk_score,
            violations=violations,
            warnings=warnings,
            suggestions=suggestions,
            metadata={
                "total_lines": len(lines),
                "rule_count": len(self.rules) + len(self.custom_rules),
            }
        )

    def _check_rule(self, code: str, rule: SecurityRule, lines: list) -> Optional[Violation]:
        """检查单个规则"""
        pattern = re.compile(rule.pattern, re.IGNORECASE)
        matches = pattern.findall(code)

        if not matches:
            return None

        # 找出匹配的行号
        line_numbers = []
        code_snippets = []

        for i, line in enumerate(lines, 1):
            if pattern.search(line):
                line_numbers.append(i)
                code_snippets.append(line.strip())

        return Violation(
            rule=rule,
            matches=matches,
            line_numbers=line_numbers,
            code_snippet="\n".join(code_snippets[:3]),  # 最多显示3行
        )

    def _generate_suggestions(self, violations: list[Violation]) -> list:
        """生成修复建议"""
        suggestions = []

        for v in violations:
            if v.rule.suggestion:
                suggestions.append({
                    "rule": v.rule.name,
                    "level": v.rule.level.value,
                    "suggestion": v.rule.suggestion,
                    "count": len(v.matches),
                })

        return suggestions

    def audit_file(self, file_path: str) -> Optional[AuditResult]:
        """审计文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            return self.audit(code)
        except Exception:
            return None

    def get_severity_summary(self, violations: list[Violation]) -> dict:
        """获取严重性摘要"""
        summary = {
            SecurityLevel.CRITICAL: 0,
            SecurityLevel.HIGH: 0,
            SecurityLevel.MEDIUM: 0,
            SecurityLevel.LOW: 0,
            SecurityLevel.INFO: 0,
        }

        for v in violations:
            summary[v.rule.level] += len(v.matches)

        return summary


# 全局单例
_auditor_instance: Optional[SecurityAuditor] = None


def get_security_auditor() -> SecurityAuditor:
    """获取安全审计器单例"""
    global _auditor_instance
    if _auditor_instance is None:
        _auditor_instance = SecurityAuditor()
    return _auditor_instance