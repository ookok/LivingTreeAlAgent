"""
任务拆解技能模块（Trae SKILL 风格）
====================================

实现 Trae IDE 的三款核心拆解 SKILL：
1. ArchitectureDesigner - 架构设计与系统规划
2. CodeRefactorer - 代码重构与优化
3. TaskSplitterPro - 智能任务拆解大师

集成方式：
- 通过 SkillRegistry 注册技能
- 通过 SkillExecutor 执行技能
- 支持 SOLO Plan 模式

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import logging
from typing import Dict, List, Any, Optional
from enum import Enum

from business.agent_skills.skill_registry import (
    SkillManifest,
    SkillCategory,
    SkillInput,
    SkillOutput,
    AgentType,
    OutputType,
    SkillEvolution,
)
from business.task_decomposer import (
    TaskDecomposer,
    DecomposedTask,
    ProcessType,
    create_architecture_task,
    create_refactoring_task,
    create_task_split_task,
)

logger = logging.getLogger(__name__)


class DecompositionSkillType(Enum):
    """拆解技能类型"""
    ARCHITECTURE = "architecture"
    REFACTORING = "refactoring"
    TASK_SPLIT = "task_split"


class BaseDecompositionSkill:
    """
    拆解技能基类
    """
    
    def __init__(self, skill_type: DecompositionSkillType):
        self.skill_type = skill_type
        self.decomposer = TaskDecomposer()
    
    def get_manifest(self) -> SkillManifest:
        """获取技能清单"""
        raise NotImplementedError
    
    def activate(self, requirement: str, **kwargs) -> DecomposedTask:
        """
        激活技能，执行任务拆解
        
        Args:
            requirement: 用户需求描述
            **kwargs: 额外参数
            
        Returns:
            DecomposedTask: 拆解后的任务
        """
        raise NotImplementedError
    
    def get_execution_summary(self, task: DecomposedTask) -> Dict[str, Any]:
        """
        获取执行摘要
        
        Args:
            task: 拆解后的任务
            
        Returns:
            执行摘要字典
        """
        return {
            "task_id": task.task_id,
            "original_question": task.original_question,
            "total_steps": task.total_steps,
            "completed_steps": task.completed_steps,
            "progress": task.progress,
            "process_type": task.process_type.value,
            "steps": [step.to_dict() for step in task.steps],
        }


class ArchitectureDesignerSkill(BaseDecompositionSkill):
    """
    架构设计与系统规划 SKILL
    
    核心定位：AI架构师级拆解工具，专治"需求模糊、模块混乱、依赖复杂"的大型项目
    
    拆解核心能力：
    - 需求分层拆解：自动梳理业务核心模块、子功能、依赖关系与数据流
    - 架构可视化拆分：生成分层架构图、微服务拆分清单、数据库 ER 图
    - 技术栈精准拆分：按模块推荐适配技术
    
    适配场景：新项目立项、系统重构、大型需求拆解
    """
    
    SKILL_ID = "architecture_designer"
    
    def __init__(self):
        super().__init__(DecompositionSkillType.ARCHITECTURE)
    
    def get_manifest(self) -> SkillManifest:
        return SkillManifest(
            id=self.SKILL_ID,
            name="架构设计与系统规划",
            description="AI架构师级拆解工具，专治需求模糊、模块混乱、依赖复杂的大型项目，从0到1把模糊需求拆成可落地的模块化方案",
            category=SkillCategory.PLANNING,
            agent=AgentType.PLANNER,
            trigger_phrases=[
                "架构设计",
                "系统规划",
                "微服务架构",
                "高可用",
                "并发系统",
                "架构师",
            ],
            inputs=[
                SkillInput(
                    name="requirement",
                    description="业务需求描述，如：开发百万级并发电商秒杀系统",
                    type="string",
                    required=True,
                ),
                SkillInput(
                    name="tech_stack",
                    description="目标技术栈（可选）",
                    type="string",
                    required=False,
                ),
                SkillInput(
                    name="constraints",
                    description="约束条件（可选）",
                    type="string",
                    required=False,
                ),
            ],
            outputs=[
                SkillOutput(type=OutputType.TEXT, description="架构设计文档"),
                SkillOutput(type=OutputType.ARTIFACTS, description="系统架构图"),
            ],
            tools=[
                "global_model_router",
                "knowledge_graph",
            ],
            conversation_starters=[
                "我需要设计一个微服务架构",
                "帮我规划一个高可用系统",
                "如何设计百万级并发系统？",
            ],
            examples=[
                "激活【架构设计与系统规划】SKILL。我要开发百万级并发电商秒杀系统，要求：微服务架构、高可用、防超卖、数据最终一致。请输出：1.系统架构图 2.服务拆分清单 3.核心技术选型 4.缓存与防雪崩策略 5.数据库设计方案",
            ],
            priority=9,
            evolution=SkillEvolution.STABLE,
        )
    
    def activate(self, requirement: str, **kwargs) -> DecomposedTask:
        """
        激活架构设计技能
        
        Args:
            requirement: 用户需求描述
            **kwargs: 额外参数（tech_stack, constraints）
            
        Returns:
            DecomposedTask: 拆解后的架构设计任务
        """
        logger.info(f"[ArchitectureDesigner] 激活技能，需求: {requirement[:50]}...")
        
        # 构建完整需求描述
        full_requirement = requirement
        if kwargs.get("tech_stack"):
            full_requirement += f"，技术栈：{kwargs['tech_stack']}"
        if kwargs.get("constraints"):
            full_requirement += f"，约束条件：{kwargs['constraints']}"
        
        # 创建架构设计任务
        task = create_architecture_task(full_requirement)
        
        logger.info(f"[ArchitectureDesigner] 任务拆解完成，步骤数: {task.total_steps}")
        return task


class CodeRefactorerSkill(BaseDecompositionSkill):
    """
    代码重构与优化 SKILL
    
    核心定位：专治"屎山代码、复杂嵌套、逻辑冗余"，把臃肿混乱的代码块，
    精准拆解为"高内聚、低耦合"的独立函数/模块
    
    拆解核心能力：
    - 逻辑拆解：识别复杂嵌套、重复代码、冗余逻辑，提取公共方法
    - 依赖解耦：拆解模块间强耦合关系，拆分独立接口
    - 分层优化：按"控制器-服务-数据层"分层拆解
    
    适配场景：接手遗留系统、优化复杂业务代码、模块解耦重构
    """
    
    SKILL_ID = "code_refactorer"
    
    def __init__(self):
        super().__init__(DecompositionSkillType.REFACTORING)
    
    def get_manifest(self) -> SkillManifest:
        return SkillManifest(
            id=self.SKILL_ID,
            name="代码重构与优化",
            description="专治屎山代码、复杂嵌套、逻辑冗余，把臃肿混乱的代码块精准拆解为高内聚、低耦合的独立函数/模块",
            category=SkillCategory.DEVELOPMENT,
            agent=AgentType.CODE_EXPERT,
            trigger_phrases=[
                "重构",
                "优化",
                "代码拆解",
                "解耦",
                "重构代码",
                "代码优化",
            ],
            inputs=[
                SkillInput(
                    name="code",
                    description="代码片段或代码描述",
                    type="string",
                    required=True,
                ),
                SkillInput(
                    name="requirements",
                    description="重构要求（可选）",
                    type="string",
                    required=False,
                ),
            ],
            outputs=[
                SkillOutput(type=OutputType.CODE, description="重构后的代码"),
                SkillOutput(type=OutputType.TEXT, description="重构说明文档"),
            ],
            tools=[
                "refactoring_engine",
                "code_generator",
            ],
            conversation_starters=[
                "帮我重构这段复杂代码",
                "优化这段代码的结构",
                "如何解耦这个模块？",
            ],
            examples=[
                "激活【代码重构与优化】SKILL。请拆解优化这段复杂订单逻辑代码：[粘贴代码片段]。要求：1.拆分独立函数 2.消除重复代码 3.添加注释 4.保持原有业务逻辑不变",
            ],
            priority=8,
            evolution=SkillEvolution.STABLE,
        )
    
    def activate(self, code: str, **kwargs) -> DecomposedTask:
        """
        激活代码重构技能
        
        Args:
            code: 代码片段或代码描述
            **kwargs: 额外参数（requirements）
            
        Returns:
            DecomposedTask: 拆解后的重构任务
        """
        logger.info(f"[CodeRefactorer] 激活技能，代码长度: {len(code)}")
        
        # 构建完整需求描述
        full_requirement = f"代码：{code}"
        if kwargs.get("requirements"):
            full_requirement += f"，要求：{kwargs['requirements']}"
        
        # 创建重构任务
        task = create_refactoring_task(full_requirement)
        
        logger.info(f"[CodeRefactorer] 任务拆解完成，步骤数: {task.total_steps}")
        return task


class TaskSplitterProSkill(BaseDecompositionSkill):
    """
    智能任务拆解大师 SKILL
    
    核心定位：通用型任务拆解SKILL，不局限于代码开发，可拆解需求、项目、文档、Bug等各类复杂任务
    
    拆解核心能力：
    - 全维度拆解：分阶段拆解为具体子任务
    - 优先级排序：自动区分核心任务、次要任务、边缘任务
    - 依赖梳理：标注任务间依赖关系，支持并行开发
    - 风险预判：识别高风险任务，提前标注应对方案
    
    适配场景：新项目规划、大型需求拆解、多模块并行开发、项目进度管理
    """
    
    SKILL_ID = "task_splitter_pro"
    
    def __init__(self):
        super().__init__(DecompositionSkillType.TASK_SPLIT)
    
    def get_manifest(self) -> SkillManifest:
        return SkillManifest(
            id=self.SKILL_ID,
            name="智能任务拆解大师",
            description="通用型任务拆解SKILL，不局限于代码开发，可拆解需求、项目、文档、Bug等各类复杂任务，输出优先级+依赖关系+执行步骤的拆解清单",
            category=SkillCategory.PLANNING,
            agent=AgentType.PLANNER,
            trigger_phrases=[
                "拆解任务",
                "任务分解",
                "任务规划",
                "分解任务",
                "任务清单",
            ],
            inputs=[
                SkillInput(
                    name="requirement",
                    description="任务描述，如：开发在线教育管理系统",
                    type="string",
                    required=True,
                ),
                SkillInput(
                    name="phases",
                    description="期望阶段数（可选）",
                    type="integer",
                    required=False,
                ),
            ],
            outputs=[
                SkillOutput(type=OutputType.TEXT, description="任务清单"),
                SkillOutput(type=OutputType.ARTIFACTS, description="任务依赖图"),
            ],
            tools=[
                "task_planning",
                "task_execution_engine",
            ],
            conversation_starters=[
                "帮我拆解这个项目",
                "规划一下开发任务",
                "如何分解这个需求？",
            ],
            examples=[
                "激活【智能任务拆解大师】SKILL。请拆解'开发在线教育管理系统'全流程任务，要求：1.分阶段拆解 2.标注优先级 3.梳理依赖关系 4.识别高风险点 5.输出可直接执行的任务清单",
            ],
            priority=8,
            evolution=SkillEvolution.STABLE,
        )
    
    def activate(self, requirement: str, **kwargs) -> DecomposedTask:
        """
        激活任务拆解技能
        
        Args:
            requirement: 用户需求描述
            **kwargs: 额外参数（phases）
            
        Returns:
            DecomposedTask: 拆解后的任务
        """
        logger.info(f"[TaskSplitterPro] 激活技能，需求: {requirement[:50]}...")
        
        # 创建任务拆解任务
        max_steps = kwargs.get("phases", 5)
        task = create_task_split_task(requirement, max_steps=max_steps)
        
        logger.info(f"[TaskSplitterPro] 任务拆解完成，步骤数: {task.total_steps}")
        return task


class DecompositionSkillFactory:
    """
    拆解技能工厂
    
    提供便捷的技能创建和访问方法
    """
    
    _skills: Dict[DecompositionSkillType, BaseDecompositionSkill] = {}
    
    @classmethod
    def get_skill(cls, skill_type: DecompositionSkillType) -> BaseDecompositionSkill:
        """
        获取指定类型的拆解技能
        
        Args:
            skill_type: 技能类型
            
        Returns:
            对应的拆解技能实例
        """
        if skill_type not in cls._skills:
            cls._skills[skill_type] = cls._create_skill(skill_type)
        return cls._skills[skill_type]
    
    @classmethod
    def _create_skill(cls, skill_type: DecompositionSkillType) -> BaseDecompositionSkill:
        """创建技能实例"""
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
        """
        注册所有拆解技能到技能注册中心
        
        Args:
            registry: SkillRegistry 实例
        """
        for skill_type in DecompositionSkillType:
            skill = cls.get_skill(skill_type)
            manifest = skill.get_manifest()
            registry.register(manifest)
            logger.info(f"[DecompositionSkillFactory] 注册技能: {manifest.name}")
    
    @classmethod
    def list_all_skills(cls) -> List[SkillManifest]:
        """列出所有拆解技能的清单"""
        manifests = []
        for skill_type in DecompositionSkillType:
            skill = cls.get_skill(skill_type)
            manifests.append(skill.get_manifest())
        return manifests


# 便捷函数
def get_architecture_designer() -> ArchitectureDesignerSkill:
    """获取架构设计技能实例"""
    return DecompositionSkillFactory.get_skill(DecompositionSkillType.ARCHITECTURE)


def get_code_refactorer() -> CodeRefactorerSkill:
    """获取代码重构技能实例"""
    return DecompositionSkillFactory.get_skill(DecompositionSkillType.REFACTORING)


def get_task_splitter() -> TaskSplitterProSkill:
    """获取任务拆解技能实例"""
    return DecompositionSkillFactory.get_skill(DecompositionSkillType.TASK_SPLIT)


def register_decomposition_skills(registry):
    """注册所有拆解技能"""
    DecompositionSkillFactory.register_all_skills(registry)


__all__ = [
    # 枚举类型
    "DecompositionSkillType",
    # 技能类
    "BaseDecompositionSkill",
    "ArchitectureDesignerSkill",
    "CodeRefactorerSkill",
    "TaskSplitterProSkill",
    # 工厂类
    "DecompositionSkillFactory",
    # 便捷函数
    "get_architecture_designer",
    "get_code_refactorer",
    "get_task_splitter",
    "register_decomposition_skills",
]