"""
规划模块

实现 GSD 的多代理编排：
- Planner: 规划代理
- ResearchAgent: 研究代理
- Executor: 执行代理
- Verifier: 验证代理
- WaveExecutor: Wave 执行器
"""

import asyncio
import time
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json

from .gsd_engine import GSDPlan, GSDTask, TaskStatus, create_gsd_task, create_gsd_plan


class AgentType(Enum):
    """代理类型"""
    PLANNER = "planner"
    RESEARCHER = "researcher"
    EXECUTOR = "executor"
    VERIFIER = "verifier"


@dataclass
class AgentResult:
    """代理结果"""
    agent_type: AgentType
    success: bool
    output: Any
    error: Optional[str] = None
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResearchAgent:
    """
    研究代理

    并行调研技术栈、功能、架构和坑点
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    async def research(
        self,
        phase_context: str,
        goals: List[str],
        constraints: List[str]
    ) -> Dict[str, Any]:
        """
        执行研究

        Args:
            phase_context: 阶段上下文
            goals: 目标列表
            constraints: 约束列表

        Returns:
            Dict: 研究结果
        """
        start_time = time.time()

        tech_stack = await self._research_tech_stack(goals, constraints)
        architecture = await self._research_architecture(goals)
        patterns = await self._research_patterns(goals)
        pitfalls = await self._research_pitfalls(goals, constraints)

        duration = (time.time() - start_time) * 1000

        return {
            "tech_stack": tech_stack,
            "architecture": architecture,
            "patterns": patterns,
            "pitfalls": pitfalls,
            "duration_ms": duration
        }

    async def _research_tech_stack(
        self,
        goals: List[str],
        constraints: List[str]
    ) -> Dict[str, Any]:
        """研究技术栈"""
        await asyncio.sleep(0.01)

        tech_map = {
            "web": ["React", "Vue", "Angular"],
            "api": ["FastAPI", "Express", "Django"],
            "database": ["PostgreSQL", "MongoDB", "Redis"],
            "ai": ["LangChain", "OpenAI", "Hugging Face"],
            "vector": ["FAISS", "Milvus", "Pinecone"],
        }

        relevant = {}
        goals_str = " ".join(goals).lower()

        for key, technologies in tech_map.items():
            if key in goals_str or any(t.lower() in goals_str for t in technologies):
                relevant[key] = technologies[:2]

        if not relevant:
            relevant = {"default": ["Python", "FastAPI", "PostgreSQL"]}

        return {
            "recommended": relevant,
            "alternatives": {},
            "rationale": "Based on project goals"
        }

    async def _research_architecture(
        self,
        goals: List[str]
    ) -> Dict[str, Any]:
        """研究架构"""
        await asyncio.sleep(0.01)

        return {
            "pattern": "modular",
            "components": [
                {"name": "core", " responsibility": "核心业务逻辑"},
                {"name": "agents", "responsibility": "AI 代理"},
                {"name": "memory", "responsibility": "记忆系统"},
                {"name": "tools", "responsibility": "工具集"}
            ],
            "data_flow": "async",
            "state_management": "distributed"
        }

    async def _research_patterns(
        self,
        goals: List[str]
    ) -> List[str]:
        """研究设计模式"""
        await asyncio.sleep(0.01)

        patterns = [
            "模块化设计",
            "异步编程模式",
            "事件驱动架构",
            "策略模式用于工具选择",
            "观察者模式用于状态更新"
        ]

        return patterns

    async def _research_pitfalls(
        self,
        goals: List[str],
        constraints: List[str]
    ) -> List[str]:
        """研究潜在坑点"""
        await asyncio.sleep(0.01)

        pitfalls = [
            "上下文窗口限制需要注意压缩策略",
            "向量嵌入维度选择影响检索质量",
            "异步任务编排需要处理好异常",
            "多模态数据格式转换可能丢失信息"
        ]

        return pitfalls


class Planner:
    """
    规划代理

    生成原子化任务计划并验证
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    async def create_plan(
        self,
        phase: int,
        name: str,
        context: str,
        requirements: List[str]
    ) -> GSDPlan:
        """
        创建计划

        Args:
            phase: 阶段号
            name: 计划名称
            context: 上下文
            requirements: 需求列表

        Returns:
            GSDPlan: 创建的计划
        """
        tasks = []

        for i, req in enumerate(requirements):
            task = create_gsd_task(
                name=f"实现 {req}",
                files=[self._infer_files(req)],
                action=f"根据上下文实现 {req}",
                verify=f"验证 {req} 是否正确实现",
                done=f"{req} 已完成并通过验证"
            )
            tasks.append(task)

        plan = create_gsd_plan(
            phase=phase,
            name=name,
            tasks=tasks
        )

        return plan

    async def validate_plan(
        self,
        plan: GSDPlan,
        requirements: List[str]
    ) -> Dict[str, Any]:
        """
        验证计划

        Args:
            plan: 计划
            requirements: 需求

        Returns:
            Dict: 验证结果
        """
        covered = set()
        missing = []

        for task in plan.tasks:
            for req in requirements:
                if any(keyword in task.name for keyword in req.split()):
                    covered.add(req)

        for req in requirements:
            if req not in covered:
                missing.append(req)

        return {
            "valid": len(missing) == 0,
            "coverage": len(covered) / len(requirements) if requirements else 1.0,
            "missing": missing,
            "task_count": len(plan.tasks)
        }

    def _infer_files(self, requirement: str) -> str:
        """推断文件路径"""
        req_lower = requirement.lower()

        if "api" in req_lower or "endpoint" in req_lower:
            return "core/api.py"
        elif "model" in req_lower or "数据" in req_lower:
            return "core/models.py"
        elif "ui" in req_lower or "界面" in req_lower:
            return "ui/components.py"
        elif "memory" in req_lower or "记忆" in req_lower:
            return "core/memory.py"
        elif "agent" in req_lower or "代理" in req_lower:
            return "core/agent.py"
        else:
            return "core/module.py"


