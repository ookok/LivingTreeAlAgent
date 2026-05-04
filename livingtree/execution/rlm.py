"""RLM — Recursive Language Model: parallel fan-out with flash models.

Inspired by DeepSeek-TUI's `rlm_query` tool. Fans out 1–16 cheap
flash model children in parallel against the existing LLM client for batched
analysis, decomposition, or parallel reasoning. Each child gets a slice of
the query and returns structured results.

Usage:
    rlm = RLMRunner(consciousness=dna.flash)
    results = await rlm.fan_out(
        prompt="Compare these 8 files for security issues and suggest fixes",
        n_workers=8,
        splitter=RLMSplitter.BY_ITEM,
    )
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable, Optional

from loguru import logger


class RLMSplitter(Enum):
    """How to split the input across parallel flash workers."""
    BY_ITEM = "by_item"
    BY_ASPECT = "by_aspect"
    BY_CHUNK = "by_chunk"
    CUSTOM = "custom"


@dataclass
class RLMTask:
    """A single sub-task for a flash worker."""
    id: int
    prompt: str
    context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class RLMResult:
    """Result from a single flash worker."""
    task_id: int
    content: str
    success: bool = True
    error: str = ""
    tokens_used: int = 0
    duration_ms: float = 0.0

@dataclass
class RLMAggregate:
    """Aggregated results from all parallel workers."""
    results: list[RLMResult]
    total_tokens: int = 0
    total_duration_ms: float = 0.0
    worker_count: int = 0
    success_count: int = 0
    fail_count: int = 0

    def summary(self) -> str:
        return (
            f"RLM fan-out: {self.success_count}/{self.worker_count} ok, "
            f"{self.total_tokens} tokens, {self.total_duration_ms:.0f}ms"
        )

    def best_result(self) -> RLMResult | None:
        if not self.results:
            return None
        return max(self.results, key=lambda r: len(r.content) if r.success else 0)


class RLMRunner:
    """Parallel flash-model fan-out engine.

    Splits a complex query into N sub-tasks, dispatches them to N
    flash-model workers in parallel, then aggregates results.
    """

    def __init__(
        self,
        consciousness: Any = None,
        max_workers: int = 16,
        worker_timeout: float = 60.0,
    ):
        self._consciousness = consciousness
        self.max_workers = max_workers
        self.worker_timeout = worker_timeout

    async def fan_out(
        self,
        prompt: str,
        n_workers: int = 4,
        splitter: RLMSplitter = RLMSplitter.BY_ASPECT,
        worker_fn: Callable[[RLMTask], Any] | None = None,
        items: list[str] | None = None,
    ) -> RLMAggregate:
        """Launch N parallel flash workers on split sub-tasks.

        Args:
            prompt: The main query/prompt
            n_workers: Number of parallel workers (1-16)
            splitter: How to split the input
            worker_fn: Custom worker function; uses default if None
            items: Pre-split items for BY_ITEM mode

        Returns:
            RLMAggregate with all worker results
        """
        n = min(max(n_workers, 1), self.max_workers)
        tasks = self._split(prompt, n, splitter, items)

        semaphore = asyncio.Semaphore(n)
        workers = [self._run_worker(t, worker_fn, semaphore) for t in tasks]

        results: list[RLMResult] = await asyncio.gather(*workers, return_exceptions=True)

        processed = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                processed.append(RLMResult(
                    task_id=tasks[i].id if i < len(tasks) else i,
                    content="",
                    success=False,
                    error=str(r),
                ))
            else:
                processed.append(r)

        return RLMAggregate(
            results=processed,
            total_tokens=sum(r.tokens_used for r in processed),
            total_duration_ms=sum(r.duration_ms for r in processed),
            worker_count=n,
            success_count=sum(1 for r in processed if r.success),
            fail_count=sum(1 for r in processed if not r.success),
        )

    def _split(
        self,
        prompt: str,
        n: int,
        splitter: RLMSplitter,
        items: list[str] | None,
    ) -> list[RLMTask]:
        """Split the prompt into N sub-tasks."""
        if splitter == RLMSplitter.BY_ITEM and items:
            return [
                RLMTask(
                    id=i,
                    prompt=f"Analyze the following item in context of: {prompt}\n\nItem:\n{item}",
                    context=prompt,
                    metadata={"item": item, "index": i},
                )
                for i, item in enumerate(items[:n])
            ]

        if splitter == RLMSplitter.BY_ASPECT:
            aspects = self._generate_aspects(prompt, n)
            return [
                RLMTask(
                    id=i,
                    prompt=f"Analyze from perspective: {aspect}\n\nQuery:\n{prompt}",
                    context=prompt,
                    metadata={"aspect": aspect},
                )
                for i, aspect in enumerate(aspects)
            ]

        if splitter == RLMSplitter.BY_CHUNK:
            words = prompt.split()
            chunk_size = max(1, len(words) // n)
            chunks = []
            for i in range(n):
                start = i * chunk_size
                end = start + chunk_size if i < n - 1 else len(words)
                chunks.append(" ".join(words[start:end]))
            return [
                RLMTask(
                    id=i,
                    prompt=f"Analyze this excerpt (part {i+1}/{n}):\n{chunk}",
                    metadata={"chunk_idx": i},
                )
                for i, chunk in enumerate(chunks)
            ]

        return [
            RLMTask(id=i, prompt=prompt, metadata={"worker": i})
            for i in range(n)
        ]

    async def _run_worker(
        self,
        task: RLMTask,
        worker_fn: Callable | None,
        semaphore: asyncio.Semaphore,
    ) -> RLMResult:
        """Run a single flash worker with concurrency control."""
        import time
        t0 = time.monotonic()

        async with semaphore:
            try:
                if worker_fn:
                    content = await worker_fn(task)
                elif self._consciousness:
                    content = await self._default_worker(task)
                else:
                    content = f"[{task.id}] no worker available for: {task.prompt[:100]}"

                elapsed = (time.monotonic() - t0) * 1000
                return RLMResult(
                    task_id=task.id,
                    content=str(content),
                    success=True,
                    tokens_used=len(content),
                    duration_ms=elapsed,
                )
            except asyncio.TimeoutError:
                return RLMResult(
                    task_id=task.id,
                    content="",
                    success=False,
                    error=f"Worker {task.id} timed out after {self.worker_timeout}s",
                )
            except Exception as e:
                return RLMResult(
                    task_id=task.id,
                    content="",
                    success=False,
                    error=str(e),
                )

    async def _default_worker(self, task: RLMTask) -> str:
        """Default worker using flash consciousness."""
        if not self._consciousness:
            return f"[Worker {task.id}] No consciousness available"

        parts = []
        try:
            async for token in self._consciousness.stream_of_thought(
                task.prompt,
                max_tokens=2048,
                temperature=0.3,
            ):
                parts.append(token)
        except Exception as e:
            return f"[Worker {task.id}] Error: {e}"

        return "".join(parts) or f"[Worker {task.id}] Empty response"

    @staticmethod
    def _generate_aspects(prompt: str, n: int) -> list[str]:
        """Generate analysis aspects based on prompt keywords."""
        default = [
            "security", "performance", "maintainability",
            "correctness", "usability", "extensibility",
            "reliability", "efficiency", "testability",
            "documentation", "architecture", "data_flow",
            "error_handling", "concurrency", "compatibility",
            "scalability",
        ]
        return default[:n]
