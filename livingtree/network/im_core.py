"""IM Core — Instant messaging, presence, contacts, groups, file transfer.

Assembles existing parts (EncryptedChannel, P2PNode, Discovery, WebRTC stack,
VirtualConference) into a unified IM/meeting system.

No external IM protocol. Everything runs through the existing WebSocket + P2P layers.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json as _json
import os
import secrets
import time as _time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger

IM_DIR = Path(".livingtree/im")
IM_DIR.mkdir(parents=True, exist_ok=True)
MSG_STORE = IM_DIR / "messages.jsonl"
CONTACTS_FILE = IM_DIR / "contacts.json"


class OnlineStatus(Enum):
    ONLINE = "online"
    AWAY = "away"
    BUSY = "busy"
    OFFLINE = "offline"


class MessageType(Enum):
    DM = "dm"                 # Direct message
    GROUP = "group_msg"       # Group message
    TYPING = "typing"         # Typing indicator
    READ = "read_receipt"     # Read receipt
    PRESENCE = "presence"     # Status update
    CALL_SIGNAL = "call"      # WebRTC signaling
    FILE_CHUNK = "file_chunk" # File transfer chunk
    FILE_META = "file_meta"   # File metadata
    SYSTEM = "system"         # System notification


@dataclass
class IMMessage:
    msg_id: str
    msg_type: MessageType
    sender_id: str
    sender_name: str = ""
    receiver_id: str = ""         # User ID or group ID
    content: str = ""
    timestamp: float = 0.0
    file_meta: dict | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id, "type": self.msg_type.value,
            "sender_id": self.sender_id, "sender_name": self.sender_name,
            "receiver_id": self.receiver_id, "content": self.content,
            "timestamp": self.timestamp, "file_meta": self.file_meta,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: dict) -> IMMessage:
        return cls(
            msg_id=d.get("msg_id", ""),
            msg_type=MessageType(d.get("type", "dm")),
            sender_id=d.get("sender_id", ""),
            sender_name=d.get("sender_name", ""),
            receiver_id=d.get("receiver_id", ""),
            content=d.get("content", ""),
            timestamp=d.get("timestamp", _time.time()),
            file_meta=d.get("file_meta"),
            extra=d.get("extra", {}),
        )


@dataclass
class Contact:
    user_id: str
    name: str
    avatar: str = ""
    status: OnlineStatus = OnlineStatus.OFFLINE
    last_seen: float = 0.0
    is_friend: bool = False
    groups: list[str] = field(default_factory=list)
    public_key: str = ""

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id, "name": self.name, "avatar": self.avatar,
            "status": self.status.value, "last_seen": self.last_seen,
            "is_friend": self.is_friend, "groups": self.groups,
        }


@dataclass
class Group:
    group_id: str
    name: str
    owner_id: str
    members: list[str] = field(default_factory=list)
    created_at: float = 0.0
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "group_id": self.group_id, "name": self.name,
            "owner_id": self.owner_id, "members": self.members,
            "description": self.description,
        }


# ═══ AES-GCM Encryption (upgrade from XOR) ═══

class SecureChannel:
    """AES-256-GCM authenticated encryption for IM messages."""

    def __init__(self, shared_secret: str = ""):
        self._key = hashlib.sha256(
            (shared_secret or secrets.token_hex(32)).encode()
        ).digest()

    @staticmethod
    def _aes_gcm_encrypt(key: bytes, plaintext: bytes) -> tuple[bytes, bytes, bytes]:
        """Returns (nonce, ciphertext, tag)."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, plaintext, None)
        return nonce, ct[:-16], ct[-16:]

    @staticmethod
    def _aes_gcm_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, tag: bytes) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext + tag, None)

    def encrypt(self, plaintext: str) -> str:
        nonce, ct, tag = self._aes_gcm_encrypt(self._key, plaintext.encode())
        combined = nonce + ct + tag
        import base64
        return base64.b64encode(combined).decode()

    def decrypt(self, ciphertext_b64: str) -> str:
        import base64
        data = base64.b64decode(ciphertext_b64)
        nonce = data[:12]
        ct = data[12:-16]
        tag = data[-16:]
        return self._aes_gcm_decrypt(self._key, nonce, ct, tag).decode()


# ═══ IM Core ═══

