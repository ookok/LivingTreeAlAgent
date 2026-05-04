"""Status bar — Simple footer with shortcuts + stats."""
from textual.widgets import Static


class StatusBar(Static):

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)

    def update_llm_info(self, elected: str, count: int = 0) -> None:
        self._render()

    def update_pulse(self, snapshot: dict) -> None:
        self._render()
    
    def update_error_count(self, count: int, recent_60s: int = 0) -> None:
        self._render()

    def update_system_status(self, hub=None) -> None:
        self.update(
            "^Q quit  Ctrl+C copy  Ctrl+Enter send  Shift+Tab effort  ^D theme"
        )

    def set_boot_steps(self, steps: list[str]) -> None:
        pass

    def advance_step(self, step_idx: int, done: bool = True) -> None:
        pass

    def show_booting(self, label: str, pct: float, elapsed: float) -> None:
        pass

    def _render(self) -> None:
        self.update(
            "^Q quit  Ctrl+C copy  Ctrl+Enter send  Shift+Tab effort  ^D theme"
        )
