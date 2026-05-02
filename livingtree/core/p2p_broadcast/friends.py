"""
好友与关系管理系统

实现好友列表管理、关系维护、黑名单等功能
from __future__ import annotations
"""


import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

from PyQt6.QtCore import QObject, pyqtSignal

from .models import DeviceInfo, FriendRequest, DeviceStatus

logger = logging.getLogger(__name__)


class FriendManager(QObject):
    """好友管理器"""
    
    friend_online = pyqtSignal(str)
    friend_offline = pyqtSignal(str)
    friend_status_changed = pyqtSignal(str, object)
    friend_request_received = pyqtSignal(object)
    relationship_changed = pyqtSignal(str, str)
    
    def __init__(self, user_id: str, user_name: str, db_path: str = None):
        super().__init__()
        
        self.user_id = user_id
        self.user_name = user_name
        
        self._db_path = db_path or self._get_db_path()
        self._init_db()
        
        self._friends: Dict[str, DeviceInfo] = {}
        self._blacklist: Dict[str, DeviceInfo] = {}
        self._requests: Dict[str, FriendRequest] = {}
        self._history: List[Dict] = []
        
        self._lock = threading.Lock()
        self._load_data()
    
    def _get_db_path(self) -> str:
        db_dir = Path.home() / ".hermes-desktop"
        db_dir.mkdir(parents=True, exist_ok=True)
        return str(db_dir / "friends.db")
    
    def _init_db(self):
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                device_id TEXT PRIMARY KEY,
                user_id TEXT,
                user_name TEXT,
                device_name TEXT,
                local_ip TEXT,
                public_ip TEXT,
                port INTEGER,
                avatar TEXT,
                status TEXT DEFAULT 'offline',
                remark TEXT,
                group_name TEXT,
                added_at REAL,
                last_seen REAL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                device_id TEXT PRIMARY KEY,
                user_id TEXT,
                user_name TEXT,
                device_name TEXT,
                reason TEXT,
                added_at REAL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friend_requests (
                id TEXT PRIMARY KEY,
                from_user TEXT,
                from_name TEXT,
                from_device TEXT,
                to_user TEXT,
                message TEXT,
                timestamp REAL,
                status TEXT DEFAULT 'pending'
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interaction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                action TEXT,
                timestamp REAL,
                details TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_data(self):
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM friends")
        for row in cursor.fetchall():
            device = DeviceInfo(
                device_id=row[0],
                user_id=row[1],
                user_name=row[2],
                device_name=row[3],
                local_ip=row[4],
                public_ip=row[5] if len(row) > 5 else "",
                port=row[6] if len(row) > 6 else 45679,
                avatar=row[7] if len(row) > 7 else "",
                status=DeviceStatus(row[8]) if len(row) > 8 else DeviceStatus.OFFLINE,
                last_seen=row[10] if len(row) > 10 else time.time(),
            )
            device.is_friend = True
            self._friends[row[0]] = device
        
        cursor.execute("SELECT * FROM blacklist")
        for row in cursor.fetchall():
            device = DeviceInfo(
                device_id=row[0],
                user_id=row[1],
                user_name=row[2],
                device_name=row[3],
            )
            self._blacklist[row[0]] = device
        
        cursor.execute("SELECT * FROM friend_requests WHERE status = 'pending'")
        for row in cursor.fetchall():
            request = FriendRequest(
                id=row[0],
                from_user=row[1],
                from_name=row[2],
                to_user=row[4],
                message=row[5],
                timestamp=row[6],
                status=row[7],
            )
            self._requests[row[0]] = request
        
        conn.close()
    
    def add_friend(self, device: DeviceInfo, remark: str = "", group: str = "") -> bool:
        if device.device_id == self.user_id:
            return False
        
        if device.device_id in self._blacklist:
            return False
        
        device.is_friend = True
        self._friends[device.device_id] = device
        
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO friends 
            (device_id, user_id, user_name, device_name, local_ip, public_ip, port, 
             avatar, status, remark, group_name, added_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            device.device_id, device.user_id, device.user_name, device.device_name,
            device.local_ip, device.public_ip, device.port, device.avatar,
            device.status.value, remark, group, time.time(), device.last_seen,
        ))
        conn.commit()
        conn.close()
        
        self._record_interaction(device.device_id, "friend_added")
        self.relationship_changed.emit(device.device_id, "added")
        return True
    
    def remove_friend(self, device_id: str):
        if device_id in self._friends:
            del self._friends[device_id]
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM friends WHERE device_id = ?", (device_id,))
            conn.commit()
            conn.close()
            self._record_interaction(device_id, "friend_removed")
            self.relationship_changed.emit(device_id, "removed")
    
    def get_friends(self, group: str = None, online_only: bool = False) -> List[DeviceInfo]:
        friends = list(self._friends.values())
        if group:
            friends = [f for f in friends if hasattr(f, 'group_name') and f.group_name == group]
        if online_only:
            friends = [f for f in friends if f.is_online()]
        return friends
    
    def get_friend(self, device_id: str) -> Optional[DeviceInfo]:
        return self._friends.get(device_id)
    
    def update_online_status(self, device_id: str, status: DeviceStatus, last_seen: float = None):
        if device_id not in self._friends:
            return
        
        friend = self._friends[device_id]
        old_status = friend.status
        friend.status = status
        friend.last_seen = last_seen or time.time()
        
        if old_status != status:
            if status == DeviceStatus.ONLINE:
                self.friend_online.emit(device_id)
            else:
                self.friend_offline.emit(device_id)
            self.friend_status_changed.emit(device_id, status)
    
    def get_online_friends(self) -> List[DeviceInfo]:
        return [f for f in self._friends.values() if f.is_online()]
    
    def add_to_blacklist(self, device: DeviceInfo, reason: str = ""):
        if device.device_id in self._friends:
            self.remove_friend(device.device_id)
        
        self._blacklist[device.device_id] = device
        
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO blacklist 
            (device_id, user_id, user_name, device_name, reason, added_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (device.device_id, device.user_id, device.user_name, device.device_name, reason, time.time()))
        conn.commit()
        conn.close()
        
        self._record_interaction(device.device_id, "blacklist_added")
    
    def is_blacklisted(self, device_id: str) -> bool:
        return device_id in self._blacklist
    
    def send_friend_request(self, to_user: str, to_device: str, message: str = "") -> str:
        request = FriendRequest(
            from_user=self.user_id,
            from_name=self.user_name,
            to_user=to_user,
            message=message,
        )
        
        self._requests[request.id] = request
        
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO friend_requests 
            (id, from_user, from_name, from_device, to_user, message, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (request.id, request.from_user, request.from_name, self.user_id, to_user, request.message, request.timestamp, request.status))
        conn.commit()
        conn.close()
        
        return request.id
    
    def accept_request(self, request_id: str, device: DeviceInfo) -> bool:
        if request_id not in self._requests:
            return False
        
        request = self._requests[request_id]
        request.status = "accepted"
        self.add_friend(device)
        
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE friend_requests SET status = 'accepted' WHERE id = ?", (request_id,))
        conn.commit()
        conn.close()
        
        return True
    
    def reject_request(self, request_id: str):
        if request_id in self._requests:
            self._requests[request_id].status = "rejected"
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE friend_requests SET status = 'rejected' WHERE id = ?", (request_id,))
            conn.commit()
            conn.close()
    
    def get_pending_requests(self) -> List[FriendRequest]:
        return [r for r in self._requests.values() if r.status == "pending"]
    
    def get_groups(self) -> List[str]:
        groups = set()
        for friend in self._friends.values():
            if hasattr(friend, 'group_name') and friend.group_name:
                groups.add(friend.group_name)
        return sorted(list(groups))
    
    def _record_interaction(self, device_id: str, action: str, details: str = ""):
        self._history.append({
            "device_id": device_id,
            "action": action,
            "timestamp": time.time(),
            "details": details,
        })
        
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO interaction_history (device_id, action, timestamp, details)
            VALUES (?, ?, ?, ?)
        """, (device_id, action, time.time(), details))
        conn.commit()
        conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_friends": len(self._friends),
            "online_friends": len(self.get_online_friends()),
            "blacklist_count": len(self._blacklist),
            "pending_requests": len(self.get_pending_requests()),
            "groups": len(self.get_groups()),
        }


__all__ = [
    "FriendManager",
]
