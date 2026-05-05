"""ToolCallWidget — expandable tool call display for agent tool executions.

Renders tool name, parameters, execution status, and result.
Supports expand/collapse, status icons, and diff-like output.
"""
from __future__ import annotations

from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Collapsible
from textual.reactive import reactive
from textual.binding import Binding


class ToolCallWidget(Vertical):
    can_focus = True
    BINDINGS = [
        Binding("enter", "toggle", "展开/折叠"),
    ]

    tool_status = reactive("idle")
    tool_result = reactive("")

    def __init__(self, tool_name: str = "", tool_params: str = "", tool_id: str = ""):
        super().__init__()
        self.tool_name = tool_name
        self.tool_params = tool_params
        self.tool_id = tool_id or f"tool-{id(self)}"
        self._expanded = False

    def compose(self):
        with Horizontal(classes="tool-header"):
            yield Static("", id=f"{self.tool_id}-icon", classes="tool-icon")
            yield Static(self.tool_name, id=f"{self.tool_id}-name", classes="tool-name")
            yield Static(self.tool_params[:80], id=f"{self.tool_id}-params", classes="tool-params")
            yield Static("", id=f"{self.tool_id}-status", classes="tool-status")
        with Collapsible(title="详细输出", collapsed=True, id=f"{self.tool_id}-detail"):
            yield Static("", id=f"{self.tool_id}-output", classes="tool-output")

    def on_mount(self):
        self._update_icon()
        self.add_class("tool-call-block")

    def set_running(self):
        self.tool_status = "running"
        self._update_icon()

    def set_done(self, result: str = ""):
        self.tool_status = "done"
        self.tool_result = result
        self._update_icon()
        self.query_one(f"#{self.tool_id}-status", Static).update("[green]✓[/green]")
        if result:
            output = self.query_one(f"#{self.tool_id}-output", Static)
            output.update(result[:4096])

    def set_error(self, error: str = ""):
        self.tool_status = "error"
        self.tool_result = error
        self._update_icon()
        self.query_one(f"#{self.tool_id}-status", Static).update("[red]✗[/red]")
        if error:
            output = self.query_one(f"#{self.tool_id}-output", Static)
            output.update(f"[red]{error[:4096]}[/red]")

    def _update_icon(self):
        icons = {"idle": "🛠", "running": "⏳", "done": "✅", "error": "❌"}
        icon = icons.get(self.tool_status, "🛠")
        self.query_one(f"#{self.tool_id}-icon", Static).update(icon)

    def action_toggle(self):
        collapsible = self.query_one(f"#{self.tool_id}-detail", Collapsible)
        if collapsible.collapsed:
            collapsible.action_toggle()
        else:
            collapsible.action_toggle()

    def watch_tool_status(self, value):
        self._update_icon()
