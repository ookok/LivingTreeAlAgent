"""Overnight task — long-running autonomous task orchestrator."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class OvernightStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class OvernightTask:
    hub: object
    _goal: str = ""
    _status: OvernightStatus = OvernightStatus.IDLE
    _progress: float = 0.0
    _result: Optional[str] = None

    @property
    def status(self) -> OvernightStatus:
        return self._status

    @property
    def goal(self) -> str:
        return self._goal

    @property
    def progress(self) -> float:
        return self._progress

    @property
    def result(self) -> Optional[str]:
        return self._result

    async def start(self, goal: str) -> None:
        self._goal = goal
        self._status = OvernightStatus.RUNNING
        self._progress = 0.0
        logger.info("OvernightTask started: %s", goal[:60])

    async def resume(self) -> None:
        if self._status == OvernightStatus.PAUSED:
            self._status = OvernightStatus.RUNNING

    def stop(self) -> None:
        self._status = OvernightStatus.IDLE

    def pause(self) -> None:
        if self._status == OvernightStatus.RUNNING:
            self._status = OvernightStatus.PAUSED


def get_overnight_task(hub: object = None) -> OvernightTask:
    return OvernightTask(hub)
