"""CodingAgentPanel — Toad agent catalog integration for code screen.

Reads Toad's 20+ agent TOML definitions, displays coding agents
with install/launch actions. Uses pkg_manager for safe installation
instead of arbitrary shell execution.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
from pathlib import Path
from typing import Optional

import tomllib

from textual import on, work
from textual.containers import VerticalScroll, Horizontal
from textual.widgets import Static, Button, RichLog
from textual.binding import Binding
from textual.message import Message

from ...integration.pkg_manager import install as pkg_install, install_from_shell, has_binary


AGENTS_DIR = Path(__file__).parent.parent / "td" / "data" / "agents"


def _parse_install_cmd(cmd: str) -> tuple[str | None, str | None]:
    """Parse a shell install command for package + provider.
    Returns (provider, package_name) or (None, None) if not parseable.
    """
    if not cmd:
        return None, None

    patterns = [
        (r'npm\s+(?:install|i)\s+(?:-g\s+)?([\w@/.-]+)', "npm"),
        (r'pip\s+(?:install|i)\s+(?:-U\s+)?([\w\[\]@.-]+)', "pip"),
        (r'uv\s+tool\s+(?:install|add)\s+([\w@/.-]+)', "uv"),
        (r'cargo\s+install\s+(?:--git\s+\S+\s+)?([\w@.-]+)', "cargo"),
        (r'brew\s+install\s+(?:--cask\s+)?([\w@/.-]+)', "brew"),
        (r'npx\s+(?:-y\s+)?([\w@/.-]+)', "npx"),
    ]
    for pat, provider in patterns:
        m = re.search(pat, cmd)
        if m:
            return provider, m.group(1).strip()
    return None, None


class AgentRunRequest(Message):
    """Request to launch an agent in the conversation."""
    def __init__(self, agent_id: str, agent_name: str):
        super().__init__()
        self.agent_id = agent_id
        self.agent_name = agent_name


class CodingAgentPanel(VerticalScroll):
    """Panel showing available coding agents from Toad's catalog."""

    BINDINGS = [
        Binding("r", "refresh", "刷新"),
    ]

    def __init__(self):
        super().__init__()
        self._agents: list[dict] = []
        self._loaded = False

    def compose(self):
        yield Static("🔧 Coding Agents", classes="panel-title")
        yield Static("", id="agent-status", classes="agent-status")

    def on_mount(self):
        self.refresh_agents()

    def action_refresh(self):
        self.refresh_agents()

    @work(thread=False)
    async def refresh_agents(self):
        agents = await asyncio.to_thread(self._load_agents)
        self._agents = agents
        self._rebuild_ui()

    def _load_agents(self) -> list[dict]:
        agents = []
        if not AGENTS_DIR.exists():
            return agents

        path: Path
        for path in sorted(AGENTS_DIR.iterdir()):
            if path.suffix not in (".toml", ""):
                continue
            try:
                with open(path, "rb") as f:
                    data = tomllib.load(f)
            except Exception:
                continue

            agent_type = data.get("type", "")
            if agent_type != "coding":
                continue

            run_cmds = data.get("run_command", {})
            actions = data.get("actions", {})

            agents.append({
                "id": data.get("identity", path.stem),
                "name": data.get("name", path.stem),
                "short_name": data.get("short_name", ""),
                "author": data.get("author_name", ""),
                "description": data.get("description", ""),
                "type": agent_type,
                "url": data.get("url", ""),
                "run_command": run_cmds.get("*", run_cmds.get(os.name, "")),
                "install_command": self._find_command(actions, "install"),
                "update_command": self._find_command(actions, "update"),
                "login_command": self._find_command(actions, "login"),
                "recommended": data.get("recommended", False),
            })

        return agents

    def _find_command(self, actions: dict, name: str) -> str:
        for os_key in ("*", os.name):
            os_actions = actions.get(os_key, {})
            if name in os_actions:
                desc = os_actions[name].get("description", "")
                cmd = os_actions[name].get("command", "")
                return cmd
        return ""

    def _rebuild_ui(self):
        children = list(self.query("AgentCard"))
        for child in children:
            child.remove()

        status = self.query_one("#agent-status", Static)
        status.update(f"[dim]{len(self._agents)} coding agents[/dim]")

        for agent in self._agents:
            self.mount(AgentCard(agent))


class AgentCard(VerticalScroll):
    """Single agent card with info and action buttons."""

    def __init__(self, agent: dict):
        super().__init__()
        self.agent = agent
        self.add_class("agent-card")

    def compose(self):
        a = self.agent
        yield Static(f"[bold]{a['name']}[/bold]  [dim]{a['author']}[/dim]", classes="card-name")
        yield Static(a["description"][:120], classes="card-desc")

        installed = self._check_installed(a)
        status_text = "[green]✓ ready[/green]" if installed else "[yellow]○ not found[/yellow]"
        yield Static(f"{status_text}  [dim]{a['short_name']}[/dim]", classes="card-status")

        with Horizontal(classes="card-actions"):
            if installed:
                yield Button("▶ Launch", id=f"launch-{a['id']}", variant="primary",
                             classes="card-btn")
            else:
                if a["install_command"]:
                    yield Button("⬇ Install", id=f"install-{a['id']}", variant="warning",
                                 classes="card-btn")

    def _check_installed(self, agent: dict) -> bool:
        run_cmd = agent.get("run_command", "")
        if not run_cmd:
            return False
        binary = run_cmd.split()[0]
        return has_binary(binary)

    @on(Button.Pressed, ".card-btn")
    async def on_action(self, event: Button.Pressed):
        agent = self.agent
        button_id = event.button.id or ""

        if button_id.startswith("launch-"):
            self.post_message(AgentRunRequest(agent["id"], agent["name"]))
            self.app.notify(f"Launching {agent['name']}...", timeout=2)

        elif button_id.startswith("install-"):
            cmd = agent.get("install_command", "")
            if not cmd:
                self.app.notify("No install command", severity="warning")
                return

            log = self.app.query_one("#command-log", RichLog) if self.app.query("#command-log") else None
            if log:
                log.write(f"[bold]Installing {agent['name']}:[/bold]\n[dim]$ {cmd}[/dim]")

            # Try safe provider-based install first
            provider, pkg_name = _parse_install_cmd(cmd)
            if provider and pkg_name:
                if log:
                    log.write(f"[dim]Using {provider} install {pkg_name}...[/dim]")
                result = pkg_install(pkg_name, providers=[provider])
                if result.installed:
                    self.app.notify(f"{agent['name']} installed via {provider}", severity="information")
                    if log:
                        log.write(f"[green]✓ Installed via {provider}[/green]")
                    self.refresh(recompose=True)
                    return
                else:
                    if log:
                        log.write(f"[yellow]Provider install failed: {result.error}. Falling back to shell...[/yellow]")

            # Fallback: safe shell execution
            code, stdout, stderr = await install_from_shell(cmd)
            if log:
                if stdout.strip():
                    log.write(stdout.strip()[:2000])
                if stderr.strip():
                    log.write(f"[red]{stderr.strip()[:1000]}[/red]")
                log.write(f"[{'green' if code == 0 else 'red'}]Exit: {code}[/]")
            if code == 0:
                self.app.notify(f"{agent['name']} installed", severity="information")
                self.refresh(recompose=True)
            else:
                self.app.notify(f"Install failed: code {code}", severity="error")
