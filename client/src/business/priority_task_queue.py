"""
Priority Task Queue — Compatibility Stub
"""

from enum import IntEnum
from queue import PriorityQueue
from threading import Thread


class TaskPriority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class PriorityTaskQueue:
    def __init__(self, max_workers: int = 4):
        self._queue = PriorityQueue()
        self._workers = []

    def submit(self, task, priority: TaskPriority = TaskPriority.NORMAL):
        self._queue.put((priority.value, task))


def get_task_queue():
    return PriorityTaskQueue()


__all__ = ["PriorityTaskQueue", "get_task_queue", "TaskPriority"]
