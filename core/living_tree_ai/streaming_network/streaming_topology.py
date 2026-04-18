"""
Streaming Topology - 树状+网状混合拓扑
=====================================

功能：
- 自适应树状拓扑
- 节点发现与选择
- 拓扑健康监控
- 自动重连与修复

Author: LivingTreeAI Community
"""

import asyncio
import time
import random
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any, List, Set, Dict
from enum import Enum
from collections import defaultdict


class TopologyType(Enum):
    """拓扑类型"""
    TREE = "tree"        # 纯树状
    MESH = "mesh"        # 纯网状
    HYBRID = "hybrid"    # 混合


@dataclass
class TreeNode:
    """树节点"""
    node_id: str
    parent: Optional[str] = None
    children: Set[str] = field(default_factory=set)
    depth: int = 0
    latency_ms: float = 0
    bandwidth_kbps: int = 0
    last_heartbeat: float = field(default_factory=time.time)
    is_stable: bool = False


class MeshNode:
    """网状节点"""
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.neighbors: Set[str] = set()
        self.connections: Dict[str, float] = {}  # neighbor -> latency
        self.last_update: float = time.time()


class StreamingTopology:
    """
    流媒体分发拓扑管理

    功能：
    1. 树状拓扑构建
    2. 网状拓扑维护
    3. 自适应拓扑切换
    4. 节点健康监控
    """

    # 配置
    MAX_CHILDREN = 3
    MAX_DEPTH = 4
    LATENCY_THRESHOLD_MS = 200
    STABILITY_WINDOW = 30  # 秒

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 拓扑类型
        self.topology_type = TopologyType.TREE

        # 树状结构
        self.tree: Dict[str, TreeNode] = {}
        self.parent: Optional[str] = None
        self.children: Set[str] = set()

        # 网状结构
        self.mesh_neighbors: Set[str] = set()

        # 网络函数
        self._send_func = send_func

        # 回调
        self._on_topology_change: Optional[Callable] = None
        self._on_parent_change: Optional[Callable] = None

        # 初始化根节点
        self.tree[node_id] = TreeNode(node_id=node_id, depth=0)

    # ========== 树状拓扑 ==========

    async def join_tree(
        self,
        stream_id: str,
        root_node: str,
    ) -> bool:
        """
        加入直播树

        Args:
            stream_id: 流ID
            root_node: 根节点ID

        Returns:
            是否成功加入
        """
        # 查找最优父节点
        parent = await self.find_optimal_parent(stream_id, root_node)
        if not parent:
            return False

        # 请求加入
        if await self.request_join(parent, stream_id):
            self.parent = parent
            node = self.tree.get(self.node_id)
            if node:
                node.parent = parent

            # 更新父节点
            if parent in self.tree:
                self.tree[parent].children.add(self.node_id)

            # 回调
            if self._on_parent_change:
                await self._on_parent_change(parent)

            return True

        return False

    async def find_optimal_parent(
        self,
        stream_id: str,
        root_node: str,
    ) -> Optional[str]:
        """查找最优父节点"""
        # 发现树中所有节点
        candidates = await self.discover_tree_nodes(stream_id, root_node)

        if not candidates:
            return root_node

        # 评分排序
        scored = []
        for node_id in candidates:
            if node_id == self.node_id:
                continue

            node = self.tree.get(node_id)
            if not node:
                continue

            score = await self._score_node(node)
            scored.append((score, node_id))

        scored.sort(reverse=True)

        # 选择最优节点
        for score, node_id in scored:
            if await self.request_join(node_id, stream_id):
                return node_id

        return None

    async def _score_node(self, node: TreeNode) -> float:
        """评分节点"""
        score = 0.0

        # 延迟分数（越低越好）
        if node.latency_ms > 0:
            score += 1000.0 / (node.latency_ms + 1)

        # 带宽分数（越高越好）
        score += node.bandwidth_kbps / 100

        # 子节点数分数（子节点少更好，说明负载轻）
        child_penalty = len(node.children) * 0.5
        score -= child_penalty

        # 深度分数（越浅越好，但不能是根）
        if node.depth > 0:
            score += (self.MAX_DEPTH - node.depth) * 0.3

        # 稳定性分数
        if node.is_stable:
            score += 0.5

        # 随机扰动（避免总是选择同一个）
        score += random.random() * 0.1

        return score

    async def discover_tree_nodes(
        self,
        stream_id: str,
        root_node: str,
    ) -> List[str]:
        """发现树中节点"""
        # 简化：使用泛洪发现
        discovered = set()
        to_visit = [root_node]
        visited = set()

        while to_visit and len(discovered) < 20:
            node_id = to_visit.pop(0)
            if node_id in visited:
                continue

            visited.add(node_id)
            discovered.add(node_id)

            # 获取邻居（简化实现）
            neighbors = await self._get_tree_children(node_id)
            to_visit.extend(neighbors)

        return list(discovered - {self.node_id})

    async def _get_tree_children(self, node_id: str) -> List[str]:
        """获取树节点子节点"""
        node = self.tree.get(node_id)
        if node:
            return list(node.children)
        return []

    async def request_join(self, parent_id: str, stream_id: str) -> bool:
        """请求加入"""
        if not self._send_func:
            return True

        try:
            response = await self._send_func(parent_id, {
                "type": "join_request",
                "stream_id": stream_id,
                "node_id": self.node_id,
            })
            return response.get("accepted", False)
        except Exception:
            return False

    async def leave_tree(self):
        """离开树"""
        if self.parent:
            # 通知父节点
            if self._send_func:
                await self._send_func(self.parent, {
                    "type": "leave_notify",
                    "node_id": self.node_id,
                })

            # 更新树结构
            if self.parent in self.tree:
                self.tree[self.parent].children.discard(self.node_id)

            # 重新连接子节点
            for child_id in list(self.children):
                await self.reconnect_child(child_id)

        self.parent = None
        node = self.tree.get(self.node_id)
        if node:
            node.parent = None

    async def reconnect_child(self, child_id: str):
        """重新连接子节点"""
        # 找到新的父节点
        new_parent = await self.find_optimal_parent(None, None)
        if new_parent:
            self.tree[child_id].parent = new_parent

    # ========== 拓扑健康监控 ==========

    async def monitor_topology_health(self):
        """监控拓扑健康"""
        while True:
            await asyncio.sleep(5)

            # 检查父节点
            if self.parent:
                if not await self._check_parent_alive():
                    await self.reparent()

            # 检查负载均衡
            if len(self.children) > self.MAX_CHILDREN * 1.5:
                await self._redistribute_children()

            # 检查延迟
            avg_latency = await self._measure_average_latency()
            if avg_latency > self.LATENCY_THRESHOLD_MS:
                await self.switch_to_mesh()

            # 更新稳定性
            await self._update_stability()

    async def _check_parent_alive(self) -> bool:
        """检查父节点是否存活"""
        node = self.tree.get(self.parent) if self.parent else None
        if not node:
            return False

        # 检查心跳超时
        if time.time() - node.last_heartbeat > 30:
            return False

        return True

    async def reparent(self):
        """重新选择父节点"""
        old_parent = self.parent

        # 查找新父节点
        new_parent = await self.find_optimal_parent(None, None)

        if new_parent and new_parent != old_parent:
            # 离开旧父节点
            if old_parent in self.tree:
                self.tree[old_parent].children.discard(self.node_id)

            # 加入新父节点
            self.parent = new_parent
            node = self.tree.get(self.node_id)
            if node:
                node.parent = new_parent

            self.tree[new_parent].children.add(self.node_id)

            if self._on_parent_change:
                await self._on_parent_change(new_parent)

    async def _measure_average_latency(self) -> float:
        """测量平均延迟"""
        if not self.parent:
            return 0

        node = self.tree.get(self.parent)
        if node:
            return node.latency_ms
        return 0

    async def switch_to_mesh(self):
        """切换为网状拓扑"""
        self.topology_type = TopologyType.MESH

        # 与多个邻居建立连接
        neighbors = await self.discover_tree_nodes(None, None)
        for neighbor in neighbors[:5]:
            self.mesh_neighbors.add(neighbor)

        if self._on_topology_change:
            await self._on_topology_change(TopologyType.MESH)

    async def _redistribute_children(self):
        """重新分配子节点"""
        # 让部分子节点重新找父节点
        children_list = list(self.children)
        to_reassign = children_list[len(children_list) // 2:]

        for child_id in to_reassign:
            self.children.discard(child_id)
            await self.reconnect_child(child_id)

    async def _update_stability(self):
        """更新节点稳定性"""
        now = time.time()
        for node in self.tree.values():
            if now - node.last_heartbeat < self.STABILITY_WINDOW:
                node.is_stable = True
            else:
                node.is_stable = False

    # ========== 回调设置 ==========

    def set_topology_change_callback(self, callback: Callable):
        self._on_topology_change = callback

    def set_parent_change_callback(self, callback: Callable):
        self._on_parent_change = callback

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取拓扑统计"""
        return {
            "topology_type": self.topology_type.value,
            "parent": self.parent,
            "children": list(self.children),
            "child_count": len(self.children),
            "total_nodes": len(self.tree),
            "depth": self.tree.get(self.node_id).depth if self.node_id in self.tree else 0,
            "mesh_neighbors": list(self.mesh_neighbors),
        }


# 全局单例
_topology_instance: Optional[StreamingTopology] = None


def get_streaming_topology(node_id: str = "local") -> StreamingTopology:
    """获取流媒体拓扑单例"""
    global _topology_instance
    if _topology_instance is None:
        _topology_instance = StreamingTopology(node_id)
    return _topology_instance