# -*- coding: utf-8 -*-
"""
P2P网络自举协议 - 统一入口引擎
P2P Network Bootstrap Unified Engine

4层架构完整实现：
- Phase 1: 节点即配置源 (Node-as-a-Config)
- Phase 2: 连接池与QoS自动切换
- Phase 3: Gossip协议自愈网络
- Phase 4: WebRTC网页节点化
+ 中继透明化模块

作者：Hermes Desktop V2.0
版本：1.0.0
"""

from typing import Dict, List, Optional, Set, Any
from datetime import datetime
import asyncio
import hashlib

from .node_discovery import (
    NodeRole,
    NodeStatus,
    NodeInfo,
    NetworkTopology,
    NodeRegistry,
    NodeDiscoveryService,
    TopologyPushService,
    BootstrapProtocol
)

from .connection_pool import (
    ConnectionStatus,
    ConnectionQuality,
    ConnectionMetrics,
    Connection,
    ConnectionPool,
    QoSRouter,
    AdaptiveTopologyManager
)

from .gossip_protocol import (
    GossipEventType,
    GossipEvent,
    PeerState,
    GossipProtocol,
    ReverseRecommendationEngine,
    SelfHealingManager
)

from .webrtc_bridge import (
    WebRTCState,
    SignalingMessage,
    WebRTCPeerConnection,
    SignalingServer,
    WebRTCGateway,
    BrowserNodeBridge,
    DistributedWebRTCNetwork
)

from .relay_transparent import (
    RelayMode,
    RelayConfig,
    RelayEndpoint,
    NATTraversalEngine,
    RelayTransparentManager,
    TransparentRelayServer,
    StealthRelayNetwork
)


