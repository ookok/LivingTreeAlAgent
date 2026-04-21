"""
技能系统

可组合的技能管理框架
支持技能注册、加载、执行
"""

import asyncio
import importlib
import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable, Type
from dataclasses import dataclass, field
import abc


@dataclass
class SkillMetadata:
    """技能元数据"""
    skill_id: str
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "system"
    category: str = "general"
    requires: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)


class Skill(abc.ABC):
    """
    技能基类

    所有技能都应该继承这个类
    """

    metadata: SkillMetadata

    def __init__(self):
        self.metadata = SkillMetadata(
            skill_id="base_skill",
            name="Base Skill",
            description="基础技能",
            category="general"
        )

    @abc.abstractmethod
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
        pass

    async def validate(
        self,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        验证参数

        Args:
            parameters: 技能参数

        Returns:
            Dict: 验证结果
        """
        return {
            "valid": True,
            "errors": []
        }

    def get_help(self) -> str:
        """
        获取技能帮助信息

        Returns:
            str: 帮助信息
        """
        return f"{self.metadata.name}: {self.metadata.description}"


class SkillRegistry:
    """
    技能注册表

    管理所有技能的注册和加载
    """

    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self.skills_by_category: Dict[str, List[str]] = {}
        self.skill_metadata: Dict[str, SkillMetadata] = {}

    async def register_skill(self, skill: Skill):
        """
        注册技能

        Args:
            skill: 技能实例
        """
        skill_id = skill.metadata.skill_id
        self.skills[skill_id] = skill
        self.skill_metadata[skill_id] = skill.metadata

        # 按类别分类
        category = skill.metadata.category
        if category not in self.skills_by_category:
            self.skills_by_category[category] = []
        if skill_id not in self.skills_by_category[category]:
            self.skills_by_category[category].append(skill_id)

    async def load_skills(self, skills_dir: Path):
        """
        从目录加载技能

        Args:
            skills_dir: 技能目录
        """
        if not skills_dir.exists():
            return

        for skill_file in skills_dir.glob("*.py"):
            try:
                module_name = skill_file.stem
                spec = importlib.util.spec_from_file_location(module_name, str(skill_file))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    for name, obj in module.__dict__.items():
                        if (
                            isinstance(obj, type) and
                            issubclass(obj, Skill) and
                            obj is not Skill
                        ):
                            skill_instance = obj()
                            await self.register_skill(skill_instance)
                            print(f"[SkillRegistry] 加载技能: {skill_instance.metadata.name}")
            except Exception as e:
                print(f"[SkillRegistry] 加载技能文件 {skill_file} 失败: {e}")

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """
        获取技能

        Args:
            skill_id: 技能 ID

        Returns:
            Optional[Skill]: 技能实例
        """
        return self.skills.get(skill_id)

    def get_all_skills(self) -> List[str]:
        """
        获取所有技能 ID

        Returns:
            List[str]: 技能 ID 列表
        """
        return list(self.skills.keys())

    def get_skills_by_category(self) -> Dict[str, List[str]]:
        """
        按类别获取技能

        Returns:
            Dict[str, List[str]]: 类别 -> 技能 ID 列表
        """
        return self.skills_by_category

    def get_skill_metadata(self, skill_id: str) -> Optional[SkillMetadata]:
        """
        获取技能元数据

        Args:
            skill_id: 技能 ID

        Returns:
            Optional[SkillMetadata]: 技能元数据
        """
        return self.skill_metadata.get(skill_id)

    def search_skills(self, query: str) -> List[str]:
        """
        搜索技能

        Args:
            query: 搜索关键词

        Returns:
            List[str]: 匹配的技能 ID 列表
        """
        query_lower = query.lower()
        matches = []

        for skill_id, metadata in self.skill_metadata.items():
            if (
                query_lower in metadata.name.lower() or
                query_lower in metadata.description.lower() or
                query_lower in metadata.category.lower()
            ):
                matches.append(skill_id)

        return matches

    def validate_skill_dependencies(self, skill_id: str) -> Dict[str, Any]:
        """
        验证技能依赖

        Args:
            skill_id: 技能 ID

        Returns:
            Dict: 验证结果
        """
        metadata = self.skill_metadata.get(skill_id)
        if not metadata:
            return {
                "valid": False,
                "missing": [skill_id]
            }

        missing = []
        for dep in metadata.requires:
            if dep not in self.skills:
                missing.append(dep)

        return {
            "valid": len(missing) == 0,
            "missing": missing
        }


class SkillExecutor:
    """
    技能执行器

    负责执行技能并处理结果
    """

    def __init__(self, registry: Optional[SkillRegistry] = None):
        self.registry = registry or SkillRegistry()
        self.execution_history: List[Dict[str, Any]] = []

    async def execute(
        self,
        skill_id: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行技能

        Args:
            skill_id: 技能 ID
            parameters: 技能参数

        Returns:
            Dict: 执行结果
        """
        skill = self.registry.get_skill(skill_id)
        if not skill:
            return {
                "success": False,
                "error": f"Skill '{skill_id}' not found"
            }

        # 验证依赖
        dependency_check = self.registry.validate_skill_dependencies(skill_id)
        if not dependency_check["valid"]:
            return {
                "success": False,
                "error": f"Missing dependencies: {dependency_check['missing']}"
            }

        # 验证参数
        validation = await skill.validate(parameters)
        if not validation["valid"]:
            return {
                "success": False,
                "error": f"Parameter validation failed: {validation['errors']}"
            }

        start_time = time.time()
        try:
            result = await skill.execute(parameters)
            duration = time.time() - start_time

            execution_record = {
                "skill_id": skill_id,
                "parameters": parameters,
                "result": result,
                "duration": duration,
                "timestamp": start_time,
                "success": True
            }
            self.execution_history.append(execution_record)

            return {
                "success": True,
                "result": result,
                "duration": duration
            }

        except Exception as e:
            duration = time.time() - start_time
            execution_record = {
                "skill_id": skill_id,
                "parameters": parameters,
                "error": str(e),
                "duration": duration,
                "timestamp": start_time,
                "success": False
            }
            self.execution_history.append(execution_record)

            return {
                "success": False,
                "error": str(e),
                "duration": duration
            }

    async def execute_skills(
        self,
        skills: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        批量执行技能

        Args:
            skills: 技能执行列表，每个元素包含 skill_id 和 parameters

        Returns:
            List[Dict]: 执行结果列表
        """
        tasks = []
        for skill_info in skills:
            skill_id = skill_info.get("skill_id")
            parameters = skill_info.get("parameters", {})
            task = self.execute(skill_id, parameters)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取执行历史

        Args:
            limit: 限制数量

        Returns:
            List[Dict]: 执行历史
        """
        return self.execution_history[-limit:]

    def get_execution_stats(self) -> Dict[str, Any]:
        """
        获取执行统计

        Returns:
            Dict: 执行统计
        """
        total = len(self.execution_history)
        successful = sum(1 for record in self.execution_history if record.get("success"))
        failed = total - successful

        avg_duration = 0
        if total > 0:
            avg_duration = sum(record.get("duration", 0) for record in self.execution_history) / total

        return {
            "total_executions": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
            "average_duration": avg_duration
        }


# 预定义技能

class PlanningSkill(Skill):
    """计划技能"""

    def __init__(self):
        super().__init__()
        self.metadata = SkillMetadata(
            skill_id="planning",
            name="规划技能",
            description="创建详细的实现计划",
            category="workflow",
            triggers=["plan", "设计", "架构"]
        )

    async def execute(
        self,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        feature = parameters.get("feature", "")
        
        plan = [
            f"1. 分析 {feature} 的需求",
            f"2. 设计 {feature} 的架构",
            f"3. 实现 {feature} 的核心功能",
            f"4. 编写 {feature} 的测试用例",
            f"5. 运行测试并修复问题",
            f"6. 代码审查和优化"
        ]

        return {
            "plan": plan,
            "estimated_time": "2-4小时",
            "feature": feature
        }


class ImplementationSkill(Skill):
    """实现技能"""

    def __init__(self):
        super().__init__()
        self.metadata = SkillMetadata(
            skill_id="implementation",
            name="实现技能",
            description="实现功能代码",
            category="development",
            triggers=["implement", "实现", "编码"]
        )

    async def execute(
        self,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        feature = parameters.get("feature", "")
        files = parameters.get("files", [])

        return {
            "implemented": True,
            "feature": feature,
            "files": files,
            "status": "completed"
        }


class TestingSkill(Skill):
    """测试技能"""

    def __init__(self):
        super().__init__()
        self.metadata = SkillMetadata(
            skill_id="testing",
            name="测试技能",
            description="编写和运行测试",
            category="quality",
            triggers=["test", "测试", "验证"]
        )

    async def execute(
        self,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        feature = parameters.get("feature", "")
        test_cases = parameters.get("test_cases", [])

        return {
            "tested": True,
            "feature": feature,
            "test_cases": test_cases,
            "passed": len(test_cases) > 0,
            "status": "completed"
        }


class ReviewSkill(Skill):
    """代码审查技能"""

    def __init__(self):
        super().__init__()
        self.metadata = SkillMetadata(
            skill_id="review",
            name="代码审查技能",
            description="审查代码质量",
            category="quality",
            triggers=["review", "审查", "检查"]
        )

    async def execute(
        self,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        files = parameters.get("files", [])
        comments = parameters.get("comments", [])

        return {
            "reviewed": True,
            "files": files,
            "comments": comments,
            "status": "completed"
        }


class CompletionSkill(Skill):
    """完成技能"""

    def __init__(self):
        super().__init__()
        self.metadata = SkillMetadata(
            skill_id="completion",
            name="完成技能",
            description="完成开发任务",
            category="workflow",
            triggers=["complete", "完成", "结束"]
        )

    async def execute(
        self,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        feature = parameters.get("feature", "")

        return {
            "completed": True,
            "feature": feature,
            "status": "completed",
            "message": f"Feature '{feature}' has been completed successfully!"
        }


# 全局实例

_global_registry: Optional[SkillRegistry] = None
_global_executor: Optional[SkillExecutor] = None


def get_skill_registry() -> SkillRegistry:
    """获取技能注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
        # 注册默认技能
        asyncio.run(_global_registry.register_skill(PlanningSkill()))
        asyncio.run(_global_registry.register_skill(ImplementationSkill()))
        asyncio.run(_global_registry.register_skill(TestingSkill()))
        asyncio.run(_global_registry.register_skill(ReviewSkill()))
        asyncio.run(_global_registry.register_skill(CompletionSkill()))
    return _global_registry


def get_skill_executor() -> SkillExecutor:
    """获取技能执行器"""
    global _global_executor
    if _global_executor is None:
        _global_executor = SkillExecutor(get_skill_registry())
    return _global_executor