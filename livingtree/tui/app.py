"""LivingTree TUI — Textual-powered AI Development Platform.

Uses Textual 8.x features: CommandPalette, DataTable, TabbedContent,
Footer with key bindings, async workers, dynamic layout.

Usage:
    python -m livingtree tui --direct
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Footer, TabbedContent, TabPane

from ..integration.hub import IntegrationHub
from ..observability import setup_observability

from .screens.chat import ChatScreen
from .screens.code import CodeScreen
from .screens.docs import DocsScreen
from .screens.settings import SettingsScreen
from .widgets.header import TuiHeader
from .widgets.footer_bar import StatusBar


class LivingTreeTuiApp(App):
    TITLE = "LivingTree AI Agent"
    SUB_TITLE = "Digital Lifeform v2.0 — www.livingtree-ai.com"

    CSS_PATH = "styles/theme.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+1", "focus_tab('chat')", "Chat", show=True),
        Binding("ctrl+2", "focus_tab('code')", "Code", show=True),
        Binding("ctrl+3", "focus_tab('docs')", "Docs", show=True),
        Binding("ctrl+4", "focus_tab('settings')", "Settings", show=True),
        Binding("ctrl+d", "toggle_dark", "Theme", show=True),
        Binding("f1", "show_help", "Help", show=False),
        Binding("f5", "refresh", "Refresh", show=False),
    ]

    ENABLE_COMMAND_PALETTE = True

    def __init__(self, workspace: str = "", hub: Optional[IntegrationHub] = None):
        super().__init__()
        self.workspace = Path(workspace) if workspace else Path.cwd()
        self._hub = hub
        self._dark = True

    def compose(self) -> ComposeResult:
        yield TuiHeader()
        with TabbedContent(initial="chat"):
            with TabPane(" Chat ", id="chat"):
                yield ChatScreen(id="chat-screen")
            with TabPane(" Code ", id="code"):
                yield CodeScreen(id="code-screen")
            with TabPane(" Docs ", id="docs"):
                yield DocsScreen(id="docs-screen")
            with TabPane(" Settings ", id="settings"):
                yield SettingsScreen(id="settings-screen")
        yield Footer()

    async def on_mount(self) -> None:
        self.sub_title = f"v2.0 — {self.workspace.name}"
        if self._hub is None:
            try:
                self._hub = IntegrationHub()
                await self._hub.start()
            except Exception as e:
                self.notify(f"Backend: {e}", severity="warning", timeout=3)

        for sid in ["chat", "code", "docs", "settings"]:
            try:
                screen = self.query_one(f"#{sid}-screen")
                screen.set_hub(self._hub)
            except Exception:
                pass

        self.notify("Ready — Ctrl+1-4 tabs, Ctrl+P commands", timeout=2)

    async def on_unmount(self) -> None:
        if self._hub:
            try:
                await self._hub.shutdown()
            except Exception:
                pass

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark

    def action_focus_tab(self, tab_id: str) -> None:
        try:
            self.query_one(TabbedContent).active = tab_id
        except Exception:
            pass

    def action_refresh(self) -> None:
        tabs = self.query_one(TabbedContent)
        for sid in ["chat", "code", "docs", "settings"]:
            try:
                screen = self.query_one(f"#{sid}-screen")
                if hasattr(screen, "refresh"):
                    asyncio.create_task(screen.refresh())
            except Exception:
                pass

    def get_system_commands(self, _):
        """Provide commands to Textual's built-in CommandPalette."""
        from textual.command import Provider, Hit, Hits
        from ..integration.hub import IntegrationHub

        class LivingTreeCommands(Provider):
            async def search(self, query: str) -> Hits:
                matcher = self.matcher(query)
                commands = [
                    ("Generate Code", "AI generates code from description", "gen_code"),
                    ("Blast Radius", "Analyze change impact of current file", "blast"),
                    ("Find Callers", "Who calls the selected function", "callers"),
                    ("Find Callees", "What the selected function calls", "callees"),
                    ("Search Code", "Search code entities by name", "search_code"),
                    ("Index Codebase", "Build the code knowledge graph", "index"),
                    ("Search Knowledge", "Search the knowledge base", "kb_search"),
                    ("Detect Knowledge Gaps", "Find missing knowledge areas", "gaps"),
                    ("System Status", "Show engine and cell status", "status"),
                    ("Cost Status", "Show budget and pricing", "cost"),
                    ("Audit Chain", "Verify Merkle audit integrity", "audit"),
                    ("Health Check", "Run all health checks", "health"),
                    ("Generate Report", "Generate industrial report", "report"),
                    ("List Cells", "List registered AI cells", "cells"),
                ]
                for name, desc, cmd in commands:
                    if matcher.match(name) or matcher.match(desc):
                        yield Hit(name, desc, f"livingtree:{cmd}")
        yield LivingTreeCommands

    @property
    def hub(self) -> Optional[IntegrationHub]:
        return self._hub


def run_tui(workspace: str = "", hub: Optional[IntegrationHub] = None) -> None:
    app = LivingTreeTuiApp(workspace=workspace, hub=hub)
    app.run()
