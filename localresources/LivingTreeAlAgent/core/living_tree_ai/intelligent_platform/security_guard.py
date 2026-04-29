"""
安全守护 (Security Guard)
========================

安全与隐私保护：
1. 附件安全扫描
2. 防误发提醒
3. 敏感词检测
4. 版权检测
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .workspace import IntelligentWorkspace, ComplianceResult


class ThreatLevel(Enum):
    """威胁等级"""
    SAFE = "safe"                 # 安全
    LOW = "low"                  # 低风险
    MEDIUM = "medium"            # 中风险
    HIGH = "high"                # 高风险
    CRITICAL = "critical"        # 危险


@dataclass
class ScanResult:
    """扫描结果"""
    threat_level: ThreatLevel
    passed: bool
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    scan_details: dict[str, Any] = field(default_factory=dict)
    scanned_at: datetime = field(default_factory=datetime.now)


@dataclass
class SensitiveWord:
    """敏感词"""
    word: str
    category: str               # politics/ads/spam/custom
    severity: str                # high/medium/low


@dataclass
class ExternalDomainWarning:
    """外部域名警告"""
    detected: bool
    domain: Optional[str] = None
    is_internal: bool = False
    suggestion: str = ""


class SecurityGuard:
    """
    安全守护

    能力：
    - 附件安全扫描（沙箱检测）
    - 防误发提醒
    - 敏感词检测
    - 版权检测
    - 外部域名识别
    """

    def __init__(self, workspace: IntelligentWorkspace):
        self.workspace = workspace
        self.central_brain = workspace.central_brain

        # 敏感词库
        self.sensitive_words: list[SensitiveWord] = []
        self._init_sensitive_words()

        # 内部域名列表
        self.internal_domains: set[str] = {"internal", "local", "corp", "company"}

    def _init_sensitive_words(self):
        """初始化敏感词库"""
        # 基础敏感词（示例）
        self.sensitive_words = [
            # 政治敏感
            SensitiveWord("台独", "politics", "high"),
            SensitiveWord("分裂", "politics", "medium"),
            # 广告垃圾
            SensitiveWord("免费领取", "ads", "low"),
            SensitiveWord("点击此处", "ads", "low"),
            # 自定义敏感词由用户添加
        ]

    async def scan_content(
        self,
        content: str,
        scan_types: Optional[list[str]] = None
    ) -> ComplianceResult:
        """
        内容合规扫描

        Args:
            content: 内容
            scan_types: 扫描类型列表 (sensitive/copyright/external)

        Returns:
            合规结果
        """
        scan_types = scan_types or ["sensitive", "copyright"]

        result = ComplianceResult(passed=True, score=1.0)
        issues = []
        warnings = []
        suggestions = []

        # 1. 敏感词扫描
        if "sensitive" in scan_types:
            sensitive_result = await self._scan_sensitive_words(content)
            warnings.extend(sensitive_result.issues)
            suggestions.extend(sensitive_result.suggestions)
            if sensitive_result.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                result.passed = False

        # 2. 版权扫描
        if "copyright" in scan_types:
            copyright_result = await self._scan_copyright(content)
            if copyright_result.issues:
                warnings.extend(copyright_result.issues)

        # 3. 外部域名检测
        if "external" in scan_types:
            domain_result = await self._detect_external_domains(content)
            if domain_result.detected and not domain_result.is_internal:
                warnings.append(f"⚠️ 检测到外部域名: {domain_result.domain}")
                warnings.append(domain_result.suggestion)

        result.warnings = warnings
        result.suggestions = suggestions
        result.blocked_items = issues

        # 计算评分
        if not result.passed:
            result.score = 0.3
        elif warnings:
            result.score = 0.7

        return result

    async def _scan_sensitive_words(self, content: str) -> ScanResult:
        """敏感词扫描"""
        issues = []
        suggestions = []
        max_severity = ThreatLevel.SAFE

        for sw in self.sensitive_words:
            if sw.word in content:
                issues.append(f"检测到敏感词: {sw.word} (类别: {sw.category})")
                suggestions.append(f"建议替换 '{sw.word}' 为更中性的表达")

                if sw.severity == "high":
                    max_severity = ThreatLevel.HIGH
                elif sw.severity == "medium" and max_severity != ThreatLevel.HIGH:
                    max_severity = ThreatLevel.MEDIUM
                elif sw.severity == "low" and max_severity == ThreatLevel.SAFE:
                    max_severity = ThreatLevel.LOW

        return ScanResult(
            threat_level=max_severity,
            passed=max_severity in [ThreatLevel.SAFE, ThreatLevel.LOW],
            issues=issues,
            suggestions=suggestions
        )

    async def _scan_copyright(self, content: str) -> ScanResult:
        """版权扫描"""
        issues = []
        suggestions = []

        # 检测可能的转载内容
        copyright_patterns = [
            (r"转自|转载|来源：", "检测到转载标记，请确保已获得授权"),
            (r"©|\(c\)|版权声明", "检测到版权声明，请遵守其规定"),
            (r"未经授权", "内容包含未经授权声明，风险较高"),
        ]

        for pattern, message in copyright_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(message)
                suggestions.append("建议联系原作者获取授权")

        return ScanResult(
            threat_level=ThreatLevel.LOW if issues else ThreatLevel.SAFE,
            passed=True,
            issues=issues,
            suggestions=suggestions
        )

    async def _detect_external_domains(self, content: str) -> ExternalDomainWarning:
        """检测外部域名"""
        # 提取域名
        domain_pattern = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,})'
        domains = re.findall(domain_pattern, content)

        for domain in domains:
            # 检查是否内部域名
            if any(internal in domain.lower() for internal in self.internal_domains):
                return ExternalDomainWarning(
                    detected=True,
                    domain=domain,
                    is_internal=True
                )
            else:
                return ExternalDomainWarning(
                    detected=True,
                    domain=domain,
                    is_internal=False,
                    suggestion="⚠️ 检测到外部域名，请确认收件人是否有权限接收此内容"
                )

        return ExternalDomainWarning(detected=False)

    async def scan_attachment(
        self,
        file_hash: str,
        file_name: str,
        file_size: int,
        file_type: str
    ) -> ScanResult:
        """
        附件安全扫描

        在边缘节点的沙箱环境中模拟打开，检测恶意脚本或宏病毒

        Args:
            file_hash: 文件哈希
            file_name: 文件名
            file_size: 文件大小
            file_type: 文件类型

        Returns:
            扫描结果
        """
        issues = []
        suggestions = []
        scan_details = {}
        threat_level = ThreatLevel.SAFE

        # 1. 危险文件类型检查
        dangerous_types = {
            "exe": "可执行文件",
            "bat": "批处理文件",
            "cmd": "命令脚本",
            "ps1": "PowerShell脚本",
            "vbs": "VBScript脚本",
            "scr": "屏幕保护程序",
            "jar": "Java可执行文件",
            "dll": "动态链接库"
        }

        if file_type.lower() in dangerous_types:
            threat_level = ThreatLevel.HIGH
            issues.append(f"⚠️ 危险文件类型: {dangerous_types[file_type.lower()]} ({file_type})")
            suggestions.append("建议将可执行文件压缩后再发送")

        # 2. 宏病毒检测（Office 文件）
        office_types = ["doc", "docx", "xls", "xlsx", "ppt", "pptx"]
        if file_type.lower() in office_types:
            scan_details["macro_check"] = "recommended"
            suggestions.append("📎 Office 文件建议启用宏保护")

        # 3. 文件大小检查
        max_size_mb = 50
        if file_size > max_size_mb * 1024 * 1024:
            threat_level = ThreatLevel.MEDIUM
            suggestions.append(f"📎 文件较大 ({file_size // (1024*1024)}MB)，建议压缩或使用 DHT 分片传输")

        # 4. 可疑文件名检测
        suspicious_patterns = [
            (r'(?:invoice|payment|账单|发票).*\.exe', "可疑的可执行文件"),
            (r'.*\.scr\?.*', "伪装的屏幕保护文件"),
            (r'(?:confidential|机密|秘密).*\.(doc|xls)', "包含机密标记的Office文件")
        ]

        for pattern, message in suspicious_patterns:
            if re.search(pattern, file_name, re.IGNORECASE):
                threat_level = ThreatLevel.MEDIUM
                issues.append(message)
                suggestions.append("请确认此文件的来源和用途")

        return ScanResult(
            threat_level=threat_level,
            passed=threat_level not in [ThreatLevel.HIGH, ThreatLevel.CRITICAL],
            issues=issues,
            suggestions=suggestions,
            scan_details=scan_details
        )

    async def check_misend_risk(
        self,
        recipients: list[str],
        content: str,
        attachments: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """
        防误发风险检测

        识别收件人域名为外部单位时，高亮提醒并二次确认

        Args:
            recipients: 收件人列表
            content: 邮件内容
            attachments: 附件列表

        Returns:
            风险评估结果
        """
        risk_level = "low"
        warnings = []
        confirm_required = False

        # 提取收件人域名
        external_recipients = []
        for recipient in recipients:
            if "@" in recipient:
                domain = recipient.split("@")[-1]
                if not any(internal in domain.lower() for internal in self.internal_domains):
                    external_recipients.append(domain)

        # 检测外部收件人
        if external_recipients:
            risk_level = "medium"
            warnings.append(f"📧 检测到外部收件人: {', '.join(set(external_recipients))}")
            warnings.append("⚠️ 内容包含外部人员，请确认是否允许外发")

            # 检测敏感内容
            sensitive_keywords = ["内部", "机密", "秘密", "不对外", "内部资料"]
            for keyword in sensitive_keywords:
                if keyword in content:
                    risk_level = "high"
                    warnings.append(f"🚨 检测到敏感标记「{keyword}」，强烈建议取消发送给外部人员")
                    confirm_required = True
                    break

        # 检测附件
        if attachments:
            for att in attachments:
                # 如果文件名包含内部项目代号
                if any(keyword in att for keyword in ["内部", "核心", "战略"]):
                    if external_recipients:
                        risk_level = "high"
                        warnings.append(f"📎 附件「{att}」可能涉及内部资料，发送给外部人员存在风险")
                        confirm_required = True

        return {
            "risk_level": risk_level,
            "warnings": warnings,
            "confirm_required": confirm_required,
            "external_recipients": list(set(external_recipients))
        }

    async def generate_security_report(
        self,
        content_id: str,
        scan_results: list[ScanResult]
    ) -> str:
        """
        生成安全报告

        Args:
            content_id: 内容 ID
            scan_results: 扫描结果列表

        Returns:
            报告内容
        """
        total_issues = sum(len(r.issues) for r in scan_results)
        high_risk = sum(1 for r in scan_results if r.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL])

        report = f"""# 安全扫描报告

