"""AI Chat Screen — Streaming DeepSeek dual-model conversation.

Routes tasks to appropriate model:
- deepseek-v4-flash: intent recognition, quick responses
- deepseek-v4-pro: deep reasoning with thinking mode

Features:
- Streaming token-by-token rendering (typewriter effect)
- Thinking mode display (reasoning_content shown in blue)
- Conversation history with user/AI/system message styling
- Multi-line input with Enter to send
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Optional

import aiohttp
from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Input, Label, RichLog, Static, TextArea, LoadingIndicator,
)


class ChatScreen(Screen):
    """AI Chat screen with DeepSeek streaming integration."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None
        self._messages: list[dict] = []
        self._thinking_tokens: list[str] = []
        self._api_key: str = ""
        self._base_url: str = "https://api.deepseek.com"
        self._flash_model: str = "deepseek-v4-flash"
        self._pro_model: str = "deepseek-v4-pro"
        self._use_pro: bool = False
        self._sending = False

    def set_hub(self, hub) -> None:
        self._hub = hub
        if hub and hasattr(hub, 'config'):
            cfg = hub.config
            self._api_key = cfg.model.deepseek_api_key
            self._base_url = cfg.model.deepseek_base_url
            self._flash_model = cfg.model.flash_model
            self._pro_model = cfg.model.pro_model

    def compose(self) -> ComposeResult:
        yield Vertical(
            ScrollableContainer(
                RichLog(id="chat-history", highlight=True, markup=True, wrap=True),
            ),
            Container(
                Horizontal(
                    TextArea.code_editor(
                        "", language="markdown", id="chat-input",
                    ),
                    Button("Send", variant="primary", id="send-btn"),
                ),
                Horizontal(
                    Label("Enter=Send  Shift+Enter=New Line  Ctrl+L=Clear  Ctrl+P=Pro Mode"),
                    Label("", id="chat-model-indicator"),
                    Button("Pro", variant="default", id="pro-toggle"),
                    Button("Clear", variant="default", id="clear-btn"),
                ),
                id="chat-input-container",
            ),
        )

    def on_mount(self) -> None:
        log = self.query_one("#chat-history", RichLog)
        log.write("[bold green]LivingTree AI Chat[/bold green]")
        log.write("[dim]DeepSeek v4 — Flash: intent/semantic | Pro: deep reasoning + thinking[/dim]")
        log.write("─" * 50)
        self._update_model_indicator()

    @work(exclusive=False)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            await self._send_message()
        elif event.button.id == "clear-btn":
            self._clear_chat()
        elif event.button.id == "pro-toggle":
            self._use_pro = not self._use_pro
            self._update_model_indicator()

    async def _send_message(self) -> None:
        if self._sending:
            return

        text_area = self.query_one("#chat-input", TextArea)
        user_text = text_area.text.strip()
        if not user_text:
            return

        text_area.clear()
        self._sending = True
        log = self.query_one("#chat-history", RichLog)

        # Show user message
        log.write(f"\n[bold green]You:[/bold green] {user_text}")
        self._messages.append({"role": "user", "content": user_text})

        # Detect intent — use flash model
        model_label = "PRO" if self._use_pro else "FLASH"
        log.write(f"[dim italic]  ({model_label} thinking...)[/dim italic]")

        try:
            response = await self._stream_chat_completion(user_text)
            log.write(f"\n[bold #58a6ff]AI:[/bold #58a6ff] {response}")
            self._messages.append({"role": "assistant", "content": response})
        except Exception as e:
            log.write(f"\n[bold red]Error:[/bold red] {e}")

        self._sending = False
        log.write("")

    async def _stream_chat_completion(self, user_text: str) -> str:
        """Stream tokens from DeepSeek API, showing thinking for pro model."""
        log = self.query_one("#chat-history", RichLog)

        if not self._api_key:
            return self._fallback_response(user_text)

        model = self._pro_model if self._use_pro else self._flash_model

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        system_prompt = (
            "你是LivingTree AI助手。回答简洁、准确、有帮助。"
            if not self._use_pro else
            "你是LivingTree深度推理引擎。进行深入的多步推理分析。"
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                *self._messages[-10:],
            ],
            "temperature": 0.3 if not self._use_pro else 0.7,
            "max_tokens": 4096 if not self._use_pro else 8192,
            "stream": True,
        }

        collected: list[str] = []
        thinking_displayed = False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        return f"API Error {resp.status}: {error[:300]}"

                    buffer = b""
                    async for chunk in resp.content.iter_any():
                        buffer += chunk
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            text = line.decode("utf-8").strip()
                            if not text.startswith("data: "):
                                continue
                            data_str = text[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                reasoning = delta.get("reasoning_content", "")
                                content = delta.get("content", "")

                                if reasoning:
                                    if not thinking_displayed:
                                        log.write("[bold #58a6ff]  Thinking:[/bold #58a6ff]")
                                        thinking_displayed = True
                                    self._thinking_tokens.append(reasoning)
                                    log.write(f"[#58a6ff italic]{reasoning}[/#58a6ff italic]")

                                if content:
                                    collected.append(content)
                            except (json.JSONDecodeError, KeyError):
                                continue

        except aiohttp.ClientError as e:
            return f"Connection error: {e}"
        except asyncio.TimeoutError:
            return "Request timed out."

        result = "".join(collected)
        return result if result else "(no response)"

    def _fallback_response(self, text: str) -> str:
        """Fallback when API key not configured."""
        return (
            "API key not configured. Please set your DeepSeek API key.\n\n"
            "To configure:\n"
            "  1. Get key from https://platform.deepseek.com\n"
            "  2. The key is stored encrypted in config/secrets.enc\n\n"
            f"You asked: {text[:100]}"
        )

    def _update_model_indicator(self) -> None:
        try:
            label = self.query_one("#chat-model-indicator", Label)
            btn = self.query_one("#pro-toggle", Button)
            if self._use_pro:
                label.update("[#58a6ff]Mode: PRO (Deep Reasoning)[/#58a6ff]")
                btn.label = "Flash"
                btn.variant = "default"
            else:
                label.update("[dim]Mode: FLASH (Quick)[/dim]")
                btn.label = "Pro"
                btn.variant = "primary"
        except Exception:
            pass

    def _clear_chat(self) -> None:
        log = self.query_one("#chat-history", RichLog)
        log.clear()
        self._messages.clear()
        self._thinking_tokens.clear()
        log.write("[bold green]LivingTree AI Chat[/bold green] — cleared")

    async def refresh(self) -> None:
        self._update_model_indicator()
