"""ModelSelector — Toad widget for browsing and enabling LLM models.

Displays all available models across all providers, sorted by model name.
Groups identical models from different providers together.
Shows pricing mode (free/token/paid) and source provider badges.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, Button

from ...treellm.model_registry import ModelRegistry, ModelInfo


class ModelSelector(VerticalScroll):
    """Model browser with sorting, pricing badges, and source labels."""

    def __init__(self):
        super().__init__()
        self._registry = ModelRegistry.instance()

    def compose(self) -> ComposeResult:
        yield Static("", id="model-list-area")
        yield Button("🔄 刷新模型列表", id="btn-refresh-all", variant="primary")

    def on_mount(self):
        self._refresh_display()

    def on_button_pressed(self, event):
        if event.button.id == "btn-refresh-all":
            self.action_refresh()

    def _get_api_key(self, provider: str) -> str:
        try:
            from ...config.secrets import get_secret_vault
            vault = get_secret_vault()
            if vault:
                return vault.get(f"{provider}_api_key", "")
        except Exception:
            pass
        return ""

    def _refresh_display(self):
        if not self._registry:
            return

        container = self.query_one("#model-list-area", Static)
        lines = []

        all_models: list[ModelInfo] = []
        for name in self._registry.get_all_providers():
            p = self._registry._providers.get(name)
            if not p or not p.models:
                continue
            all_models.extend(p.models)

        if not all_models:
            container.update("[dim]点击刷新按钮拉取模型列表[/dim]")
            return

        name_groups: dict[str, list[ModelInfo]] = {}
        for m in all_models:
            key = m.short_name.lower()
            name_groups.setdefault(key, []).append(m)

        shown = 0
        for model_name, group in sorted(name_groups.items()):
            unique_providers = list(dict.fromkeys(m.provider for m in group))
            best = group[0]
            pricing_icon = best.pricing_label
            tier_icon = {"flash": "⚡", "reasoning": "🧠", "small": "🪶",
                         "code": "💻", "pro": "🚀", "embedding": "📊",
                         "chat": "💬"}.get(best.tier, "📦")

            sources = " ".join(
                f"[dim]{p.upper()}[/dim]" for p in unique_providers[:5]
            )

            enabled = any(m.enabled for m in group)
            color = "bold #3fb950" if enabled else "dim"

            lines.append(
                f"[{color}]• {model_name}[/{color}] "
                f"[dim]{tier_icon}[/dim] {pricing_icon}  {sources}"
            )
            shown += 1

        lines.insert(0, f"[bold #58a6ff]MODELS[/bold #58a6ff]  "
                     f"[dim]{shown} unique from {len(all_models)} entries "
                     f"({len(self._registry._providers)} providers)[/dim]")
        lines.append("")
        lines.append("[dim]🆓=free  💰=token  💳=paid  ⚡=flash  🧠=reasoning  🚀=pro[/dim]")

        container.update("\n".join(lines))

    def action_refresh(self):
        self.query_one("#btn-refresh-all", Button).press()
