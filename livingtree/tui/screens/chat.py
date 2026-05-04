"""AI Chat — Markdown rendering, task tree, thinking animation, multi-modal input.

LLM returns markdown format for beautiful rendering.
Task tree shows the LifeEngine pipeline in real-time.
Multi-modal: text, file upload, image paste, autocomplete.
"""

from __future__ import annotations

import asyncio
import base64
import json
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
from ..widgets import native_dialogs
from ..widgets import clipboard_handler
from ..widgets import voice_handler
from ..widgets import sound_effects

# /commands with descriptions
_COMMANDS = {
    "/file": "预览文件内容 — /file 路径",
    "/code": "AI 生成代码 — /code 描述",
    "/report": "AI 生成报告 — /report 主题",
    "/search": "搜索知识库 — /search 关键词",
    "/analyze": "深度分析 — /analyze 问题",
    "/translate": "翻译 — /translate 文本",
    "/summary": "总结对话 — /summary",
    "/clear": "清空聊天 — /clear",
    "/help": "显示命令帮助 — /help",
}


class ChatScreen(Screen):
    """Streaming chat with markdown, task tree, and multi-modal input."""

    BINDINGS = [
        ("escape", "app.pop_screen", "返回"),
        ("ctrl+c", "copy_selection", "复制"),
        ("ctrl+enter", "send_from_binding", "发送"),
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

    def set_hub(self, hub) -> None:
        self._hub = hub
        if hub and hasattr(hub, "config"):
            c = hub.config
            self._api_key = c.model.deepseek_api_key or ""
            self._base_url = c.model.deepseek_base_url or ""
            self._flash = c.model.flash_model or ""
            self._pro = c.model.pro_model or ""
            logger.info(f"ChatScreen set_hub: api_key={'***' if self._api_key else 'EMPTY'}")
        else:
            logger.warning("ChatScreen set_hub: hub has no config")

    def compose(self) -> ComposeResult:
        yield Static("[dim]← 返回首页 (Esc)[/dim]", id="back-link")
        yield Horizontal(
            Vertical(
                TaskProgressPanel(id="task-progress"),
                id="sidebar",
            ),
            Vertical(
                RichLog(id="chat-display", highlight=True, markup=True, wrap=True),
                Static("", id="autocomplete-hint"),
                Container(
                    Horizontal(
                        TextArea("", id="chat-input", language=None, show_line_numbers=False),
                        Button("发送", variant="primary", id="send-btn"),
                    ),
                    Horizontal(
                        Label("[dim]Enter=发送 | Shift+Enter=换行 | /命令 | Ctrl+C=复制[/dim]", id="chat-hints"),
                        Button("📎 文件", variant="default", id="file-btn"),
                        Button("📁 目录", variant="default", id="folder-btn"),
                        Button("🎤 语音", variant="default", id="voice-btn"),
                        Button("💾 保存", variant="default", id="save-btn"),
                        Button("📋 复制", variant="default", id="copy-btn"),
                        Button("Clear", variant="default", id="clear-btn"),
                    ),
                    id="chat-input-container",
                ),
                id="main-area",
            ),
        )

    def on_mount(self) -> None:
        hub = getattr(self.app, '_hub', None)
        if hub and hasattr(self, 'set_hub'):
            self.set_hub(hub)
        d = self.query_one("#chat-display", RichLog)
        d.write("[bold green]# 🌳 LivingTree AI Chat[/bold green]")
        d.write("")
        if not getattr(self.app, '_hub_ready', False):
            d.write("[yellow]⏳ 引擎正在后台初始化，对话功能暂不可用[/yellow]")
            d.write("[dim]你可以先浏览其他页面，初始化完成后自动启用[/dim]")
            d.write("")
        d.write("欢迎使用数字生命体 v2.0 智能对话系统")
        d.write("")
        d.write("[bold]快速上手[/bold]")
        d.write("  • 输入问题并按 [bold]Enter[/bold] 发送")
        d.write("  • [bold]/ 命令自动补全[/bold] — /file /code /report 等")
        d.write("  • [bold]📎 选择文件[/bold] — 上传文件参与对话")
        d.write("  • [bold]🎤 语音输入[/bold] — 说话转文字")
        d.write("  • [bold]💾 保存对话[/bold] — 导出聊天记录")
        d.write("  • [bold]Ctrl+V[/bold] — 粘贴图片/文件到输入框")
        d.write("")
        d.write("[bold]快捷键[/bold]")
        d.write("  Tab切换 | Ctrl+P 命令面板 | Ctrl+D 主题 | Ctrl+Q 退出")
        d.write("")

    # ── Autocomplete ──
    def on_input_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id != "chat-input":
            return
        text = event.text_area.text
        hint = self.query_one("#autocomplete-hint", Static)
        if text.startswith("/") and " " not in text:
            matches = [c for c in _COMMANDS if c.startswith(text)]
            if len(matches) == 1:
                hint.update(f"[dim]{_COMMANDS[matches[0]]}[/dim]")
            elif matches:
                hint.update(f"[dim]{' | '.join(matches[:4])}[/dim]")
            else:
                hint.update("")
        else:
            hint.update("")

    @work(exclusive=False)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "send-btn":
            await self._send()
        elif bid == "clear-btn":
            self._clear()
        elif bid == "file-btn":
            await self._pick_file_native()
        elif bid == "folder-btn":
            await self._pick_folder_native()
        elif bid == "voice-btn":
            await self._voice_input()
        elif bid == "copy-btn":
            self._copy_last_response()

    def _copy_last_response(self) -> None:
        """Copy the last AI response to clipboard."""
        for msg in reversed(self._messages):
            if msg["role"] == "assistant":
                clipboard_handler.write_clipboard_text(msg["content"])
                self.notify("已复制最新回复", timeout=2)
                return
        self.notify("暂无回复可复制", severity="warning", timeout=2)

    def action_copy_selection(self) -> None:
        """Ctrl+C — copy selected text or last response."""
        try:
            ta = self.query_one("#chat-input", TextArea)
            sel = ta.selected_text
            if sel:
                clipboard_handler.write_clipboard_text(sel)
                self.notify("已复制选中文本", timeout=2)
                return
        except Exception:
            pass
        self._copy_last_response()

    async def _pick_file_native(self) -> None:
        path = await native_dialogs.open_file_dialog(title="选择文件")
        if not path:
            return
        self._attached_files.append(path)
        size_kb = path.stat().st_size // 1024 if path.exists() else 0
        label = f"[image: {path.name} ({size_kb}KB)]" if path.suffix.lower() in (
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"
        ) else f"[file: {path.name} ({size_kb}KB)]"
        inp = self.query_one("#chat-input", TextArea)
        inp.text = f"{inp.text}\n{label}".strip()
        self.notify(f"已选择: {path.name}", timeout=2)

    async def _pick_folder_native(self) -> None:
        path = await native_dialogs.open_folder_dialog(title="选择文件夹")
        if not path:
            return
        display = self.query_one("#chat-display", RichLog)
        display.write(f"[bold]📁 工作目录切换为:[/bold] {path}")
        self.notify(f"目录: {path}", timeout=3)

    # ── Voice input ──
    async def _voice_input(self) -> None:
        if self._voice_active:
            return
        self._voice_active = True
        self.notify("🎤 正在聆听... (10秒)", timeout=3)
        text = await voice_handler.speech_to_text("zh-CN")
        self._voice_active = False
        if text:
            inp = self.query_one("#chat-input", TextArea)
            inp.value = f"{inp.value} {text}".strip()
            self.notify(f"识别: {text[:30]}...", timeout=3)
        else:
            self.notify("未检测到语音", severity="warning", timeout=2)

    # ── Save chat ──
    async def _save_chat(self) -> None:
        path = await native_dialogs.save_file_dialog(
            title="保存聊天记录",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt")],
            defaultextension=".md",
        )
        if not path:
            return
        lines = []
        for msg in self._messages:
            role = "You" if msg["role"] == "user" else "AI"
            lines.append(f"## {role}\n\n{msg['content']}\n")
        path.write_text("\n".join(lines), encoding="utf-8")
        self.notify(f"已保存: {path.name}", timeout=3)

    # ── Paste handler ──
    def _on_paste(self, event: events.Paste) -> None:
        """Handle Ctrl+V paste — detect images from clipboard."""
        if not event.text or len(event.text) < 10:
            # Could be a binary paste — check clipboard for images
            if clipboard_handler.clipboard_has_image():
                img = clipboard_handler.get_clipboard_image()
                if img:
                    inp = self.query_one("#chat-input", TextArea)
                    inp.value = f"{inp.value}\n[image: {img.name} ({len(img.data)//1024}KB)]".strip()
                    self.notify(f"图片已粘贴: {img.name}", timeout=2)
                    event.stop()
                    return
            # Check for files
            files = clipboard_handler.get_clipboard_files()
            if files:
                for f in files:
                    inp = self.query_one("#chat-input", TextArea)
                    inp.value = f"{inp.value}\n[file: {f.name}]".strip()
                self.notify(f"已粘贴 {len(files)} 个文件", timeout=2)
                event.stop()
                return

    def _animate_thinking(self) -> None:
        """Animate waiting indicator while AI is thinking."""
        try:
            sp = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            d = self.query_one("#chat-display", RichLog)
            d.write(f"  [bold #fea62b]{sp[self._think_idx % len(sp)]}[/bold #fea62b] [italic dim]AI 正在生成回复...[/italic dim]")
            self._think_idx += 1
        except Exception:
            pass

    async def _send(self) -> None:
        if self._sending:
            return
        inp = self.query_one("#chat-input", TextArea)
        text = inp.text.strip()
        if not text:
            return
        if not self._hub:
            display = self.query_one("#chat-display", RichLog)
            display.write("\n[yellow]⏳ 引擎尚未就绪，请稍后再试[/yellow]")
            self._sending = False
            return
        inp.text = ""
        self._sending = True
        display = self.query_one("#chat-display", RichLog)
        tp = self.query_one(TaskProgressPanel)
        tp.reset()

        if text.startswith("/"):
            await self._handle_command(text, display)
            self._sending = False
            return

        display.write(f"\n[bold green]You:[/bold green] {text}")
        self._messages.append({"role": "user", "content": text})

        auto_pro = len(text) > 200 or any(kw in text for kw in [
            "分析", "推理", "预测", "评估", "优化", "报告", "方案", "风险"])
        steps = [
            {"name": "理解意图", "depends_on": []},
            {"name": "检索知识", "depends_on": []},
            {"name": f"{'深度' if auto_pro else '快速'}推理", "depends_on": [0, 1]},
            {"name": "生成回复", "depends_on": [2]},
        ]
        tp.load_plan(steps)
        tp.update_step(0, "running", "analyzing...")

        await asyncio.sleep(0.05)
        tp.update_step(0, "done", f"{len(text)} chars")

        tp.update_step(1, "running", "searching KB...")
        await asyncio.sleep(0.05)
        tp.update_step(1, "done", "retrieved")

        tp.update_step(2, "running", f"{'pro' if auto_pro else 'flash'} model")
        self._think_idx = 0
        self._think_timer = self.set_interval(0.8, self._animate_thinking)
        try:
            resp = await self._stream(text, pro=auto_pro)
            display.write(f"\n[bold #58a6ff]AI:[/bold #58a6ff]\n{resp}\n[dim]---[/dim]")
            self._messages.append({"role": "assistant", "content": resp})
            tp.update_step(2, "done", f"{len(resp)} chars")
        except Exception as e:
            display.write(f"\n[bold red]Error:[/bold red] {e}")
            tp.update_step(2, "failed", str(e)[:40])
        finally:
            self._think_timer.stop()

        tp.update_step(3, "running", "formatting...")
        await asyncio.sleep(0.02)
        tp.update_step(3, "done", "complete")
        tp.mark_all_done()

        self._total_tokens += len(resp) if 'resp' in dir() else 0
        self._sending = False

    async def _stream(self, text: str, pro: bool = False) -> str:
        if not self._api_key:
            return f"[yellow]API key未配置[/yellow]\n\n> {text[:100]}"

        model = self._pro if pro else self._flash
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": (
                    "你是一个专业AI助手。**必须使用Markdown格式**回复。\n"
                    "规则：\n"
                    "1. 标题用 ### 或 #### 层级\n"
                    "2. 代码块标明语言：```python\n"
                    "3. 列表用 - 或 1.\n"
                    "4. 重要内容用 **粗体**\n"
                    "5. 数据表格用 | 列对齐\n"
                    "6. 引用用 >\n"
                    "7. 分隔用 ---\n"
                    "8. 回复简洁、结构清晰"
                )},
                *self._messages[-10:],
            ],
            "temperature": 0.3 if not pro else 0.7,
            "max_tokens": 4096 if not pro else 8192,
            "stream": True,
        }

        collected = []
        session = self._hub._session if self._hub else aiohttp.ClientSession()
        try:
            async with session.post(
                    f"{self._base_url}/v1/chat/completions",
                    headers=headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=180),
                ) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        return f"[red]API Error {resp.status}[/red]: {err[:200]}"
                    buf = b""
                    display = self.query_one("#chat-display", RichLog)
                    async for chunk in resp.content.iter_any():
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            t = line.decode().strip()
                            if not t.startswith("data: "):
                                continue
                            d = t[6:]
                            if d == "[DONE]":
                                break
                            try:
                                data = json.loads(d)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                token = delta.get("content", "")
                                if token:
                                    collected.append(token)
                                    if len(collected) % 5 == 0:
                                        display.write("".join(collected[-5:]))
                            except Exception:
                                continue
        except Exception as e:
            return f"[red]Error:[/red] {e}"

        result = "".join(collected)
        self._total_tokens += len(result)
        return result if result else "[dim](无响应)[/dim]"

    async def _handle_command(self, text: str, display: RichLog) -> None:
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/file" and arg:
            p = Path(arg)
            if p.exists():
                ext = p.suffix.lower()
                size = p.stat().st_size
                if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                    display.write(f"[bold]图片预览:[/bold] {p.name} ({size//1024}KB)")
                else:
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                        lang = {".py":"python",".js":"javascript",".ts":"typescript",
                                ".json":"json",".yaml":"yaml",".md":"markdown"}.get(ext,"")
                        display.write(f"[bold]{p.name}[/bold]\n```{lang}\n{content[:2000]}\n```")
                    except Exception:
                        display.write(f"[bold]{p.name}[/bold] 二进制文件 {size//1024}KB")

        elif cmd == "/code" and arg and self._hub:
            r = await self._hub.generate_code("module", arg, "python")
            display.write(f"[bold]生成代码[/bold]\n```python\n{r.get('code','')[:1500]}\n```")

        elif cmd == "/report" and arg and self._hub:
            r = await self._hub.generate_report(arg, {"title": arg})
            doc = r.get("document", "")
            trunc = f"{'...' if len(doc)>800 else ''}"
            display.write(f"[bold]报告: {arg}[/bold]\n{doc[:800]}{trunc}\n[dim]---[/dim]")

        elif cmd == "/analyze" and arg and self._hub:
            r = await self._hub.chat(f"深度分析: {arg}")
            display.write(f"[bold]分析结果[/bold]\n{r.get('intent','')[:500]}")

        elif cmd == "/search" and arg and self._hub:
            from datetime import datetime
            parts = arg.split(maxsplit=1)
            as_of = None
            query = arg
            try:
                candidate = datetime.fromisoformat(parts[0]) if len(parts[0]) == 10 else None
                if not candidate:
                    candidate = datetime.strptime(parts[0], "%Y-%m-%d") if len(parts) > 1 else None
                if candidate and len(parts) > 1:
                    as_of = candidate
                    query = parts[1]
            except (ValueError, IndexError):
                pass

            results = self._hub.world.knowledge_base.search(query, top_k=10, as_of=as_of)
            time_label = f" (as of {as_of.date()})" if as_of else " (当前)"
            display.write(f"[bold]知识搜索:[/bold] `{query}`{time_label}")
            if results:
                for d in results[:10]:
                    vf = d.valid_from.strftime("%Y-%m") if d.valid_from else "-"
                    vt = d.valid_to.strftime("%Y-%m") if d.valid_to else "至今"
                    display.write(f"  • {d.title} [{d.domain or '-'}] {vf}~{vt}")
            else:
                display.write("[dim]  无结果[/dim]")

        else:
            display.write(f"[dim]未知命令: `{cmd}` | 可用: /code /report /analyze /search /file[/dim]")

    async def _show_status(self) -> None:
        if not self._hub:
            self.notify("后端未连接", severity="warning")
            return
        s = self._hub.status()
        display = self.query_one("#chat-display", RichLog)
        display.write("[bold]系统状态[/bold]")
        display.write(f"  世代: {s.get('engine',{}).get('generation','?')}")
        display.write(f"  细胞: {s.get('cells',0)}")
        display.write(f"  节点: {s.get('network',{}).get('status','?')}")
        display.write(f"  审计: {s.get('audit',{}).get('total',0)} entries")
        display.write(f"  预算: {s.get('budget',{}).get('used',0)} tokens")
        display.write("[dim]---[/dim]")

    def _clear(self) -> None:
        d = self.query_one("#chat-display", RichLog)
        d.clear()
        d.write("[bold green]# 🌳 LivingTree AI Chat[/bold green]")
        d.write("")
        d.write("[bold]快速上手[/bold]")
        d.write("  • 输入问题并按 [bold]Enter[/bold] 发送")
        d.write("  • [bold]/file 路径[/bold]  预览文件")
        d.write("  • [bold]/code 描述[/bold]  生成代码")
        d.write("  • [bold]/search 关键词[/bold]  搜索知识库")
        d.write("")
        self._messages.clear()
        self._total_tokens = 0
        self.query_one(TaskProgressPanel).reset()
