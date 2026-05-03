"""Status Bar widget — keyboard hints, progress, metrics."""
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label, Static

from datetime import datetime


class StatusBar(Horizontal):
    """Bottom status bar with key hints and status info."""

    def compose(self) -> ComposeResult:
        yield Label("^Q Quit  ^T Tab  ^D Theme  F1 Help  ^P Cmd", id="footer-keys")
        yield Label("Ready", id="footer-status")

    def set_status(self, text: str) -> None:
        try:
            self.query_one("#footer-status", Label).update(text)
        except Exception:
            pass

    def update_time(self) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self.set_status(now)
