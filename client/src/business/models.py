"""
core/models.py - 统一数据模型导出

提供 SystemConfig 等通用数据模型
"""

from business.self_upgrade.models import (
    SystemConfig,
    DebateRole,
    DebateVerdict,
    DebateArgument,
    DebateRecord,
    ExternalSource,
    ExternalInsight,
    KnowledgeEntry,
    SafetyLevel,
    SafetyCheckResult,
    EvolutionTask,
)

__all__ = [
    "SystemConfig",
    "DebateRole",
    "DebateVerdict",
    "DebateArgument",
    "DebateRecord",
    "ExternalSource",
    "ExternalInsight",
    "KnowledgeEntry",
    "SafetyLevel",
    "SafetyCheckResult",
    "EvolutionTask",
]