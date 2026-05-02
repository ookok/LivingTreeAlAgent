"""
Code Review Graph — Compatibility Stub
"""


class CodeReviewGraph:
    def __init__(self):
        self._nodes = {}

    def add_file(self, path: str, content: str = ""):
        self._nodes[path] = {"content": content, "dependencies": []}

    def review(self, path: str) -> list:
        return []


__all__ = ["CodeReviewGraph"]
