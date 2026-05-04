"""LoadingSplash — Full-screen animated startup splash with spinner."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Center, Middle
from textual.widgets import Static

SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class LoadingSplash(Static):
    """Full-screen loading overlay with animated spinner and progress."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._spinner_idx = 0
        self._spinner_task: Optional[asyncio.Task] = None
        self._t0: float = 0.0
        self._timer_task: Optional[asyncio.Task] = None
        self._status = ""
        self._detail = ""
        self._elapsed = 0.0

    def compose(self) -> ComposeResult:
        with Center():
            with Middle(id="splash-box"):
                yield Static("🌳", id="splash-logo")
                yield Static("LivingTree AI Agent", id="splash-title")
                yield Static("v2.0 — 数字生命体平台", id="splash-subtitle")
                yield Static("", id="splash-status")
                yield Static("", id="splash-detail")
                yield Static("", id="splash-timer")

    def on_mount(self) -> None:
        self._start_spinner()

    def _start_spinner(self) -> None:
        async def spin():
            while True:
                self._spinner_idx = (self._spinner_idx + 1) % len(SPINNER)
                self.refresh()
                await asyncio.sleep(0.12)

        self._spinner_task = asyncio.create_task(spin())

    def _start_timer(self) -> None:
        self._t0 = time.time()

        async def tick():
            while True:
                self._elapsed = time.time() - self._t0
                self.refresh()
                await asyncio.sleep(0.5)

        self._timer_task = asyncio.create_task(tick())

    def start_timer(self) -> None:
        self._start_timer()

    def stop_timer(self) -> None:
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None
        if self._spinner_task:
            self._spinner_task.cancel()
            self._spinner_task = None

    def set_status(self, status: str, detail: str = "") -> None:
        self._status = status
        self._detail = detail
        self.refresh()

    def render(self) -> str:
        icon = SPINNER[self._spinner_idx]
        lines = []

        line1 = f"{icon} {self._status}" if self._status else f"{icon} 正在启动..."
        lines.append(line1)

        if self._detail:
            lines.append(f"    [dim]{self._detail}[/dim]")

        if self._elapsed > 0:
            lines.append(f"    [dim]{self._elapsed:.0f}s[/dim]")

        return "\n".join(lines)