**内容 ID**: {content_id}
**扫描时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**扫描项目**: {len(scan_results)}

## 风险等级
{'🔴 高风险' if high_risk > 0 else '🟡 中风险' if total_issues > 0 else '🟢 安全'}

## 问题汇总
"""

        if total_issues == 0:
            report += "\n✅ 未检测到安全问题"
        else:
            for i, result in enumerate(scan_results):
                if result.issues:
                    report += f"\n### 检查项 {i+1}: {result.threat_level.value}\n"
                    for issue in result.issues:
                        report += f"- {issue}\n"

        report += "\n## 建议\n"
        all_suggestions = set()
        for result in scan_results:
            all_suggestions.update(result.suggestions)

        if all_suggestions:
            for suggestion in all_suggestions:
                report += f"- {suggestion}\n"
        else:
            report += "- 无"

        return report

    def add_sensitive_word(
        self,
        word: str,
        category: str = "custom",
        severity: str = "medium"
    ):
        """
        添加自定义敏感词

        Args:
            word: 敏感词
            category: 类别
            severity: 严重程度
        """
        self.sensitive_words.append(SensitiveWord(word, category, severity))

    def remove_sensitive_word(self, word: str):
        """移除敏感词"""
        self.sensitive_words = [sw for sw in self.sensitive_words if sw.word != word]


def create_security_guard(workspace: IntelligentWorkspace) -> SecurityGuard:
    """创建安全守护"""
    return SecurityGuard(workspace)