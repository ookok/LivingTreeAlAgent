"""
任务拆解技能模块
================

实现核心拆解 SKILL：
1. ArchitectureDesigner - 架构设计与系统规划
2. CodeRefactorer - 代码重构与优化
3. TaskSplitterPro - 智能任务拆解大师
"""

import logging
from typing import Dict, List, Any, Optional
from enum import Enum

from .skill_registry import (
    SkillManifest, SkillCategory, SkillInput, SkillOutput,
    AgentType, OutputType, SkillEvolution,
)
from ..planning.decomposer import TaskPlanner, TaskNode, TaskPlan

logger = logging.getLogger(__name__)


class DecompositionSkillType(Enum):
    ARCHITECTURE = "architecture"
    REFACTORING = "refactoring"
    TASK_SPLIT = "task_split"


class BaseDecompositionSkill:
    def __init__(self, skill_type: DecompositionSkillType):
        self.skill_type = skill_type
        self.planner = TaskPlanner(max_depth=3, complexity_threshold=0.5)

    def get_manifest(self) -> SkillManifest:
        raise NotImplementedError

    def activate(self, requirement: str, **kwargs) -> TaskPlan:
        raise NotImplementedError


class ArchitectureDesignerSkill(BaseDecompositionSkill):
    SKILL_ID = "architecture_designer"

    def __init__(self):
        super().__init__(DecompositionSkillType.ARCHITECTURE)

    def get_manifest(self) -> SkillManifest:
        return SkillManifest(
            id=self.SKILL_ID,
            name="架构设计与系统规划",
            description="AI架构师级拆解工具，专治需求模糊、模块混乱、依赖复杂的大型项目",
            category=SkillCategory.PLANNING,
            agent=AgentType.PLANNER,
            trigger_phrases=["架构设计", "系统规划", "微服务架构", "高可用", "并发系统", "架构师"],
            inputs=[
                SkillInput(name="requirement", description="业务需求描述", type="string", required=True),
                SkillInput(name="tech_stack", description="目标技术栈（可选）", type="string", required=False),
                SkillInput(name="constraints", description="约束条件（可选）", type="string", required=False),
            ],
            outputs=[
                SkillOutput(type=OutputType.TEXT, description="架构设计文档"),
                SkillOutput(type=OutputType.ARTIFACTS, description="系统架构图"),
            ],
            tools=["global_model_router", "knowledge_graph"],
            conversation_starters=["我需要设计一个微服务架构", "帮我规划一个高可用系统", "如何设计百万级并发系统？"],
            examples=["激活【架构设计与系统规划】SKILL。输出：系统架构图、服务拆分清单、核心技术选型、缓存策略、数据库设计方案"],
            priority=9,
            evolution=SkillEvolution.STABLE,
        )

    def activate(self, requirement: str, **kwargs) -> TaskPlan:
        logger.info(f"[ArchitectureDesigner] 激活技能，需求: {requirement[:50]}...")
        full_requirement = requirement
        if kwargs.get("tech_stack"):
            full_requirement += f"，技术栈：{kwargs['tech_stack']}"
        if kwargs.get("constraints"):
            full_requirement += f"，约束条件：{kwargs['constraints']}"
        return self.planner.plan(
            description=full_requirement, intent_type="planning", complexity=0.8)


class CodeRefactorerSkill(BaseDecompositionSkill):
    SKILL_ID = "code_refactorer"

    def __init__(self):
        super().__init__(DecompositionSkillType.REFACTORING)

    def get_manifest(self) -> SkillManifest:
        return SkillManifest(
            id=self.SKILL_ID,
            name="代码重构与优化",
            description="专治屎山代码、复杂嵌套、逻辑冗余，精准拆解为高内聚、低耦合的独立函数/模块",
            category=SkillCategory.DEVELOPMENT,
            agent=AgentType.CODE_EXPERT,
            trigger_phrases=["重构", "优化", "代码拆解", "解耦", "重构代码", "代码优化"],
            inputs=[
                SkillInput(name="code", description="代码片段或代码描述", type="string", required=True),
                SkillInput(name="requirements", description="重构要求（可选）", type="string", required=False),
            ],
            outputs=[
                SkillOutput(type=OutputType.CODE, description="重构后的代码"),
                SkillOutput(type=OutputType.TEXT, description="重构说明文档"),
            ],
            tools=["refactoring_engine", "code_generator"],
            conversation_starters=["帮我重构这段复杂代码", "优化这段代码的结构", "如何解耦这个模块？"],
            examples=["激活【代码重构与优化】SKILL。要求：拆分独立函数、消除重复代码、添加注释、保持原有业务逻辑不变"],
            priority=8,
            evolution=SkillEvolution.STABLE,
        )

    def activate(self, code: str, **kwargs) -> TaskPlan:
        logger.info(f"[CodeRefactorer] 激活技能，代码长度: {len(code)}")
        full_requirement = f"代码：{code}"
        if kwargs.get("requirements"):
            full_requirement += f"，要求：{kwargs['requirements']}"
        return self.planner.plan(
            description=full_requirement, intent_type="code", complexity=0.6)


