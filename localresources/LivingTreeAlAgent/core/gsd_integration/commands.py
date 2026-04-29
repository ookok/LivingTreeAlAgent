"""
GSD 命令接口

提供 GSD 工作流的命令行接口：
- /gsd-new-project: 新建项目
- /gsd-discuss-phase: 讨论阶段
- /gsd-plan-phase: 规划阶段
- /gsd-execute-phase: 执行阶段
- /gsd-verify-work: 验证工作
- /gsd-ship: 发布
- /gsd-progress: 进度
- /gsd-quick: 快速任务
"""

import asyncio
import time
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field

from .gsd_engine import (
    GSDEngine,
    GSDConfig,
    GSDPhase,
    GSDPlan,
    ProjectMetadata,
    DiscussionContext,
    ResearchResult,
    create_gsd_task,
    create_gsd_plan,
    get_gsd_engine,
    ExecutionMode,
    Granularity,
)
from .context_engineering import get_context_manager, ContextScope
from .planning import get_planner, get_orchestrator, Planner, ResearchAgent
from .state_manager import get_state_manager


@dataclass
class CommandResult:
    """命令结果"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)


class GSDCommands:
    """
    GSD 命令接口

    提供完整的 GSD 工作流命令
    """

    def __init__(self, workspace_path: Optional[str] = None):
        self.engine = get_gsd_engine(workspace_path)
        self.context_manager = get_context_manager()
        self.state_manager = get_state_manager()
        self.planner = get_planner()

    async def new_project(
        self,
        name: str,
        description: str,
        goals: List[str],
        constraints: Optional[List[str]] = None,
        tech_preferences: Optional[Dict[str, Any]] = None,
        scope_v1: Optional[List[str]] = None,
        scope_v2: Optional[List[str]] = None,
        out_of_scope: Optional[List[str]] = None
    ) -> CommandResult:
        """
        新建项目

        Args:
            name: 项目名称
            description: 项目描述
            goals: 目标列表
            constraints: 约束列表
            tech_preferences: 技术偏好
            scope_v1: v1 范围
            scope_v2: v2 范围
            out_of_scope: 范围外

        Returns:
            CommandResult: 命令结果
        """
        try:
            metadata = ProjectMetadata(
                name=name,
                description=description,
                goals=goals,
                constraints=constraints or [],
                tech_preferences=tech_preferences or {},
                scope_v1=scope_v1 or [],
                scope_v2=scope_v2 or [],
                out_of_scope=out_of_scope or []
            )

            project_id = self.engine.new_project(metadata)

            self.state_manager.init_project(project_id, name)

            self.context_manager.add_document(
                doc_id="project",
                title=name,
                content=description,
                scope=ContextScope.PROJECT,
                metadata={"goals": goals, "constraints": constraints}
            )

            return CommandResult(
                success=True,
                message=f"项目 '{name}' 创建成功",
                data={
                    "project_id": project_id,
                    "name": name,
                    "files_created": [
                        ".planning/PROJECT.md",
                        ".planning/REQUIREMENTS.md",
                        ".planning/ROADMAP.md",
                        ".planning/STATE.md"
                    ]
                }
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"创建项目失败: {str(e)}",
                errors=[str(e)]
            )

    async def discuss_phase(
        self,
        phase_id: int,
        visual_design: Optional[List[str]] = None,
        api_design: Optional[List[str]] = None,
        content_system: Optional[List[str]] = None,
        organization: Optional[List[str]] = None,
        decisions: Optional[Dict[str, Any]] = None
    ) -> CommandResult:
        """
        讨论阶段

        Args:
            phase_id: 阶段 ID
            visual_design: 视觉设计
            api_design: API 设计
            content_system: 内容系统
            organization: 组织
            decisions: 决策

        Returns:
            CommandResult: 命令结果
        """
        try:
            context = DiscussionContext(
                phase=phase_id,
                visual_design=visual_design or [],
                api_design=api_design or [],
                content_system=content_system or [],
                organization=organization or [],
                decisions=decisions or {}
            )

            self.engine.discuss_phase(phase_id, context)

            context_file = f".planning/phase_contexts/phase-{phase_id}-CONTEXT.md"

            return CommandResult(
                success=True,
                message=f"Phase {phase_id} 讨论完成",
                data={
                    "phase_id": phase_id,
                    "file_created": context_file
                }
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"讨论阶段失败: {str(e)}",
                errors=[str(e)]
            )

    async def plan_phase(
        self,
        phase_id: int,
        requirements: Optional[List[str]] = None,
        skip_research: bool = False
    ) -> CommandResult:
        """
        规划阶段

        Args:
            phase_id: 阶段 ID
            requirements: 需求列表
            skip_research: 跳过研究

        Returns:
            CommandResult: 命令结果
        """
        try:
            phase = None
            for p in self.engine.workspace.phases:
                if p.phase_id == phase_id:
                    phase = p
                    break

            if not phase:
                return CommandResult(
                    success=False,
                    message=f"Phase {phase_id} 不存在",
                    errors=[f"Phase {phase_id} not found"]
                )

            research = None
            if not skip_research:
                researcher = ResearchAgent()
                goals = self.engine.workspace.metadata.goals if self.engine.workspace.metadata else []
                constraints = self.engine.workspace.metadata.constraints if self.engine.workspace.metadata else []

                context_content = ""
                if phase.context:
                    context_content = str(phase.context.decisions)

                research = await researcher.research(context_content, goals, constraints)

            requirements = requirements or phase.description.split('\n')

            plans = []
            plan = await self.planner.create_plan(
                phase=phase_id,
                name=f"Phase {phase_id} Implementation",
                context=str(phase.description),
                requirements=requirements
            )
            plans.append(plan)

            created_plans = self.engine.plan_phase(phase_id, research, plans)

            plan_files = [
                f".planning/plans/phase-{phase_id}-{i+1}-PLAN.md"
                for i in range(len(created_plans))
            ]

            return CommandResult(
                success=True,
                message=f"Phase {phase_id} 规划完成",
                data={
                    "phase_id": phase_id,
                    "plans_created": len(created_plans),
                    "research_done": research is not None,
                    "files_created": plan_files
                }
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"规划阶段失败: {str(e)}",
                errors=[str(e)]
            )

    async def execute_phase(
        self,
        phase_id: int,
        parallel: bool = True
    ) -> CommandResult:
        """
        执行阶段

        Args:
            phase_id: 阶段 ID
            parallel: 是否并行执行

        Returns:
            CommandResult: 命令结果
        """
        try:
            results = self.engine.execute_phase(phase_id)

            summary_file = f".planning/summaries/phase-{phase_id}-SUMMARY.md"

            completed_count = 0
            total_count = 0

            for phase in self.engine.workspace.phases:
                if phase.phase_id == phase_id:
                    for plan in phase.plans:
                        total_count += len(plan.tasks)
                        for task in plan.tasks:
                            if task.status.value == "completed":
                                completed_count += 1
                    break

            return CommandResult(
                success=True,
                message=f"Phase {phase_id} 执行完成",
                data={
                    "phase_id": phase_id,
                    "completed_tasks": completed_count,
                    "total_tasks": total_count,
                    "parallel": parallel,
                    "file_created": summary_file
                }
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"执行阶段失败: {str(e)}",
                errors=[str(e)]
            )

    async def verify_work(self, phase_id: int) -> CommandResult:
        """
        验证工作

        Args:
            phase_id: 阶段 ID

        Returns:
            CommandResult: 命令结果
        """
        try:
            verification = self.engine.verify_phase(phase_id)

            verification_file = f".planning/verifications/phase-{phase_id}-VERIFICATION.md"

            status = "✅ 通过" if verification.passed else "❌ 失败"

            return CommandResult(
                success=True,
                message=f"Phase {phase_id} 验证结果: {status}",
                data={
                    "phase_id": phase_id,
                    "passed": verification.passed,
                    "passed_count": len(verification.items),
                    "failed_count": len(verification.failures),
                    "file_created": verification_file
                }
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"验证失败: {str(e)}",
                errors=[str(e)]
            )

    async def ship_phase(self, phase_id: int) -> CommandResult:
        """
        发布阶段

        Args:
            phase_id: 阶段 ID

        Returns:
            CommandResult: 命令结果
        """
        try:
            ship_info = self.engine.ship_phase(phase_id)

            return CommandResult(
                success=True,
                message=f"Phase {phase_id} 准备发布",
                data={
                    "phase_id": phase_id,
                    "branch": ship_info["branch"],
                    "commit_message": ship_info["message"],
                    "ready_for_pr": True
                }
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"发布失败: {str(e)}",
                errors=[str(e)]
            )

    async def complete_milestone(self) -> CommandResult:
        """
        完成里程碑

        Returns:
            CommandResult: 命令结果
        """
        try:
            info = self.engine.complete_milestone()

            return CommandResult(
                success=True,
                message=f"里程碑完成，共 {len(info['completed_phases'])} 个阶段",
                data={
                    "completed_phases": info["completed_phases"],
                    "total_phases": info["total_phases"],
                    "tag": info["tag"]
                }
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"完成里程碑失败: {str(e)}",
                errors=[str(e)]
            )

    async def add_phase(
        self,
        name: str,
        description: str
    ) -> CommandResult:
        """
        添加阶段

        Args:
            name: 阶段名称
            description: 阶段描述

        Returns:
            CommandResult: 命令结果
        """
        try:
            phase = self.engine.add_phase(name, description)
            self.state_manager.add_phase(phase.phase_id, name)

            return CommandResult(
                success=True,
                message=f"Phase {phase.phase_id} '{name}' 创建成功",
                data={
                    "phase_id": phase.phase_id,
                    "name": name,
                    "status": phase.status.value
                }
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"添加阶段失败: {str(e)}",
                errors=[str(e)]
            )

    def get_progress(self) -> CommandResult:
        """
        获取进度

        Returns:
            CommandResult: 命令结果
        """
        try:
            progress = self.engine.get_progress()

            return CommandResult(
                success=True,
                message="进度获取成功",
                data=progress
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"获取进度失败: {str(e)}",
                errors=[str(e)]
            )

    async def quick_task(
        self,
        description: str,
        use_research: bool = False,
        use_full: bool = False
    ) -> CommandResult:
        """
        快速任务

        Args:
            description: 任务描述
            use_research: 是否使用研究
            use_full: 是否使用完整模式

        Returns:
            CommandResult: 命令结果
        """
        try:
            task_dir = self.engine.quick_task(description)

            return CommandResult(
                success=True,
                message=f"快速任务 '{description}' 创建成功",
                data={
                    "description": description,
                    "directory": task_dir,
                    "research": use_research,
                    "full_mode": use_full
                }
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"创建快速任务失败: {str(e)}",
                errors=[str(e)]
            )

    def get_context_status(self) -> CommandResult:
        """
        获取上下文状态

        Returns:
            CommandResult: 命令结果
        """
        try:
            stats = self.context_manager.get_context_stats()

            return CommandResult(
                success=True,
                message="上下文状态获取成功",
                data=stats
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"获取上下文状态失败: {str(e)}",
                errors=[str(e)]
            )

    def get_state_summary(self) -> CommandResult:
        """
        获取状态摘要

        Returns:
            CommandResult: 命令结果
        """
        try:
            summary = self.state_manager.get_summary()

            return CommandResult(
                success=True,
                message="状态摘要获取成功",
                data=summary
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"获取状态摘要失败: {str(e)}",
                errors=[str(e)]
            )


_global_commands: Optional[GSDCommands] = None


def get_gsd_commands(workspace_path: Optional[str] = None) -> GSDCommands:
    """获取 GSD 命令接口"""
    global _global_commands
    if _global_commands is None:
        _global_commands = GSDCommands(workspace_path)
    return _global_commands


async def gsd_help() -> str:
    """
    显示 GSD 帮助信息

    Returns:
        str: 帮助文本
    """
    return """
# GSD (Get Shit Done) 命令

## 核心工作流

| 命令 | 作用 |
|------|------|
| /gsd-new-project | 完整初始化：提问 → 研究 → 需求 → 路线图 |
| /gsd-discuss-phase [N] | 在规划前收集实现决策 |
| /gsd-plan-phase [N] | 为某个阶段执行研究 + 规划 + 验证 |
| /gsd-execute-phase [N] | 以并行 wave 执行全部计划 |
| /gsd-verify-work [N] | 人工用户验收测试 |
| /gsd-ship [N] | 从已验证的阶段工作创建 PR |
| /gsd-complete-milestone | 归档里程碑并打 release tag |

## 快速命令

| 命令 | 作用 |
|------|------|
| /gsd-progress | 我现在在哪？下一步是什么？ |
| /gsd-quick [text] | 以 GSD 保障执行临时任务 |
| /gsd-add-phase [name] | 在路线图末尾追加 phase |
| /gsd-state | 查看项目状态摘要 |

## 上下文管理

| 命令 | 作用 |
|------|------|
| /gsd-context | 查看上下文使用状态 |
| /gsd-context-scope [scope] | 设置当前上下文范围 |
"""