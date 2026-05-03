"""TaskTreePanel — Live LifeEngine pipeline status with thinking animation.

Shows the 6 stages: perceive → cognize → plan → execute → reflect → evolve
Each stage has a status indicator: ○ pending, ◐ running, ● done, ✗ failed
"""

from __future__ import annotations

import asyncio
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Vertical, Container
from textual.widgets import Static, Label


STAGES = [
    ("perceive",  "Perceive 感知"),
    ("cognize",   "Cognize  认知"),
    ("plan",      "Plan     规划"),
    ("execute",   "Execute  执行"),
    ("reflect",   "Reflect  反思"),
    ("evolve",    "Evolve   进化"),
]


class StageIndicator(Static):
    """Single stage with status icon + label."""

    def __init__(self, stage_id: str, label: str, **kwargs):
        super().__init__(**kwargs)
        self.stage_id = stage_id
        self._label = label
        self._status = "pending"
        self._detail = ""

    def render(self) -> str:
        icons = {"pending": "○", "running": "◐", "done": "●", "failed": "✗"}
        colors = {"pending": "dim", "running": "yellow", "done": "green", "failed": "red"}
        icon = icons.get(self._status, "?")
        color = colors.get(self._status, "white")
        line = f"[{color}]{icon} {self._label}[/{color}]"
        if self._detail:
            line += f"\n   [{color} dim]{self._detail[:60]}[/{color} dim]"
        return line

    def set_pending(self) -> None:
        self._status = "pending"; self._detail = ""; self.refresh()

    def set_running(self, detail: str = "") -> None:
        self._status = "running"; self._detail = detail; self.refresh()

    def set_done(self, detail: str = "") -> None:
        self._status = "done"; self._detail = detail; self.refresh()

    def set_failed(self, detail: str = "") -> None:
        self._status = "failed"; self._detail = detail; self.refresh()


class TaskTreePanel(Container):
    """Live pipeline status panel with thinking animation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._indicators: dict[str, StageIndicator] = {}
        self._spinner_idx = 0
        self._spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._spinner_task: Optional[asyncio.Task] = None

    def compose(self) -> ComposeResult:
        yield Static("[bold]Task Pipeline[/bold]", id="task-title")
        for sid, label in STAGES:
            yield StageIndicator(sid, label, id=f"stage-{sid}")
        yield Static("", id="task-cost")
        yield Static("", id="task-budget")
        yield Static("", id="task-checkpoint")

    def on_mount(self) -> None:
        for sid, _ in STAGES:
            self._indicators[sid] = self.query_one(f"#stage-{sid}", StageIndicator)
        self._start_spinner()

    def _start_spinner(self) -> None:
        async def spin():
            while True:
                self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner_frames)
                try:
                    self.query_one("#task-title", Static).update(
                        f"[bold]{self._spinner_frames[self._spinner_idx]} Task Pipeline[/bold]")
                except Exception:
                    pass
                await asyncio.sleep(0.15)
        self._spinner_task = asyncio.create_task(spin())

    def update_stage(self, stage: str, status: str, detail: str = "") -> None:
        """Update a stage's status in real-time."""
        indicator = self._indicators.get(stage)
        if not indicator:
            return
        if status == "running":
            indicator.set_running(detail)
        elif status in ("done", "completed"):
            indicator.set_done(detail)
        elif status == "failed":
            indicator.set_failed(detail)
        else:
            indicator.set_pending()

    def set_cost(self, tokens: int = 0, cost_yuan: float = 0.0) -> None:
        try:
            self.query_one("#task-cost", Static).update(
                f"[dim]tokens: {tokens}  ¥{cost_yuan:.4f}[/dim]")
        except Exception:
            pass

    def set_budget(self, used: int = 0, limit: int = 1_000_000, degraded: bool = False) -> None:
        try:
            pct = used / max(limit, 1) * 100
            color = "red" if pct > 85 else "yellow" if pct > 50 else "green"
            status = " [red]DEGRADED[/red]" if degraded else ""
            self.query_one("#task-budget", Static).update(
                f"[dim]budget: [{color}]{used}/{limit}[/{color}]{status}[/dim]")
        except Exception:
            pass

    def set_checkpoint(self, session_id: str = "", steps_saved: int = 0) -> None:
        try:
            if steps_saved > 0:
                self.query_one("#task-checkpoint", Static).update(
                    f"[dim]checkpoint: {steps_saved} steps saved[/dim]")
            else:
                self.query_one("#task-checkpoint", Static).update("")
        except Exception:
            pass

    def all_done(self, success: bool = True) -> None:
        """Mark all pending stages as done/failed."""
        for sid, _ in STAGES:
            ind = self._indicators.get(sid)
            if ind and ind._status == "pending":
                if success:
                    ind.set_done()
                else:
                    ind.set_failed("pipeline failed")

    def reset(self) -> None:
        for indicator in self._indicators.values():
            indicator.set_pending()

    async def on_unmount(self) -> None:
        if self._spinner_task:
            self._spinner_task.cancel()
