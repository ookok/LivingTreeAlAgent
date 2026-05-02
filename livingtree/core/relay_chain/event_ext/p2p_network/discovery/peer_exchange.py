"""
节点信息交换协议 - Peer Exchange

核心功能：
1. 节点间互相交换已知的节点列表
2. 加速网络发现
3. 维护网络连通性

工作原理：
- 当节点 A 发现节点 B 时，A 会把自己的节点列表发送给 B
- B 收到后，会尝试连接 A 列表中的所有节点
- 这样可以实现快速的网络扩张
"""

import json
import time
import logging
from typing import Dict, Any, List, Set, Optional
from dataclasses import dataclass, field
from threading import RLock

logger = logging.getLogger(__name__)


@dataclass
class PeerInfo:
    """节点信息"""
    node_id: str
    endpoint: str  # "ip:port"
    capabilities: List[str] = field(default_factory=list)
    load: float = 0.0
    last_seen: float = field(default_factory=time.time)
    connected: bool = False


class PeerExchange:
    """
    节点信息交换

    机制：
    1. 本地维护已知节点列表
    2. 节点连接时互相交换列表
    3. 尝试连接新发现的节点

    使用示例：
    ```python
    exchange = PeerExchange(node_id="node-001")

    # 设置连接回调
    exchange.on_new_peer = lambda endpoint: connect_to(endpoint)

    # 添加已知节点
    exchange.add_peer(node_id="node-002", endpoint="192.168.1.10:8080")

    # 请求交换
    exchange.request_exchange(peer_endpoint)

    # 获取所有已知节点
    peers = exchange.get_all_peers()
    ```
    """

    # 节点信息过期时间（秒）
    PEER_EXPIRY = 120.0

    # 最大保存的节点数
    MAX_PEERS = 100

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._lock = RLock()

        # 节点信息表
        self._peers: Dict[str, PeerInfo] = {}

        # 连接状态
        self._connected: Set[str] = set()

        # 回调
        self.on_new_peer: Optional[callable] = None
        self.on_peer_lost: Optional[callable] = None
        self.on_peer_updated: Optional[callable] = None

    def add_peer(
        self,
        node_id: str,
        endpoint: str,
        capabilities: List[str] = None,
        load: float = 0.0,
        connected: bool = False,
    ):
        """
        添加已知节点

        Args:
            node_id: 节点ID
            endpoint: 节点地址
            capabilities: 节点能力列表
            load: 节点负载
            connected: 是否已连接
        """
        with self._lock:
            if node_id == self.node_id:
                return

            if node_id in self._peers:
                # 更新
                peer = self._peers[node_id]
                peer.endpoint = endpoint
                peer.load = load
                peer.last_seen = time.time()
                if connected:
                    peer.connected = True
                    self._connected.add(node_id)
            else:
                # 新增
                peer = PeerInfo(
                    node_id=node_id,
                    endpoint=endpoint,
                    capabilities=capabilities or [],
                    load=load,
                    connected=connected,
                )
                self._peers[node_id] = peer
                if connected:
                    self._connected.add(node_id)

                logger.info(f"[{self.node_id}] 新节点: {node_id} @ {endpoint}")

                if self.on_new_peer:
                    self.on_new_peer(endpoint)

    def update_peer(self, node_id: str, **kwargs):
        """更新节点信息"""
        with self._lock:
            if node_id in self._peers:
                peer = self._peers[node_id]
                for key, value in kwargs.items():
                    if hasattr(peer, key):
                        setattr(peer, key, value)
                peer.last_seen = time.time()

                if self.on_peer_updated:
                    self.on_peer_updated(node_id)

    def remove_peer(self, node_id: str):
        """移除节点"""
        with self._lock:
            if node_id in self._peers:
                del self._peers[node_id]
                self._connected.discard(node_id)

                logger.info(f"[{self.node_id}] 节点移除: {node_id}")

                if self.on_peer_lost:
                    self.on_peer_lost(node_id)

    def mark_connected(self, node_id: str, connected: bool = True):
        """标记节点连接状态"""
        with self._lock:
            if node_id in self._peers:
                self._peers[node_id].connected = connected
                if connected:
                    self._connected.add(node_id)
                else:
                    self._connected.discard(node_id)

    def get_peer(self, node_id: str) -> Optional[PeerInfo]:
        """获取节点信息"""
        with self._lock:
            return self._peers.get(node_id)

    def get_all_peers(self) -> List[PeerInfo]:
        """获取所有节点"""
        with self._lock:
            return list(self._peers.values())

    def get_connected_peers(self) -> List[PeerInfo]:
        """获取已连接的节点"""
        with self._lock:
            return [
                peer for peer in self._peers.values()
                if peer.connected
            ]

    def get_best_peer(self, capability: str = None) -> Optional[PeerInfo]:
        """
        获取最佳节点（负载最低）

        Args:
            capability: 需要的 capability

        Returns:
            最佳节点
        """
        connected = self.get_connected_peers()

        if not connected:
            return None

        if capability:
            candidates = [
                p for p in connected
                if capability in p.capabilities
            ]
            if not candidates:
                candidates = connected
        else:
            candidates = connected

        return min(candidates, key=lambda p: p.load)

    def create_exchange_message(self) -> Dict[str, Any]:
        """
        创建节点交换消息

        Returns:
            包含本节点已知所有节点的消息
        """
        with self._lock:
            peers_data = []
            for peer in self._peers.values():
                peers_data.append({
                    "node_id": peer.node_id,
                    "endpoint": peer.endpoint,
                    "capabilities": peer.capabilities,
                    "load": peer.load,
                })

            return {
                "type": "PEER_EXCHANGE",
                "node_id": self.node_id,
                "peers": peers_data,
                "timestamp": time.time(),
            }

    def handle_exchange_message(self, msg: Dict[str, Any]):
        """
        处理节点交换消息

        Args:
            msg: PEER_EXCHANGE 消息
        """
        from_node_id = msg.get("node_id")

        if from_node_id == self.node_id:
            return

        peers_data = msg.get("peers", [])

        logger.info(
            f"[{self.node_id}] 收到节点交换: {from_node_id}, "
            f"包含 {len(peers_data)} 个节点"
        )

        # 添加所有节点
        for peer_data in peers_data:
            self.add_peer(
                node_id=peer_data["node_id"],
                endpoint=peer_data["endpoint"],
                capabilities=peer_data.get("capabilities", []),
                load=peer_data.get("load", 0.0),
                connected=False,  # 还没连接
            )

    def cleanup_expired(self):
        """清理过期的节点"""
        now = time.time()
        expired = []

        with self._lock:
            for node_id, peer in self._peers.items():
                if now - peer.last_seen > self.PEER_EXPIRY:
                    expired.append(node_id)

            for node_id in expired:
                del self._peers[node_id]
                self._connected.discard(node_id)

        if expired:
            logger.info(f"[{self.node_id}] 清理过期节点: {len(expired)}")

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        with self._lock:
            return {
                "node_id": self.node_id,
                "total_peers": len(self._peers),
                "connected_peers": len(self._connected),
                "peers": [
                    {
                        "node_id": p.node_id,
                        "endpoint": p.endpoint,
                        "connected": p.connected,
                        "load": p.load,
                        "last_seen": p.last_seen,
                    }
                    for p in self._peers.values()
                ],
            }
