"""
Skill Distillation - 技能蒸馏集成模块

集成外部蒸馏技能仓库，包括：
- nuwa-skill
- yourself-skill
- anti-distill
- ex-skill
- bazi-skill
- steve-jobs-skill
- x-mentor-skill
- master-skill
- boss-skills
- elon-musk-skill
- munger-skill
- naval-skill
- feynman-skill
- taleb-skill
- zhang-yiming-skill
- reasoning-skill
- khazix-skills

提供技能发现、导入、转换和注册功能。

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

from .distillation_integrator import DistillationIntegrator
from .skill_finder import SkillFinder
from .skill_converter import SkillConverter
from .distillation_config import DistillationConfig, SkillSource, DEFAULT_SKILL_SOURCES
from .distilled_skills_tool import (
    DistilledSkillTool,
    get_distilled_tools,
    get_tool_by_name,
    get_tools_by_category,
    register_all_tools,
    get_skill_categories,
    get_stats,
    get_thinking_skills,
    get_business_skills,
    get_philosophy_skills,
    get_science_skills,
    get_utility_skills
)

__all__ = [
    "DistillationIntegrator",
    "SkillFinder",
    "SkillConverter",
    "DistillationConfig",
    "SkillSource",
    "DEFAULT_SKILL_SOURCES",
    "DistilledSkillTool",
    "get_distilled_tools",
    "get_tool_by_name",
    "get_tools_by_category",
    "register_all_tools",
    "get_skill_categories",
    "get_stats",
    "get_thinking_skills",
    "get_business_skills",
    "get_philosophy_skills",
    "get_science_skills",
    "get_utility_skills",
]

# 创建全局实例
distillation_integrator = DistillationIntegrator()
skill_finder = SkillFinder()
skill_converter = SkillConverter()


def get_distillation_integrator() -> DistillationIntegrator:
    """获取蒸馏技能集成器"""
    return distillation_integrator


def get_skill_finder() -> SkillFinder:
    """获取技能发现器"""
    return skill_finder


def get_skill_converter() -> SkillConverter:
    """获取技能转换器"""
    return skill_converter