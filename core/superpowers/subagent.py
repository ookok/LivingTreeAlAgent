"""
子代理调度框架

管理子代理的创建、调度和并行执行
"""

import asyncio
import time
import uuid
from typing import List, Dict, Optional, Any, Callable, AsyncGenerator
from dataclasses import dataclass, field
import concurrent.futures

from .models import AgentConfig


@dataclass
class SubAgent:
    """子代理"""
    agent_id: str
    name: str
    config: AgentConfig
    status: str = "idle"
    task_count: int = 0
    last_activity: float = field(default_factory=time.time)


@dataclass
class DispatchTask:
    """调度任务"""
    task_id: str
    task: str
    context: Dict[str, Any]
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SubAgentManager:
    """
    子代理管理器

    负责创建和管理子代理
    """

    def __init__(self):
        self.agents: Dict[str, SubAgent] = {}
        self.agent_pool: List[SubAgent] = []
        self.max_agents: int = 5

    async def create_agent(self, config: AgentConfig) -> SubAgent:
        """
        创建子代理

        Args:
            config: 代理配置

        Returns:
            SubAgent: 子代理实例
        """
        if len(self.agents) >= self.max_agents:
            raise RuntimeError(f"达到最大代理数量: {self.max_agents}")

        agent = SubAgent(
            agent_id=config.agent_id,
            name=config.name,
            config=config
        )

        self.agents[agent.agent_id] = agent
        self.agent_pool.append(agent)

        return agent

    def get_agent(self, agent_id: str) -> Optional[SubAgent]:
        """
        获取子代理

        Args:
            agent_id: 代理 ID

        Returns:
            Optional[SubAgent]: 子代理实例
        """
        return self.agents.get(agent_id)

    def get_agents(self) -> List[SubAgent]:
        """
        获取所有子代理

        Returns:
            List[SubAgent]: 子代理列表
        """
        return list(self.agents.values())

    def get_active_agents(self) -> List[SubAgent]:
        """
        获取活跃的子代理

        Returns:
            List[SubAgent]: 活跃子代理列表
        """
        return [agent for agent in self.agents.values() if agent.status == "busy"]

    def get_idle_agents(self) -> List[SubAgent]:
        """
        获取空闲的子代理

        Returns:
            List[SubAgent]: 空闲子代理列表
        """
        return [agent for agent in self.agents.values() if agent.status == "idle"]

    def get_active_count(self) -> int:
        """
        获取活跃代理数量

        Returns:
            int: 活跃代理数量
        """
        return len(self.get_active_agents())

    def get_idle_count(self) -> int:
        """
        获取空闲代理数量

        Returns:
            int: 空闲代理数量
        """
        return len(self.get_idle_agents())

    def update_agent_status(self, agent_id: str, status: str):
        """
        更新代理状态

        Args:
            agent_id: 代理 ID
            status: 新状态
        """
        agent = self.agents.get(agent_id)
        if agent:
            agent.status = status
            agent.last_activity = time.time()

    def update_agent_task_count(self, agent_id: str):
        """
        更新代理任务计数

        Args:
            agent_id: 代理 ID
        """
        agent = self.agents.get(agent_id)
        if agent:
            agent.task_count += 1

    def shutdown(self):
        """
        关闭所有代理
        """
        self.agents.clear()
        self.agent_pool.clear()


