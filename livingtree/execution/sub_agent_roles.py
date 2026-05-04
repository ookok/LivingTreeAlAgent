"""Sub-Agent Roles — Implementer + Verifier role-based agent decomposition.

Inspired by DeepSeek-TUI's sub-agent roles. Extends the Orchestrator with
fixed Implementer/Verifier role pairs. After an Implementer agent produces
output, a Verifier agent validates it. This creates a built-in quality
gate for every code generation and modification task.

Usage:
    roles = SubAgentRoles(consciousness)
    task = await roles.run_implement_verify(
        spec="Implement a caching layer for the database",
        max_iterations=3,
    )
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class RoleDefinition:
    name: str
    description: str
    system_prompt: str
    capabilities: list[str] = field(default_factory=list)

@dataclass
class RoleTask:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    spec: str = ""
    implementer_output: str = ""
    verifier_feedback: str = ""
    iterations: int = 0
    status: str = "pending"
    final_output: str = ""
    approved: bool = False


IMPLEMENTER_ROLE = RoleDefinition(
    name="Implementer",
    description="Implements changes based on specifications. Generates code, configs, docs.",
    system_prompt=(
        "You are an IMPLEMENTER agent. Your role is to BUILD and CREATE.\n"
        "Given a specification, produce a complete, working implementation.\n"
        "Rules:\n"
        "1. Output complete, runnable code\n"
        "2. Include error handling and edge cases\n"
        "3. Add brief inline comments for complex logic\n"
        "4. Format code with proper indentation\n"
        "5. List assumptions made during implementation"
    ),
    capabilities=["code_gen", "file_write", "shell_exec", "search"],
)

VERIFIER_ROLE = RoleDefinition(
    name="Verifier",
    description="Validates implementations. Checks for bugs, edge cases, style.",
    system_prompt=(
        "You are a VERIFIER agent. Your role is to REVIEW and VALIDATE.\n"
        "Given an implementation, identify issues and suggest improvements.\n"
        "Rules:\n"
        "1. Check for bugs, edge cases, security issues\n"
        "2. Verify correctness against the specification\n"
        "3. Check code style and conventions\n"
        "4. Rate the implementation: APPROVED / NEEDS_FIX / REJECTED\n"
        "5. If NEEDS_FIX, list specific actionable changes"
    ),
    capabilities=["code_review", "test_run", "lint", "security_scan"],
)


class SubAgentRoles:
    """Manages Implementer-Verifier role-based agent execution."""

    MAX_ITERATIONS = 3
    MAX_CONCURRENT_PAIRS = 10

    def __init__(self, consciousness: Any = None):
        self._consciousness = consciousness
        self._active_tasks: dict[str, RoleTask] = {}
        self._completed_tasks: list[RoleTask] = []
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_PAIRS)

    async def run_implement_verify(
        self,
        spec: str,
        max_iterations: int = 3,
        implement_fn: Any = None,
        verify_fn: Any = None,
    ) -> RoleTask:
        """Run a complete Implement-Verify cycle.

        Args:
            spec: The task specification
            max_iterations: Max implement-verify iterations
            implement_fn: Custom implementer function
            verify_fn: Custom verifier function

        Returns:
            RoleTask with final output and verification status
        """
        task = RoleTask(spec=spec, iterations=0)

        async with self._semaphore:
            self._active_tasks[task.id] = task

            for iteration in range(min(max_iterations, self.MAX_ITERATIONS)):
                task.iterations = iteration + 1
                logger.info(f"SubAgentRoles [{task.id}] iteration {task.iterations}/{max_iterations}")

                if implement_fn:
                    task.implementer_output = await implement_fn(
                        spec, task.verifier_feedback
                    )
                elif self._consciousness:
                    task.implementer_output = await self._default_implement(spec, task.verifier_feedback)
                else:
                    task.implementer_output = f"[Implementer {task.id}] No worker available"

                task.status = "verifying"

                if verify_fn:
                    task.verifier_feedback = await verify_fn(
                        spec, task.implementer_output
                    )
                elif self._consciousness:
                    task.verifier_feedback = await self._default_verify(spec, task.implementer_output)
                else:
                    task.verifier_feedback = "APPROVED"

                if "APPROVED" in task.verifier_feedback.upper():
                    task.approved = True
                    task.final_output = task.implementer_output
                    task.status = "completed"
                    break
                elif "REJECTED" in task.verifier_feedback.upper():
                    task.status = "rejected"
                    task.final_output = task.implementer_output
                    break
                else:
                    task.status = "needs_fix"

            if not task.approved:
                task.status = "max_iterations"

            self._active_tasks.pop(task.id, None)
            self._completed_tasks.append(task)

        return task

    async def run_implementer_only(self, spec: str, implement_fn: Any = None) -> str:
        task = RoleTask(spec=spec, iterations=1)
        if implement_fn:
            return await implement_fn(spec, "")
        if self._consciousness:
            return await self._default_implement(spec, "")
        return f"[Implementer] No worker for: {spec[:100]}"

    def get_status(self) -> dict[str, Any]:
        return {
            "active_tasks": len(self._active_tasks),
            "completed_tasks": len(self._completed_tasks),
            "approved_count": sum(1 for t in self._completed_tasks if t.approved),
            "current_semaphore": self._semaphore._value,
        }

    async def _default_implement(self, spec: str, feedback: str) -> str:
        try:
            context = f"Specification:\n{spec}"
            if feedback:
                context += f"\n\nPrevious feedback to address:\n{feedback}"
            return await self._consciousness.chain_of_thought(context, steps=2)
        except Exception as e:
            return f"Implementer error: {e}"

    async def _default_verify(self, spec: str, output: str) -> str:
        try:
            context = (
                f"Specification:\n{spec}\n\n"
                f"Implementation to verify:\n{output}\n\n"
                "Rate: APPROVED / NEEDS_FIX / REJECTED"
            )
            return await self._consciousness.chain_of_thought(context, steps=1)
        except Exception as e:
            return f"Verifier error: {e}"
