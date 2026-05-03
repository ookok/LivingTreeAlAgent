"""MarkdownViewer — Rich Markdown rendering widget for Textual."""

from __future__ import annotations

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual.widgets import Static


class MarkdownViewer(Static):
    """Renders Markdown content using Rich's Markdown renderer.

    Supports: headers, lists, code blocks, tables, links, images, bold, italic.
    """

    def __init__(self, markdown: str = "", **kwargs):
        super().__init__(**kwargs)
        self._markdown = markdown

    def on_mount(self) -> None:
        if self._markdown:
            self.update(self._render(self._markdown))

    def render_markdown(self, content: str) -> None:
        """Update with new markdown content."""
        self.update(self._render(content))

    def append_markdown(self, content: str) -> None:
        """Append markdown to existing content."""
        self._markdown = self._markdown + "\n\n" + content if self._markdown else content
        self.update(self._render(self._markdown))

    def _render(self, content: str) -> Markdown:
        return Markdown(
            content,
            code_theme="monokai",
            inline_code_theme="monokai",
        )


class MarkdownPanel(Static):
    """A markdown viewer wrapped in a Rich Panel for visual separation."""

    def __init__(self, markdown: str = "", title: str = "", **kwargs):
        super().__init__(**kwargs)
        self._md = Markdown(markdown) if markdown else Markdown("")
        self._title = title

    def render(self) -> Panel:
        return Panel(self._md, title=self._title, border_style="blue")

    def update_content(self, markdown: str, title: str = "") -> None:
        self._md = Markdown(markdown)
        self._title = title or self._title
        self.refresh()
