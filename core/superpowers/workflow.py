"""
工作流管理

管理完整的开发工作流：计划 → 实现 → 测试 → 审查 → 完成
"""

import asyncio
import time
import uuid
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from .models import WorkflowState, TaskStatus
from core.logger import get_logger
logger = get_logger('superpowers.workflow')



class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """任务"""
    task_id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    dependencies: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class Plan:
    """计划"""
    plan_id: str
    name: str
    tasks: List[Task] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class Workflow:
    """
    工作流

    管理完整的开发流程
    """
    workflow_id: str
    name: str
    description: str
    plans: List[Plan] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_plan_index: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    async def execute(self, parameters: Dict[str, Any]) -> WorkflowState:
        """
        执行工作流

        Args:
            parameters: 工作流参数

        Returns:
            WorkflowState: 工作流状态
        """
        self.status = WorkflowStatus.IN_PROGRESS
        self.updated_at = time.time()

        completed_tasks = []
        pending_tasks = []

        try:
            for i, plan in enumerate(self.plans):
                self.current_plan_index = i
                await self._execute_plan(plan, parameters)
                
                # 收集完成的任务
                for task in plan.tasks:
                    if task.status == TaskStatus.COMPLETED:
                        completed_tasks.append(task.task_id)
                    else:
                        pending_tasks.append(task.task_id)

            if pending_tasks:
                self.status = WorkflowStatus.FAILED
            else:
                self.status = WorkflowStatus.COMPLETED

        except Exception as e:
            self.status = WorkflowStatus.FAILED
            logger.info(f"[Workflow] 执行失败: {e}")

        self.updated_at = time.time()

        return WorkflowState(
            workflow_id=self.workflow_id,
            name=self.name,
            status=TaskStatus.COMPLETED if self.status == WorkflowStatus.COMPLETED else TaskStatus.FAILED,
            current_task=None,
            completed_tasks=completed_tasks,
            pending_tasks=pending_tasks
        )

    async def _execute_plan(self, plan: Plan, parameters: Dict[str, Any]):
        """
        执行计划

        Args:
            plan: 计划
            parameters: 参数
        """
        # 按依赖关系执行任务
        await self._execute_tasks_in_order(plan.tasks, parameters)

    async def _execute_tasks_in_order(self, tasks: List[Task], parameters: Dict[str, Any]):
        """
        按依赖顺序执行任务

        Args:
            tasks: 任务列表
            parameters: 参数
        """
        # 构建依赖图
        task_map = {task.task_id: task for task in tasks}
        dependencies = {task.task_id: task.dependencies for task in tasks}

        # 拓扑排序
        order = self._topological_sort(dependencies)

        for task_id in order:
            task = task_map.get(task_id)
            if task:
                await self._execute_task(task, parameters)

    def _topological_sort(self, dependencies: Dict[str, List[str]]) -> List[str]:
        """
        拓扑排序

        Args:
            dependencies: 依赖关系

        Returns:
            List[str]: 排序后的任务 ID 列表
        """
        visited = set()
        temp = set()
        result = []

        def visit(node):
            if node in temp:
                raise ValueError("循环依赖检测到")
            if node not in visited:
                temp.add(node)
                for dep in dependencies.get(node, []):
                    visit(dep)
                temp.remove(node)
                visited.add(node)
                result.append(node)

        for node in dependencies:
            if node not in visited:
                visit(node)

        return result

    async def _execute_task(self, task: Task, parameters: Dict[str, Any]):
        """
        执行任务

        Args:
            task: 任务
            parameters: 参数
        """
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = time.time()

        try:
            # 模拟任务执行
            await asyncio.sleep(0.5)
            task.result = {
                "success": True,
                "task": task.name,
                "parameters": parameters,
                "timestamp": time.time()
            }
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()

        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()


