"""Unified status bar — system health, budget, generation, audit.

Layout: left=shortcuts | right=status (progress when booting)
"""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class StatusBar(Horizontal):
    _boot_idx: int = 0

    def compose(self) -> ComposeResult:
        yield Label("^Q 退出  ^1-5 切标签  ^P 命令  ^D 主题", id="footer-keys")
        yield Label("", id="footer-status")

    def show_booting(self, label: str, pct: int, elapsed: float) -> None:
        self._boot_idx = (self._boot_idx + 1) % len(SPINNER)
        icon = SPINNER[self._boot_idx]
        bar_w = 18
        filled = int(bar_w * pct / 100)
        bar = f"{'█' * filled}{'░' * (bar_w - filled)}"
        text = f"{icon} {label} {pct}% [{bar}] {elapsed:.0f}s"
        try:
            self.query_one("#footer-status", Label).update(text)
        except Exception:
            pass

    def update_system_status(self, hub=None) -> None:
        if not hub:
            try:
                self.query_one("#footer-status", Label).update("🟢 在线  📧 @LivingTree")
            except Exception:
                pass
            return
        try:
            s = hub.status()
            gen = s.get("engine", {}).get("generation", "?")
            audit = s.get("audit", {})
            audit_ok = "✓" if audit.get("chain_verified") else "✗"
            node = "🟢" if s.get("network", {}).get("status") == "online" else "🔴"

            cost = hub.world.cost_aware
            budget_text = ""
            if cost:
                st = cost.status()
                budget_text = f"¥{st.cost_yuan:.4f}"

            parts = [f"{node}节点"]
            if budget_text:
                parts.append(f"💰{budget_text}")
            parts.append(f"🧬{gen}代")
            parts.append(f"{audit_ok}审计")

            self.query_one("#footer-status", Label).update(" │ ".join(parts))
        except Exception:
            pass
