"""
同步层 (Sync Layer)
===================

P2P 设备发现与数据通道

核心功能：
1. 设备发现：通过中继服务器交换节点信息
2. 数据通道：WebRTC/WebSocket 直连传输
3. 同步协议：基于操作日志的同步
4. 备份通道：加密后上传到聚合云盘

Author: Hermes Desktop AI Assistant
"""

import os
import json
import time
import socket
import struct
import hashlib
import logging
import threading
import asyncio
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List, Set, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import queue

logger = logging.getLogger(__name__)


# ============================================================
# 消息类型
# ============================================================

class MessageType(Enum):
    """消息类型"""
    # 设备发现
    DISCOVERY_REQUEST = 0x01
    DISCOVERY_RESPONSE = 0x02
    HEARTBEAT = 0x03

    # 状态同步
    STATE_REQUEST = 0x10
    STATE_RESPONSE = 0x11
    OPS_PUSH = 0x12
    OPS_PULL = 0x13

    # 内容同步
    CONTENT_REQUEST = 0x20
    CONTENT_RESPONSE = 0x21
    DELTA_SYNC = 0x22

    # 备份
    BACKUP_REQUEST = 0x30
    BACKUP_RESPONSE = 0x31

    # 控制
    SYNC_COMPLETE = 0xF0
    ERROR = 0xFF


@dataclass
class SyncMessage:
    """同步消息"""
    msg_type: MessageType
    source_id: str
    target_id: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_bytes(self) -> bytes:
        """序列化为字节"""
        data = {
            "type": self.msg_type.value,
            "src": self.source_id,
            "tgt": self.target_id,
            "payload": self.payload,
            "ts": self.timestamp,
            "id": self.message_id
        }
        content = json.dumps(data).encode('utf-8')
        return struct.pack(">I", len(content)) + content

    @classmethod
    def from_bytes(cls, data: bytes) -> 'SyncMessage':
        """从字节反序列化"""
        msg = json.loads(data.decode('utf-8'))
        return cls(
            msg_type=MessageType(msg["type"]),
            source_id=msg["src"],
            target_id=msg["tgt"],
            payload=msg["payload"],
            timestamp=msg["ts"],
            message_id=msg["id"]
        )


# ============================================================
# 设备发现
# ============================================================

class DeviceInfo:
    """设备信息"""

    def __init__(self, device_id: str, public_key: str = ""):
        self.device_id = device_id
        self.public_key = public_key
        self.address: Tuple[str, int] = ("", 0)
        self.last_seen: float = time.time()
        self.is_online: bool = False
        self.metadata: Dict[str, Any] = {}

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "public_key": self.public_key,
            "address": self.address,
            "last_seen": self.last_seen,
            "is_online": self.is_online,
            "metadata": self.metadata
        }


class DeviceDiscovery:
    """
    设备发现

    通过中继服务器实现设备发现：
    1. 向中继服务器注册自己的信息
    2. 从服务器获取已注册设备列表
    3. 维护设备在线状态
    """

    HEARTBEAT_INTERVAL = 30  # 秒
    DEVICE_TIMEOUT = 120     # 秒

    def __init__(self, device_id: str, relay_servers: List[str]):
        self.device_id = device_id
        self.relay_servers = relay_servers
        self.devices: Dict[str, DeviceInfo] = {}
        self._lock = threading.Lock()
        self._running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._socket: Optional(socket.socket) = None

    def start(self):
        """启动设备发现"""
        if self._running:
            return

        self._running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def stop(self):
        """停止设备发现"""
        self._running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)

    def _heartbeat_loop(self):
        """心跳循环"""
        while self._running:
            try:
                self._send_discovery()
                time.sleep(self.HEARTBEAT_INTERVAL)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    def _send_discovery(self):
        """发送发现请求"""
        for server in self.relay_servers:
            try:
                host, port = server.split(':')
                port = int(port)

                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(5)

                msg = SyncMessage(
                    msg_type=MessageType.DISCOVERY_REQUEST,
                    source_id=self.device_id,
                    target_id="broadcast",
                    payload={"action": "register", "online": True}
                )

                sock.sendto(msg.to_bytes(), (host, port))

                # 接收响应
                data, addr = sock.recvfrom(65536)
                response = SyncMessage.from_bytes(data)

                if response.payload.get("action") == "list":
                    self._update_devices(response.payload.get("devices", []))

                sock.close()
                break

            except Exception as e:
                logger.debug(f"Discovery to {server} failed: {e}")

    def _update_devices(self, devices_data: List[dict]):
        """更新设备列表"""
        with self._lock:
            for dev_data in devices_data:
                device_id = dev_data.get("device_id")
                if device_id == self.device_id:
                    continue

                if device_id not in self.devices:
                    self.devices[device_id] = DeviceInfo(device_id)

                dev = self.devices[device_id]
                dev.public_key = dev_data.get("public_key", "")
                dev.last_seen = time.time()
                dev.is_online = dev_data.get("online", False)

    def get_online_devices(self) -> List[DeviceInfo]:
        """获取在线设备"""
        with self._lock:
            now = time.time()
            online = []

            for dev in self.devices.values():
                if dev.is_online and (now - dev.last_seen) < self.DEVICE_TIMEOUT:
                    online.append(dev)

            return online

    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        """获取设备信息"""
        return self.devices.get(device_id)


