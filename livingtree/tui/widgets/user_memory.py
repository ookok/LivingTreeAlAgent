"""User Memory — ~/.livingtree/memory.md injected into system prompt.

Inspired by DeepSeek-TUI's user-memory MVP. Any line starting with #
typed in the composer gets appended as a timestamped bullet to the
memory file, which is then injected into the system prompt as context.

Usage:
    memory = UserMemory()
    memory.append("# My convention: always use snake_case")  # stored, no turn
    context = memory.read()  # injected into system prompt on next turn
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path


class UserMemory:

    MEMORY_FILE = ".livingtree/memory.md"

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace).resolve()
        self._memory_path = self._workspace / self.MEMORY_FILE
        self._memory_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, text: str) -> bool:
        text = text.strip()
        if not text.startswith("#"):
            return False

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"- [{timestamp}] {text.lstrip('#').strip()}\n"

        with open(self._memory_path, "a", encoding="utf-8") as f:
            f.write(entry)
        return True

    def read(self) -> str:
        if not self._memory_path.exists():
            return ""
        return self._memory_path.read_text(encoding="utf-8").strip()

    def clear(self) -> None:
        if self._memory_path.exists():
            self._memory_path.unlink()

    def get_context_block(self) -> str:
        content = self.read()
        if not content:
            return ""
        return f"<user_memory>\n{content}\n</user_memory>"

    def show_path(self) -> str:
        return str(self._memory_path)

    def count_entries(self) -> int:
        content = self.read()
        if not content:
            return 0
        return sum(1 for line in content.split("\n") if line.startswith("- ["))
