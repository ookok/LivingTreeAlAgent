"""Task Panel System — Dynamic task views with auto-expand/collapse.

Sequential tasks: each a ChatView sub-panel. Current task auto-fills main area.
Parallel tasks: title-only panels, click to expand/focus. Auto-shrink on completion.

Each task panel stores its own output. The main ChatView shows the focused task.
"""

from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button
from .chat_view import ChatView


class TaskPanel(Vertical):
    """A single task view — title bar + mini ChatView content."""

    def __init__(self, task_name: str, task_id: str, **kwargs):
        super().__init__(**kwargs)
        self._name = task_name[:30]
        self._id = task_id
        self._expanded = False
        self._status = "pending"
        self._content = ""

    def compose(self):
        yield Static(f"○ {self._name}", id="tp-title")
        yield Static("", id="tp-body")

    def set_status(self, status: str) -> None:
        self._status = status
        icons = {"pending": "○", "running": "◐", "done": "●", "failed": "✗"}
        icon = icons.get(status, "○")
        self.query_one("#tp-title", Static).update(f"{icon} {self._name}")
        if status == "done":
            self.styles.height = 1
        elif status == "running":
            self.styles.height = "1fr"

    def set_content(self, text: str) -> None:
        self._content = text
        self.query_one("#tp-body", Static).update(text[:500])

    def toggle_expand(self) -> None:
        self._expanded = not self._expanded
        self.styles.height = "1fr" if self._expanded else 1


class TaskPanelSystem(Vertical):
    """Manages multiple task panels with auto-expand/collapse."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._panels: dict[str, TaskPanel] = {}
        self._mode = "sequential"

    def compose(self):
        yield Static("", id="tps-status")

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def add_task(self, task_id: str, name: str) -> TaskPanel:
        panel = TaskPanel(name, task_id)
        self._panels[task_id] = panel
        self.mount(panel)
        return panel

    def update_task(self, task_id: str, status: str, content: str = "") -> None:
        panel = self._panels.get(task_id)
        if not panel:
            return
        panel.set_status(status)
        if content:
            panel.set_content(content)
        if self._mode == "sequential" and status == "running":
            for tid, p in self._panels.items():
                if tid != task_id:
                    p.styles.height = 1
                else:
                    p.styles.height = "1fr"
        if status == "done":
            panel.styles.height = 1

    def clear_all(self) -> None:
        for p in self._panels.values():
            p.remove()
        self._panels.clear()

    def get_active(self) -> TaskPanel | None:
        for p in self._panels.values():
            if p._status == "running":
                return p
        return None