# ============================================================
# P2P 连接管理器
# ============================================================

class ConnectionState(Enum):
    """连接状态"""
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    ERROR = 3


class P2PConnection:
    """
    P2P 连接

    管理两个设备之间的连接
    """

    def __init__(self, peer_id: str, device_id: str):
        self.peer_id = peer_id
        self.device_id = device_id
        self.state = ConnectionState.DISCONNECTED
        self.socket: Optional[socket.socket] = None
        self.last_sync: float = 0
        self.pending_ops: List[Dict] = []
        self._lock = threading.Lock()

    def connect(self, address: Tuple[str, int]) -> bool:
        """建立连接"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(30)
            self.socket.connect(address)
            self.state = ConnectionState.CONNECTED
            return True
        except Exception as e:
            logger.error(f"Connect to {address} failed: {e}")
            self.state = ConnectionState.ERROR
            return False

    def disconnect(self):
        """断开连接"""
        with self._lock:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
            self.state = ConnectionState.DISCONNECTED

    def send(self, message: SyncMessage) -> bool:
        """发送消息"""
        with self._lock:
            if self.state != ConnectionState.CONNECTED or not self.socket:
                return False

            try:
                self.socket.sendall(message.to_bytes())
                return True
            except Exception as e:
                logger.error(f"Send failed: {e}")
                self.state = ConnectionState.ERROR
                return False

    def receive(self, timeout: float = 30) -> Optional[SyncMessage]:
        """接收消息"""
        if not self.socket:
            return None

        try:
            # 先读取长度
            len_data = self.socket.recv(4)
            if not len_data:
                return None

            length = struct.unpack(">I", len_data)[0]

            # 再读取内容
            data = b""
            while len(data) < length:
                chunk = self.socket.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk

            return SyncMessage.from_bytes(data)

        except socket.timeout:
            return None
        except Exception as e:
            logger.error(f"Receive failed: {e}")
            self.state = ConnectionState.ERROR
            return None


class P2PConnectionManager:
    """
    P2P 连接管理器

    管理所有对等连接
    """

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.connections: Dict[str, P2PConnection] = {}
        self._lock = threading.Lock()

    def get_connection(self, peer_id: str) -> Optional[P2PConnection]:
        """获取连接"""
        return self.connections.get(peer_id)

    def create_connection(self, peer_id: str, address: Tuple[str, int]) -> P2PConnection:
        """创建连接"""
        with self._lock:
            if peer_id in self.connections:
                conn = self.connections[peer_id]
                if conn.state == ConnectionState.CONNECTED:
                    return conn

            conn = P2PConnection(peer_id, self.device_id)
            if conn.connect(address):
                self.connections[peer_id] = conn
            return conn

    def remove_connection(self, peer_id: str):
        """移除连接"""
        with self._lock:
            if peer_id in self.connections:
                self.connections[peer_id].disconnect()
                del self.connections[peer_id]

    def close_all(self):
        """关闭所有连接"""
        with self._lock:
            for conn in self.connections.values():
                conn.disconnect()
            self.connections.clear()


# ============================================================
# 同步协议
# ============================================================

class SyncDirection(Enum):
    """同步方向"""
    PUSH = "push"
    PULL = "pull"
    BIDIRECTIONAL = "bidirectional"


class SyncManager:
    """
    同步管理器

    负责：
    1. 状态同步（操作日志）
    2. 内容同步（文件快照）
    3. 冲突解决
    """

    def __init__(
        self,
        device_id: str,
        state_db,  # StateDB 实例
        content_repo,  # ContentRepository 实例
        connection_manager: P2PConnectionManager
    ):
        self.device_id = device_id
        self.state_db = state_db
        self.content_repo = content_repo
        self.conn_manager = connection_manager

        self._sync_callbacks: List[Callable] = []
        self._sync_thread: Optional[threading.Thread] = None
        self._running = False

    def add_sync_callback(self, callback: Callable):
        """添加同步回调"""
        self._sync_callbacks.append(callback)

    def start_auto_sync(self, interval: int = 60):
        """启动自动同步"""
        if self._running:
            return

        self._running = True
        self._sync_thread = threading.Thread(
            target=self._sync_loop,
            args=(interval,),
            daemon=True
        )
        self._sync_thread.start()

    def stop_auto_sync(self):
        """停止自动同步"""
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=5)

    def _sync_loop(self, interval: int):
        """同步循环"""
        while self._running:
            try:
                self.sync_all()
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Sync loop error: {e}")

    def sync_state_with_peer(self, peer_id: str) -> Dict[str, Any]:
        """
        与对等节点同步状态

        使用 CRDT 合并策略：
        1. 推送本地未同步的操作
        2. 拉取对端的操作
        3. 合并到本地状态
        """
        conn = self.conn_manager.get_connection(peer_id)
        if not conn or conn.state != ConnectionState.CONNECTED:
            return {"success": False, "error": "Not connected"}

        result = {"pushed": 0, "pulled": 0, "conflicts": []}

        try:
            # 1. 推送本地操作
            pending_ops = self.state_db.get_pending_ops()
            if pending_ops:
                ops_data = [op.to_dict() for op in pending_ops]

                msg = SyncMessage(
                    msg_type=MessageType.OPS_PUSH,
                    source_id=self.device_id,
                    target_id=peer_id,
                    payload={"operations": ops_data}
                )

                if conn.send(msg):
                    result["pushed"] = len(ops_data)

            # 2. 拉取对端操作
            msg = SyncMessage(
                msg_type=MessageType.OPS_PULL,
                source_id=self.device_id,
                target_id=peer_id,
                payload={}
            )

            if conn.send(msg):
                response = conn.receive(timeout=60)
                if response and response.msg_type == MessageType.OPS_PUSH:
                    remote_ops = [Operation.from_dict(op) for op in response.payload.get("operations", [])]
                    applied = self.state_db.apply_ops(remote_ops)
                    result["pulled"] = applied

            # 3. 通知回调
            for callback in self._sync_callbacks:
                try:
                    callback(peer_id, result)
                except Exception as e:
                    logger.error(f"Sync callback error: {e}")

            conn.last_sync = time.time()

        except Exception as e:
            logger.error(f"Sync with {peer_id} failed: {e}")
            return {"success": False, "error": str(e)}

        return {"success": True, **result}

    def sync_content_with_peer(self, peer_id: str, snapshot_hash: str = "") -> Dict[str, Any]:
        """
        与对等节点同步内容

        使用差量同步：
        1. 比较指纹
        2. 只同步差异部分
        """
        conn = self.conn_manager.get_connection(peer_id)
        if not conn or conn.state != ConnectionState.CONNECTED:
            return {"success": False, "error": "Not connected"}

        try:
            # 获取本地指纹
            local = self.content_repo.get_delta_sync(snapshot_hash, "")

            # 请求远程指纹
            msg = SyncMessage(
                msg_type=MessageType.DELTA_SYNC,
                source_id=self.device_id,
                target_id=peer_id,
                payload={"fingerprint": local.get("fingerprint", "")}
            )

            if not conn.send(msg):
                return {"success": False, "error": "Send failed"}

            response = conn.receive(timeout=120)
            if not response:
                return {"success": False, "error": "No response"}

            if response.msg_type == MessageType.DELTA_SYNC:
                delta = response.payload

                if delta.get("mode") == "none":
                    return {"success": True, "mode": "none", "synced": 0}

                # 导入差量
                self.content_repo.import_delta(delta)

                return {
                    "success": True,
                    "mode": delta.get("mode", "delta"),
                    "files": len(delta.get("files", []))
                }

        except Exception as e:
            logger.error(f"Content sync with {peer_id} failed: {e}")
            return {"success": False, "error": str(e)}

        return {"success": False, "error": "Unknown error"}

    def sync_all(self) -> Dict[str, Any]:
        """同步所有对等节点"""
        from .state_db import get_state_db
        from .content_store import get_content_repo

        # 获取在线设备
        state_db = self.state_db or get_state_db()
        discovery = DeviceDiscovery(self.device_id, ["139.199.124.242:8888"])
        online = discovery.get_online_devices()

        results = {}
        for device in online:
            # 状态同步
            results[device.device_id] = {
                "state": self.sync_state_with_peer(device.device_id),
            }

        return results


# 为避免循环导入，在文件末尾定义 Operation
from dataclasses import dataclass as _dc


@_dc
class Operation:
    """操作记录"""
    id: str
    type: str
    key: str
    value: Any
    timestamp: float
    device_id: str
    vector_clock: Dict[str, int]
    crdt_type: str = "lww_register"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "key": self.key,
            "value": self.value,
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "vector_clock": self.vector_clock,
            "crdt_type": self.crdt_type,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Operation':
        return cls(
            id=data["id"],
            type=data["type"],
            key=data["key"],
            value=data["value"],
            timestamp=data["timestamp"],
            device_id=data["device_id"],
            vector_clock=data.get("vector_clock", {}),
            crdt_type=data.get("crdt_type", "lww_register"),
            tags=data.get("tags", [])
        )


# ============================================================
# 全局单例
# ============================================================

_p2p_manager: Optional['P2PSyncManager'] = None


class P2PSyncManager:
    """
    P2P 同步管理器

    整合设备发现、连接管理和同步协议
    """

    def __init__(self, device_id: str, relay_servers: List[str]):
        self.device_id = device_id
        self.relay_servers = relay_servers

        # 子组件
        self.discovery = DeviceDiscovery(device_id, relay_servers)
        self.connection_manager = P2PConnectionManager(device_id)

        # 同步管理器（延迟初始化）
        self.sync_manager: Optional[SyncManager] = None

    def initialize(self, state_db, content_repo):
        """初始化同步管理器"""
        self.sync_manager = SyncManager(
            self.device_id,
            state_db,
            content_repo,
            self.connection_manager
        )

    def start(self):
        """启动P2P同步"""
        self.discovery.start()
        if self.sync_manager:
            self.sync_manager.start_auto_sync(interval=60)

    def stop(self):
        """停止P2P同步"""
        self.discovery.stop()
        if self.sync_manager:
            self.sync_manager.stop_auto_sync()
        self.connection_manager.close_all()

    def get_online_peers(self) -> List[DeviceInfo]:
        """获取在线对等节点"""
        return self.discovery.get_online_devices()


def get_p2p_manager() -> Optional[P2PSyncManager]:
    """获取全局P2P管理器"""
    return _p2p_manager


def initialize_p2p(
    device_id: str,
    relay_servers: Optional[List[str]] = None,
    state_db=None,
    content_repo=None
) -> P2PSyncManager:
    """初始化P2P同步"""
    global _p2p_manager

    if relay_servers is None:
        relay_servers = ["139.199.124.242:8888"]

    _p2p_manager = P2PSyncManager(device_id, relay_servers)
    _p2p_manager.initialize(state_db, content_repo)
    _p2p_manager.start()

    return _p2p_manager


def reset_p2p_manager():
    """重置全局P2P管理器"""
    global _p2p_manager
    if _p2p_manager:
        _p2p_manager.stop()
    _p2p_manager = None