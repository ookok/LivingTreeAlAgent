"""
中继客户端模块

支持 WebSocket/TCP 中继连接，自动重连，消息队列
from __future__ import annotations
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from collections import deque
import asyncio
import json
import logging
import time
import uuid
import random
import struct
import threading

logger = logging.getLogger(__name__)


class RelayState(Enum):
    """中继连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class RelayMessageType(Enum):
    """消息类型"""
    # 控制消息
    PING = 0x01
    PONG = 0x02
    AUTH = 0x03
    AUTH_ACK = 0x04
    REGISTER = 0x05
    REGISTER_ACK = 0x06
    
    # 点对点消息
    PEER_MSG = 0x10
    PEER_MSG_ACK = 0x11
    PEER_OFFLINE = 0x12
    PEER_ONLINE = 0x13
    
    # 广播消息
    BROADCAST = 0x20
    MULTICAST = 0x21
    
    # 文件传输
    FILE_REQUEST = 0x30
    FILE_CHUNK = 0x31
    FILE_COMPLETE = 0x32
    FILE_CANCEL = 0x33


@dataclass
class RelayServerConfig:
    """中继服务器配置"""
    # 服务器地址
    host: str = "139.199.124.242"
    port: int = 8888
    
    # 协议选项
    use_ssl: bool = False
    websocket_mode: bool = True  # 使用 WebSocket vs TCP
    http_path: str = "/relay"
    
    # 连接参数
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    heartbeat_interval: float = 30.0
    heartbeat_timeout: float = 10.0
    
    # 重连参数
    max_reconnect_attempts: int = 10
    reconnect_base_delay: float = 1.0
    reconnect_max_delay: float = 60.0
    
    # 消息队列
    max_queue_size: int = 1000
    message_retry: int = 3
    message_retry_delay: float = 5.0
    
    # 认证
    api_key: str = ""
    auth_token: str = ""
    
    # 调试
    debug: bool = False


@dataclass
class PeerInfo:
    """对等节点信息"""
    peer_id: str
    public_addr: str = ""
    local_addr: str = ""
    nat_type: str = "unknown"
    online: bool = False
    last_seen: datetime = field(default_factory=datetime.now)
    latency: float = 0


@dataclass
class QueuedMessage:
    """排队消息"""
    message_id: str
    target_peer: str
    content: Any
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    priority: int = 0
    
    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "target_peer": self.target_peer,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "retry_count": self.retry_count,
            "priority": self.priority,
        }


