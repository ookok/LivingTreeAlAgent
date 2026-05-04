"""LivingTree TUI — smooth progressive boot architecture."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from loguru import logger
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Static, Input

from .screens.chat import ChatScreen
from .screens.code import CodeScreen
from .screens.docs import KnowledgeScreen
from .screens.tools import ToolsScreen
from .screens.settings import SettingsScreen
from .screens.help import HelpScreen
from .screens.boot import BootScreen
from .widgets.footer_bar import StatusBar
from .widgets.card import Card

BOOT_STEPS = ["配置系统", "导入引擎", "构建世界", "启动服务", "初始化完成"]

class LivingTreeTuiApp(App):
    TITLE = "LivingTree"
    SUB_TITLE = "数字生命体 v2.0"
    CSS_PATH = "styles/theme.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出"),
        Binding("ctrl+d", "toggle_dark", "主题"),
        Binding("ctrl+p", "command_palette", "命令", show=False),
        Binding("f1", "show_help", "帮助"),
        Binding("enter", "activate_card", "进入", show=False),
    ]

    ENABLE_COMMAND_PALETTE = True

    SCREENS = {"chat": ChatScreen, "code": CodeScreen, "docs": KnowledgeScreen,
               "tools": ToolsScreen, "settings": SettingsScreen}

    def __init__(self, workspace: str = "", hub=None):
        super().__init__()
        self.workspace = Path(workspace) if workspace else Path.cwd()
        self._hub = hub
        self._boot_done = hub is not None
        self._boot_task: Optional[asyncio.Task] = None

    def compose(self) -> ComposeResult:
        yield Static("LivingTree AI Agent  v2.0", id="title-bar")
        yield Input(placeholder="搜索...", id="card-search")
        with VerticalScroll(id="card-scroll"):
            with Horizontal(classes="card-row"):
                yield Card("💬\nAI 对话\n多模态智能助手", "chat")
                yield Card("📝\n代码编辑器\n编辑 · 运行 · Diff", "code")
                yield Card("📚\n知识库\n文档管理与检索", "docs")
            with Horizontal(classes="card-row"):
                yield Card("🔧\n工具箱\nPDF · 翻译 · 图表", "tools")
                yield Card("⚙\n系统配置\nAPI · 基因组 · 训练", "settings")
        yield StatusBar()

    async def on_mount(self) -> None:
        self.sub_title = f"v2.0 · {self.workspace.name}"
        self.query_one("#card-search", Input).display = False
        self._focus_first_card()

        if not self._boot_done:
            boot = BootScreen(BOOT_STEPS)
            await self.push_screen(boot)
            self._boot_task = asyncio.create_task(self._run_boot(boot))
        else:
            self._update_status()

        self._status_timer = self.set_interval(5, self._update_status)

    # ═══ Boot: everything async, nothing blocks ═══
    async def _run_boot(self, boot: BootScreen) -> None:
        loop = asyncio.get_event_loop()
        try:
            boot.current = 0
            await asyncio.sleep(0.3)
            boot.advance()
            boot.current = 1
            await asyncio.sleep(0.2)

            def _create_hub():
                from ..integration.hub import IntegrationHub
                return IntegrationHub()
            self._hub = await loop.run_in_executor(None, _create_hub)
            boot.advance()
            boot.current = 2
            await asyncio.sleep(0.2)

            await loop.run_in_executor(None, self._hub._init_sync)
            boot.advance()
            boot.current = 3
            await asyncio.sleep(0.3)

            await self._hub._init_async()
            boot.advance()
            boot.current = 4
            await asyncio.sleep(0.5)

            self._boot_done = True
            self._update_status()
            self.pop_screen()
            self.notify("系统就绪 — 全部功能已启用", timeout=3)
            await self._auto_start_opencode_serve()

        except Exception as e:
            logger.error(f"Boot failed: {e}")
            self._boot_done = True
            self._update_status()
            try:
                self.pop_screen()
            except Exception:
                pass
            self.notify(f"启动失败: {e}", severity="error", timeout=5)

    # ═══ Interaction ═══
    async def on_click(self, event) -> None:
        try:
            widget, _ = self.screen.get_widget_at(event.x, event.y)
            for node in widget.ancestors_with_self:
                if isinstance(node, Card):
                    self.push_screen(node.screen_name)
                    return
                if getattr(node, 'id', '') == 'back-link':
                    self.pop_screen()
                    return
        except Exception:
            pass

    def action_activate_card(self) -> None:
        if not self._boot_done:
            self.notify("系统初始化中，请稍候...", timeout=2, severity="warning")
            return
        f = self.focused
        if isinstance(f, Card):
            self.push_screen(f.screen_name)

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_toggle_dark(self) -> None:
        self.theme = "textual-dark" if self.theme == "textual-light" else "textual-light"

    def _focus_first_card(self) -> None:
        try:
            cards = list(self.query(Card))
            if cards:
                self.set_focus(cards[0])
        except Exception:
            pass

    def _update_status(self) -> None:
        try:
            bar = self.query_one(StatusBar)
            bar.update_system_status(self._hub)
        except Exception:
            pass

    async def on_unmount(self) -> None:
        if self._boot_task:
            self._boot_task.cancel()
        if self._hub:
            try:
                await self._hub.shutdown()
            except Exception:
                pass

    @property
    def hub(self):
        return self._hub

    async def _auto_start_opencode_serve(self) -> None:
        try:
            from .widgets.opencode_launcher import OpenCodeLauncher
            launcher = OpenCodeLauncher(workspace=str(self.workspace), hub=self._hub)
            ok, msg = await launcher.auto_start_serve_if_needed()
            if ok and "already" not in msg.lower():
                logger.info(f"OpenCode serve auto-started: {msg}")
            elif ok:
                logger.debug(f"OpenCode serve: {msg}")
        except Exception as e:
            logger.debug(f"OpenCode serve auto-start skipped: {e}")


def run_tui(workspace: str = "", hub=None) -> None:
    app = LivingTreeTuiApp(workspace=workspace, hub=hub)
    app.run()

