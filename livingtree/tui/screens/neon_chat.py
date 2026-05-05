"""NeonChatScreen — Toad Conversation + SideBar + Footer + mouse-friendly toolbar."""
from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Button, Static
from textual.containers import Horizontal
from textual.binding import Binding

from ..td.widgets.conversation import Conversation
from ..td.widgets.side_bar import SideBar
from ..td.widgets.plan import Plan
from ..td.widgets.project_directory_tree import ProjectDirectoryTree


class NeonChatScreen(Screen):
    """Full Toad chat with mouse-friendly toolbar.

    Keyboard users: Ctrl+Enter send, Esc back, Ctrl+B sidebar.
    Mouse users: click toolbar buttons for same actions.
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "返回"),
        Binding("ctrl+b", "toggle_sidebar", "侧栏"),
    ]

    def compose(self) -> ComposeResult:
        hub = self.app.hub if hasattr(self.app, 'hub') else None
        workspace = getattr(self.app, 'workspace', Path.cwd())
        if isinstance(workspace, str):
            workspace = Path(workspace)

        # ── Mouse-friendly toolbar ──
        yield Static("← 返回主页 (Esc)", id="back-link")
        with Horizontal(id="action-bar"):
            yield Button("🔍 搜索 (/search)", id="btn-search", variant="default")
            yield Button("📄 抓取 (/fetch)", id="btn-fetch", variant="default")
            yield Button("🧹 清空 (/clear)", id="btn-clear", variant="default")
            yield Button("📊 状态 (/status)", id="btn-status", variant="default")
            yield Button("📋 计划 (/plan)", id="btn-plan", variant="default")
            yield Static("│", classes="toolbar-sep")
            yield Button("◀ 返回", id="btn-back", variant="primary")

        yield Static("💡 提示: 按 Ctrl+Enter 发送  按 Esc 退出  /help 查看所有命令", id="context-hint")

        yield Conversation(
            project_path=workspace, agent=None, hub=hub,
        )
        yield Footer()

    def on_mount(self):
        conv = self.query_one(Conversation)
        conv.focus()

    def on_screen_resume(self):
        try:
            self.query_one(Conversation).focus()
        except Exception:
            pass

    def action_toggle_sidebar(self):
        try:
            sidebar = self.query_one(SideBar)
            sidebar.toggle_class("-hidden")
        except Exception:
            pass

    # ── Mouse clicks → slash commands ──

    @on(Button.Pressed, "#btn-search")
    def _click_search(self):
        self._type_command("/search ")

    @on(Button.Pressed, "#btn-fetch")
    def _click_fetch(self):
        self._type_command("/fetch ")

    @on(Button.Pressed, "#btn-clear")
    def _click_clear(self):
        self._type_command("/clear")

    @on(Button.Pressed, "#btn-status")
    def _click_status(self):
        self._type_command("/status")

    @on(Button.Pressed, "#btn-plan")
    def _click_plan(self):
        self._type_command("/plan ")

    @on(Button.Pressed, "#btn-back")
    def _click_back(self):
        self.app.pop_screen()

    def _type_command(self, text: str):
        """Type a slash command into the prompt."""
        try:
            conv = self.query_one(Conversation)
            prompt = conv.query_one("#prompt-input")
            if hasattr(prompt, 'text'):
                prompt.text = text
                prompt.focus()
        except Exception:
            self.app.notify(text, timeout=2)