class RelayClient:
    """
    中继客户端
    
    Features:
    - WebSocket/TCP 双协议支持
    - 自动重连
    - 消息队列与重试
    - 点对点消息
    - 广播/多播
    - 心跳保活
    - 加密传输
    """
    
    def __init__(
        self,
        peer_id: str,
        config: RelayServerConfig = None
    ):
        self.peer_id = peer_id
        self.config = config or RelayServerConfig()
        
        # 状态
        self._state = RelayState.DISCONNECTED
        self._lock = threading.RLock()
        
        # 连接
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 消息队列
        self._message_queue: deque = deque(maxlen=self.config.max_queue_size)
        self._pending_messages: Dict[str, QueuedMessage] = {}
        
        # 节点管理
        self._peers: Dict[str, PeerInfo] = {}
        
        # 统计
        self._stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "reconnects": 0,
            "errors": 0,
        }
        
        # 监听器
        self._on_message: Optional[Callable] = None
        self._on_peer_online: Optional[Callable] = None
        self._on_peer_offline: Optional[Callable] = None
        self._on_state_change: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        
        # 重连
        self._reconnect_attempts = 0
    
    @property
    def state(self) -> RelayState:
        """获取连接状态"""
        return self._state
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._state in [RelayState.CONNECTED, RelayState.AUTHENTICATED]
    
    def set_callbacks(
        self,
        on_message: Callable = None,
        on_peer_online: Callable = None,
        on_peer_offline: Callable = None,
        on_state_change: Callable = None,
        on_error: Callable = None,
    ):
        """设置回调函数"""
        if on_message:
            self._on_message = on_message
        if on_peer_online:
            self._on_peer_online = on_peer_online
        if on_peer_offline:
            self._on_peer_offline = on_peer_offline
        if on_state_change:
            self._on_state_change = on_state_change
        if on_error:
            self._on_error = on_error
    
    def _set_state(self, new_state: RelayState):
        """设置状态"""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            logger.info(f"Relay state: {old_state.value} -> {new_state.value}")
            if self._on_state_change:
                try:
                    self._on_state_change(old_state, new_state)
                except Exception as e:
                    logger.error(f"State change callback error: {e}")
    
    async def connect(self) -> bool:
        """连接到中继服务器"""
        if self.is_connected:
            return True
        
        self._set_state(RelayState.CONNECTING)
        
        try:
            # 根据配置选择协议
            if self.config.websocket_mode:
                success = await self._connect_websocket()
            else:
                success = await self._connect_tcp()
            
            if success:
                # 认证
                if await self._authenticate():
                    self._set_state(RelayState.AUTHENTICATED)
                    
                    # 注册节点
                    if await self._register_peer():
                        # 启动心跳
                        self._running = True
                        self._start_heartbeat()
                        
                        # 启动消息处理
                        self._start_message_processor()
                        
                        logger.info(f"Connected to relay server {self.config.host}:{self.config.port}")
                        return True
                
                self._set_state(RelayState.ERROR)
                return False
            else:
                self._set_state(RelayState.DISCONNECTED)
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self._set_state(RelayState.ERROR)
            self._stats["errors"] += 1
            if self._on_error:
                self._on_error(e)
            return False
    
    async def _connect_tcp(self) -> bool:
        """TCP连接"""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self.config.host,
                    self.config.port,
                    ssl=self.config.use_ssl,
                ),
                timeout=self.config.connect_timeout,
            )
            return True
        except Exception as e:
            logger.error(f"TCP connection failed: {e}")
            return False
    
    async def _connect_websocket(self) -> bool:
        """WebSocket连接"""
        try:
            # 简化实现：使用 TCP 模拟 WebSocket
            # 实际项目中可使用 websockets 库
            return await self._connect_tcp()
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            return False
    
    async def _authenticate(self) -> bool:
        """认证"""
        try:
            # 发送认证消息
            auth_data = {
                "type": "auth",
                "peer_id": self.peer_id,
                "api_key": self.config.api_key,
                "timestamp": int(time.time()),
            }
            
            await self._send_raw(json.dumps(auth_data).encode())
            
            # 等待认证响应
            response = await asyncio.wait_for(
                self._receive_message(),
                timeout=self.config.read_timeout,
            )
            
            if response:
                data = json.loads(response)
                if data.get("type") == "auth_ack" and data.get("success"):
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    async def _register_peer(self) -> bool:
        """注册节点"""
        try:
            register_data = {
                "type": "register",
                "peer_id": self.peer_id,
                "public_addr": "",  # 服务器自动获取
                "timestamp": int(time.time()),
            }
            
            await self._send_raw(json.dumps(register_data).encode())
            return True
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        self._running = False
        
        # 停止任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._ws_task:
            self._ws_task.cancel()
        
        # 关闭连接
        if self._writer:
            self._writer.close()
            await asyncio.wait_for(self._writer.wait_closed(), timeout=5)
        
        self._set_state(RelayState.DISCONNECTED)
        logger.info("Disconnected from relay server")
    
    async def _send_raw(self, data: bytes) -> bool:
        """发送原始数据"""
        if not self._writer:
            return False
        
        try:
            # 添加长度前缀
            length = struct.pack('>I', len(data))
            self._writer.write(length + data)
            await self._writer.drain()
            self._stats["bytes_sent"] += len(data)
            return True
        except Exception as e:
            logger.error(f"Send failed: {e}")
            self._stats["errors"] += 1
            return False
    
    async def _receive_message(self) -> Optional[str]:
        """接收消息"""
        if not self._reader:
            return None
        
        try:
            # 读取长度前缀
            length_data = await asyncio.wait_for(
                self._reader.readexactly(4),
                timeout=self.config.read_timeout,
            )
            length = struct.unpack('>I', length_data)[0]
            
            # 读取数据
            data = await asyncio.wait_for(
                self._reader.readexactly(length),
                timeout=self.config.read_timeout,
            )
            
            self._stats["bytes_received"] += len(data)
            return data.decode()
        except Exception as e:
            logger.error(f"Receive failed: {e}")
            return None
    
    def _start_heartbeat(self):
        """启动心跳"""
        async def heartbeat_loop():
            while self._running and self.is_connected:
                try:
                    ping_data = {
                        "type": "ping",
                        "timestamp": int(time.time()),
                    }
                    await self._send_raw(json.dumps(ping_data).encode())
                    await asyncio.sleep(self.config.heartbeat_interval)
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
                    if self._running:
                        await self._handle_disconnect()
        
        self._heartbeat_task = asyncio.create_task(heartbeat_loop())
    
    def _start_message_processor(self):
        """启动消息处理器"""
        async def process_loop():
            while self._running and self.is_connected:
                try:
                    data = await self._receive_message()
                    if data:
                        await self._handle_message(data)
                except Exception as e:
                    logger.error(f"Message processor error: {e}")
        
        self._ws_task = asyncio.create_task(process_loop())
    
    async def _handle_message(self, data: str):
        """处理接收到的消息"""
        try:
            msg = json.loads(data)
            msg_type = msg.get("type", "")
            
            if msg_type == "pong":
                # 心跳响应
                pass
            
            elif msg_type == "peer_msg":
                # 点对点消息
                await self._handle_peer_message(msg)
            
            elif msg_type == "peer_online":
                # 节点上线
                await self._handle_peer_online(msg)
            
            elif msg_type == "peer_offline":
                # 节点下线
                await self._handle_peer_offline(msg)
            
            elif msg_type == "broadcast":
                # 广播消息
                await self._handle_broadcast(msg)
            
            elif msg_type == "error":
                # 错误消息
                logger.error(f"Server error: {msg.get('message')}")
                if self._on_error:
                    self._on_error(msg.get("message"))
            
            self._stats["messages_received"] += 1
            
            if self._on_message:
                self._on_message(msg)
                
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    async def _handle_peer_message(self, msg: dict):
        """处理点对点消息"""
        from_peer = msg.get("from_peer", "")
        content = msg.get("content", "")
        message_id = msg.get("message_id", "")
        
        # 发送确认
        ack = {
            "type": "peer_msg_ack",
            "message_id": message_id,
        }
        await self._send_raw(json.dumps(ack).encode())
    
    async def _handle_peer_online(self, msg: dict):
        """处理节点上线"""
        peer_id = msg.get("peer_id", "")
        if peer_id and peer_id != self.peer_id:
            if peer_id not in self._peers:
                self._peers[peer_id] = PeerInfo(peer_id=peer_id)
            self._peers[peer_id].online = True
            self._peers[peer_id].last_seen = datetime.now()
            
            if self._on_peer_online:
                self._on_peer_online(peer_id)
    
    async def _handle_peer_offline(self, msg: dict):
        """处理节点下线"""
        peer_id = msg.get("peer_id", "")
        if peer_id in self._peers:
            self._peers[peer_id].online = False
            
            if self._on_peer_offline:
                self._on_peer_offline(peer_id)
    
    async def _handle_broadcast(self, msg: dict):
        """处理广播"""
        # 广播消息通常转发给应用层
        pass
    
    async def _handle_disconnect(self):
        """处理断开连接"""
        self._set_state(RelayState.RECONNECTING)
        
        # 尝试重连
        if self._reconnect_attempts < self.config.max_reconnect_attempts:
            delay = min(
                self.config.reconnect_base_delay * (2 ** self._reconnect_attempts),
                self.config.reconnect_max_delay,
            )
            delay += random.uniform(0, 1)  # 添加随机抖动
            
            logger.info(f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts + 1})")
            await asyncio.sleep(delay)
            
            self._reconnect_attempts += 1
            self._stats["reconnects"] += 1
            
            if await self.connect():
                self._reconnect_attempts = 0
                return
        
        # 重连失败
        self._set_state(RelayState.DISCONNECTED)
        logger.error("Failed to reconnect after maximum attempts")
    
    # ==================== 公共 API ====================
    
    async def send_to_peer(
        self,
        target_peer: str,
        content: Any,
        priority: int = 0,
    ) -> Optional[str]:
        """
        发送消息给指定节点
        
        Args:
            target_peer: 目标节点ID
            content: 消息内容
            priority: 优先级 (0=低, 1=中, 2=高)
            
        Returns:
            message_id 或 None
        """
        if not self.is_connected:
            # 加入队列等待发送
            msg_id = str(uuid.uuid4())
            queued = QueuedMessage(
                message_id=msg_id,
                target_peer=target_peer,
                content=content,
                priority=priority,
            )
            self._message_queue.append(queued)
            self._pending_messages[msg_id] = queued
            return msg_id
        
        message_id = str(uuid.uuid4())
        
        try:
            msg_data = {
                "type": "peer_msg",
                "message_id": message_id,
                "from_peer": self.peer_id,
                "to_peer": target_peer,
                "content": content,
                "timestamp": int(time.time()),
            }
            
            success = await self._send_raw(json.dumps(msg_data).encode())
            
            if success:
                self._stats["messages_sent"] += 1
                return message_id
            else:
                # 发送失败，加入队列
                queued = QueuedMessage(
                    message_id=message_id,
                    target_peer=target_peer,
                    content=content,
                    priority=priority,
                )
                self._message_queue.append(queued)
                self._pending_messages[message_id] = queued
                return message_id
                
        except Exception as e:
            logger.error(f"Send to peer failed: {e}")
            return None
    
    async def broadcast(
        self,
        content: Any,
        exclude_peers: List[str] = None,
    ) -> bool:
        """
        广播消息
        
        Args:
            content: 消息内容
            exclude_peers: 排除的节点列表
            
        Returns:
            是否成功
        """
        if not self.is_connected:
            return False
        
        try:
            msg_data = {
                "type": "broadcast",
                "from_peer": self.peer_id,
                "content": content,
                "exclude": exclude_peers or [],
                "timestamp": int(time.time()),
            }
            
            return await self._send_raw(json.dumps(msg_data).encode())
        except Exception as e:
            logger.error(f"Broadcast failed: {e}")
            return False
    
    async def get_online_peers(self) -> List[str]:
        """获取在线节点列表"""
        return [p.peer_id for p in self._peers.values() if p.online]
    
    def get_peer_info(self, peer_id: str) -> Optional[PeerInfo]:
        """获取节点信息"""
        return self._peers.get(peer_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "state": self._state.value,
            "queue_size": len(self._message_queue),
            "online_peers": len([p for p in self._peers.values() if p.online]),
            "reconnect_attempts": self._reconnect_attempts,
        }
    
    # ==================== 消息队列 ====================
    
    async def _process_queue(self):
        """处理消息队列"""
        while self._running and self._message_queue:
            queued = self._message_queue.popleft()
            
            # 检查重试次数
            if queued.retry_count >= self.config.message_retry:
                logger.warning(f"Message {queued.message_id} exceeded max retries")
                self._pending_messages.pop(queued.message_id, None)
                continue
            
            # 尝试发送
            success = await self.send_to_peer(
                queued.target_peer,
                queued.content,
                queued.priority,
            )
            
            if not success:
                queued.retry_count += 1
                self._message_queue.append(queued)
                await asyncio.sleep(self.config.message_retry_delay)
    
    def clear_queue(self):
        """清空消息队列"""
        self._message_queue.clear()
        self._pending_messages.clear()


