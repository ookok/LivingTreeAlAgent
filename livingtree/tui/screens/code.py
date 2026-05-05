"""Code Editor — file tree, multi-tab, search, diff, opencode LSP, AI tools."""
from __future__ import annotations

import asyncio, json, os, shutil, subprocess
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DirectoryTree, Input, Label, RichLog, Static, TabbedContent, TabPane, TextArea, Collapsible

from ...config.system_config import EXT_TO_LANG, LANG_DISPLAY_NAMES as LANGUAGES
from ..widgets.coding_agent_panel import CodingAgentPanel, AgentRunRequest


class CodeScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "返回")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None
        self._files: dict[str, dict] = {}
        self._active_file: Optional[str] = None
        self._recent_path = Path("./data/recent_files.json")
        self._recent_path.parent.mkdir(parents=True, exist_ok=True)
        self._workspace = "."
        self._lsp_bridge = None

    def set_hub(self, hub) -> None:
        self._hub = hub

    def compose(self) -> ComposeResult:
        yield Static("[dim]← 返回首页 (Esc)[/dim]", id="back-link")
        yield Horizontal(
            Vertical(
                Input(placeholder="Search files (Ctrl+F)", id="code-search"),
                DirectoryTree(".", id="code-tree"),
                Label("", id="code-file-info"),
                id="code-sidebar",
            ),
            Vertical(
                Horizontal(
                    Button("New", variant="default", id="new-btn"),
                    Button("Save", variant="default", id="save-btn"),
                    Button("Diff", variant="default", id="diff-btn"),
                    Button("AI Gen", variant="primary", id="ai-gen-btn"),
                    Button("Run", variant="primary", id="run-btn"),
                    Button("Goto", variant="default", id="goto-btn"),
                    id="code-toolbar",
                ),
                TabbedContent(id="code-tabs"),
                RichLog(id="code-output", highlight=True, markup=True, wrap=True),
                id="code-main",
            ),
            Vertical(
                CodingAgentPanel(id="agent-panel"),
                id="code-agent-sidebar",
            ),
        )

    def on_mount(self) -> None:
        hub = getattr(self.app, '_hub', None)
        if hub and hasattr(self, 'set_hub'):
            self.set_hub(hub)
        self._workspace = getattr(self.app, 'workspace', '.')
        self._workspace = str(self._workspace) if not isinstance(self._workspace, str) else self._workspace

        try:
            from .widgets.opencode_lsp import OpenCodeLSPBridge
            self._lsp_bridge = OpenCodeLSPBridge()
        except Exception:
            pass

        output = self.query_one("#code-output", RichLog)
        output.write("[#58a6ff]# Code Editor[/#58a6ff]")
        output.write("")
        output.write("[bold]Features[/bold]")
        output.write("  File tree → click to open")
        output.write("  Multi-tab editing")
        output.write("  [bold]Diff[/bold] — Git vs HEAD")
        output.write("  [bold]AI Gen[/bold] — Generate code")
        output.write("  [bold]Run[/bold] — Python run")
        output.write("  [bold #58a6ff]OpenCode[/bold #58a6ff] — AI dev env (TUI)")
        output.write("  [bold #3fb950]Serve[/bold #3fb950] — Auto-start opencode API")
        output.write("")
        if not shutil.which("opencode"):
            output.write("[dim]First use: auto-downloads Node.js + opencode locally[/dim]")
            output.write("")
        output.write("[bold]Shortcuts[/bold]")
        output.write("  Ctrl+F search  |  Ctrl+H replace  |  Ctrl+G goto")
        output.write("")
        self._load_recent()

    @on(DirectoryTree.FileSelected, "#code-tree")
    def on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = str(event.path)
        if Path(path).is_dir():
            return
        ext = Path(path).suffix.lower()
        if ext not in EXT_TO_LANG and ext not in (".txt", ".cfg", ".ini", ".toml", ".env", ".csv", ".xml"):
            return
        self._open_file(path)
        self._run_lsp_diagnostics(path)

    @work(exclusive=False)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "save-btn":
            await self._save()
        elif bid == "diff-btn":
            await self._git_diff()
        elif bid == "ai-gen-btn":
            await self._ai_gen()
        elif bid == "run-btn":
            await self._run()
        elif bid == "new-btn":
            self._new_tab()
        elif bid == "goto-btn":
            self._goto_line()
        elif bid == "opencode-btn":
            await self._launch_opencode(serve=False)
        elif bid == "opencode-serve-btn":
            await self._launch_opencode(serve=True)

    async def _open_file(self, path: str) -> None:
        if path in self._files:
            self._activate_tab(path)
            return
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        ext = Path(path).suffix.lower()
        lang = EXT_TO_LANG.get(ext, "")
        tab_id = f"tab-{len(self._files)}"
        self._files[path] = {"text": content, "lang": lang, "tab_id": tab_id}
        tabs = self.query_one("#code-tabs", TabbedContent)
        pane = TabPane(Path(path).name, id=tab_id)
        pane.mount(TextArea(content, language=lang, id=f"editor-{tab_id}", show_line_numbers=True))
        tabs.add_pane(pane)
        tabs.active = tab_id
        self._active_file = path
        self._add_recent(path)
        self.query_one("#code-file-info", Label).update(f"[dim]{path} ({len(content)} chars)[/dim]")

    def _activate_tab(self, path: str) -> None:
        if path in self._files:
            self._active_file = path
            self.query_one("#code-tabs", TabbedContent).active = self._files[path]["tab_id"]

    @work(exclusive=False)
    async def _save(self) -> None:
        if not self._active_file:
            return
        tab_id = self._files[self._active_file]["tab_id"]
        try:
            editor = self.query_one(f"#editor-{tab_id}", TextArea)
            content = editor.text
            Path(self._active_file).write_text(content, encoding="utf-8")
            self._files[self._active_file]["text"] = content
            output = self.query_one("#code-output", RichLog)
            output.write(f"[#3fb950]Saved: {self._active_file}[/#3fb950]")
            self._run_lsp_diagnostics(self._active_file)
        except Exception as e:
            output = self.query_one("#code-output", RichLog)
            output.write(f"[#f85149]Save failed: {e}[/#f85149]")

    @work(exclusive=False)
    async def _git_diff(self) -> None:
        if not self._active_file:
            return
        output = self.query_one("#code-output", RichLog)
        output.clear()
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "diff", "HEAD", "--", self._active_file,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            diff_text = stdout.decode(errors="replace")
            if diff_text.strip():
                output.write(f"[bold]Diff: {self._active_file}[/bold]")
                output.write(diff_text[:2000])
            else:
                output.write("[dim]No changes from HEAD[/dim]")
        except Exception as e:
            output.write(f"[#f85149]Diff failed: {e}[/#f85149]")

    @work(exclusive=False)
    async def _ai_gen(self) -> None:
        output = self.query_one("#code-output", RichLog)
        output.clear()
        if not self._hub:
            output.write("[#d29922]Engine not ready[/#d29922]")
            return
        try:
            result = await self._hub.generate_code("module", "utility function", "python")
            code = result.get("code", "")
            if code:
                self._new_tab()
                tab_id = self._files.get(list(self._files.keys())[-1], {}).get("tab_id", "")
                if tab_id:
                    editor = self.query_one(f"#editor-{tab_id}", TextArea)
                    editor.text = code
                output.write("[#3fb950]Code generated[/#3fb950]")
            else:
                output.write("[dim]No code generated[/dim]")
        except Exception as e:
            output.write(f"[#f85149]AI Gen failed: {e}[/#f85149]")

    @work(exclusive=False)
    async def _run(self) -> None:
        output = self.query_one("#code-output", RichLog)
        output.clear()
        if not self._active_file:
            return
        path = self._active_file
        if not path.endswith(".py"):
            output.write("[dim]Only Python files can be run[/dim]")
            return
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            output.write(f"[bold]Run: {path}[/bold]")
            if stdout:
                output.write(stdout.decode(errors="replace")[:2000])
            if stderr:
                output.write(f"[#f85149]{stderr.decode(errors='replace')[:1000]}[/#f85149]")
            if proc.returncode == 0:
                output.write("[#3fb950]Exit: 0[/#3fb950]")
            else:
                output.write(f"[#f85149]Exit: {proc.returncode}[/#f85149]")
        except Exception as e:
            output.write(f"[#f85149]Run failed: {e}[/#f85149]")

    def _new_tab(self) -> None:
        tab_id = f"tab-{len(self._files)+1}"
        tabs = self.query_one("#code-tabs", TabbedContent)
        pane = TabPane("New", id=tab_id)
        pane.mount(TextArea("", language="python", id=f"editor-{tab_id}", show_line_numbers=True))
        tabs.add_pane(pane)
        tabs.active = tab_id

    def _goto_line(self) -> None:
        if not self._active_file:
            return
        tab_id = self._files[self._active_file]["tab_id"]
        try:
            editor = self.query_one(f"#editor-{tab_id}", TextArea)
            editor.focus()
        except Exception:
            pass

    @on(Input.Submitted, "#code-search")
    def on_search(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return
        output = self.query_one("#code-output", RichLog)
        output.clear()
        output.write(f"[bold]Search: {query}[/bold]")
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".livingtree", "node_modules")]
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    content = Path(fpath).read_text(encoding="utf-8", errors="replace")
                    if query.lower() in content.lower():
                        output.write(f"  {fpath}")
                except Exception:
                    pass

    @work(exclusive=False)
    async def _launch_opencode(self, serve: bool = False) -> None:
        from .widgets.opencode_launcher import OpenCodeLauncher
        output = self.query_one("#code-output", RichLog)
        output.clear()
        mode_label = "OpenCode Serve" if serve else "OpenCode"
        output.write(f"[#58a6ff]Starting {mode_label}...[/#58a6ff]")

        def on_progress(msg):
            output.write(f"  [#d29922]{msg}[/#d29922]")

        launcher = OpenCodeLauncher(workspace=self._workspace, hub=self._hub)
        if serve:
            ok, msg = await launcher.auto_start_serve(on_progress=on_progress)
        else:
            ok, msg = await launcher.launch_tui(on_progress=on_progress)

        if ok:
            output.write(f"  [#3fb950]{msg}[/#3fb950]")
            if serve:
                output.write(f"[#3fb950]API: http://localhost:{launcher.SERVE_PORT}[/#3fb950]")
                output.write("[#3fb950]LSP enabled via opencode[/#3fb950]")
        else:
            output.write(f"  [#f85149]Failed: {msg}[/#f85149]")

    @work(exclusive=False)
    async def _run_lsp_diagnostics(self, file_path: str) -> None:
        if not self._lsp_bridge or not file_path:
            return
        output = self.query_one("#code-output", RichLog)
        try:
            diag_text = await self._lsp_bridge.check_file_and_format(file_path)
            if diag_text:
                output.write(diag_text)
        except Exception:
            pass

    def _add_recent(self, path: str) -> None:
        recent = self._load_recent_list()
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        recent = recent[:20]
        self._recent_path.write_text(json.dumps(recent))

    def _load_recent_list(self) -> list[str]:
        try:
            return json.loads(self._recent_path.read_text())
        except Exception:
            return []

    @on(AgentRunRequest)
    async def on_agent_launch(self, event: AgentRunRequest) -> None:
        output = self.query_one("#code-output", RichLog)
        output.write(f"[bold #58a6ff]Launching {event.agent_name}...[/bold #58a6ff]")

        try:
            from ..widgets.coding_agent_panel import AGENTS_DIR
            agent_file = AGENTS_DIR / f"{event.agent_id}.toml"
            if not agent_file.exists():
                output.write(f"[red]Agent not found: {event.agent_id}[/red]")
                return

            import tomllib
            with open(agent_file, "rb") as f:
                agent_data = tomllib.load(f)

            run_cmds = agent_data.get("run_command", {})
            run_cmd = run_cmds.get("*", run_cmds.get(os.name, ""))
            if not run_cmd:
                output.write("[red]No run command configured[/red]")
                return

            output.write(f"[dim]$ {run_cmd}[/dim]")

            proc = await asyncio.create_subprocess_shell(
                run_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._workspace) if self._workspace else None,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=60
                )
                if stdout:
                    output.write(stdout.decode(errors="replace")[:8000])
                if stderr:
                    output.write(f"[red]{stderr.decode(errors="replace")[:4000]}[/red]")
                output.write(f"[dim]Exit: {proc.returncode}[/dim]")
            except asyncio.TimeoutError:
                proc.kill()
                output.write("[yellow]Agent timed out (60s)[/yellow]")

        except Exception as e:
            output.write(f"[red]Agent error: {e}[/red]")

    def _load_recent(self) -> None:
        recent = self._load_recent_list()
        if recent:
            name = Path(recent[0]).name if recent else "none"
            self.query_one("#code-file-info", Label).update(f"[dim]Recent: {name}[/dim]")
