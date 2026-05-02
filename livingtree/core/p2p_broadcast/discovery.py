"""
广播发现服务

实现UDP广播、mDNS服务发现、设备管理等功能
from __future__ import annotations
"""


import asyncio
import json
import logging
import socket
import struct
import threading
import time
import uuid
from typing import Dict, Optional, List, Callable, Any
from dataclasses import asdict

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from .models import (
    DeviceInfo, DeviceStatus, BroadcastMessage, BroadcastCategory, ResponseType,
    BROADCAST_PORT, CHAT_PORT, BROADCAST_INTERVAL, DEVICE_TIMEOUT,
    PROTOCOL_VERSION, CAPABILITY_TEXT, CAPABILITY_FILE, NetworkAddress
)

logger = logging.getLogger(__name__)


class MessageProtocol:
    """消息协议封装"""
    
    @staticmethod
    def pack(msg_type: str, data: Dict[str, Any]) -> bytes:
        """打包消息"""
        content = json.dumps(data, ensure_ascii=False)
        content_bytes = content.encode("utf-8")
        # 格式：版本(4字节) + 类型长度(1字节) + 类型 + 长度(4字节) + 内容
        msg_type_bytes = msg_type.encode("utf-8")
        header = struct.pack("!4sBIB", PROTOCOL_VERSION[:4].encode("utf-8"), 
                           len(msg_type_bytes), msg_type_bytes,
                           len(content_bytes))
        return header + content_bytes
    
    @staticmethod
    def unpack(raw: bytes) -> Optional[tuple]:
        """解包消息"""
        if len(raw) < 10:
            return None
        
        try:
            # 解析头部
            version = raw[:4].decode("utf-8")
            type_len = raw[4]
            msg_type = raw[5:5+type_len].decode("utf-8")
            content_len = struct.unpack("!I", raw[5+type_len:9+type_len])[0]
            
            # 解析内容
            content = raw[9+type_len:9+type_len+content_len].decode("utf-8")
            data = json.loads(content)
            
            return msg_type, data
        except Exception as e:
            logger.debug(f"Failed to unpack message: {e}")
            return None


