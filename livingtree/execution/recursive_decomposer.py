"""ROMA-inspired Recursive Task Decomposer.

Based on arXiv:2602.01848: "ROMA: Recursive Open Meta-Agent Framework"

Core: Decompose goals into dependency-aware subtask trees.
Four modular roles: Atomizer → Planner → Executor → Aggregator.
Key insight: recursive, dependency-aware decomposition enables parallel execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class TaskType(str, Enum):
    ATOMIC = "atomic"      # Directly executable
    COMPOSITE = "composite"  # Needs decomposition


class DepType(str, Enum):
    SEQUENTIAL = "sequential"    # Must run after predecessor
    PARALLEL = "parallel"        # Can run simultaneously
    CONDITIONAL = "conditional"  # Run only if condition met


@dataclass
class SubTask:
    """A node in the task decomposition tree."""
    id: str
    description: str
    task_type: TaskType = TaskType.COMPOSITE
    dependencies: list[str] = field(default_factory=list)  # IDs of prerequisite tasks
    dep_type: DepType = DepType.SEQUENTIAL
    agent: str = ""           # Assigned agent/model
    estimated_tokens: int = 0
    result: str = ""
    status: str = "pending"   # pending/running/done/failed


class RecursiveDecomposer:
    """Recursive task decomposition following ROMA's four-role pattern.

    Atomizer: decide if task is atomic or needs decomposition.
    Planner: expand composite tasks into dependency-annotated subtasks.
    Executor: process atomic tasks (delegated to agent).
    Aggregator: synthesize and verify subtask results bottom-up.
    """

    DECOMPOSITION_PATTERNS = {
        # Pattern: input keywords → subtask breakdown
        "analyze": [
            ("gather_context", "Gather relevant context and data", DepType.PARALLEL),
            ("identify_patterns", "Identify key patterns and insights", DepType.SEQUENTIAL),
            ("synthesize_findings", "Synthesize findings into conclusions", DepType.SEQUENTIAL),
        ],
        "implement": [
            ("understand_requirements", "Understand implementation requirements", DepType.SEQUENTIAL),
            ("design_solution", "Design the solution approach", DepType.SEQUENTIAL),
            ("implement_code", "Implement the code", DepType.PARALLEL),
            ("test_verify", "Test and verify the implementation", DepType.SEQUENTIAL),
        ],
        "compare": [
            ("extract_features_a", "Extract features of option A", DepType.PARALLEL),
            ("extract_features_b", "Extract features of option B", DepType.PARALLEL),
            ("compare_features", "Compare extracted features", DepType.SEQUENTIAL),
        ],
        "search": [
            ("formulate_query", "Formulate search query", DepType.SEQUENTIAL),
            ("execute_search", "Execute search across sources", DepType.PARALLEL),
            ("rank_results", "Rank and filter results", DepType.SEQUENTIAL),
        ],
        "summarize": [
            ("extract_key_points", "Extract key points from content", DepType.SEQUENTIAL),
            ("organize_structure", "Organize into logical structure", DepType.SEQUENTIAL),
            ("write_summary", "Write the final summary", DepType.SEQUENTIAL),
        ],
    }

    def decompose(self, task: str, max_depth: int = 3) -> list[SubTask]:
        """Recursively decompose a task into dependency-annotated subtasks.

        Args:
            task: Task description.
            max_depth: Maximum recursion depth.

        Returns:
            List of SubTask nodes with dependency annotations.
        """
        task_lower = task.lower()

        # Atomizer: check if atomic
        if self._is_atomic(task) or max_depth <= 0:
            return [SubTask(
                id=f"atomic_{hash(task) % 10000}",
                description=task,
                task_type=TaskType.ATOMIC,
            )]

        # Planner: select decomposition pattern
        subtasks = self._plan(task, task_lower)
        return subtasks

    def parallel_groups(self, subtasks: list[SubTask]) -> list[list[SubTask]]:
        """Group subtasks that can run in parallel.

        Returns groups ordered by dependency: each group's tasks can run
        simultaneously, and groups must execute sequentially.
        """
        completed: set = set()
        groups: list[list[SubTask]] = []
        remaining = list(subtasks)

        while remaining:
            ready = []
            still_waiting = []

            for st in remaining:
                deps_met = all(d in completed for d in st.dependencies)
                if deps_met:
                    ready.append(st)
                else:
                    still_waiting.append(st)

            if not ready:
                # Circular dependency or all blocked — force sequential
                if still_waiting:
                    groups.append([still_waiting[0]])
                    completed.add(still_waiting[0].id)
                    remaining = still_waiting[1:]
                else:
                    break
            else:
                groups.append(ready)
                for st in ready:
                    completed.add(st.id)
                remaining = still_waiting

        return groups

    # ── Internal ──

    def _is_atomic(self, task: str) -> bool:
        """Atomizer: determine if task can be executed directly."""
        return len(task.split()) < 5

    def _plan(self, task: str, task_lower: str) -> list[SubTask]:
        """Planner: expand task into dependency-annotated subtasks."""
        for keyword, pattern in self.DECOMPOSITION_PATTERNS.items():
            if keyword in task_lower:
                return [
                    SubTask(
                        id=f"{keyword}_{name}_{i}",
                        description=desc,
                        dependencies=[f"{keyword}_{pattern[j-1][0]}_{j-1}" for j in range(i)],
                        dep_type=dtype,
                    )
                    for i, (name, desc, dtype) in enumerate(pattern)
                ]

        # Default: sequential decomposition
        return [
            SubTask(
                id=f"step_{i}",
                description=f"Step {i+1} of: {task[:60]}",
                dependencies=[f"step_{j}" for j in range(i)],
            )
            for i in range(3)
        ]


# ── Singleton ──

_decomposer: Optional[RecursiveDecomposer] = None


def get_recursive_decomposer() -> RecursiveDecomposer:
    global _decomposer
    if _decomposer is None:
        _decomposer = RecursiveDecomposer()
    return _decomposer
