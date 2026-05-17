"""DevTUI — minimal terminal UI for project development.

Single chat panel. Type at bottom. Responses scroll up.
Status bar shows provider, tokens, latency. Ctrl+C to quit.
"""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Header, Footer, Input, Static, RichLog
from textual.binding import Binding


class DevTUI(App):
    """Minimal dev chat TUI."""

    CSS = """
    Screen { background: #0d1117; }
    Header { background: #161b22; color: #58a6ff; }
    Footer { background: #161b22; color: #8b949e; }
    #chat-log { height: 1fr; padding: 1; overflow-y: auto; }
    #chat-log Static { margin-bottom: 1; }
    .user { color: #58a6ff; }
    .assistant { color: #c9d1d9; }
    .meta { color: #484f58; text-style: italic; }
    #input-area { dock: bottom; height: auto; padding: 1; background: #161b22; border-top: solid #30363d; }
    #input { width: 100%; background: #0d1117; color: #c9d1d9; border: solid #30363d; padding: 1; }
    #status-bar { dock: bottom; height: 1; background: #161b22; color: #8b949e; padding: 0 1; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear", "Clear", show=True),
        Binding("ctrl+r", "refresh", "Refresh", show=True),
        Binding("ctrl+p", "toggle_palette", "Palette", show=False),
    ]

    def __init__(self, llm=None):
        super().__init__()
        self._llm = llm
        self._provider = "deepseek"
        self._tokens = 0
        self._total_ms = 0.0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="chat-log", highlight=True, markup=True)
        yield Static(id="status-bar")
        yield Container(
            Input(id="input", placeholder="Ask anything... (Ctrl+C to quit)"),
            id="input-area",
        )

    def on_mount(self) -> None:
        self.query_one("#chat-log", RichLog).write(
            "[bold #58a6ff]🌳 LivingTree DevTUI[/]\n"
            "[#484f58]Type a message and press Enter. Ctrl+L to clear. Ctrl+C to quit.[/]\n"
        )
        self._update_status()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if not event.value.strip():
            return
        message = event.value.strip()
        event.input.value = ""

        log = self.query_one("#chat-log", RichLog)
        log.write(f"\n[bold #58a6ff]> {message}[/]")

        # Run LLM in background
        asyncio.create_task(self._chat(message))

    async def _chat(self, message: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        try:
            if self._llm:
                import time
                t0 = time.time()
                result = await self._llm.chat(
                    [{"role": "user", "content": message}],
                    max_tokens=2048, tools=True,
                )
                self._total_ms = (time.time() - t0) * 1000
                if result and hasattr(result, 'text') and result.text:
                    self._provider = getattr(result, 'provider', '?')
                    self._tokens = getattr(result, 'tokens', 0)
                    log.write(f"[#c9d1d9]{result.text}[/]")
                else:
                    log.write("[#f85149]No response[/]")
            else:
                log.write("[#f85149]LLM not initialized. Run: livingtree start[/]")
        except Exception as e:
            log.write(f"[#f85149]Error: {e}[/]")
        self._update_status()

    def _update_status(self) -> None:
        bar = self.query_one("#status-bar", Static)
        bar.update(
            f" provider={self._provider} | tokens={self._tokens} | "
            f"{self._total_ms:.0f}ms | Ctrl+C quit | Ctrl+L clear"
        )

    def action_clear(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.clear()
        log.write("[#484f58]Cleared. Type a message.[/]\n")


def start_tui(tree_llm=None) -> None:
    """Start the minimal dev TUI."""
    app = DevTUI(tree_llm)
    app.run()
