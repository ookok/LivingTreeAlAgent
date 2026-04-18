"""
路由表 - Routing Table

实现类似于 BitTorrent DHT 的路由机制：
1. 节点维护邻居节点列表
2. 新节点加入时随机选择几个现有节点连接
3. 通过邻居学习整个网络拓扑

路由策略：
- 泛洪查找：广播查找请求
- 距离向量：基于节点 ID 的距离进行路由
"""

import time
import logging
from typing import Dict, Any, Optional, Set, List, Callable
from dataclasses import dataclass, field
from threading import RLock

logger = logging.getLogger(__name__)


@dataclass
class Route:
    """路由信息"""
    node_id: str
    endpoint: str  # "ip:port"
    distance: int = 0  # 到目标节点的跳数
    last_update: float = field(default_factory=time.time)
    next_hop: Optional[str] = None  # 下一跳节点ID


class RoutingTable:
    """
    路由表

    负责维护网络拓扑信息和路由计算。

    使用示例：
    ```python
    routing = RoutingTable(node_id="node-001")

    # 添加邻居
    routing.add_neighbor("node-002", "192.168.1.10:8080")
    routing.add_neighbor("node-003", "192.168.1.11:8080")

    # 查找路由
    route = routing.find_route("node-005")
    if route:
        print(f"到 node-005 的下一跳: {route.next_hop}")

    # 获取所有可达节点
    nodes = routing.get_reachable_nodes()
    ```
    """

    # 路由信息过期时间（秒）
    ROUTE_EXPIRY = 60.0

    # 最大邻居数
    MAX_NEIGHBORS = 50

    # 路由刷新间隔（秒）
    REFRESH_INTERVAL = 30.0

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._lock = RLock()

        # 路由表：node_id -> Route
        self._routes: Dict[str, Route] = {}

        # 邻居节点
        self._neighbors: Set[str] = set()

        # 回调
        self.on_route_discovered: Optional[Callable[[str, Route], None]] = None
        self.on_neighbor_added: Optional[Callable[[str], None]] = None
        self.on_neighbor_removed: Optional[Callable[[str], None]] = None

    def add_neighbor(self, node_id: str, endpoint: str):
        """
        添加邻居节点

        Args:
            node_id: 邻居节点ID
            endpoint: 邻居节点地址 "ip:port"
        """
        with self._lock:
            if node_id == self.node_id:
                return

            # 检查邻居数限制
            if len(self._neighbors) >= self.MAX_NEIGHBORS:
                # 移除最老的邻居
                self._evict_oldest_neighbor()

            route = Route(
                node_id=node_id,
                endpoint=endpoint,
                distance=1,  # 直接邻居，距离为1
                next_hop=node_id,  # 下一跳就是目标节点
            )

            self._routes[node_id] = route
            self._neighbors.add(node_id)

            logger.debug(f"[{self.node_id}] 添加邻居: {node_id} @ {endpoint}")

            if self.on_neighbor_added:
                self.on_neighbor_added(node_id)

    def remove_neighbor(self, node_id: str):
        """
        移除邻居节点

        Args:
            node_id: 邻居节点ID
        """
        with self._lock:
            if node_id in self._neighbors:
                self._neighbors.remove(node_id)
                # 不删除路由，标记为不可达
                if node_id in self._routes:
                    self._routes[node_id].distance = -1

                logger.info(f"[{self.node_id}] 移除邻居: {node_id}")

                if self.on_neighbor_removed:
                    self.on_neighbor_removed(node_id)

    def update_route(
        self,
        node_id: str,
        endpoint: str = None,
        distance: int = None,
        next_hop: str = None,
    ):
        """
        更新路由信息

        Args:
            node_id: 节点ID
            endpoint: 节点地址
            distance: 跳数
            next_hop: 下一跳
        """
        with self._lock:
            if node_id == self.node_id:
                return

            if node_id in self._routes:
                route = self._routes[node_id]
                if endpoint:
                    route.endpoint = endpoint
                if distance is not None and distance < route.distance:
                    route.distance = distance
                    route.next_hop = next_hop
                route.last_update = time.time()
            else:
                # 新路由
                self._routes[node_id] = Route(
                    node_id=node_id,
                    endpoint=endpoint or "",
                    distance=distance or 999,
                    next_hop=next_hop,
                )

                logger.debug(f"[{self.node_id}] 新路由: {node_id}, 距离={distance}")

    def find_route(self, target_id: str) -> Optional[Route]:
        """
        查找到目标节点的路由

        Args:
            target_id: 目标节点ID

        Returns:
            路由信息，如果不可达则返回 None
        """
        with self._lock:
            route = self._routes.get(target_id)

            if route and route.distance > 0:
                return route

            return None

    def get_next_hop(self, target_id: str) -> Optional[str]:
        """
        获取到目标节点的下一跳

        Args:
            target_id: 目标节点ID

        Returns:
            下一跳节点ID
        """
        route = self.find_route(target_id)
        return route.next_hop if route else None

    def get_all_neighbors(self) -> List[Route]:
        """获取所有邻居"""
        with self._lock:
            return [
                self._routes[n]
                for n in self._neighbors
                if n in self._routes
            ]

    def get_reachable_nodes(self) -> List[str]:
        """获取所有可达节点"""
        with self._lock:
            return [
                node_id
                for node_id, route in self._routes.items()
                if route.distance > 0
            ]

    def get_best_nodes(self, count: int = 5) -> List[Route]:
        """
        获取最近的节点（用于节点交换）

        Args:
            count: 返回数量

        Returns:
            最近的节点列表
        """
        with self._lock:
            routes = sorted(
                [r for r in self._routes.values() if r.distance > 0],
                key=lambda r: r.distance
            )
            return routes[:count]

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        with self._lock:
            return {
                "node_id": self.node_id,
                "total_routes": len(self._routes),
                "neighbors": len(self._neighbors),
                "reachable_nodes": self.get_reachable_nodes(),
                "routes": [
                    {
                        "node_id": r.node_id,
                        "endpoint": r.endpoint,
                        "distance": r.distance,
                        "next_hop": r.next_hop,
                        "last_update": r.last_update,
                    }
                    for r in self._routes.values()
                    if r.distance > 0
                ],
            }

    def _evict_oldest_neighbor(self):
        """驱逐最老的邻居"""
        oldest = None
        oldest_time = float("inf")

        for node_id in self._neighbors:
            route = self._routes.get(node_id)
            if route and route.last_update < oldest_time:
                oldest = node_id
                oldest_time = route.last_update

        if oldest:
            self.remove_neighbor(oldest)

    def cleanup_expired(self):
        """清理过期路由"""
        now = time.time()
        expired = []

        with self._lock:
            for node_id, route in self._routes.items():
                if now - route.last_update > self.ROUTE_EXPIRY:
                    expired.append(node_id)

            for node_id in expired:
                if node_id in self._neighbors:
                    self._neighbors.remove(node_id)
                del self._routes[node_id]

        if expired:
            logger.debug(f"[{self.node_id}] 清理过期路由: {len(expired)}")


