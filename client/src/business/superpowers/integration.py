"""
Superpowers 与现有技能系统的集成

将 Superpowers 框架集成到现有的 skill_evolution 系统中
"""

import asyncio
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass

from core.skill_evolution import (
    SkillEvolutionAgent,
    TaskSkill,
    TaskStatus as EvolutionTaskStatus,
    create_agent
)

from .superpowers_engine import SuperpowersEngine, get_superpowers_engine
from .skills import Skill, SkillRegistry, get_skill_registry
from .workflow import WorkflowManager, get_workflow_manager
from .trigger_system import TriggerSystem, get_trigger_system


class EvolutionSkillAdapter(Skill):
    """
    现有技能系统适配器

    将现有的 TaskSkill 适配为 Superpowers 技能
    """

    def __init__(self, task_skill: TaskSkill):
        super().__init__()
        self.task_skill = task_skill
        self.metadata.skill_id = task_skill.skill_id
        self.metadata.name = task_skill.name
        self.metadata.description = task_skill.description
        self.metadata.category = task_skill.category or "general"
        self.metadata.triggers = task_skill.tags or []

    async def execute(
        self,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行技能

        Args:
            parameters: 技能参数

        Returns:
            Dict: 执行结果
        """
        # 这里可以调用现有的技能执行逻辑
        return {
            "success": True,
            "skill_id": self.task_skill.skill_id,
            "name": self.task_skill.name,
            "parameters": parameters,
            "result": f"Executed skill: {self.task_skill.name}"
        }


class SuperpowersIntegration:
    """
    Superpowers 集成

    将 Superpowers 框架与现有技能系统集成
    """

    def __init__(self, agent: Optional[SkillEvolutionAgent] = None):
        self.superpowers = get_superpowers_engine()
        self.evolution_agent = agent or create_agent()
        self.skill_registry = get_skill_registry()
        self.workflow_manager = get_workflow_manager()
        self.trigger_system = get_trigger_system()

    async def initialize(self):
        """
        初始化集成
        """
        await self.superpowers.initialize()
        await self._sync_skills()
        await self._setup_workflows()

    async def _sync_skills(self):
        """
        同步现有技能到 Superpowers
        """
        # 获取现有技能
        skills = await self._get_existing_skills()
        
        # 注册为 Superpowers 技能
        for skill in skills:
            adapter = EvolutionSkillAdapter(skill)
            await self.skill_registry.register_skill(adapter)
            print(f"[SuperpowersIntegration] 同步技能: {skill.name}")

    async def _get_existing_skills(self) -> List[TaskSkill]:
        """
        获取现有技能

        Returns:
            List[TaskSkill]: 现有技能列表
        """
        # 这里应该调用现有技能系统的 API 获取技能列表
        # 暂时返回模拟数据
        return []

    async def _setup_workflows(self):
        """
        设置工作流
        """
        # 创建默认工作流
        workflows = [
            ("技能开发工作流", "技能开发的完整流程：分析 → 设计 → 实现 → 测试 → 部署"),
            ("技能优化工作流", "技能优化流程：分析 → 改进 → 测试 → 验证")
        ]

        for name, description in workflows:
            await self.workflow_manager.create_workflow(name, description)

    async def execute_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行任务

        Args:
            task: 任务描述
            context: 上下文

        Returns:
            Dict: 执行结果
        """
        # 分析上下文，推荐技能
        recommended_skills = await self.trigger_system.analyze_context(task)

        # 执行推荐的技能
        results = []
        for skill_id in recommended_skills:
            result = await self.superpowers.execute_skill(skill_id, context or {})
            results.append({
                "skill_id": skill_id,
                "result": result
            })

        # 如果没有推荐技能，使用现有的技能系统
        if not results:
            result = self.evolution_agent.execute_task(task)
            results.append({
                "skill_id": "evolution_agent",
                "result": result
            })

        return {
            "task": task,
            "recommended_skills": recommended_skills,
            "results": results
        }

    async def run_workflow(
        self,
        workflow_name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        运行工作流

        Args:
            workflow_name: 工作流名称
            parameters: 工作流参数

        Returns:
            Dict: 工作流执行结果
        """
        state = await self.superpowers.run_workflow(workflow_name, parameters or {})
        return {
            "workflow": workflow_name,
            "state": {
                "status": state.status.value,
                "completed_tasks": state.completed_tasks,
                "pending_tasks": state.pending_tasks
            }
        }

    async def analyze_context(
        self,
        context: str
    ) -> Dict[str, Any]:
        """
        分析上下文

        Args:
            context: 上下文文本

        Returns:
            Dict: 分析结果
        """
        recommended_skills = await self.trigger_system.analyze_context(context)
        return {
            "context": context,
            "recommended_skills": recommended_skills
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        获取集成统计

        Returns:
            Dict: 统计信息
        """
        superpowers_stats = self.superpowers.get_stats()
        return {
            "superpowers": superpowers_stats,
            "evolution_agent": {
                "status": "active"
            }
        }


# 全局集成实例

_global_integration: Optional[SuperpowersIntegration] = None


def get_superpowers_integration(agent: Optional[SkillEvolutionAgent] = None) -> SuperpowersIntegration:
    """获取 Superpowers 集成"""
    global _global_integration
    if _global_integration is None:
        _global_integration = SuperpowersIntegration(agent)
    return _global_integration


def integrate_superpowers() -> SuperpowersIntegration:
    """
    集成 Superpowers

    Returns:
        SuperpowersIntegration: 集成实例
    """
    integration = get_superpowers_integration()
    asyncio.run(integration.initialize())
    return integration