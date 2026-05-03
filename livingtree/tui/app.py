"""LivingTree TUI — Chinese, 5 tabs, unified status, WT GPU accel."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Optional

from loguru import logger
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import TabbedContent, TabPane

from ..observability import setup_observability

from .screens.chat import ChatScreen
from .screens.code import CodeScreen
from .screens.docs import KnowledgeScreen
from .screens.tools import ToolsScreen
from .screens.settings import SettingsScreen
from .widgets.header import TuiHeader
from .widgets.footer_bar import StatusBar


class LivingTreeTuiApp(App):
    TITLE = "🌳 LivingTree"
    SUB_TITLE = "数字生命体 v2.0"

    CSS_PATH = "styles/theme.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出", show=True),
        Binding("ctrl+1", "focus_tab('chat')", "对话", show=True),
        Binding("ctrl+2", "focus_tab('code')", "代码", show=True),
        Binding("ctrl+3", "focus_tab('docs')", "知识库", show=True),
        Binding("ctrl+4", "focus_tab('tools')", "工具箱", show=True),
        Binding("ctrl+5", "focus_tab('settings')", "配置", show=True),
        Binding("ctrl+d", "toggle_dark", "主题", show=True),
        Binding("ctrl+p", "command_palette", "命令", show=False),
        Binding("f1", "show_help", "帮助", show=False),
        Binding("f5", "refresh", "刷新", show=False),
    ]

    ENABLE_COMMAND_PALETTE = True

    def __init__(self, workspace: str = "", hub=None):
        super().__init__()
        self.workspace = Path(workspace) if workspace else Path.cwd()
        self._hub = hub
        self._hub_task: Optional[asyncio.Task] = None
        self._boot_time = 0.0
        self._boot_pct = 0
        self._boot_target = 0
        self._boot_label = ""

    def compose(self) -> ComposeResult:
        yield TuiHeader()
        with TabbedContent(initial="chat"):
            with TabPane(" 💬 对话 ", id="chat"):
                yield ChatScreen(id="chat-screen")
            with TabPane(" 📝 代码 ", id="code"):
                yield CodeScreen(id="code-screen")
            with TabPane(" 📚 知识库 ", id="docs"):
                yield KnowledgeScreen(id="docs-screen")
            with TabPane(" 🔧 工具箱 ", id="tools"):
                yield ToolsScreen(id="tools-screen")
            with TabPane(" ⚙ 配置 ", id="settings"):
                yield SettingsScreen(id="settings-screen")
        yield StatusBar()

    async def on_mount(self) -> None:
        self.sub_title = f"数字生命体 v2.0 · {self.workspace.name}"

        if self._hub is None:
            self._boot_time = time.time()
            self._boot_label = "初始化..."
            self._boot_target = 5
            self._update_status()
            self._hub_task = asyncio.create_task(self._boot_hub())
            self.set_interval(0.3, self._update_boot_progress)
        else:
            self._wire_screens()
            self._update_status()
            self.set_interval(5, self._update_status)
            self.notify("就绪 · ^P 命令 · ^1-5 切换标签", timeout=2)

    def _update_boot_progress(self) -> None:
        if not self._hub_task or self._hub_task.done():
            return
        if self._boot_pct < self._boot_target:
            self._boot_pct = min(self._boot_pct + 1, self._boot_target)
        self._update_status()

    def _set_phase(self, label: str, target: int) -> None:
        self._boot_label = label
        self._boot_target = target
        self._update_status()

    async def _boot_hub(self) -> None:
        loop = asyncio.get_event_loop()

        self._set_phase("加载模块...", 10)
        await asyncio.sleep(0.2)

        def _import_hub():
            from ..integration.hub import IntegrationHub
            return IntegrationHub

        self._set_phase("导入引擎...", 50)
        HubClass = await loop.run_in_executor(None, _import_hub)

        self._set_phase("构建世界...", 70)
        self._hub = HubClass()

        self._set_phase("启动服务...", 95)
        await self._hub.start()

        self._boot_pct = 100
        self._boot_label = "完成"
        self._boot_target = 100
        self._update_status()
        await asyncio.sleep(0.5)

        self._boot_label = ""
        self._boot_pct = 100

        self._wire_screens()
        self._update_status()
        self.set_interval(5, self._update_status)
        self.notify("就绪 · ^P 命令 · ^1-5 切换标签", timeout=2)

    def _wire_screens(self) -> None:
        for sid in ["chat", "code", "docs", "tools", "settings"]:
            try:
                screen = self.query_one(f"#{sid}-screen")
                screen.set_hub(self._hub)
            except Exception as e:
                logger.warning(f"Failed to wire screen '{sid}': {e}")

    def _update_status(self) -> None:
        try:
            bar = self.query_one(StatusBar)
            if self._boot_label:
                elapsed = time.time() - self._boot_time
                bar.show_booting(self._boot_label, self._boot_pct, elapsed)
            else:
                bar.update_system_status(self._hub)
        except Exception as e:
            logger.debug(f"Status update failed: {e}")

    async def on_unmount(self) -> None:
        if self._hub_task:
            self._hub_task.cancel()
        if self._hub:
            try:
                await self._hub.shutdown()
            except Exception as e:
                logger.warning(f"Hub shutdown error: {e}")

    def action_toggle_dark(self) -> None:
        self.theme = "textual-dark" if self.theme == "textual-light" else "textual-light"

    def action_focus_tab(self, tab_id: str) -> None:
        try:
            self.query_one(TabbedContent).active = tab_id
        except Exception as e:
            logger.warning(f"Failed to switch to tab '{tab_id}': {e}")
            self.notify(f"无法切换到标签 '{tab_id}'", severity="error", timeout=2)

    def action_refresh(self) -> None:
        tabs = self.query_one(TabbedContent)
        for sid in ["chat", "code", "docs", "tools", "settings"]:
            try:
                screen = self.query_one(f"#{sid}-screen")
                if hasattr(screen, "refresh"):
                    asyncio.create_task(screen.refresh())
            except Exception:
                pass

    @property
    def hub(self):
        return self._hub


def run_tui(workspace: str = "", hub=None) -> None:
    app = LivingTreeTuiApp(workspace=workspace, hub=hub)
    app.run()
