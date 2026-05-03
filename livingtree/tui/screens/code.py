"""Code Editor — Deep-integrated with CodeGraph.

Built-in tools: blast_radius, callers, callees, hubs, code_search, AST parse.
Ctrl+P to access, or use toolbar buttons.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, RichLog, Select, TextArea


LANGUAGES = [
    ("python", "Python"), ("javascript", "JavaScript"), ("typescript", "TypeScript"),
    ("html", "HTML"), ("css", "CSS"), ("json", "JSON"), ("yaml", "YAML"),
    ("markdown", "Markdown"), ("sql", "SQL"), ("bash", "Bash"),
    ("rust", "Rust"), ("go", "Go"), ("java", "Java"), ("cpp", "C++"),
]


class CodeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None
        self._current_file: Optional[Path] = None
        self._language = "python"

    def set_hub(self, hub) -> None:
        self._hub = hub

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                Select([(l, n) for l, n in LANGUAGES], prompt="Lang", value="python", id="lang-select"),
                Input(placeholder="File path or symbol name...", id="code-query"),
                Button("Open", variant="default", id="open-btn"),
                Button("Save", variant="default", id="save-btn"),
                Button("AI Gen", variant="primary", id="ai-gen-btn"),
                Button("▼ Run", variant="primary", id="run-btn"),
                id="code-toolbar",
            ),
            Horizontal(
                Button("Callers", variant="default", id="callers-btn"),
                Button("Callees", variant="default", id="callees-btn"),
                Button("Blast", variant="default", id="blast-btn"),
                Button("Hubs", variant="default", id="hubs-btn"),
                Button("AST", variant="default", id="ast-btn"),
                Button("Index", variant="default", id="index-btn"),
                id="graph-toolbar",
            ),
            TextArea.code_editor("", language="python", id="code-editor",
                                 show_line_numbers=True, tab_behavior="focus"),
            RichLog(id="code-output", highlight=True, markup=True, wrap=True),
        )

    def on_mount(self) -> None:
        output = self.query_one("#code-output", RichLog)
        output.write("[bold green]Code Graph Ready[/bold green]")
        output.write("[dim]Open a file or use Ctrl+P for tools[/dim]")

    @work(exclusive=False)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id
        output = self.query_one("#code-output", RichLog)
        editor = self.query_one("#code-editor", TextArea)
        methods = {
            "ai-gen-btn": self._ai_gen,
            "run-btn": self._run,
            "save-btn": self._save,
            "open-btn": self._open,
            "callers-btn": self.cmd_find_callers,
            "callees-btn": self.cmd_find_callees,
            "blast-btn": self.cmd_blast_radius,
            "hubs-btn": self.cmd_find_hubs,
            "ast-btn": self.cmd_parse_ast,
            "index-btn": self.cmd_index_codebase,
        }
        fn = methods.get(btn)
        if fn:
            await fn() if asyncio.iscoroutinefunction(fn) else fn()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "lang-select" and event.value:
            self._language = str(event.value)
            try:
                self.query_one("#code-editor", TextArea).language = self._language
            except Exception:
                pass

    # ── Integrated tools ──

    async def cmd_generate_code(self) -> None:
        await self._ai_gen()

    async def cmd_improve_code(self) -> None:
        editor = self.query_one("#code-editor", TextArea)
        output = self.query_one("#code-output", RichLog)
        output.clear()
        output.write("[bold #58a6ff]AI improving code...[/bold #58a6ff]")
        if self._hub and self._hub.world.code_engine:
            result = await self._hub.world.code_engine.improve_code(editor.text, {})
            editor.text = result.code
            output.write(f"[green]Improved: {result.annotations}[/green]")

    async def cmd_blast_radius(self) -> None:
        output = self.query_one("#code-output", RichLog)
        output.clear()
        if not self._current_file:
            output.write("[yellow]Open a file first to analyze impact[/yellow]")
            return
        if not self._hub or not self._hub.world.code_graph:
            output.write("[yellow]Index codebase first (press Index button or use index_codebase)[/yellow]")
            return

        results = self._hub.world.code_graph.blast_radius([str(self._current_file)])
        output.write(f"[bold]Blast Radius: {str(self._current_file)}[/bold]")
        for r in results:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(r.risk, "⚪")
            output.write(f"  {icon} [{r.risk}] {r.file} — {r.reason}")

    async def cmd_find_callers(self) -> None:
        output = self.query_one("#code-output", RichLog)
        output.clear()
        name = self._get_selected_name()
        if not name:
            output.write("[yellow]Select a function name or enter in query field[/yellow]")
            return
        cg = self._hub.world.code_graph if self._hub else None
        if not cg:
            output.write("[yellow]Index codebase first[/yellow]")
            return
        callers = cg.get_callers(name)
        output.write(f"[bold]Callers of '{name}': {len(callers)}[/bold]")
        for c in callers[:20]:
            output.write(f"  {c.name} ({c.file}:{c.line})")

    async def cmd_find_callees(self) -> None:
        output = self.query_one("#code-output", RichLog)
        output.clear()
        name = self._get_selected_name()
        if not name:
            output.write("[yellow]Select a function name[/yellow]")
            return
        cg = self._hub.world.code_graph if self._hub else None
        if not cg:
            output.write("[yellow]Index codebase first[/yellow]")
            return
        callees = cg.get_callees(name)
        output.write(f"[bold]'{name}' calls: {len(callees)}[/bold]")
        for c in callees[:20]:
            output.write(f"  {c}")

    async def cmd_find_hubs(self) -> None:
        output = self.query_one("#code-output", RichLog)
        output.clear()
        cg = self._hub.world.code_graph if self._hub else None
        if not cg:
            output.write("[yellow]Index codebase first[/yellow]")
            return
        hubs = cg.find_hubs(10)
        output.write("[bold]Architectural Hubs[/bold]")
        for h in hubs:
            conns = len(h.dependents) + len(h.dependencies)
            output.write(f"  {h.name} ({h.file}) — {conns} connections")

    async def cmd_search_code(self) -> None:
        output = self.query_one("#code-output", RichLog)
        output.clear()
        query = self.query_one("#code-query", Input).value.strip()
        if not query:
            output.write("[yellow]Enter a search query[/yellow]")
            return
        cg = self._hub.world.code_graph if self._hub else None
        if not cg:
            output.write("[yellow]Index codebase first[/yellow]")
            return
        results = cg.search(query)
        output.write(f"[bold]Search: '{query}' — {len(results)} results[/bold]")
        for e in results[:20]:
            output.write(f"  [{e.kind}] {e.name} ({e.file}:{e.line})")

    async def cmd_parse_ast(self) -> None:
        output = self.query_one("#code-output", RichLog)
        output.clear()
        editor = self.query_one("#code-editor", TextArea)
        code = editor.text
        if not code.strip():
            output.write("[yellow]No code to parse[/yellow]")
            return
        if self._hub and self._hub.world.ast_parser:
            nodes, edges = self._hub.world.ast_parser.parse_source(code, self._language)
            funcs = [n for n in nodes if n.kind == "function"]
            classes = [n for n in nodes if n.kind == "class"]
            imports = [n for n in nodes if n.kind == "import"]
            output.write(f"[bold]AST: {len(nodes)} nodes, {len(edges)} edges[/bold]")
            output.write(f"  Functions: {len(funcs)}  Classes: {len(classes)}  Imports: {len(imports)}")
            for f in funcs[:10]:
                output.write(f"  fn: {f.name} (L{f.line})")

    async def cmd_index_codebase(self) -> None:
        output = self.query_one("#code-output", RichLog)
        output.clear()
        output.write("[bold]Indexing codebase...[/bold]")
        if self._hub:
            stats = self._hub.world.code_graph.index(".")
            self._hub.world.code_graph.save()
            output.write(f"[green]Indexed: {stats.total_entities} entities in {stats.total_files} files ({stats.build_time_ms:.0f}ms)[/green]")
            output.write(f"  Languages: {stats.languages}")
            output.write(f"  Edges: {stats.total_edges}")

    # ── Core operations ──

    async def _ai_gen(self) -> None:
        editor = self.query_one("#code-editor", TextArea)
        output = self.query_one("#code-output", RichLog)
        output.clear()
        output.write("[bold #58a6ff]AI generating code...[/bold #58a6ff]")
        if self._hub:
            r = await self._hub.generate_code(
                self._current_file.stem if self._current_file else "module",
                editor.selected_text or editor.text or "utility function",
                self._language,
            )
            if r.get("code"):
                editor.text = r["code"]
                editor.language = self._language
                output.write(f"[green]Generated: {r.get('annotations', '')}[/green]")
                return
        editor.text = self._template()
        editor.language = self._language
        output.write("[green]Template generated[/green]")

    async def _run(self) -> None:
        editor = self.query_one("#code-editor", TextArea)
        output = self.query_one("#code-output", RichLog)
        code = editor.text
        if not code.strip() or self._language != "python":
            output.write("[yellow]Python only[/yellow]")
            return
        output.clear()
        output.write("[bold]Running...[/bold]")
        try:
            proc = await asyncio.create_subprocess_exec("python", "-c", code,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if stdout:
                output.write(f"[green]{stdout.decode('utf-8', errors='replace')}[/green]")
            if stderr:
                output.write(f"[red]{stderr.decode('utf-8', errors='replace')}[/red]")
        except asyncio.TimeoutError:
            output.write("[red]Timeout (30s)[/red]")
        except Exception as e:
            output.write(f"[red]{e}[/red]")

    async def _save(self) -> None:
        editor = self.query_one("#code-editor", TextArea)
        output = self.query_one("#code-output", RichLog)
        path = self.query_one("#code-query", Input).value or str(self._current_file or "untitled.py")
        try:
            Path(path).write_text(editor.text, encoding="utf-8")
            self._current_file = Path(path)
            output.write(f"[green]Saved: {path}[/green]")
        except Exception as e:
            output.write(f"[red]{e}[/red]")

    async def _open(self) -> None:
        editor = self.query_one("#code-editor", TextArea)
        output = self.query_one("#code-output", RichLog)
        path = self.query_one("#code-query", Input).value.strip()
        if not path:
            output.write("[yellow]Enter file path[/yellow]")
            return
        try:
            content = Path(path).read_text(encoding="utf-8")
            editor.text = content
            self._current_file = Path(path)
            ext_map = {".py": "python", ".js": "javascript", ".ts": "typescript", ".html": "html",
                       ".css": "css", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
                       ".md": "markdown", ".sql": "sql", ".sh": "bash", ".rs": "rust",
                       ".go": "go", ".java": "java"}
            self._language = ext_map.get(Path(path).suffix.lower(), "python")
            editor.language = self._language
            try:
                self.query_one("#lang-select", Select).value = self._language
            except Exception:
                pass
            output.write(f"[green]Loaded: {path} ({len(content)} chars)[/green]")
        except Exception as e:
            output.write(f"[red]{e}[/red]")

    def _get_selected_name(self) -> str:
        editor = self.query_one("#code-editor", TextArea)
        query = self.query_one("#code-query", Input).value.strip()
        if query:
            return query
        sel = editor.selected_text
        if sel:
            m = re.search(r'(?:def|class|fn|func|function)\s+(\w+)', sel)
            if m:
                return m.group(1)
        return Path(self._current_file).stem if self._current_file else ""

    def _template(self) -> str:
        return {
            "python": '"""LivingTree AI-generated module."""\n\nfrom typing import Any\n\n\ndef process(data: Any) -> dict:\n    """Process input and return result."""\n    return {"status": "ok", "input": str(data)}\n\n\nif __name__ == "__main__":\n    print(process("Hello"))\n',
            "javascript": '// LivingTree AI-generated module\n\nfunction process(data) {\n    return { status: "ok", input: String(data) };\n}\n\nconsole.log(process("Hello"));\n',
        }.get(self._language, f"# {self._language} code\n\nprint('Hello LivingTree!')\n")

    async def refresh(self) -> None:
        pass
