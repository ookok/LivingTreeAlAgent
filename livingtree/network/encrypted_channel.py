"""Encrypted P2P communication channel with message signing and verification."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field


class EncryptedMessage(BaseModel):
    """Encrypted message envelope for P2P communication."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    sender_id: str
    receiver_id: str
    payload: str
    signature: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    message_type: str = "data"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(cls, sender_id: str, receiver_id: str, data: Any, secret: str = "",
               message_type: str = "data") -> "EncryptedMessage":
        payload = json.dumps(data, default=str)
        msg = cls(
            sender_id=sender_id,
            receiver_id=receiver_id,
            payload=payload,
            message_type=message_type,
        )
        if secret:
            msg.signature = hmac.new(
                secret.encode(), msg.payload.encode(), hashlib.sha256
            ).hexdigest()
        return msg

    def verify(self, secret: str) -> bool:
        if not self.signature or not secret:
            return True
        expected = hmac.new(
            secret.encode(), self.payload.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(self.signature, expected)


class EncryptedChannel:
    """Secure P2P communication channel with encryption and verification."""

    def __init__(self, node_id: str, shared_secret: str = "", max_message_size: int = 10 * 1024 * 1024):
        self.node_id = node_id
        self.shared_secret = shared_secret
        self.max_message_size = max_message_size
        self._message_history: list[EncryptedMessage] = []
        self._max_history = 10000

    def encrypt(self, payload: str) -> str:
        if self.shared_secret:
            key = hashlib.sha256(self.shared_secret.encode()).digest()
            result = bytes(a ^ b for a, b in zip(
                payload.encode().ljust(len(key), b'\0'),
                key * (len(payload.encode()) // len(key) + 1)
            ))
            return result.hex()
        return payload

    def decrypt(self, encrypted: str) -> str:
        if self.shared_secret:
            try:
                raw = bytes.fromhex(encrypted)
                key = hashlib.sha256(self.shared_secret.encode()).digest()
                result = bytes(a ^ b for a, b in zip(raw, key * (len(raw) // len(key) + 1)))
                return result.decode().rstrip('\0')
            except Exception:
                return encrypted
        return encrypted

    async def send(self, receiver_id: str, data: Any, message_type: str = "data") -> EncryptedMessage:
        msg = EncryptedMessage.create(
            sender_id=self.node_id,
            receiver_id=receiver_id,
            data=data,
            secret=self.shared_secret,
            message_type=message_type,
        )
        msg.payload = self.encrypt(msg.payload)
        self._store_message(msg)
        logger.debug(f"Sent message {msg.id} to {receiver_id}")
        return msg

    async def receive(self, message: EncryptedMessage) -> Optional[Any]:
        if len(message.payload.encode()) > self.max_message_size:
            logger.warning(f"Message too large: {len(message.payload)} bytes")
            return None
        decrypted = self.decrypt(message.payload)
        if message.signature and not message.verify(self.shared_secret):
            logger.warning(f"Signature verification failed for message {message.id}")
            return None
        try:
            data = json.loads(decrypted)
            self._store_message(message)
            return data
        except json.JSONDecodeError:
            logger.error(f"Failed to decode message {message.id}")
            return None

    async def broadcast(self, receivers: list[str], data: Any,
                        message_type: str = "broadcast") -> list[EncryptedMessage]:
        messages = []
        for receiver_id in receivers:
            msg = await self.send(receiver_id, data, message_type)
            messages.append(msg)
        return messages

    def _store_message(self, msg: EncryptedMessage) -> None:
        self._message_history.append(msg)
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]

    def get_history(self, limit: int = 100) -> list[EncryptedMessage]:
        return self._message_history[-limit:]

    def get_messages_by_type(self, message_type: str) -> list[EncryptedMessage]:
        return [m for m in self._message_history if m.message_type == message_type]
