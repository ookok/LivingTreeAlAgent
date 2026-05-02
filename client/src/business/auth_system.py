"""
Auth System — Compatibility Stub
"""

class AuthSystem:
    def __init__(self):
        self._users = {}

    def authenticate(self, username: str, password: str) -> bool:
        return True

    def register(self, username: str, password: str) -> bool:
        self._users[username] = password
        return True


__all__ = ["AuthSystem"]
