"""
P2P通信协议

实现消息传输、文件传输、心跳保活等核心通信功能
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import socket
import struct
import threading
import time
import uuid
from typing import Dict, Optional, List, Callable, Any
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from .models import (
    ChatMessage, MessageType, MessageStatus, DeviceInfo,
    CHAT_PORT, HEARTBEAT_INTERVAL, CONNECTION_TIMEOUT, ConnectionType
)

logger = logging.getLogger(__name__)


class ProtocolHandler:
    """通信协议处理器"""
    
    # 消息头格式: 魔数(4) + 版本(1) + 类型(1) + 长度(4) = 10字节
    MAGIC = b"HMS1"  # Hermes 协议标识
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
    
    def register(self, msg_type: str, handler: Callable):
        """注册消息处理器"""
        self._handlers[msg_type] = handler
    
    def handle(self, msg_type: str, data: bytes, addr: tuple):
        """处理消息"""
        handler = self._handlers.get(msg_type)
        if handler:
            try:
                handler(data, addr)
            except Exception as e:
                logger.error(f"Handler error for {msg_type}: {e}")
    
    @staticmethod
    def pack_message(msg_type: str, data: Dict[str, Any]) -> bytes:
        """打包消息"""
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        
        # 格式: 魔数(4) + 版本(1) + 类型(1) + 长度(4) + 内容
        header = ProtocolHandler.MAGIC + b"\x01" + msg_type.encode("utf-8")[:1] + struct.pack("!I", len(content))
        return header + content
    
    @staticmethod
    def pack_text_message(content: str, sender_id: str, sender_name: str, 
                         receiver_id: str, msg_id: str = None) -> bytes:
        """打包文本消息"""
        msg_id = msg_id or str(uuid.uuid4())
        data = {
            "id": msg_id,
            "type": "text",
            "sender_id": sender_id,
            "sender_name": sender_name,
            "receiver_id": receiver_id,
            "content": content,
            "timestamp": time.time(),
        }
        return ProtocolHandler.pack_message("T", data)
    
    @staticmethod
    def pack_ack(message_id: str) -> bytes:
        """打包确认消息"""
        data = {"message_id": message_id, "timestamp": time.time()}
        return ProtocolHandler.pack_message("A", data)
    
    @staticmethod
    def pack_file_request(file_name: str, file_size: int, file_hash: str,
                         sender_id: str, sender_name: str, receiver_id: str) -> bytes:
        """打包文件请求"""
        data = {
            "id": str(uuid.uuid4()),
            "type": "file_request",
            "sender_id": sender_id,
            "sender_name": sender_name,
            "receiver_id": receiver_id,
            "file_name": file_name,
            "file_size": file_size,
            "file_hash": file_hash,
            "timestamp": time.time(),
        }
        return ProtocolHandler.pack_message("F", data)
    
    @staticmethod
    def unpack_message(raw: bytes) -> Optional[tuple]:
        """解包消息"""
        if len(raw) < 9:
            return None, None, None
        
        try:
            magic = raw[:4]
            if magic != ProtocolHandler.MAGIC:
                return None, None, None
            
            msg_type_byte = raw[4]
            length = struct.unpack("!I", raw[5:9])[0]
            
            if len(raw) < 9 + length:
                return None, None, None
            
            content = raw[9:9+length]
            data = json.loads(content.decode("utf-8"))
            
            # 根据类型字节确定消息类型
            msg_types = {
                ord("T"): MessageType.TEXT,
                ord("A"): MessageType.ACK,
                ord("F"): MessageType.FILE_REQUEST,
                ord("H"): MessageType.HEARTBEAT,
                ord("P"): MessageType.PING,
            }
            
            msg_type = msg_types.get(msg_type_byte, MessageType.TEXT)
            
            return msg_type, data, msg_type_byte
            
        except Exception as e:
            logger.debug(f"Unpack error: {e}")
            return None, None, None


class ChatConnection(QObject):
    """
    聊天连接管理
    
    管理TCP连接、消息发送/接收、文件传输等功能
    """
    
    # 信号定义
    message_received = pyqtSignal(ChatMessage)       # 收到消息
    message_sent = pyqtSignal(str)                 # 消息发送成功
    message_failed = pyqtSignal(str)                # 消息发送失败
    connection_status_changed = pyqtSignal(str, bool) # 连接状态变化
    file_transfer_progress = pyqtSignal(str, float) # 文件传输进度
    file_transfer_complete = pyqtSignal(str, str)   # 文件传输完成 (id, path)
    file_transfer_failed = pyqtSignal(str, str)     # 文件传输失败
    
    def __init__(self, user_id: str, user_name: str, parent=None):
        super().__init__(parent)
        
        self.user_id = user_id
        self.user_name = user_name
        
        # 连接状态
        self._running = False
        self._server_thread: Optional[threading.Thread] = None
        self._connections: Dict[str, socket.socket] = {}
        self._lock = threading.Lock()
        
        # 待发送消息
        self._pending_messages: Dict[str, ChatMessage] = {}
        
        # 文件传输
        self._file_transfers: Dict[str, Dict] = {}
        self._download_dir = Path.home() / ".hermes-desktop" / "downloads"
        self._download_dir.mkdir(parents=True, exist_ok=True)
        
        # AI回复
        self._ai_reply_enabled = False
        self._ai_engine: Optional[Callable] = None
        
        # 协议处理器
        self._protocol = ProtocolHandler()
        self._setup_protocol()
    
    def _setup_protocol(self):
        """设置协议处理器"""
        pass  # 将在server_loop中使用unpack_message
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    def start(self):
        """启动聊天服务"""
        if self._running:
            return
        
        logger.info("Starting Chat Connection Service...")
        self._running = True
        
        # 启动服务器线程
        self._server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self._server_thread.start()
        
        logger.info(f"Chat Connection started on port {CHAT_PORT}")
    
    def stop(self):
        """停止聊天服务"""
        if not self._running:
            return
        
        logger.info("Stopping Chat Connection Service...")
        self._running = False
        
        # 关闭所有连接
        with self._lock:
            for peer_id, sock in self._connections.items():
                try:
                    sock.close()
                except Exception:
                    pass
            self._connections.clear()
        
        self._running = False
        logger.info("Chat Connection stopped")
    
    def _server_loop(self):
        """服务器主循环"""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_sock.bind(("0.0.0.0", CHAT_PORT))
            server_sock.listen(10)
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
                except Exception as e:
                    if self._running:
                        continue
                    break
                    
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            server_sock.close()
    
    def _handle_client(self, sock: socket.socket, addr: tuple):
        """处理客户端连接"""
        peer_id = f"{addr[0]}:{addr[1]}"
        
        try:
            sock.settimeout(CONNECTION_TIMEOUT)
            
            # 接收消息头
            header = sock.recv(9)
            if len(header) < 9:
                return
            
            magic = header[:4]
            if magic != ProtocolHandler.MAGIC:
                return
            
            msg_type_byte = header[4]
            length = struct.unpack("!I", header[5:9])[0]
            
            # 接收消息内容
            content = b""
            while len(content) < length:
                chunk = sock.recv(length - len(content))
                if not chunk:
                    break
                content += chunk
            
            # 解析消息
            data = json.loads(content.decode("utf-8"))
            msg_type = MessageType(data.get("type", "text"))
            
            # 处理不同类型的消息
            if msg_type == MessageType.TEXT:
                self._handle_text_message(data, sock, addr)
            elif msg_type == MessageType.ACK:
                self._handle_ack(data)
            elif msg_type == MessageType.FILE_REQUEST:
                self._handle_file_request(data, sock, addr)
            elif msg_type == MessageType.HEARTBEAT:
                self._handle_heartbeat(data, sock, addr)
                
        except Exception as e:
            logger.debug(f"Client handler error: {e}")
        finally:
            sock.close()
    
    def _handle_text_message(self, data: Dict, sock: socket.socket, addr: tuple):
        """处理文本消息"""
        message = ChatMessage(
            id=data.get("id", str(uuid.uuid4())),
            msg_type=MessageType.TEXT,
            sender_id=data.get("sender_id", ""),
            sender_name=data.get("sender_name", "Unknown"),
            receiver_id=data.get("receiver_id", self.user_id),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
            status=MessageStatus.DELIVERED,
        )
        
        # 发送确认
        try:
            ack = ProtocolHandler.pack_ack(message.id)
            sock.sendall(ack)
        except Exception:
            pass
        
        # 发送信号
        self.message_received.emit(message)
        
        # AI自动回复
        if self._ai_reply_enabled and self._ai_engine:
            self._generate_ai_reply(message)
    
    def _handle_ack(self, data: Dict):
        """处理确认消息"""
        message_id = data.get("message_id", "")
        
        if message_id in self._pending_messages:
            msg = self._pending_messages.pop(message_id)
            msg.status = MessageStatus.DELIVERED
            self.message_sent.emit(message_id)
    
    def _handle_file_request(self, data: Dict, sock: socket.socket, addr: tuple):
        """处理文件请求"""
        logger.info(f"File request: {data.get('file_name')} from {data.get('sender_name')}")
    
    def _handle_heartbeat(self, data: Dict, sock: socket.socket, addr: tuple):
        """处理心跳"""
        pass
    
    def send_message(self, receiver_ip: str, receiver_port: int, 
                    content: str, receiver_id: str = "") -> str:
        """
        发送消息
        
        Args:
            receiver_ip: 接收方IP
            receiver_port: 接收方端口
            content: 消息内容
            receiver_id: 接收方ID
            
        Returns:
            消息ID
        """
        message = ChatMessage(
            sender_id=self.user_id,
            sender_name=self.user_name,
            receiver_id=receiver_id,
            content=content,
        )
        
        self._pending_messages[message.id] = message
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(CONNECTION_TIMEOUT)
            sock.connect((receiver_ip, receiver_port))
            
            packet = ProtocolHandler.pack_text_message(
                content=content,
                sender_id=self.user_id,
                sender_name=self.user_name,
                receiver_id=receiver_id,
                msg_id=message.id,
            )
            
            sock.sendall(packet)
            
            # 等待确认
            sock.settimeout(5.0)
            ack_header = sock.recv(9)
            
            if len(ack_header) >= 9:
                _, ack_data = ProtocolHandler.unpack_message(ack_header + b"{}")
                if ack_data and ack_data.get("message_id") == message.id:
                    self._pending_messages.pop(message.id, None)
                    message.status = MessageStatus.SENT
                    self.message_sent.emit(message.id)
            
            sock.close()
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            if message.id in self._pending_messages:
                self._pending_messages.pop(message.id)
            message.status = MessageStatus.FAILED
            self.message_failed.emit(message.id)
        
        return message.id
    
    def send_file(self, receiver_ip: str, receiver_port: int,
                 file_path: str, receiver_id: str = "") -> str:
        """
        发送文件
        
        Args:
            receiver_ip: 接收方IP
            receiver_port: 接收方端口
            file_path: 文件路径
            receiver_id: 接收方ID
            
        Returns:
            文件传输ID
        """
        transfer_id = str(uuid.uuid4())
        
        try:
            path = Path(file_path)
            if not path.exists():
                self.file_transfer_failed.emit(transfer_id, "File not found")
                return ""
            
            file_size = path.stat().st_size
            
            # 计算文件哈希
            with open(path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            # 发送文件请求
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(CONNECTION_TIMEOUT)
            sock.connect((receiver_ip, receiver_port))
            
            request = ProtocolHandler.pack_file_request(
                file_name=path.name,
                file_size=file_size,
                file_hash=file_hash,
                sender_id=self.user_id,
                sender_name=self.user_name,
                receiver_id=receiver_id,
            )
            sock.sendall(request)
            
            # 分块发送文件
            chunk_size = 64 * 1024  # 64KB
            total_chunks = (file_size + chunk_size - 1) // chunk_size
            
            with open(path, "rb") as f:
                for i, chunk in enumerate(iter(lambda: f.read(chunk_size), b"")):
                    sock.sendall(chunk)
                    progress = (i + 1) / total_chunks * 100
                    self.file_transfer_progress.emit(transfer_id, progress)
            
            sock.close()
            self.file_transfer_complete.emit(transfer_id, str(path))
            logger.info(f"File sent: {path.name}")
            
        except Exception as e:
            logger.error(f"Failed to send file: {e}")
            self.file_transfer_failed.emit(transfer_id, str(e))
        
        return transfer_id
    
    def _generate_ai_reply(self, message: ChatMessage):
        """生成AI回复"""
        if not self._ai_engine:
            return
        
        def reply():
            try:
                reply_text = self._ai_engine(message.content, message.sender_name)
                
                if reply_text:
                    sender_ip = ""
                    self.send_message(
                        receiver_ip=sender_ip,
                        receiver_port=CHAT_PORT,
                        content=reply_text,
                        receiver_id=message.sender_id,
                    )
            except Exception as e:
                logger.error(f"AI reply error: {e}")
        
        thread = threading.Thread(target=reply, daemon=True)
        thread.start()
    
    def set_ai_reply(self, enabled: bool, engine: Callable = None):
        """设置AI回复"""
        self._ai_reply_enabled = enabled
        if engine:
            self._ai_engine = engine


class NATTraversalHelper:
    """
    NAT穿透辅助工具
    
    提供STUN检测和连接优化功能
    """
    
    def __init__(self, stun_servers: List[str] = None):
        self.stun_servers = stun_servers or [
            "stun.l.google.com:19302",
            "stun1.l.google.com:19302",
        ]
        self._local_ip = ""
        self._public_ip = ""
        self._nat_type = "unknown"
    
    def get_local_ip(self) -> str:
        """获取本地IP"""
        if not self._local_ip:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                self._local_ip = s.getsockname()[0]
                s.close()
            except Exception:
                self._local_ip = "127.0.0.1"
        return self._local_ip
    
    async def detect_nat_type(self) -> Dict[str, Any]:
        """检测NAT类型（简化版）"""
        self._local_ip = self.get_local_ip()
        
        try:
            import urllib.request
            with urllib.request.urlopen("https://api.ipify.org", timeout=5) as response:
                self._public_ip = response.read().decode()
            
            if self._local_ip.startswith(("10.", "172.", "192.")):
                self._nat_type = "full_cone"
            else:
                self._nat_type = "open"
                
        except Exception as e:
            logger.warning(f"NAT detection failed: {e}")
            self._public_ip = self._local_ip
            self._nat_type = "unknown"
        
        return {
            "local_ip": self._local_ip,
            "public_ip": self._public_ip,
            "nat_type": self._nat_type,
        }
    
    def get_connection_hint(self, peer_local_ip: str, peer_public_ip: str) -> ConnectionType:
        """获取连接提示"""
        local_ip = self.get_local_ip()
        
        if self._is_same_subnet(local_ip, peer_local_ip):
            return ConnectionType.DIRECT_LAN
        
        if not self._is_private_ip(local_ip) and not self._is_private_ip(peer_public_ip):
            return ConnectionType.DIRECT_WAN
        
        if self._nat_type in ("full_cone", "restricted"):
            return ConnectionType.STUN
        
        return ConnectionType.TURN
    
    def _is_same_subnet(self, ip1: str, ip2: str) -> bool:
        """检查是否在同一子网"""
        try:
            p1 = ip1.split(".")
            p2 = ip2.split(".")
            if len(p1) != 4 or len(p2) != 4:
                return False
            return p1[:3] == p2[:3]
        except Exception:
            return False
    
    def _is_private_ip(self, ip: str) -> bool:
        """检查是否为私网IP"""
        try:
            parts = [int(p) for p in ip.split(".")]
            if len(parts) != 4:
                return True
            if parts[0] == 10:
                return True
            if parts[0] == 172 and 16 <= parts[1] <= 31:
                return True
            if parts[0] == 192 and parts[1] == 168:
                return True
            return False
        except Exception:
            return True


__all__ = [
    "ProtocolHandler",
    "ChatConnection",
    "NATTraversalHelper",
]
