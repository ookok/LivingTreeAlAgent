"""Knowledge Base — AI-powered document management with Q&A and graph.

Compared to Tencent IMA: adds AI Q&A over docs, knowledge graph, dashboard.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button, DirectoryTree, Input, Label, RichLog, Static, TabbedContent, TabPane, TextArea, Tree,
)
from rich.syntax import Syntax
from rich.table import Table


EXT_TO_LANG = {".py":"python",".js":"javascript",".ts":"typescript",".json":"json",
               ".yaml":"yaml",".html":"html",".css":"css",".sql":"sql",".sh":"bash",
               ".rs":"rust",".go":"go"}


def _build_tree(root_node, path: Path, depth: int = 0) -> None:
    if depth >= 4:
        return
    try:
        for entry in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if entry.name.startswith(".") or "pycache" in entry.name: continue
            if entry.name.endswith((".pyc",".enc",".db",".log",".ico")): continue
            icon = "📁" if entry.is_dir() else "📄"
            child = root_node.add(f"{icon} {entry.name}", expand=False)
            child.data = {"path": str(entry), "is_dir": entry.is_dir()}
            if entry.is_dir(): _build_tree(child, entry, depth + 1)
    except PermissionError: pass


class KnowledgeScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "返回")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None
        self._workspace = Path.cwd()
        self._current_file: Optional[str] = None

    def set_hub(self, hub) -> None: self._hub = hub

    def compose(self) -> ComposeResult:
        yield Static("[dim]← 返回首页 (Esc)[/dim]", id="back-link")
        with Horizontal():
            with Vertical(id="kb-sidebar"):
                yield Input(placeholder="🔍 Search knowledge...", id="kb-search")
                yield Tree("📁 Workspace", id="kb-tree")
                with Horizontal():
                    yield Button("🔍 Search", variant="primary", id="kb-search-btn")
                    yield Button("📥 Import", variant="default", id="kb-import-btn")
                    yield Button("📊 Stats", variant="default", id="kb-stats-btn")
                    yield Button("🔄 Refresh", variant="default", id="kb-refresh-btn")
            with Vertical(id="kb-main"):
                with TabbedContent(id="kb-tabs"):
                    with TabPane("📄 Preview", id="preview-tab"):
                        yield RichLog(id="kb-preview", highlight=True, markup=True, wrap=True)
                    with TabPane("💬 AI Q&A", id="qa-tab"):
                        yield Vertical(
                            RichLog(id="kb-qa-output", highlight=True, markup=True, wrap=True),
                            Horizontal(
                                Input(placeholder="Ask about the current document...", id="kb-qa-input"),
                                Button("Ask AI", variant="primary", id="kb-ask-btn"),
                                id="kb-qa-row",
                            ),
                        )
                    with TabPane("🕸 Graph", id="graph-tab"):
                        yield RichLog(id="kb-graph", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        hub = getattr(self.app, '_hub', None)
        if hub and hasattr(self, 'set_hub'):
            self.set_hub(hub)
        ws = getattr(self.app, 'workspace', '.')
        self._workspace = Path(ws) if not isinstance(ws, Path) else ws
        self._populate_tree()
        preview = self.query_one("#kb-preview", RichLog)
        preview.write("[bold green]📚 Knowledge Base[/bold green]")
        preview.write("[dim]Click file → preview | Q&A tab → ask about docs | Graph → entity map[/dim]")

        qa_out = self.query_one("#kb-qa-output", RichLog)
        qa_out.write("[bold]💬 AI Document Q&A[/bold]")
        qa_out.write("[dim]Select a document, then ask questions about its content.[/dim]")

        graph = self.query_one("#kb-graph", RichLog)
        graph.write("[bold]🕸 Knowledge Graph[/bold]")
        graph.write("[dim]Entity relationships extracted from your documents.[/dim]")

    def _populate_tree(self) -> None:
        tree = self.query_one("#kb-tree", Tree)
        tree.clear()
        tree.root.set_label(f"📁 {self._workspace.name}")
        _build_tree(tree.root, self._workspace)

    @work(exclusive=False)
    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        if not node or not node.data or node.data.get("is_dir"): return
        path = node.data["path"]
        self._current_file = path
        preview = self.query_one("#kb-preview", RichLog)
        preview.clear()
        try:
            p = Path(path)
            content = p.read_text(encoding="utf-8", errors="replace")
            size = self._fsize(p.stat().st_size)
            ext = p.suffix.lower()
            preview.write(f"[bold]{p.name}[/bold] ([dim]{size}[/dim])")
            preview.write("─" * 40)
            if ext in EXT_TO_LANG:
                syntax = Syntax(content[:8000], EXT_TO_LANG.get(ext,"text"),
                                theme="monokai", line_numbers=True)
                preview.write(syntax)
            elif ext in (".md", ".markdown"):
                preview.write(content[:8000])
            else:
                preview.write(content[:5000])
        except Exception as e:
            preview.write(f"[red]{e}[/red]")

    @work(exclusive=False)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "kb-search-btn": await self._search_kb()
        elif bid == "kb-import-btn": await self._import_doc()
        elif bid == "kb-stats-btn": await self._show_stats()
        elif bid == "kb-refresh-btn": self._populate_tree()
        elif bid == "kb-ask-btn": await self._ask_ai()

    @on(Input.Submitted, "#kb-search")
    async def on_search_submit(self, event: Input.Submitted) -> None:
        if event.value.strip():
            await self._search_kb(event.value.strip())

    @on(Input.Submitted, "#kb-qa-input")
    async def on_qa_submit(self, event: Input.Submitted) -> None:
        if event.value.strip():
            await self._ask_ai(event.value.strip())

    async def _search_kb(self, query: str = "") -> None:
        preview = self.query_one("#kb-preview", RichLog)
        q = query or self.query_one("#kb-search", Input).value.strip()
        if not q:
            preview.write("[yellow]Enter search query[/yellow]")
            return
        if not self._hub:
            return
        preview.clear()
        preview.write(f"[bold]🔍 Search: '{q}'[/bold]")
        try:
            results = self._hub.world.knowledge_base.search(q, top_k=10)
            table = Table("Title", "Domain", "Preview", "Valid")
            for d in results:
                vf = d.valid_from.strftime("%Y-%m") if d.valid_from else "-"
                vt = d.valid_to.strftime("%Y-%m") if d.valid_to else "now"
                table.add_row(d.title[:30], d.domain or "-",
                              d.content[:60] + "...", f"{vf}~{vt}")
            self._render_rich(preview, table)
        except Exception as e:
            preview.write(f"[red]{e}[/red]")

    async def _import_doc(self) -> None:
        preview = self.query_one("#kb-preview", RichLog)
        if not self._current_file:
            preview.write("[yellow]Select a file to import[/yellow]")
            return
        path = Path(self._current_file)
        if not self._hub:
            return
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            from livingtree.knowledge.knowledge_base import Document
            doc = Document(title=path.name, content=content[:50000],
                          domain=path.suffix.lstrip("."), source="import")
            doc_id = self._hub.world.knowledge_base.add_knowledge(doc)
            preview.write(f"[green]✅ Imported: {path.name} → KB (id={doc_id[:8]})[/green]")
        except Exception as e:
            preview.write(f"[red]{e}[/red]")

    @work(exclusive=False)
    async def _show_stats(self) -> None:
        preview = self.query_one("#kb-preview", RichLog)
        preview.clear()
        if not self._hub:
            return
        preview.write("[bold]📊 Knowledge Stats[/bold]")
        try:
            kb = self._hub.world.knowledge_base
            docs = kb.history()
            current = kb.search("", top_k=100)
            expired = [d for d in docs if not d.is_valid_at()]
            preview.write(f"  Total documents: {len(docs)}")
            preview.write(f"  Currently valid: {len([d for d in docs if d.is_valid_at()])}")
            preview.write(f"  Expired: {len(expired)}")

            domains: dict[str, int] = {}
            for d in docs:
                domains[d.domain or "general"] = domains.get(d.domain or "general", 0) + 1
            preview.write(f"  Domains: {len(domains)}")
            for domain, count in sorted(domains.items(), key=lambda x: -x[1])[:10]:
                preview.write(f"    {domain}: {count} docs")

            # Show graph
            graph = self.query_one("#kb-graph", RichLog)
            graph.clear()
            graph.write("[bold]🕸 Knowledge Graph[/bold]")
            graph.write(f"[dim]{len(domains)} domains connected[/dim]")
            for d, c in sorted(domains.items(), key=lambda x: -x[1])[:8]:
                bar = "█" * min(20, c)
                graph.write(f"  {d:15s} {bar} {c}")
        except Exception as e:
            preview.write(f"[red]{e}[/red]")

    @work(exclusive=False)
    async def _ask_ai(self, question: str = "") -> None:
        qa_out = self.query_one("#kb-qa-output", RichLog)
        q = question or self.query_one("#kb-qa-input", Input).value.strip()
        if not q:
            qa_out.write("[yellow]Enter a question[/yellow]")
            return

        # Get document context
        context = ""
        if self._current_file:
            try:
                content = Path(self._current_file).read_text(encoding="utf-8", errors="replace")
                context = content[:5000]
                doc_name = Path(self._current_file).name
            except Exception:
                doc_name = "unknown"
        else:
            # Search KB for context
            if self._hub:
                try:
                    results = self._hub.world.knowledge_base.search(q, top_k=3)
                    context = "\n\n".join(d.content[:1000] for d in results)
                    doc_name = "knowledge base"
                except Exception:
                    doc_name = "general"

        qa_out.write(f"\n[bold green]❓ {q}[/bold green]")

        if not self._hub:
            qa_out.write("[red]Backend not available[/red]")
            return

        api_key = self._hub.config.model.deepseek_api_key
        if not api_key:
            qa_out.write("[yellow]API key not configured[/yellow]")
            return

        model = self._hub.config.model.flash_model
        base_url = self._hub.config.model.deepseek_base_url

        import aiohttp
        session = self._hub._session if self._hub else aiohttp.ClientSession()
        try:
            headers = {"Content-Type":"application/json","Authorization":f"Bearer {api_key}"}
            payload = {
                "model": model,
                "messages": [{"role":"system","content":f"Answer the question based on the document context. Be concise and accurate.\n\nDocument ({doc_name}):\n{context}"},
                             {"role":"user","content": q}],
                "temperature": 0.3, "max_tokens": 1024,
            }
            async with session.post(
                f"{base_url}/v1/chat/completions",
                headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                data = await resp.json()
                answer = data["choices"][0]["message"]["content"]
            qa_out.write(f"\n[bold #58a6ff]🤖 AI:[/bold #58a6ff] {answer}\n")
            self.query_one("#kb-qa-input", Input).clear()
        except Exception as e:
            qa_out.write(f"\n[red]Error: {e}[/red]")

    def _render_rich(self, widget: RichLog, renderable) -> None:
        widget.write(renderable)

    def _fsize(self, size: int) -> str:
        for unit in ("B","KB","MB","GB"):
            if size < 1024: return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    async def refresh(self, **kwargs) -> None:
        self._populate_tree()
