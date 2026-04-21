"""
聊天会话管理

实现聊天会话管理、消息历史、AI回复等功能
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

from PyQt6.QtCore import QObject, pyqtSignal

from .models import (
    ChatMessage, Conversation, FriendRequest, DeviceInfo,
    MessageStatus, MessageType, DeviceStatus
)
from .protocol import ChatConnection

logger = logging.getLogger(__name__)


class ChatSessionManager(QObject):
    """
    聊天会话管理器
    
    管理所有聊天会话、消息历史、联系人等
    """
    
    # 信号定义
    conversation_updated = pyqtSignal(str)
    new_message = pyqtSignal(str, object)
    friend_request_received = pyqtSignal(object)
    friend_added = pyqtSignal(str)
    friend_removed = pyqtSignal(str)
    ai_reply_received = pyqtSignal(str, str)
    
    def __init__(self, user_id: str, user_name: str, db_path: str = None):
        super().__init__()
        
        self.user_id = user_id
        self.user_name = user_name
        
        self._db_path = db_path or self._get_db_path()
        self._init_db()
        
        self._chat = ChatConnection(user_id, user_name)
        self._chat.message_received.connect(self._on_message_received)
        self._chat.message_sent.connect(self._on_message_sent)
        
        self._conversations: Dict[str, Conversation] = {}
        self._device_map: Dict[str, DeviceInfo] = {}
        self._lock = threading.Lock()
        
        self._friends: Dict[str, DeviceInfo] = {}
        self._friend_requests: Dict[str, FriendRequest] = {}
        self._load_friends()
    
    def _get_db_path(self) -> str:
        db_dir = Path.home() / ".hermes-desktop"
        db_dir.mkdir(parents=True, exist_ok=True)
        return str(db_dir / "p2p_chat.db")
    
    def _init_db(self):
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                msg_type TEXT,
                sender_id TEXT,
                sender_name TEXT,
                receiver_id TEXT,
                content TEXT,
                timestamp REAL,
                status TEXT,
                read INTEGER DEFAULT 0,
                is_ai INTEGER DEFAULT 0,
                file_name TEXT,
                file_size INTEGER DEFAULT 0,
                metadata TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                peer_id TEXT,
                peer_name TEXT,
                is_group INTEGER DEFAULT 0,
                is_temporary INTEGER DEFAULT 0,
                last_message_time REAL,
                unread_count INTEGER DEFAULT 0,
                created_at REAL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                device_id TEXT PRIMARY KEY,
                user_id TEXT,
                user_name TEXT,
                device_name TEXT,
                local_ip TEXT,
                port INTEGER,
                status TEXT,
                added_at REAL,
                last_seen REAL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friend_requests (
                id TEXT PRIMARY KEY,
                from_user TEXT,
                from_name TEXT,
                to_user TEXT,
                message TEXT,
                timestamp REAL,
                status TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_friends(self):
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM friends")
        for row in cursor.fetchall():
            friend = DeviceInfo(
                device_id=row[0],
                user_id=row[1],
                user_name=row[2],
                device_name=row[3],
                local_ip=row[4],
                port=row[5],
                status=DeviceStatus(row[6]),
                last_seen=row[8],
            )
            friend.is_friend = True
            self._friends[row[0]] = friend
        conn.close()
    
    def start(self):
        self._chat.start()
    
    def stop(self):
        self._chat.stop()
    
    def _on_message_received(self, message: ChatMessage):
        conv_id = self._get_or_create_conversation(message.sender_id, message.sender_name)
        conv = self._conversations.get(conv_id)
        if conv:
            conv.add_message(message)
        self._save_message(message, conv_id)
        self.new_message.emit(conv_id, message)
        self.conversation_updated.emit(conv_id)
    
    def _on_message_sent(self, message_id: str):
        self._update_message_status(message_id, MessageStatus.SENT)
    
    def send_message(self, peer_id: str, content: str) -> str:
        device = self._friends.get(peer_id) or self._device_map.get(peer_id)
        if not device:
            return ""
        
        conv_id = self._get_or_create_conversation(peer_id, device.user_name)
        conv = self._conversations.get(conv_id)
        
        message = ChatMessage(
            sender_id=self.user_id,
            sender_name=self.user_name,
            receiver_id=peer_id,
            content=content,
            status=MessageStatus.SENDING,
        )
        
        if conv:
            conv.add_message(message)
        
        self._save_message(message, conv_id)
        
        self._chat.send_message(
            receiver_ip=device.local_ip,
            receiver_port=device.port,
            content=content,
            receiver_id=peer_id,
        )
        
        self.conversation_updated.emit(conv_id)
        return message.id
    
    def send_file(self, peer_id: str, file_path: str) -> str:
        device = self._friends.get(peer_id) or self._device_map.get(peer_id)
        if not device:
            return ""
        
        return self._chat.send_file(
            receiver_ip=device.local_ip,
            receiver_port=device.port,
            file_path=file_path,
            receiver_id=peer_id,
        )
    
    def _get_or_create_conversation(self, peer_id: str, peer_name: str) -> str:
        with self._lock:
            for conv_id, conv in self._conversations.items():
                if conv.peer_id == peer_id:
                    return conv_id
            
            conv = Conversation(
                peer_id=peer_id,
                peer_name=peer_name,
                is_temporary=True,
            )
            self._conversations[conv.id] = conv
            self._save_conversation(conv)
            return conv.id
    
    def get_conversations(self) -> List[Conversation]:
        with self._lock:
            convs = list(self._conversations.values())
            return sorted(convs, key=lambda c: c.last_message_time, reverse=True)
    
    def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        return self._conversations.get(conv_id)
    
    def mark_conversation_read(self, conv_id: str):
        conv = self._conversations.get(conv_id)
        if conv:
            conv.mark_read()
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE messages SET read = 1 WHERE conversation_id = ? AND receiver_id = ?",
                (conv_id, self.user_id)
            )
            cursor.execute(
                "UPDATE conversations SET unread_count = 0 WHERE id = ?",
                (conv_id,)
            )
            conn.commit()
            conn.close()
    
    def add_friend(self, device: DeviceInfo) -> bool:
        if device.device_id == self.user_id:
            return False
        
        device.is_friend = True
        self._friends[device.device_id] = device
        
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO friends 
            (device_id, user_id, user_name, device_name, local_ip, port, status, added_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            device.device_id,
            device.user_id,
            device.user_name,
            device.device_name,
            device.local_ip,
            device.port,
            device.status.value,
            time.time(),
            device.last_seen,
        ))
        conn.commit()
        conn.close()
        
        self.friend_added.emit(device.device_id)
        return True
    
    def remove_friend(self, device_id: str):
        if device_id in self._friends:
            del self._friends[device_id]
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM friends WHERE device_id = ?", (device_id,))
            conn.commit()
            conn.close()
            self.friend_removed.emit(device_id)
    
    def get_friends(self) -> List[DeviceInfo]:
        return list(self._friends.values())
    
    def is_friend(self, device_id: str) -> bool:
        return device_id in self._friends
    
    def update_device(self, device: DeviceInfo):
        self._device_map[device.device_id] = device
        if device.device_id in self._friends:
            existing = self._friends[device.device_id]
            existing.local_ip = device.local_ip
            existing.status = device.status
            existing.last_seen = device.last_seen
    
    def send_friend_request(self, device_id: str, message: str = "") -> bool:
        device = self._friends.get(device_id) or self._device_map.get(device_id)
        if not device:
            return False
        
        request = FriendRequest(
            from_user=self.user_id,
            from_name=self.user_name,
            to_user=device.user_id,
            message=message,
        )
        
        self._friend_requests[request.id] = request
        
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO friend_requests (id, from_user, from_name, to_user, message, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            request.id,
            request.from_user,
            request.from_name,
            request.to_user,
            request.message,
            request.timestamp,
            request.status,
        ))
        conn.commit()
        conn.close()
        
        return True
    
    def accept_friend_request(self, request_id: str) -> bool:
        if request_id not in self._friend_requests:
            return False
        
        request = self._friend_requests[request_id]
        request.status = "accepted"
        
        device = DeviceInfo(
            device_id=request.from_user,
            user_id=request.from_user,
            user_name=request.from_name,
        )
        self.add_friend(device)
        
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE friend_requests SET status = ? WHERE id = ?",
            ("accepted", request_id)
        )
        conn.commit()
        conn.close()
        
        return True
    
    def get_friend_requests(self) -> List[FriendRequest]:
        return list(self._friend_requests.values())
    
    def set_ai_reply_enabled(self, enabled: bool, engine: Callable = None):
        self._chat.set_ai_reply(enabled, engine)
    
    def set_ai_engine(self, engine: Callable):
        self._ai_engine = engine
        self._chat.set_ai_reply(True, engine)
    
    def _save_message(self, message: ChatMessage, conv_id: str):
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO messages
            (id, conversation_id, msg_type, sender_id, sender_name, receiver_id, 
             content, timestamp, status, read, is_ai, file_name, file_size, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message.id,
            conv_id,
            message.msg_type.value,
            message.sender_id,
            message.sender_name,
            message.receiver_id,
            message.content,
            message.timestamp,
            message.status.value,
            int(message.read),
            int(message.is_ai),
            message.file_name,
            message.file_size,
            json.dumps(message.metadata),
        ))
        cursor.execute(
            "UPDATE conversations SET last_message_time = ? WHERE id = ?",
            (message.timestamp, conv_id)
        )
        conn.commit()
        conn.close()
    
    def _save_conversation(self, conv: Conversation):
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO conversations
            (id, peer_id, peer_name, is_group, is_temporary, last_message_time, unread_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conv.id,
            conv.peer_id,
            conv.peer_name,
            int(conv.is_group),
            int(conv.is_temporary),
            conv.last_message_time,
            conv.unread_count,
            conv.created_at,
        ))
        conn.commit()
        conn.close()
    
    def _update_message_status(self, message_id: str, status: MessageStatus):
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE messages SET status = ? WHERE id = ?",
            (status.value, message_id)
        )
        conn.commit()
        conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM messages")
        total_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM friends")
        total_friends = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM conversations")
        total_conversations = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM messages WHERE read = 0 AND receiver_id = ?", (self.user_id,))
        unread_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_messages": total_messages,
            "total_friends": total_friends,
            "total_conversations": total_conversations,
            "unread_count": unread_count,
            "online_friends": sum(1 for f in self._friends.values() if f.is_online()),
        }


__all__ = [
    "ChatSessionManager",
]
