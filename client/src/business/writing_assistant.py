"""
Writing Assistant — Compatibility Stub

Functionality migrated to livingtree.core.skills.
"""

class WritingAssistant:
    def __init__(self, model: str = ""):
        self.model = model

    def assist(self, prompt: str, style: str = "general") -> str:
        return f"[WritingAssistant] {prompt[:50]}"


__all__ = ["WritingAssistant"]
