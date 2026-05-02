"""
IDE Service — Compatibility Stub
"""


class IDEService:
    def __init__(self):
        self._projects = []

    def open_project(self, path: str):
        self._projects.append(path)

    def get_completions(self, code: str, cursor_pos: int) -> list:
        return []


__all__ = ["IDEService"]
