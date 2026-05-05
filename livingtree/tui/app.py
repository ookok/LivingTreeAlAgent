"""LivingTree TUI — extends ToadApp for full Toad panel integration."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import ClassVar, Optional

from loguru import logger

try:
    from ..observability.error_interceptor import install as _install_interceptor
    _install_interceptor()
except Exception:
    pass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Static, Input
from textual.containers import VerticalScroll, Horizontal
from textual import on

from .td.app import ToadApp
from .td import messages
from .td.agent_schema import Agent as AgentData

from .widgets.footer_bar import StatusBar
from .widgets.card import Card
from .i18n import t


class LivingTreeTuiApp(ToadApp):
    """LivingTree TUI — inherits Toad settings/sessions/tracker/signals."""

    TITLE = "LivingTree"
    SUB_TITLE = "Digital Life Form v2.1"

    CSS_PATH = "styles/theme.tcss"

    BINDINGS: ClassVar = [
        Binding("ctrl+t", "push_chat", t("bind.chat")),
        Binding("ctrl+e", "push_code", t("bind.code")),
        Binding("ctrl+d", "push_docs", t("bind.docs")),
        Binding("ctrl+k", "push_tools", t("bind.tools")),
        Binding("f2", "push_settings", t("bind.settings")),
        Binding("ctrl+q", "quit", t("bind.quit")),
        Binding("f1", "show_help", t("bind.help")),
        Binding("ctrl+l", "toggle_lang", "语言/Lang"),
        Binding("enter", "activate_card", t("bind.enter"), show=False),
    ]

    ALLOW_IN_MAXIMIZED_VIEW = ""

    SCREENS = {}

    def __init__(self, workspace: str = "", hub=None):
        super().__init__()
        self.workspace = Path(workspace) if workspace else Path.cwd()
        self._hub = hub
        self._boot_done = hub is not None
        self._boot_task: Optional[asyncio.Task] = None
        self.project_dir = self.workspace

        # Override Toad's settings pages with our screens
        self._override_toad_screens()

    def _override_toad_screens(self):
        from .td.screens.settings import SettingsScreen as ToadSettings
        from .td.screens.sessions import SessionsScreen as ToadSessions
        from .td.screens.store import StoreScreen

        self.SCREENS = {
            "settings": lambda: ToadSettings(),
            "sessions": lambda: ToadSessions(),
        }
        self.MODES = {"store": lambda: StoreScreen()}

    def compose(self) -> ComposeResult:
        yield Static("🌳 LivingTree AI Agent  v2.1", id="title-bar")
        yield Input(placeholder=t("app.search_placeholder"), id="card-search")
        with VerticalScroll(id="card-scroll"):
            with Horizontal(classes="card-row"):
                yield Card(t("card.chat"), "neon-chat")
                yield Card(t("card.code"), "code")
                yield Card(t("card.docs"), "docs")
            with Horizontal(classes="card-row"):
                yield Card(t("card.tools"), "tools")
                yield Card(t("card.settings"), "settings")
        yield StatusBar()

    async def on_mount(self) -> None:
        from .screens.neon_chat import NeonChatScreen
        from .screens.code import CodeScreen
        from .screens.docs import KnowledgeScreen
        from .screens.tools import ToolsScreen
        from .screens.help import HelpScreen
        from .td.screens.settings import SettingsScreen as ToadSettings

        self.SCREENS.update({
            "neon-chat": NeonChatScreen,
            "code": CodeScreen,
            "docs": KnowledgeScreen,
            "tools": ToolsScreen,
            "settings": lambda: ToadSettings(),
        })
        self.install_screen(HelpScreen(), "help")

        self.sub_title = f"v2.1 · {self.workspace.name}"
        self.query_one("#card-search", Input).display = False
        self._focus_first_card()

        if not self._boot_done:
            from .screens.boot import BootScreen
            BOOT_STEPS = [
                t("boot.step_config"), t("boot.step_engine"),
                t("boot.step_world"), t("boot.step_service"),
                t("boot.step_done"),
            ]
            boot = BootScreen(BOOT_STEPS)
            await self.push_screen(boot)
            self._boot_task = asyncio.create_task(self._run_boot(boot))
        else:
            self._update_status()

        self._status_timer = self.set_interval(5, self._update_status)

    async def _run_boot(self, boot) -> None:
        loop = asyncio.get_event_loop()
        try:
            boot.current = 0
            boot.advance()
            boot.current = 1

            def _create_hub():
                from ..integration.hub import IntegrationHub
                return IntegrationHub(lazy=True)
            self._hub = await loop.run_in_executor(None, _create_hub)
            boot.advance()
            boot.current = 2

            await loop.run_in_executor(None, self._hub._init_sync)
            boot.advance()
            boot.current = 3

            await self._hub._init_async()
            boot.advance()
            boot.current = 4

            self._boot_done = True
            self._update_status()
            self.pop_screen()
            self.notify("系统就绪", timeout=2)

            # ── Mandatory login check ──
            if not self._auth_verified:
                from .screens.login import LoginScreen
                await self.push_screen(LoginScreen())

            # ── Start panel agents ──
            asyncio.create_task(self._start_panel_agents())
            asyncio.create_task(self._auto_start_opencode_serve())

        except Exception as e:
            logger.error(f"Boot failed: {e}")
            self._boot_done = True
            self._update_status()
            try: self.pop_screen()
            except Exception: pass
            self.notify(t("app.boot_failed") + f": {e}", severity="error", timeout=5)

    def action_push_chat(self) -> None:
        if not self._boot_done:
            self.notify(t("app.booting"), timeout=2, severity="warning")
            return
        self.push_screen("neon-chat")

    def action_push_code(self) -> None:
        if not self._boot_done:
            self.notify(t("app.booting"), timeout=2, severity="warning")
            return
        self.push_screen("code")

    def action_push_docs(self) -> None:
        if not self._boot_done:
            self.notify(t("app.booting"), timeout=2, severity="warning")
            return
        self.push_screen("docs")

    def action_push_tools(self) -> None:
        if not self._boot_done:
            self.notify(t("app.booting"), timeout=2, severity="warning")
            return
        self.push_screen("tools")

    def action_push_settings(self) -> None:
        if not self._boot_done:
            self.notify(t("app.booting"), timeout=2, severity="warning")
            return
        self.push_screen("settings")

    def action_activate_card(self) -> None:
        if not self._boot_done:
            self.notify(t("app.booting"), timeout=2, severity="warning")
            return
        f = self.focused
        if isinstance(f, Card):
            self.push_screen(f.screen_name)

    def action_show_help(self) -> None:
        self.push_screen("help")

    def action_toggle_lang(self) -> None:
        from .i18n import i18n
        current = i18n.lang
        new_lang = "en" if current == "zh" else "zh"
        i18n.switch(new_lang)
        self.notify(f"Language: {'中文' if new_lang == 'zh' else 'English'}", timeout=2)

    def action_toggle_dark(self) -> None:
        self.theme = "textual-dark" if self.theme == "textual-light" else "textual-light"

    def on_click(self, event) -> None:
        try:
            widget, _ = self.screen.get_widget_at(event.x, event.y)
            for node in widget.ancestors_with_self:
                if isinstance(node, Card):
                    if self._boot_done:
                        self.push_screen(node.screen_name)
                    return
        except Exception:
            pass

    def _focus_first_card(self) -> None:
        try:
            cards = list(self.query(Card))
            if cards: self.set_focus(cards[0])
        except Exception: pass

    def _update_status(self) -> None:
        try:
            bar = self.query_one(StatusBar)
            bar.update_system_status(self._hub)
        except Exception: pass

    async def on_unmount(self) -> None:
        if self._boot_task:
            self._boot_task.cancel()
        if self._hub:
            try: await self._hub.shutdown()
            except Exception: pass

    @property
    def hub(self):
        return self._hub

    def _handle_exception(self, error: Exception) -> None:
        try:
            from ..observability.error_interceptor import get_interceptor
            ei = get_interceptor()
            if ei: ei.capture(error, context="textual_app_handler")
        except Exception: pass
        super()._handle_exception(error)

    async def _start_panel_agents(self):
        """Register and start self-healing agents for each panel."""
        try:
            from ..execution.panel_agent import (
                ChatPanelAgent, CodePanelAgent, KnowledgePanelAgent, ToolsPanelAgent, get_agent_manager
            )
            manager = get_agent_manager()
            root = Path.cwd()
            manager.register("chat", ChatPanelAgent(root, self._hub))
            manager.register("code", CodePanelAgent(root, self._hub))
            manager.register("knowledge", KnowledgePanelAgent(root, self._hub))
            manager.register("tools", ToolsPanelAgent(root, self._hub))
            await manager.start_all()
            logger.info("Panel agents started with self-healing")
        except Exception as e:
            logger.debug(f"Panel agents: {e}")

    async def _auto_start_opencode_serve(self) -> None:
        try:
            from .widgets.opencode_launcher import OpenCodeLauncher
            launcher = OpenCodeLauncher(workspace=str(self.workspace), hub=self._hub)
            ok, msg = await launcher.auto_start_serve_if_needed()
            if ok: logger.info(f"OpenCode: {msg}")
        except Exception: pass

    # ── Toad message handlers we forward ──

    @on(messages.LaunchAgent)
    async def on_launch_agent(self, event: messages.LaunchAgent) -> None:
        """Handle LaunchAgent from Toad's store/agent panels."""
        try:
            agent_id = event.identity
            from .td.agents import read_agents
            agents = await read_agents()
            agent_data = agents.get(agent_id)
            if not agent_data:
                self.notify(f"Agent not found: {agent_id}", severity="error")
                return
            await self.launch_agent(agent_data, session_id=event.session_id,
                                     pk=event.pk, prompt=event.prompt)
        except Exception as e:
            logger.debug(f"Launch agent: {e}")

    async def launch_agent(self, agent_data: dict, session_id=None, pk=None, prompt=None):
        """Launch a Toad agent as a new session."""
        from .td.screens.main import MainScreen
        from pathlib import Path

        def get_screen() -> MainScreen:
            return MainScreen(
                project_path=self.workspace,
                agent=agent_data,
                agent_session_id=session_id,
                session_pk=pk,
            )

        await self.new_session_screen(get_screen, prompt=prompt)

    async def new_session_screen(self, get_screen, prompt=None):
        """Create a new session via Toad's SessionTracker."""
        details = self.session_tracker.new_session()
        self.update_show_sessions()
        self.session_update_signal.publish((details.mode_name, details))

        def make_screen():
            screen = get_screen()
            screen.id = details.mode_name
            if prompt:
                screen._initial_prompt = prompt
            return screen

        self.add_mode(details.mode_name, make_screen)
        await self.switch_mode(details.mode_name)
        return details

    # ── Required ToadApp overrides ──

    def update_terminal_title(self):
        pass

    def open_url(self, url: str):
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception:
            pass


def run_tui(workspace: str = "", hub=None) -> None:
    try:
        app = LivingTreeTuiApp(workspace=workspace, hub=hub)
        app.run()
    except Exception as e:
        logger.exception(f"TUI crashed: {e}")
        raise