class BroadcastDiscovery(QObject):
    """
    广播发现服务
    
    使用UDP广播发现局域网内的设备，支持多种广播类型
    """
    
    # 信号定义
    device_found = pyqtSignal(DeviceInfo)        # 发现新设备
    device_left = pyqtSignal(str)                # 设备离线
    device_updated = pyqtSignal(DeviceInfo)      # 设备状态更新
    broadcast_received = pyqtSignal(BroadcastMessage)  # 收到广播消息
    status_changed = pyqtSignal(bool)            # 服务状态变化
    
    def __init__(
        self,
        user_id: str,
        user_name: str,
        device_name: str = "My Device",
        capabilities: List[str] = None,
        parent=None
    ):
        super().__init__(parent)
        
        # 用户信息
        self.user_id = user_id
        self.user_name = user_name
        self.device_name = device_name
        self.device_id = f"{user_id}_{uuid.uuid4().hex[:8]}"
        self.capabilities = capabilities or [CAPABILITY_TEXT, CAPABILITY_FILE]
        
        # 状态
        self._running = False
        self._devices: Dict[str, DeviceInfo] = {}
        self._lock = threading.Lock()
        
        # Socket
        self._sock: Optional[socket.socket] = None
        self._recv_thread: Optional[threading.Thread] = None
        
        # 定时器
        self._broadcast_timer: Optional[QTimer] = None
        self._cleanup_timer: Optional[QTimer] = None
        self._heartbeat_timer: Optional[QTimer] = None
        
        # 广播队列
        self._pending_broadcasts: Dict[str, BroadcastMessage] = {}
        
        # 本地IP
        self._local_ip = ""
        
    @property
    def is_running(self) -> bool:
        return self._running
    
    def start(self):
        """启动发现服务"""
        if self._running:
            return
        
        logger.info("Starting Broadcast Discovery Service...")
        self._running = True
        
        # 获取本地IP
        self._local_ip = self._get_local_ip()
        
        # 创建UDP Socket
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.settimeout(1.0)
        
        # 绑定端口
        try:
            self._sock.bind(("", BROADCAST_PORT))
        except OSError:
            # 端口被占用，使用随机端口
            self._sock.bind(("", 0))
        
        # 启动接收线程
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()
        
        # 启动广播定时器
        self._broadcast_timer = QTimer(self)
        self._broadcast_timer.timeout.connect(self._send_discovery)
        self._broadcast_timer.start(BROADCAST_INTERVAL * 1000)
        
        # 启动清理定时器
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.timeout.connect(self._cleanup_offline)
        self._cleanup_timer.start(5000)
        
        # 启动心跳定时器
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)
        self._heartbeat_timer.start(BROADCAST_INTERVAL * 1000)
        
        # 立即发送一次广播
        self._send_discovery()
        
        self.status_changed.emit(True)
        logger.info(f"Broadcast Discovery started. Local IP: {self._local_ip}")
    
    def stop(self):
        """停止发现服务"""
        if not self._running:
            return
        
        logger.info("Stopping Broadcast Discovery Service...")
        self._running = False
        
        # 发送离开通知
        self._send_bye()
        
        # 停止定时器
        for timer in [self._broadcast_timer, self._cleanup_timer, self._heartbeat_timer]:
            if timer:
                timer.stop()
        
        # 关闭Socket
        if self._sock:
            self._sock.close()
            self._sock = None
        
        self.status_changed.emit(False)
        logger.info("Broadcast Discovery stopped")
    
    def _send_discovery(self):
        """发送设备发现广播"""
        if not self._sock:
            return
        
        try:
            msg_data = {
                "type": "announce",
                "device_id": self.device_id,
                "device_name": self.device_name,
                "user_id": self.user_id,
                "user_name": self.user_name,
                "local_ip": self._local_ip,
                "port": CHAT_PORT,
                "capabilities": self.capabilities,
                "version": PROTOCOL_VERSION,
                "timestamp": time.time(),
            }
            
            message = MessageProtocol.pack("discovery", msg_data)
            
            # 发送到局域网广播地址
            self._sock.sendto(message, ("<broadcast>", BROADCAST_PORT))
            
            # 发送到本机广播地址（确保同网段设备能收到）
            if self._local_ip:
                subnet_broadcast = self._get_subnet_broadcast()
                if subnet_broadcast:
                    self._sock.sendto(message, (subnet_broadcast, BROADCAST_PORT))
                    
        except Exception as e:
            logger.debug(f"Discovery broadcast error: {e}")
    
    def _send_heartbeat(self):
        """发送心跳包"""
        if not self._sock:
            return
        
        try:
            msg_data = {
                "type": "heartbeat",
                "device_id": self.device_id,
                "user_id": self.user_id,
                "timestamp": time.time(),
            }
            
            message = MessageProtocol.pack("heartbeat", msg_data)
            
            # 只发送到广播地址
            self._sock.sendto(message, ("<broadcast>", BROADCAST_PORT))
            
        except Exception as e:
            logger.debug(f"Heartbeat error: {e}")
    
    def _send_bye(self):
        """发送离开通知"""
        if not self._sock:
            return
        
        try:
            msg_data = {
                "type": "bye",
                "device_id": self.device_id,
                "user_id": self.user_id,
                "timestamp": time.time(),
            }
            
            message = MessageProtocol.pack("bye", msg_data)
            self._sock.sendto(message, ("<broadcast>", BROADCAST_PORT))
            
        except Exception:
            pass
    
    def send_broadcast_message(
        self,
        content: str,
        category: BroadcastCategory = BroadcastCategory.GENERAL,
        keywords: List[str] = None,
        response_type: ResponseType = ResponseType.REPLY,
        expires_seconds: int = 60
    ) -> str:
        """
        发送广播消息
        
        Args:
            content: 广播内容
            category: 广播分类
            keywords: 关键词列表
            response_type: 期望的响应类型
            expires_seconds: 过期时间（秒）
            
        Returns:
            广播消息ID
        """
        if not self._sock:
            return ""
        
        broadcast = BroadcastMessage(
            sender=DeviceInfo(
                device_id=self.device_id,
                device_name=self.device_name,
                user_id=self.user_id,
                user_name=self.user_name,
                local_ip=self._local_ip,
                port=CHAT_PORT,
                capabilities=self.capabilities,
            ),
            content=content,
            category=category,
            keywords=keywords or [],
            response_type=response_type,
            expires_at=time.time() + expires_seconds,
        )
        
        self._pending_broadcasts[broadcast.id] = broadcast
        
        try:
            msg_data = {
                "type": "broadcast",
                "broadcast_id": broadcast.id,
                "sender": broadcast.sender.to_dict(),
                "content": content,
                "category": category.value,
                "keywords": keywords or [],
                "response_type": response_type.value,
                "timestamp": broadcast.timestamp,
                "expires_at": broadcast.expires_at,
            }
            
            message = MessageProtocol.pack("broadcast", msg_data)
            self._sock.sendto(message, ("<broadcast>", BROADCAST_PORT))
            
            logger.info(f"Broadcast sent: {content[:50]}...")
            return broadcast.id
            
        except Exception as e:
            logger.error(f"Failed to send broadcast: {e}")
            return ""
    
    def _recv_loop(self):
        """接收循环"""
        while self._running and self._sock:
            try:
                data, addr = self._sock.recvfrom(8192)
                self._handle_received(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    continue
                break
    
    def _handle_received(self, data: bytes, addr: tuple):
        """处理接收到的数据"""
        result = MessageProtocol.unpack(data)
        if not result:
            return
        
        msg_type, msg_data = result
        
        if msg_type == "discovery":
            self._handle_discovery(msg_data, addr)
        elif msg_type == "discovery_ack":
            self._handle_discovery_ack(msg_data, addr)
        elif msg_type == "heartbeat":
            self._handle_heartbeat(msg_data, addr)
        elif msg_type == "bye":
            self._handle_bye(msg_data)
        elif msg_type == "broadcast":
            self._handle_broadcast(msg_data, addr)
    
    def _handle_discovery(self, data: Dict, addr: tuple):
        """处理发现消息"""
        device_id = data.get("device_id", "")
        
        # 忽略自己
        if device_id == self.device_id:
            return
        
        # 创建设备信息
        device = DeviceInfo(
            device_id=device_id,
            device_name=data.get("device_name", "Unknown"),
            user_id=data.get("user_id", ""),
            user_name=data.get("user_name", "Unknown"),
            local_ip=data.get("local_ip", addr[0]),
            port=data.get("port", CHAT_PORT),
            capabilities=data.get("capabilities", [CAPABILITY_TEXT]),
            last_seen=time.time(),
        )
        
        # 检查是否新设备
        with self._lock:
            is_new = device_id not in self._devices
            self._devices[device_id] = device
        
        # 发送信号
        if is_new:
            logger.info(f"New device discovered: {device.user_name} ({device.local_ip})")
            self.device_found.emit(device)
        else:
            self.device_updated.emit(device)
        
        # 发送ACK响应
        self._send_discovery_ack(device, addr)
    
    def _handle_discovery_ack(self, data: Dict, addr: tuple):
        """处理发现ACK"""
        device_id = data.get("device_id", "")
        
        with self._lock:
            if device_id in self._devices:
                self._devices[device_id].last_seen = time.time()
    
    def _handle_heartbeat(self, data: Dict, addr: tuple):
        """处理心跳"""
        device_id = data.get("device_id", "")
        
        with self._lock:
            if device_id in self._devices:
                self._devices[device_id].last_seen = time.time()
    
    def _handle_bye(self, data: Dict):
        """处理离开消息"""
        device_id = data.get("device_id", "")
        
        with self._lock:
            if device_id in self._devices:
                del self._devices[device_id]
        
        self.device_left.emit(device_id)
        logger.info(f"Device left: {device_id}")
    
    def _handle_broadcast(self, data: Dict, addr: tuple):
        """处理广播消息"""
        # 忽略自己发送的广播
        sender_id = data.get("sender", {}).get("device_id", "")
        if sender_id == self.device_id:
            return
        
        # 检查是否过期
        expires_at = data.get("expires_at", 0)
        if expires_at and time.time() > expires_at:
            return
        
        broadcast = BroadcastMessage.from_dict(data)
        
        logger.info(f"Broadcast received from {broadcast.sender.user_name}: {broadcast.content[:50]}...")
        self.broadcast_received.emit(broadcast)
    
    def _send_discovery_ack(self, device: DeviceInfo, addr: tuple):
        """发送发现响应"""
        if not self._sock:
            return
        
        try:
            msg_data = {
                "type": "ack",
                "device_id": self.device_id,
                "device_name": self.device_name,
                "user_id": self.user_id,
                "user_name": self.user_name,
                "local_ip": self._local_ip,
                "port": CHAT_PORT,
            }
            
            message = MessageProtocol.pack("discovery_ack", msg_data)
            self._sock.sendto(message, (device.local_ip, BROADCAST_PORT))
            
        except Exception:
            pass
    
    def _cleanup_offline(self):
        """清理离线设备"""
        offline_devices = []
        
        with self._lock:
            for device_id, device in self._devices.items():
                if not device.is_online():
                    offline_devices.append(device_id)
            
            for device_id in offline_devices:
                del self._devices[device_id]
        
        for device_id in offline_devices:
            self.device_left.emit(device_id)
    
    def _get_local_ip(self) -> str:
        """获取本机IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def _get_subnet_broadcast(self) -> str:
        """获取子网广播地址"""
        if not self._local_ip:
            return ""
        
        try:
            parts = self._local_ip.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{parts[2]}.255"
        except Exception:
            pass
        
        return ""
    
    # ============= 公开API =============
    
    def get_devices(self) -> List[DeviceInfo]:
        """获取所有发现的设备"""
        with self._lock:
            return [d for d in self._devices.values() if d.is_online()]
    
    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        """获取指定设备"""
        with self._lock:
            return self._devices.get(device_id)
    
    def get_friends(self) -> List[DeviceInfo]:
        """获取好友设备"""
        with self._lock:
            return [d for d in self._devices.values() if d.is_friend and d.is_online()]
    
    def get_online_count(self) -> int:
        """获取在线设备数"""
        with self._lock:
            return sum(1 for d in self._devices.values() if d.is_online())
    
    def set_friend(self, device_id: str, is_friend: bool = True):
        """设置好友"""
        with self._lock:
            if device_id in self._devices:
                self._devices[device_id].is_friend = is_friend


# ============= 模块导出 =============

__all__ = [
    "BroadcastDiscovery",
    "MessageProtocol",
]
