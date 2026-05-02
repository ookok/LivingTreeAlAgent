"""
LivingTree 形式化验证引擎
=========================

Full migration from client/src/business/formal_verification/

核心功能：
1. 约束验证（A > B等逻辑）
2. 数值范围验证
3. 公式正确性验证
4. 一致性检查
5. 关键数据验证
"""

from .verification_engine import (
    FormalVerifier,
    Constraint,
    ConstraintType,
    VerificationStatus as FVVerificationStatus,
    VerificationResult,
    VerificationReport,
)

from .rules_engine import (
    RulesEngine,
    BusinessRule,
    RuleExecutionResult,
    EIA_Rules,
    FinancialRules,
)

__all__ = [
    "FormalVerifier",
    "Constraint",
    "ConstraintType",
    "FVVerificationStatus",
    "VerificationResult",
    "VerificationReport",
    "RulesEngine",
    "BusinessRule",
    "RuleExecutionResult",
    "EIA_Rules",
    "FinancialRules",
]
