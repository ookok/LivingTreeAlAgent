"""TUI Header widget — app title, workspace path."""
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label, Static


class TuiHeader(Horizontal):
    """Application header bar with title and workspace."""

    def compose(self) -> ComposeResult:
        yield Label("🌳 LivingTree", id="header-title")
        yield Label("", id="header-workspace")

    def update_workspace(self, path: str) -> None:
        try:
            self.query_one("#header-workspace", Label).update(f"  {path}")
        except Exception:
            pass
