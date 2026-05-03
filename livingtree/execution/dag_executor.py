"""DAGExecutor — Parallel step execution with dependency graph.

Replaces serial for-loop with topological parallel execution.
Steps with no dependencies run concurrently.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger


class DAGExecutor:
    """Execute task steps respecting DAG dependencies in parallel.

    Steps without resolved dependencies run concurrently.
    Steps with unmet dependencies wait until satisfied.
    """

    def __init__(self, max_parallel: int = 5):
        self.max_parallel = max_parallel
        self._semaphore = asyncio.Semaphore(max_parallel)

    async def execute(self, plan: list[dict[str, Any]], execute_one,
                      ctx: Any = None) -> list[dict[str, Any]]:
        """Execute a plan with DAG-aware parallelism.

        Args:
            plan: list of step dicts with optional 'depends_on': [idx0, idx1]
            execute_one: async func(step, ctx) -> result dict
            ctx: shared context

        Returns:
            results list in original plan order
        """
        total = len(plan)
        results: list[Any] = [None] * total
        completed = asyncio.Event()
        # Track which steps are ready
        done: set[int] = set()
        running: set[int] = set()
        lock = asyncio.Lock()

        async def run_step(idx: int) -> None:
            async with self._semaphore:
                step = plan[idx]
                try:
                    r = await execute_one(step, ctx)
                    results[idx] = r or {"step": step, "status": "completed"}
                except Exception as e:
                    results[idx] = {"step": step, "status": "failed", "error": str(e)}
                finally:
                    async with lock:
                        done.add(idx)
                        running.discard(idx)

        while len(done) < total:
            # Find steps whose dependencies are all done AND not yet running
            ready = []
            for i in range(total):
                if i in done or i in running:
                    continue
                deps = plan[i].get("depends_on", [])
                if all(d in done for d in deps):
                    ready.append(i)

            if not ready and not running:
                # Deadlock or empty: run remaining in order
                for i in range(total):
                    if i not in done and i not in running:
                        ready.append(i)
                        break

            for i in ready[:self.max_parallel]:
                running.add(i)
                asyncio.create_task(run_step(i))

            await asyncio.sleep(0.05)

        return results


def add_dependencies(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Auto-add sequential dependencies if none specified.

    If no step has 'depends_on', chains them serially.
    This preserves backward compatibility.
    """
    has_deps = any("depends_on" in s for s in plan)
    if has_deps:
        return plan
    # Chain: step N depends on step N-1
    for i in range(1, len(plan)):
        plan[i]["depends_on"] = [i - 1]
    return plan
