"""
Adaptive Task Decomposer — Compatibility Stub
"""

from typing import List
from dataclasses import dataclass, field


@dataclass
class Task:
    id: str = ""
    description: str = ""
    subtasks: List["Task"] = field(default_factory=list)


@dataclass
class Plan:
    steps: List[Task] = field(default_factory=list)
    estimated_tokens: int = 0


class TaskType:
    SIMPLE = "simple"
    COMPLEX = "complex"
    PARALLEL = "parallel"


class AdaptiveTaskDecomposer:
    def __init__(self, max_depth: int = 3):
        self.max_depth = max_depth

    def decompose(self, description: str, complexity: float = 0.5) -> List[Task]:
        return [Task(id="1", description=description)]


def get_adaptive_task_decomposer():
    return AdaptiveTaskDecomposer()


__all__ = ["AdaptiveTaskDecomposer", "Task", "Plan", "TaskType", "get_adaptive_task_decomposer"]
