"""ChatScreen — Toad-styled chat using NeonConversation + sidebar."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen

from ..widgets.neon_conversation import NeonConversation, NeonPrompt
from ..widgets.footer_bar import StatusBar


class ChatScreen(Screen):
    BINDINGS = [
        ("escape", "app.pop_screen", "返回"),
    ]

    def compose(self) -> ComposeResult:
        yield NeonConversation(
            id="neon-conversation",
            classes="Conversation -column",
        )
        yield StatusBar()

    def on_mount(self) -> None:
        conv = self.query_one("#neon-conversation", NeonConversation)
        if self.app.hub:
            conv.set_hub(self.app.hub)

    def on_screen_resume(self) -> None:
        try:
            self.query_one(NeonPrompt).focus_input()
        except Exception:
            pass
