"""
形式化验证引擎

Full migration complete. → livingtree.core.formal_verification

核心功能：
1. 约束验证（A > B等逻辑）
2. 数值范围验证
3. 公式正确性验证
4. 一致性检查
5. 关键数据验证
"""
from .verification_engine import FormalVerifier, VerificationResult, Constraint
from .rules_engine import RulesEngine, BusinessRule

__all__ = [
    "FormalVerifier",
    "VerificationResult",
    "Constraint",
    "RulesEngine",
    "BusinessRule",
]