class P2PNetworkBootstrapEngine:
    """
    P2P网络自举引擎 - 统一入口

    整合4层架构的所有组件，提供统一的API
    """

    def __init__(
        self,
        node_id: str,
        node_url: str,
        role: NodeRole = NodeRole.PEER
    ):
        # 节点信息
        self.node_id = node_id
        self.node_url = node_url
        self.role = role

        # Phase 1: 节点发现
        self.discovery_service: Optional[NodeDiscoveryService] = None
        self.topology_push: Optional[TopologyPushService] = None
        self.bootstrap_protocol: Optional[BootstrapProtocol] = None

        # Phase 2: 连接池
        self.connection_pool: Optional[ConnectionPool] = None
        self.qos_router: Optional[QoSRouter] = None
        self.topology_manager: Optional[AdaptiveTopologyManager] = None

        # Phase 3: Gossip协议
        self.gossip_protocol: Optional[GossipProtocol] = None
        self.reverse_recommendation: Optional[ReverseRecommendationEngine] = None
        self.self_healing: Optional[SelfHealingManager] = None

        # Phase 4: WebRTC
        self.webrtc_network: Optional[DistributedWebRTCNetwork] = None
        self.browser_bridge: Optional[BrowserNodeBridge] = None

        # 中继透明化
        self.relay_network: Optional[StealthRelayNetwork] = None

        # 状态
        self.is_initialized = False
        self.is_running = False

        # 回调
        self.on_node_discovered: Optional[callable] = None
        self.on_connection_established: Optional[callable] = None
        self.on_connection_lost: Optional[callable] = None
        self.on_network_changed: Optional[callable] = None

    async def initialize(self, bootstrap_nodes: List[str] = None):
        """
        初始化P2P网络自举引擎

        bootstrap_nodes: 初始引导节点列表
        """
        if self.is_initialized:
            return

        # ========== Phase 1: 节点发现服务 ==========
        self.discovery_service = NodeDiscoveryService(
            node_id=self.node_id,
            url=self.node_url,
            role=self.role
        )

        self.topology_push = TopologyPushService(self.discovery_service)

        self.bootstrap_protocol = BootstrapProtocol()
        if bootstrap_nodes:
            for node in bootstrap_nodes:
                self.bootstrap_protocol.add_bootstrap_node(node)

        # 设置发现回调
        self.discovery_service.on_node_discovered = self._handle_node_discovered
        self.discovery_service.on_node_lost = self._handle_node_lost

        # ========== Phase 2: 连接池 ==========
        self.connection_pool = ConnectionPool(
            client_id=self.node_id,
            min_connections=2,
            max_connections=5
        )

        self.connection_pool.node_registry = self.discovery_service.registry
        self.connection_pool.on_connection_established = self._handle_connection_established
        self.connection_pool.on_connection_lost = self._handle_connection_lost
        self.connection_pool.on_failover = self._handle_failover

        self.qos_router = QoSRouter(self.connection_pool)
        self.topology_manager = AdaptiveTopologyManager(
            self.connection_pool,
            self.discovery_service.registry
        )

        # ========== Phase 3: Gossip协议 ==========
        self.gossip_protocol = GossipProtocol(
            node_id=self.node_id,
            fanout=3,
            gossip_interval=5,
            ttl=3
        )

        self.gossip_protocol.on_network_changed = self._handle_network_changed

        self.reverse_recommendation = ReverseRecommendationEngine(self.gossip_protocol)

        self.self_healing = SelfHealingManager(
            self.gossip_protocol,
            self.connection_pool,
            self.discovery_service.registry
        )

        # ========== Phase 4: WebRTC网络 ==========
        webrtc_network_id = hashlib.sha256(
            self.node_id.encode()
        ).hexdigest()[:8]

        self.webrtc_network = DistributedWebRTCNetwork(webrtc_network_id)

        # ========== 中继透明化 ==========
        self.relay_network = StealthRelayNetwork(
            f"relay_network_{self.node_id[:8]}"
        )

        self.is_initialized = True

    async def start(self):
        """
        启动引擎

        开始所有后台服务和循环
        """
        if not self.is_initialized:
            await self.initialize()

        self.is_running = True

        # 启动各组件
        await self.topology_push.start()
        await self.connection_pool.start()
        await self.gossip_protocol.start()
        await self.self_healing.start()

        # 启动WebRTC网络
        await self.webrtc_network.initialize(self)

        # 启动中继网络
        await self.relay_network.initialize(self)

        # 执行初始节点发现
        await self._bootstrap_initial_nodes()

    async def stop(self):
        """停止引擎"""
        self.is_running = False

        # 停止各组件
        await self.topology_push.stop()
        await self.connection_pool.stop()
        await self.gossip_protocol.stop()
        await self.self_healing.stop()

    async def _bootstrap_initial_nodes(self):
        """
        引导初始节点发现

        通过引导节点获取初始拓扑
        """
        if not self.bootstrap_protocol:
            return

        nodes = await self.bootstrap_protocol.discover_initial_nodes()

        for node in nodes:
            # 添加到连接池
            await self.connection_pool.add_node({
                "node_id": node.node_id,
                "url": node.url
            })

            # 添加到Gossip对等体
            self.gossip_protocol.add_peer(node.node_id, node.url)

            # 通知发现
            if self.on_node_discovered:
                await self.on_node_discovered(node)

    async def connect_to_network(self, target_node_url: str = None) -> bool:
        """
        连接到P2P网络

        如果没有指定目标，使用引导节点
        """
        if target_node_url:
            # 直接连接到指定节点
            topology = await self.discovery_service.handle_topology_request(
                self.node_id
            )

            # 添加到连接池
            await self.connection_pool.add_node({
                "node_id": topology.nodes[0].node_id if topology.nodes else "",
                "url": target_node_url
            })

            return True

        # 使用引导协议发现节点
        await self._bootstrap_initial_nodes()
        return True

    async def handle_topology_request(self, client_id: str) -> NetworkTopology:
        """处理拓扑请求（作为服务器）"""
        return await self.discovery_service.handle_topology_request(client_id)

    async def announce_node(self, node_info: Dict):
        """广播新节点"""
        await self.gossip_protocol.announce_node_up(node_info)

    async def announce_webrtc_gateway(self, gateway_id: str):
        """广播WebRTC网关"""
        event = GossipEvent(
            event_type=GossipEventType.NODE_ANNOUNCE,
            node_id=gateway_id,
            timestamp=datetime.now(),
            data={
                "type": "webrtc_gateway",
                "gateway_id": gateway_id
            }
        )
        await self.gossip_protocol.broadcast_event(event)

    def get_network_status(self) -> Dict:
        """
        获取网络状态

        返回各层架构的状态信息
        """
        return {
            "node_id": self.node_id,
            "role": self.role.value,
            "is_running": self.is_running,

            # Phase 1: 节点发现
            "phase1_discovery": {
                "total_known_nodes": len(self.discovery_service.registry.nodes) if self.discovery_service else 0,
                "alive_nodes": len([n for n in self.discovery_service.registry.nodes.values() if n.status == NodeStatus.ALIVE]) if self.discovery_service else 0
            },

            # Phase 2: 连接池
            "phase2_connection_pool": self.connection_pool.get_pool_status() if self.connection_pool else {},

            # Phase 3: Gossip
            "phase3_gossip": self.gossip_protocol.get_network_health() if self.gossip_protocol else {},

            # Phase 4: WebRTC
            "phase4_webrtc": self.webrtc_network.get_network_topology() if self.webrtc_network else {},

            # 中继透明化
            "relay_transparent": self.relay_network.get_network_stats() if self.relay_network else {}
        }

    def get_topology(self) -> Dict:
        """获取网络拓扑"""
        if self.discovery_service:
            topology = self.discovery_service.registry.get_topology()
            return topology.to_dict()

        return {}

    # ========== 回调处理 ==========

    async def _handle_node_discovered(self, node: NodeInfo):
        """处理节点发现"""
        if self.on_node_discovered:
            await self.on_node_discovered(node)

    async def _handle_node_lost(self, node_id: str):
        """处理节点丢失"""
        if self.on_connection_lost:
            await self.on_connection_lost(node_id)

    async def _handle_connection_established(self, connection: Connection):
        """处理连接建立"""
        # 注册到反向推荐引擎
        if self.reverse_recommendation:
            asyncio.create_task(
                self.reverse_recommendation.register_client_nodes(
                    connection.node_id,
                    [self.node_id]
                )
            )

        if self.on_connection_established:
            await self.on_connection_established(connection)

    async def _handle_connection_lost(self, node_id: str):
        """处理连接丢失"""
        if self.on_connection_lost:
            await self.on_connection_lost(node_id)

    async def _handle_failover(self, new_primary: Connection):
        """处理故障转移"""
        if self.on_network_changed:
            await self.on_network_changed({
                "type": "failover",
                "new_primary": new_primary.node_id
            })

    async def _handle_network_changed(self, event: Any):
        """处理网络变更"""
        if self.on_network_changed:
            await self.on_network_changed(event)


