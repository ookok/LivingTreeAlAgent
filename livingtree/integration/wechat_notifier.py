"""WeChat Work (企业微信) Bot — Message decryption, auto-reply, and knowledge base sync.

Architecture:
    WeChat Work Server → webhook POST → WXBizMsgCrypt.decrypt → XML parse
    → TreeLLM reply generation → WXBizMsgCrypt.encrypt → XML response
    → [async] sync to KnowledgeBase

Env vars:
    WEWORK_BOT_TOKEN      - Bot callback token (from WeChat Work admin)
    WEWORK_BOT_AES_KEY    - AES encoding key (43-char base64 from WeChat Work admin)
    WEWORK_CORP_ID        - Enterprise Corp ID (override, default from auth config)
    WEWORK_BOT_ENABLED    - "true" to enable bot (default: true if token set)
"""
from __future__ import annotations

import base64
import hashlib
import os
import random
import struct
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from loguru import logger

# Lazy import for Document to avoid circular deps
_Document: Any = None


def _get_document_cls():
    global _Document
    if _Document is None:
        from ..knowledge.knowledge_base import Document as Doc
        _Document = Doc
    return _Document


# ═══ Config ═══

BOT_TOKEN = os.environ.get("WEWORK_BOT_TOKEN", "")
BOT_AES_KEY_B64 = os.environ.get("WEWORK_BOT_AES_KEY", "")
CORP_ID = os.environ.get("WEWORK_CORP_ID", "")
BOT_ENABLED = os.environ.get("WEWORK_BOT_ENABLED", "true").lower() == "true" if BOT_TOKEN else False

# ═══ WXBizMsgCrypt ═══


class WXBizMsgCrypt:
    """WeChat Work message encryption/decryption (AES-256-CBC)."""

    BLOCK_SIZE = 32

    def __init__(self, token: str, encoding_aes_key: str, corp_id: str):
        self.token = token
        self.corp_id = corp_id
        # Decode 43-char AES key → 32 bytes
        self.aes_key = base64.b64decode(encoding_aes_key + "=")

    def _sha1(self, *args: str) -> str:
        raw = "".join(sorted(args))
        return hashlib.sha1(raw.encode()).hexdigest()

    def verify_signature(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> bool:
        computed = self._sha1(self.token, timestamp, nonce, echostr)
        return computed == msg_signature

    def decrypt(self, encrypted: str) -> tuple[int, str]:
        """Decrypt WeChat Work message. Returns (status_code, plaintext_xml)."""
        try:
            cipher = Cipher(
                algorithms.AES(self.aes_key),
                modes.CBC(self.aes_key[:16]),
            )
            decryptor = cipher.decryptor()
            raw = base64.b64decode(encrypted)
            decrypted = decryptor.update(raw) + decryptor.finalize()

            # Un-pad PKCS7
            pad = decrypted[-1]
            if pad < 1 or pad > 32:
                return -40001, "invalid padding"
            content = decrypted[:-pad]

            # Parse: 16 bytes random + 4 bytes msg_len + msg + corp_id
            msg_len = struct.unpack("!I", content[16:20])[0]
            msg = content[20:20 + msg_len].decode("utf-8")
            received_corp_id = content[20 + msg_len:].decode("utf-8")

            if received_corp_id != self.corp_id:
                logger.warning(f"CorpId mismatch: expected {self.corp_id}, got {received_corp_id}")

            return 0, msg
        except Exception as e:
            logger.error(f"WX decrypt failed: {e}")
            return -40002, str(e)

    def encrypt(self, reply_xml: str, nonce: str, timestamp: str | None = None) -> str:
        """Encrypt a reply message. Returns encrypted XML response string."""
        ts = timestamp or str(int(time.time()))

        # Build plaintext: 16 bytes random + 4 bytes len + xml + corp_id
        random_bytes = os.urandom(16)
        xml_bytes = reply_xml.encode("utf-8")
        corp_bytes = self.corp_id.encode("utf-8")
        plaintext = random_bytes + struct.pack("!I", len(xml_bytes)) + xml_bytes + corp_bytes

        # PKCS7 pad
        pad = self.BLOCK_SIZE - len(plaintext) % self.BLOCK_SIZE
        plaintext += bytes([pad] * pad)

        # AES-CBC encrypt
        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.aes_key[:16]))
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(plaintext) + encryptor.finalize()
        encrypted_b64 = base64.b64encode(encrypted).decode()

        # Compute signature
        signature = self._sha1(self.token, ts, nonce, encrypted_b64)

        # Build response XML
        return (
            f'<xml>'
            f'<Encrypt><![CDATA[{encrypted_b64}]]></Encrypt>'
            f'<MsgSignature><![CDATA[{signature}]]></MsgSignature>'
            f'<TimeStamp>{ts}</TimeStamp>'
            f'<Nonce><![CDATA[{nonce}]]></Nonce>'
            f'</xml>'
        )


