# Living Tree AI — 智能体自我升级系统
# Self-Upgrade System for Living Tree AI Assistant

"""
四大升级引擎（闭环架构）：

1. 本地左右互搏 (debate_engine.py)
   - Hermes 分饰 保守派/激进派，对同一议题辩论
   - 产出结构化辩论记录 + 矛盾点集合

2. 外部营养吸收 (external_absorption.py)
   - 抓取 Reddit/知乎/微博/GitHub 热点争论
   - AI 消化外部观点，标记差异

3. 安全审查管道 (safety_pipeline.py)
   - KeywordFilter → PatternMatch → 来源检查 → 人类审核

4. 人类修正回路 (human_reviewer.py)
   - 展示辩论记录与外部吸收结论
   - 人类可删除/改写/打标签 ✅认可/⚠️存疑/❌驳回

辅助组件：
- knowledge_base.py: 进化知识库（SQLite + 版本管理）
- evolution_scheduler.py: 闲置调度器（idle/conflict/publish/manual）
"""

from .system import SelfUpgradeSystem, get_self_upgrade_system
from .models import (
    DebateRole, DebateVerdict, HumanVerdict,
    DebateRecord, DebateArgument,
    ExternalInsight, ExternalSource,
    KnowledgeEntry, SafetyLevel,
    EvolutionTask, SystemConfig,
)

__all__ = [
    # 系统
    "SelfUpgradeSystem",
    "get_self_upgrade_system",
    # 模型
    "DebateRole", "DebateVerdict", "HumanVerdict",
    "DebateRecord", "DebateArgument",
    "ExternalInsight", "ExternalSource",
    "KnowledgeEntry", "SafetyLevel",
    "EvolutionTask", "SystemConfig",
]