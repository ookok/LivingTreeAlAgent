"""
自我身份系统 (Self Identity System)

核心功能：
1. 职业身份定义 - self_identity.json
2. KPI监控 - 代码覆盖率、报告格式正确性等
3. 元认知自我审查 - "我知道我知道什么，我知道我不知道什么"
4. Idle循环自动优化 - 在空闲时间主动重构

实现Meta-cognition（元认知）能力。
"""
from .self_identity import SelfIdentity, IdentityAuditResult, KPIDefinition

__all__ = [
    "SelfIdentity",
    "IdentityAuditResult",
    "KPIDefinition",
]