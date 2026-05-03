"""Unified status bar — system health, budget, generation, audit."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label


class StatusBar(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label("^Q 退出  ^1-5 切标签  ^P 命令  ^D 主题", id="footer-keys")
        yield Label("", id="footer-status")
        yield Label("livingtreeai@163.com", id="footer-contact")

    def set_status(self, text: str) -> None:
        try:
            self.query_one("#footer-status", Label).update(text)
        except Exception:
            pass

    def update_system_status(self, hub=None) -> None:
        """Refresh system status from hub."""
        if not hub:
            return
        try:
            s = hub.status()
            gen = s.get("engine", {}).get("generation", "?")
            audit = s.get("audit", {})
            audit_ok = "✓" if audit.get("chain_verified") else "✗"
            node = "🟢" if s.get("network", {}).get("status") == "online" else "🔴"

            cost = hub.world.cost_aware
            budget = ""
            if cost:
                st = cost.status()
                budget = f"¥{st.cost_yuan:.4f}"

            parts = []
            if node:
                parts.append(f"{node} 节点")
            if budget:
                parts.append(f"💰 {budget}")
            if gen:
                parts.append(f"🧬 {gen}代")
            if audit:
                parts.append(f"{audit_ok} 审计")
            parts.append("🌐 在线")

            self.query_one("#footer-status", Label).update(" │ ".join(parts))
        except Exception:
            pass
