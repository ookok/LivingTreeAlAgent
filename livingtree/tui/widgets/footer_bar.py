"""Status bar — key shortcuts + system status + animated boot steps."""
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class StatusBar(Horizontal):
    _boot_idx: int = 0
    _steps: list[str] = []
    _current_step: int = -1
    _done_steps: set[int] = set()

    def compose(self) -> ComposeResult:
        yield Label("^Q quit  Ctrl+Enter send  ^C copy  Shift+Tab effort  ^D theme", id="footer-keys")
        yield Label("", id="footer-llm")
        yield Label("", id="footer-pulse")
        yield Label("", id="error-chip")
        yield Label("", id="footer-status")

    def set_boot_steps(self, steps: list[str]) -> None:
        self._steps = steps
        self._current_step = -1
        self._done_steps = set()
        self._render_steps()

    def advance_step(self, step_idx: int, done: bool = True) -> None:
        if done and step_idx >= 0:
            self._done_steps.add(step_idx)
        self._current_step = step_idx + 1
        self._render_steps()

    def _render_steps(self) -> None:
        if not self._steps:
            return
        self._boot_idx = (self._boot_idx + 1) % len(SPINNER)
        spinner = SPINNER[self._boot_idx]

        parts = []
        for i, name in enumerate(self._steps):
            if i in self._done_steps:
                prefix = "[green]●[/green]"
            elif i == self._current_step:
                prefix = f"[bold #fea62b]{spinner}[/bold #fea62b]"
            else:
                prefix = "[dim]○[/dim]"

            if i > 0:
                if i - 1 in self._done_steps:
                    arrow = "[green]··>[/green]"
                elif i - 1 == self._current_step - 1:
                    arrow = "[bold #fea62b]··>[/bold #fea62b]"
                else:
                    arrow = "[dim]··>[/dim]"
                parts.append(arrow)
            parts.append(f"{prefix} [bold]{name}[/bold]")

        text = " ".join(parts)
        self.query_one("#footer-status", Label).update(text)

    def show_booting(self, label: str, pct: float, elapsed: float) -> None:
        self._render_steps()

    def update_mcp_health(self, healthy: int, total: int) -> None:
        try:
            chip = self.query_one("#mcp-chip", Label)
            if total == 0:
                chip.update("")
            else:
                color = "green" if healthy == total else ("yellow" if healthy > 0 else "red")
                chip.update(f"MCP [{color}]{healthy}/{total}[/{color}]")
        except Exception:
            pass

    def update_error_count(self, count: int, recent_60s: int = 0) -> None:
        try:
            chip = self.query_one("#error-chip", Label)
            if count == 0:
                chip.update("")
            else:
                color = "red" if recent_60s > 0 else "yellow"
                chip.update(f"[{color}]! {count} errors[/{color}]")
        except Exception:
            pass

    def update_llm_info(self, elected: str, count: int = 0) -> None:
        try:
            c = self.query_one("#footer-llm", Label)
            c.update(f"[#58a6ff]{elected}[/#58a6ff]" + (f" ({count})" if count else ""))
        except Exception:
            pass

    def update_pulse(self, snapshot: dict) -> None:
        try:
            c = self.query_one("#footer-pulse", Label)
            state = snapshot.get("state", "active")
            icons = {"active": "[#3fb950]●[/#3fb950]", "reflecting": "[#d29922]◉[/#d29922]",
                     "resting": "[#8b949e]○[/#8b949e]", "dreaming": "[#d2a8ff]◎[/#d2a8ff]"}
            icon = icons.get(state, "●")
            c.update(f"{icon} {state}")
        except Exception:
            pass

    def update_system_status(self, hub=None) -> None:
        try:
            self.query_one("#footer-status", Label).update("")
        except Exception:
            pass
        if not hub:
            try:
                self.query_one("#footer-status", Label).update("🟢 在线")
            except Exception:
                pass
            return
        try:
            s = hub.status()
            if not s.get("online"):
                self.query_one("#footer-status", Label).update("🟡 初始化中...")
                return
            gen = s.get("engine", {}).get("generation", "?")
            audit = s.get("audit", {})
            audit_ok = "✓" if audit.get("chain_verified") else "✗"
            node = "🟢" if s.get("network", {}).get("status") == "online" else "🔴"
            cost = hub.world.cost_aware
            budget_text = ""
            if cost:
                st = cost.status()
                budget_text = f"💰¥{st.cost_yuan:.4f}"
            parts = [f"{node}节点"]
            if budget_text:
                parts.append(budget_text)
            parts.append(f"🧬{gen}代")
            parts.append(f"{audit_ok}审计")
            self.query_one("#footer-status", Label).update(" │ ".join(parts))
        except Exception:
            self.query_one("#footer-status", Label).update("🟡 初始化中...")
