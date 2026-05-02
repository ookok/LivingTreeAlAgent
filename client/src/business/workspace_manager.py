"""
Workspace Manager — Compatibility Stub
"""

from pathlib import Path


class WorkspaceManager:
    def __init__(self, root: str = ""):
        self.root = Path(root) if root else Path.home() / "workspace"

    def list_projects(self) -> list:
        return []

    def create(self, name: str) -> str:
        return str(self.root / name)


__all__ = ["WorkspaceManager"]
