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
        yield Label("^Q 退出  Tab切换  Enter进入  ^D 主题", id="footer-keys")
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
