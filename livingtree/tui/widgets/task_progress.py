"""TaskProgress — Dynamic multi-step task visualization.

Replaces static 6-stage pipeline with live subtask tracking:
- Each subtask shown with status icon: ○ ◐ ● ✗
- Parallel steps shown with visual grouping
- Progress bar + percentage + ETA
- Shared cache indicators (step uses data from another)
- Strategy retry badges (retry with pro model, etc.)
- Auto-scroll to current running step
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static, Label


class ProgressBar(Static):
    """Animated progress bar with percentage."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pct = 0.0
        self._width = 20

    def set_progress(self, pct: float) -> None:
        self._pct = min(100.0, max(0.0, pct))
        self.refresh()

    def render(self) -> str:
        filled = int(self._width * self._pct / 100)
        empty = self._width - filled
        color = "green" if self._pct >= 100 else "yellow"
        bar = f"[{color}]{'█' * filled}[/{color}]{'░' * empty}"
        return f" {bar} [{color}]{self._pct:.0f}%[/{color}]"


class SubTaskRow(Static):
    """Single subtask row with status icon, name, and metadata."""

    def __init__(self, step_id: int, name: str, **kwargs):
        super().__init__(**kwargs)
        self.step_id = step_id
        self._name = name[:40]
        self._status = "pending"
        self._detail = ""
        self._cost = ""
        self._strategy = ""
        self._parallel_group: Optional[int] = None

    def render(self) -> str:
        icons = {"pending": "○", "running": "◐", "done": "●", "failed": "✗", "denied": "⊘", "cached": "↻"}
        colors = {"pending": "dim", "running": "yellow", "done": "green", "failed": "red", "denied": "magenta", "cached": "blue"}
        icon = icons.get(self._status, "?")
        color = colors.get(self._status, "white")
        indent = "  " * (self._parallel_group or 0)
        line = f"[{color}]{icon}[/{color}] {self._name}"
        if self._detail:
            line += f" [{color} dim]{self._detail}[/{color} dim]"
        if self._strategy:
            line += f" [dim italic]({self._strategy})[/dim italic]"
        if self._cost:
            line += f" [dim]{self._cost}[/dim]"
        return f"{indent}{line}"

    def update_status(self, status: str, detail: str = "", strategy: str = "",
                      cost: str = "", parallel_group: int = 0) -> None:
        self._status = status
        self._detail = detail
        self._strategy = strategy
        self._cost = cost
        if parallel_group:
            self._parallel_group = parallel_group
        self.refresh()


class TaskProgressPanel(Container):
    """Dynamic multi-step task progress visualization.

    Shows:
    - Overall progress bar with ETA
    - Per-subtask live status rows
    - Parallel execution groups (visual indentation)
    - Strategy retry badges
    - Shared cache indicators
    - Budget/cost per step
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rows: dict[int, SubTaskRow] = {}
        self._plan: list[dict] = []
        self._start_time = 0.0
        self._spinner_task: Optional[asyncio.Task] = None
        self._spinner_idx = 0
        self._spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def compose(self) -> ComposeResult:
        yield Static("", id="tp-title")
        yield ProgressBar(id="tp-bar")
        yield Static("", id="tp-stats")
        yield Vertical(id="tp-tasks")

    def on_mount(self) -> None:
        self._start_spinner()

    def _start_spinner(self) -> None:
        async def spin():
            while True:
                self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner_frames)
                try:
                    now = time.time()
                    elapsed = now - self._start_time if self._start_time else 0
                    self.query_one("#tp-title", Static).update(
                        f"[bold]{self._spinner_frames[self._spinner_idx]} Task Progress[/bold]")
                except Exception:
                    pass
                await asyncio.sleep(0.15)
        self._spinner_task = asyncio.create_task(spin())

    def load_plan(self, plan: list[dict]) -> None:
        import time as _time
        uid = str(int(_time.time() * 1000))[-6:]
        container = self.query_one("#tp-tasks", Vertical)

        for child in list(container.children):
            child.remove()
        self._rows.clear()

        for i, step in enumerate(plan):
            name = step.get("name", step.get("description", f"Step {i+1}"))[:40]
            row = SubTaskRow(i, name, id=f"tp-row-{uid}-{i}")
            self._rows[i] = row
            container.mount(row)

        self.query_one("#tp-stats", Static).update(
            f"[dim]{len(plan)} steps | pending[/dim]")

    def update_step(self, idx: int, status: str, detail: str = "",
                    strategy: str = "", cost: str = "",
                    parallel_group: int = 0) -> None:
        """Update a single step's status."""
        row = self._rows.get(idx)
        if row:
            row.update_status(status, detail, strategy, cost, parallel_group)

        # Also update the execute stage in the legacy task tree if present
        try:
            # Update overall progress
            done = sum(1 for r in self._rows.values()
                      if r._status in ("done", "failed", "denied", "cached"))
            total = max(len(self._rows), 1)
            pct = done / total * 100
            self.query_one("#tp-bar", ProgressBar).set_progress(pct)

            elapsed = time.time() - self._start_time if self._start_time else 0
            if pct > 0 and done > 0:
                eta = elapsed / pct * 100 - elapsed
                eta_str = f"{eta:.0f}s" if eta < 120 else f"{eta/60:.1f}m"
            else:
                eta_str = "..."

            running_count = sum(1 for r in self._rows.values() if r._status == "running")
            self.query_one("#tp-stats", Static).update(
                f"[dim]{done}/{len(self._rows)} | {running_count} running | ETA {eta_str}[/dim]")
        except Exception:
            pass

    def mark_all_done(self) -> None:
        """Mark all pending rows as done."""
        for i in range(len(self._plan)):
            row = self._rows.get(i)
            if row and row._status == "pending":
                row.update_status("done", "completed")

    def reset(self) -> None:
        for row in self._rows.values():
            row.update_status("pending", "")
        self._start_time = 0.0

    async def on_unmount(self) -> None:
        if self._spinner_task:
            self._spinner_task.cancel()
