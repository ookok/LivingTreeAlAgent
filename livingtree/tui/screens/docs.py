"""Document Manager Screen — File tree browser + preview + AI analysis.

Features:
- Hierarchical file tree browser
- File preview (text, markdown, code)
- AI document analysis (summary, keywords)
- Knowledge base integration
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Input, Label, RichLog, Static, Tree,
)
from textual.widgets._tree import TreeNode

from rich.text import Text as RichText
from rich.syntax import Syntax


def _build_file_tree(tree: Tree[dict], path: Path, node: Optional[TreeNode] = None,
                     max_depth: int = 3, current_depth: int = 0) -> None:
    """Recursively build a file tree."""
    if current_depth >= max_depth:
        return

    try:
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        for entry in entries:
            if entry.name.startswith(".") or entry.name.startswith("__pycache__"):
                continue
            if entry.name.endswith((".pyc", ".enc", ".db", ".log")):
                continue

            is_dir = entry.is_dir()
            icon = "" if is_dir else ""
            label = f"{icon} {entry.name}"
            child = tree.root.add(label, expand=False) if node is None else node.add(label, expand=False)
            child.data = {"path": str(entry), "is_dir": is_dir}
            if is_dir:
                _build_file_tree(tree, entry, child, max_depth, current_depth + 1)
    except PermissionError:
        pass


class DocsScreen(Screen):
    """Document manager with file tree and preview."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None
        self._workspace = Path.cwd()
        self._current_file: Optional[str] = None

    def set_hub(self, hub) -> None:
        self._hub = hub

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Vertical(
                Input(placeholder="Search files...", id="doc-search"),
                Tree("Workspace", id="file-tree"),
                Horizontal(
                    Button("Refresh", variant="default", id="doc-refresh"),
                    Button("Analyze", variant="primary", id="doc-analyze"),
                ),
                id="file-tree-panel",
            ),
            Vertical(
                RichLog(id="doc-preview", highlight=True, markup=True, wrap=True),
                id="doc-preview-panel",
            ),
        )

    def on_mount(self) -> None:
        self._workspace = self.app.workspace if hasattr(self.app, 'workspace') else Path.cwd()
        self._populate_tree()
        preview = self.query_one("#doc-preview", RichLog)
        preview.write("[bold green]Document Manager[/bold green]")
        preview.write("[dim]Select a file from the tree to preview. Use 'Analyze' for AI document analysis.[/dim]")

    def _populate_tree(self) -> None:
        tree = self.query_one("#file-tree", Tree)
        tree.clear()
        tree.root.set_label(str(self._workspace.name))
        _build_file_tree(tree, self._workspace, max_depth=4)

    @work(exclusive=False)
    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        if not node or not node.data:
            return

        data = node.data
        filepath = data.get("path", "")
        is_dir = data.get("is_dir", False)

        if is_dir:
            return

        preview = self.query_one("#doc-preview", RichLog)
        preview.clear()

        path = Path(filepath)
        if not path.exists():
            preview.write(f"[red]File not found: {filepath}[/red]")
            return

        self._current_file = filepath

        size_str = self._format_size(path.stat().st_size)
        preview.write(f"[bold]File:[/bold] {path.name} ([dim]{size_str}[/dim])")
        preview.write("─" * 40)

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            ext = path.suffix.lower()

            if ext in (".md", ".markdown"):
                preview.write(content)
            elif ext in (".py", ".js", ".ts", ".json", ".yaml", ".yml", ".html", ".css", ".sql", ".sh", ".rs", ".go"):
                lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript",
                            ".json": "json", ".yaml": "yaml", ".yml": "yaml",
                            ".html": "html", ".css": "css", ".sql": "sql",
                            ".sh": "bash", ".rs": "rust", ".go": "go"}
                lang = lang_map.get(ext, "")
                if lang:
                    syntax = Syntax(content, lang, theme="monokai", line_numbers=True)
                    preview.write(syntax)
                else:
                    preview.write(content[:5000])
            else:
                preview.write(content[:5000])
                if len(content) > 5000:
                    preview.write(f"\n[dim]... ({len(content) - 5000} more characters)[/dim]")

        except UnicodeDecodeError:
            preview.write(f"[yellow]Binary file — {size_str}[/yellow]")
        except Exception as e:
            preview.write(f"[red]Error reading file: {e}[/red]")

    @work(exclusive=False)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "doc-refresh":
            self._populate_tree()
        elif event.button.id == "doc-analyze":
            await self._analyze_document()

    async def _analyze_document(self) -> None:
        """Analyze current file using AI."""
        preview = self.query_one("#doc-preview", RichLog)

        if not self._current_file:
            preview.write("[yellow]Select a file first[/yellow]")
            return

        path = Path(self._current_file)
        preview.write("\n[bold #58a6ff]Analyzing document...[/bold #58a6ff]")

        if self._hub and hasattr(self._hub, 'config'):
            api_key = self._hub.config.model.deepseek_api_key
            if api_key:
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")[:3000]
                    import aiohttp, json

                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    }
                    payload = {
                        "model": "deepseek-v4-flash",
                        "messages": [
                            {"role": "system", "content": "Analyze the document. Return: summary (1-2 lines), keywords (5-10 comma-separated), type (document type). Format as plain text."},
                            {"role": "user", "content": f"Analyze: {path.name}\n\n{content}"},
                        ],
                        "temperature": 0.2,
                        "max_tokens": 512,
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{self._hub.config.model.deepseek_base_url}/v1/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=30),
                        ) as resp:
                            data = await resp.json()
                            analysis = data["choices"][0]["message"]["content"]

                    preview.write(f"[bold green]AI Analysis:[/bold green]\n{analysis}")
                    return
                except Exception as e:
                    preview.write(f"[red]Analysis error: {e}[/red]")
                    return

        # Heuristic analysis
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        ext = path.suffix.lower()
        preview.write(f"\n[bold green]Heuristic Analysis:[/bold green]")
        preview.write(f"  Type: {ext} file")
        preview.write(f"  Lines: {len(lines)}")
        preview.write(f"  Size: {self._format_size(len(content.encode()))}")
        preview.write(f"  First line: {lines[0][:80] if lines else '(empty)'}")

    def _format_size(self, size: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    async def refresh(self) -> None:
        self._populate_tree()
