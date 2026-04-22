"""
Agent Skills 集成模块
===================

参考 https://github.com/addyosmani/agent-skills 项目，
将生产级工程技能集成到 LivingTree AI Agent 中。

核心功能：
- 技能注册和管理
- Markdown 技能加载
- 工作流执行引擎
- 斜杠命令系统
- 上下文感知加载

Author: Hermes Desktop Team
Date: 2026-04-22
"""

from core.agent_skills.skill_registry import SkillRegistry, SkillManifest, SkillCategory
from core.agent_skills.skill_loader import SkillLoader
from core.agent_skills.skill_executor import SkillExecutor
from core.agent_skills.slash_commands import SlashCommandRegistry, SlashCommand
from core.agent_skills.context_aware import ContextAwareLoader
from core.agent_skills.initializer import AgentSkillsInitializer

__all__ = [
    "SkillRegistry",
    "SkillManifest", 
    "SkillCategory",
    "SkillLoader",
    "SkillExecutor",
    "SlashCommandRegistry",
    "SlashCommand",
    "ContextAwareLoader",
    "AgentSkillsInitializer",
]
