"""
审计者Agent (Auditor Agent)

Full migration complete. → livingtree.core.auditor

核心功能：
1. 红队验证 - 主动寻找生成内容的漏洞
2. 一致性检查 - 验证报告与代码的数值一致性
3. 法规引用检查 - 检测过期法规
4. EvoSkill黑名单 - 记录陷阱模式，避免重复犯错
"""
from .auditor_agent import AuditorAgent, AuditResult, AuditIssue
from .blacklist_manager import BlacklistManager

__all__ = [
    "AuditorAgent",
    "AuditResult",
    "AuditIssue",
    "BlacklistManager",
]