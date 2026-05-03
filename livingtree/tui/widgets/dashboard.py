"""Status dashboard widget for system overview."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Container
from textual.widgets import Static, Label


class StatusCard(Static):
    """A single metric card showing label + value."""

    def __init__(self, label: str, value: str = "", color: str = "green", **kwargs):
        super().__init__(**kwargs)
        self._label = label
        self._value = value
        self._color = color

    def render(self) -> str:
        return f"[bold {self._color}]{self._label}[/bold {self._color}]\n[{self._color}]{self._value}[/{self._color}]"

    def update_value(self, value: str) -> None:
        self._value = value
        self.refresh()


class StatusDashboard(Static):
    """System status overview with metric cards.

    Shows: engine generation, cell count, knowledge docs,
    network status, budget, audit integrity.
    """

    def __init__(self, hub: Any = None, **kwargs):
        super().__init__(**kwargs)
        self._hub = hub

    def compose(self) -> ComposeResult:
        yield Container(
            Static("[bold]System Status[/bold]", id="dash-title"),
            Horizontal(
                StatusCard("Generation", "1", "green"),
                StatusCard("Cells", "0", "blue"),
                StatusCard("Knowledge", "0 docs", "yellow"),
                id="dash-row1",
            ),
            Horizontal(
                StatusCard("Node", "offline", "magenta"),
                StatusCard("Budget", "0/1M", "cyan"),
                StatusCard("Audit", "not verified", "red"),
                id="dash-row2",
            ),
        )

    def refresh_cards(self, status: dict) -> None:
        try:
            self.query_one("#dash-row1").query(StatusCard)[0].update_value(
                str(status.get("engine", {}).get("generation", "?")))
            self.query_one("#dash-row1").query(StatusCard)[1].update_value(
                str(status.get("cells", 0)))
            self.query_one("#dash-row1").query(StatusCard)[2].update_value(
                str(status.get("knowledge", {}).get("documents", 0)))
            self.query_one("#dash-row2").query(StatusCard)[0].update_value(
                status.get("network", {}).get("status", "?"))
            self.query_one("#dash-row2").query(StatusCard)[1].update_value(
                f"{status.get('budget', {}).get('used', 0)}/{status.get('budget', {}).get('limit', '?')}")
            self.query_one("#dash-row2").query(StatusCard)[2].update_value(
                "verified" if status.get("audit_ok") else "pending")
        except Exception:
            pass
