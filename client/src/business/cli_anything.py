"""
CLI Anything — Compatibility Stub
"""


class CLIAnything:
    def __init__(self):
        self._commands = {}

    def register(self, name: str, handler):
        self._commands[name] = handler

    def run(self, command: str, *args) -> str:
        return f"[CLIAnything] {command}"


__all__ = ["CLIAnything"]
