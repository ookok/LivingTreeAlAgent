"""RemoteAssist — real-time collaborative observation and assistance.

    Like TeamViewer for AI conversations. A host can invite observers who:
    - See the full conversation in real-time
    - Can type messages (shown dimmed, LLM doesn't respond to them)
    - Can suggest edits and highlight text
    - When host sends a message, LLM sees BOTH parties' input merged

    Observer protocol:
      Observer  → /connect 5193847261 → WS handshake via relay
      Host      ← accepts connection
      Observer  ← enters observation mode (reads only, dimmed text)
      Host      types "帮我改一下这个函数"
      LLM       sees: [Host: 帮我改一下这个函数] [Observer建议: 用lru_cache]
      LLM       responds to host normally

    Key features:
    - 10-digit numeric fixed ID (deterministic, persisted)
    - Real-time conversation fragment sync via WS
    - Dual-mode LLM: host-triggered only, observer context merged
    - Typing indicators (observer sees host typing, vice versa)
    - Suggest edits: observer highlights + proposes text, host accepts/rejects

    Usage:
        /id                         — show my ID
        /connect 5193847261         — request observation of this host
        /observe accept/decline     — host: accept or decline observer
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

ASSIST_DIR = Path(".livingtree/remote_assist")
ID_FILE = ASSIST_DIR / "client_id.json"
SESSION_FILE = ASSIST_DIR / "sessions.json"


# ═══ Client ID ═══

def generate_client_id() -> str:
    """Generate a deterministic 10-digit numeric ID from machine identity.

    Same machine always gets the same ID. Different machines get different IDs.
    10 digits: 0-9 only.
    """
    import uuid
    import platform
    seed = f"{platform.node()}|{uuid.getnode()}|livingtree-client-v1"
    h = hashlib.sha256(seed.encode()).digest()
    num = int.from_bytes(h[:8], "big") % 9_000_000_000 + 1_000_000_000
    return f"{num:010d}"


def get_client_id() -> str:
    """Get or create the client's 10-digit numeric ID."""
    ASSIST_DIR.mkdir(parents=True, exist_ok=True)
    if ID_FILE.exists():
        try:
            data = json.loads(ID_FILE.read_text())
            if data.get("id", "").isdigit() and len(data["id"]) == 10:
                return data["id"]
        except Exception:
            pass
    cid = generate_client_id()
    ID_FILE.write_text(json.dumps({"id": cid, "created": time.time()}, indent=2))
    logger.info(f"Client ID: {cid}")
    return cid


# ═══ Observation Session ═══

@dataclass
class ObserverSession:
    session_id: str
    host_id: str                    # who is being observed
    observer_id: str                # who is watching
    status: str = "pending"         # pending, active, declined, ended
    created_at: float = 0.0
    accepted_at: float = 0.0
    message_count: int = 0          # total messages exchanged
    observer_can_speak: bool = True # can observer type messages?
    observer_can_suggest: bool = True
    control_transferred: bool = False  # host temporarily gave control


@dataclass
class SyncFragment:
    fragment_id: str               # unique per fragment
    sender_id: str                 # who sent it
    sender_role: str               # "host" | "observer"
    content: str = ""              # text content
    msg_type: str = "message"      # message | typing | highlight | suggestion | system
    highlight_range: tuple = ()    # (start, end) for text highlights
    suggestion_id: str = ""        # for edit suggestions
    suggestion_status: str = ""    # pending, accepted, rejected
    timestamp: float = 0.0


