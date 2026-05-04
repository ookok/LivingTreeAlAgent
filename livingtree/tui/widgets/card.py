"""Card — pure render component. Screen name stored as data attribute.
   
Browser-DOM principle: separation of structure (this widget), 
style (CSS), and behavior (App-level event delegation).
"""
from __future__ import annotations

from textual.widget import Widget


class Card(Widget):
    """Display-only module card. App handles all interaction."""

    can_focus = True

    DEFAULT_CSS = """
    Card {
        width: 1fr;
        height: 7;
        border: solid $primary;
        content-align: center middle;
        padding: 1 2;
        margin: 1 1;
    }
    Card:focus {
        border: solid $accent;
        background: $primary 10%;
    }
    Card:hover {
        border: solid $accent;
        background: $primary 5%;
    }
    """

    def __init__(self, label: str, screen_name: str):
        super().__init__()
        self.screen_name = screen_name
        self._label = label

    def render(self) -> str:
        return self._label
