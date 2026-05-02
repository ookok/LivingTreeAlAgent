"""
EnhancedTask — Compatibility Stub
===================================

已迁移至 livingtree.core.planning.decomposer。
TaskNode + CoT 分解 + 调度器功能已整合。
"""


class EnhancedTask:
    def __init__(self, description: str = "", **kwargs):
        self.description = description
        self.subtasks = []

    def decompose(self) -> list:
        return self.subtasks

    def execute(self) -> dict:
        return {"success": True, "output": f"[EnhancedTask] {self.description}"}


__all__ = ["EnhancedTask"]
