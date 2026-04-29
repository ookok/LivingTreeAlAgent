# -*- coding: utf-8 -*-
"""
Phase 4: WebRTC网页节点化
P2P网络自举协议 - 浏览器端P2P连接

核心理念：
- 当所有已知节点和中继都断开时，浏览器可直接建立P2P连接
- 浏览器本身也成为网络中的临时中继节点
- 实现"最后一公里"的完全去中心化

作者：Hermes Desktop V2.0
版本：1.0.0
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable
from datetime import datetime
import asyncio
import json


class WebRTCState(Enum):
    """WebRTC连接状态"""
    NEW = "new"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    CLOSED = "closed"


@dataclass
class SignalingMessage:
    """信令消息"""
    type: str  # offer, answer, ice_candidate, leave
    from_peer: str
    to_peer: str
    data: Dict
    timestamp: datetime = field(default_factory=datetime.now)

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type,
            "from_peer": self.from_peer,
            "to_peer": self.to_peer,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        })

    @classmethod
    def from_json(cls, json_str: str) -> "SignalingMessage":
        data = json.loads(json_str)
        return cls(
            type=data["type"],
            from_peer=data["from_peer"],
            to_peer=data["to_peer"],
            data=data["data"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


@dataclass
class WebRTCPeerConnection:
    """WebRTC对等连接"""
    peer_id: str
    peer_name: str

    state: WebRTCState = WebRTCState.NEW

    # RTCPeerConnection引用（实际使用WebRTC API）
    connection: Optional[Any] = None

    # 数据通道
    data_channel: Optional[Any] = None

    # 统计
    bytes_sent: int = 0
    bytes_received: int = 0
    connected_at: Optional[datetime] = None

    # 能力标志
    can_relay: bool = True  # 是否可以作为中继
    is_relay: bool = False  # 是否正在作为中继


class SignalingServer:
    """
    WebRTC信令服务器

    负责：
    1. 用户注册和状态管理
    2. offer/answer交换
    3. ICE候选者转发
    4. 房间/会话管理
    """

    def __init__(self, server_id: str):
        self.server_id = server_id

        # 注册的用户
        self.registered_peers: Dict[str, Dict] = {}

        # 待处理的offer/answer
        self.pending_offers: Dict[str, SignalingMessage] = {}

        # 信令回调
        self.on_signaling_message: Optional[Callable] = None

        # WebSocket连接（模拟）
        self.connections: Dict[str, Any] = {}

    async def register_peer(self, peer_id: str, peer_info: Dict) -> bool:
        """
        注册对等体

        存储对等体的连接信息，等待其他对等体连接
        """
        self.registered_peers[peer_id] = {
            "peer_id": peer_id,
            "name": peer_info.get("name", f"Peer-{peer_id[:6]}"),
            "can_relay": peer_info.get("can_relay", True),
            "registered_at": datetime.now(),
            "last_seen": datetime.now(),
            "webrtc_enabled": True
        }

        return True

    async def unregister_peer(self, peer_id: str):
        """注销对等体"""
        if peer_id in self.registered_peers:
            del self.registered_peers[peer_id]

        # 清理待处理的offer
        if peer_id in self.pending_offers:
            del self.pending_offers[peer_id]

    async def get_available_peers(self, exclude_peer_id: str) -> List[Dict]:
        """获取可用的对等体列表"""
        return [
            {
                "peer_id": pid,
                "name": info["name"],
                "can_relay": info["can_relay"],
                "last_seen": info["last_seen"].isoformat()
            }
            for pid, info in self.registered_peers.items()
            if pid != exclude_peer_id
        ]

    async def send_offer(self, from_peer: str, to_peer: str, offer_data: Dict) -> bool:
        """
        发送WebRTC Offer

        存储offer，等待目标对等体获取
        """
        if to_peer not in self.registered_peers:
            return False

        message = SignalingMessage(
            type="offer",
            from_peer=from_peer,
            to_peer=to_peer,
            data=offer_data
        )

        self.pending_offers[to_peer] = message

        # 如果目标对等体已连接，通知它
        if self.on_signaling_message:
            await self.on_signaling_message(message)

        return True

    async def send_answer(self, from_peer: str, to_peer: str, answer_data: Dict) -> bool:
        """
        发送WebRTC Answer
        """
        if to_peer not in self.registered_peers:
            return False

        message = SignalingMessage(
            type="answer",
            from_peer=from_peer,
            to_peer=to_peer,
            data=answer_data
        )

        # 发送给目标
        if self.on_signaling_message:
            await self.on_signaling_message(message)

        return True

    async def send_ice_candidate(self, from_peer: str, to_peer: str, candidate_data: Dict) -> bool:
        """
        发送ICE候选者
        """
        if to_peer not in self.registered_peers:
            return False

        message = SignalingMessage(
            type="ice_candidate",
            from_peer=from_peer,
            to_peer=to_peer,
            data=candidate_data
        )

        if self.on_signaling_message:
            await self.on_signaling_message(message)

        return True

    async def get_pending_offer(self, peer_id: str) -> Optional[SignalingMessage]:
        """获取待处理的offer"""
        return self.pending_offers.pop(peer_id, None)

    async def update_last_seen(self, peer_id: str):
        """更新最后可见时间"""
        if peer_id in self.registered_peers:
            self.registered_peers[peer_id]["last_seen"] = datetime.now()


class WebRTCGateway:
    """
    WebRTC网关

    作为传统P2P网络和浏览器WebRTC节点之间的桥梁
    """

    def __init__(
        self,
        gateway_id: str,
        signaling_server: SignalingServer,
        relay_service: Any = None
    ):
        self.gateway_id = gateway_id
        self.signaling = signaling_server
        self.relay = relay_service

        # 当前连接的WebRTC对等体
        self.connected_peers: Dict[str, WebRTCPeerConnection] = {}

        # 作为中继的连接
        self.relay_connections: Dict[str, WebRTCPeerConnection] = {}

        # 回调
        self.on_peer_connected: Optional[Callable] = None
        self.on_peer_disconnected: Optional[Callable] = None
        self.on_relay_request: Optional[Callable] = None

    async def register_as_gateway(self, network_bootstrap: Any):
        """
        注册为网关节点

        向主网络广播自己是WebRTC网关
        """
        # 向节点注册表注册
        if network_bootstrap:
            await network_bootstrap.announce_webRTC_gateway(self.gateway_id)

    async def connect_to_peer(self, peer_id: str, peer_info: Dict) -> bool:
        """
        连接到WebRTC对等体
        """
        peer_conn = WebRTCPeerConnection(
            peer_id=peer_id,
            peer_name=peer_info.get("name", f"Peer-{peer_id[:6]}"),
            can_relay=peer_info.get("can_relay", True)
        )

        self.connected_peers[peer_id] = peer_conn

        return True

    async def disconnect_peer(self, peer_id: str):
        """断开对等体连接"""
        if peer_id in self.connected_peers:
            peer = self.connected_peers[peer_id]

            # 如果是作为中继的连接，清理
            if peer.is_relay and peer_id in self.relay_connections:
                del self.relay_connections[peer_id]

            del self.connected_peers[peer_id]

            if self.on_peer_disconnected:
                await self.on_peer_disconnected(peer_id)

    async def relay_data(self, from_peer: str, to_peer: str, data: bytes):
        """
        通过WebRTC连接中继数据

        当两个浏览器之间无法直连时，通过网关中继
        """
        if from_peer not in self.connected_peers or to_peer not in self.connected_peers:
            return False

        # 这里会调用实际的数据通道发送
        # await self.connected_peers[to_peer].data_channel.send(data)
        return True

    def get_gateway_status(self) -> Dict:
        """获取网关状态"""
        return {
            "gateway_id": self.gateway_id,
            "connected_peers": len(self.connected_peers),
            "relay_connections": len(self.relay_connections),
            "total_bytes_relayed": sum(
                p.bytes_sent + p.bytes_received
                for p in self.connected_peers.values()
            )
        }


class BrowserNodeBridge:
    """
    浏览器节点桥接器

    在浏览器环境中模拟节点行为，
    实现"网页即节点"的概念
    """

    def __init__(
        self,
        node_id: str,
        signaling_gateway_url: str,
        webrtc_gateway: WebRTCGateway
    ):
        self.node_id = node_id
        self.signaling_url = signaling_gateway_url
        self.gateway = webrtc_gateway

        # WebRTC连接管理
        self.connections: Dict[str, WebRTCPeerConnection] = {}
        self.pending_connections: Dict[str, asyncio.Future] = {}

        # 作为中继的能力
        self.can_relay = True
        self.relayed_peers: Set[str] = set()

        # 信令服务引用
        self.signaling: Optional[SignalingServer] = None

    async def initialize(self):
        """
        初始化浏览器节点

        连接到信令服务器
        """
        # 连接信令服务器
        # 实际使用WebSocket
        # self.signaling = await connect_to_signaling(self.signaling_url)

        # 注册到信令服务器
        if self.signaling:
            await self.signaling.register_peer(self.node_id, {
                "name": f"BrowserNode-{self.node_id[:6]}",
                "can_relay": self.can_relay
            })

    async def discover_peers(self) -> List[Dict]:
        """
        发现可用的对等体

        从信令服务器获取可连接的浏览器节点
        """
        if not self.signaling:
            return []

        peers = await self.signaling.get_available_peers(self.node_id)
        return peers

    async def connect_to_peer(self, target_peer_id: str) -> bool:
        """
        连接到目标对等体
        """
        # 创建连接Future
        self.pending_connections[target_peer_id] = asyncio.get_event_loop().create_future()

        # 检查待处理的offer
        if self.signaling:
            pending_offer = await self.signaling.get_pending_offer(self.node_id)

            if pending_offer and pending_offer.from_peer == target_peer_id:
                # 有来自目标对等体的offer，处理它
                await self._handle_offer(pending_offer)
            else:
                # 没有offer，发送自己的offer
                await self._send_offer(target_peer_id)

        # 等待连接建立
        try:
            await asyncio.wait_for(
                self.pending_connections[target_peer_id],
                timeout=30
            )
            return True
        except asyncio.TimeoutError:
            return False

    async def _send_offer(self, target_peer_id: str):
        """
        发送WebRTC Offer

        实际使用时创建RTCPeerConnection并生成offer
        """
        # 模拟创建offer
        offer_data = {
            "type": "offer",
            "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\n...",  # 模拟SDP
            "connection_id": self.node_id
        }

        if self.signaling:
            await self.signaling.send_offer(self.node_id, target_peer_id, offer_data)

    async def _handle_offer(self, offer: SignalingMessage):
        """
        处理接收到的offer
        """
        # 创建answer
        answer_data = {
            "type": "answer",
            "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\n...",
            "connection_id": self.node_id
        }

        if self.signaling:
            await self.signaling.send_answer(
                self.node_id,
                offer.from_peer,
                answer_data
            )

    async def _handle_answer(self, answer: SignalingMessage):
        """
        处理接收到的answer
        """
        # 完成连接建立
        if answer.from_peer in self.pending_connections:
            self.pending_connections[answer.from_peer].set_result(True)

    async def _handle_ice_candidate(self, candidate: SignalingMessage):
        """
        处理ICE候选者
        """
        # 将候选者添加到RTCPeerConnection
        pass

    async def send_data(self, to_peer: str, data: bytes) -> bool:
        """
        发送数据到对等体
        """
        if to_peer not in self.connections:
            return False

        conn = self.connections[to_peer]

        if conn.data_channel and conn.state == WebRTCState.CONNECTED:
            # await conn.data_channel.send(data)
            conn.bytes_sent += len(data)
            return True

        return False

    async def relay_data(self, from_peer: str, to_peer: str, data: bytes) -> bool:
        """
        中继数据

        当浏览器作为中继节点时，转发两个对等体之间的数据
        """
        if not self.can_relay:
            return False

        # 记录中继关系
        self.relayed_peers.add(from_peer)
        self.relayed_peers.add(to_peer)

        # 转发数据
        return await self.send_data(to_peer, data)

    def get_node_status(self) -> Dict:
        """获取节点状态"""
        connected_count = sum(
            1 for c in self.connections.values()
            if c.state == WebRTCState.CONNECTED
        )

        return {
            "node_id": self.node_id,
            "type": "browser_node",
            "can_relay": self.can_relay,
            "connected_peers": connected_count,
            "relayed_peers": len(self.relayed_peers),
            "total_bytes_sent": sum(c.bytes_sent for c in self.connections.values()),
            "total_bytes_received": sum(c.bytes_received for c in self.connections.values())
        }


class DistributedWebRTCNetwork:
    """
    分布式WebRTC网络

    整合所有WebRTC相关组件，
    实现浏览器节点的完全去中心化组网
    """

    def __init__(self, network_id: str):
        self.network_id = network_id

        # 组件
        self.signaling = SignalingServer(f"signaling_{network_id}")
        self.gateway: Optional[WebRTCGateway] = None
        self.browser_nodes: Dict[str, BrowserNodeBridge] = {}

        # 网络引用
        self.network_bootstrap: Optional[Any] = None

        # 配置
        self.max_browser_nodes = 1000
        self.relay_bandwidth_limit_mbps = 100

    async def initialize(self, network_bootstrap: Any):
        """
        初始化WebRTC网络
        """
        self.network_bootstrap = network_bootstrap

        # 创建网关
        self.gateway = WebRTCGateway(
            f"webrtc_gateway_{self.network_id}",
            self.signaling
        )

        # 注册为网关到主网络
        await self.gateway.register_as_gateway(network_bootstrap)

    def add_browser_node(self, node_id: str, signaling_url: str) -> BrowserNodeBridge:
        """
        添加浏览器节点
        """
        if len(self.browser_nodes) >= self.max_browser_nodes:
            raise Exception("Maximum browser nodes reached")

        if node_id in self.browser_nodes:
            return self.browser_nodes[node_id]

        bridge = BrowserNodeBridge(
            node_id=node_id,
            signaling_gateway_url=signaling_url,
            webrtc_gateway=self.gateway
        )

        self.browser_nodes[node_id] = bridge

        return bridge

    async def remove_browser_node(self, node_id: str):
        """移除浏览器节点"""
        if node_id in self.browser_nodes:
            bridge = self.browser_nodes[node_id]

            # 断开所有连接
            for peer_id in list(bridge.connections.keys()):
                await bridge.send_data(peer_id, b"CLOSE")

            del self.browser_nodes[node_id]

    async def get_network_topology(self) -> Dict:
        """
        获取网络拓扑

        包括传统节点和浏览器节点
        """
        browser_info = [
            node.get_node_status()
            for node in self.browser_nodes.values()
        ]

        return {
            "network_id": self.network_id,
            "signaling_server": self.signaling.server_id,
            "gateway": self.gateway.get_gateway_status() if self.gateway else None,
            "browser_nodes": {
                "total": len(self.browser_nodes),
                "nodes": browser_info
            }
        }
