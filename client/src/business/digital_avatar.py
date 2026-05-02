"""
Digital Avatar — Compatibility Stub
"""

class DigitalAvatar:
    def __init__(self, name: str = "", personality: str = ""):
        self.name = name
        self.personality = personality

    def respond(self, message: str) -> str:
        return f"[{self.name}] {message}"


__all__ = ["DigitalAvatar"]
