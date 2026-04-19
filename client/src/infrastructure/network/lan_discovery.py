"""
局域网聊天系统
LAN Chat System

功能：
- UDP广播发现局域网内的用户
- TCP点对点消息传输
- AI自动回复
- 消息历史记录
"""

import os
import socket
import json
import time
import uuid
import threading
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum
import struct

from PyQt6.QtCore import QObject, pyqtSignal, QTimer


# 常量
DISCOVERY_PORT = 45678
CHAT_PORT = 45679
BROADCAST_INTERVAL = 5  # 秒
USER_TIMEOUT = 30  # 秒


class UserStatus(Enum):
    """用户状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"


@dataclass
class LANUser:
    """局域网用户"""
    id: str
    name: str
    ip_address: str
    port: int
    status: UserStatus = UserStatus.ONLINE
    last_seen: float = field(default_factory=time.time)
    avatar: str = ""

    def is_online(self) -> bool:
        """检查是否在线"""
        return time.time() - self.last_seen < USER_TIMEOUT

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "ip_address": self.ip_address,
            "port": self.port,
            "status": self.status.value,
            "last_seen": self.last_seen,
            "avatar": self.avatar,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LANUser":
        """从字典创建"""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "Unknown"),
            ip_address=data.get("ip_address", ""),
            port=data.get("port", CHAT_PORT),
            status=UserStatus(data.get("status", "online")),
            last_seen=data.get("last_seen", time.time()),
            avatar=data.get("avatar", ""),
        )


@dataclass
class ChatMessage:
    """聊天消息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    sender_name: str = ""
    receiver_id: str = ""
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    read: bool = False
    ai_generated: bool = False  # AI自动生成的回复

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "receiver_id": self.receiver_id,
            "content": self.content,
            "timestamp": self.timestamp,
            "read": self.read,
            "ai_generated": self.ai_generated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        """从字典创建"""
        return cls(
            id=data.get("id", ""),
            sender_id=data.get("sender_id", ""),
            sender_name=data.get("sender_name", ""),
            receiver_id=data.get("receiver_id", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
            read=data.get("read", False),
            ai_generated=data.get("ai_generated", False),
        )


class MessageProtocol:
    """消息协议"""

    # 消息类型
    MSG_DISCOVERY = 1  # 发现广播
    MSG_DISCOVERY_ACK = 2  # 发现响应
    MSG_CHAT = 3  # 聊天消息
    MSG_CHAT_ACK = 4  # 消息确认
    MSG_STATUS = 5  # 状态更新
    MSG_BYE = 6  # 离开通知

    @staticmethod
    def pack_message(msg_type: int, data: Dict[str, Any]) -> bytes:
        """打包消息"""
        content = json.dumps(data, ensure_ascii=False)
        content_bytes = content.encode("utf-8")

        # 格式：类型(1字节) + 长度(4字节) + 内容
        header = struct.pack("!BI", msg_type, len(content_bytes))
        return header + content_bytes

    @staticmethod
    def unpack_message(raw: bytes) -> tuple:
        """解包消息"""
        if len(raw) < 5:
            return None, None

        msg_type, length = struct.unpack("!BI", raw[:5])
        content = raw[5:5+length]

        try:
            data = json.loads(content.decode("utf-8"))
            return msg_type, data
        except Exception:
            return msg_type, None


class LANDiscoveryService(QObject):
    """
    局域网发现服务

    使用UDP广播发现局域网内的用户
    """

    # 信号
    user_found = pyqtSignal(LANUser)  # 发现新用户
    user_left = pyqtSignal(str)  # 用户离开（id）
    user_updated = pyqtSignal(LANUser)  # 用户状态更新

    def __init__(self, user_id: str, user_name: str, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.user_name = user_name

        self._running = False
        self._users: Dict[str, LANUser] = {}
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()

        # 定时器
        self._broadcast_timer: Optional[QTimer] = None
        self._cleanup_timer: Optional[QTimer] = None

    def start(self):
        """启动发现服务"""
        if self._running:
            return

        self._running = True

        # 创建UDP socket
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.settimeout(1.0)

        # 绑定端口
        try:
            self._sock.bind(("", DISCOVERY_PORT))
        except OSError:
            # 端口被占用，使用随机端口
            self._sock.bind(("", 0))

        # 启动接收线程
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

        # 启动广播定时器
        self._broadcast_timer = QTimer(self)
        self._broadcast_timer.timeout.connect(self._broadcast)
        self._broadcast_timer.start(BROADCAST_INTERVAL * 1000)

        # 启动清理定时器
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.timeout.connect(self._cleanup_offline_users)
        self._cleanup_timer.start(10000)

        # 立即广播
        self._broadcast()

    def stop(self):
        """停止发现服务"""
        self._running = False

        # 发送离开通知
        self._send_bye()

        # 停止定时器
        if self._broadcast_timer:
            self._broadcast_timer.stop()
            self._broadcast_timer = None

        if self._cleanup_timer:
            self._cleanup_timer.stop()
            self._cleanup_timer = None

        # 关闭socket
        if self._sock:
            self._sock.close()
            self._sock = None

    def _broadcast(self):
        """发送广播"""
        if not self._sock:
            return

        try:
            # 获取本机IP
            local_ip = self._get_local_ip()

            msg_data = {
                "type": "announce",
                "id": self.user_id,
                "name": self.user_name,
                "ip_address": local_ip,
                "port": CHAT_PORT,
                "version": "2.0.0"
            }

            message = MessageProtocol.pack_message(
                MessageProtocol.MSG_DISCOVERY,
                msg_data
            )

            # 广播到本地网络
            self._sock.sendto(message, ("<broadcast>", DISCOVERY_PORT))

        except Exception as e:
            pass

    def _send_bye(self):
        """发送离开通知"""
        if not self._sock:
            return

        try:
            local_ip = self._get_local_ip()

            msg_data = {
                "type": "bye",
                "id": self.user_id,
            }

            message = MessageProtocol.pack_message(
                MessageProtocol.MSG_BYE,
                msg_data
            )

            self._sock.sendto(message, ("<broadcast>", DISCOVERY_PORT))

        except Exception:
            pass

    def _recv_loop(self):
        """接收循环"""
        while self._running and self._sock:
            try:
                data, addr = self._sock.recvfrom(4096)
                msg_type, msg_data = MessageProtocol.unpack_message(data)

                if msg_type == MessageProtocol.MSG_DISCOVERY:
                    self._handle_discovery(msg_data, addr)
                elif msg_type == MessageProtocol.MSG_DISCOVERY_ACK:
                    self._handle_discovery_ack(msg_data, addr)
                elif msg_type == MessageProtocol.MSG_BYE:
                    self._handle_bye(msg_data)

            except socket.timeout:
                continue
            except Exception:
                if self._running:
                    continue
                break

    def _handle_discovery(self, data: Dict[str, Any], addr):
        """处理发现消息"""
        if data.get("id") == self.user_id:
            # 自己发的，忽略
            return

        user = LANUser(
            id=data.get("id", ""),
            name=data.get("name", "Unknown"),
            ip_address=data.get("ip_address", addr[0]),
            port=data.get("port", CHAT_PORT),
            last_seen=time.time()
        )

        with self._lock:
            is_new = user.id not in self._users
            self._users[user.id] = user

        if is_new:
            self.user_found.emit(user)
        else:
            self.user_updated.emit(user)

        # 发送响应
        self._send_ack(user)

    def _handle_discovery_ack(self, data: Dict[str, Any], addr):
        """处理发现响应"""
        user_id = data.get("id", "")

        if user_id == self.user_id:
            return

        with self._lock:
            if user_id in self._users:
                self._users[user_id].last_seen = time.time()

    def _handle_bye(self, data: Dict[str, Any]):
        """处理离开消息"""
        user_id = data.get("id", "")

        with self._lock:
            if user_id in self._users:
                del self._users[user_id]

        self.user_left.emit(user_id)

    def _send_ack(self, user: LANUser):
        """发送响应"""
        if not self._sock:
            return

        try:
            local_ip = self._get_local_ip()

            msg_data = {
                "type": "ack",
                "id": self.user_id,
                "name": self.user_name,
                "ip_address": local_ip,
                "port": CHAT_PORT,
            }

            message = MessageProtocol.pack_message(
                MessageProtocol.MSG_DISCOVERY_ACK,
                msg_data
            )

            self._sock.sendto(message, (user.ip_address, DISCOVERY_PORT))

        except Exception:
            pass

    def _cleanup_offline_users(self):
        """清理离线用户"""
        with self._lock:
            offline_users = [
                uid for uid, user in self._users.items()
                if not user.is_online()
            ]

            for uid in offline_users:
                del self._users[uid]
                self.user_left.emit(uid)

    def _get_local_ip(self) -> str:
        """获取本机IP"""
        try:
            # 连接到一个外部地址来获取本机IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def get_users(self) -> List[LANUser]:
        """获取所有用户"""
        with self._lock:
            return list(self._users.values())

    def get_user(self, user_id: str) -> Optional[LANUser]:
        """获取指定用户"""
        with self._lock:
            return self._users.get(user_id)


class LANChatService(QObject):
    """
    局域网聊天服务

    使用TCP进行点对点消息传输
    """

    # 信号
    message_received = pyqtSignal(ChatMessage)  # 收到消息
    message_sent = pyqtSignal(ChatMessage)  # 消息发送成功
    message_failed = pyqtSignal(str)  # 消息发送失败（id）
    connection_status_changed = pyqtSignal(str, bool)  # 连接状态变化

    def __init__(self, user_id: str, user_name: str, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.user_name = user_name

        self._running = False
        self._sock: Optional[socket.socket] = None
        self._server_thread: Optional[threading.Thread] = None
        self._pending_messages: Dict[str, ChatMessage] = {}

        # AI回复引擎
        self._ai_reply_enabled = False
        self._ai_engine: Optional[Callable] = None

    def start(self):
        """启动聊天服务"""
        if self._running:
            return

        self._running = True

        # 启动服务器线程
        self._server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self._server_thread.start()

    def stop(self):
        """停止聊天服务"""
        self._running = False

        if self._sock:
            self._sock.close()
            self._sock = None

    def _server_loop(self):
        """服务器循环"""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server_sock.bind(("0.0.0.0", CHAT_PORT))
            server_sock.listen(5)
            server_sock.settimeout(1.0)

            while self._running:
                try:
                    client_sock, addr = server_sock.accept()
                    thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_sock, addr),
                        daemon=True
                    )
                    thread.start()
                except socket.timeout:
                    continue
                except Exception:
                    if self._running:
                        continue
                    break

        except Exception:
            pass
        finally:
            server_sock.close()

    def _handle_client(self, sock: socket.socket, addr):
        """处理客户端连接"""
        try:
            sock.settimeout(10.0)

            # 接收消息
            header = sock.recv(5)
            if len(header) < 5:
                return

            msg_type, length = struct.unpack("!BI", header)
            content = b""
            while len(content) < length:
                chunk = sock.recv(length - len(content))
                if not chunk:
                    break
                content += chunk

            if msg_type == MessageProtocol.MSG_CHAT:
                data = json.loads(content.decode("utf-8"))
                message = ChatMessage.from_dict(data)
                message.receiver_id = self.user_id

                # 发送确认
                ack = MessageProtocol.pack_message(
                    MessageProtocol.MSG_CHAT_ACK,
                    {"message_id": message.id}
                )
                sock.sendall(ack)

                # 发送信号
                self.message_received.emit(message)

                # AI自动回复
                if self._ai_reply_enabled and self._ai_engine:
                    self._generate_ai_reply(message)

        except Exception:
            pass
        finally:
            sock.close()

    def send_message(self, receiver_id: str, receiver_ip: str, receiver_port: int, content: str) -> str:
        """
        发送消息

        Returns:
            消息ID
        """
        message = ChatMessage(
            sender_id=self.user_id,
            sender_name=self.user_name,
            receiver_id=receiver_id,
            content=content
        )

        self._pending_messages[message.id] = message

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            sock.connect((receiver_ip, receiver_port))

            msg_data = MessageProtocol.pack_message(
                MessageProtocol.MSG_CHAT,
                message.to_dict()
            )

            sock.sendall(msg_data)

            # 等待确认
            ack_header = sock.recv(5)
            if len(ack_header) == 5:
                msg_type, length = struct.unpack("!BI", ack_header)
                if msg_type == MessageProtocol.MSG_CHAT_ACK:
                    # 删除待确认消息
                    if message.id in self._pending_messages:
                        del self._pending_messages[message.id]

                    self.message_sent.emit(message)
                    return message.id

            sock.close()

        except Exception as e:
            if message.id in self._pending_messages:
                del self._pending_messages[message.id]
            self.message_failed.emit(message.id)
            return message.id

        return message.id

    def _generate_ai_reply(self, received_message: ChatMessage):
        """生成AI回复"""
        if not self._ai_engine:
            return

        def reply():
            try:
                # 调用AI引擎生成回复
                reply_text = self._ai_engine(received_message.content, received_message.sender_name)

                if reply_text:
                    # 发送回复
                    self.send_message(
                        received_message.sender_id,
                        self.get_user_ip(received_message.sender_id) or "localhost",
                        CHAT_PORT,
                        reply_text
                    )
            except Exception:
                pass

        thread = threading.Thread(target=reply, daemon=True)
        thread.start()

    def get_user_ip(self, user_id: str) -> Optional[str]:
        """获取用户IP（需要外部提供）"""
        # 这个需要从Discovery服务获取
        return None

    def set_ai_reply_enabled(self, enabled: bool, engine: Callable = None):
        """设置AI自动回复"""
        self._ai_reply_enabled = enabled
        if engine:
            self._ai_engine = engine


class LANChatManager:
    """
    局域网聊天管理器

    整合发现服务和聊天服务
    """

    def __init__(self, user_id: str, user_name: str, db_path: str = None):
        self.user_id = user_id
        self.user_name = user_name

        # 发现服务
        self.discovery = LANDiscoveryService(user_id, user_name)

        # 聊天服务
        self.chat = LANChatService(user_id, user_name)

        # 消息数据库
        self._db_path = db_path or self._get_db_path()
        self._init_db()

        # AI引擎
        self._ai_engine: Optional[Callable] = None

        # 连接信号
        self.discovery.user_found.connect(self._on_user_found)
        self.discovery.user_left.connect(self._on_user_left)
        self.chat.message_received.connect(self._on_message_received)

    def _get_db_path(self) -> str:
        """获取数据库路径"""
        db_dir = Path.home() / ".hermes-desktop"
        db_dir.mkdir(parents=True, exist_ok=True)
        return str(db_dir / "lan_chat.db")

    def _init_db(self):
        """初始化数据库"""
        import sqlite3

        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                sender_id TEXT,
                sender_name TEXT,
                receiver_id TEXT,
                content TEXT,
                timestamp REAL,
                read INTEGER DEFAULT 0,
                ai_generated INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT,
                ip_address TEXT,
                port INTEGER,
                last_seen REAL,
                avatar TEXT
            )
        """)

        conn.commit()
        conn.close()

    def start(self):
        """启动聊天服务"""
        self.discovery.start()
        self.chat.start()

        # 设置AI回复
        if self._ai_engine:
            self.chat.set_ai_reply_enabled(True, self._ai_engine)

    def stop(self):
        """停止聊天服务"""
        self.discovery.stop()
        self.chat.stop()

    def set_ai_engine(self, engine: Callable):
        """设置AI引擎"""
        self._ai_engine = engine
        if engine:
            self.chat.set_ai_reply_enabled(True, engine)

    def send_message(self, receiver_id: str, content: str) -> str:
        """发送消息"""
        user = self.discovery.get_user(receiver_id)
        if not user:
            return ""

        return self.chat.send_message(
            receiver_id,
            user.ip_address,
            user.port,
            content
        )

    def get_messages(self, peer_id: str = None, limit: int = 100) -> List[ChatMessage]:
        """获取消息历史"""
        import sqlite3

        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        if peer_id:
            cursor.execute(
                """SELECT * FROM messages
                   WHERE (sender_id = ? AND receiver_id = ?)
                      OR (sender_id = ? AND receiver_id = ?)
                   ORDER BY timestamp DESC LIMIT ?""",
                (self.user_id, peer_id, peer_id, self.user_id, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM messages ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )

        rows = cursor.fetchall()
        conn.close()

        messages = []
        for row in rows:
            messages.append(ChatMessage(
                id=row[0],
                sender_id=row[1],
                sender_name=row[2],
                receiver_id=row[3],
                content=row[4],
                timestamp=row[5],
                read=bool(row[6]),
                ai_generated=bool(row[7])
            ))

        return list(reversed(messages))

    def mark_messages_read(self, peer_id: str):
        """标记消息已读"""
        import sqlite3

        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE messages SET read = 1 WHERE sender_id = ? AND receiver_id = ?",
            (peer_id, self.user_id)
        )

        conn.commit()
        conn.close()

    def get_unread_count(self, peer_id: str = None) -> int:
        """获取未读消息数"""
        import sqlite3

        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        if peer_id:
            cursor.execute(
                "SELECT COUNT(*) FROM messages WHERE sender_id = ? AND receiver_id = ? AND read = 0",
                (peer_id, self.user_id)
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM messages WHERE receiver_id = ? AND read = 0",
                (self.user_id,)
            )

        count = cursor.fetchone()[0]
        conn.close()

        return count

    def _on_user_found(self, user: LANUser):
        """用户上线"""
        # 保存到数据库
        import sqlite3

        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT OR REPLACE INTO users (id, name, ip_address, port, last_seen, avatar)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user.id, user.name, user.ip_address, user.port, user.last_seen, user.avatar)
        )

        conn.commit()
        conn.close()

    def _on_user_left(self, user_id: str):
        """用户离线"""
        pass

    def _on_message_received(self, message: ChatMessage):
        """收到消息"""
        # 保存到数据库
        import sqlite3

        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT OR REPLACE INTO messages
               (id, sender_id, sender_name, receiver_id, content, timestamp, read, ai_generated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                message.id, message.sender_id, message.sender_name,
                message.receiver_id, message.content, message.timestamp,
                int(message.read), int(message.ai_generated)
            )
        )

        conn.commit()
        conn.close()


# 单例
_lan_chat_manager: Optional[LANChatManager] = None


def get_lan_chat_manager(user_id: str = None, user_name: str = "Hermes") -> LANChatManager:
    """获取LAN聊天管理器单例"""
    global _lan_chat_manager
    if _lan_chat_manager is None:
        _lan_chat_manager = LANChatManager(
            user_id or str(uuid.uuid4()),
            user_name
        )
    return _lan_chat_manager


def init_lan_chat_async(user_id: str = None, user_name: str = "Hermes") -> LANChatManager:
    """异步初始化LAN聊天"""
    manager = get_lan_chat_manager(user_id, user_name)
    manager.start()
    return manager


# 别名
LANDiscovery = LANDiscoveryService