class Executor:
    """
    执行代理

    负责执行单个任务
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._hooks: Dict[str, List[Callable]] = {
            "before_execute": [],
            "after_execute": [],
            "on_error": []
        }

    async def execute(
        self,
        task: GSDTask,
        context: Optional[str] = None
    ) -> AgentResult:
        """
        执行任务

        Args:
            task: 任务
            context: 上下文

        Returns:
            AgentResult: 执行结果
        """
        start_time = time.time()

        self._emit("before_execute", task)

        try:
            result = await self._do_execute(task, context)
            task.status = TaskStatus.COMPLETED
            task.result = str(result)

            self._emit("after_execute", task, result)

            duration = (time.time() - start_time) * 1000

            return AgentResult(
                agent_type=AgentType.EXECUTOR,
                success=True,
                output=result,
                duration_ms=duration
            )

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)

            self._emit("on_error", task, e)

            duration = (time.time() - start_time) * 1000

            return AgentResult(
                agent_type=AgentType.EXECUTOR,
                success=False,
                output=None,
                error=str(e),
                duration_ms=duration
            )

    async def _do_execute(
        self,
        task: GSDTask,
        context: Optional[str]
    ) -> Any:
        """执行任务（实际逻辑）"""
        await asyncio.sleep(0.05)

        return {
            "task_id": task.task_id,
            "name": task.name,
            "files": task.files,
            "action": task.action,
            "timestamp": time.time()
        }

    def on(self, event: str, handler: Callable):
        """注册钩子"""
        if event in self._hooks:
            self._hooks[event].append(handler)

    def _emit(self, event: str, *args):
        """触发钩子"""
        for handler in self._hooks.get(event, []):
            try:
                handler(*args)
            except Exception as e:
                print(f"[Executor] Hook error: {e}")


class WaveExecutor:
    """
    Wave 执行器

    按依赖关系分组并行执行任务
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.executor = Executor(config)

    async def execute_plan(
        self,
        plan: GSDPlan,
        context: Optional[str] = None,
        parallel: bool = True
    ) -> Dict[str, AgentResult]:
        """
        执行计划

        Args:
            plan: 计划
            context: 上下文
            parallel: 是否并行执行

        Returns:
            Dict: 任务 ID -> 结果
        """
        results = {}
        waves = self._group_by_waves(plan.tasks)

        for wave_num in sorted(waves.keys()):
            tasks_in_wave = waves[wave_num]

            if parallel and len(tasks_in_wave) > 1:
                tasks_coros = [
                    self.executor.execute(task, context)
                    for task in tasks_in_wave
                ]
                wave_results = await asyncio.gather(*tasks_coros)

                for task, result in zip(tasks_in_wave, wave_results):
                    results[task.task_id] = result
            else:
                for task in tasks_in_wave:
                    result = await self.executor.execute(task, context)
                    results[task.task_id] = result

        return results

    def _group_by_waves(
        self,
        tasks: List[GSDTask]
    ) -> Dict[int, List[GSDTask]]:
        """按 wave 分组"""
        waves: Dict[int, List[GSDTask]] = {}

        for task in tasks:
            wave = task.wave
            if wave not in waves:
                waves[wave] = []
            waves[wave].append(task)

        return dict(sorted(waves.items()))


