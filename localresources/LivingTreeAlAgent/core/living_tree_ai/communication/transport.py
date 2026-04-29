"""
NodeConnection - 跨平台传输层
============================

支持：
1. WebRTC DataChannel（NAT穿透）
2. WebSocket（高兼容性）
3. 原始TCP（兜底方案）

Author: LivingTreeAI Community
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """传输类型"""
    WEBRTC = "webrtc"
    WEBSOCKET = "websocket"
    TCP = "tcp"
    UNKNOWN = "unknown"


class ConnectionStrategy(Enum):
    """连接策略"""
    WEBRTC_FIRST = "webrtc_first"      # WebRTC优先
    WEBSOCKET_ONLY = "websocket_only"  # 仅WebSocket
    TCP_FALLBACK = "tcp_fallback"      # TCP兜底
    MANUAL = "manual"                  # 手动选择


@dataclass
class NodeEndpoint:
    """节点端点"""
    node_id: str
    ip: str
    port: int
    webrtc_enabled: bool = True
    websocket_port: int = 8765
    tcp_port: int = 8766
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "ip": self.ip,
            "port": self.port,
            "webrtc_enabled": self.webrtc_enabled,
            "websocket_port": self.websocket_port,
            "tcp_port": self.tcp_port,
            "metadata": self.metadata,
        }


@dataclass
class ConnectionInfo:
    """连接信息"""
    connection_id: str
    transport_type: TransportType
    node_id: str
    remote_ip: str
    remote_port: int
    local_ip: str = ""
    local_port: int = 0
    established_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    bytes_sent: int = 0
    bytes_received: int = 0
    is_active: bool = True


class NodeConnection:
    """
    跨平台节点连接管理器

    自动选择最优传输协议：
    1. WebRTC（支持NAT穿透，低延迟）
    2. WebSocket（高兼容性）
    3. TCP（最终兜底）
    """

    def __init__(self, node_id: str, strategy: ConnectionStrategy = ConnectionStrategy.WEBRTC_FIRST):
        self.node_id = node_id
        self.strategy = strategy

        # 连接存储
        self._connections: Dict[str, ConnectionInfo] = {}
        self._transports: Dict[str, Any] = {}  # 实际传输对象

        # 信令服务器（WebRTC需要）
        self._signaling_server: str = None

        # 监听器
        self._listeners: List[Callable] = []

        logger.info(f"NodeConnection 初始化: node_id={node_id}, strategy={strategy.value}")

    def set_signaling_server(self, server: str):
        """设置WebRTC信令服务器"""
        self._signaling_server = server

    async def connect_to(self, endpoint: NodeEndpoint) -> ConnectionInfo:
        """
        连接到目标节点，自动选择最优传输协议

        Args:
            endpoint: 目标节点端点信息

        Returns:
            ConnectionInfo: 连接信息

        Raises:
            ConnectionError: 所有传输方式均失败
        """
        if endpoint.node_id in self._connections:
            conn_info = self._connections[endpoint.node_id]
            if conn_info.is_active:
                return conn_info

        # 根据策略选择连接方式
        strategies = self._get_strategies(endpoint)

        last_error = None
        for transport_type in strategies:
            try:
                logger.info(f"尝试连接 {endpoint.node_id} via {transport_type.value}")
                conn_info = await self._connect(transport_type, endpoint)

                self._connections[endpoint.node_id] = conn_info
                self._notify_listeners("connection_established", conn_info)
                return conn_info

            except Exception as e:
                logger.debug(f"{transport_type.value} 连接失败: {e}")
                last_error = e
                continue

        raise ConnectionError(f"无法连接到节点 {endpoint.node_id}: {last_error}")

    def _get_strategies(self, endpoint: NodeEndpoint) -> List[TransportType]:
        """根据策略和端点信息获取传输类型列表"""
        if self.strategy == ConnectionStrategy.WEBRTC_FIRST:
            if endpoint.webrtc_enabled:
                return [TransportType.WEBRTC, TransportType.WEBSOCKET, TransportType.TCP]
            return [TransportType.WEBSOCKET, TransportType.TCP]

        elif self.strategy == ConnectionStrategy.WEBSOCKET_ONLY:
            return [TransportType.WEBSOCKET]

        elif self.strategy == ConnectionStrategy.TCP_FALLBACK:
            return [TransportType.TCP]

        else:  # MANUAL
            return [TransportType.WEBRTC, TransportType.WEBSOCKET, TransportType.TCP]

    async def _connect(self, transport_type: TransportType, endpoint: NodeEndpoint) -> ConnectionInfo:
        """执行具体类型的连接"""
        if transport_type == TransportType.WEBRTC:
            return await self._connect_webrtc(endpoint)
        elif transport_type == TransportType.WEBSOCKET:
            return await self._connect_websocket(endpoint)
        elif transport_type == TransportType.TCP:
            return await self._connect_tcp(endpoint)
        else:
            raise ConnectionError(f"未知传输类型: {transport_type}")

    async def _connect_webrtc(self, endpoint: NodeEndpoint) -> ConnectionInfo:
        """WebRTC连接（支持NAT穿透）"""
        try:
            # 检查是否安装了 aiortc
            from aiortc import RTCPeerConnection, RTCDataChannel
            from aiortc.contrib.media import MediaBlackhole

            pc = RTCPeerConnection()

            # 创建数据通道
            channel = pc.createDataChannel("lifetree", ordered=True)

            # 创建Offer
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)

            # 通过信令服务器交换SDP
            sdp_answer = await self._exchange_sdp_via_signaling(
                endpoint.node_id,
                pc.localDescription.sdp,
                pc.localDescription.type,
            )

            # 设置远程描述
            await pc.setRemoteDescription({
                "type": sdp_answer.get("type", "answer"),
                "sdp": sdp_answer.get("sdp"),
            })

            # 等待连接建立
            await self._wait_for_connection(pc)

            conn_id = str(uuid.uuid4())
            conn_info = ConnectionInfo(
                connection_id=conn_id,
                transport_type=TransportType.WEBRTC,
                node_id=endpoint.node_id,
                remote_ip=endpoint.ip,
                remote_port=endpoint.port,
            )

            self._transports[conn_id] = {
                "pc": pc,
                "channel": channel,
            }

            return conn_info

        except ImportError:
            raise ConnectionError("aiortc 未安装，无法使用 WebRTC")
        except Exception as e:
            raise ConnectionError(f"WebRTC 连接失败: {e}")

    async def _exchange_sdp_via_signaling(self, target_node_id: str, sdp: str, sdp_type: str) -> Dict:
        """通过信令服务器交换SDP"""
        if not self._signaling_server:
            raise ConnectionError("未配置信令服务器")

        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._signaling_server}/signal",
                json={
                    "from_node": self.node_id,
                    "to_node": target_node_id,
                    "sdp": sdp,
                    "type": sdp_type,
                },
                timeout=aiohttp.ClientTimeout(total=10.0)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise ConnectionError(f"信令服务器返回错误: {resp.status}")

    async def _wait_for_connection(self, pc, timeout: float = 10.0):
        """等待WebRTC连接建立"""
        start = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start < timeout:
            if pc.iceConnectionState == "connected":
                return
            if pc.iceConnectionState in ["failed", "closed"]:
                raise ConnectionError("ICE连接失败")
            await asyncio.sleep(0.1)

        raise ConnectionError("WebRTC连接超时")

    async def _connect_websocket(self, endpoint: NodeEndpoint) -> ConnectionInfo:
        """WebSocket连接"""
        try:
            import websockets

            ws_url = f"ws://{endpoint.ip}:{endpoint.websocket_port}"

            ws = await websockets.connect(
                ws_url,
                open_timeout=10.0,
                close_timeout=5.0,
            )

            conn_id = str(uuid.uuid4())
            conn_info = ConnectionInfo(
                connection_id=conn_id,
                transport_type=TransportType.WEBSOCKET,
                node_id=endpoint.node_id,
                remote_ip=endpoint.ip,
                remote_port=endpoint.websocket_port,
            )

            self._transports[conn_id] = {
                "ws": ws,
            }

            return conn_info

        except ImportError:
            raise ConnectionError("websockets 未安装")
        except Exception as e:
            raise ConnectionError(f"WebSocket连接失败: {e}")

    async def _connect_tcp(self, endpoint: NodeEndpoint) -> ConnectionInfo:
        """原始TCP连接（最终兜底）"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(endpoint.ip, endpoint.tcp_port),
                timeout=10.0,
            )

            conn_id = str(uuid.uuid4())
            conn_info = ConnectionInfo(
                connection_id=conn_id,
                transport_type=TransportType.TCP,
                node_id=endpoint.node_id,
                remote_ip=endpoint.ip,
                remote_port=endpoint.tcp_port,
            )

            self._transports[conn_id] = {
                "reader": reader,
                "writer": writer,
            }

            return conn_info

        except Exception as e:
            raise ConnectionError(f"TCP连接失败: {e}")

    async def send(self, node_id: str, data: bytes) -> int:
        """发送数据到指定节点"""
        if node_id not in self._connections:
            raise ConnectionError(f"未连接到节点: {node_id}")

        conn_info = self._connections[node_id]
        conn_id = conn_info.connection_id

        if conn_id not in self._transports:
            raise ConnectionError("传输对象不存在")

        transport = self._transports[conn_id]
        sent_bytes = 0

        if conn_info.transport_type == TransportType.WEBSOCKET:
            await transport["ws"].send(data)
            sent_bytes = len(data)

        elif conn_info.transport_type == TransportType.TCP:
            transport["writer"].write(data)
            await transport["writer"].drain()
            sent_bytes = len(data)

        conn_info.bytes_sent += sent_bytes
        conn_info.last_activity = datetime.now()

        return sent_bytes

    async def receive(self, node_id: str, timeout: float = None) -> Optional[bytes]:
        """从指定节点接收数据"""
        if node_id not in self._connections:
            raise ConnectionError(f"未连接到节点: {node_id}")

        conn_info = self._connections[node_id]
        conn_id = conn_info.connection_id

        if conn_id not in self._transports:
            raise ConnectionError("传输对象不存在")

        transport = self._transports[conn_id]

        if conn_info.transport_type == TransportType.WEBSOCKET:
            try:
                data = await asyncio.wait_for(
                    transport["ws"].recv(),
                    timeout=timeout,
                )
                conn_info.bytes_received += len(data)
                conn_info.last_activity = datetime.now()
                return data
            except asyncio.TimeoutError:
                return None

        elif conn_info.transport_type == TransportType.TCP:
            try:
                data = await asyncio.wait_for(
                    transport["reader"].read(4096),
                    timeout=timeout,
                )
                if data:
                    conn_info.bytes_received += len(data)
                    conn_info.last_activity = datetime.now()
                    return data
                return None
            except asyncio.TimeoutError:
                return None

        return None

    async def disconnect(self, node_id: str):
        """断开与指定节点的连接"""
        if node_id not in self._connections:
            return

        conn_info = self._connections[node_id]
        conn_id = conn_info.connection_id

        if conn_id in self._transports:
            transport = self._transports[conn_id]

            if conn_info.transport_type == TransportType.WEBRTC:
                if "channel" in transport:
                    transport["channel"].close()
                if "pc" in transport:
                    transport["pc"].close()

            elif conn_info.transport_type == TransportType.WEBSOCKET:
                if "ws" in transport:
                    await transport["ws"].close()

            elif conn_info.transport_type == TransportType.TCP:
                if "writer" in transport:
                    transport["writer"].close()
                    await transport["writer"].wait_closed()

            del self._transports[conn_id]

        conn_info.is_active = False
        del self._connections[node_id]

        self._notify_listeners("connection_closed", conn_info)

    def get_connection(self, node_id: str) -> Optional[ConnectionInfo]:
        """获取连接信息"""
        return self._connections.get(node_id)

    def get_all_connections(self) -> List[ConnectionInfo]:
        """获取所有连接"""
        return list(self._connections.values())

    def is_connected(self, node_id: str) -> bool:
        """检查是否连接到指定节点"""
        conn = self._connections.get(node_id)
        return conn is not None and conn.is_active

    def subscribe(self, callback: Callable):
        """订阅连接事件"""
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)

    def _notify_listeners(self, event: str, data: Any):
        for listener in self._listeners:
            try:
                listener(event, data)
            except Exception as e:
                logger.error(f"监听器回调错误: {e}")


# 单例实例
_transport: Optional[NodeConnection] = None


def get_transport(node_id: str = None, strategy: ConnectionStrategy = ConnectionStrategy.WEBRTC_FIRST) -> NodeConnection:
    global _transport
    if _transport is None:
        _transport = NodeConnection(
            node_id=node_id or "anonymous",
            strategy=strategy,
        )
    return _transport