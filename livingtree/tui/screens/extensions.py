"""Skills & MCP Management — CRUD for skills, MCP server configuration.

Supports:
- SKILL.md format: markdown with YAML frontmatter (Claude Code compatible)
- MCP JSON format: {"mcpServers": {...}} (standard config)
- Live preview and editing
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button, Input, Label, ListView, ListItem, RichLog, Select,
    TabbedContent, TabPane, TextArea, Tree,
)
from textual.widgets._tree import TreeNode


SKILL_DIR = Path("./data/skills")
MCP_CONFIG_PATH = Path("./data/mcp_servers.json")

SKILL_TEMPLATE = """---
name: {name}
description: {description}
version: "1.0"
author: "LivingTree"
tags: []
tools: []
---

# {name}

{description}

## Instructions

{instructions}

## Examples

```
# Example usage
```

## Notes

Add specific domain knowledge here.
"""

MCP_TEMPLATE = {
    "mcpServers": {
        "example-server": {
            "command": "python",
            "args": ["-m", "example.server"],
            "env": {"API_KEY": ""}
        }
    }
}


class ExtensionsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None
        self._skills_dir = SKILL_DIR
        self._mcp_path = MCP_CONFIG_PATH
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        if not self._mcp_path.exists():
            self._mcp_path.write_text(json.dumps(MCP_TEMPLATE, indent=2, ensure_ascii=False))

    def set_hub(self, hub) -> None:
        self._hub = hub

    def compose(self) -> ComposeResult:
        yield TabbedContent(
            TabPane("🧩 Skills", id="skills-tab"),
            TabPane("🔌 MCP", id="mcp-tab"),
            id="ext-tabs",
        )

    def on_mount(self) -> None:
        self._setup_skills_tab()
        self._setup_mcp_tab()

    # ── Skills tab ──

    def _setup_skills_tab(self) -> None:
        tab = self.query_one("#skills-tab", TabPane)
        tab.mount(Horizontal(
            Vertical(
                Label("📋 Skills", id="skills-title"),
                ListView(id="skills-list"),
                Horizontal(
                    Button("➕ New", variant="primary", id="skill-new"),
                    Button("🗑 Delete", variant="default", id="skill-delete"),
                    Button("🔄 Refresh", variant="default", id="skill-refresh"),
                ),
                id="skills-sidebar",
            ),
            Vertical(
                Input(placeholder="Skill name", id="skill-name"),
                TextArea("", id="skill-editor", language="markdown"),
                Horizontal(
                    Button("💾 Save", variant="primary", id="skill-save"),
                    Button("📋 Copy", variant="default", id="skill-copy"),
                    Label("", id="skill-status"),
                    id="skill-actions",
                ),
                id="skills-editor-panel",
            ),
        ))
        self._load_skills()

    def _load_skills(self) -> None:
        lst = self.query_one("#skills-list", ListView)
        lst.clear()
        for f in sorted(self._skills_dir.glob("*.md")):
            lst.append(ListItem(Label(f.stem)))
        self.query_one("#skills-title", Label).update(
            f"📋 Skills ({len(list(self._skills_dir.glob('*.md')))})")

    @on(ListView.Selected, "#skills-list")
    def on_skill_selected(self, event: ListView.Selected) -> None:
        if not event.item:
            return
        name = str(event.item.query_one(Label).renderable)
        path = self._skills_dir / f"{name}.md"
        if path.exists():
            content = path.read_text(encoding="utf-8")
            self.query_one("#skill-name", Input).value = name
            self.query_one("#skill-editor", TextArea).text = content

    @work(exclusive=False)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "skill-new":
            self._skill_new()
        elif bid == "skill-delete":
            self._skill_delete()
        elif bid == "skill-refresh":
            self._load_skills()
        elif bid == "skill-save":
            await self._skill_save()
        elif bid == "skill-copy":
            self._skill_copy()
        elif bid == "mcp-save":
            await self._mcp_save()
        elif bid == "mcp-add":
            self._mcp_add_server()
        elif bid == "mcp-remove":
            self._mcp_remove_server()

    def _skill_new(self) -> None:
        name = self.query_one("#skill-name", Input).value.strip()
        if not name:
            name = f"skill_{len(list(self._skills_dir.glob('*.md'))) + 1}"
        content = SKILL_TEMPLATE.format(
            name=name, description=f"Skill: {name}",
            instructions="Describe how to use this skill.",
        )
        self.query_one("#skill-name", Input).value = name
        self.query_one("#skill-editor", TextArea).text = content
        self.query_one("#skill-status", Label).update("[green]New skill created[/green]")

    @work(exclusive=False)
    async def _skill_save(self) -> None:
        name = self.query_one("#skill-name", Input).value.strip()
        if not name:
            self.query_one("#skill-status", Label).update("[red]Name required[/red]")
            return
        content = self.query_one("#skill-editor", TextArea).text
        path = self._skills_dir / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        self.query_one("#skill-status", Label).update(f"[green]Saved: {name}.md ({len(content)} chars)[/green]")
        self._load_skills()

    def _skill_delete(self) -> None:
        name = self.query_one("#skill-name", Input).value.strip()
        if not name:
            return
        path = self._skills_dir / f"{name}.md"
        if path.exists():
            path.unlink()
            self.query_one("#skill-status", Label).update(f"[green]Deleted: {name}.md[/green]")
        self._load_skills()

    def _skill_copy(self) -> None:
        content = self.query_one("#skill-editor", TextArea).text
        name = self.query_one("#skill-name", Input).value.strip()
        new_name = f"{name}_copy"
        path = self._skills_dir / f"{new_name}.md"
        path.write_text(content, encoding="utf-8")
        self.query_one("#skill-name", Input).value = new_name
        self.query_one("#skill-status", Label).update(f"[green]Copied to {new_name}.md[/green]")
        self._load_skills()

    # ── MCP tab ──

    def _setup_mcp_tab(self) -> None:
        tab = self.query_one("#mcp-tab", TabPane)
        tab.mount(Vertical(
            Label("🔌 MCP Servers", id="mcp-title"),
            TextArea("", id="mcp-editor", language="json"),
            Horizontal(
                Button("💾 Save", variant="primary", id="mcp-save"),
                Button("➕ Add Server", variant="default", id="mcp-add"),
                Button("🗑 Remove Server", variant="default", id="mcp-remove"),
                Label("", id="mcp-status"),
                id="mcp-actions",
            ),
        ))
        self._load_mcp()

    def _load_mcp(self) -> None:
        if self._mcp_path.exists():
            content = self._mcp_path.read_text(encoding="utf-8")
            self.query_one("#mcp-editor", TextArea).text = content
            try:
                config = json.loads(content)
                servers = list(config.get("mcpServers", {}).keys())
                self.query_one("#mcp-title", Label).update(
                    f"🔌 MCP Servers ({len(servers)}): {', '.join(servers[:5])}")
            except Exception:
                pass

    @work(exclusive=False)
    async def _mcp_save(self) -> None:
        content = self.query_one("#mcp-editor", TextArea).text
        try:
            config = json.loads(content)
            self._mcp_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
            servers = list(config.get("mcpServers", {}).keys())
            self.query_one("#mcp-status", Label).update(
                f"[green]Saved: {len(servers)} servers[/green]")
            self.query_one("#mcp-title", Label).update(
                f"🔌 MCP Servers ({len(servers)}): {', '.join(servers[:5])}")
        except json.JSONDecodeError as e:
            self.query_one("#mcp-status", Label).update(f"[red]JSON Error: {e}[/red]")

    def _mcp_add_server(self) -> None:
        content = self.query_one("#mcp-editor", TextArea).text
        try:
            config = json.loads(content)
            name = f"server-{len(config.get('mcpServers', {})) + 1}"
            config.setdefault("mcpServers", {})[name] = {
                "command": "python",
                "args": ["-m", name],
            }
            self.query_one("#mcp-editor", TextArea).text = json.dumps(config, indent=2, ensure_ascii=False)
            self.query_one("#mcp-status", Label).update(f"[green]Added: {name}[/green]")
        except Exception as e:
            self.query_one("#mcp-status", Label).update(f"[red]{e}[/red]")

    def _mcp_remove_server(self) -> None:
        content = self.query_one("#mcp-editor", TextArea).text
        try:
            config = json.loads(content)
            servers = list(config.get("mcpServers", {}).keys())
            if servers:
                del config["mcpServers"][servers[0]]
                self.query_one("#mcp-editor", TextArea).text = json.dumps(config, indent=2, ensure_ascii=False)
                self.query_one("#mcp-status", Label).update(f"[green]Removed: {servers[0]}[/green]")
        except Exception as e:
            self.query_one("#mcp-status", Label).update(f"[red]{e}[/red]")

    async def refresh(self) -> None:
        self._load_skills()
        self._load_mcp()