class Verifier:
    """
    验证代理

    验证任务是否按要求完成
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    async def verify(
        self,
        plan: GSDPlan,
        verification_criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        验证计划

        Args:
            plan: 计划
            verification_criteria: 验证标准

        Returns:
            Dict: 验证结果
        """
        passed = []
        failed = []
        fixes = []

        for task in plan.tasks:
            if task.status == TaskStatus.COMPLETED:
                passed.append({
                    "task_id": task.task_id,
                    "name": task.name,
                    "done": task.done
                })
            else:
                failed.append({
                    "task_id": task.task_id,
                    "name": task.name,
                    "error": task.error or "未完成"
                })
                fixes.append(f"修复 {task.name}")

        all_passed = len(failed) == 0

        return {
            "passed": all_passed,
            "passed_count": len(passed),
            "failed_count": len(failed),
            "passed_items": passed,
            "failed_items": failed,
            "suggested_fixes": fixes
        }

    async def verify_single(
        self,
        task: GSDTask
    ) -> bool:
        """
        验证单个任务

        Args:
            task: 任务

        Returns:
            bool: 是否通过
        """
        return task.status == TaskStatus.COMPLETED


class Orchestrator:
    """
    编排器

    协调多个代理完成任务
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.researcher = ResearchAgent(config)
        self.planner = Planner(config)
        self.executor = WaveExecutor(config)
        self.verifier = Verifier(config)

    async def run_phase(
        self,
        phase: int,
        context: str,
        goals: List[str],
        requirements: List[str],
        constraints: List[str]
    ) -> Dict[str, Any]:
        """
        运行完整阶段

        Args:
            phase: 阶段号
            context: 上下文
            goals: 目标
            requirements: 需求
            constraints: 约束

        Returns:
            Dict: 阶段结果
        """
        research_result = await self.researcher.research(context, goals, constraints)

        plan = await self.planner.create_plan(
            phase=phase,
            name=f"Phase {phase} Implementation",
            context=context,
            requirements=requirements
        )

        validation = await self.planner.validate_plan(plan, requirements)

        execution_results = await self.executor.execute_plan(plan, context)

        verification = await self.verifier.verify(plan, {})

        return {
            "phase": phase,
            "research": research_result,
            "plan": plan,
            "validation": validation,
            "execution": execution_results,
            "verification": verification
        }


_global_planner: Optional[Planner] = None
_global_orchestrator: Optional[Orchestrator] = None


def get_planner() -> Planner:
    """获取规划代理"""
    global _global_planner
    if _global_planner is None:
        _global_planner = Planner()
    return _global_planner


def get_orchestrator() -> Orchestrator:
    """获取编排器"""
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = Orchestrator()
    return _global_orchestrator