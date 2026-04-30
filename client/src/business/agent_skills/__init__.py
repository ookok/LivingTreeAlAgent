"""
Agent Skills 集成模块
===================

参考以下项目增强：
- https://github.com/addyosmani/agent-skills 项目
- https://github.com/NousResearch/hermes-agent (SKILL.md 格式)

核心功能：
- 技能注册和管理（支持 Hermes SKILL.md 格式）
- Markdown 技能加载
- 工作流执行引擎
- 斜杠命令系统
- 上下文感知加载
- 自进化记忆机制 (AutoEvolutionSkill)
- 用户建模 (Honcho)
- 定时任务调度 (CronScheduler)

Author: Hermes Desktop Team
Date: 2026-04-22
Updated: 2026-04-25 (对齐 Hermes Agent)
"""

from client.src.business.agent_skills.skill_registry import (
    SkillRegistry, 
    SkillManifest, 
    SkillCategory,
    SkillInput,
    SkillOutput,
    AgentType,
    OutputType,
    SkillEvolution,
)
from client.src.business.agent_skills.skill_loader import SkillLoader
from client.src.business.agent_skills.skill_executor import SkillExecutor
from client.src.business.agent_skills.slash_commands import SlashCommandRegistry, SlashCommand
from client.src.business.agent_skills.context_aware import ContextAwareLoader
from client.src.business.agent_skills.initializer import AgentSkillsInitializer
from client.src.business.agent_skills.auto_evolution_skill import (
    AutoEvolutionSkill,
    PatternDetector,
    SkillSeedGenerator,
    InteractionPattern,
    SkillSeed,
    EvolutionCandidate,
)
from client.src.business.agent_skills.honcho_user_modeling import (
    HonchoUserModeling,
    UserProfile,
    UserPreference,
    Dialect,
    CommunicationStyle,
)
from client.src.business.agent_skills.cron_scheduler import (
    CronScheduler,
    ScheduledTask,
    TaskStatus,
    TaskPriority,
    CronParser,
    NaturalLanguageScheduler,
    ExecutionRecord,
)
from client.src.business.agent_skills.task_decomposition_skills import (
    DecompositionSkillType,
    BaseDecompositionSkill,
    ArchitectureDesignerSkill,
    CodeRefactorerSkill,
    TaskSplitterProSkill,
    DecompositionSkillFactory,
    get_architecture_designer,
    get_code_refactorer,
    get_task_splitter,
    register_decomposition_skills,
)

__all__ = [
    # 注册中心
    "SkillRegistry",
    "SkillManifest",
    "SkillCategory",
    "SkillInput",
    "SkillOutput",
    "AgentType",
    "OutputType",
    "SkillEvolution",
    # 加载器
    "SkillLoader",
    # 执行器
    "SkillExecutor",
    # 斜杠命令
    "SlashCommandRegistry",
    "SlashCommand",
    # 上下文加载
    "ContextAwareLoader",
    # 初始化器
    "AgentSkillsInitializer",
    # 自进化技能
    "AutoEvolutionSkill",
    "PatternDetector",
    "SkillSeedGenerator",
    "InteractionPattern",
    "SkillSeed",
    "EvolutionCandidate",
    # 用户建模
    "HonchoUserModeling",
    "UserProfile",
    "UserPreference",
    "Dialect",
    "CommunicationStyle",
    # 定时任务
    "CronScheduler",
    "ScheduledTask",
    "TaskStatus",
    "TaskPriority",
    "CronParser",
    "NaturalLanguageScheduler",
    "ExecutionRecord",
    # 任务拆解技能（Trae SKILL 风格）
    "DecompositionSkillType",
    "BaseDecompositionSkill",
    "ArchitectureDesignerSkill",
    "CodeRefactorerSkill",
    "TaskSplitterProSkill",
    "DecompositionSkillFactory",
    "get_architecture_designer",
    "get_code_refactorer",
    "get_task_splitter",
    "register_decomposition_skills",
]
