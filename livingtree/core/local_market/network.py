"""
去中心化 P2P 网络层

实现节点发现、广播、连接管理等功能
"""

import asyncio
import json
import socket
import struct
import hashlib
import random
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging

from .models import NodeInfo, NodeType, GeoLocation, NetworkMessage, MessageType


logger = logging.getLogger(__name__)


class Protocol(Enum):
    """网络协议类型"""
    UDP = "udp"
    TCP = "tcp"
    WEBRTC = "webrtc"


@dataclass
class Connection:
    """连接信息"""
    conn_id: str
    node_id: str
    protocol: Protocol
    address: tuple  # (ip, port)

    is_incoming: bool = False
    is_encrypted: bool = False

    # 统计
    bytes_sent: int = 0
    bytes_recv: int = 0
    last_activity: datetime = field(default_factory=datetime.now)
    latency_ms: float = 0.0

    # 状态
    is_alive: bool = True
    relay_count: int = 0  # 作为中继的次数


class NodePeer:
    """P2P 网络节点"""

    BUFFER_SIZE = 65536
    UDP_DISCOVERY_PORT = 54321
    TCP_BASE_PORT = 54322

    def __init__(
        self,
        node_id: str,
        node_info: NodeInfo,
        enable_udp: bool = True,
        enable_tcp: bool = True
    ):
        self.node_id = node_id
        self.node_info = node_info

        self.enable_udp = enable_udp
        self.enable_tcp = enable_tcp

        # 网络组件
        self.udp_socket: Optional(socket.socket) = None
        self.tcp_server: Optional[socket.socket] = None
        self.tcp_connections: Dict[str, Connection] = {}
        self.relay_connections: Dict[str, Connection] = {}

        # 节点路由表
        self.routing_table: Dict[str, NodeInfo] = {}
        self.pending_discovery: Set[str] = set()  # 待发现的节点ID

        # 消息处理
        self.message_handlers: Dict[MessageType, Callable] = {}

        # 统计
        self.stats = {
            "messages_sent": 0,
            "messages_recv": 0,
            "bytes_sent": 0,
            "bytes_recv": 0,
            "relay_count": 0
        }

        # 状态
        self._running = False
        self._lock = asyncio.Lock()

        # 回调
        self.on_node_discovered: Optional[Callable] = None
        self.on_message_received: Optional[Callable] = None

    # ========================================================================
    # 生命周期
    # ========================================================================

    async def start(self):
        """启动节点"""
        async with self._lock:
            if self._running:
                return

            self._running = True

            # 启动 UDP 发现
            if self.enable_udp:
                await self._start_udp()

            # 启动 TCP 服务器
            if self.enable_tcp:
                await self._start_tcp()

            # 启动定期任务
            asyncio.create_task(self._heartbeat_loop())
            asyncio.create_task(self._cleanup_loop())

            logger.info(f"Node {self.node_id} started")

    async def stop(self):
        """停止节点"""
        async with self._lock:
            if not self._running:
                return

            self._running = False

            # 关闭 UDP
            if self.udp_socket:
                self.udp_socket.close()
                self.udp_socket = None

            # 关闭 TCP
            if self.tcp_server:
                self.tcp_server.close()
                self.tcp_server = None

            # 关闭所有连接
            for conn in list(self.tcp_connections.values()):
                try:
                    conn.is_alive = False
                except:
                    pass

            self.tcp_connections.clear()
            self.relay_connections.clear()

            logger.info(f"Node {self.node_id} stopped")

    # ========================================================================
    # UDP 发现
    # ========================================================================

    async def _start_udp(self):
        """启动 UDP 发现服务"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # 绑定到发现端口
            self.udp_socket.bind(("", self.UDP_DISCOVERY_PORT))
            self.udp_socket.settimeout(1.0)

            # 启动接收循环
            asyncio.create_task(self._udp_receive_loop())

            logger.info(f"UDP discovery started on port {self.UDP_DISCOVERY_PORT}")

        except Exception as e:
            logger.error(f"Failed to start UDP: {e}")

    async def _udp_receive_loop(self):
        """UDP 接收循环"""
        while self._running and self.udp_socket:
            try:
                data, addr = self.udp_socket.recvfrom(self.BUFFER_SIZE)
                await self._handle_udp_packet(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"UDP receive error: {e}")
                await asyncio.sleep(0.1)

    async def _handle_udp_packet(self, data: bytes, addr: tuple):
        """处理 UDP 数据包"""
        try:
            msg = NetworkMessage.from_bytes(data)

            # 更新统计
            self.stats["bytes_recv"] += len(data)

            # 忽略自己
            if msg.sender_id == self.node_id:
                return

            # 处理发现消息
            if msg.msg_type == MessageType.DISCOVERY:
                await self._handle_discovery(msg, addr)

            # 广播给其他节点（TTL 递减）
            elif msg.msg_type in [MessageType.PRODUCT_QUERY, MessageType.REPUTATION]:
                await self._relay_broadcast(msg)

        except Exception as e:
            logger.error(f"Error handling UDP packet: {e}")

    async def _handle_discovery(self, msg: NetworkMessage, addr: tuple):
        """处理发现消息"""
        node_info = NodeInfo.from_dict(msg.payload.get("node_info", {}))

        if not node_info.node_id:
            return

        # 添加到路由表
        async with self._lock:
            self.routing_table[node_info.node_id] = node_info

        # 响应自己的存在
        response = NetworkMessage(
            msg_type=MessageType.DISCOVERY,
            sender_id=self.node_id,
            sender_name=self.node_info.name,
            payload={"node_info": self.node_info.to_dict()}
        )

        await self._send_udp(response, addr)

        # 回调
        if self.on_node_discovered:
            await self.on_node_discovered(node_info)

    async def broadcast_discovery(self):
        """广播自己的存在"""
        msg = NetworkMessage(
            msg_type=MessageType.DISCOVERY,
            sender_id=self.node_id,
            sender_name=self.node_info.name,
            payload={"node_info": self.node_info.to_dict()}
        )

        await self._send_udp_broadcast(msg)

    async def _send_udp_broadcast(self, msg: NetworkMessage):
        """发送 UDP 广播"""
        try:
            data = msg.to_bytes()
            self.udp_socket.sendto(
                data,
                ("<broadcast>", self.UDP_DISCOVERY_PORT)
            )
            self.stats["bytes_sent"] += len(data)
        except Exception as e:
            logger.error(f"UDP broadcast error: {e}")

    async def _send_udp(self, msg: NetworkMessage, addr: tuple):
        """发送 UDP 单播"""
        try:
            data = msg.to_bytes()
            self.udp_socket.sendto(data, addr)
            self.stats["bytes_sent"] += len(data)
        except Exception as e:
            logger.error(f"UDP send error: {e}")

    # ========================================================================
    # TCP 连接
    # ========================================================================

    async def _start_tcp(self):
        """启动 TCP 服务器"""
        try:
            self.tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # 尝试绑定端口
            port = self.TCP_BASE_PORT
            for _ in range(100):
                try:
                    self.tcp_server.bind(("", port))
                    self.tcp_server.listen(50)
                    self.node_info.port = port
                    break
                except OSError:
                    port += 1

            self.tcp_server.setblocking(False)

            # 启动接受循环
            asyncio.create_task(self._tcp_accept_loop())

            logger.info(f"TCP server started on port {port}")

        except Exception as e:
            logger.error(f"Failed to start TCP: {e}")

    async def _tcp_accept_loop(self):
        """TCP 接受循环"""
        loop = asyncio.get_event_loop()

        while self._running and self.tcp_server:
            try:
                client, addr = await loop.sock_accept(self.tcp_server)
                asyncio.create_task(self._handle_tcp_connection(client, addr))
            except Exception as e:
                if self._running:
                    await asyncio.sleep(0.1)

    async def _handle_tcp_connection(self, client: socket.socket, addr: tuple):
        """处理 TCP 连接"""
        conn_id = f"{addr[0]}:{addr[1]}"
        connection = Connection(
            conn_id=conn_id,
            node_id="",
            protocol=Protocol.TCP,
            address=addr,
            is_incoming=True
        )

        try:
            # 读取消息头（包含发送者ID）
            header = await self._recvall(client, 4)
            if len(header) < 4:
                return

            sender_id_len = struct.unpack("!H", header[:2])[0]
            msg_len = struct.unpack("!H", header[2:])[0]

            # 读取发送者ID和消息
            sender_id_data = await self._recvall(client, sender_id_len)
            msg_data = await self._recvall(client, msg_len)

            connection.node_id = sender_id_data.decode("utf-8")

            # 处理消息
            msg = NetworkMessage.from_bytes(msg_data)
            await self._handle_tcp_message(msg, connection)

            # 更新连接
            async with self._lock:
                self.tcp_connections[conn_id] = connection

        except Exception as e:
            logger.error(f"TCP connection error: {e}")
        finally:
            client.close()
            async with self._lock:
                self.tcp_connections.pop(conn_id, None)

    async def _recvall(self, sock: socket.socket, n: int) -> bytes:
        """接收指定长度数据"""
        data = b""
        while len(data) < n:
            chunk = sock.recv(min(n - len(data), 4096))
            if not chunk:
                break
            data += chunk
        return data

    async def _handle_tcp_message(self, msg: NetworkMessage, connection: Connection):
        """处理 TCP 消息"""
        self.stats["messages_recv"] += 1

        # 中继消息
        if msg.receiver_id and msg.receiver_id != self.node_id:
            await self._relay_message(msg)
            return

        # 分发到处理器
        handler = self.message_handlers.get(msg.msg_type)
        if handler:
            await handler(msg)

        # 回调
        if self.on_message_received:
            await self.on_message_received(msg)

    async def send_tcp_message(self, target_node_id: str, msg: NetworkMessage) -> bool:
        """发送 TCP 消息"""
        # 找到目标连接
        connection = None
        async with self._lock:
            for conn in self.tcp_connections.values():
                if conn.node_id == target_node_id:
                    connection = conn
                    break

        if not connection:
            # 尝试通过路由表建立新连接
            target_info = self.routing_table.get(target_node_id)
            if not target_info:
                logger.warning(f"Target node {target_node_id} not found in routing table")
                return False

            conn = await self._create_tcp_connection(target_info)
            if not conn:
                return False
            connection = conn

        try:
            # 发送格式: [sender_id_len(2)] [sender_id] [msg_len(2)] [msg]
            sender_id = self.node_id.encode("utf-8")
            msg_bytes = msg.to_bytes()

            header = struct.pack("!HH", len(sender_id), len(msg_bytes))
            connection.address[0].sendall(header + sender_id + msg_bytes)

            self.stats["messages_sent"] += 1
            self.stats["bytes_sent"] += len(header) + len(sender_id) + len(msg_bytes)

            return True

        except Exception as e:
            logger.error(f"TCP send error: {e}")
            connection.is_alive = False
            return False

    async def _create_tcp_connection(self, target_info: NodeInfo) -> Optional[Connection]:
        """创建 TCP 连接到目标节点"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((target_info.ip, target_info.port))
            sock.setblocking(False)

            conn = Connection(
                conn_id=f"{target_info.ip}:{target_info.port}",
                node_id=target_info.node_id,
                protocol=Protocol.TCP,
                address=(target_info.ip, target_info.port),
                is_incoming=False
            )

            async with self._lock:
                self.tcp_connections[conn.conn_id] = conn

            return conn

        except Exception as e:
            logger.error(f"Failed to create TCP connection: {e}")
            return None

    # ========================================================================
    # 消息中继
    # ========================================================================

    async def _relay_broadcast(self, msg: NetworkMessage):
        """广播中继（TTL 递减）"""
        if msg.ttl <= 0:
            return

        msg.ttl -= 1
        msg.hop_count += 1

        # 添加自己到中继路径
        if self.node_id not in msg.relay_nodes:
            msg.relay_nodes.append(self.node_id)

        # 广播给所有连接的节点
        async with self._lock:
            connections = list(self.tcp_connections.values())

        for conn in connections:
            if conn.is_alive and conn.node_id != msg.sender_id:
                try:
                    await self.send_tcp_message(conn.node_id, msg)
                except:
                    pass

    async def _relay_message(self, msg: NetworkMessage):
        """单播中继"""
        if msg.receiver_id not in self.routing_table:
            # 通过 UDP 寻找路径
            logger.debug(f"Relaying message via UDP for {msg.receiver_id}")
            return

        msg.hop_count += 1
        if self.node_id not in msg.relay_nodes:
            msg.relay_nodes.append(self.node_id)

        self.stats["relay_count"] += 1

        await self.send_tcp_message(msg.receiver_id, msg)

    # ========================================================================
    # 定期任务
    # ========================================================================

    async def _heartbeat_loop(self):
        """心跳循环 - 定期广播自己的存在"""
        while self._running:
            try:
                await self.broadcast_discovery()
                await asyncio.sleep(30)  # 每30秒广播一次
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(5)

    async def _cleanup_loop(self):
        """清理循环 - 移除不活跃的连接"""
        while self._running:
            try:
                async with self._lock:
                    now = datetime.now()
                    to_remove = []

                    # 清理超时连接
                    for conn_id, conn in self.tcp_connections.items():
                        if (now - conn.last_activity).seconds > 300:  # 5分钟超时
                            to_remove.append(conn_id)

                    for conn_id in to_remove:
                        conn = self.tcp_connections.pop(conn_id, None)
                        if conn:
                            conn.is_alive = False

                    # 清理超时路由
                    old_routes = []
                    for node_id, info in self.routing_table.items():
                        if (now - info.last_seen).seconds > 600:  # 10分钟未更新
                            old_routes.append(node_id)

                    for node_id in old_routes:
                        self.routing_table.pop(node_id, None)

                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Cleanup error: {e}")
                await asyncio.sleep(10)

    # ========================================================================
    # 消息处理注册
    # ========================================================================

    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器"""
        self.message_handlers[msg_type] = handler

    # ========================================================================
    # 节点查询
    # ========================================================================

    def get_alive_nodes(self) -> List[NodeInfo]:
        """获取所有活跃节点"""
        now = datetime.now()
        return [
            info for info in self.routing_table.values()
            if (now - info.last_seen).seconds < 300
        ]

    def get_nearest_nodes(self, node_id: str, k: int = 8) -> List[NodeInfo]:
        """获取距离最近的 K 个节点（基于节点ID的XOR距离）"""
        nodes = self.get_alive_nodes()

        def xor_distance(a: str, b: str) -> int:
            """XOR 距离"""
            ha = int(hashlib.sha256(a.encode()).hexdigest(), 16)
            hb = int(hashlib.sha256(b.encode()).hexdigest(), 16)
            return ha ^ hb

        nodes.sort(key=lambda n: xor_distance(node_id, n.node_id))
        return nodes[:k]

    def get_nodes_by_geohash(self, geohash_prefix: str) -> List[NodeInfo]:
        """获取指定地理位置附近的节点"""
        nodes = self.get_alive_nodes()
        return [
            n for n in nodes
            if n.location and n.location.geohash.startswith(geohash_prefix[:4])
        ]


# ========================================================================
# 消息队列
# ========================================================================

class MessageQueue:
    """消息队列 - 用于异步消息处理"""

    def __init__(self, max_size: int = 10000):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._running = False
        self._handlers: List[Callable] = []

    async def put(self, msg: NetworkMessage):
        """添加消息"""
        try:
            self._queue.put_nowait(msg)
        except asyncio.QueueFull:
            logger.warning("Message queue is full, dropping message")

    async def start(self):
        """启动队列处理器"""
        self._running = True
        asyncio.create_task(self._process_loop())

    async def stop(self):
        """停止队列处理器"""
        self._running = False

    def register_handler(self, handler: Callable):
        """注册处理器"""
        self._handlers.append(handler)

    async def _process_loop(self):
        """处理循环"""
        while self._running:
            try:
                msg = await self._queue.get()
                for handler in self._handlers:
                    try:
                        await handler(msg)
                    except Exception as e:
                        logger.error(f"Handler error: {e}")
            except Exception as e:
                logger.error(f"Queue process error: {e}")
                await asyncio.sleep(0.1)
