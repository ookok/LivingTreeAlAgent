"""Message List — Dynamic widget-based chat rendering.

Replaces RichLog with per-message widgets. Each message type has
its own rendering logic: markdown, thinking, code, files, errors.

Benefits: proper markdown per message, collapsible blocks, code highlighting,
better performance (incremental updates), clean type-based rendering.
"""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button, TextArea
from textual.scroll_view import ScrollView


class ChatMessage(Static):
    """Base message widget."""

    def __init__(self, content: str, role: str = "system", **kwargs):
        super().__init__(content, **kwargs)
        self._role = role
        self._content = content

    def append_text(self, text: str) -> None:
        self._content += text
        self.update(self._content)


class ThinkingBlock(Static):
    """Collapsible thinking/reasoning display."""

    def __init__(self, content: str = "", collapsed: bool = False, **kwargs):
        super().__init__("", **kwargs)
        self._thinking = content
        self._collapsed = collapsed
        self._render()

    def append(self, text: str) -> None:
        self._thinking += text
        self._render()

    def toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._render()

    def _render(self) -> None:
        if self._collapsed:
            self.update(f"[#d2a8ff]💭 Thought for {len(self._thinking)} chars (click to expand)[/#d2a8ff]")
        else:
            self.update(f"[#d2a8ff]💭 Thinking:[/#d2a8ff]\n{self._thinking[-500:]}")


class MessageList(Vertical, can_focus=False):
    """Scrollable message list with dynamic widget management."""

    MAX_MESSAGES = 100

    def compose(self) -> ComposeResult:
        yield Static("[dim]No messages yet[/dim]", id="msg-placeholder")

    def add_message(self, content: str, role: str = "system") -> Static:
        try:
            self.query_one("#msg-placeholder", Static).remove()
        except Exception:
            pass

        label = {
            "user": "[#3fb950]You:[/#3fb950] ",
            "assistant": "[#58a6ff]AI:[/#58a6ff] ",
            "thinking": "[#d2a8ff]💭[/#d2a8ff] ",
            "error": "[#f85149]Error:[/#f85149] ",
            "system": "[dim]System:[/dim] ",
        }.get(role, "")
        msg = Static(f"{label}{content}")
        msg.add_class(f"msg-{role}")
        self.mount(msg)
        self._trim()
        return msg

    def update_last(self, content: str) -> None:
        children = list(self.query("*"))
        if children:
            children[-1].update(content)

    @property
    def last_widget(self):
        children = list(self.query("*"))
        return children[-1] if children else None

    def clear_all(self) -> None:
        for w in list(self.query("*")):
            if w.id != "msg-placeholder":
                w.remove()
        try:
            self.query_one("#msg-placeholder", Static)
        except Exception:
            self.mount(Static("[dim]No messages yet[/dim]", id="msg-placeholder"))

    def thinking_block(self, content: str = "") -> ThinkingBlock:
        block = ThinkingBlock(content)
        self.mount(block)
        return block

    def code_block(self, code: str, language: str = "") -> Static:
        lang_label = f"[dim]{language}[/dim]\n" if language else ""
        msg = Static(f"{lang_label}```{language or ''}\n{code}\n```")
        self.mount(msg)
        self._trim()
        return msg

    def _trim(self) -> None:
        children = [w for w in self.query("*") if w.id != "msg-placeholder"]
        while len(children) > self.MAX_MESSAGES:
            children[0].remove()
            children.pop(0)

    # ── RichLog compatibility ──
    def write(self, text: str, scroll_end: bool = False) -> None:
        if text.strip():
            self.add_message(text)

    def clear(self) -> None:
        self.clear_all()
