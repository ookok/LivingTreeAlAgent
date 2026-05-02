"""
企业节点管理器
Enterprise Node Manager

管理企业内的P2P节点，负责节点发现、资源分配和负载均衡
"""

from __future__ import annotations



import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field

from livingtree.core.p2p_cdn import CDNNode, NodeCapability

logger = logging.getLogger(__name__)


@dataclass
class EnterpriseNode:
    """企业节点模型"""
    node_id: str
    name: str
    ip: str
    port: int
    capability: NodeCapability
    role: str  # master, worker, storage
    status: str  # online, offline, maintenance
    last_seen: float = field(default_factory=time.time)
    storage_allocated: int = 0  # 已分配存储空间
    storage_used: int = 0  # 已使用存储空间
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "ip": self.ip,
            "port": self.port,
            "capability": self.capability.to_dict(),
            "role": self.role,
            "status": self.status,
            "last_seen": self.last_seen,
            "storage_allocated": self.storage_allocated,
            "storage_used": self.storage_used,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EnterpriseNode:
        """从字典创建"""
        return cls(
            node_id=data.get("node_id"),
            name=data.get("name"),
            ip=data.get("ip"),
            port=data.get("port"),
            capability=NodeCapability.from_dict(data.get("capability", {})),
            role=data.get("role", "worker"),
            status=data.get("status", "offline"),
            last_seen=data.get("last_seen", time.time()),
            storage_allocated=data.get("storage_allocated", 0),
            storage_used=data.get("storage_used", 0),
            tags=data.get("tags", [])
        )


class EnterpriseNodeManager:
    """企业节点管理器"""

    def __init__(self, enterprise_id: str):
        self.enterprise_id = enterprise_id
        self.nodes: Dict[str, EnterpriseNode] = {}
        self.master_node: Optional[str] = None
        self.heartbeat_interval = 30  # 心跳间隔（秒）
        self.node_timeout = 90  # 节点超时时间（秒）
        self._heartbeat_task: Optional[asyncio.Task] = None
        self.is_running = False

    async def start(self):
        """启动节点管理器"""
        logger.info(f"Starting Enterprise Node Manager for {self.enterprise_id}...")
        self.is_running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"Enterprise Node Manager started")

    async def stop(self):
        """停止节点管理器"""
        logger.info(f"Stopping Enterprise Node Manager for {self.enterprise_id}...")
        self.is_running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Enterprise Node Manager stopped")

    async def _heartbeat_loop(self):
        """心跳循环"""
        while self.is_running:
            try:
                # 检查节点状态
                await self._check_node_status()
                # 平衡资源分配
                await self._balance_resources()
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(self.heartbeat_interval)

    async def _check_node_status(self):
        """检查节点状态"""
        current_time = time.time()
        offline_nodes = []

        for node_id, node in self.nodes.items():
            if current_time - node.last_seen > self.node_timeout:
                node.status = "offline"
                offline_nodes.append(node_id)
                logger.warning(f"Node {node_id} marked as offline")

        # 处理离线节点
        if offline_nodes and self.master_node in offline_nodes:
            await self._elect_new_master()

    async def _elect_new_master(self):
        """选举新的主节点"""
        # 选择最适合的节点作为主节点
        candidates = [
            node for node in self.nodes.values()
            if node.status == "online" and node.role != "storage"
        ]

        if candidates:
            # 按能力排序
            candidates.sort(key=lambda x: (
                -x.capability.storage_available,
                -x.capability.bandwidth,
                -x.capability.uptime
            ))
            new_master = candidates[0]
            self.master_node = new_master.node_id
            new_master.role = "master"
            logger.info(f"New master node elected: {new_master.node_id}")
        else:
            logger.warning("No suitable node for master election")

    async def _balance_resources(self):
        """平衡资源分配"""
        # 计算总存储空间和已使用空间
        total_storage = sum(node.capability.storage_available for node in self.nodes.values() if node.status == "online")
        total_used = sum(node.storage_used for node in self.nodes.values() if node.status == "online")

        if total_storage > 0:
            usage_ratio = total_used / total_storage
            logger.info(f"Storage usage ratio: {usage_ratio:.2f}")

            # 检查是否需要重新分配资源
            if usage_ratio > 0.8:
                logger.warning("Storage usage above 80%, consider adding more nodes")

    def add_node(self, node: EnterpriseNode):
        """添加节点"""
        self.nodes[node.node_id] = node
        logger.info(f"Node added: {node.node_id} ({node.name})")

        # 如果是第一个节点，设为主节点
        if not self.master_node:
            self.master_node = node.node_id
            node.role = "master"
            logger.info(f"Node {node.node_id} set as master")

    def remove_node(self, node_id: str):
        """移除节点"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            logger.info(f"Node removed: {node_id}")

            # 如果移除的是主节点，重新选举
            if node_id == self.master_node:
                asyncio.create_task(self._elect_new_master())

    def get_node(self, node_id: str) -> Optional[EnterpriseNode]:
        """获取节点"""
        return self.nodes.get(node_id)

    def get_nodes(self, status: Optional[str] = None, role: Optional[str] = None) -> List[EnterpriseNode]:
        """获取节点列表"""
        nodes = list(self.nodes.values())

        if status:
            nodes = [node for node in nodes if node.status == status]

        if role:
            nodes = [node for node in nodes if node.role == role]

        return nodes

    def update_node_status(self, node_id: str, status: str):
        """更新节点状态"""
        if node_id in self.nodes:
            self.nodes[node_id].status = status
            self.nodes[node_id].last_seen = time.time()
            logger.info(f"Node {node_id} status updated to {status}")

    def allocate_storage(self, node_id: str, size: int) -> bool:
        """分配存储空间"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            if node.capability.storage_available >= size:
                node.storage_allocated += size
                node.capability.storage_available -= size
                return True
        return False

    def release_storage(self, node_id: str, size: int):
        """释放存储空间"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.storage_allocated -= size
            node.capability.storage_available += size

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        online_nodes = [node for node in self.nodes.values() if node.status == "online"]
        offline_nodes = [node for node in self.nodes.values() if node.status == "offline"]

        total_storage = sum(node.capability.storage_available + node.storage_allocated for node in self.nodes.values())
        used_storage = sum(node.storage_used for node in self.nodes.values())

        return {
            "enterprise_id": self.enterprise_id,
            "total_nodes": len(self.nodes),
            "online_nodes": len(online_nodes),
            "offline_nodes": len(offline_nodes),
            "master_node": self.master_node,
            "total_storage": total_storage,
            "used_storage": used_storage,
            "storage_usage": used_storage / total_storage if total_storage > 0 else 0
        }


# 单例管理
enterprise_managers: Dict[str, EnterpriseNodeManager] = {}


def get_enterprise_manager(enterprise_id: str) -> EnterpriseNodeManager:
    """获取企业节点管理器"""
    if enterprise_id not in enterprise_managers:
        enterprise_managers[enterprise_id] = EnterpriseNodeManager(enterprise_id)
    return enterprise_managers[enterprise_id]


def list_enterprises() -> List[str]:
    """列出所有企业"""
    return list(enterprise_managers.keys())
