"""
LivingTree WebSocket 服务
=========================

为 Vue 前端提供 WebSocket 实时通信。
"""

import json
import asyncio
from typing import Dict, Any, Optional, Set, Callable
from threading import Lock
from datetime import datetime


class WSConnection:
    def __init__(self, conn_id: str, send_handler: Callable = None):
        self.id = conn_id
        self._send = send_handler or (lambda x: None)
        self.connected_at = datetime.now()
        self.last_active = datetime.now()
        self.metadata: Dict[str, Any] = {}

    async def send(self, data: Dict[str, Any]):
        await self._send(json.dumps(data, ensure_ascii=False, default=str))


class WebSocketManager:
    def __init__(self):
        self._connections: Dict[str, WSConnection] = {}
        self._rooms: Dict[str, Set[str]] = {}
        self._lock = Lock()
        self._life_engine = None

    def bind_life_engine(self, engine):
        self._life_engine = engine

    def register(self, conn_id: str, send_handler: Callable) -> WSConnection:
        conn = WSConnection(conn_id, send_handler)
        with self._lock:
            self._connections[conn_id] = conn
        return conn

    def unregister(self, conn_id: str):
        with self._lock:
            self._connections.pop(conn_id, None)
            for room_members in self._rooms.values():
                room_members.discard(conn_id)

    def join_room(self, conn_id: str, room: str):
        with self._lock:
            self._rooms.setdefault(room, set()).add(conn_id)

    def leave_room(self, conn_id: str, room: str):
        with self._lock:
            if room in self._rooms:
                self._rooms[room].discard(conn_id)

    async def send_to_client(self, conn_id: str, data: Dict[str, Any]):
        with self._lock:
            conn = self._connections.get(conn_id)
        if conn:
            await conn.send(data)

    async def broadcast_to_room(self, room: str, data: Dict[str, Any]):
        with self._lock:
            members = list(self._rooms.get(room, set()))
        for conn_id in members:
            await self.send_to_client(conn_id, data)

    async def broadcast_all(self, data: Dict[str, Any]):
        with self._lock:
            conn_ids = list(self._connections.keys())
        for conn_id in conn_ids:
            await self.send_to_client(conn_id, data)

    async def handle_message(self, conn_id: str, raw_message: str):
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            await self.send_to_client(conn_id, {"type": "error", "error": "Invalid JSON"})
            return

        msg_type = message.get("type", "")

        if msg_type == "chat":
            content = message.get("content", "")
            if self._life_engine and content.strip():
                try:
                    response = await self._life_engine.process(
                        type("Stimulus", (), {"user_input": content, "metadata": {}})
                    )
                    await self.send_to_client(conn_id, {
                        "type": "chat_response",
                        "content": response.text,
                        "trace_id": response.trace_id,
                    })
                except Exception as e:
                    await self.send_to_client(conn_id, {
                        "type": "error",
                        "error": str(e),
                    })
            else:
                await self.send_to_client(conn_id, {
                    "type": "chat_response",
                    "content": f"[未绑定引擎] 收到: {content[:100]}",
                })

        elif msg_type == "ping":
            await self.send_to_client(conn_id, {"type": "pong"})

        elif msg_type == "join_room":
            room = message.get("room", "default")
            self.join_room(conn_id, room)
            await self.send_to_client(conn_id, {"type": "joined_room", "room": room})

        else:
            await self.send_to_client(conn_id, {
                "type": "error",
                "error": f"Unknown message type: {msg_type}",
            })

    def active_connections(self) -> int:
        return len(self._connections)


__all__ = ["WebSocketManager", "WSConnection"]
