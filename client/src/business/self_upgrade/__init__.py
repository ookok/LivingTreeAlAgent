# Living Tree AI — 智能体自我升级系统
# Self-Upgrade System for Living Tree AI Assistant
"""向后兼容shim - 已迁移至 livingtree.core.maintenance"""

from livingtree.core.maintenance import (
    SelfUpgradeSystem,
    get_self_upgrade_system,
    create_self_upgrade_system,
    check_safety,
    DebateRole, DebateVerdict, HumanVerdict,
    DebateRecord, DebateArgument,
    ExternalInsight, ExternalSource,
    KnowledgeEntry, SafetyLevel, SafetyCheckResult,
    EvolutionTask, SystemConfig,
    DebateEngine, ExternalAbsorption,
    SafetyPipeline, HumanReviewer,
    KnowledgeBase, EvolutionScheduler,
)

__all__ = [
    "SelfUpgradeSystem", "get_self_upgrade_system", "create_self_upgrade_system",
    "check_safety",
    "DebateRole", "DebateVerdict", "HumanVerdict",
    "DebateRecord", "DebateArgument",
    "ExternalInsight", "ExternalSource",
    "KnowledgeEntry", "SafetyLevel", "SafetyCheckResult",
    "EvolutionTask", "SystemConfig",
    "DebateEngine", "ExternalAbsorption",
    "SafetyPipeline", "HumanReviewer",
    "KnowledgeBase", "EvolutionScheduler",
]