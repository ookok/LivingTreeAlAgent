"""Channel Bridge — multi-platform messaging integration.

Inspired by CowAgent's 7-channel architecture (WeChat/Feishu/DingTalk/QQ/WeCom/Web).

Channels:
  weixin      — WeChat via itchat/gewechat (QR code scan)
  feishu      — Feishu/Lark WebSocket bot
  dingtalk    — DingTalk bot via Stream mode
  wecom_bot   — WeCom bot (Enterprise WeChat)
  qq          — QQ bot WebSocket
  terminal    — CLI terminal chat
  web         — Web chat (primary, existing)
"""

from __future__ import annotations

import asyncio
import importlib
import json as _json
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger
import itchat


class ChannelType(str, Enum):
    WEB = "web"
    WEIXIN = "weixin"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    WECOM_BOT = "wecom_bot"
    QQ = "qq"
    TERMINAL = "terminal"


@dataclass
class ChannelConfig:
    channel_type: ChannelType = ChannelType.WEB
    enabled: bool = False
    # WeChat
    weixin_hot_reload: bool = True
    weixin_qrcode: bool = True
    # Feishu
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    # DingTalk
    dingtalk_client_id: str = ""
    dingtalk_client_secret: str = ""
    # WeCom Bot
    wecom_bot_id: str = ""
    wecom_bot_secret: str = ""
    # QQ
    qq_app_id: str = ""
    qq_app_secret: str = ""
    # General
    web_port: int = 8100
    proxy: str = ""         # "http://127.0.0.1:7890" for GFW


