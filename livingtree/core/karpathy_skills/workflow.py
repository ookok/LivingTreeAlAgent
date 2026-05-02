"""
Karpathy 工作流

实现 Karpathy 编程最佳实践的工作流
"""

import asyncio
import time
import uuid
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field

from .models import KarpathyTask
from .skill_configs import get_karpathy_registry


class KarpathyWorkflowSystem:
    """
    Karpathy 工作流系统

    管理 Karpathy 工作流
    """

    def __init__(self):
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.registry = get_karpathy_registry()
        self._setup_default_workflows()

    def _setup_default_workflows(self):
        """
        设置默认工作流
        """
        self.workflows = {
            "code_quality": {
                "name": "代码质量工作流",
                "description": "代码质量检查：审查 → 测试 → 重构 → 文档",
                "tasks": [
                    {
                        "skill_id": "code_review",
                        "name": "代码审查",
                        "description": "深度代码审查"
                    },
                    {
                        "skill_id": "test_generator",
                        "name": "生成测试",
                        "description": "生成测试用例"
                    },
                    {
                        "skill_id": "refactor_advisor",
                        "name": "重构建议",
                        "description": "获取重构建议"
                    },
                    {
                        "skill_id": "doc_writer",
                        "name": "生成文档",
                        "description": "生成代码文档"
                    }
                ]
            },
            "performance_optimization": {
                "name": "性能优化工作流",
                "description": "性能优化：分析 → 优化 → 测试",
                "tasks": [
                    {
                        "skill_id": "code_review",
                        "name": "性能分析",
                        "description": "分析性能问题"
                    },
                    {
                        "skill_id": "performance_optimizer",
                        "name": "性能优化",
                        "description": "优化代码性能"
                    },
                    {
                        "skill_id": "test_generator",
                        "name": "性能测试",
                        "description": "生成性能测试"
                    }
                ]
            },
            "codebase_analysis": {
                "name": "代码库分析工作流",
                "description": "代码库全面分析",
                "tasks": [
                    {
                        "skill_id": "code_review",
                        "name": "代码审查",
                        "description": "代码库审查"
                    },
                    {
                        "skill_id": "refactor_advisor",
                        "name": "重构建议",
                        "description": "代码库重构建议"
                    },
                    {
                        "skill_id": "performance_optimizer",
                        "name": "性能分析",
                        "description": "代码库性能分析"
                    },
                    {
                        "skill_id": "doc_writer",
                        "name": "文档生成",
                        "description": "代码库文档生成"
                    }
                ]
            }
        }

    async def initialize(self):
        """
        初始化工作流系统
        """
        print("[KarpathyWorkflow] 初始化工作流系统")

    async def run(
        self,
        workflow_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        运行工作流

        Args:
            workflow_name: 工作流名称
            parameters: 工作流参数

        Returns:
            Dict: 工作流执行结果
        """
        workflow = self.workflows.get(workflow_name)
        if not workflow:
            return {
                "success": False,
                "error": f"Workflow '{workflow_name}' not found"
            }

        results = []
        start_time = time.time()

        try:
            for task_info in workflow["tasks"]:
                task = KarpathyTask(
                    task_id=str(uuid.uuid4()),
                    name=task_info["name"],
                    description=task_info["description"],
                    skill_id=task_info["skill_id"],
                    parameters=parameters
                )

                # 执行任务
                result = await self._execute_task(task)
                results.append({
                    "task": task.name,
                    "skill": task.skill_id,
                    "result": result
                })

            duration = time.time() - start_time
            return {
                "success": True,
                "workflow": workflow_name,
                "results": results,
                "duration": duration,
                "timestamp": start_time
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _execute_task(self, task: KarpathyTask) -> Dict[str, Any]:
        """
        执行任务

        Args:
            task: 任务

        Returns:
            Dict: 执行结果
        """
        task.status = "in_progress"
        task.created_at = time.time()

        try:
            result = await self.registry.execute_skill(
                task.skill_id,
                task.parameters
            )
            task.status = "completed"
            task.result = result
            task.completed_at = time.time()
            return result

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = time.time()
            return {
                "success": False,
                "error": str(e)
            }

    def get_workflows(self) -> List[str]:
        """
        获取所有工作流

        Returns:
            List[str]: 工作流名称列表
        """
        return list(self.workflows.keys())

    def get_workflow_info(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """
        获取工作流信息

        Args:
            workflow_name: 工作流名称

        Returns:
            Optional[Dict[str, Any]]: 工作流信息
        """
        return self.workflows.get(workflow_name)

    def create_workflow(
        self,
        name: str,
        description: str,
        tasks: List[Dict[str, Any]]
    ) -> str:
        """
        创建工作流

        Args:
            name: 工作流名称
            description: 工作流描述
            tasks: 任务列表

        Returns:
            str: 工作流 ID
        """
        workflow_id = str(uuid.uuid4())
        self.workflows[workflow_id] = {
            "name": name,
            "description": description,
            "tasks": tasks
        }
        return workflow_id

    def update_workflow(
        self,
        workflow_name: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        更新工作流

        Args:
            workflow_name: 工作流名称
            updates: 更新内容

        Returns:
            bool: 是否成功更新
        """
        workflow = self.workflows.get(workflow_name)
        if not workflow:
            return False

        workflow.update(updates)
        return True

    def delete_workflow(self, workflow_name: str) -> bool:
        """
        删除工作流

        Args:
            workflow_name: 工作流名称

        Returns:
            bool: 是否成功删除
        """
        if workflow_name in self.workflows:
            del self.workflows[workflow_name]
            return True
        return False


# 全局实例

_global_workflow: Optional[KarpathyWorkflowSystem] = None


def get_karpathy_workflow() -> KarpathyWorkflowSystem:
    """获取 Karpathy 工作流系统"""
    global _global_workflow
    if _global_workflow is None:
        _global_workflow = KarpathyWorkflowSystem()
    return _global_workflow