class WorkflowManager:
    """
    工作流管理器

    管理所有工作流
    """

    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}
        self.default_workflows = {
            "默认开发工作流": "标准的开发工作流：计划 → 实现 → 测试 → 审查 → 完成",
            "快速修复工作流": "快速修复bug的工作流：分析 → 修复 → 测试 → 验证",
            "新功能工作流": "新功能开发工作流：需求 → 设计 → 实现 → 测试 → 文档"
        }

    async def create_workflow(
        self,
        name: str,
        description: str
    ) -> Workflow:
        """
        创建工作流

        Args:
            name: 工作流名称
            description: 工作流描述

        Returns:
            Workflow: 工作流实例
        """
        workflow_id = str(uuid.uuid4())
        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            description=description
        )

        # 创建默认计划
        if name == "默认开发工作流":
            await self._create_default_workflow(workflow)
        elif name == "快速修复工作流":
            await self._create_quick_fix_workflow(workflow)
        elif name == "新功能工作流":
            await self._create_feature_workflow(workflow)

        self.workflows[workflow_id] = workflow
        return workflow

    async def _create_default_workflow(self, workflow: Workflow):
        """
        创建默认工作流

        Args:
            workflow: 工作流
        """
        # 计划 1: 规划
        plan1 = Plan(
            plan_id=str(uuid.uuid4()),
            name="规划阶段"
        )
        plan1.tasks = [
            Task(
                task_id=str(uuid.uuid4()),
                name="分析需求",
                description="分析功能需求和约束",
                priority=10
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="设计架构",
                description="设计系统架构和组件",
                priority=9
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="创建计划",
                description="创建详细的实现计划",
                priority=8
            )
        ]

        # 计划 2: 实现
        plan2 = Plan(
            plan_id=str(uuid.uuid4()),
            name="实现阶段"
        )
        plan2.tasks = [
            Task(
                task_id=str(uuid.uuid4()),
                name="实现核心功能",
                description="实现主要功能代码",
                priority=7
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="编写测试",
                description="编写单元测试和集成测试",
                priority=6
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="修复问题",
                description="修复测试中发现的问题",
                priority=5
            )
        ]

        # 计划 3: 审查和完成
        plan3 = Plan(
            plan_id=str(uuid.uuid4()),
            name="审查阶段"
        )
        plan3.tasks = [
            Task(
                task_id=str(uuid.uuid4()),
                name="代码审查",
                description="进行代码审查",
                priority=4
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="性能测试",
                description="进行性能测试和优化",
                priority=3
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="文档更新",
                description="更新项目文档",
                priority=2
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="完成交付",
                description="完成最终交付",
                priority=1
            )
        ]

        workflow.plans = [plan1, plan2, plan3]

    async def _create_quick_fix_workflow(self, workflow: Workflow):
        """
        创建快速修复工作流

        Args:
            workflow: 工作流
        """
        plan = Plan(
            plan_id=str(uuid.uuid4()),
            name="快速修复计划"
        )
        plan.tasks = [
            Task(
                task_id=str(uuid.uuid4()),
                name="分析问题",
                description="分析bug的根本原因",
                priority=10
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="实施修复",
                description="实施bug修复",
                priority=9
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="验证修复",
                description="验证修复是否成功",
                priority=8
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="更新测试",
                description="更新相关测试用例",
                priority=7
            )
        ]
        workflow.plans = [plan]

    async def _create_feature_workflow(self, workflow: Workflow):
        """
        创建新功能工作流

        Args:
            workflow: 工作流
        """
        plan = Plan(
            plan_id=str(uuid.uuid4()),
            name="新功能开发计划"
        )
        plan.tasks = [
            Task(
                task_id=str(uuid.uuid4()),
                name="需求分析",
                description="分析新功能需求",
                priority=10
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="设计方案",
                description="设计功能实现方案",
                priority=9
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="实现功能",
                description="实现新功能代码",
                priority=8
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="测试验证",
                description="测试新功能",
                priority=7
            ),
            Task(
                task_id=str(uuid.uuid4()),
                name="文档编写",
                description="编写功能文档",
                priority=6
            )
        ]
        workflow.plans = [plan]

    async def get_workflow(self, workflow_name: str) -> Optional[Workflow]:
        """
        获取工作流

        Args:
            workflow_name: 工作流名称

        Returns:
            Optional[Workflow]: 工作流实例
        """
        for workflow in self.workflows.values():
            if workflow.name == workflow_name:
                return workflow
        return None

    def get_workflows(self) -> List[Workflow]:
        """
        获取所有工作流

        Returns:
            List[Workflow]: 工作流列表
        """
        return list(self.workflows.values())

    async def update_workflow(
        self,
        workflow_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Workflow]:
        """
        更新工作流

        Args:
            workflow_id: 工作流 ID
            updates: 更新内容

        Returns:
            Optional[Workflow]: 更新后的工作流
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return None

        for key, value in updates.items():
            if hasattr(workflow, key):
                setattr(workflow, key, value)

        workflow.updated_at = time.time()
        return workflow

    def delete_workflow(self, workflow_id: str) -> bool:
        """
        删除工作流

        Args:
            workflow_id: 工作流 ID

        Returns:
            bool: 是否成功删除
        """
        if workflow_id in self.workflows:
            del self.workflows[workflow_id]
            return True
        return False

    def get_workflow_stats(self) -> Dict[str, Any]:
        """
        获取工作流统计

        Returns:
            Dict: 工作流统计
        """
        total = len(self.workflows)
        completed = sum(1 for w in self.workflows.values() if w.status == WorkflowStatus.COMPLETED)
        in_progress = sum(1 for w in self.workflows.values() if w.status == WorkflowStatus.IN_PROGRESS)

        return {
            "total_workflows": total,
            "completed_workflows": completed,
            "in_progress_workflows": in_progress,
            "pending_workflows": total - completed - in_progress
        }


# 全局实例

_global_workflow_manager: Optional[WorkflowManager] = None


def get_workflow_manager() -> WorkflowManager:
    """获取工作流管理器"""
    global _global_workflow_manager
    if _global_workflow_manager is None:
        _global_workflow_manager = WorkflowManager()
    return _global_workflow_manager