class RemoteAssist:
    """Real-time collaborative observation and assistance engine."""

    def __init__(self):
        ASSIST_DIR.mkdir(parents=True, exist_ok=True)
        self._client_id = get_client_id()
        self._sessions: dict[str, ObserverSession] = {}
        self._ws_connections: dict[str, Any] = {}    # session_id → WS connection
        self._observers: dict[str, str] = {}          # observer_id → session_id
        self._hosts: dict[str, str] = {}              # host_id → session_id (for their observers)
        self._fragment_log: list[SyncFragment] = []
        self._pending_connect: dict[str, str] = {}    # target_id → "waiting for host accept"
        self._load_sessions()

    # ═══ Connection Management ═══

    async def request_observe(self, target_id: str, hub=None) -> dict:
        """Request to observe another client. Returns status.

        Args:
            target_id: 10-digit ID of the host to observe
        """
        if target_id == self._client_id:
            return {"status": "error", "message": "不能观察自己"}

        if not target_id.isdigit() or len(target_id) != 10:
            return {"status": "error", "message": f"无效ID: {target_id}。需要10位数字"}

        session_id = f"obs_{target_id}_{self._client_id}_{int(time.time())}"
        session = ObserverSession(
            session_id=session_id,
            host_id=target_id,
            observer_id=self._client_id,
            status="pending",
            created_at=time.time(),
        )
        self._sessions[session_id] = session
        self._pending_connect[self._client_id] = target_id
        self._save_sessions()

        # Send connect request via P2P relay
        try:
            from ..network.p2p_node import get_p2p_node
            node = get_p2p_node()
            await node.send_to_peer(target_id, json.dumps({
                "type": "observe_request",
                "from_id": self._client_id,
                "session_id": session_id,
                "timestamp": time.time(),
            }))
        except Exception as e:
            logger.debug(f"Observe request: {e}")

        return {"status": "pending", "message": f"已发送观察请求到 {target_id}，等待对方接受",
                "session_id": session_id}

    def accept_observer(self, session_id: str) -> dict:
        """Host accepts an observation request."""
        session = self._sessions.get(session_id)
        if not session:
            return {"status": "error", "message": "会话不存在"}

        session.status = "active"
        session.accepted_at = time.time()
        self._observers[session.observer_id] = session_id
        self._hosts[session.host_id] = session_id
        self._save_sessions()

        logger.info(f"Observer accepted: {session.observer_id} → {session.host_id}")
        return {"status": "active", "message": f"观察者 {session.observer_id} 已连接",
                "observer_id": session.observer_id}

    def decline_observer(self, session_id: str) -> dict:
        """Host declines observation."""
        session = self._sessions.get(session_id)
        if not session:
            return {"status": "error", "message": "会话不存在"}
        session.status = "declined"
        self._save_sessions()
        return {"status": "declined"}

    async def end_observation(self, session_id: str = "") -> dict:
        """End an observation session. Either party can end."""
        if session_id:
            session = self._sessions.get(session_id)
        else:
            # Find session by self ID
            session = (
                self._sessions.get(self._observers.get(self._client_id, ""))
                or self._sessions.get(self._hosts.get(self._client_id, ""))
            )

        if not session:
            return {"status": "error", "message": "当前没有观察会话"}

        session.status = "ended"
        self._observers.pop(session.observer_id, None)
        self._hosts.pop(session.host_id, None)
        self._ws_connections.pop(session.session_id, None)
        self._save_sessions()

        logger.info(f"Observation ended: {session.session_id}")
        return {"status": "ended", "session_id": session.session_id}

    # ═══ Real-time Sync ═══

    async def sync_fragment(self, fragment: SyncFragment, hub=None):
        """Send a fragment to the other party via WebSocket relay."""
        self._fragment_log.append(fragment)
        if len(self._fragment_log) > 200:
            self._fragment_log = self._fragment_log[-200:]

        session_id = self._observers.get(self._client_id) or self._hosts.get(self._client_id)
        if not session_id:
            return

        session = self._sessions.get(session_id)
        if not session or session.status != "active":
            return

        target = session.host_id if fragment.sender_role == "observer" else session.observer_id

        try:
            from ..network.p2p_node import get_p2p_node
            node = get_p2p_node()
            await node.send_to_peer(target, json.dumps({
                "type": "observe_sync",
                "fragment": {
                    "fragment_id": fragment.fragment_id,
                    "sender_id": fragment.sender_id,
                    "sender_role": fragment.sender_role,
                    "content": fragment.content,
                    "msg_type": fragment.msg_type,
                    "highlight_range": list(fragment.highlight_range),
                    "suggestion_id": fragment.suggestion_id,
                    "suggestion_status": fragment.suggestion_status,
                    "timestamp": fragment.timestamp,
                },
            }))
        except Exception as e:
            logger.debug(f"Sync fragment: {e}")

    def receive_fragment(self, data: dict) -> SyncFragment:
        """Receive a sync fragment from the other party."""
        f = data.get("fragment", data)
        fragment = SyncFragment(
            fragment_id=f.get("fragment_id", secrets.token_hex(6)),
            sender_id=f.get("sender_id", ""),
            sender_role=f.get("sender_role", ""),
            content=f.get("content", ""),
            msg_type=f.get("msg_type", "message"),
            highlight_range=tuple(f.get("highlight_range", ())),
            suggestion_id=f.get("suggestion_id", ""),
            suggestion_status=f.get("suggestion_status", ""),
            timestamp=f.get("timestamp", time.time()),
        )
        self._fragment_log.append(fragment)
        return fragment

    async def send_typing_indicator(self, is_typing: bool, partial_text: str = ""):
        """Send typing indicator to observer/host."""
        fragment = SyncFragment(
            fragment_id=f"typing_{int(time.time())}",
            sender_id=self._client_id,
            sender_role=self._get_my_role(),
            content=partial_text[:200],
            msg_type="typing" if is_typing else "message",
            timestamp=time.time(),
        )
        await self.sync_fragment(fragment)

    # ═══ Dual-mode LLM ═══

    def build_merged_prompt(self, host_message: str) -> str:
        """Build LLM prompt that includes observer context.

        LLM sees observer's messages as context but only responds to host.
        """
        session_id = self._hosts.get(self._client_id)
        if not session_id:
            return host_message

        # Gather recent observer messages
        observer_msgs = []
        for f in self._fragment_log[-20:]:
            if (f.sender_role == "observer" and f.msg_type == "message"
                    and f.content.strip()):
                observer_msgs.append(f.content)

        if not observer_msgs:
            return host_message

        observer_context = "\n".join(
            f"[观察者建议: {m[:300]}]" for m in observer_msgs[-3:]
        )
        return f"{observer_context}\n\n[用户请求: {host_message}]"

    def get_recent_suggestions(self, n: int = 5) -> list[SyncFragment]:
        """Get recent edit suggestions from observer."""
        return [
            f for f in self._fragment_log[-50:]
            if f.msg_type == "suggestion" and f.suggestion_status == "pending"
        ][-n:]

    def accept_suggestion(self, suggestion_id: str):
        """Mark a suggestion as accepted."""
        for f in self._fragment_log:
            if f.suggestion_id == suggestion_id:
                f.suggestion_status = "accepted"
                break

    # ═══ Status Queries ═══

    @property
    def client_id(self) -> str:
        return self._client_id

    def am_i_host(self) -> bool:
        return self._client_id in self._hosts

    def am_i_observer(self) -> bool:
        return self._client_id in self._observers

    def my_session(self) -> ObserverSession | None:
        sid = self._observers.get(self._client_id) or self._hosts.get(self._client_id)
        return self._sessions.get(sid)

    def _get_my_role(self) -> str:
        if self.am_i_host():
            return "host"
        if self.am_i_observer():
            return "observer"
        return "solo"

    def status(self) -> dict:
        session = self.my_session()
        return {
            "client_id": self._client_id,
            "role": self._get_my_role(),
            "session": {
                "session_id": session.session_id,
                "status": session.status,
                "other_party": session.observer_id if self.am_i_host() else session.host_id,
                "message_count": session.message_count,
                "control_transferred": session.control_transferred,
            } if session else None,
            "active_sessions": len([s for s in self._sessions.values() if s.status == "active"]),
        }

    def _save_sessions(self):
        data = {}
        for sid, s in self._sessions.items():
            data[sid] = {
                "session_id": s.session_id, "host_id": s.host_id,
                "observer_id": s.observer_id, "status": s.status,
                "created_at": s.created_at, "accepted_at": s.accepted_at,
                "message_count": s.message_count,
            }
        SESSION_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_sessions(self):
        if not SESSION_FILE.exists():
            return
        try:
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            for sid, d in data.items():
                self._sessions[sid] = ObserverSession(
                    session_id=sid, host_id=d.get("host_id", ""),
                    observer_id=d.get("observer_id", ""),
                    status=d.get("status", "pending"),
                    created_at=d.get("created_at", 0),
                    accepted_at=d.get("accepted_at", 0),
                    message_count=d.get("message_count", 0),
                )
                s = self._sessions[sid]
                if s.status == "active":
                    self._observers[s.observer_id] = sid
                    self._hosts[s.host_id] = sid
        except Exception:
            pass


_ra: RemoteAssist | None = None


def get_remote_assist() -> RemoteAssist:
    global _ra
    if _ra is None:
        _ra = RemoteAssist()
    return _ra
