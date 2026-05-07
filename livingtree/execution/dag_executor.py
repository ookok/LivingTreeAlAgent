"""DAGExecutor — Parallel step execution with dependency graph + Context-Folding.

Replaces serial for-loop with topological parallel execution.
Steps with no dependencies run concurrently.

FoldAgent integration: each step's result is folded into a compact structured
summary, collapsing verbose intermediate outputs while preserving key entities,
decisions, and action items. This keeps downstream context ~10x smaller.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from loguru import logger

from .context_fold import FoldResult, fold_context, fold_text_heuristic


class DAGExecutor:
    """Execute task steps respecting DAG dependencies in parallel.

    Steps without resolved dependencies run concurrently.
    Steps with unmet dependencies wait until satisfied.

    FoldAgent: after execution, each step result can be folded into a
    compact summary via fold_results() or automatically via fold=True.
    """

    def __init__(self, max_parallel: int = 5):
        self.max_parallel = max_parallel
        self._semaphore = asyncio.Semaphore(max_parallel)

    async def execute(self, plan: list[dict[str, Any]], execute_one,
                      ctx: Any = None, fold: bool = False,
                      fold_max_chars: int = 500) -> list[dict[str, Any]]:
        """Execute a plan with DAG-aware parallelism and optional context-folding.

        Args:
            plan: list of step dicts with optional 'depends_on': [idx0, idx1]
            execute_one: async func(step, ctx) -> result dict
            ctx: shared context
            fold: FoldAgent — if True, fold each step result into compact summary
            fold_max_chars: Target max chars per folded step

        Returns:
            results list in original plan order, each with optional '_fold' key
        """
        total = len(plan)
        results: list[Any] = [None] * total
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
            ready = []
            for i in range(total):
                if i in done or i in running:
                    continue
                deps = plan[i].get("depends_on", [])
                if all(d in done for d in deps):
                    ready.append(i)

            if not ready and not running:
                for i in range(total):
                    if i not in done and i not in running:
                        ready.append(i)
                        break

            for i in ready[:self.max_parallel]:
                running.add(i)
                asyncio.create_task(run_step(i))

            await asyncio.sleep(0.05)

        if fold:
            await self._fold_results(results, fold_max_chars)

        return results

    async def _fold_results(self, results: list[dict[str, Any]],
                             max_chars: int = 500):
        """FoldAgent: post-execution folding of step results into compact summaries.

        Each result dict gets a '_fold' key with a FoldResult, and the
        original content is preserved in '_full_content' for fallback.
        """
        for i, r in enumerate(results):
            if not isinstance(r, dict):
                continue
            content_parts = []
            for key in ("output", "content", "result", "summary", "text"):
                val = r.get(key)
                if isinstance(val, str) and len(val) > 0:
                    content_parts.append(val)
            if not content_parts:
                r["_fold"] = FoldResult(original_length=0, folded_length=0,
                                         summary=str(r.get("status", "ok")))
                continue

            full = "\n".join(content_parts)
            if len(full) <= max_chars:
                r["_fold"] = FoldResult(original_length=len(full),
                                         folded_length=len(full), summary=full)
            else:
                folded = fold_text_heuristic(full, max_chars)
                r["_fold"] = FoldResult(original_length=len(full),
                                         folded_length=len(folded),
                                         summary=folded)
            r["_full_content"] = full

    async def fold_results(self, results: list[dict[str, Any]],
                           consciousness: Any = None,
                           max_chars: int = 500) -> list[dict[str, Any]]:
        """FoldAgent: fold existing results with optional LLM consciousness.

        Each result is folded in-place: '_fold' key added, original preserved
        in '_full_content'. Returns modified results list.
        """
        for i, r in enumerate(results):
            if not isinstance(r, dict):
                continue
            content_parts = []
            for key in ("output", "content", "result", "summary", "text"):
                val = r.get(key)
                if isinstance(val, str) and len(val) > 0:
                    content_parts.append(val)
            if not content_parts:
                r["_fold"] = FoldResult(original_length=0, folded_length=0,
                                         summary=str(r.get("status", "ok")))
                continue

            full = "\n".join(content_parts)
            r["_full_content"] = full

            if len(full) <= max_chars:
                r["_fold"] = FoldResult(original_length=len(full),
                                         folded_length=len(full), summary=full)
            else:
                folded = await fold_context(full, consciousness, "general", max_chars)
                r["_fold"] = folded

        return results

    def compact_context(self, results: list[dict[str, Any]]) -> str:
        """FoldAgent: build a compact context block from folded results.

        For feeding downstream tasks — includes only folded summaries,
        not the full intermediate outputs.
        """
        lines = [f"## DAG执行结果 ({len(results)}步骤)\n"]
        for i, r in enumerate(results):
            if not isinstance(r, dict):
                continue
            status = r.get("status", "?")
            fold = r.get("_fold")
            step_name = r.get("step", {}).get("name", f"步骤{i+1}") if isinstance(r.get("step"), dict) else f"步骤{i+1}"
            if fold:
                summary = fold.summary if hasattr(fold, 'summary') else str(fold)
                lines.append(f"- [{status}] {step_name}: {summary[:200]}")
            else:
                lines.append(f"- [{status}] {step_name}")
        return "\n".join(lines)


def add_dependencies(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Auto-add sequential dependencies if none specified.

    If no step has 'depends_on', chains them serially.
    This preserves backward compatibility.
    """
    has_deps = any("depends_on" in s for s in plan)
    if has_deps:
        return plan
    for i in range(1, len(plan)):
        plan[i]["depends_on"] = [i - 1]
    return plan
