"""Formal Logic — 亚里士多德形式逻辑工程实现."""
from .rule_engine import (
    RuleEngine, Rule, Fact, FactStatus,
    SyllogismVerifier, CategoricalProposition, Quantifier, SyllogismFigure, SyllogismResult,
)

__all__ = [
    "RuleEngine", "Rule", "Fact", "FactStatus",
    "SyllogismVerifier", "CategoricalProposition", "Quantifier", "SyllogismFigure", "SyllogismResult",
]
