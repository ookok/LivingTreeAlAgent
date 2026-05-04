"""Message List — Typed message widgets inspired by Doubao/Yuanbao UI.

Each message in the conversation is a specific widget type:
- UserMessage: compact green label
- ThinkingBlock: collapsible purple stream, auto-collapse after done
- AIResponse: RichMarkdown rendered, code blocks highlighted
- ToolCall: tool name + args in a box
- ScriptBlock: code with output
- ErrorBlock: red prominent error

Architecture: Vertical container with per-message widgets.
Streaming: last widget updates incrementally, then finalizes.
Sessions: Ctrl+N new session, older 5+ blocks auto-collapse.
"""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button
from textual.reactive import var


class UserMessage(Static):
    """User input — compact, right-aligned feel via green."""
    def __init__(self, text: str, **kw):
        super().__init__(f"[#3fb950]You: {text}[/#3fb950]", **kw)


class ThinkingBlock(Static):
    """Collapsible thinking stream. Auto-collapses when done."""
    collapsed = var(False)

    def __init__(self, **kw):
        super().__init__("", **kw)
        self._text = ""
        self._done = False
        self._render()

    def append(self, token: str) -> None:
        self._text += token
        self._render()

    def finish(self) -> None:
        self._done = True
        self.collapsed = True
        self._render()

    def toggle(self) -> None:
        self.collapsed = not self.collapsed
        self._render()

    def _render(self) -> None:
        if not self._text:
            self.update("")
        elif self.collapsed:
            n = len(self._text)
            self.update(f"[#d2a8ff]💭 Thought for {n} chars [dim](click to expand)[/dim][/#d2a8ff]")
        else:
            self.update(f"[#d2a8ff]💭 Thinking...[/#d2a8ff]\n{self._text[-600:]}")


class AIResponse(Static):
    """AI response — rendered as RichMarkdown."""
    def __init__(self, text: str = "", **kw):
        rendered = self._markdown(text) if text else ""
        super().__init__(rendered, **kw)
        self._text = text

    def finalize(self, text: str) -> None:
        self._text = text
        self.update(self._markdown(text))

    @staticmethod
    def _markdown(text: str) -> str:
        try:
            from rich.markdown import Markdown
            from rich.console import Console
            from io import StringIO
            buf = StringIO()
            Console(file=buf, force_terminal=False, width=80).print(Markdown(text))
            return buf.getvalue()
        except Exception:
            return text


class CodeBlock(Static):
    """Syntax-highlighted code block."""
    def __init__(self, code: str, language: str = "", **kw):
        label = f"[dim]{language}[/dim]\n" if language else ""
        content = f"{label}```{language}\n{code}\n```"
        super().__init__(content, **kw)


class ToolCall(Static):
    """Tool invocation display."""
    def __init__(self, tool: str, args: str = "", result: str = "", **kw):
        header = f"🔧 [#fea62b]{tool}[/#fea62b]"
        if args:
            header += f" [dim]({args[:80]})[/dim]"
        body = header
        if result:
            body += f"\n  → {result[:200]}"
        super().__init__(body, **kw)


class ScriptBlock(Static):
    """Script execution with output."""
    def __init__(self, script: str, output: str = "", **kw):
        body = f"```bash\n{script[:500]}\n```"
        if output:
            body += f"\n[dim]Output: {output[:200]}[/dim]"
        super().__init__(body, **kw)


class ErrorBlock(Static):
    """Red error display."""
    def __init__(self, msg: str, **kw):
        super().__init__(f"[#f85149]✗ {msg}[/#f85149]", **kw)


class MessageList(Vertical):
    """Typed message container with session management."""

    MAX_BLOCKS = 5  # keep last 5 blocks expanded, older auto-collapse

    def __init__(self, **kw):
        super().__init__(**kw)
        self._widgets: list[Static] = []
        self._sessions: list[list[Static]] = [[]]
        self._session_idx = 0

    def compose(self) -> ComposeResult:
        yield Static("[dim]No messages yet[/dim]", id="msg-placeholder")

    # ── Message factories ──

    def user_message(self, text: str) -> UserMessage:
        return self._add(UserMessage(text))

    def thinking_block(self) -> ThinkingBlock:
        return self._add(ThinkingBlock())

    def ai_response(self, text: str = "") -> AIResponse:
        return self._add(AIResponse(text))

    def code_block(self, code: str, language: str = "") -> CodeBlock:
        return self._add(CodeBlock(code, language))

    def tool_call(self, tool: str, args: str = "", result: str = "") -> ToolCall:
        return self._add(ToolCall(tool, args, result))

    def script_block(self, script: str, output: str = "") -> ScriptBlock:
        return self._add(ScriptBlock(script, output))

    def error_block(self, msg: str) -> ErrorBlock:
        return self._add(ErrorBlock(msg))

    def write(self, text: str, scroll_end: bool = False) -> None:
        if text.strip():
            self._add(Static(text))

    def clear(self) -> None:
        self.clear_all()

    def clear_all(self) -> None:
        self._widgets.clear()
        self._sessions = [[]]
        self._session_idx = 0
        self.remove_children()
        self.mount(Static("[dim]No messages yet[/dim]", id="msg-placeholder"))

    def new_session(self) -> None:
        self._sessions.append([])
        self._session_idx = len(self._sessions) - 1

    # ── Internal ──

    def _add(self, widget: Static):
        try:
            self.query_one("#msg-placeholder", Static).remove()
        except Exception:
            pass
        self._widgets.append(widget)
        self._sessions[self._session_idx].append(widget)
        if self.app is not None:
            self.app._register(self, widget)
        self._auto_collapse()
        return widget

    def _auto_collapse(self) -> None:
        current = self._sessions[self._session_idx]
        ai_blocks = [w for w in current if isinstance(w, AIResponse)]
        if len(ai_blocks) > self.MAX_BLOCKS:
            for old in ai_blocks[:-self.MAX_BLOCKS]:
                try:
                    old.update(f"[dim]... older response ({len(getattr(old, '_text', ''))} chars)[/dim]")
                except Exception:
                    pass
