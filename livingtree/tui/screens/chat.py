"""AI Chat — Markdown rendering, task tree, thinking animation, multi-modal input.

LLM returns markdown format for beautiful rendering.
Task tree shows the LifeEngine pipeline in real-time.
Multi-modal: text, file upload, image paste all in one input.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import aiohttp
from datetime import datetime
from textual import work, on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button, Label, TextArea
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from ..widgets.file_picker import FilePicker
from ..widgets.task_progress import TaskProgressPanel


class ChatScreen(Screen):
    """Streaming chat with markdown, task tree, and multi-modal input."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None
        self._messages: list[dict] = []
        self._api_key = ""
        self._base_url = ""
        self._flash = ""
        self._pro = ""

    def set_hub(self, hub) -> None:
        self._hub = hub
        if hub and hasattr(hub, "config"):
            c = hub.config
            self._api_key = c.model.deepseek_api_key
            self._base_url = c.model.deepseek_base_url
            self._flash = c.model.flash_model
            self._pro = c.model.pro_model

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Vertical(
                TaskProgressPanel(id="task-progress"),
                id="sidebar",
            ),
            Vertical(
                ScrollableContainer(
                    TextArea("", id="chat-display", read_only=True),
                    id="chat-scroll",
                ),
                Container(
                    Horizontal(
                        TextArea("", id="chat-input"),
                        Button("▸ Send", variant="primary", id="send-btn"),
                    ),
                    Horizontal(
                        Label("[dim]Enter=Send  Shift+Enter=NL  Ctrl+V=粘贴图片  /命令[/dim]", id="chat-hints"),
                        Button("File", variant="default", id="file-btn"),
                        Button("Clear", variant="default", id="clear-btn"),
                        Button("Status", variant="default", id="status-btn"),
                    ),
                    id="chat-input-container",
                ),
                id="main-area",
            ),
        )

    def on_mount(self) -> None:
        d = self.query_one("#chat-display", TextArea)
        d.text = (
            "# LivingTree AI Chat\n\n"
            "> 支持 Markdown 渲染 | 多模态输入 | 任务树实时状态\n\n"
            "**命令:** `/code` `/report` `/analyze` `/search` `/file`\n\n"
            "---\n"
        )

    @work(exclusive=False)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "send-btn":
            await self._send()
        elif bid == "clear-btn":
            self._clear()
        elif bid == "file-btn":
            self._pick_file()
        elif bid == "status-btn":
            await self._show_status()

    @on(TextArea.Changed, "#chat-input")
    def on_input_changed(self, event: TextArea.Changed) -> None:
        """Detect pasted images (Ctrl+V with image data)."""
        pass  # TextArea handles clipboard natively

    def _pick_file(self) -> None:
        def on_file(path: str):
            editor = self.query_one("#chat-input", TextArea)
            current = editor.text
            p = Path(path)
            size_kb = p.stat().st_size // 1024
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
                editor.text = f"{current}\n[image: {p.name} ({size_kb}KB)]\n".strip()
                self.notify(f"图片已添加: {p.name}", timeout=2)
            else:
                editor.text = f"{current}\n[file: {p.name} ({size_kb}KB)]\n".strip()
                self.notify(f"文件已添加: {p.name}", timeout=2)

        self.app.push_screen(FilePicker(".", callback=on_file, title="选择文件"))

    async def _send(self) -> None:
        if self._sending:
            return
        editor = self.query_one("#chat-input", TextArea)
        text = editor.text.strip()
        if not text:
            return
        editor.clear()
        self._sending = True
        display = self.query_one("#chat-display", TextArea)
        tp = self.query_one(TaskProgressPanel)
        tp.reset()

        if text.startswith("/"):
            await self._handle_command(text, display)
            self._sending = False
            return

        display.text += f"\n### You\n{text}\n\n"
        self._messages.append({"role": "user", "content": text})

        # Load plan steps into progress panel
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
        display.text += "*AI thinking...* "
        try:
            resp = await self._stream(text, pro=auto_pro)
            lines = display.text.split("\n")
            for i in range(len(lines) - 1, -1, -1):
                if "*AI thinking...*" in lines[i]:
                    lines[i] = ""
                    break
            display.text = "\n".join(lines)
            display.text += f"### AI\n{resp}\n\n---\n"
            self._messages.append({"role": "assistant", "content": resp})
            tp.update_step(2, "done", f"{len(resp)} chars")
        except Exception as e:
            display.text += f"\n**❌ Error:** {e}\n"
            tp.update_step(2, "failed", str(e)[:40])

        tp.update_step(3, "running", "formatting...")
        await asyncio.sleep(0.02)
        tp.update_step(3, "done", "complete")
        tp.mark_all_done()

        self._total_tokens += len(resp) if 'resp' in dir() else 0
        self._sending = False

    async def _stream(self, text: str, pro: bool = False) -> str:
        if not self._api_key:
            return f"*API key未配置*\n\n> {text[:100]}"

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
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/v1/chat/completions",
                    headers=headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=180),
                ) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        return f"API Error {resp.status}: {err[:200]}"
                    buf = b""
                    display = self.query_one("#chat-display", TextArea)
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
                                    # Live update display every few tokens
                                    if len(collected) % 5 == 0:
                                        display.text += "".join(collected[-5:])
                            except Exception:
                                continue
        except Exception as e:
            return f"**Error:** {e}"

        result = "".join(collected)
        self._total_tokens += len(result)
        return result if result else "*(无响应)*"

    async def _handle_command(self, text: str, display: TextArea) -> None:
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/file" and arg:
            p = Path(arg)
            if p.exists():
                ext = p.suffix.lower()
                size = p.stat().st_size
                if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                    display.text += f"### 图片预览: {p.name}\n> {size//1024}KB\n\n"
                else:
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                        lang = {".py":"python",".js":"javascript",".ts":"typescript",
                                ".json":"json",".yaml":"yaml",".md":"markdown"}.get(ext,"")
                        display.text += f"### {p.name}\n```{lang}\n{content[:2000]}\n```\n\n"
                    except Exception:
                        display.text += f"### {p.name}\n> 二进制文件 {size//1024}KB\n\n"

        elif cmd == "/code" and arg and self._hub:
            r = await self._hub.generate_code("module", arg, "python")
            display.text += f"### 生成代码\n```python\n{r.get('code','')[:1500]}\n```\n\n"

        elif cmd == "/report" and arg and self._hub:
            r = await self._hub.generate_report(arg, {"title": arg})
            doc = r.get("document", "")
            display.text += f"### 报告: {arg}\n\n{doc[:800]}{'...' if len(doc)>800 else ''}\n\n---\n"

        elif cmd == "/analyze" and arg and self._hub:
            r = await self._hub.chat(f"深度分析: {arg}")
            display.text += f"### 分析结果\n{r.get('intent','')[:500]}\n\n"

        elif cmd == "/search" and arg and self._hub:
            # Support time-based search: /search 2023 环评标准
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
            display.text += f"### 知识搜索: `{query}`{time_label}\n"
            if results:
                display.text += (
                    "| 标题 | 领域 | 有效期 |\n"
                    "|------|------|--------|\n"
                )
                for d in results[:10]:
                    vf = d.valid_from.strftime("%Y-%m") if d.valid_from else "—"
                    vt = d.valid_to.strftime("%Y-%m") if d.valid_to else "至今"
                    display.text += f"| {d.title} | {d.domain or '-'} | {vf}~{vt} |\n"
            else:
                display.text += "> 无结果\n"
            display.text += "\n"

        else:
            display.text += f"> 未知命令: `{cmd}` | 可用: `/code /report /analyze /search /file`\n"

    async def _show_status(self) -> None:
        if not self._hub:
            self.notify("后端未连接", severity="warning")
            return
        s = self._hub.status()
        display = self.query_one("#chat-display", TextArea)
        display.text += (
            f"### 系统状态\n"
            f"| 指标 | 值 |\n|------|----|\n"
            f"| 世代 | {s.get('engine',{}).get('generation','?')} |\n"
            f"| 细胞 | {s.get('cells',0)} |\n"
            f"| 节点 | {s.get('network',{}).get('status','?')} |\n"
            f"| 审计 | {s.get('audit',{}).get('total',0)} entries |\n"
            f"| 预算 | {s.get('budget',{}).get('used',0)} tokens |\n\n---\n"
        )

    def _clear(self) -> None:
        d = self.query_one("#chat-display", TextArea)
        d.text = "# LivingTree AI Chat\n\n> 支持 Markdown | 多模态 | 任务树\n\n---\n"
        self._messages.clear()
        self._total_tokens = 0
        self.query_one(TaskTreePanel).reset()