# ═══ Message Parser ═══


def parse_message(xml_text: str) -> dict[str, str]:
    """Parse WeChat Work XML message into a dict."""
    root = ET.fromstring(xml_text)
    return {child.tag: (child.text or "") for child in root}


def build_text_reply(to_user: str, from_user: str, content: str) -> str:
    """Build a text reply XML."""
    ts = str(int(time.time()))
    return (
        f"<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{ts}</CreateTime>"
        f"<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        f"</xml>"
    )


# ═══ Bot Handler ═══


class WeWorkBot:
    """Handles WeChat Work bot webhooks: verify → receive → reply → sync to KB."""

    def __init__(
        self,
        token: str = "",
        aes_key: str = "",
        corp_id: str = "",
        kb: Any = None,
        reply_fn: Any = None,
        hub: Any = None,
    ):
        self.enabled = bool(token and aes_key and corp_id)
        self.crypt = WXBizMsgCrypt(token, aes_key, corp_id) if self.enabled else None
        self.corp_id = corp_id
        self.kb = kb
        self.reply_fn = reply_fn  # async fn (message: str, from_user: str) -> str | None
        self.hub = hub  # Hub reference for LLM chat fallback
        self._message_count = 0

    def verify_url(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> tuple[bool, str]:
        """Verify callback URL (GET request). Returns (ok, decrypted_echostr)."""
        if not self.enabled or not self.crypt:
            return False, "bot not enabled"
        if not self.crypt.verify_signature(msg_signature, timestamp, nonce, echostr):
            return False, "signature verification failed"
        code, result = self.crypt.decrypt(echostr)
        return code == 0, result

    async def handle_message(self, msg_signature: str, timestamp: str, nonce: str, body: bytes) -> Optional[str]:
        """Handle incoming bot message (POST). Returns encrypted reply XML or None."""
        if not self.enabled or not self.crypt:
            return None

        # Verify signature on the raw body first
        try:
            root = ET.fromstring(body)
            encrypt_elem = root.find("Encrypt")
            if encrypt_elem is None:
                logger.warning("No Encrypt element in bot message")
                return None
            encrypted = encrypt_elem.text or ""
        except ET.ParseError as e:
            logger.error(f"Failed to parse bot message XML: {e}")
            return None

        if not self.crypt.verify_signature(msg_signature, timestamp, nonce, encrypted):
            logger.warning("Bot message signature verification failed")
            return None

        # Decrypt
        code, xml_text = self.crypt.decrypt(encrypted)
        if code != 0:
            logger.error(f"Bot message decrypt failed: {xml_text}")
            return None

        # Parse
        msg = parse_message(xml_text)
        msg_type = msg.get("MsgType", "")
        from_user = msg.get("FromUserName", "")
        to_user = msg.get("ToUserName", "")
        content = msg.get("Content", "")
        chat_id = msg.get("ChatId", "")
        msg_id = msg.get("MsgId", "")

        logger.info(
            f"Bot msg: type={msg_type} from={from_user} "
            f"chat={chat_id} msgid={msg_id} content={content[:80] if content else ''}"
        )

        # Store in knowledge base (async, don't block reply)
        self._sync_to_kb(msg)

        # Generate auto-reply
        reply_text = await self._generate_reply(content, from_user, chat_id)

        if reply_text:
            reply_xml = build_text_reply(from_user, to_user, reply_text)
            encrypted_reply = self.crypt.encrypt(reply_xml, nonce, timestamp)
            return encrypted_reply

        return None  # No reply (empty response = success)

    def _sync_to_kb(self, msg: dict) -> None:
        """Sync a group chat message to the knowledge base (fire-and-forget)."""
        if self.kb is None:
            return
        try:
            content = msg.get("Content", "")
            if not content or len(content) < 10:
                return

            from_user = msg.get("FromUserName", "unknown")
            chat_id = msg.get("ChatId", "")
            msg_type = msg.get("MsgType", "text")

            Document = _get_document_cls()
            doc = Document(
                title=f"企微群聊 - {chat_id[:8] if chat_id else '私聊'} - {content[:40]}",
                content=content,
                domain="wechat_group",
                source=f"wework_bot:{chat_id}" if chat_id else f"wework_bot:private:{from_user}",
                author=from_user,
                metadata={
                    "from_user": from_user,
                    "chat_id": chat_id,
                    "msg_type": msg_type,
                    "msg_id": msg.get("MsgId", ""),
                    "create_time": msg.get("CreateTime", ""),
                    "platform": "wework_bot",
                },
            )
            self.kb.add_knowledge(doc, skip_dedup=True)
            self._message_count += 1
            if self._message_count % 10 == 0:
                logger.info(f"Bot KB sync: {self._message_count} messages synced")
        except Exception as e:
            logger.warning(f"Bot KB sync failed: {e}")

    async def _generate_reply(self, content: str, from_user: str, chat_id: str) -> Optional[str]:
        """Generate auto-reply using LLM."""
        if not content or not content.strip():
            return None

        # Priority 1: custom reply function
        if self.reply_fn:
            try:
                reply = await self.reply_fn(content, from_user)
                if reply:
                    return reply[:2000]
            except Exception as e:
                logger.error(f"Custom reply fn failed: {e}")

        # Priority 2: TreeLLM via hub reference
        if self.hub and hasattr(self.hub, 'chat'):
            try:
                context_msg = (
                    f"[企微群聊消息 - 来自用户 {from_user}"
                    + (f" 群聊 {chat_id}" if chat_id else "")
                    + f"]\n{content}\n\n请用简洁的中文回复这条消息。"
                )
                result = await self.hub.chat(context_msg)
                if result:
                    resp = result.get("response") or result.get("content") or str(result)
                    return resp[:2000]
            except Exception as e:
                logger.warning(f"TreeLLM reply via hub failed: {e}")

        return None


# ═══ Global instance ═══

_bot_instance: Optional[WeWorkBot] = None


def get_bot(kb: Any = None, reply_fn: Any = None, hub: Any = None) -> WeWorkBot:
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = WeWorkBot(
            token=BOT_TOKEN, aes_key=BOT_AES_KEY_B64, corp_id=CORP_ID,
            kb=kb, reply_fn=reply_fn, hub=hub,
        )
        if _bot_instance.enabled:
            logger.info("WeWork Bot initialized (reply + KB sync)")
        else:
            logger.info("WeWork Bot disabled (no token/aes_key/corp_id)")
    else:
        if kb and not _bot_instance.kb:
            _bot_instance.kb = kb
        if reply_fn and not _bot_instance.reply_fn:
            _bot_instance.reply_fn = reply_fn
        if hub and not _bot_instance.hub:
            _bot_instance.hub = hub
    return _bot_instance


def init_bot(kb: Any = None, reply_fn: Any = None, hub: Any = None) -> WeWorkBot:
    global _bot_instance
    _bot_instance = WeWorkBot(
        token=BOT_TOKEN, aes_key=BOT_AES_KEY_B64, corp_id=CORP_ID,
        kb=kb, reply_fn=reply_fn, hub=hub,
    )
    return _bot_instance
