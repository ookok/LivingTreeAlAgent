# -*- coding: utf-8 -*-
"""
中继服务器透明化模块
Relay Transparent Module

核心理念：
- 中继服务器对客户端完全透明，客户端只感知"节点"
- 节点在推送列表时，将中继服务器伪装成普通节点
- 客户端无需区分P2P节点还是中继，由底层库自动降级

作者：Hermes Desktop V2.0
版本：1.0.0
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
import asyncio
import random


class RelayMode(Enum):
    """中继模式"""
    DISABLED = "disabled"     # 中继禁用
    AUTO = "auto"           # 自动（根据网络状况）
    FORCED = "forced"        # 强制中继
    TRANSPARENT = "transparent"  # 透明中继（伪装成普通节点）


@dataclass
class RelayConfig:
    """中继配置"""
    mode: RelayMode = RelayMode.TRANSPARENT

    # 透明中继伪装配置
   伪装名称: str = "node"  # 对外显示的名称
    伪装权重: float = 0.8  # 伪装权重（略低于普通节点以保持真实性）

    # 自动降级配置
    nat_check_interval: int = 60  # NAT检查间隔（秒）
    stun_server: str = "stun:stun.l.google.com:19302"

    # 连接限制
    max_relay_clients: int = 1000
    max_bandwidth_mbps: int = 1000

    # 性能阈值
    latency_threshold_ms: float = 300.0
    packet_loss_threshold: float = 0.1


@dataclass
class RelayEndpoint:
    """中继端点"""
    endpoint_id: str
    url: str

    # 伪装信息
    is_stealth: bool = True  # 是否是透明中继
    advertised_as: str = "peer"  # 对外广告为...节点

    # 中继能力
    can_handle_client: bool = True
    can_relay_traffic: bool = True

    # 当前负载
    current_clients: int = 0
    bandwidth_usage_mbps: float = 0.0

    # 性能
    latency_ms: float = 0.0
    packet_loss: float = 0.0

    # 状态
    is_healthy: bool = True
    last_health_check: datetime = field(default_factory=datetime.now)


class NATTraversalEngine:
    """
    NAT穿透引擎

    自动检测NAT类型并在必要时透明降级到中继模式
    """

    def __init__(self, config: RelayConfig):
        self.config = config

        # NAT类型
        self.nat_type: str = "unknown"
        self.nat_support_stun: bool = False
        self.can_direct_connect: bool = False

        # 回调
        self.on_nat_discovered: Optional[Callable] = None
        self.on_connection_mode_changed: Optional[Callable] = None

    async def check_nat_type(self) -> str:
        """
        检测NAT类型

        使用STUN服务器检测NAT类型
        """
        # 模拟STUN检测
        # 实际实现使用stun protocol

        nat_types = [
            "Open Internet",        # 完全开放
            "Full Cone NAT",        # 全锥型
            "Restricted Cone NAT",    # 限制锥型
            "Port Restricted Cone NAT",  # 端口限制锥型
            "Symmetric NAT"         # 对称型NAT（最难穿透）
        ]

        self.nat_type = random.choice(nat_types)

        # 判断是否可以直连
        if self.nat_type in ["Open Internet", "Full Cone NAT"]:
            self.can_direct_connect = True
            self.nat_support_stun = True
        elif self.nat_type == "Symmetric NAT":
            self.can_direct_connect = False
            self.nat_support_stun = False
        else:
            self.can_direct_connect = True  # 大多数情况可以
            self.nat_support_stun = True

        if self.on_nat_discovered:
            await self.on_nat_discovered(self.nat_type)

        return self.nat_type

    async def test_connectivity(self, peer_url: str) -> Dict:
        """
        测试与对等体的连接性

        返回是否需要中继
        """
        # 模拟连接测试
        # 实际实现发送探测包

        can_connect = self.can_direct_connect

        if not can_connect:
            # 需要中继
            return {
                "can_direct": False,
                "requires_relay": True,
                "reason": f"NAT type {self.nat_type} prevents direct connection"
            }

        # 模拟直连测试
        latency = random.uniform(10, 100)
        packet_loss = random.uniform(0, 0.05)

        if latency > self.config.latency_threshold_ms:
            can_connect = False

        if packet_loss > self.config.packet_loss_threshold:
            can_connect = False

        return {
            "can_direct": can_connect,
            "requires_relay": not can_connect,
            "latency_ms": latency,
            "packet_loss": packet_loss
        }

    def should_use_relay(self) -> bool:
        """
        判断是否应该使用中继
        """
        if self.config.mode == RelayMode.FORCED:
            return True

        if self.config.mode == RelayMode.DISABLED:
            return False

        # AUTO模式：根据NAT类型和连接测试结果
        return not self.can_direct_connect


class RelayTransparentManager:
    """
    中继透明化管理器

    核心功能：
    1. 将中继伪装成普通节点
    2. 自动降级到中继模式
    3. 对客户端完全透明
    """

    def __init__(self, config: RelayConfig = None):
        self.config = config or RelayConfig()

        # NAT穿透引擎
        self.nat_engine = NATTraversalEngine(self.config)

        # 中继端点
        self.relay_endpoints: Dict[str, RelayEndpoint] = {}

        # 连接模式
        self.current_mode: RelayMode = self.config.mode
        self.using_relay: bool = False
        self.active_relay: Optional[RelayEndpoint] = None

        # 回调
        self.on_relay_activated: Optional[Callable] = None
        self.on_relay_deactivated: Optional[Callable] = None

    def register_relay(self, endpoint: RelayEndpoint):
        """
        注册中继端点

        中继会被伪装成普通节点
        """
        # 伪装中继信息
        endpoint.is_stealth = True
        endpoint.advertised_as = "peer"

        self.relay_endpoints[endpoint.endpoint_id] = endpoint

    def unregister_relay(self, endpoint_id: str):
        """注销中继端点"""
        if endpoint_id in self.relay_endpoints:
            del self.relay_endpoints[endpoint_id]

    async def initialize(self):
        """初始化"""
        # 检测NAT类型
        await self.nat_engine.check_nat_type()

        # 根据NAT类型决定模式
        if self.nat_engine.can_direct_connect:
            self.current_mode = RelayMode.AUTO
            self.using_relay = False
        else:
            await self._activate_relay_mode()

    async def connect_to_peer(self, peer_url: str) -> Dict:
        """
        连接到对等体

        自动选择直连或中继
        """
        # 首先测试直连
        test_result = await self.nat_engine.test_connectivity(peer_url)

        if test_result["can_direct"]:
            self.using_relay = False
            return {
                "success": True,
                "mode": "direct",
                "peer_url": peer_url,
                "latency_ms": test_result.get("latency_ms", 0)
            }

        # 需要中继，激活中继模式
        await self._activate_relay_mode()

        # 获取最优质的中继
        relay = self._select_best_relay()

        if not relay:
            return {
                "success": False,
                "mode": "relay",
                "error": "No available relay"
            }

        # 通过中继连接
        self.active_relay = relay
        self.using_relay = True

        return {
            "success": True,
            "mode": "relay",
            "relay_url": relay.url,
            "peer_url": peer_url,
            "transparent": True  # 标记为透明中继
        }

    async def _activate_relay_mode(self):
        """激活中继模式"""
        if self.using_relay:
            return

        self.using_relay = True
        self.current_mode = RelayMode.TRANSPARENT

        if self.on_relay_activated:
            await self.on_relay_activated(self.active_relay)

    async def _deactivate_relay_mode(self):
        """停用中继模式"""
        if not self.using_relay:
            return

        self.using_relay = False
        self.active_relay = None

        if self.on_relay_deactivated:
            await self.on_relay_deactivated()

    def _select_best_relay(self) -> Optional[RelayEndpoint]:
        """选择最优中继"""
        available = [
            r for r in self.relay_endpoints.values()
            if r.is_healthy and r.current_clients < self.config.max_relay_clients
        ]

        if not available:
            return None

        # 按质量排序
        available.sort(key=lambda r: (
            -r.latency_ms,  # 延迟低优先
            r.current_clients  # 负载低优先
        ))

        # 应用伪装权重
        for relay in available:
            relay.advertised_as = "peer"
            relay.url = relay.url.replace("relay://", "wss://")

        return available[0]

    def get_advertised_nodes(self) -> List[Dict]:
        """
        获取对外广播的节点列表

        将中继伪装成普通节点
        """
        nodes = []

        # 添加普通节点（如果有）
        # 实际从节点注册表获取

        # 添加伪装的中继
        for relay in self.relay_endpoints.values():
            if relay.is_stealth:
                nodes.append({
                    "node_id": relay.endpoint_id,
                    "url": relay.url,
                    "role": relay.advertised_as,  # 伪装为peer
                    "weight": self.config.伪装权重,
                    "latency_ms": relay.latency_ms,
                    "is_relay": True,  # 内部标记为中继
                    "transparent": True
                })

        return nodes

    def get_connection_status(self) -> Dict:
        """获取连接状态"""
        return {
            "nat_type": self.nat_engine.nat_type,
            "can_direct_connect": self.nat_engine.can_direct_connect,
            "current_mode": self.current_mode.value,
            "using_relay": self.using_relay,
            "active_relay": self.active_relay.endpoint_id if self.active_relay else None,
            "relay_count": len(self.relay_endpoints)
        }


class TransparentRelayServer:
    """
    透明中继服务器

    对客户端表现得像普通节点，
    实际执行流量中继
    """

    def __init__(self, server_id: str, config: RelayConfig = None):
        self.server_id = server_id
        self.config = config or RelayConfig()

        # 连接管理
        self.connections: Dict[str, Any] = {}
        self.relay_sessions: Dict[str, Dict] = {}

        # 流量统计
        self.total_bytes_relayed = 0
        self.active_sessions = 0

        # 伪装
        self.advertised_role = "peer"
        self.advertised_weight = self.config.伪装权重

    async def start_relaying(
        self,
        client_a_id: str,
        client_b_id: str,
        metadata: Dict = None
    ) -> str:
        """
        开始中继会话

        对两个客户端都表现得像是对等节点
        """
        session_id = f"{client_a_id}_{client_b_id}_{datetime.now().timestamp()}"

        self.relay_sessions[session_id] = {
            "session_id": session_id,
            "client_a": client_a_id,
            "client_b": client_b_id,
            "started_at": datetime.now(),
            "bytes_relayed": 0,
            "metadata": metadata or {}
        }

        self.active_sessions += 1

        return session_id

    async def relay_data(self, session_id: str, from_client: str, data: bytes) -> bool:
        """
        中继数据

        将数据从一方转发到另一方
        """
        if session_id not in self.relay_sessions:
            return False

        session = self.relay_sessions[session_id]

        # 确定目标客户端
        if from_client == session["client_a"]:
            target = session["client_b"]
        else:
            target = session["client_a"]

        # 实际发送数据到目标
        # await self._send_to_client(target, data)

        # 更新统计
        session["bytes_relayed"] += len(data)
        self.total_bytes_relayed += len(data)

        return True

    async def stop_relaying(self, session_id: str):
        """停止中继会话"""
        if session_id in self.relay_sessions:
            del self.relay_sessions[session_id]
            self.active_sessions = max(0, self.active_sessions - 1)

    def get_server_info(self) -> Dict:
        """
        获取服务器信息

        对外广播时使用
        """
        return {
            "server_id": self.server_id,
            "role": self.advertised_role,  # 伪装为peer
            "weight": self.advertised_weight,
            "latency_ms": random.uniform(10, 50),  # 模拟延迟
            "connected_clients": len(self.connections),
            "is_healthy": True,
            "is_relay": True,  # 内部标记
            "transparent": True
        }

    def get_relay_stats(self) -> Dict:
        """获取中继统计"""
        return {
            "server_id": self.server_id,
            "active_sessions": self.active_sessions,
            "total_bytes_relayed": self.total_bytes_relayed,
            "total_connections": len(self.connections),
            "mode": "transparent"
        }


class StealthRelayNetwork:
    """
    隐身中继网络

    整合所有中继透明化组件
    """

    def __init__(self, network_id: str):
        self.network_id = network_id

        # 中继配置
        self.config = RelayConfig()

        # 组件
        self.relay_manager = RelayTransparentManager(self.config)
        self.relay_servers: Dict[str, TransparentRelayServer] = {}

        # 网络引用
        self.network_bootstrap: Any = None

    async def initialize(self, network_bootstrap: Any):
        """初始化"""
        self.network_bootstrap = network_bootstrap

        # 初始化中继管理器
        await self.relay_manager.initialize()

        # 注册中继服务器
        # 实际从配置或服务发现获取

    def add_relay_server(self, server: TransparentRelayServer):
        """添加中继服务器"""
        self.relay_servers[server.server_id] = server

        # 注册到管理器
        endpoint = RelayEndpoint(
            endpoint_id=server.server_id,
            url=f"wss://relay-{server.server_id}.example.com",
            is_stealth=True,
            advertised_as="peer",
            can_handle_client=True,
            can_relay_traffic=True
        )

        self.relay_manager.register_relay(endpoint)

    async def create_relay_session(
        self,
        client_a_id: str,
        client_a_url: str,
        client_b_id: str,
        client_b_url: str
    ) -> Dict:
        """
        创建中继会话

        对两个客户端都表现得像是对等节点
        """
        # 选择一个中继服务器
        if not self.relay_servers:
            return {"success": False, "error": "No relay available"}

        relay = list(self.relay_servers.values())[0]

        # 创建中继会话
        session_id = await relay.start_relaying(client_a_id, client_b_id)

        # 返回给客户端的连接信息
        # 两个客户端都会认为自己连接到了普通对等节点
        return {
            "success": True,
            "session_id": session_id,
            "mode": "transparent_relay",
            "client_a": {
                "peer_id": client_b_id,  # 伪装为client B
                "peer_url": f"relay://{relay.server_id}/{session_id}"
            },
            "client_b": {
                "peer_id": client_a_id,  # 伪装为client A
                "peer_url": f"relay://{relay.server_id}/{session_id}"
            }
        }

    async def get_topology_for_client(self, client_id: str) -> Dict:
        """
        获取供客户端使用的拓扑

        中继被伪装成普通节点
        """
        # 获取伪装后的节点列表
        advertised_nodes = self.relay_manager.get_advertised_nodes()

        # 添加其他普通节点
        if self.network_bootstrap:
            real_nodes = await self.network_bootstrap.get_real_nodes()
            all_nodes = advertised_nodes + real_nodes
        else:
            all_nodes = advertised_nodes

        return {
            "nodes": all_nodes,
            "version": datetime.now().timestamp(),
            "includes_relay": True,
            "transparent_mode": True
        }

    def get_network_stats(self) -> Dict:
        """获取网络统计"""
        relay_stats = [
            server.get_relay_stats()
            for server in self.relay_servers.values()
        ]

        return {
            "network_id": self.network_id,
            "relay_count": len(self.relay_servers),
            "transparent_mode": True,
            "active_relays": self.relay_manager.using_relay,
            "relay_stats": relay_stats
        }