class P2PClientNode:
    """
    P2P客户端节点

    用于连接到P2P网络的客户端
    """

    def __init__(self, client_id: str):
        self.client_id = client_id

        # 创建引擎
        self.engine: Optional[P2PNetworkBootstrapEngine] = None

        # 连接状态
        self.is_connected = False

    async def connect(
        self,
        bootstrap_url: str = None,
        bootstrap_nodes: List[str] = None
    ):
        """
        连接到P2P网络
        """
        # 创建客户端节点ID
        node_id = f"client_{self.client_id}"
        node_url = f"client://{self.client_id}"

        # 创建引擎
        self.engine = P2PNetworkBootstrapEngine(
            node_id=node_id,
            node_url=node_url,
            role=NodeRole.PEER
        )

        # 设置回调
        self.engine.on_node_discovered = self._on_node_discovered
        self.engine.on_connection_established = self._on_connected
        self.engine.on_connection_lost = self._on_disconnected

        # 初始化
        await self.engine.initialize(bootstrap_nodes)

        # 启动
        await self.engine.start()

        # 连接到网络
        await self.engine.connect_to_network(bootstrap_url)

        self.is_connected = True

    async def disconnect(self):
        """断开连接"""
        if self.engine:
            await self.engine.stop()
            self.engine = None
        self.is_connected = False

    def get_status(self) -> Dict:
        """获取状态"""
        if self.engine:
            return self.engine.get_network_status()
        return {"connected": False}

    async def _on_node_discovered(self, node: NodeInfo):
        """节点发现回调"""
        pass

    async def _on_connected(self, connection: Connection):
        """连接建立回调"""
        pass

    async def _on_disconnected(self, node_id: str):
        """连接断开回调"""
        pass


# 导出所有组件
__all__ = [
    # Phase 1
    "NodeRole",
    "NodeStatus",
    "NodeInfo",
    "NetworkTopology",
    "NodeRegistry",
    "NodeDiscoveryService",
    "TopologyPushService",
    "BootstrapProtocol",

    # Phase 2
    "ConnectionStatus",
    "ConnectionQuality",
    "ConnectionMetrics",
    "Connection",
    "ConnectionPool",
    "QoSRouter",
    "AdaptiveTopologyManager",

    # Phase 3
    "GossipEventType",
    "GossipEvent",
    "PeerState",
    "GossipProtocol",
    "ReverseRecommendationEngine",
    "SelfHealingManager",

    # Phase 4
    "WebRTCState",
    "SignalingMessage",
    "WebRTCPeerConnection",
    "SignalingServer",
    "WebRTCGateway",
    "BrowserNodeBridge",
    "DistributedWebRTCNetwork",

    # 中继透明化
    "RelayMode",
    "RelayConfig",
    "RelayEndpoint",
    "NATTraversalEngine",
    "RelayTransparentManager",
    "TransparentRelayServer",
    "StealthRelayNetwork",

    # 统一引擎
    "P2PNetworkBootstrapEngine",
    "P2PClientNode"
]
