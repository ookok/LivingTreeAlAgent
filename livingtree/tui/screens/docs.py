"""Document Manager — Deep-integrated with KnowledgeBase + CodeGraph.

Built-in tools: search_knowledge, discover_formats, detect_gaps, index_codebase.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button, Input, RichLog, Static, Tree,
)
from textual.widgets._tree import TreeNode
from rich.syntax import Syntax


def _build_tree(tree_root: TreeNode, path: Path, depth: int = 0) -> None:
    if depth >= 4:
        return
    try:
        for entry in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if entry.name.startswith(".") or entry.name.startswith("__pycache__"):
                continue
            if entry.name.endswith((".pyc", ".enc", ".db", ".log")):
                continue
            icon = "" if entry.is_dir() else ""
            child = tree_root.add(f"{icon} {entry.name}", expand=False)
            child.data = {"path": str(entry), "is_dir": entry.is_dir()}
            if entry.is_dir():
                _build_tree(child, entry, depth + 1)
    except PermissionError:
        pass


class DocsScreen(Screen):
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
                Input(placeholder="Search knowledge or files...", id="doc-search"),
                Tree("Workspace", id="file-tree"),
                Horizontal(
                    Button("Search KB", variant="primary", id="kb-btn"),
                    Button("Formats", variant="default", id="fmt-btn"),
                    Button("Gaps", variant="default", id="gap-btn"),
                    Button("Index", variant="default", id="index-code-btn"),
                    Button("Refresh", variant="default", id="refresh-btn"),
                ),
                id="file-tree-panel",
            ),
            Vertical(
                RichLog(id="doc-preview", highlight=True, markup=True, wrap=True),
                Horizontal(
                    Button("Save As", variant="primary", id="saveas-btn"),
                    Button("Analyze", variant="default", id="analyze-btn"),
                    id="doc-actions",
                ),
                id="doc-preview-panel",
            ),
        )

    def on_mount(self) -> None:
        self._workspace = self.app.workspace if hasattr(self.app, 'workspace') else Path.cwd()
        self._populate_tree()
        preview = self.query_one("#doc-preview", RichLog)
        preview.write("[bold green]Knowledge Explorer[/bold green]")
        preview.write("[dim]Search the knowledge base or browse files[/dim]")

    def _populate_tree(self) -> None:
        tree = self.query_one("#file-tree", Tree)
        tree.clear()
        tree.root.set_label(str(self._workspace.name))
        _build_tree(tree.root, self._workspace)

    @work(exclusive=False)
    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        if not node or not node.data or node.data.get("is_dir"):
            return
        path = node.data["path"]
        self._current_file = path
        preview = self.query_one("#doc-preview", RichLog)
        preview.clear()
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            size = self._fsize(Path(path).stat().st_size)
            ext = Path(path).suffix.lower()
            preview.write(f"[bold]{Path(path).name}[/bold] ([dim]{size}[/dim])")
            preview.write("─" * 40)
            if ext in (".py", ".js", ".ts", ".json", ".yaml", ".yml", ".html", ".css", ".sql", ".sh", ".rs", ".go"):
                lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript",
                            ".json": "json", ".yaml": "yaml", ".html": "html", ".css": "css",
                            ".sql": "sql", ".sh": "bash", ".rs": "rust", ".go": "go"}
                syntax = Syntax(content[:5000], lang_map.get(ext, "text"), theme="monokai", line_numbers=True)
                preview.write(syntax)
            else:
                preview.write(content[:5000])
        except Exception as e:
            preview.write(f"[red]{e}[/red]")

    @work(exclusive=False)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id
        methods = {
            "kb-btn": self.cmd_search_knowledge,
            "fmt-btn": self.cmd_discover_formats,
            "gap-btn": self.cmd_detect_gaps,
            "index-code-btn": self.cmd_index_codebase,
            "refresh-btn": self._refresh,
            "saveas-btn": self._save_as,
            "analyze-btn": self._analyze_doc,
        }
        fn = methods.get(btn)
        if fn:
            await fn() if asyncio.iscoroutinefunction(fn) else fn()

    # ── Integrated tools ──

    async def cmd_search_knowledge(self) -> None:
        preview = self.query_one("#doc-preview", RichLog)
        query = self.query_one("#doc-search", Input).value.strip()
        if not query:
            preview.write("[yellow]Enter search query[/yellow]")
            return
        if not self._hub:
            return
        preview.clear()
        preview.write(f"[bold]Knowledge Search: '{query}'[/bold]")
        try:
            results = self._hub.world.knowledge_base.search(query)
            for d in results[:10]:
                preview.write(f"[bold]{d.title}[/bold]\n  {d.content[:200]}...\n")
            if not results:
                preview.write("[dim]No results[/dim]")
        except Exception as e:
            preview.write(f"[red]{e}[/red]")

    async def cmd_discover_formats(self) -> None:
        preview = self.query_one("#doc-preview", RichLog)
        if not self._current_file:
            preview.write("[yellow]Select a file first[/yellow]")
            return
        preview.clear()
        preview.write(f"[bold]Format: {Path(self._current_file).name}[/bold]")
        if self._hub:
            try:
                t = self._hub.world.format_discovery.analyze_document(self._current_file)
                preview.write(f"  Formats: {t.formats}")
                preview.write(f"  Structure: {t.structure}")
            except Exception as e:
                preview.write(f"[red]{e}[/red]")

    async def cmd_detect_gaps(self) -> None:
        preview = self.query_one("#doc-preview", RichLog)
        if not self._hub:
            return
        preview.clear()
        preview.write("[bold]Knowledge Gaps[/bold]")
        try:
            plan = self._hub.world.gap_detector.generate_learning_plan(self._hub.world.knowledge_base)
            for g in plan[:15]:
                preview.write(f"  [{g.priority}] {g.domain}/{g.topic}")
        except Exception as e:
            preview.write(f"[red]{e}[/red]")

    async def cmd_index_codebase(self) -> None:
        preview = self.query_one("#doc-preview", RichLog)
        preview.clear()
        preview.write("[bold]Indexing codebase...[/bold]")
        if self._hub:
            stats = self._hub.world.code_graph.index(".")
            self._hub.world.code_graph.save()
            preview.write(f"[green]Indexed: {stats.total_entities} entities in {stats.total_files} files ({stats.build_time_ms:.0f}ms)[/green]")
            preview.write(f"  Languages: {stats.languages}")

    def _refresh(self) -> None:
        self._populate_tree()

    async def _save_as(self) -> None:
        """Save the currently viewed file to a new location."""
        preview = self.query_one("#doc-preview", RichLog)
        if not self._current_file:
            preview.write("[yellow]Select a file first[/yellow]")
            return
        src = Path(self._current_file)
        default_dest = str(Path.home() / "Downloads" / src.name)
        dest = input(f"Save as [{default_dest}]: ") or default_dest
        try:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            preview.write(f"[green]Saved: {dest}[/green]")
            self.notify(f"Saved {src.name}", timeout=2)
        except Exception as e:
            preview.write(f"[red]Save error: {e}[/red]")

    async def _analyze_doc(self) -> None:
        """AI analysis of current document."""
        preview = self.query_one("#doc-preview", RichLog)
        if not self._current_file:
            preview.write("[yellow]Select a file first[/yellow]")
            return
        path = Path(self._current_file)
        preview.write(f"\n[bold blue]Analyzing {path.name}...[/bold blue]")
        if self._hub and hasattr(self._hub, "config"):
            api_key = self._hub.config.model.deepseek_api_key
            if api_key:
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")[:2000]
                    import aiohttp, json
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{self._hub.config.model.deepseek_base_url}/v1/chat/completions",
                            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                            json={
                                "model": "deepseek-v4-flash",
                                "messages": [{"role": "system", "content": "Analyze document: summary, type, keywords, quality."},
                                              {"role": "user", "content": f"{path.name}:\n{content}"}],
                                "temperature": 0.2, "max_tokens": 512,
                            },
                            timeout=aiohttp.ClientTimeout(total=30),
                        ) as resp:
                            data = await resp.json()
                            analysis = data["choices"][0]["message"]["content"]
                    preview.write(f"\n[green]Analysis:[/green]\n{analysis}")
                    return
                except Exception as e:
                    preview.write(f"\n[red]{e}[/red]")
                    return
        preview.write(f"\n[yellow]API key not configured[/yellow]")

    def _fsize(self, size: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    async def refresh(self) -> None:
        self._populate_tree()
