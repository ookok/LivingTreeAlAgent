"""
Agent Skills 集成模块 - 向后兼容层

⚠️ 已迁移至 livingtree.core.skills
本模块保留为兼容层，所有导入将自动重定向到新位置。
"""

from livingtree.core.skills import *

__all__ = [
    'SkillRegistry', 'SkillManifest', 'SkillCategory',
    'SkillInput', 'SkillOutput', 'AgentType', 'OutputType', 'SkillEvolution',
    'SkillLoader', 'SkillExecutor',
    'SlashCommandRegistry', 'SlashCommand',
    'ContextAwareLoader', 'AgentSkillsInitializer',
    'AutoEvolutionSkill', 'PatternDetector', 'SkillSeedGenerator', 'SkillSeed',
    'EvolutionCandidate', 'InteractionPattern',
    'CronScheduler', 'CronParser', 'NaturalLanguageScheduler', 'ScheduledTask',
    'HonchoUserModeling', 'UserProfile', 'UserPreference', 'Dialect', 'CommunicationStyle',
    'TaskDecompositionSkills', 'BaseDecompositionSkill',
    'ArchitectureDesignerSkill', 'CodeRefactorerSkill', 'TaskSplitterProSkill',
    'DecompositionSkillFactory',
]
