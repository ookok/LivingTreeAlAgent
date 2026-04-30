"""
Hermes Skill Factory - 技能工厂模块

提供自动化技能生成、模板管理、代码生成等功能。

核心组件：
1. SkillFactory - 技能工厂主类
2. SkillTemplateEngine - 技能模板引擎
3. SkillGenerator - 技能代码生成器
4. SkillRegistryIntegrator - 与现有技能注册中心的集成

遵循自我进化原则：
- 从配置自动生成技能代码
- 支持技能版本自动管理
- 与现有技能进化系统无缝集成

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

from .skill_factory import SkillFactory
from .skill_template_engine import SkillTemplateEngine
from .skill_generator import SkillGenerator
from .registry_integrator import SkillRegistryIntegrator
from .skill_config import SkillConfig, ParameterConfig, ToolConfig

__all__ = [
    "SkillFactory",
    "SkillTemplateEngine",
    "SkillGenerator",
    "SkillRegistryIntegrator",
    "SkillConfig",
    "ParameterConfig",
    "ToolConfig",
]

# 创建全局实例
skill_factory = SkillFactory()
template_engine = SkillTemplateEngine()
registry_integrator = SkillRegistryIntegrator()


def get_skill_factory() -> SkillFactory:
    """获取技能工厂实例"""
    return skill_factory


def get_template_engine() -> SkillTemplateEngine:
    """获取模板引擎实例"""
    return template_engine


def get_registry_integrator() -> SkillRegistryIntegrator:
    """获取注册中心集成器实例"""
    return registry_integrator