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
from rich.highlighter import ReprHighlighter
from rich.console import Console, RenderableType
from rich.text import Text
from rich.style import Style
from rich.panel import Panel
from rich.table import Table as RichTable
from io import StringIO


STYLES = {
    "user": Style(color="#3fb950", bold=True),
    "thinking": Style(color="#d2a8ff"),
    "assistant": Style(color="#58a6ff", bold=True),
    "code": Style(color="#79c0ff"),
    "tool": Style(color="#fea62b"),
    "error": Style(color="#f85149", bold=True),
    "system": Style(color="#8b949e"),
    "clarification": Style(color="#fea62b", bold=True),
}


class ChatMessage:
    """A single message in the conversation."""

    def __init__(self, role: str, content: str = ""):
        self.role = role
        self.content = content
        self.collapsed = False
        self.rendered: list[str] = []
        self.timestamp = None
        from datetime import datetime
        self.timestamp = datetime.now().strftime("%H:%M")

    def append(self, text: str) -> None:
        self.content += text

    def render_lines(self, width: int) -> list[Strip]:
        text = self._format()
        if not text:
            return [Strip.blank(max(width, 1))]
        from rich.console import Console as RichConsole
        strips = []
        try:
            console = RichConsole(
                file=StringIO(), force_terminal=False,
                width=max(width, 20), color_system="truecolor"
            )
            render_iter = console.render_lines(text, pad=False)
            for rich_segments in render_iter:
                segs = []
                for s in rich_segments:
                    style = s.style if s.style else Style()
                    segs.append(Segment(s.text, style))
                strips.append(Strip(segs) if segs else Strip.blank(max(width, 1)))
        except Exception:
            for line in str(text).split("\n"):
                strips.append(Strip([Segment(line, Style())]))
        return strips

    def _format(self) -> RenderableType:
        if self.collapsed:
            return Text(f"💭 {len(self.content)} chars (click to expand)", style=STYLES["thinking"])

        if self.role == "user":
            try:
                md = Markdown(self.content)
                return Panel(md, border_style="#3fb950", title="You", title_align="left")
            except Exception:
                return Panel(Text(self.content, style=Style(color="#c9d1d9")),
                           border_style="#3fb950", title="You", title_align="left")
        elif self.role == "thinking":
            return Text(f"💭 Thinking:\n{self.content[-500:]}", style=STYLES["thinking"])
        elif self.role == "tool":
            return Text(f"🔧 {self.content}", style=STYLES["tool"])
        elif self.role == "clarification":
            return Panel(
                Text(f"❓ {self.content}", style=STYLES["clarification"]),
                border_style="orange1",
                title="Needs Clarification",
            )
        elif self.role == "error":
            return Text(f"✗ {self.content}", style=STYLES["error"])
        elif self.role == "assistant":
            return self._render_assistant()
        elif self.role == "system":
            try:
                return Text.from_markup(self.content)
            except Exception:
                try:
                    return ReprHighlighter()(self.content)
                except Exception:
                    return Text(self.content, style=Style(color="#c9d1d9"))
        else:
            if self.content.strip().startswith("[") and "[/" in self.content:
                try:
                    return Text.from_markup(self.content)
                except Exception:
                    pass
            # Standard markdown → use Markdown renderer
            try:
                return Markdown(self.content)
            except Exception:
                try:
                    return ReprHighlighter()(self.content)
                except Exception:
                    return Text(self.content, style=Style(color="#c9d1d9"))

    def _render_assistant(self) -> RenderableType:
        try:
            md = Markdown(self.content)
            return Panel(md, border_style="#58a6ff", title="AI", title_align="left")
        except Exception:
            return Panel(Text(self.content), border_style="#58a6ff", title="AI", title_align="left")


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
        self._streaming = False
        self._spinner_idx = 0
        self._status_text = ""

    def set_streaming(self, active: bool) -> None:
        self._streaming = active
        self._dirty = True
        self.refresh()

    def set_status(self, text: str) -> None:
        self._status_text = text
        self._dirty = True
        self.refresh()

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
        # Quick pattern detection (no LLM needed for obvious cases)
        lower = text.lower()
        if any(kw in lower for kw in ["哪个", "which one", "clarify", "澄清", "you mean", "你是说", 
                                        "请确认", "confirm", "还是", "or would you"]):
            if "?" in text or "？" in text:
                return "clarification"
        try:
            import asyncio
            result = asyncio.run(
                self._consciousness.chain_of_thought(
                    f"Classify with ONE word (markdown/code/thinking/clarification/tool/error/plain):\n{text[:300]}",
                    steps=1, max_tokens=10, temperature=0.1
                )
            )
            for label in ["clarification", "markdown", "code", "thinking", "tool", "error"]:
                if label in result.lower():
                    return "assistant" if label == "markdown" else label
        except Exception:
            pass
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
            self.scroll_end(animate=False)

    def update_last_content(self, content: str) -> None:
        if self._messages:
            self._messages[-1].content = content
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
        spinner = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

        for i, msg in enumerate(self._messages):
            lines = msg.render_lines(width - 8)
            ts = msg.timestamp or ""
            for j, line in enumerate(lines):
                if j == 0:
                    prefix = f"[dim]{ts}[/dim] "
                else:
                    prefix = "     "
                if self._streaming and i == len(self._messages) - 1 and msg.role in ("assistant",):
                    prefix += f"[#d2a8ff]{spinner[self._spinner_idx % 10]}[/#d2a8ff] "
                else:
                    prefix += "  "
                strips.append(Strip([Segment(prefix, Style())]) + line)

        if self._status_text:
            strips.append(Strip.blank(width))
            strips.append(Strip([Segment(self._status_text, Style(color="#484f58"))]))

        self._lines = strips
        self._spinner_idx += 1
        self._dirty = False