@dataclass
class ChannelMessage:
    channel: ChannelType
    user_id: str = ""
    user_name: str = ""
    group_id: str = ""
    text: str = ""
    images: list[bytes] = field(default_factory=list)
    voice_bytes: bytes = b""
    files: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class ChannelBridge:
    """Unified messaging bridge — receive from channels, route to LivingTree, reply back."""

    def __init__(self):
        self._channels: dict[str, Any] = {}
        self._callbacks: list = []
        self._running: bool = False
        self._config = ChannelConfig()

    def configure(self, config: ChannelConfig):
        self._config = config

    def on_message(self, callback):
        """Register a callback for incoming messages from any channel."""
        self._callbacks.append(callback)

    async def start(self):
        """Auto-start ALL available channels silently in background.

        Priority order (most likely to have credentials):
          1. WeCom Bot (企业微信机器人) — token-based, most reliable
          2. Feishu (飞书) — tenant_access_token, WebSocket
          3. DingTalk (钉钉) — Stream mode
          4. WeChat (微信) — itchat QR (requires user scan, lowest priority)
          5. Terminal — always available fallback
        """
        self._running = True
        tasks = []

        # Auto-detect which channels have credentials
        cfg = self._config

        # WeCom Bot: check for env vars or vault secrets
        if cfg.wecom_bot_id or self._auto_load_secret("wework_corp_id"):
            logger.info("ChannelBridge: auto-starting 企业微信")
            tasks.append(asyncio.create_task(self._run_wecom()))

        # Feishu: check for app credentials
        if cfg.feishu_app_id or self._auto_load_secret("feishu_app_id"):
            logger.info("ChannelBridge: auto-starting 飞书")
            tasks.append(asyncio.create_task(self._run_feishu()))

        # DingTalk: check for client credentials
        if cfg.dingtalk_client_id or self._auto_load_secret("dingtalk_client_id"):
            logger.info("ChannelBridge: auto-starting 钉钉")
            tasks.append(asyncio.create_task(self._run_dingtalk()))

        # WeChat: always try (may need QR scan, but will try silently first)
        try:
            importlib.import_module("itchat")
            logger.info("ChannelBridge: auto-starting 微信 (itchat)")
            tasks.append(asyncio.create_task(self._run_weixin()))
        except ImportError:
            logger.debug("ChannelBridge: itchat not installed, skipping WeChat auto-connect")

        # Terminal: always available
        if cfg.channel_type == ChannelType.TERMINAL or not tasks:
            tasks.append(asyncio.create_task(self._run_terminal()))

        # Web: if nothing else, web is default
        if not tasks:
            logger.info("ChannelBridge: no channel credentials found, using web only")

        # Feed all incoming messages to user profile pipeline
        self._callbacks.append(self._auto_profile_feed)

        logger.info(f"ChannelBridge: {len(tasks)} channels auto-started")
        return tasks

    def _auto_load_secret(self, key: str) -> str:
        """Load credential from secrets vault or environment."""
        try:
            from ..config.secrets import get_secret_vault
            return get_secret_vault().get(key, "")
        except Exception:
            return ""

    async def _auto_profile_feed(self, msg: ChannelMessage):
        """Silently feed incoming channel messages to user profile pipeline."""
        try:
            from ..capability.chat_profile import ChannelToUserAdapter
            await ChannelToUserAdapter.on_message(
                platform=msg.channel.value,
                user_id=msg.user_id or "unknown",
                content=msg.text,
                group_id=msg.group_id,
                metadata={"timestamp": msg.timestamp, "user_name": msg.user_name},
            )
        except Exception:
            pass  # Silent — user shouldn't notice this

    async def stop(self):
        self._running = False

    async def send(self, channel: ChannelType, user_id: str, text: str, **kwargs) -> bool:
        handler = getattr(self, f"_send_{channel.value}", None)
        if handler:
            await handler(user_id, text, **kwargs)
            return True
        return False

    def stats(self) -> dict:
        return {
            "active_channels": [c.value for c in ChannelType if c != ChannelType.WEB and self._running],
            "web_port": self._config.web_port,
            "proxy": self._config.proxy,
        }

    # ═══ Channel Listeners ═══

    async def _run_terminal(self):
        """CLI terminal channel — stdin/stdout."""
        import sys
        logger.info("Channel: terminal listening on stdin")
        loop = asyncio.get_event_loop()

        while self._running:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                text = line.strip()
                if text and not text.startswith("/"):
                    msg = ChannelMessage(channel=ChannelType.TERMINAL, text=text, user_id="cli")
                    await self._dispatch(msg)
            except EOFError:
                break
            except Exception as e:
                logger.debug(f"Terminal channel: {e}")
                await asyncio.sleep(0.5)

    async def _run_weixin(self):
        """WeChat via itchat."""
        logger.info("Channel: WeChat (itchat) loading...")

        @itchat.msg_register(itchat.content.TEXT)
        def _on_text(msg):
            asyncio.create_task(self._dispatch(ChannelMessage(
                channel=ChannelType.WEIXIN,
                user_id=msg.get("FromUserName", ""),
                user_name=msg.get("User", {}).get("NickName", ""),
                text=msg.get("Text", ""),
                raw=msg,
            )))

        def _itchat_loop():
            if self._config.weixin_qrcode:
                itchat.auto_login(hotReload=self._config.weixin_hot_reload)
            itchat.run()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _itchat_loop)

    async def _run_feishu(self):
        """Feishu bot via WebSocket."""
        c = self._config
        if not c.feishu_app_id:
            return
        try:
            import aiohttp as _aiohttp
            import hashlib as _hashlib

            logger.info("Channel: Feishu (WebSocket) connecting...")
            async with _aiohttp.ClientSession() as session:
                token_resp = await session.post(
                    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                    json={"app_id": c.feishu_app_id, "app_secret": c.feishu_app_secret},
                )
                if token_resp.status != 200:
                    return
                token = (await token_resp.json()).get("tenant_access_token", "")

                while self._running:
                    resp = await session.post(
                        "https://open.feishu.cn/open-apis/im/v1/messages",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"receive_id_type": "open_id"},
                    )
                    data = await resp.json()
                    for item in data.get("data", {}).get("items", []):
                        text = _json.dumps(item.get("body", {}).get("content", ""))
                        await self._dispatch(ChannelMessage(
                            channel=ChannelType.FEISHU,
                            user_id=item.get("sender", {}).get("id", ""),
                            text=text, raw=item,
                        ))
                    await asyncio.sleep(2)
        except ImportError:
            logger.info("Feishu: aiohttp not installed")
        except Exception as e:
            logger.debug(f"Feishu channel: {e}")

    async def _run_dingtalk(self):
        """DingTalk bot."""
        c = self._config
        if not c.dingtalk_client_id:
            return
        logger.info("Channel: DingTalk placeholder — configure in config.json")

    async def _run_wecom(self):
        """WeCom bot."""
        c = self._config
        if not c.wecom_bot_id:
            return
        logger.info("Channel: WeCom placeholder — configure in config.json")

    async def _run_qq(self):
        """QQ bot."""
        c = self._config
        if not c.qq_app_id:
            return
        logger.info("Channel: QQ placeholder — configure in config.json")

    # ═══ Dispatch ═══

    async def _dispatch(self, msg: ChannelMessage):
        for cb in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(msg)
                else:
                    cb(msg)
            except Exception as e:
                logger.debug(f"Channel callback: {e}")


_bridge: Optional[ChannelBridge] = None


def get_channel_bridge() -> ChannelBridge:
    global _bridge
    if _bridge is None:
        _bridge = ChannelBridge()
    return _bridge