# ==================== 中继服务器管理器 ====================

class RelayServerManager:
    """
    中继服务器管理器
    
    管理多个中继服务器，自动选择最优服务器
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._servers: Dict[str, RelayServer] = {}
        self._clients: Dict[str, RelayClient] = {}
        self._primary_server_id: Optional[str] = None
        
        # 监听器
        self._on_server_added: Optional[Callable] = None
        self._on_server_removed: Optional[Callable] = None
        self._on_server_health_changed: Optional[Callable] = None
    
    def add_server(
        self,
        server_id: str,
        host: str,
        port: int = 8888,
        name: str = "",
        region: str = "",
        is_primary: bool = False,
        api_key: str = "",
    ) -> RelayServer:
        """
        添加中继服务器
        
        Args:
            server_id: 服务器ID
            host: 主机地址
            port: 端口
            name: 服务器名称
            region: 区域
            is_primary: 是否主服务器
            api_key: API密钥
            
        Returns:
            RelayServer
        """
        from .models import RelayServer as RelayServerModel
        
        with self._lock:
            server = RelayServerModel(
                id=server_id,
                host=host,
                port=port,
                name=name or f"Relay-{host}",
                region=region,
                is_primary=is_primary,
                api_key=api_key,
            )
            
            self._servers[server_id] = server
            
            if is_primary or not self._primary_server_id:
                self._primary_server_id = server_id
            
            if self._on_server_added:
                self._on_server_added(server)
            
            return server
    
    def remove_server(self, server_id: str):
        """移除服务器"""
        with self._lock:
            if server_id in self._servers:
                server = self._servers.pop(server_id)
                
                # 断开客户端连接
                if server_id in self._clients:
                    client = self._clients.pop(server_id)
                    asyncio.create_task(client.disconnect())
                
                # 更新主服务器
                if self._primary_server_id == server_id:
                    self._primary_server_id = next(
                        (s.id for s in self._servers.values() if s.enabled),
                        None
                    )
                
                if self._on_server_removed:
                    self._on_server_removed(server)
    
    def get_server(self, server_id: str) -> Optional[Any]:
        """获取服务器"""
        with self._lock:
            return self._servers.get(server_id)
    
    def get_all_servers(self) -> List[Any]:
        """获取所有服务器"""
        with self._lock:
            return list(self._servers.values())
    
    def get_best_server(self) -> Optional[Any]:
        """获取最佳服务器（质量分数最高）"""
        with self._lock:
            healthy = [s for s in self._servers.values() if s.is_healthy]
            if not healthy:
                return None
            return max(healthy, key=lambda s: s.quality_score)
    
    def get_primary_server(self) -> Optional[Any]:
        """获取主服务器"""
        with self._lock:
            return self._servers.get(self._primary_server_id)
    
    async def create_client(
        self,
        peer_id: str,
        server_id: str = None,
    ) -> Optional[RelayClient]:
        """
        创建中继客户端
        
        Args:
            peer_id: 节点ID
            server_id: 服务器ID（None表示自动选择）
            
        Returns:
            RelayClient 或 None
        """
        # 选择服务器
        if server_id:
            server = self.get_server(server_id)
        else:
            server = self.get_best_server() or self.get_primary_server()
        
        if not server:
            logger.error("No available relay server")
            return None
        
        # 创建客户端
        config = RelayServerConfig(
            host=server.host,
            port=server.port,
            api_key=server.api_key,
            websocket_mode=True,
        )
        
        client = RelayClient(peer_id, config)
        
        # 保存客户端
        with self._lock:
            self._clients[server.id] = client
        
        return client
    
    def get_client(self, server_id: str) -> Optional[RelayClient]:
        """获取客户端"""
        with self._lock:
            return self._clients.get(server_id)
    
    def set_callbacks(
        self,
        on_server_added: Callable = None,
        on_server_removed: Callable = None,
        on_server_health_changed: Callable = None,
    ):
        """设置回调"""
        if on_server_added:
            self._on_server_added = on_server_added
        if on_server_removed:
            self._on_server_removed = on_server_removed
        if on_server_health_changed:
            self._on_server_health_changed = on_server_health_changed
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        with self._lock:
            return {
                "server_count": len(self._servers),
                "client_count": len(self._clients),
                "primary_server": self._primary_server_id,
                "servers": {
                    sid: {
                        "host": s.host,
                        "port": s.port,
                        "quality_score": s.quality_score,
                        "latency": s.latency,
                        "online": s.is_healthy,
                    }
                    for sid, s in self._servers.items()
                },
            }


# ==================== 单例 ====================

_relay_manager: Optional[RelayServerManager] = None


def get_relay_manager() -> RelayServerManager:
    """获取中继管理器"""
    global _relay_manager
    if _relay_manager is None:
        _relay_manager = RelayServerManager()
        
        # 添加默认服务器配置
        _relay_manager.add_server(
            server_id="default",
            host="139.199.124.242",
            port=8888,
            name="腾讯云服务器",
            region="华南",
            is_primary=True,
        )
    
    return _relay_manager


__all__ = [
    "RelayState",
    "RelayMessageType",
    "RelayServerConfig",
    "PeerInfo",
    "QueuedMessage",
    "RelayClient",
    "RelayServerManager",
    "get_relay_manager",
]
