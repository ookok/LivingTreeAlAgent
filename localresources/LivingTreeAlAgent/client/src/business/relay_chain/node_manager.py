"""
节点管理器 - Node Manager

负责：
1. 节点注册与发现
2. 心跳保活
3. 节点状态跟踪
4. 可用节点列表维护

架构设计：
- Registry（注册中心）：核心节点，部署在南京
- Relay（中继）：普通节点，可动态加入退出
"""

import time
import threading
import hashlib
import socket
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
import json


class NodeType(Enum):
    """节点类型"""
    REGISTRY = "registry"  # 注册中心
    CORE = "core"          # 核心中继（南京/上海/杭州）
    EDGE = "edge"          # 边缘中继（全国分布）


class NodeState(Enum):
    """节点状态"""
    ONLINE = "online"      # 在线
    OFFLINE = "offline"    # 离线
    SUSPECT = "suspect"    # 可能离线（未收到心跳）
    MAINTENANCE = "maintenance"  # 维护中


@dataclass
class RelayNode:
    """中继节点"""
    relay_id: str
    node_type: NodeType = NodeType.EDGE
    host: str = ""
    port: int = 8080
    region: str = "unknown"  # 地区
    state: NodeState = NodeState.ONLINE

    # 健康状态
    last_heartbeat: float = field(default_factory=time.time)
    heartbeat_interval: float = 30.0  # 心跳间隔（秒）
    consecutive_failures: int = 0

    # 能力标签
    capabilities: Set[str] = field(default_factory=set)  # write/read/sync

    # 负载
    current_load: int = 0  # 当前连接数
    max_load: int = 100    # 最大连接数

    def is_healthy(self) -> bool:
        """检查节点是否健康"""
        if self.state != NodeState.ONLINE:
            return False
        if time.time() - self.last_heartbeat > self.heartbeat_interval * 3:
            return False
        return True

    def is_overloaded(self) -> bool:
        """检查是否过载"""
        return self.current_load >= self.max_load

    def update_heartbeat(self):
        """更新心跳"""
        self.last_heartbeat = time.time()
        self.consecutive_failures = 0
        if self.state != NodeState.ONLINE:
            self.state = NodeState.ONLINE

    def get_address(self) -> str:
        """获取节点地址"""
        return f"{self.host}:{self.port}"