class RoutingProtocol:
    """
    路由协议

    实现类似 DHT 的路由查找：
    1. ROUTING_REQUEST: 路由请求（查找节点）
    2. ROUTING_RESPONSE: 路由响应（返回找到的节点）
    3. ROUTING_UPDATE: 路由更新（周期性广播）
    """

    ROUTING_REQUEST = "ROUTING_REQUEST"
    ROUTING_RESPONSE = "ROUTING_RESPONSE"
    ROUTING_UPDATE = "ROUTING_UPDATE"

    def __init__(self, node_id: str, routing_table: RoutingTable):
        self.node_id = node_id
        self.routing_table = routing_table

    def create_routing_request(self, target_id: str) -> Dict[str, Any]:
        """创建路由请求"""
        return {
            "type": self.ROUTING_REQUEST,
            "from": self.node_id,
            "target": target_id,
            "known_nodes": [
                r.node_id for r in self.routing_table.get_best_nodes(5)
            ],
        }

    def handle_routing_request(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """处理路由请求"""
        target = msg.get("target")
        from_node = msg.get("from")

        # 检查是否有目标节点的路由
        route = self.routing_table.find_route(target)

        # 获取最近的节点列表
        best_nodes = self.routing_table.get_best_nodes(10)

        return {
            "type": self.ROUTING_RESPONSE,
            "from": self.node_id,
            "to": from_node,
            "target": target,
            "target_route": {
                "node_id": route.node_id,
                "endpoint": route.endpoint,
                "distance": route.distance,
            } if route else None,
            "nodes": [
                {"node_id": r.node_id, "endpoint": r.endpoint}
                for r in best_nodes
            ],
        }

    def handle_routing_response(self, msg: Dict[str, Any]):
        """处理路由响应"""
        target_route = msg.get("target_route")
        nodes = msg.get("nodes", [])

        # 更新到目标节点的路由
        if target_route:
            self.routing_table.update_route(
                target_route["node_id"],
                target_route["endpoint"],
                target_route["distance"],
            )

        # 添加响应中的节点
        for node in nodes:
            if node["node_id"] != self.node_id:
                self.routing_table.update_route(
                    node["node_id"],
                    node["endpoint"],
                    distance=999,  # 未知距离
                )

    def broadcast_routes(self) -> Dict[str, Any]:
        """广播本节点的路由信息"""
        return {
            "type": self.ROUTING_UPDATE,
            "from": self.node_id,
            "nodes": [
                {
                    "node_id": r.node_id,
                    "endpoint": r.endpoint,
                    "distance": r.distance,
                }
                for r in self.routing_table.get_best_nodes(20)
            ],
        }
