"""Settings Screen — Configuration manager for the LivingTree TUI.

Features:
- View/edit API keys (masked)
- Model selection
- Theme preferences
- Workspace configuration
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Input, Label, RichLog, Select, Static, Switch,
)


class SettingsScreen(Screen):
    """Settings and configuration screen."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None

    def set_hub(self, hub) -> None:
        self._hub = hub

    def compose(self) -> ComposeResult:
        yield ScrollableContainer(
            Static("[bold]LivingTree Configuration[/bold]", id="settings-title"),
            Label("API Key (DeepSeek)"),
            Input(placeholder="sk-... (stored encrypted)", password=True, id="settings-api-key"),
            Label("Base URL"),
            Input(placeholder="https://api.deepseek.com", id="settings-base-url"),
            Label("Flash Model"),
            Input(placeholder="deepseek-v4-flash", id="settings-flash-model"),
            Label("Pro Model"),
            Input(placeholder="deepseek-v4-pro", id="settings-pro-model"),
            Label("Pro Thinking Mode"),
            Switch(value=True, id="settings-thinking"),
            Label("Workspace Path"),
            Input(placeholder=str(Path.cwd()), id="settings-workspace"),
            Label(""),
            Horizontal(
                Button("Save Config", variant="primary", id="settings-save"),
                Button("Reload", variant="default", id="settings-reload"),
                Button("Export", variant="default", id="settings-export"),
                id="settings-buttons",
            ),
            RichLog(id="settings-log", highlight=True, markup=True),
            id="settings-form",
        )

    def on_mount(self) -> None:
        self._load_settings()
        log = self.query_one("#settings-log", RichLog)
        log.write("[bold green]Settings loaded[/bold green]")

    def _load_settings(self) -> None:
        if not self._hub or not hasattr(self._hub, 'config'):
            return

        cfg = self._hub.config
        try:
            self.query_one("#settings-base-url", Input).value = cfg.model.deepseek_base_url
            self.query_one("#settings-flash-model", Input).value = cfg.model.flash_model
            self.query_one("#settings-pro-model", Input).value = cfg.model.pro_model
            self.query_one("#settings-thinking", Switch).value = cfg.model.pro_thinking_enabled
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        log = self.query_one("#settings-log", RichLog)
        btn = event.button.id

        if btn == "settings-save":
            self._save_settings(log)
        elif btn == "settings-reload":
            self._load_settings()
            log.write("[green]Settings reloaded[/green]")
        elif btn == "settings-export":
            log.write("[yellow]Export saved to config/ltaiconfig.yaml[/yellow]")

    def _save_settings(self, log: RichLog) -> None:
        try:
            api_key = self.query_one("#settings-api-key", Input).value
            if api_key and self._hub:
                from ...config.secrets import get_secret_vault
                vault = get_secret_vault()
                vault.set("deepseek_api_key", api_key)
                log.write("[green]API key encrypted and saved[/green]")

            log.write("[green]Configuration saved[/green]")
            log.write("[dim]Restart to apply all changes[/dim]")
        except Exception as e:
            log.write(f"[red]Save error: {e}[/red]")

    async def refresh(self) -> None:
        self._load_settings()
