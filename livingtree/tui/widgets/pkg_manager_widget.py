"""PackageManagerWidget — Toad-styled TUI for managing packages via abxpkg."""
from __future__ import annotations

from textual import on, work
from textual.containers import VerticalScroll, Horizontal
from textual.widgets import Static, Button, Input, RichLog
from textual.binding import Binding
from textual.message import Message


class PackageManagerWidget(VerticalScroll):
    """Package management panel: search, install, list packages."""

    BINDINGS = [
        Binding("r", "refresh", "刷新"),
    ]

    def compose(self):
        yield Static("📦 包管理器", classes="panel-title")
        with Horizontal(classes="pkg-search-row"):
            yield Input(placeholder="搜索包名...", id="pkg-search")
            yield Button("🔍 搜索", id="btn-pkg-search", variant="primary")
            yield Button("📋 列表", id="btn-pkg-list", variant="default")
            yield Button("🔄 检查环境", id="btn-env-check", variant="default")
        yield RichLog(id="pkg-output", highlight=True, markup=True, wrap=True)
        yield Static("", id="pkg-status", classes="pkg-status")

    def on_mount(self):
        self.action_refresh()

    def action_refresh(self):
        self._show_env_status()

    def _show_env_status(self):
        try:
            from ...integration.pkg_manager import check_environment
            status = check_environment()
            output = self.query_one("#pkg-output", RichLog)
            output.clear()
            output.write(f"[bold]🔬 环境状态[/bold]")
            output.write(f"Python: {status.python}")
            output.write(f"pip: {status.pip or '[red]缺失[/red]'}")
            output.write(f"uv: {status.uv or '[yellow]未安装[/yellow]'}")
            output.write(f"Node.js: {status.node or '[yellow]未安装[/yellow]'}")
            output.write(f"npm: {status.npm or '[yellow]未安装[/yellow]'}")
            output.write(f"Git: {status.git or '[red]缺失[/red]'}")
            output.write(f"abxpkg: {status.abxpkg or '[yellow]未安装[/yellow]'}")
            if status.issues:
                output.write(f"\n[bold yellow]⚠ 问题:[/bold yellow]")
                for issue in status.issues:
                    output.write(f"  • {issue}")
            else:
                output.write(f"\n[green]✓ 环境就绪[/green]")
        except Exception as e:
            self.query_one("#pkg-output", RichLog).write(f"[red]{e}[/red]")

    @on(Button.Pressed, "#btn-pkg-search")
    async def on_search(self, event: Button.Pressed):
        query = self.query_one("#pkg-search", Input).value.strip()
        if not query:
            self.query_one("#pkg-status", Static).update("[yellow]输入包名[/yellow]")
            return

        output = self.query_one("#pkg-output", RichLog)
        output.clear()
        output.write(f"[bold]🔍 搜索: {query}[/bold]")

        try:
            from ...integration.pkg_manager import search_package
            results = search_package(query, providers=["pip", "npm", "brew"])
            if results:
                for r in results:
                    output.write(f"  [green]• {r.name}[/green] [{r.provider}]")
            else:
                output.write("[dim]未找到匹配的包[/dim]")
                output.write("[dim]尝试 pip install:[/dim]")

                try:
                    from ...integration.pkg_manager import install_package
                    info = install_package(query, providers=["pip"], dry_run=True)
                    if info.error:
                        output.write(f"[red]{info.error[:300]}[/red]")
                    else:
                        output.write(f"[green]可安装: {info.name} via pip[/green]")
                except Exception as e2:
                    output.write(f"[red]{e2}[/red]")

            self.query_one("#pkg-status", Static).update(
                f"[green]{len(results)} 个结果[/green]"
            )
        except Exception as e:
            output.write(f"[red]搜索失败: {e}[/red]")

    @on(Button.Pressed, "#btn-pkg-list")
    async def on_list(self, event: Button.Pressed):
        output = self.query_one("#pkg-output", RichLog)
        output.clear()
        output.write("[bold]📋 已安装包[/bold]")

        try:
            from ...integration.pkg_manager import list_installed_packages
            packages = list_installed_packages()
            count = 0
            for p in sorted(packages, key=lambda x: x.name.lower()):
                if count < 50:
                    output.write(f"  {p.name} [dim]{p.version}[/dim]")
                count += 1
            output.write(f"\n[dim]共 {count} 个包[/dim]")
            self.query_one("#pkg-status", Static).update(f"[green]{count} packages[/green]")
        except Exception as e:
            output.write(f"[red]{e}[/red]")

    @on(Button.Pressed, "#btn-env-check")
    async def on_env_check(self, event: Button.Pressed):
        output = self.query_one("#pkg-output", RichLog)
        output.write("\n[bold]🔄 检查并修复环境...[/bold]")

        try:
            from ...integration.pkg_manager import ensure_environment
            status = await ensure_environment()
            if status.all_ready:
                output.write("[green]✓ 环境就绪[/green]")
            else:
                output.write(f"[yellow]⚠ 仍有问题: {status.issues}[/yellow]")
        except Exception as e:
            output.write(f"[red]环境检查失败: {e}[/red]")
