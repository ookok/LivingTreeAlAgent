"""
分层穿透网络
Layered Relay Network for DeCommerce

架构:
┌─────────────────────────────────────────────────────────────┐
│                    Super Relay (你的Windows云)                │
│  - 商品目录/身份/小额支付结算/关键穿透兜底                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  Edge Relay   │  │  Edge Relay   │  │  Edge Relay   │
│ (大卖家节点1)  │  │ (大卖家节点2)  │  │ (边缘节点)     │
│  公网IP自建    │  │  公网IP自建    │  │  有公网IP      │
└───────────────┘  └───────────────┘  └───────────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
┌──────────────────────────────────────────────────────────────┐
│                     Buyer Clients                             │
│              (通过最优路径连接到Seller)                         │
└──────────────────────────────────────────────────────────────┘

特性:
1. 分层路由: 云目录 → 边缘节点 → 卖家
2. 负载分担: 减轻Windows云服务器压力
3. 就近接入: 买家连接最近的边缘节点
4. 网状互联: 边缘节点之间可互相转发
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import time
import uuid
import json

logger = logging.getLogger(__name__)


class RelayNodeType(Enum):
    """中继节点类型"""
    SUPER = "super"           # 超级中继 (Windows云)
    EDGE = "edge"             # 边缘中继 (大卖家/专业节点)
    BACKUP = "backup"         # 备用中继


class RelayStatus(Enum):
    """中继状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"     # 降级 (负载高/延迟高)
    MAINTENANCE = "maintenance"


