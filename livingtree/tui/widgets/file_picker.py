"""File picker dialog for uploading files and images."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, Static


class FilePicker(ModalScreen):
    """Modal file picker with directory tree navigation.

    Usage:
        app.push_screen(FilePicker("/path"), callback=handle_file)
    """

    def __init__(self, start_path: str = ".", callback: Optional[Callable] = None,
                 title: str = "Select File", **kwargs):
        super().__init__(**kwargs)
        self._start = str(Path(start_path).absolute())
        self._callback = callback
        self._title = title
        self._selected: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(f"[bold]{self._title}[/bold]", id="picker-title"),
            Input(placeholder="Filter by name or extension...", id="picker-filter"),
            DirectoryTree(self._start, id="picker-tree"),
            Horizontal(
                Label("", id="picker-selected"),
                Button("Open", variant="primary", id="picker-open"),
                Button("Cancel", variant="default", id="picker-cancel"),
                id="picker-buttons",
            ),
        )

    def on_mount(self) -> None:
        self.query_one(DirectoryTree).focus()

    @on(DirectoryTree.FileSelected)
    def on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self._selected = str(event.path)
        self.query_one("#picker-selected", Label).update(f"[green]{Path(event.path).name}[/green]")

    @on(Input.Changed, "#picker-filter")
    def on_filter(self, event: Input.Changed) -> None:
        query = event.value.lower()
        tree = self.query_one(DirectoryTree)
        tree.clear()
        tree.path = self._start
        if query:
            try:
                tree.load_directory(Path(self._start))
            except Exception:
                pass

    @on(Button.Pressed, "#picker-open")
    def on_open(self) -> None:
        if self._selected and self._callback:
            try:
                self._callback(self._selected)
            except Exception:
                pass
        self.dismiss()

    @on(Button.Pressed, "#picker-cancel")
    def on_cancel(self) -> None:
        self.dismiss()
