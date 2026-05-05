"""NeonConversation + NeonPrompt — Toad-CSS-compatible chat using our hub."""
from __future__ import annotations

import asyncio
from datetime import datetime

from textual import on
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.widgets import RichLog, Static, TextArea
from textual.binding import Binding
from textual.message import Message


class NeonPrompt(Vertical):
    """Matches Toad's Prompt CSS structure."""

    class PromptSubmitted(Message):
        def __init__(self, text: str):
            super().__init__()
            self.text = text

    BINDINGS = [
        Binding("ctrl+enter", "submit", "发送"),
    ]

    def compose(self):
        with Vertical(id="prompt-container"):
            with Horizontal(id="text-prompt"):
                yield Static("❯", id="prompt")
                yield TextArea(id="prompt-input")
        with Horizontal(id="info-container"):
            yield Static("Neon", id="agent-info")
            yield Static("", id="status-line")
            yield Static("", id="mode-info")

    def on_mount(self):
        self.query_one("#prompt-input", TextArea).focus()

    def focus_input(self):
        self.query_one("#prompt-input", TextArea).focus()

    def action_submit(self):
        input_widget = self.query_one("#prompt-input", TextArea)
        text = input_widget.text.strip()
        if text:
            input_widget.text = ""
            input_widget.focus()
            self.post_message(self.PromptSubmitted(text))


class NeonConversation(Vertical):
    """Matches Toad's Conversation CSS structure."""

    BINDINGS = [
        Binding("esc,esc", "cancel", "取消"),
    ]

    def __init__(self, hub=None):
        super().__init__()
        self._hub = hub
        self._thinking = False
        self._cancel_flag = False

    def compose(self):
        with VerticalScroll(id="window"):
            yield RichLog(
                id="contents",
                highlight=True,
                markup=True,
                wrap=True,
            )
        yield NeonPrompt(id="prompt-area")

    def on_mount(self):
        self.query_one("#contents", RichLog).write(
            "[dim #8b949e]🌳 LivingTree AI Agent[/]"
        )
        self.query_one(NeonPrompt).focus_input()

    def set_hub(self, hub):
        self._hub = hub

    @property
    def hub(self):
        if self._hub:
            return self._hub
        app = getattr(self, 'app', None)
        if app:
            return getattr(app, 'hub', None)
        return None

    def action_cancel(self):
        if self._thinking:
            self._cancel_flag = True

    @on(NeonPrompt.PromptSubmitted)
    async def on_prompt_submitted(self, event: NeonPrompt.PromptSubmitted):
        await self._process_prompt(event.text)

    async def _process_prompt(self, text: str):
        if self._thinking:
            return

        contents = self.query_one("#contents", RichLog)
        contents.write(f"[bold #3fb950]❯[/bold #3fb950] {text}")

        self._thinking = True
        self._cancel_flag = False

        hub = self.hub
        if not hub or not hub.world:
            contents.write("[#f85149]Engine not ready[/#f85149]")
            self._thinking = False
            return

        try:
            messages = [
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": text},
            ]
            llm = hub.world.consciousness._llm
            provider = getattr(llm, 'elected_provider', 'deepseek')

            buffer = ""
            async for token in llm.stream(
                messages=messages,
                provider=provider,
                temperature=0.3,
                max_tokens=8192,
            ):
                if self._cancel_flag:
                    break
                buffer += token
                if token.endswith("\n") or len(buffer) > 200:
                    contents.write(buffer.rstrip())
                    buffer = ""

            if buffer.strip():
                contents.write(buffer.rstrip())

            if self._cancel_flag:
                contents.write("[yellow]⚠ Cancelled[/yellow]")

        except asyncio.TimeoutError:
            contents.write("[#f85149]Request timeout[/#f85149]")
        except Exception as e:
            contents.write(f"[#f85149]Error: {e}[/#f85149]")
        finally:
            self._thinking = False
