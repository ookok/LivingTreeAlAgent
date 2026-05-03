"""TUI Header widget — app title, workspace path, status indicator."""
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label, Static


class TuiHeader(Horizontal):
    """Application header bar with title, workspace, and status."""

    def compose(self) -> ComposeResult:
        yield Label("LivingTree AI Agent", id="header-title")
        yield Label("", id="header-workspace")
        yield Label("ONLINE", id="header-status")

    def update_workspace(self, path: str) -> None:
        try:
            self.query_one("#header-workspace", Label).update(f"  {path}")
        except Exception:
            pass

    def update_status(self, status: str, color: str = "green") -> None:
        try:
            self.query_one("#header-status", Label).update(status)
        except Exception:
            pass
