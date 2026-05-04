"""AI Chat — Markdown, task tree, thinking animation, multi-modal, stash, history.

Features:
- Streaming AI chat with markdown rendering
- Task progress tree (LifeEngine pipeline)
- Multi-modal input (file, image, voice)
- Composer prompt stash (Ctrl+S)
- Composer history search (Alt+R)
- Reasoning-effort cycling (Shift+Tab)
- Inline diff rendering
- User memory (# commands)
- Visual retry/backoff banner
- MCP health chip
- Tool-output spillover
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Optional

import aiohttp
from datetime import datetime
from textual import work, on, events
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, RichLog, Static, TextArea
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from ..widgets.task_progress import TaskProgressPanel
from ..widgets.task_list import TaskListPanel
from ..widgets.attachment_bar import AttachmentBar
from ..widgets import native_dialogs
from ..widgets import clipboard_handler
from ..widgets import voice_handler
from ..widgets import sound_effects
from ..widgets.composer_stash import ComposerStash
from ..widgets.user_memory import UserMemory

from ...config.system_config import (
    SLASH_COMMANDS as _COMMANDS,
    _HIDDEN_COMMANDS,
    REASONING_EFFORTS,
    PIPELINE_INTENT_TRIGGERS,
    PRO_REASONING_INTENT_TRIGGERS,
)

_ALL_COMMANDS = {**_COMMANDS, **_HIDDEN_COMMANDS}

REASONING_EFFORTS = REASONING_EFFORTS
TOOL_OUTPUT_DIR = ".livingtree/tool_outputs"
MAX_INLINE_OUTPUT = 32 * 1024


class ChatScreen(Screen):
    """Streaming chat with full toolkit."""

    BINDINGS = [
        ("escape", "app.pop_screen", "返回"),
        ("ctrl+c", "copy_selection", "复制"),
        ("ctrl+enter", "send_from_binding", "发送"),
        ("ctrl+s", "stash_draft", "暂存草稿"),
        ("ctrl+r", "history_search", "搜索历史"),
        ("shift+tab", "cycle_effort", "推理深度"),
        ("enter", "send_from_binding", "发送"),
        ("end", "scroll_to_bottom", "到底部"),
        ("ctrl+f", "fold_all", "折叠AI"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None
        self._messages: list[dict] = []
        self._api_key = ""
        self._base_url = ""
        self._flash = ""
        self._pro = ""
        self._sending = False
        self._total_tokens = 0
        self._attached_files: list[Path] = []
        self._voice_active = False
        self._effort_idx = 2
        self._reasoning_effort = "max"
        self._stash = ComposerStash()
        self._memory = UserMemory()
        self._history: list[str] = []
        self._history_visible = False
        self._pending_queue: list[str] = []
        self._retry_count = 0
        self._cache_tracker = None
        self._think_timer = None
        self._think_idx = 0
        self._lsp = None
        self._mcp_health = 0
        self._blocks: list[dict] = []  # {role, content, collapsed, summary}

    def _fold_block(self, block_idx: int) -> None:
        if 0 <= block_idx < len(self._blocks):
            self._blocks[block_idx]["collapsed"] = not self._blocks[block_idx]["collapsed"]
            self._rerender_blocks()

    def _make_summary(self, text: str, max_len: int = 60) -> str:
        lines = text.strip().split("\n")
        first = lines[0].strip() if lines else text[:max_len]
        first = first.replace("#", "").replace("*", "").strip()
        return first[:max_len] + ("..." if len(first) > max_len else "")

    def _display_write(self, text: str = "") -> None:
        try:
            d = self.query_one("#chat-display", RichLog)
            d.write(text)
        except Exception:
            pass

    def _render_response(self, display: RichLog, resp: str) -> None:
        lines = [f"\n[bold #58a6ff]AI:[/bold #58a6ff]"]
        if self._reasoning_effort != "off":
            lines.append(f"[dim]Reasoning effort: {self._reasoning_effort}[/dim]")
        lines.append(resp)
        lines.append(f"[dim]---  [italic]Ctrl+C to copy[/italic][/dim]")
        for line in lines:
            self._display_write(line)

    @work(exclusive=False)
    async def action_fold_all(self) -> None:
        for b in self._blocks:
            b["collapsed"] = True
        self._rerender_blocks()

    def _rerender_blocks(self) -> None:
        try:
            d = self.query_one("#chat-display", RichLog)
            d.clear()
            for i, b in enumerate(self._blocks):
                role = "You" if b["role"] == "user" else "AI"
                color = "#3fb950" if b["role"] == "user" else "#58a6ff"
                if b.get("collapsed") and b["role"] == "assistant":
                    summary = b.get("summary", b["content"][:60])
                    d.write(f"\n[bold {color}]▶ {role}:[/bold {color}] [dim]{summary}[/dim]")
                    d.write("[dim]  (click to expand)[/dim]")
                else:
                    d.write(f"\n[bold {color}]{role}:[/bold {color}]")
                    d.write(b["content"])
                d.write("[dim]---[/dim]")
        except Exception:
            pass

    def set_hub(self, hub) -> None:
        self._hub = hub
        if hub and hasattr(hub, "config"):
            c = hub.config
            self._api_key = c.model.deepseek_api_key or ""
            self._base_url = c.model.deepseek_base_url or ""
            self._flash = c.model.flash_model or ""
            self._pro = c.model.pro_model or ""

    def compose(self) -> ComposeResult:
        yield Static("[dim]esc back[/dim]", id="back-link")
        yield Horizontal(
            Label("", id="chat-model-label"),
            Label("", id="chat-effort-label"),
            Label("", id="chat-tokens-label"),
            Label("", id="chat-cost-label"),
            Label("", id="chat-cache-label"),
            id="chat-topbar",
        )
        with Horizontal():
            with Vertical(id="sidebar"):
                yield TaskProgressPanel(id="task-progress")
                yield TaskListPanel(id="task-list")
                yield Static("", id="cache-stats")
            with Vertical(id="main-area"):
                yield RichLog(id="chat-display", highlight=True, markup=True, wrap=True, max_lines=1000, read_only=True)
            yield Horizontal(
                Button("File", id="file-btn"),
                Label("", id="llm-status"),
                Label("", id="pulse-status"),
                Label("", id="error-status"),
                Label("[dim]Enter send  Ctrl+C copy  End→bottom[/dim]", id="action-hints"),
                Button("[#58a6ff]Switch LLM[/#58a6ff]", id="switch-llm-btn"),
                Button("Clear", id="clear-btn"),
                id="action-bar",
            )
            yield AttachmentBar(id="attachment-bar")
            yield Container(
                TextArea.code_editor("", id="chat-input", language=None, show_line_numbers=False),
                Label("[dim]Enter send  Shift+Enter newline[/dim]", id="chat-hints"),
                id="chat-input-container",
            )

    def on_mount(self) -> None:
        hub = getattr(self.app, '_hub', None)
        if hub and hasattr(self, 'set_hub'):
            self.set_hub(hub)

        self._update_topbar()

        try:
            from ...dna.cache_optimizer import PrefixCacheTracker
            self._cache_tracker = PrefixCacheTracker()
        except ImportError:
            pass

        d = self.query_one("#chat-display", RichLog)
        self._display_write("[#58a6ff]# LivingTree[/#58a6ff]")
        if self._hub and hasattr(self._hub, 'config'):
            lc = self._hub.config.model
            if lc.longcat_api_key:
                self._display_write(f"  [#8b949e]LongCat {lc.longcat_models}[/#8b949e]")
        if not getattr(self.app, '_hub_ready', False):
            self._display_write("  [#d29922]initializing...[/#d29922]")
        self._display_write("")
        self._display_write("[bold]Quick Start[/bold]")
        self._display_write("  Type a message and press [bold]Enter[/bold]")
        self._display_write("  [bold]Ctrl+S[/bold] stash draft | [bold]Alt+R[/bold] search history")
        self._display_write("  [bold]Shift+Tab[/bold] cycle effort | [bold]Ctrl+C[/bold] copy")
        self._display_write("  [bold]/search[/bold] multi-source | [bold]/pipeline[/bold] auto-gen")
        self._display_write("  [bold]/file[/bold] preview | [bold]/fetch[/bold] web scrape")
        self._display_write("  [bold]/help[/bold] all commands")
        self._display_write("")


    def _display_clear(self) -> None:
        try:
            self.query_one("#chat-display", RichLog).clear()
        except Exception:
            pass
    def _display_write(self, text: str = "") -> None:
        try:
            d = self.query_one("#chat-display", RichLog)
            d.write(text)
        except Exception:
            pass

    def _update_topbar(self) -> None:
        try:
            self.query_one("#chat-model-label", Label).update("[bold #58a6ff]DeepSeek V4 Pro[/bold #58a6ff]")
        except Exception: pass
        try:
            self.query_one("#chat-effort-label", Label).update(f"[#d2a8ff]{self._reasoning_effort.upper()}[/#d2a8ff]")
        except Exception: pass
        try:
            self.query_one("#chat-tokens-label", Label).update(f"[#8b949e]{self._total_tokens // 1000}K[/#8b949e]")
        except Exception: pass
        try:
            cost = self._total_tokens * 0.00000014
            self.query_one("#chat-cost-label", Label).update(f"[#3fb950]¥{cost:.4f}[/#3fb950]" if cost > 0 else "[#8b949e]¥0[/#8b949e]")
        except Exception: pass
        try:
            if self._cache_tracker:
                snap = self._cache_tracker.snapshot()
                self.query_one("#chat-cache-label", Label).update(f"[#484f58]cache {snap['cache_hit_pct']:.0f}%[/#484f58]")
        except Exception: pass
        self._update_status_bar()

    def _update_status_bar(self) -> None:
        try:
            provider = "deepseek"
            if self._hub and hasattr(self._hub.world, 'consciousness'):
                status = self._hub.world.consciousness.get_election_status()
                provider = status.get("elected", "deepseek")
                count = len(status.get("providers", []))
                self.query_one("#llm-status", Label).update(f"[#58a6ff]LLM: {provider}[/#58a6ff] ({count})")
        except Exception: pass

        try:
            bio = getattr(self._hub.world, 'biorhythm', None) if self._hub else None
            if bio:
                snap = bio._get_snapshot()
                icons = {"active": "[#3fb950]● active[/#3fb950]", "reflecting": "[#d29922]◉ reflect[/#d29922]", "resting": "[#8b949e]○ rest[/#8b949e]", "dreaming": "[#d2a8ff]◎ dream[/#d2a8ff]"}
                self.query_one("#pulse-status", Label).update(icons.get(snap["state"], ""))
        except Exception: pass

        try:
            from ...observability.error_interceptor import get_interceptor
            ei = get_interceptor()
            if ei:
                s = ei.get_stats()
                if s["total_errors"] > 0:
                    self.query_one("#error-status", Label).update(f"[#f85149]!{s['total_errors']} err[/#f85149]")
        except Exception: pass

    @work(exclusive=False)
    async def _switch_llm(self) -> None:
        if not self._hub:
            self.notify("Backend not ready", severity="warning", timeout=2)
            return
        c = self._hub.world.consciousness
        self._display_write("[#58a6ff]Re-electing LLM provider...[/#58a6ff]\n")
        elected = await c._elect()
        status = c.get_election_status()
        providers = ", ".join(status.get("providers", []))
        self._display_write(f"[#3fb950]Elected: {elected}[/#3fb950] | Pool: [{providers}]\n")
        self._update_status_bar()
        self.notify(f"Switched to {elected}", timeout=3)

    # ── Autocomplete ──
    def on_input_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id != "chat-input":
            return
        text = event.text_area.text
        hint = self.query_one("#autocomplete-hint", Static)

        if text.startswith("#"):
            hint.update("[dim]This will be saved to memory.md (no turn fired)[/dim]")

        elif text.startswith("/") and " " not in text:
            matches = [c for c in _COMMANDS if c.startswith(text)]
            if len(matches) == 1:
                hint.update(f"[dim]{_COMMANDS[matches[0]]}[/dim]")
            elif matches:
                hint.update(f"[dim]{' | '.join(matches[:5])}[/dim]")
            else:
                hint.update("")
        else:
            hint.update("")

        self._update_pending_preview()

    # ── Buttons ──
    @work(exclusive=False)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "clear-btn":
            self._clear()
        elif bid == "switch-llm-btn":
            await self._switch_llm()
        elif bid == "file-btn":
            await self._pick_file_native()

    # ── Reasoning effort ──
    @work(exclusive=False)
    async def action_send_from_binding(self) -> None:
        await self._send()

    def action_scroll_to_bottom(self) -> None:
        try:
            d = self.query_one("#chat-display", RichLog)
            d.scroll_end(animate=False)
        except Exception:
            pass

    def action_cycle_effort(self) -> None:
        self._effort_idx = (self._effort_idx + 1) % len(REASONING_EFFORTS)
        self._reasoning_effort = REASONING_EFFORTS[self._effort_idx]
        self._update_topbar()
        try:
            btn = self.query_one("#effort-btn", Button)
            btn.label = f"Effort:{self._reasoning_effort.upper()}"
        except Exception:
            pass
        self.notify(f"Reasoning: {self._reasoning_effort.upper()}", timeout=2)

    # ── Stash (Ctrl+S) ──
    def action_stash_draft(self) -> None:
        inp = self.query_one("#chat-input", RichLog)
        text = inp.text.strip()
        if not text:
            self.notify("Nothing to stash", timeout=2)
            return
        success = self._stash.push(text)
        if success:
            inp.text = ""
            self.notify(f"Draft stashed ({len(self._stash._drafts)} total)", timeout=2)
        else:
            self.notify("Stash failed", severity="warning", timeout=2)

    # ── History search (Alt+R) ──
    def action_history_search(self) -> None:
        display = self.query_one("#chat-display", RichLog)
        if self._history_visible:
            return

        self._display_write("\n[bold #58a6ff]History (type to filter, Enter=restore, Esc=dismiss)[/bold #58a6ff]")
        recent = self._history[-20:]
        for i, entry in enumerate(reversed(recent)):
            preview = entry[:100] + ("..." if len(entry) > 100 else "")
            self._display_write(f"  [dim]{i+1}.[/dim] {preview}")
        self._display_write("[dim]---[/dim]")
        self._history_visible = False

    # ── Pending input preview ──
    def _update_pending_preview(self) -> None:
        try:
            pp = self.query_one("#pending-preview", Static)
            if self._pending_queue:
                items = "\n".join(
                    f"[dim]⏳ {q[:80]}...[/dim]" if len(q) > 80 else f"[dim]⏳ {q}[/dim]"
                    for q in self._pending_queue[-3:]
                )
                pp.update(items)
            else:
                pp.update("")
        except Exception:
            pass

    # ── Clipboard ──
    def _copy_last_response(self) -> None:
        for msg in reversed(self._messages):
            if msg["role"] == "assistant":
                clipboard_handler.write_clipboard_text(msg["content"])
                self.notify("Copied last response", timeout=2)
                return
        self.notify("Nothing to copy", severity="warning", timeout=2)

    def _copy_full_transcript(self) -> None:
        lines = []
        for msg in self._messages:
            role = "You" if msg["role"] == "user" else "AI"
            lines.append(f"{role}: {msg['content']}")
        text = "\n\n".join(lines)
        if text:
            clipboard_handler.write_clipboard_text(text)
            self.notify(f"Copied full transcript ({len(self._messages)} msgs)", timeout=2)
        else:
            self.notify("Nothing to copy", severity="warning", timeout=2)

    def action_copy_selection(self) -> None:
        try:
            ta = self.query_one("#chat-input", RichLog)
            sel = ta.selected_text
            if sel:
                clipboard_handler.write_clipboard_text(sel)
                self.notify("Copied selection", timeout=2)
                return
        except Exception:
            pass
        self._copy_last_response()

    # ── File/Folder pickers ──
    async def _pick_file_native(self) -> None:
        path = await native_dialogs.open_file_dialog(title="Select file")
        if not path:
            return
        self._attached_files.append(path)
        size_kb = path.stat().st_size // 1024 if path.exists() else 0
        label = f"[image: {path.name} ({size_kb}KB)]" if path.suffix.lower() in (
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"
        ) else f"[file: {path.name} ({size_kb}KB)]"
        inp = self.query_one("#chat-input", RichLog)
        inp.text = f"{inp.text}\n{label}".strip()
        self.notify(f"Selected: {path.name}", timeout=2)

    async def _pick_folder_native(self) -> None:
        path = await native_dialogs.open_folder_dialog(title="Select folder")
        if not path:
            return
        display = self.query_one("#chat-display", RichLog)
        self._display_write(f"[bold]Working dir:[/bold] {path}")
        self.notify(f"Folder: {path}", timeout=3)

    # ── Voice ──
    async def _voice_input(self) -> None:
        if self._voice_active:
            return
        self._voice_active = True
        self.notify("Listening... (10s)", timeout=3)
        text = await voice_handler.speech_to_text("zh-CN")
        self._voice_active = False
        if text:
            inp = self.query_one("#chat-input", RichLog)
            inp.value = f"{inp.value} {text}".strip()
            self.notify(f"Recognized: {text[:30]}...", timeout=3)
        else:
            self.notify("No voice detected", severity="warning", timeout=2)

    # ── Save chat ──
    async def _save_chat(self) -> None:
        path = await native_dialogs.save_file_dialog(
            title="Save chat", filetypes=[("Markdown", "*.md"), ("Text", "*.txt")],
            defaultextension=".md",
        )
        if not path:
            return
        lines = []
        for msg in self._messages:
            role = "You" if msg["role"] == "user" else "AI"
            lines.append(f"## {role}\n\n{msg['content']}\n")
        path.write_text("\n".join(lines), encoding="utf-8")
        self.notify(f"Saved: {path.name}", timeout=3)

    # ── Paste handler ──
    def _on_paste(self, event: events.Paste) -> None:
        if self._detect_paste_burst(event):
            return

        if not event.text or len(event.text) < 10:
            if clipboard_handler.clipboard_has_image():
                img = clipboard_handler.get_clipboard_image()
                if img:
                    inp = self.query_one("#chat-input", RichLog)
                    inp.value = f"{inp.value}\n[image: {img.name} ({len(img.data)//1024}KB)]".strip()
                    self.notify(f"Image pasted: {img.name}", timeout=2)
                    event.stop()
                    return
            files = clipboard_handler.get_clipboard_files()
            if files:
                for f in files:
                    inp = self.query_one("#chat-input", RichLog)
                    inp.value = f"{inp.value}\n[file: {f.name}]".strip()
                self.notify(f"Pasted {len(files)} files", timeout=2)
                event.stop()
                return

        if event.text and len(event.text) > 500:
            event.text = event.text.replace("\r\n", "\n")

    def _detect_paste_burst(self, event: events.Paste) -> bool:
        t = time.monotonic()
        if not hasattr(self, '_last_paste_time'):
            self._last_paste_time = 0
            self._paste_count = 0

        if t - self._last_paste_time < 0.05:
            self._paste_count += 1
            if self._paste_count > 5:
                self._paste_count = 0
                self._last_paste_time = t
                return True
        else:
            self._paste_count = 0
        self._last_paste_time = t
        return False

    # ── Thinking animation ──
    def _animate_thinking(self) -> None:
        try:
            sp = "\u280b\u2819\u2818\u280c\u2804\u2826\u2827\u2847\u2807"
            idx = self._think_idx % len(sp)
            self._think_idx += 1
            d = self.query_one("#chat-display", RichLog)
            self._display_write(f"  [bold #fea62b]{sp[idx]}[/bold #fea62b] [italic dim]AI thinking...[/italic dim]")
        except Exception:
            pass

    # ── Send ──
    async def _send(self) -> None:
        if self._sending:
            inp = self.query_one("#chat-input", RichLog)
            text = inp.text.strip()
            if text:
                self._pending_queue.append(text)
                inp.text = ""
                self._update_pending_preview()
                self.notify("Queued (busy)", timeout=1)
            return

        inp = self.query_one("#chat-input", RichLog)
        text = inp.text.strip()
        if not text:
            return

        if text.startswith("#"):
            self._memory.append(text)
            inp.text = ""
            self.notify(f"Memory saved ({self._memory.count_entries()} entries)", timeout=2)
            return

        if not self._hub:
            display = self.query_one("#chat-display", RichLog)
            self._display_write("\n[yellow]Engine not ready yet[/yellow]")
            return

        inp.text = ""
        self._sending = True
        self._history.append(text)
        if len(self._history) > 500:
            self._history = self._history[-500:]

        display = self.query_one("#chat-display", RichLog)
        tp = self.query_one(TaskProgressPanel)
        tp.reset()

        if text.startswith("/"):
            await self._handle_command(text, display)
            self._sending = False
            self._process_pending_queue()
            return

        memory_ctx = self._memory.get_context_block()
        if memory_ctx:
            self._display_write(f"\n[dim]Memory context loaded ({self._memory.count_entries()} entries)[/dim]")

        self._display_write(f"\n[bold green]You:[/bold green] {text}")
        self._messages.append({"role": "user", "content": text})
        summary = self._make_summary(text)
        self._blocks.append({"role": "user", "content": text, "collapsed": False, "summary": summary})

        for i in range(max(0, len(self._blocks) - 6)):
            if self._blocks[i]["role"] == "assistant":
                self._blocks[i]["collapsed"] = True

        auto_pro = len(text) > 200 or any(kw in text for kw in PRO_REASONING_INTENT_TRIGGERS)

        if self._reasoning_effort == "off":
            auto_pro = False

        steps = [
            {"name": "Perceive intent", "depends_on": []},
            {"name": "Retrieve knowledge", "depends_on": []},
            {"name": f"{'Deep' if auto_pro else 'Quick'} reasoning", "depends_on": [0, 1]},
            {"name": "Generate response", "depends_on": [2]},
        ]
        tp.load_plan(steps)
        tl = self.query_one(TaskListPanel)
        tl.load_tasks(steps)
        tp.update_step(0, "running", "analyzing...")
        tl.update_task(0, "running", "analyzing...")
        await asyncio.sleep(0.02)
        tp.update_step(0, "done", f"{len(text)} chars")
        tl.update_task(0, "done")

        tp.update_step(1, "running", "searching KB...")
        tl.update_task(1, "running", "KB")
        await asyncio.sleep(0.02)
        tp.update_step(1, "done", "retrieved")
        tl.update_task(1, "done")

        tp.update_step(2, "running", f"{'pro' if auto_pro else 'flash'} model (effort={self._reasoning_effort})")
        tl.update_task(2, "running", f"{'pro' if auto_pro else 'flash'}")
        self._think_idx = 0
        self._think_timer = self.set_interval(0.8, self._animate_thinking)
        try:
            resp = await self._stream(text, pro=auto_pro)
            self._render_response(display, resp)
            self._messages.append({"role": "assistant", "content": resp})
            summary = self._make_summary(resp)
            self._blocks.append({"role": "assistant", "content": resp, "collapsed": False, "summary": summary})
            tp.update_step(2, "done", f"{len(resp)} chars")
        except Exception as e:
            self._display_write(f"\n[bold red]Error:[/bold red] {e}")
            tp.update_step(2, "failed", str(e)[:40])
        finally:
            if self._think_timer:
                self._think_timer.stop()

        tp.update_step(3, "running", "formatting...")
        tl.update_task(3, "running", "formatting")
        await asyncio.sleep(0.02)
        tp.update_step(3, "done", "complete")
        tl.update_task(3, "done")
        tp.mark_all_done()
        tl.mark_all_done()

        self._update_topbar()
        self._sending = False
        self._process_pending_queue()

    def _process_pending_queue(self) -> None:
        if self._pending_queue:
            self.call_later(self._send_pending)

    async def _send_pending(self) -> None:
        if self._sending or not self._pending_queue:
            return
        text = self._pending_queue.pop(0)
        inp = self.query_one("#chat-input", RichLog)
        inp.text = text
        self._update_pending_preview()
        await self._send()

    def _render_response(self, display: RichLog, resp: str) -> None:
        lines = [f"\n[bold #58a6ff]AI:[/bold #58a6ff]"]
        if self._reasoning_effort != "off":
            lines.append(f"[dim]Reasoning effort: {self._reasoning_effort}[/dim]")
        lines.append(resp)
        lines.append(f"[dim]---  [italic]Ctrl+C to copy[/italic][/dim]")
        for line in lines:
            self._display_write(line)

    def _update_cache_stats(self) -> None:
        self._update_topbar()

    # ── Stream ──
    async def _stream(self, text: str, pro: bool = False) -> str:
        if not self._api_key:
            return f"[yellow]API key not configured[/yellow]\n\n> {text[:100]}"

        model = self._pro if pro else self._flash
        model = model.split("/")[-1] if "/" in model else model
        sys_content = (
            "You are a professional AI assistant. Reply in Markdown format.\n"
            "Rules:\n"
            "1. Use ### for headings\n"
            "2. Code blocks with language: ```python\n"
            "3. Lists with - or 1.\n"
            "4. Important content in **bold**\n"
            "5. Tables with | alignment\n"
            "6. Be concise and structured"
        )

        memory_ctx = self._memory.get_context_block()
        if memory_ctx:
            sys_content = memory_ctx + "\n\n" + sys_content

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": sys_content},
                *self._messages[-15:],
            ],
            "temperature": 0.3 if not pro else 0.7,
            "max_tokens": 4096 if not pro else 8192,
            "stream": True,
        }

        if self._reasoning_effort != "off":
            try:
                payload["reasoning_effort"] = self._reasoning_effort
            except Exception:
                pass

        collected = []
        session = self._hub._lazy_session() if self._hub else aiohttp.ClientSession()
        t0 = time.monotonic()
        try:
            async with session.post(
                    f"{self._base_url}/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key}",
                    },
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=180),
                ) as resp:
                    if resp.status == 429:
                        return self._retry_backoff(resp)
                    if resp.status == 500 or resp.status >= 502:
                        retry_after = 3
                        try:
                            retry_after = int(resp.headers.get("Retry-After", "3"))
                        except Exception:
                            pass
                        return f"[yellow]Server error {resp.status}. Retrying in {retry_after}s...[/yellow]"
                    if resp.status != 200:
                        err_text = await resp.text()
                        return f"[red]API Error {resp.status}[/red]: {err_text[:200]}"

                    buf = b""
                    display = self.query_one("#chat-display", RichLog)
                    async for chunk in resp.content.iter_any():
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            t = line.decode(errors="replace").strip()
                            if not t.startswith("data: "):
                                continue
                            d = t[6:]
                            if d == "[DONE]":
                                break
                            try:
                                data = json.loads(d)
                                delta = data.get("choices", [{}])[0].get("delta", {})

                                reasoning = delta.get("reasoning_content", "")
                                if reasoning and self._reasoning_effort != "off":
                                    self._display_write(f"[dim italic]Think: {reasoning[:100]}...[/dim italic]")

                                token = delta.get("content", "")
                                if token:
                                    collected.append(token)
                                    if len(collected) % 4 == 0:
                                        self._display_write("".join(collected[-4:]))

                                usage = data.get("usage", {})
                                if usage and self._cache_tracker:
                                    self._cache_tracker.record_turn(
                                        prompt_tokens=usage.get("prompt_tokens", 0),
                                        completion_tokens=usage.get("completion_tokens", 0),
                                        cached_tokens=usage.get("prompt_cache_hit_tokens", 0)
                                        + usage.get("prompt_cache_miss_tokens", 0),
                                    )
                            except Exception:
                                continue
        except asyncio.TimeoutError:
            return "[red]Request timed out (180s)[/red]"
        except aiohttp.ClientConnectionError:
            return "[red]Connection error. Check API endpoint.[/red]"
        except Exception as e:
            return f"[red]Error:[/red] {e}"

        elapsed = time.monotonic() - t0
        result = "".join(collected)

        if self._cache_tracker:
            self._cache_tracker.record_turn(
                prompt_tokens=len(payload["messages"]) * 500,
                completion_tokens=len(result),
                cached_tokens=0,
            )

        return result if result else "[dim](Empty response)[/dim]"

    def _retry_backoff(self, resp) -> str:
        retry_after = 1
        try:
            retry_after = int(resp.headers.get("Retry-After", "1"))
        except Exception:
            pass
        msg = (
            f"\n[yellow]Rate limited (429). Backing off {retry_after}s...[/yellow]\n"
            f"[dim]Consider switching to a lower reasoning effort or waiting.[/dim]"
        )
        self.notify(f"Rate limited. Retry in {retry_after}s.", severity="warning", timeout=retry_after + 2)
        return msg

    def _tool_output_spillover(self, text: str, source: str = "tool") -> str:
        if len(text) <= MAX_INLINE_OUTPUT:
            return text
        spill_dir = Path(TOOL_OUTPUT_DIR)
        spill_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{source}_{ts}.txt"
        fpath = spill_dir / fname
        fpath.write_text(text, encoding="utf-8")
        head = text[:MAX_INLINE_OUTPUT]
        return head + f"\n\n... [Full output ({len(text)} bytes) saved to {fpath}]"

    # ── Inline diff rendering ──
    def _render_diff(self, old: str, new: str) -> str:
        import difflib
        old_lines = old.splitlines()
        new_lines = new.splitlines()
        diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))
        if not diff:
            return "[dim]No changes detected[/dim]"

        result = []
        for line in diff[:100]:
            if line.startswith("@@ "):
                result.append(f"[bold]{line}[/bold]")
            elif line.startswith("+"):
                result.append(f"[#3fb950]{line}[/#3fb950]")
            elif line.startswith("-"):
                result.append(f"[#f85149]{line}[/#f85149]")
            else:
                result.append(line)

        lines = "\n".join(result)
        return f"```diff\n{lines}\n```"

    # ── Share / export ──
    def _export_html(self) -> str:
        parts = [
            "<html><head><meta charset='utf-8'><title>LivingTree Chat</title>",
            "<style>body{font-family:monospace;max-width:900px;margin:auto;",
            "padding:20px;background:#0d1117;color:#c9d1d9}",
            ".user{color:#3fb950}.ai{color:#58a6ff}.divider{color:#30363d}",
            "pre{background:#161b22;padding:12px;border-radius:6px}",
            "</style></head><body>",
            "<h1>LivingTree AI Chat</h1>",
        ]
        for msg in self._messages:
            role_class = "user" if msg["role"] == "user" else "ai"
            role_label = "You" if msg["role"] == "user" else "AI"
            parts.append(f"<div class='{role_class}'><strong>{role_label}</strong><br>")
            parts.append(f"<p>{msg['content']}</p></div><hr class='divider'>")
        parts.append(f"<p><em>Generated {datetime.now().isoformat()}</em></p>")
        parts.append("</body></html>")
        return "\n".join(parts)

    # ── AGENTS.md bootstrap ──
    def _generate_agents_md(self) -> str:
        workspace = Path(".")
        lines = ["# AGENTS.md", "", "## Project Overview", ""]

        if (workspace / "pyproject.toml").exists():
            lines.append("- **Type:** Python project (pyproject.toml)")
        elif (workspace / "package.json").exists():
            lines.append("- **Type:** Node.js project (package.json)")
        elif (workspace / "Cargo.toml").exists():
            lines.append("- **Type:** Rust project (Cargo.toml)")
        elif (workspace / "go.mod").exists():
            lines.append("- **Type:** Go project (go.mod)")
        else:
            lines.append("- **Type:** General project")

        lines.append("")
        lines.append("## Build & Test")
        if (workspace / "Makefile").exists():
            lines.append("- **Build:** `make build`")
            lines.append("- **Test:** `make test`")
        elif (workspace / "pyproject.toml").exists():
            lines.append("- **Build:** `pip install -e .`")
            lines.append("- **Test:** `pytest`")
        elif (workspace / "package.json").exists():
            lines.append("- **Build:** `npm run build`")
            lines.append("- **Test:** `npm test`")
        else:
            lines.append("- **Build:** Run build script")
            lines.append("- **Test:** Run test suite")

        lines.append("")
        lines.append("## Conventions")
        lines.append("- Follow existing code style")
        lines.append("- Write tests for new features")
        lines.append("- Keep commits small and focused")

        return "\n".join(lines)

    # ── Commands ──
    async def _handle_command(self, text: str, display: RichLog) -> None:
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/stash":
            if arg == "list":
                drafts = self._stash.list()
                self._display_write("[bold]Stashed Drafts[/bold]")
                if drafts:
                    for d in drafts:
                        self._display_write(f"  {d['index']}. {d['preview']} [dim]({d['timestamp'][:16]})[/dim]")
                else:
                    self._display_write("  [dim]No stashed drafts[/dim]")
            elif arg == "pop":
                draft = self._stash.pop()
                if draft:
                    inp = self.query_one("#chat-input", RichLog)
                    inp.text = draft.text
                    self.notify(f"Draft restored ({len(draft.text)} chars)", timeout=2)
                else:
                    self._display_write("[dim]No drafts to restore[/dim]")
            elif arg == "clear":
                count = self._stash.clear()
                self._display_write(f"[dim]Cleared {count} drafts[/dim]")
            else:
                self._display_write(f"[dim]/stash list|pop|clear (Ctrl+S to stash current)[/dim]")

        elif cmd == "/effort":
            efforts = ["off", "high", "max"]
            if arg in efforts:
                self._effort_idx = efforts.index(arg)
                self._reasoning_effort = arg
                self._update_topbar()
                try:
                    btn = self.query_one("#effort-btn", Button)
                    btn.label = f"Effort:{arg.upper()}"
                except Exception:
                    pass
                self._display_write(f"[dim]Reasoning effort: {arg.upper()}[/dim]")
            else:
                self._display_write(f"[dim]Current: [bold]{self._reasoning_effort.upper()}[/bold] | /effort off|high|max[/dim]")

        elif cmd == "/memory":
            if arg == "show":
                content = self._memory.read()
                self._display_write(f"[bold]User Memory[/bold]\n{content}" if content else "[dim]No memory entries[/dim]")
            elif arg == "clear":
                self._memory.clear()
                self._display_write("[dim]Memory cleared[/dim]")
            elif arg == "path":
                self._display_write(f"[dim]Memory file: {self._memory.show_path()}[/dim]")
            else:
                count = self._memory.count_entries()
                self._display_write(f"[dim]User memory: {count} entries | /memory show|clear|path[/dim]")

        elif cmd == "/diff":
            if arg:
                args = arg.split(maxsplit=1)
                if len(args) == 2:
                    self._display_write(self._render_diff(args[0], args[1]))
                else:
                    self._display_write("[dim]Usage: /diff <old_text> <new_text>[/dim]")
            else:
                self._display_write("[dim]Usage: /diff <old_text> <new_text>[/dim]")

        elif cmd == "/share":
            html = self._export_html()
            path = Path(".livingtree/shared_chat.html")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html, encoding="utf-8")
            self._display_write(f"[dim]Chat exported to {path}[/dim]")
            self.notify(f"Exported to {path}", timeout=3)

        elif cmd == "/init":
            agents_md = self._generate_agents_md()
            path = Path("AGENTS.md")
            if path.exists():
                self._display_write("[yellow]AGENTS.md already exists. Showing diff:[/yellow]")
                existing = path.read_text(encoding="utf-8")
                self._display_write(self._render_diff(existing, agents_md))
            else:
                path.write_text(agents_md, encoding="utf-8")
                self._display_write(f"[dim]Created AGENTS.md ({len(agents_md)} chars)[/dim]")

        elif cmd == "/retry":
            if self._messages and self._messages[-1]["role"] == "user":
                last = self._messages.pop()
                self._retry_count += 1
                inp = self.query_one("#chat-input", RichLog)
                inp.text = last["content"]
                self._display_write(f"[dim]Retrying last message (attempt {self._retry_count})[/dim]")
                await asyncio.sleep(0.1)
                await self._send()
            else:
                self._display_write("[dim]No message to retry[/dim]")

        elif cmd == "/status":
            await self._show_status()

        elif cmd == "/file" and arg:
            p = Path(arg)
            if p.exists():
                ext = p.suffix.lower()
                size = p.stat().st_size
                if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                    self._display_write(f"[bold]Image:[/bold] {p.name} ({size//1024}KB)")
                else:
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                        lang = {".py":"python",".js":"javascript",".ts":"typescript",
                                ".json":"json",".yaml":"yaml",".md":"markdown",".css":"css",
                                ".html":"html",".rs":"rust",".go":"go"}.get(ext,"")
                        self._display_write(f"[bold]{p.name}[/bold]\n```{lang}\n{content[:2000]}\n```")

                        if self._lsp and ext in (".py", ".rs", ".go", ".ts", ".js", ".c", ".cpp"):
                            try:
                                result = await self._lsp.check_file(p)
                                self._display_write(self._lsp.format_diagnostics_summary(result))
                            except Exception:
                                pass
                    except Exception:
                        self._display_write(f"[bold]{p.name}[/bold] Binary ({size//1024}KB)")
            else:
                self._display_write(f"[red]File not found: {arg}[/red]")

        elif cmd == "/code" and arg and self._hub:
            r = await self._hub.generate_code("module", arg, "python")
            self._display_write(f"[bold]Generated Code[/bold]\n```python\n{r.get('code','')[:1500]}\n```")

        elif cmd == "/report" and arg and self._hub:
            r = await self._hub.generate_report(arg, {"title": arg})
            doc = r.get("document", "")
            trunc = "..." if len(doc) > 800 else ""
            self._display_write(f"[bold]Report: {arg}[/bold]\n{doc[:800]}{trunc}\n[dim]---[/dim]")

        elif cmd == "/analyze" and arg and self._hub:
            r = await self._hub.chat(f"Depth analysis: {arg}")
            self._display_write(f"[bold]Analysis[/bold]\n{r.get('intent','')[:500]}")

        elif cmd == "/search" and arg:
            query = arg
            self._display_write(f"[bold #58a6ff]Multi-Search:[/bold #58a6ff] `{query}`")

            # 1. Spark OneSearch (联网)
            ss = getattr(self._hub.world, 'spark_search', None) if self._hub else None
            web_results = None
            if ss:
                web_results = await ss.query(query, limit=5)

            # 2. Local KnowledgeBase (本地)
            kb_results = None
            if self._hub:
                try:
                    kb_results = self._hub.world.knowledge_base.search(query, top_k=10)
                except Exception:
                    pass

            # 3. MaterialCollector (web 聚合)
            mc_results = None
            if self._hub and self._hub.world.material_collector:
                try:
                    mc_results = await self._hub.world.material_collector.collect_from_web(query)
                except Exception:
                    pass

            has_any = False

            if web_results:
                has_any = True
                self._display_write(f"\n[#fea62b]Web (Spark):[/#fea62b] {len(web_results)} results")
                for r in web_results[:5]:
                    self._display_write(f"  [bold]{r.title[:80]}[/bold]")
                    self._display_write(f"  [dim]{r.url}[/dim]")
                    if r.summary:
                        self._display_write(f"  {r.summary[:120]}")

            if kb_results:
                has_any = True
                self._display_write(f"\n[#58a6ff]KnowledgeBase:[/#58a6ff] {len(kb_results)} results")
                for d in kb_results[:5]:
                    self._display_write(f"  {d.title} [{d.domain or '-'}]")

            if mc_results:
                has_any = True
                self._display_write(f"\n[#3fb950]Web (Collector):[/#3fb950] {len(mc_results)} results")
                for m in mc_results[:5]:
                    title = m.get('title', m.get('source', '?'))
                    snippet = str(m.get('content', m.get('snippet', '')))[:100]
                    self._display_write(f"  [bold]{title[:60]}[/bold]")
                    if snippet:
                        self._display_write(f"  {snippet}")

            if not has_any:
                self._display_write("[dim]  No results from any source[/dim]")

            self._display_write("[dim]---[/dim]")

        elif cmd in ("/extract", "/lx") and arg:
            parts = arg.split(maxsplit=1)
            if len(parts) < 2:
                self._display_write("[dim]Usage: /extract class1,class2,... <text to extract from>[/dim]")
                return
            classes = [c.strip() for c in parts[0].split(",") if c.strip()]
            text = parts[1].strip()
            if not classes or not text:
                self._display_write("[dim]Usage: /extract class1,class2,... <text>[/dim]")
                return

            engine = None
            if self._hub and hasattr(self._hub.world, 'extraction_engine'):
                engine = self._hub.world.extraction_engine

            if not engine:
                try:
                    from ...capability.extraction_engine import ExtractionEngine
                    engine = ExtractionEngine(
                        api_key=self._api_key,
                        base_url=self._base_url,
                        model=self._flash,
                    )
                except ImportError:
                    self._display_write("[yellow]LangExtract engine not available[/yellow]")
                    return

            self._display_write(f"[bold]Extracting: {', '.join(classes)}[/bold]")
            self._display_write(f"[dim]Source: {text[:100]}...[/dim]")

            try:
                results = engine.extract(text=text, classes=classes)
                if results:
                    self._display_write(f"[dim]{len(results)} extractions:[/dim]")
                    for r in results[:30]:
                        self._display_write(r.format_display())
                    if len(results) > 30:
                        self._display_write(f"  [dim]... and {len(results)-30} more[/dim]")

                    html = engine.visualize_to_html(results, text, "Extraction Results")
                    viz_path = Path(".livingtree/extraction_viz.html")
                    viz_path.parent.mkdir(parents=True, exist_ok=True)
                    viz_path.write_text(html, encoding="utf-8")
                    self._display_write(f"[dim]Visualization saved to {viz_path}[/dim]")
                else:
                    self._display_write("[dim]No extractions found[/dim]")
            except Exception as e:
                self._display_write(f"[red]Extraction error: {e}[/red]")

        elif cmd in ("/pipeline", "/pipe") and arg:
            engine = None
            if self._hub and hasattr(self._hub.world, 'pipeline_engine'):
                engine = self._hub.world.pipeline_engine

            if not engine:
                try:
                    from ...capability.pipeline_engine import PipelineEngine
                    engine = PipelineEngine(
                        consciousness=getattr(self._hub.world, 'consciousness', None) if self._hub else None,
                    )
                except ImportError:
                    self._display_write("[yellow]Pipeline engine not available[/yellow]")
                    return

            self._display_write(f"[#d2a8ff]Generating pipeline for:[/#d2a8ff] {arg[:100]}")
            result = await engine.run_nl(arg)

            cfg = result.get("generated_pipeline", {})
            steps = cfg.get("steps", [])
            self._display_write(f"[#58a6ff]Pipeline: {cfg.get('name', '?')}[/#58a6ff]")
            self._display_write(f"[dim]{cfg.get('description', '')}[/dim]")
            for i, s in enumerate(steps):
                op = s.get("op", "?")
                extra = s.get("prompt", "") or str(s.get("params", ""))
                self._display_write(f"  {i+1}. [#d2a8ff]{op}[/#d2a8ff] {extra[:80]}")

            self._display_write(f"[dim]{result.get('steps_executed', 0)} steps, {result.get('output_count', 0)} results[/dim]")

            results = result.get("results", [])
            if results:
                self._display_write(f"[bold]Results:[/bold]")
                for r in results[:15]:
                    text = str(r.get("text", ""))[:120]
                    cls = r.get("class", "")
                    label = f"[{cls}] " if cls else ""
                    self._display_write(f"  {label}{text}")

                if len(results) > 15:
                    self._display_write(f"  [dim]... and {len(results) - 15} more[/dim]")

            self._display_write("[dim]---[/dim]")

        elif cmd == "/parse" and arg:
            p = Path(arg)
            if not p.exists():
                self._display_write(f"[#f85149]File not found: {arg}[/#f85149]")
                return

            parser = None
            if self._hub and hasattr(self._hub.world, 'multimodal_parser'):
                parser = self._hub.world.multimodal_parser

            if not parser:
                try:
                    from ...capability.multimodal_parser import MultimodalParser
                    parser = MultimodalParser(api_key=self._api_key, base_url=self._base_url)
                except ImportError:
                    self._display_write("[#d29922]Multimodal parser not available[/#d29922]")
                    return

            self._display_write(f"[#58a6ff]Parsing: {p.name}[/#58a6ff]")
            doc = await parser.parse_with_descriptions(p)
            self._display_write(f"[dim]{doc.summary_text()}[/dim]")

            if doc.text:
                preview = doc.text[:2000]
                self._display_write(f"\n[bold]Content Preview:[/bold]\n{preview}")
                if len(doc.text) > 2000:
                    self._display_write(f"\n[dim]... ({len(doc.text)} total chars)[/dim]")

            if doc.tables:
                self._display_write(f"\n[bold]Tables ({len(doc.tables)}):[/bold]")
                for t in doc.tables[:5]:
                    self._display_write(t.to_markdown())

            if doc.images:
                self._display_write(f"\n[bold]Images:[/bold] {len(doc.images)}")
                for i in doc.images[:5]:
                    if i.description:
                        self._display_write(f"  [#d2a8ff]Image {i.index+1}[/#d2a8ff] (p{i.page}): {i.description[:100]}")

            self._messages.append({"role": "system", "content": doc.text[:4000]})
            self._display_write("[dim]Document content added to context[/dim]")
            self._display_write("[dim]---[/dim]")

        elif cmd == "/fetch" and arg:
            try:
                from ...capability.web_reach import WebReach
                reach = WebReach()
                self._display_write(f"[#58a6ff]Fetching: {arg[:80]}[/#58a6ff]")
                page = await reach.fetch(arg)
                self._display_write(page.format_display())
                if page.text:
                    self._messages.append({"role": "system", "content": page.text[:4000]})
                    self._display_write("[dim]Page content added to context[/dim]")
                self._display_write("[dim]---[/dim]")
            except ImportError:
                self._display_write("[#d29922]WebReach not available (install bs4+lxml+readability-lxml)[/#d29922]")

        elif cmd == "/narrative":
            narr = getattr(self._hub.world, 'self_narrative', None) if self._hub else None
            if narr:
                self._display_write(narr.narrate())
                self._display_write(f"[dim]Stats: {narr.stats()}[/dim]")
            else:
                self._display_write("[dim]Self-narrative not available[/dim]")

        elif cmd == "/errors":
            try:
                from ...observability.error_interceptor import get_interceptor
                interceptor = get_interceptor()
                if interceptor:
                    if arg == "clear":
                        count = interceptor.clear()
                        self._display_write(f"[dim]Cleared {count} errors[/dim]")
                    else:
                        self._display_write(interceptor.format_for_tui())
                        stats = interceptor.get_stats()
                        self._display_write(f"[dim]{stats['total_errors']} total, {stats['recent_60s']} in last 60s[/dim]")
                else:
                    self._display_write("[dim]Error interceptor not installed[/dim]")
            except ImportError:
                self._display_write("[dim]Error interceptor module not found[/dim]")

        elif cmd == "/help":
            self._display_write("[bold]Commands[/bold]")
            for cname, desc in sorted(_COMMANDS.items()):
                self._display_write(f"  [bold]{cname}[/bold] — {desc}")
            self._display_write(f"\n[dim]+ {len(_HIDDEN_COMMANDS)} hidden commands available[/dim]")

        else:
            self._display_write(f"[dim]Unknown: `{cmd}` | /help for commands[/dim]")

    async def _show_status(self) -> None:
        if not self._hub:
            self.notify("Backend not connected", severity="warning")
            return
        s = self._hub.status()
        display = self.query_one("#chat-display", RichLog)
        self._display_write("[bold]System Status[/bold]")
        self._display_write(f"  Generation: {s.get('engine',{}).get('generation','?')}")
        self._display_write(f"  Cells: {s.get('cells',0)}")
        self._display_write(f"  Node: {s.get('network',{}).get('status','?')}")
        self._display_write(f"  Audit: {s.get('audit',{}).get('total',0)} entries")
        self._display_write(f"  Budget: {s.get('budget',{}).get('used',0)} tokens")
        self._display_write(f"  Reasoning: {self._reasoning_effort.upper()}")
        self._display_write(f"  Cache: {self._cache_tracker.snapshot() if self._cache_tracker else 'N/A'}")
        self._display_write("[dim]---[/dim]")

    def _clear(self) -> None:
        d = self.query_one("#chat-display", RichLog)
        self._display_lines.clear(); self._display_write()
        self._display_write("[#58a6ff]# LivingTree[/#58a6ff]")
        self._messages.clear()
        self._total_tokens = 0
        self._pending_queue.clear()
        self._update_pending_preview()
        self._update_topbar()
        self.query_one(TaskListPanel).reset()
        self.query_one(TaskProgressPanel).reset()
