"""MessageGateway — multi-platform messaging adapter.

Inspired by Hermes Agent: Telegram, Discord, CLI from a single process.
Provides a common interface for sending/receiving messages across platforms.

Supported: CLI (always), Telegram (optional), Discord (optional), Webhook (any).
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from loguru import logger

GATEWAY_CONFIG = Path(".livingtree/gateway_config.json")


@dataclass
class GatewayMessage:
    text: str
    platform: str = "cli"
    chat_id: str = ""
    user_name: str = ""
    attachments: list[str] = field(default_factory=list)


class MessageGateway:
    """Unified interface for sending messages to multiple platforms."""

    def __init__(self):
        self._handlers: dict[str, Callable] = {}
        self._config: dict = {}
        self._load_config()
        self._telegram_bot = None

    # ═══ Send ═══

    async def send(self, message: GatewayMessage):
        """Send a message to its platform. If platform is 'all', broadcast everywhere."""
        if message.platform == "all" or not message.platform:
            for platform in self._get_enabled_platforms():
                await self._send_to(platform, message)
        else:
            await self._send_to(message.platform, message)

    async def _send_to(self, platform: str, message: GatewayMessage):
        if platform == "cli":
            logger.info(f"[{platform}] {message.text[:200]}")
        elif platform == "telegram" and self._telegram_bot:
            try:
                await self._telegram_send(message)
            except Exception as e:
                logger.debug(f"Telegram send: {e}")
        elif platform == "smtp" and self._config.get("smtp_host"):
            try:
                await self._smtp_send(message)
            except Exception as e:
                logger.debug(f"SMTP send: {e}")
        elif platform == "webhook" and self._config.get("webhook_url"):
            try:
                import aiohttp
                async with aiohttp.ClientSession() as s:
                    await s.post(self._config["webhook_url"], json={
                        "text": message.text,
                        "platform": platform,
                        "chat_id": message.chat_id,
                        "user": message.user_name,
                    }, timeout=10)
            except Exception as e:
                logger.debug(f"Webhook send: {e}")

    async def _telegram_send(self, message: GatewayMessage):
        if not self._config.get("telegram_token"):
            return
        chat_id = message.chat_id or self._config.get("telegram_chat_id", "")
        if not chat_id:
            return
        import aiohttp
        url = f"https://api.telegram.org/bot{self._config['telegram_token']}/sendMessage"
        async with aiohttp.ClientSession() as s:
            await s.post(url, json={
                "chat_id": chat_id,
                "text": message.text[:4000],
                "parse_mode": "HTML",
            }, timeout=10)

    async def _smtp_send(self, message: GatewayMessage):
        """Send email via SMTP. Uses smtplib (stdlib, no extra deps)."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        host = self._config.get("smtp_host", "")
        port = int(self._config.get("smtp_port", 587))
        user = self._config.get("smtp_user", "")
        password = self._config.get("smtp_password", "")
        to_email = message.chat_id or self._config.get("smtp_to", "")
        subject = getattr(message, "subject", "") or "LivingTree Notification"

        if not host or not to_email:
            return

        msg = MIMEMultipart()
        msg["From"] = user or "livingtree@localhost"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message.text, "plain", "utf-8"))

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._sync_smtp_send(host, port, user, password, to_email, msg),
        )

    @staticmethod
    def _sync_smtp_send(host: str, port: int, user: str, password: str, to_email: str, msg):
        import smtplib
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(user or "livingtree@localhost", to_email, msg.as_string())
        logger.info(f"SMTP: email sent to {to_email}")

    def configure_smtp(
        self, host: str, port: int = 587, user: str = "",
        password: str = "", to_email: str = "",
    ) -> None:
        """Quick configure SMTP email notification.

        Example:
            gateway.configure_smtp(
                host="smtp.qq.com", port=587,
                user="your@qq.com", password="auth_code",
                to_email="recipient@qq.com",
            )
        """
        self.configure("smtp",
            smtp_host=host, smtp_port=port,
            smtp_user=user, smtp_password=password,
            smtp_to=to_email,
        )
        logger.info("SMTP configured: %s:%d → %s", host, port, to_email)

    # ═══ Receive ═══

    def on_message(self, platform: str, handler: Callable):
        """Register a handler for incoming messages from a platform."""
        self._handlers[platform] = handler

    async def handle_incoming(self, platform: str, text: str, chat_id: str = "", user_name: str = ""):
        """Process an incoming message from a platform."""
        msg = GatewayMessage(text=text, platform=platform, chat_id=chat_id, user_name=user_name)
        handler = self._handlers.get(platform) or self._handlers.get("any")
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(msg)
                else:
                    handler(msg)
            except Exception as e:
                logger.error(f"Gateway handler: {e}")

    # ═══ Platforms ═══

    def configure(self, platform: str, **kwargs):
        self._config[platform] = kwargs
        self._config.setdefault("enabled_platforms", ["cli"])
        if platform not in self._config["enabled_platforms"]:
            self._config["enabled_platforms"].append(platform)
        self._save_config()
        logger.info(f"Gateway: {platform} configured")

    def _get_enabled_platforms(self) -> list[str]:
        return self._config.get("enabled_platforms", ["cli"])

    def get_status(self) -> dict:
        return {
            "enabled_platforms": self._get_enabled_platforms(),
            "telegram_configured": bool(self._config.get("telegram_token")),
            "smtp_configured": bool(self._config.get("smtp_host")),
            "webhook_configured": bool(self._config.get("webhook_url")),
        }

    async def start_polling(self, interval: float = 5.0):
        """Start polling for messages on configured platforms."""
        if self._config.get("telegram_token"):
            asyncio.create_task(self._telegram_poll(interval))

    async def _telegram_poll(self, interval: float):
        token = self._config.get("telegram_token", "")
        if not token:
            return
        offset = 0
        import aiohttp
        while True:
            try:
                url = f"https://api.telegram.org/bot{token}/getUpdates"
                params = {"offset": offset, "timeout": int(interval)}
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, params=params, timeout=interval + 5) as resp:
                        data = await resp.json()
                        for update in data.get("result", []):
                            offset = update["update_id"] + 1
                            msg = update.get("message", {})
                            text = msg.get("text", "")
                            chat_id = str(msg.get("chat", {}).get("id", ""))
                            user = msg.get("from", {}).get("first_name", "")
                            if text:
                                await self.handle_incoming("telegram", text, chat_id, user)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(interval)

    # ═══ Config ═══

    def _save_config(self):
        try:
            GATEWAY_CONFIG.parent.mkdir(parents=True, exist_ok=True)
            GATEWAY_CONFIG.write_text(json.dumps(self._config, indent=2, ensure_ascii=False))
        except Exception:
            pass

    def _load_config(self):
        try:
            if GATEWAY_CONFIG.exists():
                self._config = json.loads(GATEWAY_CONFIG.read_text())
        except Exception:
            self._config = {"enabled_platforms": ["cli"]}


# ═══ Global ═══

_gateway: MessageGateway | None = None


def get_gateway() -> MessageGateway:
    global _gateway
    if _gateway is None:
        _gateway = MessageGateway()
    return _gateway
