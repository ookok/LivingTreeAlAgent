"""StatusBar — Footer with shortcuts and system status."""
from textual.widgets import Static


class StatusBar(Static):

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)

    def update_llm_info(self, elected: str, count: int = 0) -> None:
        pass

    def update_pulse(self, snapshot: dict) -> None:
        pass

    def update_error_count(self, count: int, recent_60s: int = 0) -> None:
        pass

    def update_system_status(self, hub=None) -> None:
        from ..i18n import t
        provider = "auto"
        oc_status = ""
        agent_status = ""
        if hub and hub.world:
            try:
                consciousness = hub.world.consciousness
                elected = getattr(consciousness._llm, '_elected', 'auto')
                provider = elected if elected else "auto"
                oc_providers = getattr(consciousness, '_opencode_cache', [])
                oc_serve = [p for p in oc_providers if p.get("source") == "opencode_serve"]
                if oc_serve:
                    oc_status = " [green]OC✓[/green]"
            except Exception:
                pass
        try:
            from ...execution.panel_agent import get_agent_manager
            mgr = get_agent_manager()
            status = mgr.get_status()
            error_count = sum(1 for s in status.values() if s["state"] == "error")
            if error_count:
                agent_status = f" [red]⚠{error_count}[/red]"
            else:
                agent_status = ""
        except Exception:
            pass
        self.update(
            t("status.keys") + f"   [#58a6ff]{t('status.llm')}: {provider}[/#58a6ff]{oc_status}{agent_status}"
        )

    def set_boot_steps(self, steps: list[str]) -> None:
        pass

    def advance_step(self, step_idx: int, done: bool = True) -> None:
        pass

    def show_booting(self, label: str, pct: float, elapsed: float) -> None:
        pass

    def _render(self) -> None:
        from ..i18n import t
        self.update(t("status.keys") + "   " + t("bind.quit", default="Ctrl+Q Quit"))
