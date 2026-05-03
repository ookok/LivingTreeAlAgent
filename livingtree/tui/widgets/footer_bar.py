"""Status Bar — keyboard hints, progress, system info, contact."""
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label


class StatusBar(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label("^Q Quit  ^1-4 Tabs  ^P Cmd  ^D Theme", id="footer-keys")
        yield Label("www.livingtree-ai.com  |  livingtreeai@163.com", id="footer-contact")
        yield Label("Ready", id="footer-status")

    def set_status(self, text: str) -> None:
        try:
            self.query_one("#footer-status", Label).update(text)
        except Exception:
            pass
