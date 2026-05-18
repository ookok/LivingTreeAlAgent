"""DevTUI — terminal chat UI with streaming, markdown, code highlight, tool calls.

Streaming: tokens arrive from LLM → rendered in real-time (typewriter effect).
Tool calls: detected in stream → auto‑executed → result injected → LLM continues.
"""

from __future__ import annotations

import asyncio
import re
import time
from enum import Enum

from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import RenderableType, Group
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Header, Footer, Input, Static
from textual.widget import Widget
from textual.binding import Binding


class TaskPhase(str, Enum):
    SUBMITTED = "submitted"
    STREAMING = "streaming"
    PROCESSING_TOOLS = "tools"
    REVIEWING = "reviewing"
    DONE = "done"
    FAILED = "failed"


class Pulse(Widget):
    """Animated pulse — system alive indicator."""

    DEFAULT_CSS = """
    Pulse { width: 3; height: 1; }
    """

    _frames = ["◐", "◓", "◑", "◒"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._frame = 0

    def on_mount(self) -> None:
        self.set_interval(0.15, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(self._frames)
        self.refresh()

    def render(self) -> RenderableType:
        return Text(self._frames[self._frame], style="bold #58a6ff")


class ChatBubble(Widget):
    """Static chat bubble for user messages and final assistant responses."""

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
                title="You", title_align="right",
                width=min(len(self.content) + 8, 100),
            )
        return Panel(
            Markdown(self.content, code_theme="github-dark"),
            border_style="#238636",
            title="🌳 小树", title_align="left",
        )


class StreamingBubble(Widget):
    """Real‑time streaming chat bubble.

    Tokens arrive via .append() → immediately re‑rendered (typewriter effect).
    Tool calls detected with regex → extracted, shown in a sub‑table.
    After all streamed tokens arrive, tool results update the table.
    """

    DEFAULT_CSS = """
    StreamingBubble { width: 100%; padding: 0 1; margin: 1 0; }
    """

    _TOOL_RE = re.compile(
        r'<tool_call\s+name="(\w+)"\s*>(.*?)</tool_call>', re.DOTALL
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._text = ""
        self._tool_calls: list[dict] = []

    def append(self, token: str) -> None:
        self._text += token
        for name, args in self._TOOL_RE.findall(self._text):
            key = f"{name}|{args.strip()}"
            if not any(t["key"] == key for t in self._tool_calls):
                self._tool_calls.append({
                    "key": key, "name": name,
                    "args": args.strip()[:100],
                    "status": "running", "result": "",
                })
        self.refresh()

    def update_tool(self, tool_name: str, result: str) -> None:
        for t in self._tool_calls:
            if t["name"] == tool_name and t["status"] == "running":
                t["status"] = "done" if "error" not in result.lower()[:60] else "failed"
                t["result"] = result[:500]
                break
        self.refresh()

    @property
    def clean_text(self) -> str:
        return self._TOOL_RE.sub("", self._text)

    def render(self) -> RenderableType:
        parts: list[RenderableType] = []

        if self._tool_calls:
            tbl = Table(show_header=False, box=None, padding=(0, 1))
            tbl.add_column("", width=2)
            tbl.add_column("tool", width=18)
            tbl.add_column("args", width=30)
            tbl.add_column("status", width=8)
            for t in self._tool_calls:
                icon = {"running": "🔄", "done": "✅", "failed": "❌"}.get(t["status"], "⏳")
                style = {"running": "yellow", "done": "green", "failed": "red"}.get(t["status"], "")
                tbl.add_row(icon, f"[bold]{t['name']}[/]", t["args"][:80], f"[{style}]{t['status']}[/]")
                if t["result"]:
                    tbl.add_row("", "", f"[dim]{t['result'][:120]}[/]", "")
            parts.append(Panel(tbl, border_style="#30363d", title="🔧 Tools"))

        clean = self.clean_text.strip()
        if clean:
            parts.append(Markdown(clean + " ▌" if self._text.endswith("▌") else clean, code_theme="github-dark"))
        elif not parts:
            parts.append(Text("▌", style="bold #58a6ff"))

        return Panel(
            parts[0] if len(parts) == 1 else Group(*parts),
            border_style="#238636",
            title="🌳 小树", title_align="left",
        )


class TaskBar(Widget):
    """Bottom task bar — up to 5 concurrent tasks."""

    DEFAULT_CSS = """
    TaskBar { height: auto; padding: 0 1; background: #161b22; border-top: solid #30363d; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tasks: list[dict] = []

    def upsert(self, task_id: str, status: str, detail: str = "") -> None:
        for t in self._tasks:
            if t["id"] == task_id:
                t["status"] = status
                t["detail"] = detail
                break
        else:
            if len(self._tasks) < 5:
                self._tasks.append({"id": task_id, "status": status, "detail": detail})
        self.refresh()

    def done_all(self) -> None:
        for t in self._tasks:
            if t["status"] == "running":
                t["status"] = "done"
        self.refresh()

    def render(self) -> RenderableType:
        if not self._tasks:
            return Text("")
        parts = []
        for t in self._tasks:
            icon = {"running": "🔄", "done": "✅", "failed": "❌", "pending": "⏳"}.get(t["status"], "•")
            label = f"{icon} {t['id'][:20]}"
            if t["detail"]:
                label += f" ({t['detail'][:30]})"
            parts.append(label)
        return Text(" │ ".join(parts), style="#8b949e")


class DevTUI(App):
    """Streaming chat TUI with multi‑turn tool execution."""

    CSS = """
    Screen { background: #0d1117; }
    Header { background: #161b22; color: #58a6ff; }
    #chat-scroll { height: 1fr; overflow-y: auto; }
    #input-area { dock: bottom; height: auto; padding: 1; background: #161b22; border-top: solid #30363d; }
    #input { width: 100%; background: #0d1117; color: #c9d1d9; border: solid #30363d; padding: 1; }
    #status-row { dock: bottom; height: 1; background: #161b22; padding: 0 1; }
    #status-bar { width: 1fr; color: #8b949e; }
    """

    _LABELS = {
        TaskPhase.SUBMITTED: "📥",
        TaskPhase.STREAMING: "📝",
        TaskPhase.PROCESSING_TOOLS: "🔧",
        TaskPhase.REVIEWING: "🔍",
        TaskPhase.DONE: "✅",
        TaskPhase.FAILED: "❌",
    }
    MAX_TOOL_TURNS = 5

    def __init__(self, llm=None):
        super().__init__()
        self._llm = llm
        self._provider_name = "deepseek"
        self._model = "deepseek-v4-flash"
        self._phase = TaskPhase.DONE
        self._phase_start = 0.0
        self._msg_count = 0
        self._task_bar = TaskBar(id="task-bar")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(id="chat-scroll")
        yield self._task_bar
        yield Horizontal(Pulse(), Static(id="status-bar"), id="status-row")
        yield Container(Input(id="input", placeholder="Ask anything... (Ctrl+C quit)"), id="input-area")

    def on_mount(self) -> None:
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.mount(ChatBubble(
            "Type a message and press **Enter**.\n\n"
            "Streaming output • Markdown • Code highlight • Tool calls\n"
            "`Ctrl+L` clear  `Ctrl+D` git diff  `Ctrl+C` quit",
            role="assistant",
        ))
        self._update_status()
        asyncio.create_task(self._morning_brief())

    async def _morning_brief(self) -> None:
        try:
            if self._llm:
                from livingtree.treellm.proactive_agent import morning_brief
                brief = await morning_brief(self._llm)
                scroll = self.query_one("#chat-scroll", VerticalScroll)
                scroll.mount(ChatBubble(brief, role="assistant"))
        except Exception:
            pass

    # ── Input ──────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""

        self._msg_count += 1
        self._phase = TaskPhase.SUBMITTED
        self._phase_start = time.time()
        self._update_status()

        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.mount(ChatBubble(text, role="user"))

        bubble = StreamingBubble()
        scroll.mount(bubble)

        tid = f"msg{self._msg_count}"
        self._task_bar.upsert(tid, "running", "")
        asyncio.create_task(self._run_conversation(text, bubble, tid))

    # ── Core streaming loop ────────────────────────────────────────────

    async def _run_conversation(
        self, user_msg: str, bubble: StreamingBubble, tid: str,
    ) -> None:
        if not self._llm:
            bubble.append("\n❌ LLM not initialized.")
            self._phase = TaskPhase.FAILED
            self._update_status()
            return

        messages = [{"role": "user", "content": user_msg}]
        total_tokens = 0
        total_ms = 0.0

        for turn in range(self.MAX_TOOL_TURNS):
            t0 = time.time()
            self._phase = TaskPhase.STREAMING
            self._update_status()
            self._task_bar.upsert(tid, "running",
                                  f"turn {turn + 1}" if turn else "streaming")

            try:
                provider = self._resolve_provider()
                full_text = ""
                tool_call_names: set[str] = set()

                async for token in provider.stream(
                    messages,
                    temperature=0.3,
                    max_tokens=2048,
                    model=self._model,
                ):
                    if not token:
                        continue
                    full_text += token
                    bubble.append(token)

                    # Detect new tool calls on the fly
                    if "<tool_call" in full_text:
                        found = set(re.findall(
                            r'<tool_call\s+name="(\w+)"', full_text,
                        ))
                        new_tools = found - tool_call_names
                        tool_call_names = found
                        if new_tools:
                            self._phase = TaskPhase.PROCESSING_TOOLS
                            self._update_status()
                            for tn in new_tools:
                                self._task_bar.upsert(tn, "running", "")

                    # Scroll to bottom on each token
                    self.call_from_thread(self._scroll_to_end)

                elapsed = (time.time() - t0) * 1000
                total_ms += elapsed
                total_tokens += len(full_text)

                # ── Execute tool calls if any ──
                tool_calls = re.findall(
                    r'<tool_call\s+name="(\w+)"\s*>\s*(.*?)\s*</tool_call>',
                    full_text, re.DOTALL,
                )
                if not tool_calls:
                    self._phase = TaskPhase.DONE
                    break

                self._phase = TaskPhase.PROCESSING_TOOLS
                self._update_status()

                # Execute each tool
                tool_results: list[tuple[str, str]] = []
                for tname, targs in tool_calls:
                    t0_tool = time.time()
                    targs_clean = targs.strip()
                    result_text = await self._execute_tool(tname, targs_clean)
                    tool_elapsed = (time.time() - t0_tool) * 1000
                    bubble.update_tool(tname, result_text)
                    self._task_bar.upsert(
                        tname, "done",
                        f"{tool_elapsed:.0f}ms",
                    )
                    tool_results.append((tname, result_text))

                # Feed tool results back to LLM
                self._phase = TaskPhase.REVIEWING
                self._update_status()

                for tname, tresult in tool_results:
                    messages.append({
                        "role": "assistant",
                        "content": f'<tool_call name="{tname}">\n{tname}\n</tool_call>',
                    })
                    messages.append({
                        "role": "tool",
                        "tool_name": tname,
                        "content": tresult[:3000],
                    })
                messages.append({
                    "role": "user",
                    "content": "Continue based on the tool results above.",
                })

            except Exception as e:
                self._phase = TaskPhase.FAILED
                bubble.append(f"\n\n❌ {e}")
                break

        self._task_bar.done_all()
        self._task_bar.upsert(
            tid, "done",
            f"{total_tokens} tokens | {total_ms:.0f}ms",
        )
        self._update_status()

    # ── Helpers ────────────────────────────────────────────────────────

    def _resolve_provider(self):
        return self._llm._resolve_provider(self._provider_name)

    def _scroll_to_end(self) -> None:
        try:
            scroll = self.query_one("#chat-scroll", VerticalScroll)
            scroll.scroll_end(animate=False)
        except Exception:
            pass

    async def _execute_tool(self, tool_name: str, args: str) -> str:
        """Route tool calls through CapabilityBus or direct handlers."""
        try:
            # Tier 1: CapabilityBus
            from livingtree.treellm.capability_bus import get_capability_bus
            bus = get_capability_bus()
            for prefix in ("tool:", "vfs:", "mcp:"):
                result = await bus.invoke(f"{prefix}{tool_name}", input=args)
                if result and not (isinstance(result, dict) and result.get("error")):
                    return str(result)[:5000]
        except Exception:
            pass

        # Tier 2: Direct handlers
        try:
            if tool_name == "bash" or tool_name == "run_command":
                from livingtree.treellm.unified_exec import run
                r = await run(args)
                return (r.stdout + r.stderr)[:5000]

            if tool_name == "git_status":
                from livingtree.treellm.developer_tools import git_status
                return git_status()

            if tool_name == "git_diff":
                from livingtree.treellm.developer_tools import git_diff
                return git_diff(args)

            if tool_name == "git_log":
                from livingtree.treellm.developer_tools import git_log
                return git_log(10, args if args else "")

            if tool_name == "git_commit":
                from livingtree.treellm.developer_tools import git_commit
                return git_commit(args)

            if tool_name == "codegraph_update":
                from livingtree.treellm.codegraph_tools import codegraph_update
                return codegraph_update()

            if tool_name == "codegraph_deps":
                from livingtree.treellm.codegraph_tools import codegraph_deps
                return codegraph_deps(args)

            if tool_name == "codegraph_callers":
                from livingtree.treellm.codegraph_tools import codegraph_callers
                return codegraph_callers(args)

            if tool_name == "codegraph_impact":
                from livingtree.treellm.codegraph_tools import codegraph_impact
                return codegraph_impact(args)

            if tool_name in ("read_file", "file_read"):
                path = args.strip().split("\n")[0]
                from pathlib import Path
                p = Path(path)
                if p.exists():
                    return p.read_text(encoding="utf-8", errors="replace")[:10000]
                return f"File not found: {path}"

        except Exception as e:
            return f"[tool:{tool_name} error: {e}]"

        return f"[tool:{tool_name}] not available"

    def _update_status(self) -> None:
        elapsed = time.time() - self._phase_start if self._phase_start else 0
        icon = self._LABELS.get(self._phase, "")
        try:
            bar = self.query_one("#status-bar", Static)
            bar.update(
                f"{icon} {self._phase.value}  |  {self._provider_name}  "
                f"|  {elapsed:.0f}s  |  Ctrl+L clear  Ctrl+D diff  Ctrl+C quit"
            )
        except Exception:
            pass

    # ── Actions ────────────────────────────────────────────────────────

    def action_show_diff(self) -> None:
        try:
            from livingtree.treellm.unified_exec import run_sync
            result = run_sync("git diff --stat", timeout=10)
            out = result.stdout[:5000] or "(no changes)"
            scroll = self.query_one("#chat-scroll", VerticalScroll)
            scroll.mount(ChatBubble(f"**Git Diff**\n```diff\n{out}\n```", role="assistant"))
        except Exception as e:
            scroll = self.query_one("#chat-scroll", VerticalScroll)
            scroll.mount(ChatBubble(f"Diff error: {e}", role="assistant"))

    def action_clear(self) -> None:
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        for child in list(scroll.children):
            if not isinstance(child, ChatBubble):
                child.remove()
        scroll.mount(ChatBubble("Cleared.", role="assistant"))
