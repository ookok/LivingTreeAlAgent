"""Task List Panel — Real-time todo list showing system orchestration tasks.

Displays active tasks from the orchestrator/planner with live status icons.
Updates via timer or manual refresh. Compact, scrollable, color-coded.
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

STATUS_ICONS = {"pending": "○", "running": "◐", "done": "●", "failed": "✗", "cancelled": "⊘"}
STATUS_COLORS = {"pending": "#484f58", "running": "#d29922", "done": "#3fb950", "failed": "#f85149", "cancelled": "#8b949e"}


class TaskListPanel(Vertical):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tasks: list[dict] = []
        self._title = "Tasks"

    def compose(self) -> ComposeResult:
        yield Static(f"[bold #58a6ff]{self._title}[/bold #58a6ff]", id="task-list-header")
        yield Static("[dim]Waiting for tasks...[/dim]", id="task-list-body")

    def load_tasks(self, tasks: list[dict]) -> None:
        self._tasks = tasks
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
        self._render()

    def _render(self) -> None:
        try:
            body = self.query_one("#task-list-body", Static)
            if not self._tasks:
                body.update("[dim]Waiting for tasks...[/dim]")
                return

            lines = [f"[bold #58a6ff]{self._title} ({len(self._tasks)})[/bold #58a6ff]"]
            for i, t in enumerate(self._tasks[-12:]):
                status = t.get("status", "pending")
                name = t.get("name", t.get("action", f"Task {i+1}"))
                detail = t.get("detail", "")
                icon = STATUS_ICONS.get(status, "?")
                color = STATUS_COLORS.get(status, "#8b949e")
                name_short = name[:30] + ("..." if len(name) > 30 else "")
                line = f"  [{color}]{icon}[/{color}] {name_short}"
                if detail:
                    line += f" [dim]{detail[:20]}[/dim]"
                lines.append(line)

            body.update("\n".join(lines))
        except Exception:
            pass