class ParallelDispatcher:
    """
    并行调度器

    负责并行调度任务到子代理
    """

    def __init__(self, manager: Optional[SubAgentManager] = None):
        self.manager = manager or SubAgentManager()
        self.tasks: Dict[str, DispatchTask] = {}
        self.pending_tasks: List[DispatchTask] = []
        self.running_tasks: Dict[str, DispatchTask] = {}
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

    async def dispatch(
        self,
        task: str,
        context: Dict[str, Any],
        priority: int = 0,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        调度任务

        Args:
            task: 任务描述
            context: 上下文
            priority: 优先级
            timeout: 超时时间（秒）

        Returns:
            Dict: 执行结果
        """
        task_id = str(uuid.uuid4())
        dispatch_task = DispatchTask(
            task_id=task_id,
            task=task,
            context=context,
            priority=priority
        )

        self.tasks[task_id] = dispatch_task
        self.pending_tasks.append(dispatch_task)

        # 排序待处理任务
        self.pending_tasks.sort(key=lambda t: t.priority, reverse=True)

        result = await self._execute_task(dispatch_task, timeout)
        return result

    async def dispatch_batch(
        self,
        tasks: List[Dict[str, Any]],
        timeout: int = 300
    ) -> List[Dict[str, Any]]:
        """
        批量调度任务

        Args:
            tasks: 任务列表，每个元素包含 task、context、priority
            timeout: 超时时间

        Returns:
            List[Dict]: 执行结果列表
        """
        coros = []
        for task_info in tasks:
            task = task_info.get("task")
            context = task_info.get("context", {})
            priority = task_info.get("priority", 0)
            coro = self.dispatch(task, context, priority, timeout)
            coros.append(coro)

        results = await asyncio.gather(*coros, return_exceptions=True)
        return results

    async def _execute_task(
        self,
        task: DispatchTask,
        timeout: int
    ) -> Dict[str, Any]:
        """
        执行任务

        Args:
            task: 调度任务
            timeout: 超时时间

        Returns:
            Dict: 执行结果
        """
        # 找到空闲代理
        idle_agents = self.manager.get_idle_agents()
        if not idle_agents:
            # 等待空闲代理
            await self._wait_for_idle_agent()
            idle_agents = self.manager.get_idle_agents()

        if not idle_agents:
            return {
                "success": False,
                "error": "No idle agents available"
            }

        agent = idle_agents[0]
        self.manager.update_agent_status(agent.agent_id, "busy")
        task.started_at = time.time()
        self.running_tasks[task.task_id] = task

        try:
            # 模拟任务执行
            result = await self._simulate_task_execution(agent, task, timeout)
            task.result = result
            task.completed_at = time.time()
            self.manager.update_agent_status(agent.agent_id, "idle")
            self.manager.update_agent_task_count(agent.agent_id)

            # 从运行任务中移除
            self.running_tasks.pop(task.task_id, None)
            self.pending_tasks = [t for t in self.pending_tasks if t.task_id != task.task_id]

            return result

        except Exception as e:
            task.error = str(e)
            task.completed_at = time.time()
            self.manager.update_agent_status(agent.agent_id, "idle")

            # 从运行任务中移除
            self.running_tasks.pop(task.task_id, None)
            self.pending_tasks = [t for t in self.pending_tasks if t.task_id != task.task_id]

            return {
                "success": False,
                "error": str(e)
            }

    async def _simulate_task_execution(
        self,
        agent: SubAgent,
        task: DispatchTask,
        timeout: int
    ) -> Dict[str, Any]:
        """
        模拟任务执行

        Args:
            agent: 代理
            task: 任务
            timeout: 超时时间

        Returns:
            Dict: 执行结果
        """
        # 模拟执行时间
        execution_time = min(3, max(0.5, len(task.task) / 100))
        await asyncio.sleep(execution_time)

        # 生成模拟结果
        return {
            "success": True,
            "agent": agent.name,
            "task": task.task,
            "context": task.context,
            "result": f"Task '{task.task}' completed by {agent.name}",
            "execution_time": execution_time,
            "timestamp": time.time()
        }

    async def _wait_for_idle_agent(self, timeout: int = 30):
        """
        等待空闲代理

        Args:
            timeout: 超时时间
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.manager.get_idle_count() > 0:
                return
            await asyncio.sleep(0.5)
        raise TimeoutError("No idle agents available within timeout")

    def get_pending_tasks(self) -> List[DispatchTask]:
        """
        获取待处理任务

        Returns:
            List[DispatchTask]: 待处理任务列表
        """
        return self.pending_tasks

    def get_running_tasks(self) -> Dict[str, DispatchTask]:
        """
        获取运行中任务

        Returns:
            Dict[str, DispatchTask]: 运行中任务
        """
        return self.running_tasks

    def get_task_status(self, task_id: str) -> Optional[DispatchTask]:
        """
        获取任务状态

        Args:
            task_id: 任务 ID

        Returns:
            Optional[DispatchTask]: 任务状态
        """
        return self.tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务 ID

        Returns:
            bool: 是否成功取消
        """
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.task_id in self.running_tasks:
            # 从运行任务中移除
            self.running_tasks.pop(task.task_id, None)
        elif task in self.pending_tasks:
            # 从待处理任务中移除
            self.pending_tasks.remove(task)

        self.tasks.pop(task_id, None)
        return True

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            Dict: 统计信息
        """
        return {
            "total_tasks": len(self.tasks),
            "pending_tasks": len(self.pending_tasks),
            "running_tasks": len(self.running_tasks),
            "active_agents": self.manager.get_active_count(),
            "idle_agents": self.manager.get_idle_count(),
            "total_agents": len(self.manager.get_agents())
        }

    def shutdown(self):
        """
        关闭调度器
        """
        self.executor.shutdown()
        self.tasks.clear()
        self.pending_tasks.clear()
        self.running_tasks.clear()


# 全局实例

_global_manager: Optional[SubAgentManager] = None
_global_dispatcher: Optional[ParallelDispatcher] = None


def get_subagent_manager() -> SubAgentManager:
    """获取子代理管理器"""
    global _global_manager
    if _global_manager is None:
        _global_manager = SubAgentManager()
    return _global_manager


def get_parallel_dispatcher() -> ParallelDispatcher:
    """获取并行调度器"""
    global _global_dispatcher
    if _global_dispatcher is None:
        _global_dispatcher = ParallelDispatcher(get_subagent_manager())
    return _global_dispatcher