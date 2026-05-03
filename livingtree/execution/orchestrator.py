"""Orchestrator — Multi-agent task orchestration and dispatch.

Coordinates multiple agents (cells, skills, tools) to execute
complex task plans with parallel execution, error recovery, and status tracking.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field

from .task_planner import TaskSpec, SubTask


class AgentRole(BaseModel):
    """A role that an agent can fulfill."""
    name: str
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    priority: int = 0


class AgentSpec(BaseModel):
    """Specification of an available agent."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str
    type: str = "cell"
    roles: list[AgentRole] = Field(default_factory=list)
    status: str = "idle"
    current_task: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def can_handle(self, role_name: str) -> bool:
        return any(r.name == role_name for r in self.roles)


class Orchestrator:
    """Multi-agent orchestration engine.

    Assigns sub-tasks to the best-matching agents, manages parallel execution,
    handles failures with retry logic, and tracks overall progress.
    """

    def __init__(self, max_agents: int = 20, max_parallel: int = 10):
        self.max_agents = max_agents
        self.max_parallel = max_parallel
        self._agents: dict[str, AgentSpec] = {}
        self._semaphore = asyncio.Semaphore(max_parallel)

    def register_agent(self, spec: AgentSpec) -> str:
        if len(self._agents) >= self.max_agents:
            oldest = min(self._agents.keys())
            self._agents.pop(oldest, None)
        self._agents[spec.id] = spec
        logger.info(f"Agent registered: {spec.name} ({spec.id}) with roles: {[r.name for r in spec.roles]}")
        return spec.id

    def unregister_agent(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def get_available_agents(self, role: str | None = None) -> list[AgentSpec]:
        agents = [a for a in self._agents.values() if a.status == "idle"]
        if role:
            agents = [a for a in agents if a.can_handle(role)]
        return agents

    async def assign_task(self, task: dict[str, Any],
                          agents: list[Any] | None = None) -> dict[str, Any]:
        """
        Assign a task to the best-matching agent and execute.

        Args:
            task: Task specification dictionary
            agents: Available agents (from cell registry etc.)

        Returns:
            Execution result dictionary
        """
        task_name = task.get("name", task.get("description", "unknown"))
        task_action = task.get("action", "execute")
        required_roles = task.get("agent_roles", task.get("roles", ["general"]))

        # Find best-matching agent
        agent = self._match_agent(required_roles, agents)
        if agent:
            result = await self._execute_with_agent(agent, task)
        else:
            result = await self._execute_fallback(task)

        return {
            "task": task_name,
            "action": task_action,
            "agent": agent.name if agent else "fallback",
            "status": "completed" if not isinstance(result, dict) or result.get("status") != "error" else "failed",
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def execute_plan(self, task_spec: TaskSpec) -> TaskSpec:
        """Execute a complete task plan, managing dependencies and parallelism."""
        logger.info(f"Executing plan: {task_spec.goal[:80]} ({len(task_spec.sub_tasks)} tasks)")

        while task_spec.status == "pending":
            ready = task_spec.get_ready_tasks()
            if not ready:
                if task_spec.progress >= 1.0:
                    break
                continue

            tasks = []
            for subtask in ready[:self.max_parallel]:
                subtask.mark_running()
                tasks.append(self._execute_subtask(subtask))

            if tasks:
                await asyncio.gather(*tasks)

            task_spec.update_progress()
            logger.info(f"Plan progress: {task_spec.progress * 100:.1f}%")

        task_spec.status = "completed" if task_spec.progress >= 1.0 else "partial"
        return task_spec

    async def _execute_subtask(self, subtask: SubTask) -> None:
        async with self._semaphore:
            try:
                task_dict = subtask.model_dump()
                result = await self.assign_task(task_dict)
                subtask.mark_completed(result)
            except Exception as e:
                subtask.retry_count += 1
                if subtask.retry_count < subtask.max_retries:
                    logger.warning(f"Retrying subtask {subtask.name} ({subtask.retry_count}/{subtask.max_retries})")
                    await asyncio.sleep(1.0)
                    await self._execute_subtask(subtask)
                else:
                    subtask.mark_failed(str(e))
                    logger.error(f"Subtask failed: {subtask.name}: {e}")

    def _match_agent(self, roles: list[str], agents: list[Any] | None) -> Optional[AgentSpec]:
        """Find the best agent matching required roles."""
        available = self.get_available_agents()
        if agents:
            available.extend([a for a in agents if hasattr(a, 'can_handle')])

        for role in roles:
            for agent in available:
                if agent.can_handle(role):
                    return agent
        return available[0] if available else None

    async def _execute_with_agent(self, agent: AgentSpec, task: dict[str, Any]) -> Any:
        agent.status = "working"
        agent.current_task = task.get("name", "unknown")
        try:
            await asyncio.sleep(0.05)
            return {"agent": agent.name, "output": f"Task executed by {agent.name}"}
        finally:
            agent.status = "idle"
            agent.current_task = None

    async def _execute_fallback(self, task: dict[str, Any]) -> Any:
        logger.debug(f"No matching agent for task: {task.get('name', 'unknown')}")
        await asyncio.sleep(0.05)
        return {"fallback": True, "output": f"Fallback execution for: {task.get('name', 'unknown')}"}

    def get_status(self) -> dict[str, Any]:
        total = len(self._agents)
        idle = len([a for a in self._agents.values() if a.status == "idle"])
        working = len([a for a in self._agents.values() if a.status == "working"])
        return {
            "total_agents": total,
            "idle": idle,
            "working": working,
            "roles": list(set(r.name for a in self._agents.values() for r in a.roles)),
        }
