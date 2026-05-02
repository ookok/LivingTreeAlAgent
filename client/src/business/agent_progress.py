"""
Agent Progress — Compatibility Stub

Tracking agent task progress and emitting status updates.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any
from datetime import datetime


class ProgressPhase(Enum):
    INIT = "init"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class AgentProgress:
    phase: ProgressPhase = ProgressPhase.INIT
    message: str = ""
    percent: float = 0.0
    agent_id: str = ""
    task_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentProgressCallback:
    def __init__(self):
        self._listeners: list = []

    def on_progress(self, progress: AgentProgress):
        for listener in self._listeners:
            try:
                listener(progress)
            except Exception:
                pass

    def add_listener(self, callback):
        self._listeners.append(callback)


def get_progress_tracker():
    return AgentProgressCallback()


def on_progress(progress: AgentProgress):
    pass


__all__ = [
    "AgentProgress", "AgentProgressCallback",
    "ProgressPhase", "get_progress_tracker", "on_progress",
]
