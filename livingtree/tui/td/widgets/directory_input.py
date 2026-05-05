from __future__ import annotations

from textual.widgets import Input

from livingtree.tui.td.directory_suggester import DirectorySuggester


class DirectoryInput(Input):
    def on_mount(self) -> None:
        self.suggester = DirectorySuggester()
