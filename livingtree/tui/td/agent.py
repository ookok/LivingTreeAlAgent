"""Compatibility stub — original Toad AgentBase from TUI has been removed.

Provides minimal AgentBase, AgentReady, AgentFail symbols so that
execution/panel_agent.py and other modules can import without crash.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AgentBase:
    """Minimal base class for panel agents (original Toad interface)."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    async def start(self, message_target=None) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send_prompt(self, prompt: str) -> str | None:
        return None

    async def cancel(self) -> bool:
        return True

    async def set_mode(self, mode_id: str) -> str | None:
        return None

    def get_info(self) -> Any:
        return ""


@dataclass
class AgentReady:
    """Signal that an agent has completed startup and is ready."""


@dataclass
class AgentFail:
    """Signal that an agent has encountered an error."""
    reason: str = ""
