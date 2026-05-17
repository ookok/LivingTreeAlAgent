"""DevTUI — minimal terminal UI with bubble messages, streaming, markdown, code highlight.

Features:
  - Bubble messages (user/assistant with colors)
  - Streaming output (tokens appear in real-time)
  - Markdown rendering (Rich Markdown)
  - Code syntax highlighting (Rich Syntax)
  - Diff view
  - Multi-task status bar
"""

from __future__ import annotations

import asyncio
import re

from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text
from rich.console import RenderableType
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Horizontal
from textual.widgets import Header, Footer, Input, Static
from textual.widget import Widget
from textual.binding import Binding
from textual.reactive import reactive
from textual.message import Message
from loguru import logger


class ChatBubble(Widget):
    """A single chat bubble — user or assistant."""

    DEFAULT_CSS = """
    ChatBubble { width: 100%; padding: 0 1; margin: 1 0; }
    ChatBubble.user { align: right; }
    ChatBubble.assistant { align: left; }
    """

    def __init__(self, content: str, role: str = "assistant", **kwargs):
        super().__init__(**kwargs)
        self.content = content
        self.role = role
        self.add_class(role)

    def render(self) -> RenderableType:
        if self.role == "user":
            return Panel(
                Text(self.content, style="bold #58a6ff"),
                border_style="#30363d",
                title="You",
                title_align="right",
                width=min(len(self.content) + 8, 100),
            )
        # Assistant: render markdown
        return Panel(
            Markdown(self.content, code_theme="github-dark"),
            border_style="#238636",
            title="🌳 小树",
            title_align="left",
        )


class StreamingBubble(Widget):
    """A bubble that streams content in real-time."""

    DEFAULT_CSS = """
    StreamingBubble { width: 100%; padding: 0 1; margin: 1 0; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._text = ""

    def append(self, token: str):
        self._text += token
        self.refresh()

    def render(self) -> RenderableType:
        return Panel(
            Markdown(self._text or "▊", code_theme="github-dark"),
            border_style="#238636",
            title="🌳 小树",
            title_align="left",
        )

    @property
    def text(self) -> str:
        return self._text


class TaskBar(Widget):
    """Multi-task status display."""

    DEFAULT_CSS = """
    TaskBar { height: auto; padding: 0 1; background: #161b22; border-top: solid #30363d; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tasks: list[dict] = []

    def update_task(self, task_id: str, status: str, detail: str = ""):
        found = False
        for t in self._tasks:
            if t["id"] == task_id:
                t["status"] = status
                t["detail"] = detail
                found = True
                break
        if not found and len(self._tasks) < 5:
            self._tasks.append({"id": task_id, "status": status, "detail": detail})
        self.refresh()

    def render(self) -> RenderableType:
        if not self._tasks:
            return Text("")
        parts = []
        for t in self._tasks:
            icon = {"running": "🔄", "done": "✅", "failed": "❌", "pending": "⏳"}.get(t["status"], "•")
            parts.append(f"{icon} {t['id'][:20]}")
            if t["detail"]:
                parts[-1] += f" ({t['detail'][:30]})"
        return Text(" │ ".join(parts), style="#8b949e")


class DevTUI(App):
    """Minimal dev chat TUI with streaming and markdown."""

    CSS = """
    Screen { background: #0d1117; }
    Header { background: #161b22; color: #58a6ff; }
    #chat-scroll { height: 1fr; overflow-y: auto; }
    #input-area { dock: bottom; height: auto; padding: 1; background: #161b22; border-top: solid #30363d; }
    #input { width: 100%; background: #0d1117; color: #c9d1d9; border: solid #30363d; padding: 1; }
    #status-bar { dock: bottom; height: 1; background: #161b22; color: #8b949e; padding: 0 1; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+d", "show_diff", "Diff"),
        Binding("ctrl+t", "toggle_tasks", "Tasks"),
    ]

    def __init__(self, llm=None):
        super().__init__()
        self._llm = llm
        self._provider = "deepseek"
        self._tokens = 0
        self._total_ms = 0.0
        self._message_count = 0
        self._task_bar = TaskBar(id="task-bar")
        self._streaming: StreamingBubble | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(id="chat-scroll")
        yield self._task_bar
        yield Static(id="status-bar")
        yield Container(Input(id="input", placeholder="Ask anything... (Ctrl+C quit, Ctrl+D diff)"), id="input-area")

    def on_mount(self) -> None:
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.mount(ChatBubble(
            "Type a message and press Enter.\n\n"
            "**Features:** streaming • markdown • code highlight • diff view\n"
            "`Ctrl+L` clear • `Ctrl+D` diff • `Ctrl+C` quit",
            role="assistant",
        ))
        self._update_status()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if not event.value.strip():
            return
        message = event.value.strip()
        event.input.value = ""
        self._message_count += 1

        scroll = self.query_one("#chat-scroll", VerticalScroll)
        # User bubble
        scroll.mount(ChatBubble(message, role="user"))

        # Streaming assistant bubble
        self._streaming = StreamingBubble()
        scroll.mount(self._streaming)
        scroll.scroll_end(animate=False)

        self._task_bar.update_task(f"msg{self._message_count}", "running", "thinking...")

        asyncio.create_task(self._stream_chat(message))

    async def _stream_chat(self, message: str) -> None:
        if not self._llm:
            self._streaming.append("\n❌ LLM not initialized.")
            return

        import time
        t0 = time.time()
        collected = []

        try:
            p = self._llm._resolve_provider(self._provider)
            if not p:
                p = self._llm._resolve_provider("deepseek")
            if p:
                async for token in p.stream(
                    [{"role": "user", "content": message}],
                    temperature=0.3, max_tokens=2048, model="deepseek-v4-flash",
                ):
                    if isinstance(token, str) and token:
                        collected.append(token)
                        self._streaming.append(token)
                self._total_ms = (time.time() - t0) * 1000
                self._streaming.append("")  # Final refresh
            else:
                self._streaming.append("\n❌ No provider available.")
        except Exception as e:
            self._streaming.append(f"\n❌ {e}")

        self._task_bar.update_task(f"msg{self._message_count}", "done",
                                   f"{len(''.join(collected))} chars")
        self._update_status()

    def _update_status(self) -> None:
        bar = self.query_one("#status-bar", Static)
        bar.update(
            f" provider={self._provider} | "
            f"{self._total_ms:.0f}ms | "
            f"Ctrl+C quit | Ctrl+L clear | Ctrl+D diff"
        )

    async def action_show_diff(self) -> None:
        """Show git diff in the chat."""
        try:
            from livingtree.treellm.unified_exec import run_sync
            result = run_sync("git diff --stat", timeout=10)
            diff_text = result.stdout[:5000] or "(no changes)"

            scroll = self.query_one("#chat-scroll", VerticalScroll)
            scroll.mount(ChatBubble(
                f"**Git Diff**\n```diff\n{diff_text}\n```",
                role="assistant",
            ))
        except Exception as e:
            scroll = self.query_one("#chat-scroll", VerticalScroll)
            scroll.mount(ChatBubble(f"Diff error: {e}", role="assistant"))

    def action_clear(self) -> None:
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        for child in list(scroll.children):
            if not isinstance(child, ChatBubble):
                child.remove()
        scroll.mount(ChatBubble("Cleared. Type a message.", role="assistant"))

    def action_toggle_tasks(self) -> None:
        tb = self.query_one("#task-bar", TaskBar)
        tb.display = not tb.display
