"""
IDE Agent — Compatibility Stub
"""


class IDEAgent:
    def __init__(self, workspace: str = ""):
        self.workspace = workspace

    def analyze(self, file_path: str) -> dict:
        return {"file": file_path, "issues": []}

    def suggest(self, context: str) -> str:
        return ""


__all__ = ["IDEAgent"]
