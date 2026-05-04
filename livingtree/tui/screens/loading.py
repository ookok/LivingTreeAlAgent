"""LoadingScreen — Full-screen startup splash shown during backend init."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen

from ..widgets.loading_splash import LoadingSplash


class LoadingScreen(Screen):
    """Screen overlay with animated loading splash."""

    def compose(self) -> ComposeResult:
        yield LoadingSplash(id="loading-splash")