@dataclass
class RelayNode:
    """中继节点信息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    node_type: RelayNodeType = RelayNodeType.EDGE

    # 位置信息
    region: str = "default"   # 区域/机房
    country: str = "CN"
    city: str = ""

    # 网络信息
    host: str = ""
    port: int = 3478
    public_ip: Optional[str] = None

    # TURN配置
    turn_username: Optional[str] = None
    turn_credential: Optional[str] = None

    # 能力
    max_connections: int = 1000
    current_connections: int = 0
    bandwidth_mbps: int = 100

    # 健康状态
    status: RelayStatus = RelayStatus.ONLINE
    latency_ms: int = 0       # 到该节点的延迟
    quality_score: float = 100.0  # 质量评分 (0-100)

    # 统计
    total_relayed_bytes: int = 0
    total_sessions: int = 0
    uptime_seconds: int = 0

    # 心跳
    last_heartbeat: float = field(default_factory=time.time)
    registration_time: float = field(default_factory=time.time)

    def is_healthy(self) -> bool:
        """节点是否健康"""
        return (
            self.status == RelayStatus.ONLINE and
            time.time() - self.last_heartbeat < 30 and
            self.quality_score >= 60
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type.value,
            "region": self.region,
            "country": self.country,
            "city": self.city,
            "host": self.host,
            "port": self.port,
            "public_ip": self.public_ip,
            "turn_username": self.turn_username,
            "max_connections": self.max_connections,
            "current_connections": self.current_connections,
            "bandwidth_mbps": self.bandwidth_mbps,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "quality_score": self.quality_score,
            "total_relayed_bytes": self.total_relayed_bytes,
            "total_sessions": self.total_sessions,
            "uptime_seconds": int(time.time() - self.registration_time),
        }


class EdgeRelayNetwork:
    """
    分层穿透网络管理器

    功能:
    - 管理超级中继和边缘中继节点
    - 提供最优穿透路径路由
    - 负载均衡和故障转移
    - 流量统计和监控
    """

    _instance: Optional["EdgeRelayNetwork"] = None

    @classmethod
    def get_instance(cls) -> "EdgeRelayNetwork":
        if cls._instance is None:
            cls._instance = EdgeRelayNetwork()
        return cls._instance

    def __init__(self):
        # 节点注册表 node_id -> RelayNode
        self._nodes: Dict[str, RelayNode] = {}

        # 区域索引 region -> [node_id]
        self._region_index: Dict[str, List[str]] = {}

        # 超级中继 (单例, Windows云)
        self._super_relay: Optional[RelayNode] = None

        # 连接会话 session_id -> {buyer_id, seller_id, relay_node_id, ...}
        self._sessions: Dict[str, Dict[str, Any]] = {}

        # 回调
        self._on_session_start: List[Callable] = []
        self._on_session_end: List[Callable] = []

        # 统计
        self._stats = {
            "total_sessions": 0,
            "total_bytes_relayed": 0,
            "active_sessions": 0,
        }

    # ==================== 节点管理 ====================

    def register_super_relay(
        self,
        host: str,
        port: int = 3478,
        turn_username: Optional[str] = None,
        turn_credential: Optional[str] = None,
        **kwargs
    ) -> RelayNode:
        """注册超级中继 (Windows云)"""
        node = RelayNode(
            id="super_relay",
            node_type=RelayNodeType.SUPER,
            host=host,
            port=port,
            public_ip=kwargs.get("public_ip", host),
            turn_username=turn_username,
            turn_credential=turn_credential,
            max_connections=kwargs.get("max_connections", 5000),
            bandwidth_mbps=kwargs.get("bandwidth_mbps", 1000),
            region="cloud",
        )
        self._super_relay = node
        self._nodes[node.id] = node
        logger.info(f"[EdgeRelay] Registered Super Relay at {host}:{port}")
        return node

    def register_edge_relay(
        self,
        host: str,
        port: int = 3478,
        region: str = "default",
        turn_username: Optional[str] = None,
        turn_credential: Optional[str] = None,
        **kwargs
    ) -> RelayNode:
        """注册边缘中继节点"""
        node = RelayNode(
            node_type=RelayNodeType.EDGE,
            host=host,
            port=port,
            public_ip=kwargs.get("public_ip", host),
            turn_username=turn_username,
            turn_credential=turn_credential,
            max_connections=kwargs.get("max_connections", 500),
            bandwidth_mbps=kwargs.get("bandwidth_mbps", 100),
            region=region,
            country=kwargs.get("country", "CN"),
            city=kwargs.get("city", ""),
        )

        self._nodes[node.id] = node

        # 更新区域索引
        if region not in self._region_index:
            self._region_index[region] = []
        self._region_index[region].append(node.id)

        logger.info(f"[EdgeRelay] Registered Edge Relay {node.id} at {host}:{port}")
        return node

    def unregister_node(self, node_id: str) -> bool:
        """注销节点"""
        if node_id in self._nodes:
            node = self._nodes[node_id]
            # 从区域索引移除
            if node.region in self._region_index:
                self._region_index[node.region].remove(node_id)
            del self._nodes[node_id]
            logger.info(f"[EdgeRelay] Unregistered node {node_id}")
            return True
        return False

    def update_node_heartbeat(self, node_id: str, latency_ms: int = 0) -> bool:
        """更新节点心跳"""
        node = self._nodes.get(node_id)
        if not node:
            return False

        node.last_heartbeat = time.time()
        node.latency_ms = latency_ms

        # 根据延迟更新质量评分
        if latency_ms < 50:
            node.quality_score = 100
        elif latency_ms < 100:
            node.quality_score = 90
        elif latency_ms < 200:
            node.quality_score = 80
        elif latency_ms < 500:
            node.quality_score = 70
        else:
            node.quality_score = 60

        return True

    def update_node_status(self, node_id: str, status: RelayStatus) -> bool:
        """更新节点状态"""
        node = self._nodes.get(node_id)
        if not node:
            return False
        node.status = status
        return True

    # ==================== 路由 ====================

    def get_best_relay(
        self,
        buyer_region: str = "default",
        seller_region: str = "default",
        require_quality: float = 60.0,
    ) -> Optional[RelayNode]:
        """
        获取最优中继节点

        策略:
        1. 优先选择区域匹配的边缘节点
        2. 其次选择距离买卖双方都较近的节点
        3. 最后选择超级中继兜底
        """
        candidates = []

        # 1. 先收集边缘节点
        region_nodes = self._region_index.get(buyer_region, [])
        for node_id in region_nodes:
            node = self._nodes.get(node_id)
            if node and node.is_healthy() and node.quality_score >= require_quality:
                # 计算综合评分: 质量 * (1 - 负载率) * 区域匹配度
                load_factor = 1 - (node.current_connections / node.max_connections)
                region_bonus = 1.2 if buyer_region == node.region else 1.0
                score = node.quality_score * load_factor * region_bonus
                candidates.append((score, node))

        # 2. 如果没有匹配的区域节点，找最近的
        if not candidates:
            for node in self._nodes.values():
                if node.node_type == RelayNodeType.EDGE and node.is_healthy():
                    candidates.append((node.quality_score * 0.8, node))

        # 3. 按评分排序
        candidates.sort(key=lambda x: x[0], reverse=True)

        # 4. 选择最优节点
        if candidates:
            return candidates[0][1]

        # 5. 最后兜底: 超级中继
        if self._super_relay and self._super_relay.is_healthy():
            return self._super_relay

        return None

    def get_relay_chain(
        self,
        buyer_region: str,
        seller_region: str,
    ) -> List[RelayNode]:
        """
        获取完整的穿透链路

        返回: [buyer_side_relay, ..., seller_side_relay]
        可能经过多个边缘节点
        """
        chain = []

        # 买家侧中继
        buyer_relay = self.get_best_relay(buyer_region, "any")
        if buyer_relay:
            chain.append(buyer_relay)

        # 如果买卖不在同一区域，可能需要中间节点
        if buyer_region != seller_region:
            # 找一个中间节点
            mid_relay = self.get_best_relay("middle", seller_region)
            if mid_relay and mid_relay.id not in [n.id for n in chain]:
                chain.append(mid_relay)

        # 卖家侧中继 (如果有边缘节点在卖家区域)
        seller_relays = [
            self._nodes[nid]
            for nid in self._region_index.get(seller_region, [])
            if self._nodes[nid].is_healthy()
        ]
        if seller_relays:
            chain.append(seller_relays[0])

        return chain

    def get_ice_config_for_relay(
        self,
        relay_node: RelayNode,
        buyer_id: str,
    ) -> Dict[str, Any]:
        """
        获取指定中继的ICE配置

        Returns:
            ICE服务器配置字典
        """
        ice_servers = []

        # 添加STUN
        ice_servers.append({"urls": f"stun:{relay_node.host}:{relay_node.port}"})

        # 添加TURN (如果配置了凭证)
        if relay_node.turn_username and relay_node.turn_credential:
            ice_servers.append({
                "urls": f"turn:{relay_node.host}:{relay_node.port}",
                "username": relay_node.turn_username,
                "credential": relay_node.turn_credential,
            })

        return {
            "iceServers": ice_servers,
            "iceTransportPolicy": "relay",  # 优先relay保证连通性
        }

    # ==================== 会话管理 ====================

    def create_session(
        self,
        session_id: str,
        buyer_id: str,
        seller_id: str,
        relay_node: RelayNode,
    ) -> Dict[str, Any]:
        """创建穿透会话"""
        session = {
            "id": session_id,
            "buyer_id": buyer_id,
            "seller_id": seller_id,
            "relay_node_id": relay_node.id,
            "created_at": time.time(),
            "last_activity": time.time(),
            "bytes_relayed": 0,
            "status": "active",
        }

        self._sessions[session_id] = session

        # 更新节点连接数
        relay_node.current_connections += 1
        relay_node.total_sessions += 1

        # 更新统计
        self._stats["total_sessions"] += 1
        self._stats["active_sessions"] = len(self._sessions)

        logger.info(f"[EdgeRelay] Created session {session_id} via relay {relay_node.id}")

        # 触发回调
        for cb in self._on_session_start:
            try:
                cb(session)
            except Exception as e:
                logger.error(f"[EdgeRelay] Session start callback error: {e}")

        return session

    def update_session_activity(self, session_id: str, bytes_relayed: int = 0) -> bool:
        """更新会话活跃状态"""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session["last_activity"] = time.time()
        session["bytes_relayed"] += bytes_relayed

        # 更新节点统计
        relay_node = self._nodes.get(session.get("relay_node_id"))
        if relay_node:
            relay_node.total_relayed_bytes += bytes_relayed

        self._stats["total_bytes_relayed"] += bytes_relayed

        return True

    def end_session(self, session_id: str) -> bool:
        """结束穿透会话"""
        session = self._sessions.get(session_id)
        if not session:
            return False

        # 更新节点连接数
        relay_node = self._nodes.get(session.get("relay_node_id"))
        if relay_node:
            relay_node.current_connections = max(0, relay_node.current_connections - 1)

        # 从会话表移除
        del self._sessions[session_id]

        # 更新统计
        self._stats["active_sessions"] = len(self._sessions)

        logger.info(f"[EdgeRelay] Ended session {session_id}")

        # 触发回调
        for cb in self._on_session_end:
            try:
                cb(session)
            except Exception as e:
                logger.error(f"[EdgeRelay] Session end callback error: {e}")

        return True

    # ==================== 统计与监控 ====================

    def get_network_stats(self) -> Dict[str, Any]:
        """获取网络统计"""
        healthy_nodes = sum(1 for n in self._nodes.values() if n.is_healthy())
        total_capacity = sum(n.max_connections for n in self._nodes.values())
        total_used = sum(n.current_connections for n in self._nodes.values())

        return {
            "total_nodes": len(self._nodes),
            "healthy_nodes": healthy_nodes,
            "super_relay": self._super_relay.to_dict() if self._super_relay else None,
            "edge_relays": [
                n.to_dict() for n in self._nodes.values()
                if n.node_type == RelayNodeType.EDGE
            ],
            "total_capacity": total_capacity,
            "total_used": total_used,
            "utilization_percent": (total_used / total_capacity * 100) if total_capacity > 0 else 0,
            "total_sessions": self._stats["total_sessions"],
            "active_sessions": self._stats["active_sessions"],
            "total_bytes_relayed": self._stats["total_bytes_relayed"],
        }

    def get_node_health_report(self) -> List[Dict[str, Any]]:
        """获取所有节点健康报告"""
        return [n.to_dict() for n in self._nodes.values()]

    # ==================== 回调 ====================

    def on_session_start(self, callback: Callable) -> None:
        """监听会话开始"""
        self._on_session_start.append(callback)

    def on_session_end(self, callback: Callable) -> None:
        """监听会话结束"""
        self._on_session_end.append(callback)


# 全局单例访问函数
_edge_relay_network: Optional[EdgeRelayNetwork] = None


def get_edge_relay_network() -> EdgeRelayNetwork:
    """获取分层穿透网络单例"""
    global _edge_relay_network
    if _edge_relay_network is None:
        _edge_relay_network = EdgeRelayNetwork()
    return _edge_relay_network


def init_edge_relay_network(
    super_relay_host: str,
    super_relay_port: int = 3478,
    turn_username: Optional[str] = None,
    turn_credential: Optional[str] = None,
) -> EdgeRelayNetwork:
    """初始化分层穿透网络"""
    global _edge_relay_network
    _edge_relay_network = EdgeRelayNetwork()
    _edge_relay_network.register_super_relay(
        host=super_relay_host,
        port=super_relay_port,
        turn_username=turn_username,
        turn_credential=turn_credential,
    )
    return _edge_relay_network
