"""ChatView — Custom scrollable AI conversation widget.

Extends ScrollView directly. Stores typed messages and renders them.
No RichLog dependency. Full control over rendering pipeline.

Message types: user, thinking, assistant, code, tool, error, system.
Streaming: append tokens to the last message in real-time.
Markdown: uses Rich's Markdown renderer for assistant messages.
"""

from __future__ import annotations

from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.geometry import Size
from rich.segment import Segment
from rich.style import Style

from rich.markdown import Markdown
from rich.console import Console, RenderableType
from rich.text import Text
from rich.style import Style
from rich.panel import Panel
from io import StringIO


STYLES = {
    "user": Style(color="#3fb950", bold=True),
    "thinking": Style(color="#d2a8ff"),
    "assistant": Style(color="#58a6ff", bold=True),
    "code": Style(color="#79c0ff"),
    "tool": Style(color="#fea62b"),
    "error": Style(color="#f85149", bold=True),
    "system": Style(color="#8b949e"),
}


class ChatMessage:
    """A single message in the conversation."""

    def __init__(self, role: str, content: str = ""):
        self.role = role
        self.content = content
        self.collapsed = False
        self.rendered: list[str] = []

    def append(self, text: str) -> None:
        self.content += text

    def render_lines(self, width: int) -> list[Strip]:
        text = self._format()
        if not text:
            return []
        from rich.console import Console as RichConsole
        console = RichConsole(
            file=StringIO(), force_terminal=False,
            width=max(width, 20), color_system="truecolor"
        )
        strips = []
        try:
            render_iter = console.render(text)
            for line_output in render_iter:
                segments = console.render(line_output)
                for segment in segments:
                    seg_text = segment.text
                    seg_style = segment.style or Style()
                    strips.append(Strip([Segment(seg_text, seg_style)]))
        except Exception:
            fallback = str(text).split("\n")
            for line in fallback:
                if line:
                    strips.append(Strip([Segment(line, Style())]))
        return strips

    def _format(self) -> RenderableType:
        if self.collapsed:
            return Text(f"💭 {len(self.content)} chars (click to expand)", style=STYLES["thinking"])

        if self.role == "user":
            return Text(f"You: {self.content}", style=STYLES["user"])
        elif self.role == "thinking":
            return Text(f"💭 Thinking:\n{self.content[-500:]}", style=STYLES["thinking"])
        elif self.role == "tool":
            return Text(f"🔧 {self.content}", style=STYLES["tool"])
        elif self.role == "error":
            return Text(f"✗ {self.content}", style=STYLES["error"])
        elif self.role == "assistant":
            return self._render_assistant()
        else:
            try:
                return Text.from_markup(self.content)
            except Exception:
                return Text(self.content, style=STYLES["system"])

    def _render_assistant(self) -> RenderableType:
        text = self.content
        parts = []
        # Split by code blocks
        import re
        segments = re.split(r'(```\w*\n.*?```)', text, flags=re.DOTALL)
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            if seg.startswith("```") and seg.endswith("```"):
                lines = seg.split("\n")
                lang = lines[0][3:].strip()
                code = "\n".join(lines[1:-1])
                label = f"[bold #79c0ff]{lang or 'code'}:[/bold #79c0ff]\n" if lang else ""
                parts.append(Text.assemble(
                    (label, Style(color="#79c0ff", bold=True)),
                    (code, Style(color="#c9d1d9")),
                ))
            else:
                try:
                    parts.append(Markdown(seg))
                except Exception:
                    parts.append(Text(seg, style=Style(color="#c9d1d9")))

        from rich.table import Table as RichTable
        if len(parts) == 1:
            return parts[0]
        table = RichTable.grid()
        for p in parts:
            table.add_row(p)
        return table


class ChatView(ScrollView):
    """Custom chat display widget with typed message rendering."""

    DEFAULT_CSS = """
    ChatView {
        background: #0d1117;
        border: solid #30363d;
        &:focus { border: solid #58a6ff; }
    }
    """

    def __init__(self, consciousness=None, **kwargs):
        super().__init__(**kwargs)
        self._messages: list[ChatMessage] = []
        self._lines: list[Strip] = []
        self._dirty = True
        self.can_focus = False
        self._consciousness = consciousness

    # ── Public API ──

    def add_message(self, role: str, content: str = "") -> ChatMessage:
        if role == "assistant" and self._consciousness:
            role = self._classify_format(content[:500])
        msg = ChatMessage(role, content)
        self._messages.append(msg)
        self._dirty = True
        self.refresh()
        return msg

    def _classify_format(self, text: str) -> str:
        try:
            import asyncio
            result = asyncio.run(
                self._consciousness.chain_of_thought(
                    f"Classify this content format with ONE word (markdown/code/thinking/tool_output/error/plain):\n{text[:300]}",
                    steps=1, max_tokens=10, temperature=0.1
                )
            )
            for label in ["markdown", "code", "thinking", "tool_output", "error"]:
                if label in result.lower():
                    return "assistant" if label == "markdown" else label
        except Exception:
            pass
        if "```" in text:
            return "assistant"
        return "assistant"

    # ── Public API ──

    def add_message(self, role: str, content: str = "") -> ChatMessage:
        msg = ChatMessage(role, content)
        self._messages.append(msg)
        self._dirty = True
        self.refresh()
        return msg

    def thinking_block(self) -> ChatMessage:
        return self.add_message("thinking")

    def user_message(self, text: str) -> ChatMessage:
        return self.add_message("user", text)

    def assistant_message(self, text: str = "") -> ChatMessage:
        return self.add_message("assistant", text)

    def write(self, text: str, scroll_end: bool = False) -> None:
        if text.strip():
            msg = ChatMessage("system", text)
            self._messages.append(msg)
            self._dirty = True
            self.refresh()

    def clear(self) -> None:
        self._messages.clear()
        self._lines.clear()
        self._dirty = True
        self.refresh()

    def last_message(self) -> ChatMessage | None:
        return self._messages[-1] if self._messages else None

    # ── ScrollView interface ──

    def render_line(self, y: int) -> Strip:
        self._ensure_rendered()
        if 0 <= y < len(self._lines):
            return self._lines[y]
        return Strip.blank(self.size.width)

    @property
    def virtual_size(self) -> Size:
        self._ensure_rendered()
        width = max((len(l) for l in self._lines), default=1)
        return Size(width, max(len(self._lines), 1))

    # ── Internal ──

    def _ensure_rendered(self) -> None:
        if not self._dirty:
            return
        width = max(self.size.width, 40)
        strips = []
        for msg in self._messages:
            lines = msg.render_lines(width)
            strips.extend(lines)
        self._lines = strips
        self._dirty = False