class TaskSplitterProSkill(BaseDecompositionSkill):
    SKILL_ID = "task_splitter_pro"

    def __init__(self):
        super().__init__(DecompositionSkillType.TASK_SPLIT)

    def get_manifest(self) -> SkillManifest:
        return SkillManifest(
            id=self.SKILL_ID,
            name="智能任务拆解大师",
            description="通用型任务拆解SKILL，可拆解需求、项目、文档、Bug等各类复杂任务",
            category=SkillCategory.PLANNING,
            agent=AgentType.PLANNER,
            trigger_phrases=["拆解任务", "任务分解", "任务规划", "分解任务", "任务清单"],
            inputs=[
                SkillInput(name="requirement", description="任务描述", type="string", required=True),
                SkillInput(name="phases", description="期望阶段数（可选）", type="integer", required=False),
            ],
            outputs=[
                SkillOutput(type=OutputType.TEXT, description="任务清单"),
                SkillOutput(type=OutputType.ARTIFACTS, description="任务依赖图"),
            ],
            tools=["task_planning", "task_execution_engine"],
            conversation_starters=["帮我拆解这个项目", "规划一下开发任务", "如何分解这个需求？"],
            examples=["激活【智能任务拆解大师】SKILL。拆解'开发在线教育管理系统'全流程任务"],
            priority=8,
            evolution=SkillEvolution.STABLE,
        )

    def activate(self, requirement: str, **kwargs) -> TaskPlan:
        logger.info(f"[TaskSplitterPro] 激活技能，需求: {requirement[:50]}...")
        return self.planner.plan(
            description=requirement, intent_type="planning", complexity=0.7)


class DecompositionSkillFactory:
    _skills: Dict[DecompositionSkillType, BaseDecompositionSkill] = {}

    @classmethod
    def get_skill(cls, skill_type: DecompositionSkillType) -> BaseDecompositionSkill:
        if skill_type not in cls._skills:
            cls._skills[skill_type] = cls._create_skill(skill_type)
        return cls._skills[skill_type]

    @classmethod
    def _create_skill(cls, skill_type: DecompositionSkillType) -> BaseDecompositionSkill:
        if skill_type == DecompositionSkillType.ARCHITECTURE:
            return ArchitectureDesignerSkill()
        elif skill_type == DecompositionSkillType.REFACTORING:
            return CodeRefactorerSkill()
        elif skill_type == DecompositionSkillType.TASK_SPLIT:
            return TaskSplitterProSkill()
        else:
            raise ValueError(f"未知技能类型: {skill_type}")

    @classmethod
    def register_all_skills(cls, registry):
        for skill_type in DecompositionSkillType:
            skill = cls.get_skill(skill_type)
            manifest = skill.get_manifest()
            registry.register(manifest)
            logger.info(f"[DecompositionSkillFactory] 注册技能: {manifest.name}")

    @classmethod
    def list_all_skills(cls) -> List[SkillManifest]:
        manifests = []
        for skill_type in DecompositionSkillType:
            skill = cls.get_skill(skill_type)
            manifests.append(skill.get_manifest())
        return manifests


def get_architecture_designer() -> ArchitectureDesignerSkill:
    return DecompositionSkillFactory.get_skill(DecompositionSkillType.ARCHITECTURE)


def get_code_refactorer() -> CodeRefactorerSkill:
    return DecompositionSkillFactory.get_skill(DecompositionSkillType.REFACTORING)


def get_task_splitter() -> TaskSplitterProSkill:
    return DecompositionSkillFactory.get_skill(DecompositionSkillType.TASK_SPLIT)


def register_decomposition_skills(registry):
    DecompositionSkillFactory.register_all_skills(registry)


__all__ = [
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