class Registry:
    """
    注册中心

    功能：
    1. 管理所有中继节点的注册
    2. 维护节点心跳
    3. 提供节点发现服务
    4. 负载均衡

    注意：注册中心本身不是中继，它只负责元数据管理
    """

    def __init__(self, registry_id: str = "registry_nanjing"):
        self.registry_id = registry_id
        self.nodes: Dict[str, RelayNode] = {}  # relay_id -> RelayNode
        self._lock = threading.RLock()

        # 统计
        self.total_registrations = 0
        self.started_at = time.time()

    def register_node(
        self,
        relay_id: str,
        host: str,
        port: int,
        node_type: NodeType = NodeType.EDGE,
        region: str = "unknown",
        capabilities: Set[str] = None
    ) -> Tuple[bool, str]:
        """
        注册节点

        Returns:
            (success, message)
        """
        with self._lock:
            if relay_id in self.nodes:
                # 更新现有节点
                node = self.nodes[relay_id]
                node.host = host
                node.port = port
                node.node_type = node_type
                node.region = region
                if capabilities:
                    node.capabilities = capabilities
                node.update_heartbeat()
                return True, "节点已更新"

            # 创建新节点
            node = RelayNode(
                relay_id=relay_id,
                node_type=node_type,
                host=host,
                port=port,
                region=region,
                capabilities=capabilities or {"read", "write", "sync"}
            )
            self.nodes[relay_id] = node
            self.total_registrations += 1

            return True, f"节点已注册: {relay_id}"

    def unregister_node(self, relay_id: str) -> bool:
        """注销节点"""
        with self._lock:
            if relay_id in self.nodes:
                del self.nodes[relay_id]
                return True
            return False

    def heartbeat(self, relay_id: str) -> Tuple[bool, str]:
        """
        处理节点心跳

        Returns:
            (success, message)
        """
        with self._lock:
            if relay_id not in self.nodes:
                return False, "节点未注册"

            node = self.nodes[relay_id]
            node.update_heartbeat()
            return True, "心跳已接收"

    def get_node(self, relay_id: str) -> Optional[RelayNode]:
        """获取节点信息"""
        return self.nodes.get(relay_id)

    def get_all_nodes(
        self,
        node_type: NodeType = None,
        state: NodeState = None,
        capabilities: Set[str] = None
    ) -> List[RelayNode]:
        """
        获取节点列表（可过滤）

        Args:
            node_type: 节点类型过滤
            state: 状态过滤
            capabilities: 必须包含的能力

        Returns:
            符合条件的节点列表
        """
        with self._lock:
            result = []

            for node in self.nodes.values():
                # 类型过滤
                if node_type and node.node_type != node_type:
                    continue

                # 状态过滤
                if state and node.state != state:
                    continue

                # 能力过滤
                if capabilities and not capabilities.issubset(node.capabilities):
                    continue

                result.append(node)

            return result

    def get_healthy_nodes(
        self,
        capabilities: Set[str] = None,
        prefer_types: List[NodeType] = None
    ) -> List[RelayNode]:
        """
        获取健康的可用节点

        优先返回：
        1. 核心节点 > 边缘节点
        2. 低负载 > 高负载
        3. 本地节点 > 远程节点
        """
        nodes = self.get_all_nodes(state=NodeState.ONLINE)

        # 过滤健康且未过载
        nodes = [n for n in nodes if n.is_healthy() and not n.is_overloaded()]

        # 能力过滤
        if capabilities:
            nodes = [n for n in nodes if capabilities.issubset(n.capabilities)]

        # 按优先级排序
        def priority(node: RelayNode) -> Tuple[int, int, float]:
            # (节点类型优先级, 负载, 距离权重)
            type_priority = 0 if node.node_type == NodeType.CORE else 1
            return (type_priority, node.current_load, node.last_heartbeat)

        nodes.sort(key=priority)

        return nodes

    def get_least_loaded_node(self, capabilities: Set[str] = None) -> Optional[RelayNode]:
        """获取负载最低的节点"""
        nodes = self.get_healthy_nodes(capabilities=capabilities)
        if not nodes:
            return None
        return min(nodes, key=lambda n: n.current_load)

    def check_health(self) -> Dict:
        """健康检查"""
        with self._lock:
            now = time.time()
            healthy = 0
            unhealthy = 0

            for node in self.nodes.values():
                if node.is_healthy():
                    healthy += 1
                else:
                    unhealthy += 1

                # 超时节点标记为离线
                if now - node.last_heartbeat > node.heartbeat_interval * 5:
                    node.state = NodeState.OFFLINE

            return {
                "total_nodes": len(self.nodes),
                "healthy": healthy,
                "unhealthy": unhealthy,
                "uptime_seconds": now - self.started_at,
                "total_registrations": self.total_registrations,
                "by_type": {
                    "core": len([n for n in self.nodes.values() if n.node_type == NodeType.CORE]),
                    "edge": len([n for n in self.nodes.values() if n.node_type == NodeType.EDGE]),
                }
            }

    def export_nodes(self) -> List[Dict]:
        """导出节点列表（用于同步）"""
        with self._lock:
            return [
                {
                    "relay_id": n.relay_id,
                    "node_type": n.node_type.value,
                    "host": n.host,
                    "port": n.port,
                    "region": n.region,
                    "state": n.state.value,
                    "last_heartbeat": n.last_heartbeat,
                    "capabilities": list(n.capabilities)
                }
                for n in self.nodes.values()
            ]

    def import_nodes(self, nodes_data: List[Dict]) -> int:
        """
        导入节点列表（从其他注册中心同步）

        Returns:
            导入的节点数量
        """
        count = 0
        for data in nodes_data:
            node = RelayNode(
                relay_id=data["relay_id"],
                node_type=NodeType(data.get("node_type", "edge")),
                host=data.get("host", ""),
                port=data.get("port", 8080),
                region=data.get("region", "unknown"),
                state=NodeState(data.get("state", "online")),
                last_heartbeat=data.get("last_heartbeat", time.time()),
                capabilities=set(data.get("capabilities", ["read", "write", "sync"]))
            )
            self.nodes[node.relay_id] = node
            count += 1

        return count


class NodeManager:
    """
    节点管理器（供中继节点使用）

    功能：
    1. 向注册中心注册自己
    2. 维护心跳
    3. 获取其他节点信息
    4. 处理节点发现
    """

    def __init__(
        self,
        relay_id: str,
        registry_host: str = "127.0.0.1",
        registry_port: int = 8081
    ):
        self.relay_id = relay_id
        self.registry_host = registry_host
        self.registry_port = registry_port

        # 本地缓存的节点信息
        self.cached_nodes: Dict[str, RelayNode] = {}

        # 心跳线程
        self._heartbeat_thread: threading.Thread = None
        self._running = False

    def start(self):
        """启动节点管理器"""
        self._running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def stop(self):
        """停止节点管理器"""
        self._running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)

    def _heartbeat_loop(self):
        """心跳循环"""
        while self._running:
            try:
                self._send_heartbeat()
            except Exception as e:
                print(f"Heartbeat failed: {e}")

            time.sleep(30)  # 30秒心跳

    def _send_heartbeat(self):
        """发送心跳到注册中心"""
        # 这里应该使用实际的RPC调用
        # 简化实现：仅记录时间
        pass

    def register_to_registry(
        self,
        host: str,
        port: int,
        node_type: NodeType = NodeType.EDGE,
        region: str = "unknown"
    ) -> Tuple[bool, str]:
        """
        向注册中心注册

        Returns:
            (success, message)
        """
        # 实际应该调用注册中心的RPC接口
        # 简化：返回成功
        return True, "注册成功"

    def discover_nodes(
        self,
        capabilities: Set[str] = None
    ) -> List[RelayNode]:
        """
        发现可用节点

        Returns:
            可用节点列表
        """
        # 实际应该查询注册中心
        # 简化：返回本地缓存
        return list(self.cached_nodes.values())

    def get_best_node(self, capability: str = "write") -> Optional[RelayNode]:
        """
        获取最佳节点（用于写入）

        Returns:
            最佳节点
        """
        nodes = self.discover_nodes(capabilities={capability})
        if not nodes:
            return None
        return min(nodes, key=lambda n: n.current_load)