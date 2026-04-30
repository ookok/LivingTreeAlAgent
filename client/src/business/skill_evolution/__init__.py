"""
技能进化模块 (Skill Evolution)
遵循自我进化原则：从交互中进化技能，而非预置模板

架构指南参考: docs/LIVINGTREE_ARCHITECTURE_GUIDE.md (章节 5.3.2, 5.4.1)
"""

from business.skill_evolution.vibe_skill_builder import (
    VibeSkillBuilder,
    Skill as VibeSkill,
)

from business.skill_evolution.skill_encapsulation import (
    SkillEncapsulationEngine,
    Skill,
    SkillStatus,
    SkillTemplate,
)

from business.skill_evolution.skill_rating_system import (
    SkillRatingSystem,
    SkillRating,
    SkillFeedback,
    RatingType,
)

from business.skill_evolution.skill_version_control import (
    SkillVersionControl,
    SkillVersion,
    VersionStatus,
    VersionChangeType,
    VersionDiff,
)


__all__ = [
    # Vibe 技能构建器
    "VibeSkillBuilder",
    "VibeSkill",
    
    # 技能封装引擎
    "SkillEncapsulationEngine",
    "Skill",
    "SkillStatus",
    "SkillTemplate",
    
    # 技能评分系统
    "SkillRatingSystem",
    "SkillRating",
    "SkillFeedback",
    "RatingType",
    
    # 版本控制
    "SkillVersionControl",
    "SkillVersion",
    "VersionStatus",
    "VersionChangeType",
    "VersionDiff",
]
