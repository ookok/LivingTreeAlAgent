"""LoginScreen — mandatory login against relay server before TUI access."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, Button
from textual.containers import Vertical, Center
from textual.binding import Binding

import asyncio
import aiohttp

RELAY_URL = "http://www.mogoo.com.cn:8888"
LOCAL_RELAY = "http://127.0.0.1:8888"


class LoginScreen(Screen):
    """Login screen — validates credentials against relay server."""

    BINDINGS = [
        Binding("enter", "submit", "登录"),
        Binding("escape", "quit", "退出"),
        Binding("ctrl+s", "skip_login", "跳过"),
    ]

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="login-box"):
                yield Static("🌳 LivingTree", id="login-title")
                yield Static("请登录以继续使用", id="login-subtitle")
                yield Input(placeholder="用户名", id="login-user")
                yield Input(placeholder="密码", password=True, id="login-pass")
                yield Static("", id="login-error")
                yield Button("登录", id="btn-login", variant="primary")
                yield Static(
                    "没有账号？发送邮件至 livingtreeai@163.com 申请，并说明用途",
                    id="login-hint",
                )

    def on_mount(self):
        self.query_one("#login-user", Input).focus()

    def action_submit(self):
        self._do_login()

    @on(Button.Pressed, "#btn-login")
    async def on_login_button(self, event: Button.Pressed):
        self._do_login()

    def _do_login(self):
        user = self.query_one("#login-user", Input).value.strip()
        pwd = self.query_one("#login-pass", Input).value
        if not user or not pwd:
            self.query_one("#login-error", Static).update("[red]请输入用户名和密码[/red]")
            return
        self.run_worker(self._async_login(user, pwd))

    async def _async_login(self, user: str, pwd: str):
        error_widget = self.query_one("#login-error", Static)
        error_widget.update("[yellow]正在验证...[/yellow]")

        # Try remote relay first, then local
        urls = [RELAY_URL, LOCAL_RELAY]
        for url in urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{url}/login",
                        json={"username": user, "password": pwd},
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self._on_login_success(data, user)
                            return
                        else:
                            data = await resp.json()
                            error_widget.update(f"[red]{data.get('error', '登录失败')}[/red]")
                            return
            except asyncio.TimeoutError:
                continue
            except (aiohttp.ClientConnectorError, aiohttp.ClientError):
                continue
            except Exception:
                continue

        error_widget.update("[red]无法连接中继服务器 (尝试了远程和本地)[/red]")

    def _on_login_success(self, data: dict, user: str):
        token = data.get("token", data.get("api_key", ""))
        self.app._auth_token = token
        self.app._auth_user = user
        self.app._auth_verified = True
        from ..network.p2p_node import get_p2p_node
        node = get_p2p_node()
        node._auth_token = token
        node._username = user
        self.app.pop_screen()
        self.app.notify(f"✓ 已登录: {user}", timeout=2)

    def action_skip_login(self):
        """Skip login for offline/local use."""
        self.app._auth_verified = True
        self.app._auth_user = "offline"
        self.app._auth_token = "offline-mode"
        self.app.pop_screen()
        self.app.notify("⚠ 离线模式 (跳过登录)", timeout=2)
