"""ModelSelector — browse, filter, and select models from all providers."""
from __future__ import annotations

from textual import on, work
from textual.containers import VerticalScroll, Horizontal
from textual.widgets import Static, Button, Collapsible, RichLog
from textual.binding import Binding
from textual.message import Message


class ModelSelected(Message):
    """A model was selected by the user."""
    def __init__(self, provider: str, model_id: str, tier: str):
        super().__init__()
        self.provider = provider
        self.model_id = model_id
        self.tier = tier


class ModelSelector(VerticalScroll):
    """Scrollable panel showing available models grouped by provider+tier."""

    BINDINGS = [
        Binding("r", "refresh", "刷新模型"),
    ]

    def __init__(self):
        super().__init__()
        self._registry = None
        self._selected: dict[str, str] = {}  # provider:tier → model_id

    def compose(self):
        yield Static("🔬 模型管理", classes="panel-title")
        yield Static("", id="model-status")
        yield Button("🔄 刷新所有平台模型", id="btn-refresh-all", variant="primary")
        yield Static("", id="model-list-area")

    def on_mount(self):
        self._load_registry()

    def _load_registry(self):
        try:
            from ...treellm.model_registry import get_model_registry
            self._registry = get_model_registry()
            self._refresh_display()
        except Exception as e:
            self.query_one("#model-status", Static).update(f"[red]{e}[/red]")

    @on(Button.Pressed, "#btn-refresh-all")
    async def on_refresh_all(self, event: Button.Pressed):
        event.button.disabled = True
        event.button.label = "⏳ 刷新中..."
        self.query_one("#model-status", Static).update("[yellow]正在从各平台拉取模型列表...[/yellow]")

        await self._do_refresh()

        event.button.label = "🔄 刷新所有平台模型"
        event.button.disabled = False
        self._refresh_display()

    @work(thread=False)
    async def _do_refresh(self):
        if not self._registry:
            return
        self._registry.register_provider(
            "siliconflow", "https://api.siliconflow.cn/v1",
            self._get_key("siliconflow")
        )
        self._registry.register_provider(
            "mofang", "https://ai.gitee.com/v1",
            self._get_key("mofang")
        )
        self._registry.register_provider(
            "deepseek", "https://api.deepseek.com/v1",
            self._get_key("deepseek")
        )
        await self._registry.refresh_all()

        # Also discover opencode models
        try:
            from ...integration.opencode_bridge import OpenCodeBridge
            bridge = OpenCodeBridge()
            oc_models = bridge.discover_providers()
            if oc_models:
                self._registry.register_provider("opencode", "", "")
                oc_data = self._registry._providers.get("opencode")
                if oc_data:
                    from ...treellm.model_registry import ModelInfo
                    for m in oc_models:
                        oc_data.models.append(ModelInfo(
                            id=m.get("model", m.get("name", "")),
                            provider="opencode",
                            owned_by=m.get("name", "opencode"),
                            free=True,
                            tier=m.get("tier", "flash"),
                        ))
        except Exception:
            pass

        stats = self._registry.get_stats()
        total = sum(s["models"] for s in stats.values())
        self.query_one("#model-status", Static).update(
            f"[green]✓ 已刷新 {len(stats)} 个平台，共 {total} 个模型[/green]"
        )

    def _get_key(self, provider: str) -> str:
        try:
            from ...config.secrets import get_secret_vault
            vault = get_secret_vault()
            return vault.get(f"{provider}_api_key", "")
        except Exception:
            return ""

    def _refresh_display(self):
        if not self._registry:
            return

        container = self.query_one("#model-list-area", Static)
        lines = []

        for name in self._registry.get_all_providers():
            p = self._registry._providers.get(name)
            if not p or not p.models:
                continue

            tiers = {}
            for m in p.models:
                if not m.free:
                    continue
                tiers.setdefault(m.tier, []).append(m)

            if not tiers:
                continue

            lines.append(f"[bold #58a6ff]{name.upper()}[/bold #58a6ff]  "
                         f"[dim]{len(p.models)} models, {sum(len(v) for v in tiers.values())} free[/dim]")

            for tier in ["flash", "reasoning", "small", "code", "pro"]:
                if tier not in tiers:
                    continue
                models = tiers[tier][:8]  # show top 8 per tier
                model_list = "  ".join(
                    f"[{'bold #3fb950' if m.enabled else 'dim'}]• {m.id.split('/')[-1]}[/{'bold #3fb950' if m.enabled else 'dim'}]"
                    for m in models
                )
                tier_icon = {"flash": "⚡", "reasoning": "🧠", "small": "🪶",
                             "code": "💻", "pro": "🚀"}.get(tier, "📦")
                lines.append(f"  {tier_icon} {tier}: {model_list}")

            lines.append("")

        container.update("\n".join(lines) if lines else "[dim]点击刷新按钮拉取模型列表[/dim]")

    def action_refresh(self):
        self.query_one("#btn-refresh-all", Button).press()
