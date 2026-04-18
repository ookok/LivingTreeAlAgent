"""
政策合规与知识库模块
====================

法规标准库 + 类比项目 + 排污许可查询

Author: Hermes Desktop EIA System
"""

from .policy_engine import (
    StandardType,
    StandardLevel,
    Standard,
    StandardClause,
    SimilarProject,
    PermitInfo,
    ComplianceCheckResult,
    StandardsDatabase,
    SimilarProjectsFinder,
    PollutionPermitChecker,
    PolicyKnowledgeEngine,
    get_policy_engine,
)

__all__ = [
    "StandardType",
    "StandardLevel",
    "Standard",
    "StandardClause",
    "SimilarProject",
    "PermitInfo",
    "ComplianceCheckResult",
    "StandardsDatabase",
    "SimilarProjectsFinder",
    "PollutionPermitChecker",
    "PolicyKnowledgeEngine",
    "get_policy_engine",
]
