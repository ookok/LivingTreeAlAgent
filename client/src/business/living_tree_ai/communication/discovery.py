"""
NodeDiscovery - 混合节点发现机制
================================

支持：
1. 中心服务器查询
2. UDP组播发现（局域网）
3. mDNS/Zeroconf（跨平台）

Author: LivingTreeAI Community
from __future__ import annotations
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable
from datetime import datetime
import asyncio
import json
import struct
import socket
import logging
import sys

logger = logging.getLogger(__name__)


class DiscoveryType(Enum):
    """发现类型"""
    CENTRAL = "central"         # 中心服务器
    MULTICAST = "multicast"     # UDP组播
    ZEROCONF = "zeroconf"       # mDNS
    MANUAL = "manual"           # 手动添加


@dataclass
class DiscoveredNode:
    """发现的节点"""
    node_id: str
    ip: str
    port: int
    discovery_type: DiscoveryType
    timestamp: datetime = field(default_factory=datetime.now)
    latency_ms: float = 0
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "ip": self.ip,
            "port": self.port,
            "discovery_type": self.discovery_type.value,
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": self.latency_ms,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
        }


@dataclass
class DiscoveryResult:
    """发现结果"""
    nodes: List[DiscoveredNode] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    sources: List[str] = field(default_factory=list)

    def merge(self, other: "DiscoveryResult"):
        """合并另一个发现结果"""
        existing_ids = {n.node_id for n in self.nodes}
        for node in other.nodes:
            if node.node_id not in existing_ids:
                self.nodes.append(node)
                existing_ids.add(node.node_id)
        self.sources.extend(other.sources)

    def get_best_nodes(self, k: int = 5) -> List[DiscoveredNode]:
        """获取最优的k个节点（按延迟排序）"""
        sorted_nodes = sorted(self.nodes, key=lambda n: n.latency_ms)
        return sorted_nodes[:k]


class NodeDiscovery:
    """
    混合节点发现器

    同时执行多种发现机制：
    1. 中心服务器查询
    2. UDP组播（局域网）
    3. mDNS/Zeroconf（苹果生态）
    """

    MDNS_GROUP = "224.0.0.251"
    MDNS_PORT = 5353
    SERVICE_TYPE = "_lifetree._udp.local."

    def __init__(
        self,
        node_id: str,
        central_server: str = None,
        multicast_port: int = 19888,
    ):
        self.node_id = node_id
        self.central_server = central_server
        self.multicast_port = multicast_port
        self._nodes: Dict[str, DiscoveredNode] = {}
        self._listeners: List[Callable] = []
        self._zeroconf_available = self._check_zeroconf()
        self._running = False

        logger.info(f"NodeDiscovery 初始化: node_id={node_id}, central={central_server}")

    def _check_zeroconf(self) -> bool:
        try:
            import zeroconf
            return True
        except ImportError:
            logger.warning("zeroconf 未安装，mDNS发现将不可用")
            return False

    async def discover(self, timeout: float = 5.0) -> DiscoveryResult:
        """执行混合发现"""
        result = DiscoveryResult()
        tasks = []

        if self.central_server:
            tasks.append(self._discover_central())
        tasks.append(self._discover_multicast(timeout))
        if self._zeroconf_available:
            tasks.append(self._discover_zeroconf(timeout))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, DiscoveryResult):
                result.merge(r)

        for node in result.nodes:
            self._nodes[node.node_id] = node

        self._notify_listeners("discovery_complete", result)
        return result

    async def _discover_central(self) -> DiscoveryResult:
        """从中心服务器获取节点列表"""
        if not self.central_server:
            return DiscoveryResult()

        result = DiscoveryResult(sources=["central"])

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{self.central_server}/api/nodes"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5.0)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data.get("nodes", []):
                            node = DiscoveredNode(
                                node_id=item["node_id"],
                                ip=item["ip"],
                                port=item["port"],
                                discovery_type=DiscoveryType.CENTRAL,
                                capabilities=item.get("capabilities", []),
                                metadata=item.get("metadata", {}),
                            )
                            result.nodes.append(node)
        except Exception as e:
            logger.debug(f"中心服务器发现失败: {e}")

        return result

    async def _discover_multicast(self, timeout: float) -> DiscoveryResult:
        """UDP组播发现（局域网）"""
        result = DiscoveryResult(sources=["multicast"])
        loop = asyncio.get_event_loop()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            group = socket.inet_aton(self.MDNS_GROUP)
            mreq = struct.pack("4sL", group, socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.settimeout(min(timeout, 2.0))
            sock.bind(('', self.multicast_port))

            discovery_msg = json.dumps({
                "type": "discovery_request",
                "node_id": self.node_id,
                "timestamp": datetime.now().isoformat(),
            }).encode()

            sock.sendto(discovery_msg, (self.MDNS_GROUP, self.multicast_port))

            start_time = loop.time()
            while True:
                try:
                    data, addr = sock.recvfrom(4096)
                    elapsed = (loop.time() - start_time) * 1000
                    node_info = json.loads(data.decode())

                    if node_info.get("type") == "discovery_response":
                        node = DiscoveredNode(
                            node_id=node_info["node_id"],
                            ip=addr[0],
                            port=node_info.get("port", self.multicast_port),
                            discovery_type=DiscoveryType.MULTICAST,
                            latency_ms=elapsed,
                            capabilities=node_info.get("capabilities", []),
                        )
                        result.nodes.append(node)
                except socket.timeout:
                    break

            sock.close()
        except Exception as e:
            logger.debug(f"UDP组播发现失败: {e}")

        return result

    async def _discover_zeroconf(self, timeout: float) -> DiscoveryResult:
        """mDNS/Zeroconf发现"""
        result = DiscoveryResult(sources=["zeroconf"])

        if not self._zeroconf_available:
            return result

        try:
            import zeroconf
            zc = zeroconf.Zeroconf()
            listener = _ZeroconfListener()

            browser = zeroconf.ServiceBrowser(zc, self.SERVICE_TYPE, listener)
            await asyncio.sleep(timeout)

            for service_info in listener.services.values():
                if service_info.addresses:
                    ip = socket.inet_ntoa(service_info.addresses[0])
                    node = DiscoveredNode(
                        node_id=service_info.name,
                        ip=ip,
                        port=service_info.port,
                        discovery_type=DiscoveryType.ZEROCONF,
                        metadata={"properties": dict(service_info.properties)},
                    )
                    result.nodes.append(node)

            zc.close()
        except Exception as e:
            logger.debug(f"mDNS发现失败: {e}")

        return result

    async def start_advertising(self):
        """开始广播自己的存在"""
        self._running = True
        while self._running:
            try:
                await self._advertise_multicast()
            except Exception as e:
                logger.debug(f"广播失败: {e}")
            await asyncio.sleep(5.0)

    def stop_advertising(self):
        """停止广播"""
        self._running = False

    async def _advertise_multicast(self):
        """UDP组播广播自己"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

            response_msg = json.dumps({
                "type": "discovery_response",
                "node_id": self.node_id,
                "port": self.multicast_port,
                "capabilities": ["search", "relay", "storage"],
            }).encode()

            sock.sendto(response_msg, (self.MDNS_GROUP, self.multicast_port))
            sock.close()
        except Exception as e:
            logger.debug(f"组播广播失败: {e}")

    def add_node(self, node_id: str, ip: str, port: int, **kwargs):
        """手动添加节点"""
        node = DiscoveredNode(
            node_id=node_id,
            ip=ip,
            port=port,
            discovery_type=DiscoveryType.MANUAL,
            capabilities=kwargs.get("capabilities", []),
            metadata=kwargs.get("metadata", {}),
        )
        self._nodes[node_id] = node
        self._notify_listeners("node_added", node)

    def remove_node(self, node_id: str):
        """移除节点"""
        if node_id in self._nodes:
            del self._nodes[node_id]
            self._notify_listeners("node_removed", node_id)

    def get_nodes(self) -> List[DiscoveredNode]:
        return list(self._nodes.values())

    def get_node(self, node_id: str) -> Optional[DiscoveredNode]:
        return self._nodes.get(node_id)

    def subscribe(self, callback: Callable):
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)

    def _notify_listeners(self, event: str, data: Any):
        for listener in self._listeners:
            try:
                listener(event, data)
            except Exception as e:
                logger.error(f"监听器回调错误: {e}")


class _ZeroconfListener:
    """Zeroconf 服务监听器"""
    def __init__(self):
        self.services = {}

    def add_service(self, zc, type_, name):
        pass

    def remove_service(self, zc, type_, name):
        self.services.pop(name, None)

    def update_service(self, zc, type_, name):
        pass


_discovery: Optional[NodeDiscovery] = None


def get_discovery(node_id: str = None, central_server: str = None) -> NodeDiscovery:
    global _discovery
    if _discovery is None:
        _discovery = NodeDiscovery(
            node_id=node_id or "anonymous",
            central_server=central_server,
        )
    return _discovery