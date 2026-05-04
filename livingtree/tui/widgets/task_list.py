"""Task List Panel — Clickable task items with detail expansion.

Shows tasks from orchestrator. Click a task to expand details in chat output.
Files created by tasks are detected and shown as clickable references.
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button

STATUS_ICONS = {"pending": "○", "running": "◐", "done": "●", "failed": "✗", "cancelled": "⊘"}
STATUS_COLORS = {"pending": "#484f58", "running": "#d29922", "done": "#3fb950", "failed": "#f85149", "cancelled": "#8b949e"}


class TaskListPanel(Vertical):

    def __init__(self, on_task_click=None, **kwargs):
        super().__init__(**kwargs)
        self._tasks: list[dict] = []
        self._on_task_click = on_task_click
        self._expanded_idx = -1

    def compose(self) -> ComposeResult:
        yield Static("[bold #58a6ff]Tasks[/bold #58a6ff]", id="task-list-header")
        yield Static("[dim]Waiting for tasks...[/dim]", id="task-list-body")

    def load_tasks(self, tasks: list[dict]) -> None:
        self._tasks = tasks
        self._expanded_idx = -1
        self._render()

    def update_task(self, idx: int, status: str, detail: str = "") -> None:
        if 0 <= idx < len(self._tasks):
            self._tasks[idx]["status"] = status
            if detail:
                self._tasks[idx]["detail"] = detail
            self._render()

    def mark_all_done(self) -> None:
        for t in self._tasks:
            if t.get("status") not in ("done", "failed"):
                t["status"] = "done"
        self._render()

    def reset(self) -> None:
        self._tasks.clear()
        self._expanded_idx = -1
        self._render()

    def toggle_task(self, idx: int) -> dict | None:
        if 0 <= idx < len(self._tasks):
            self._expanded_idx = idx if self._expanded_idx != idx else -1
            self._render()
            return self._tasks[idx]
        return None

    def _render(self) -> None:
        try:
            body = self.query_one("#task-list-body", Static)
            if not self._tasks:
                body.update("[dim]Waiting for tasks...[/dim]")
                return

            lines = []
            for i, t in enumerate(self._tasks[-15:]):
                status = t.get("status", "pending")
                name = t.get("name", t.get("action", f"T{i+1}"))[:28]
                detail = t.get("detail", "")
                icon = STATUS_ICONS.get(status, "?")
                color = STATUS_COLORS.get(status, "#8b949e")

                marker = "▼" if i == self._expanded_idx else ""
                line = f"  [{color}]{icon}[/{color}] {marker} {name}"
                if detail and i == self._expanded_idx:
                    line += f"\n    [dim]{detail[:100]}[/dim]"
                    result = t.get("result", "")
                    if result:
                        line += f"\n    [dim]Result: {str(result)[:80]}[/dim]"
                    files = t.get("files", [])
                    if files:
                        line += "\n    Files: " + ", ".join(f"[#58a6ff]{f}[/#58a6ff]" for f in files[:3])
                lines.append(line)

            body.update("\n".join(lines))
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = str(event.button.id)
        if bid.startswith("task-btn-"):
            try:
                idx = int(bid.split("-")[-1])
                task = self.toggle_task(idx)
                if task and self._on_task_click:
                    self._on_task_click(task)
            except Exception:
                pass
