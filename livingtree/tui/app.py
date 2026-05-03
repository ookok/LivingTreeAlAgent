"""LivingTree TUI — Main Application.

Windows Terminal-native Textual TUI app for the LivingTree digital life form.
Keyboard-first, mouse-friendly, with DeepSeek dual-model streaming chat.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Header, Footer, TabbedContent, TabPane, Label, Button,
    Input, RichLog, LoadingIndicator, Static,
)

from ..config import get_config, reload_config
from ..integration.hub import IntegrationHub
from ..observability import setup_observability, get_logger

from .screens.chat import ChatScreen
from .screens.code import CodeScreen
from .screens.docs import DocsScreen
from .screens.map_viewer import MapScreen
from .screens.settings import SettingsScreen
from .widgets.header import TuiHeader
from .widgets.footer_bar import StatusBar


class HelpScreen(ModalScreen):
    """Modal help screen showing key bindings."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("LivingTree TUI — Keyboard Shortcuts"),
            Static("""
 Global:
   Ctrl+Q          Quit application
   Ctrl+T          Cycle tabs
   Ctrl+D          Toggle dark/light theme
   F1              Show this help
   F5              Refresh / Reload
   Ctrl+P          Command palette

 Chat:
   Enter           Send message
   Shift+Enter     New line
   Ctrl+L          Clear chat
   Ctrl+U          Scroll up in history
   Ctrl+D          Scroll down in history

 Code:
   Ctrl+S          Save file
   Ctrl+/          Toggle comment
   Alt+Enter       AI complete / explain
   F8              Run / Preview

 Docs:
   Enter           Open selected file
   Backspace       Go to parent folder
   Ctrl+F          Search in file tree

 Map:
   + / -           Zoom in/out
   Arrow keys      Pan map
   /               Search location

 Settings:
   Tab / Shift+Tab Navigate fields
   Enter           Apply setting
            """.strip(), id="help-text"),
            Button("Close", variant="primary", id="help-close"),
            id="help-panel",
        )

    @on(Button.Pressed, "#help-close")
    def on_close(self) -> None:
        self.dismiss()


class LivingTreeTuiApp(App):
    """Main LivingTree TUI application.

    Integrates with the livingtree backend for:
    - AI chat with DeepSeek dual-model (flash + pro with thinking)
    - Code generation and analysis
    - Document management with knowledge base
    - Map/GIS visualization
    - Settings and configuration
    """

    TITLE = "LivingTree AI Agent"
    SUB_TITLE = "Digital Lifeform v2.0"

    CSS_PATH = "styles/theme.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+t", "cycle_tab", "Cycle Tab", show=True),
        Binding("ctrl+d", "toggle_theme", "Toggle Theme", show=True),
        Binding("f1", "show_help", "Help", show=True),
        Binding("f5", "refresh", "Refresh", show=True),
        Binding("ctrl+p", "command_palette", "Commands", show=False),
    ]

    ENABLE_COMMAND_PALETTE = True

    def __init__(self, workspace: str = "", hub: Optional[IntegrationHub] = None):
        super().__init__()
        self.workspace = Path(workspace) if workspace else Path.cwd()
        self._hub = hub
        self._dark_mode = True
        self._tab_order = ["chat", "code", "docs", "map", "settings"]
        self._current_tab_idx = 0

    def compose(self) -> ComposeResult:
        yield TuiHeader()

        with TabbedContent(initial="chat"):
            with TabPane("  Chat  ", id="chat"):
                yield ChatScreen(id="chat-screen")
            with TabPane("  Code  ", id="code"):
                yield CodeScreen(id="code-screen")
            with TabPane("  Docs  ", id="docs"):
                yield DocsScreen(id="docs-screen")
            with TabPane("  Map  ", id="map"):
                yield MapScreen(id="map-screen")
            with TabPane("  Settings  ", id="settings"):
                yield SettingsScreen(id="settings-screen")

        yield StatusBar()

    async def on_mount(self) -> None:
        """Initialize the backend hub and set up the application."""
        self.sub_title = f"Digital Lifeform v2.0 — {self.workspace.name}"

        # Initialize backend hub if not provided
        if self._hub is None:
            try:
                self._hub = IntegrationHub()
                await self._hub.start()
            except Exception as e:
                self.notify(f"Backend init: {e}", severity="warning", timeout=5)

        # Pass hub reference to screens
        for screen_id in self._tab_order:
            try:
                screen = self.query_one(f"#{screen_id}-screen")
                screen.set_hub(self._hub)
            except Exception:
                pass

        self.notify("LivingTree TUI ready — F1 for help", timeout=3)

    async def on_unmount(self) -> None:
        """Shutdown the backend hub."""
        if self._hub:
            try:
                await self._hub.shutdown()
            except Exception:
                pass

    # ── Actions ──

    def action_cycle_tab(self) -> None:
        """Cycle through tabs."""
        self._current_tab_idx = (self._current_tab_idx + 1) % len(self._tab_order)
        tab_id = self._tab_order[self._current_tab_idx]
        try:
            tabs = self.query_one(TabbedContent)
            tabs.active = tab_id
        except Exception:
            pass

    def action_toggle_theme(self) -> None:
        """Toggle between dark and light theme."""
        self._dark_mode = not self._dark_mode
        if self._dark_mode:
            self.screen.remove_class("light")
            self.notify("Dark theme", timeout=1)
        else:
            self.screen.add_class("light")
            self.notify("Light theme", timeout=1)

    def action_show_help(self) -> None:
        """Show help modal."""
        self.push_screen(HelpScreen())

    def action_refresh(self) -> None:
        """Refresh the current view."""
        self.notify("Refreshing...", timeout=1)
        try:
            tabs = self.query_one(TabbedContent)
            screen = tabs.query_one(f"#{tabs.active}-screen")
            if hasattr(screen, "refresh"):
                asyncio.create_task(screen.refresh())
        except Exception:
            pass

    # ── Properties ──

    @property
    def hub(self) -> Optional[IntegrationHub]:
        return self._hub

    def get_hub(self) -> Optional[IntegrationHub]:
        return self._hub


def run_tui(workspace: str = "", hub: Optional[IntegrationHub] = None) -> None:
    """Entry point to run the TUI app."""
    app = LivingTreeTuiApp(workspace=workspace, hub=hub)
    app.run()
