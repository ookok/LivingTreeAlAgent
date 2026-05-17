"""Session management mixin for IntegrationHub — extracted from hub.py."""
from __future__ import annotations
from typing import Any

class SessionManagementMixin:
    """Mixin providing session management methods."""

    async def restore_turn(self, turn_id: int) -> dict:
        if self.side_git:
            ok = await self.side_git.restore(turn_id)
            return {"restored": ok, "turn_id": turn_id}
        return {"restored": False, "error": "SideGit not available"}

    async def revert_turn(self, turn_id: int) -> dict:
        return await self.restore_turn(turn_id)

    async def list_side_git_turns(self) -> list[dict]:
        if self.side_git:
            return await self.side_git.list_turns()
        return []

    async def list_sessions(self) -> list[dict]:
        if self.session_manager:
            return await self.session_manager.list_sessions()
        return []

    async def resume_session(self, session_id: str) -> dict | None:
        if self.session_manager:
            state = await self.session_manager.load(session_id)
            return state.model_dump() if state else None
        return None

__all__ = ["SessionManagementMixin"]