class IMCore:
    """Central IM hub: connections, routing, persistence, presence, contacts."""

    def __init__(self):
        self._connections: dict[str, Any] = {}      # user_id → WebSocket
        self._presence: dict[str, OnlineStatus] = {} # user_id → status
        self._contacts: dict[str, dict[str, Contact]] = {}  # user_id → {contact_id → Contact}
        self._groups: dict[str, Group] = {}         # group_id → Group
        self._message_history: list[IMMessage] = []
        self._file_chunks: dict[str, list[bytes]] = {}
        self._active_calls: dict[str, dict] = {}    # call_id → call state
        self._load_state()

    def _load_state(self):
        if CONTACTS_FILE.exists():
            try:
                data = _json.loads(CONTACTS_FILE.read_text())
                for uid, contacts_dict in data.get("contacts", {}).items():
                    self._contacts[uid] = {
                        cid: Contact(**cd) for cid, cd in contacts_dict.items()
                    }
                for gid, gd in data.get("groups", {}).items():
                    self._groups[gid] = Group(**gd)
            except Exception:
                pass

    def _save_state(self):
        CONTACTS_FILE.write_text(_json.dumps({
            "contacts": {
                uid: {cid: c.to_dict() for cid, c in contacts.items()}
                for uid, contacts in self._contacts.items()
            },
            "groups": {gid: g.to_dict() for gid, g in self._groups.items()},
        }, indent=2, ensure_ascii=False))

    def _persist_message(self, msg: IMMessage):
        self._message_history.append(msg)
        try:
            with open(MSG_STORE, "a", encoding="utf-8") as f:
                f.write(_json.dumps(msg.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass

    # ── Connection Management ──

    def connect(self, user_id: str, ws) -> bool:
        self._connections[user_id] = ws
        self.set_presence(user_id, OnlineStatus.ONLINE)
        logger.info(f"IM: {user_id} connected ({len(self._connections)} online)")
        return True

    def disconnect(self, user_id: str):
        self._connections.pop(user_id, None)
        self.set_presence(user_id, OnlineStatus.OFFLINE)
        logger.info(f"IM: {user_id} disconnected")

    def get_connection(self, user_id: str):
        return self._connections.get(user_id)

    # ── Presence ──

    def set_presence(self, user_id: str, status: OnlineStatus):
        self._presence[user_id] = status
        self._broadcast_presence(user_id, status)

    def get_presence(self, user_id: str) -> OnlineStatus:
        return self._presence.get(user_id, OnlineStatus.OFFLINE)

    def _broadcast_presence(self, user_id: str, status: OnlineStatus):
        name = ""
        if user_id in self._contacts:
            for c in self._contacts.get(user_id, {}).values():
                name = c.name
                break
        asyncio.create_task(self._broadcast_to_friends(user_id, IMMessage(
            msg_id=f"presence_{int(_time.time()*1000)}",
            msg_type=MessageType.PRESENCE,
            sender_id=user_id, sender_name=name,
            content=status.value,
            extra={"status": status.value},
        )))

    # ── Contacts ──

    def get_contacts(self, user_id: str) -> list[Contact]:
        return list(self._contacts.get(user_id, {}).values())

    def add_contact(self, user_id: str, contact: Contact) -> bool:
        self._contacts.setdefault(user_id, {})[contact.user_id] = contact
        contact.is_friend = True
        contact.status = self.get_presence(contact.user_id)
        self._save_state()
        return True

    def remove_contact(self, user_id: str, contact_id: str) -> bool:
        if user_id in self._contacts:
            self._contacts[user_id].pop(contact_id, None)
            self._save_state()
        return True

    def get_nearby_users(self, exclude_user_id: str = "") -> list[dict]:
        """Get nearby users from LAN discovery + online presence."""
        nearby = []
        for uid, status in self._presence.items():
            if uid != exclude_user_id and status != OnlineStatus.OFFLINE:
                name = uid[:8]
                for c in self._contacts.get(exclude_user_id, {}).values():
                    if c.user_id == uid:
                        name = c.name
                        break
                nearby.append({"user_id": uid, "name": name, "status": status.value})
        return nearby

    # ── Groups ──

    def create_group(self, name: str, owner_id: str, members: list[str]) -> Group:
        gid = f"grp_{int(_time.time())}_{secrets.token_hex(4)}"
        g = Group(group_id=gid, name=name, owner_id=owner_id,
                   members=list(set(members + [owner_id])),
                   created_at=_time.time())
        self._groups[gid] = g
        self._save_state()
        return g

    def join_group(self, group_id: str, user_id: str) -> bool:
        g = self._groups.get(group_id)
        if g and user_id not in g.members:
            g.members.append(user_id)
            self._save_state()
            return True
        return False

    def get_user_groups(self, user_id: str) -> list[Group]:
        return [g for g in self._groups.values() if user_id in g.members]

    # ── Message Routing ──

    async def send_message(self, msg: IMMessage) -> bool:
        """Route a message to its destination."""
        msg.timestamp = _time.time()
        self._persist_message(msg)

        if msg.msg_type == MessageType.DM:
            return await self._send_to_user(msg.receiver_id, msg)
        elif msg.msg_type == MessageType.GROUP:
            return await self._send_to_group(msg.receiver_id, msg)
        elif msg.msg_type == MessageType.PRESENCE:
            return await self._broadcast_to_friends(msg.sender_id, msg)
        return False

    async def _send_to_user(self, user_id: str, msg: IMMessage) -> bool:
        ws = self._connections.get(user_id)
        if ws:
            try:
                await ws.send_json(msg.to_dict())
                return True
            except Exception:
                pass
        return False

    async def _send_to_group(self, group_id: str, msg: IMMessage) -> bool:
        g = self._groups.get(group_id)
        if not g:
            return False
        sent = 0
        for member_id in g.members:
            if member_id != msg.sender_id:
                ws = self._connections.get(member_id)
                if ws:
                    try:
                        await ws.send_json(msg.to_dict())
                        sent += 1
                    except Exception:
                        pass
        return sent > 0

    async def _broadcast_to_friends(self, user_id: str, msg: IMMessage) -> bool:
        sent = 0
        for contact_id in self._contacts.get(user_id, {}):
            ws = self._connections.get(contact_id)
            if ws:
                try:
                    await ws.send_json(msg.to_dict())
                    sent += 1
                except Exception:
                    pass
        return sent > 0

    def get_history(self, user_id: str, with_user: str = "",
                    group_id: str = "", limit: int = 50) -> list[dict]:
        """Get message history for a conversation."""
        result = []
        for msg in reversed(self._message_history):
            if with_user:
                if (msg.sender_id == with_user and msg.receiver_id == user_id) or \
                   (msg.sender_id == user_id and msg.receiver_id == with_user):
                    result.append(msg.to_dict())
            elif group_id:
                if msg.receiver_id == group_id:
                    result.append(msg.to_dict())
            if len(result) >= limit:
                break
        return list(reversed(result))

    # ── File Transfer ──

    def start_file_receive(self, file_id: str, total_chunks: int, filename: str,
                            file_size: int):
        self._file_chunks[file_id] = []
        logger.info(f"IM file transfer start: {filename} ({file_size} bytes, {total_chunks} chunks)")

    def receive_file_chunk(self, file_id: str, chunk_index: int, data: bytes) -> bool:
        chunks = self._file_chunks.get(file_id)
        if chunks is None:
            return False
        while len(chunks) <= chunk_index:
            chunks.append(b"")
        chunks[chunk_index] = data
        return True

    def finalize_file(self, file_id: str) -> Optional[bytes]:
        chunks = self._file_chunks.pop(file_id, None)
        if not chunks:
            return None
        return b"".join(chunks)

    # ── Call Management ──

    def create_call(self, call_id: str, caller_id: str, callee_ids: list[str],
                     call_type: str = "audio") -> dict:
        self._active_calls[call_id] = {
            "call_id": call_id, "caller": caller_id,
            "callees": callee_ids, "type": call_type,
            "state": "ringing", "started_at": _time.time(),
            "participants": [caller_id],
        }
        return self._active_calls[call_id]

    def get_call(self, call_id: str) -> Optional[dict]:
        return self._active_calls.get(call_id)

    def get_active_calls(self) -> list[dict]:
        return list(self._active_calls.values())

    # ── Virtual Meeting ──

    async def create_meeting(self, topic: str, host_id: str,
                              ai_participants: list[dict] | None = None) -> dict:
        """Create a virtual meeting with AI agent participants."""
        meeting_id = f"mtg_{int(_time.time())}_{secrets.token_hex(4)}"

        participants = [
            {"id": host_id, "name": host_id, "role": "主持人", "is_ai": False},
        ]
        if ai_participants:
            for ap in ai_participants:
                participants.append({
                    "id": ap.get("id", f"ai_{secrets.token_hex(4)}"),
                    "name": ap.get("name", "AI Agent"),
                    "role": ap.get("role", "参与者"),
                    "persona": ap.get("persona", ""),
                    "is_ai": True,
                })

        meeting = {
            "meeting_id": meeting_id, "topic": topic,
            "host_id": host_id, "participants": participants,
            "state": "created", "created_at": _time.time(),
            "transcript": [],
            "agenda": [],
        }

        if ai_participants and hasattr(self, '_hub') and self._hub:
            world = self._hub.world if hasattr(self._hub, 'world') else None
            consc = getattr(world, 'consciousness', None) if world else None
            if consc:
                try:
                    prompt = f"为主题'{topic}'生成3-5个会议议程项。每行一项，以- 开头。"
                    resp = await consc.chain_of_thought(prompt, steps=1)
                    text = resp if isinstance(resp, str) else str(resp)
                    meeting["agenda"] = [
                        l.strip().lstrip("- ").strip()
                        for l in text.split("\n") if l.strip().startswith("-")
                    ][:5]
                except Exception:
                    pass

        self._active_calls[meeting_id] = meeting
        return meeting

    def get_meeting(self, meeting_id: str) -> Optional[dict]:
        return self._active_calls.get(meeting_id)

    def status(self) -> dict:
        return {
            "online_users": len(self._connections),
            "active_calls": len([c for c in self._active_calls.values() if "participants" in c]),
            "groups": len(self._groups),
            "messages_stored": len(self._message_history),
            "users": list(self._connections.keys()),
            "online_status": {
                uid: s.value for uid, s in self._presence.items()
            },
        }


_im_instance: Optional[IMCore] = None


def get_im() -> IMCore:
    global _im_instance
    if _im_instance is None:
        _im_instance = IMCore()
    return _im_instance
