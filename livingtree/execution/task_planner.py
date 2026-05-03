"""TaskPlanner — Intelligent task decomposition with chain-of-thought planning.

Decomposes complex goals into executable sub-tasks with dependencies,
resource estimates, and domain-aware splitting strategies.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field


class SubTask(BaseModel):
    """A single executable sub-task in a plan."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str
    description: str = ""
    action: str = "execute"
    agent_roles: list[str] = Field(default_factory=lambda: ["general"])
    dependencies: list[str] = Field(default_factory=list)
    estimated_duration: float = 60.0
    retry_count: int = 0
    max_retries: int = 3
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    result: Any = None
    needs_approval: bool = False
    approval_question: str = ""
    needs_deep_reasoning: bool = False

    def mark_completed(self, result: Any = None) -> None:
        self.status = "completed"
        self.result = result

    def mark_failed(self, error: str = "") -> None:
        self.status = "failed"
        self.result = {"error": error}

    def mark_running(self) -> None:
        self.status = "running"


class TaskSpec(BaseModel):
    """Full task specification with decomposed plan."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    goal: str
    domain: str = "general"
    sub_tasks: list[SubTask] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    total_estimated_duration: float = 0.0
    progress: float = 0.0
    status: str = "pending"

    def get_ready_tasks(self) -> list[SubTask]:
        """Get tasks whose dependencies are all completed."""
        completed = {t.id for t in self.sub_tasks if t.status == "completed"}
        return [
            t for t in self.sub_tasks
            if t.status == "pending"
            and all(dep in completed for dep in t.dependencies)
        ]

    def update_progress(self) -> None:
        total = len(self.sub_tasks)
        if total == 0:
            self.progress = 1.0
            return
        completed = sum(1 for t in self.sub_tasks if t.status == "completed")
        failed = sum(1 for t in self.sub_tasks if t.status == "failed")
        self.progress = (completed + failed) / total
        if self.progress >= 1.0:
            self.status = "completed" if failed == 0 else "partial"


class TaskPlanner:
    """Task planner with dynamic template learning.

    No hardcoded domain templates. Templates are learned from:
    1. KnowledgeBase (previously learned)
    2. Distillation (expert model)
    3. FormatDiscovery (document analysis)

    Usage:
        planner = TaskPlanner(kb=world.knowledge_base)
        steps = await planner.decompose_task(goal, domain="环评报告")
    """

    def __init__(self, max_depth: int = 10, kb: Any = None,
                 distillation: Any = None, expert_config: Any = None,
                 format_discovery: Any = None):
        self.max_depth = max_depth
        self.kb = kb
        self.distillation = distillation
        self.expert_config = expert_config
        self.format_discovery = format_discovery
        self._learner: Any = None

    async def decompose_task(self, goal: str, context: dict[str, Any] | None = None,
                             domain: str = "general", depth: int = 0) -> list[dict[str, Any]]:
        """Dynamically learn or retrieve a task template."""
        if self._learner is None:
            from ..knowledge.learning_engine import TemplateLearner
            self._learner = TemplateLearner(
                kb=self.kb, distillation=self.distillation, expert_config=self.expert_config,
            )

        return await self._learner.get_template(domain, goal)

    async def record_result(self, domain: str, success_rate: float) -> None:
        if self._learner:
            self._learner.record_success(domain, success_rate)

    async def estimate_complexity(self, goal: str) -> dict[str, Any]:
        return {"complexity": "medium", "estimated_steps": 5, "parallel_possible": True}
