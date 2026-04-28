"""
技能进化模块 (Skill Evolution)
遵循自我进化原则：从交互中进化技能，而非预置模板

架构指南参考: docs/LIVINGTREE_ARCHITECTURE_GUIDE.md (章节 5.3.2, 5.4.1)
"""

from client.src.business.skill_evolution.vibe_skill_builder import (
    VibeSkillBuilder,
    Skill,
)


__all__ = [
    "VibeSkillBuilder",
    "Skill",
]
