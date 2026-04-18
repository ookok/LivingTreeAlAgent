"""
分布式哈希表 (DHT)

实现商品索引的分布式存储和检索
采用 Kademlia 风格的路由协议
"""

import asyncio
import json
import hashlib
import random
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

from .models import ProductIndex, DHTEntry, GeoLocation, NodeInfo


logger = logging.getLogger(__name__)


class DHTProtocol(Enum):
    """DHT 协议类型"""
    PING = "ping"
    STORE = "store"
    FIND_NODE = "find_node"
    FIND_VALUE = "find_value"
    REPLICATE = "replicate"
    DELETE = "delete"


@dataclass
class DHTMessage:
    """DHT 消息"""
    protocol: DHTProtocol
    node_id: str
    request_id: str

    # 负载
    key: str = ""
    value: Any = None

    # 路由
    sender: str = ""
    ttl: int = 3

    # 时间戳
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol": self.protocol.value,
            "node_id": self.node_id,
            "request_id": self.request_id,
            "key": self.key,
            "value": self.value,
            "sender": self.sender,
            "ttl": self.ttl,
            "timestamp": self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'DHTMessage':
        return cls(
            protocol=DHTProtocol(data["protocol"]),
            node_id=data["node_id"],
            request_id=data["request_id"],
            key=data.get("key", ""),
            value=data.get("value"),
            sender=data.get("sender", ""),
            ttl=data.get("ttl", 3),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now()
        )


@dataclass
class Bucket:
    """K-桶：存储同一距离范围的节点"""
    k: int = 20  # 每个桶最多存储的节点数
    nodes: List[Tuple[str, NodeInfo, datetime]] = field(default_factory=list)  # (node_id, info, last_seen)

    def add(self, node_id: str, info: NodeInfo) -> bool:
        """添加节点到桶"""
        # 检查是否已存在
        for i, (nid, _, _) in enumerate(self.nodes):
            if nid == node_id:
                # 更新最后见时间
                self.nodes[i] = (node_id, info, datetime.now())
                return True

        # 如果桶未满，添加
        if len(self.nodes) < self.k:
            self.nodes.append((node_id, info, datetime.now()))
            return True

        # 桶已满，尝试替换最老的节点
        oldest_idx = 0
        oldest_time = self.nodes[0][2]

        for i, (_, _, last_seen) in enumerate(self.nodes):
            if (datetime.now() - last_seen).total_seconds() > (datetime.now() - oldest_time).total_seconds():
                oldest_idx = i
                oldest_time = last_seen

        self.nodes[oldest_idx] = (node_id, info, datetime.now())
        return True

    def remove(self, node_id: str):
        """从桶中移除节点"""
        self.nodes = [(nid, info, t) for nid, info, t in self.nodes if nid != node_id]

    def get_nodes(self) -> List[Tuple[str, NodeInfo]]:
        """获取所有节点"""
        return [(nid, info) for nid, info, _ in self.nodes]


class DHTNode:
    """DHT 节点 - Kademlia 风格的分布式哈希表"""

    ALPHA = 3  # 并发查找参数
    K = 20     # 数据复制参数
    B = 160    # 节点ID位数

    def __init__(self, node_id: str, local_ip: str = "", local_port: int = 0):
        self.node_id = node_id
        self.local_ip = local_ip
        self.local_port = local_port

        # K-桶路由表
        self.buckets: List[Bucket] = [Bucket() for _ in range(self.B)]

        # 本地存储
        self.local_store: Dict[str, DHTEntry] = {}

        # 待处理的请求
        self.pending_requests: Dict[str, asyncio.Future] = {}

        # 回调
        self.on_value_received: Optional[callable] = None
        self.on_node_contacted: Optional[callable] = None

        # 统计
        self.stats = {
            "store_count": 0,
            "find_success": 0,
            "find_fail": 0,
            "relay_count": 0
        }

    def _distance(self, node_id_a: str, node_id_b: str) -> int:
        """计算两个节点ID之间的XOR距离"""
        ha = int(hashlib.sha256(node_id_a.encode()).hexdigest(), 16)
        hb = int(hashlib.sha256(node_id_b.encode()).hexdigest(), 16)
        return ha ^ hb

    def _bucket_index(self, node_id: str) -> int:
        """计算节点应该放入哪个桶"""
        distance = self._distance(self.node_id, node_id)
        if distance == 0:
            return 0

        for i in range(self.B - 1, -1, -1):
            if distance & (1 << i):
                return self.B - 1 - i

        return 0

    def add_node(self, node_id: str, info: NodeInfo):
        """添加节点到路由表"""
        index = self._bucket_index(node_id)
        self.buckets[index].add(node_id, info)

    def remove_node(self, node_id: str):
        """从路由表移除节点"""
        index = self._bucket_index(node_id)
        self.buckets[index].remove(node_id)

    def get_nearest_nodes(self, key: str, k: int = None) -> List[Tuple[str, NodeInfo]]:
        """获取距离 key 最近的 k 个节点"""
        if k is None:
            k = self.K

        nodes_with_distance = []
        for bucket in self.buckets:
            for node_id, info in bucket.get_nodes():
                distance = self._distance(key, node_id)
                nodes_with_distance.append((distance, node_id, info))

        nodes_with_distance.sort(key=lambda x: x[0])
        return [(nid, info) for _, nid, info in nodes_with_distance[:k]]

    async def store(self, key: str, value: Any, ttl: int = 86400) -> bool:
        """存储 (key, value) 到网络中"""
        entry = DHTEntry(
            key=key,
            value=value,
            publisher_id=self.node_id,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=ttl)
        )

        self.local_store[key] = entry
        self.stats["store_count"] += 1

        nearest = self.get_nearest_nodes(key, self.K)

        for _, info in nearest:
            if info.node_id != self.node_id:
                asyncio.create_task(self._send_store(info, key, entry))

        return True

    async def _send_store(self, info: NodeInfo, key: str, entry: DHTEntry):
        """发送存储请求到其他节点"""
        msg = DHTMessage(
            protocol=DHTProtocol.STORE,
            node_id=self.node_id,
            request_id=self._generate_request_id(),
            key=key,
            value=entry.to_dict()
        )

        if self.on_node_contacted:
            await self.on_node_contacted(info, msg)

    async def find_node(self, key: str) -> List[Tuple[str, NodeInfo]]:
        """查找距离 key 最近的节点"""
        return self.get_nearest_nodes(key, self.ALPHA)

    async def find_value(self, key: str) -> Optional[Any]:
        """查找 value（如果存在）"""
        if key in self.local_store:
            entry = self.local_store[key]
            if not entry.is_expired():
                self.stats["find_success"] += 1
                return entry.value

        result = await self._parallel_find(key)
        if result:
            self.stats["find_success"] += 1
        else:
            self.stats["find_fail"] += 1

        return result

    async def _parallel_find(self, key: str) -> Optional[Any]:
        """并行查找"""
        queried: Set[str] = {self.node_id}
        closest: List[Tuple[int, str, NodeInfo]] = []

        for distance, node_id, info in self.get_nearest_nodes(key, self.ALPHA):
            closest.append((distance, node_id, info))
            queried.add(node_id)

        for _ in range(self.B):
            if not closest:
                break

            to_query = [(d, nid, info) for d, nid, info in closest if nid not in queried]
            if not to_query:
                break

            tasks = []
            for distance, node_id, info in to_query[:self.ALPHA]:
                tasks.append(self._query_node(info, key))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    continue

                if isinstance(result, dict):
                    if "value" in result:
                        return result["value"]

                    if "nodes" in result:
                        for node_data in result["nodes"]:
                            nid = node_data["node_id"]
                            if nid not in queried:
                                distance = self._distance(key, nid)
                                closest.append((distance, nid, NodeInfo.from_dict(node_data)))
                                queried.add(nid)

            closest.sort(key=lambda x: x[0])
            closest = closest[:self.K]

        return None

    async def _query_node(self, info: NodeInfo, key: str) -> Dict[str, Any]:
        """查询单个节点"""
        msg = DHTMessage(
            protocol=DHTProtocol.FIND_VALUE if key in self.local_store else DHTProtocol.FIND_NODE,
            node_id=self.node_id,
            request_id=self._generate_request_id(),
            key=key
        )

        if self.on_node_contacted:
            response = await self.on_node_contacted(info, msg)
            if response:
                return response.to_dict() if hasattr(response, 'to_dict') else response

        return {"nodes": []}

    async def delete(self, key: str) -> bool:
        """删除 key"""
        if key in self.local_store:
            del self.local_store[key]

        nearest = self.get_nearest_nodes(key, self.K)
        for _, info in nearest:
            if info.node_id != self.node_id:
                asyncio.create_task(self._send_delete(info, key))

        return True

    async def _send_delete(self, info: NodeInfo, key: str):
        """发送删除请求"""
        msg = DHTMessage(
            protocol=DHTProtocol.DELETE,
            node_id=self.node_id,
            request_id=self._generate_request_id(),
            key=key
        )

        if self.on_node_contacted:
            await self.on_node_contacted(info, msg)

    async def handle_message(self, msg: DHTMessage) -> Optional[DHTMessage]:
        """处理收到的 DHT 消息"""
        if msg.ttl <= 0:
            return None

        if msg.protocol == DHTProtocol.PING:
            return self._handle_ping(msg)
        elif msg.protocol == DHTProtocol.STORE:
            return await self._handle_store(msg)
        elif msg.protocol == DHTProtocol.FIND_NODE:
            return self._handle_find_node(msg)
        elif msg.protocol == DHTProtocol.FIND_VALUE:
            return await self._handle_find_value(msg)
        elif msg.protocol == DHTProtocol.DELETE:
            return await self._handle_delete(msg)

        return None

    def _handle_ping(self, msg: DHTMessage) -> DHTMessage:
        return DHTMessage(
            protocol=DHTProtocol.PING,
            node_id=self.node_id,
            request_id=msg.request_id,
            sender=self.node_id
        )

    async def _handle_store(self, msg: DHTMessage) -> Optional[DHTMessage]:
        entry = DHTEntry(
            key=msg.key,
            value=msg.value,
            publisher_id=msg.sender,
            created_at=datetime.now()
        )

        self.local_store[msg.key] = entry

        return DHTMessage(
            protocol=DHTProtocol.STORE,
            node_id=self.node_id,
            request_id=msg.request_id,
            value={"success": True}
        )

    def _handle_find_node(self, msg: DHTMessage) -> DHTMessage:
        nearest = self.get_nearest_nodes(msg.key, self.K)

        return DHTMessage(
            protocol=DHTProtocol.FIND_NODE,
            node_id=self.node_id,
            request_id=msg.request_id,
            value={
                "nodes": [
                    {"node_id": nid, "ip": info.ip, "port": info.port}
                    for nid, info in nearest
                ]
            }
        )

    async def _handle_find_value(self, msg: DHTMessage) -> DHTMessage:
        if msg.key in self.local_store:
            entry = self.local_store[msg.key]
            if not entry.is_expired():
                return DHTMessage(
                    protocol=DHTProtocol.FIND_VALUE,
                    node_id=self.node_id,
                    request_id=msg.request_id,
                    value={"value": entry.value}
                )

        nearest = self.get_nearest_nodes(msg.key, self.K)
        return DHTMessage(
            protocol=DHTProtocol.FIND_VALUE,
            node_id=self.node_id,
            request_id=msg.request_id,
            value={
                "nodes": [
                    {"node_id": nid, "ip": info.ip, "port": info.port}
                    for nid, info in nearest
                ]
            }
        )

    async def _handle_delete(self, msg: DHTMessage) -> Optional[DHTMessage]:
        if msg.key in self.local_store:
            del self.local_store[msg.key]

        return DHTMessage(
            protocol=DHTProtocol.DELETE,
            node_id=self.node_id,
            request_id=msg.request_id,
            value={"success": True}
        )

    def _generate_request_id(self) -> str:
        """生成请求ID"""
        return hashlib.sha256(
            f"{self.node_id}{datetime.now().isoformat()}{random.random()}".encode()
        ).hexdigest()[:16]


class ProductIndexManager:
    """商品索引管理器 - 在 DHT 上管理商品索引"""

    def __init__(self, dht_node: DHTNode, node_id: str):
        self.dht = dht_node
        self.node_id = node_id
        self.local_indexes: Dict[str, ProductIndex] = {}

    def create_index(self, product_id: str, title: str, price: float,
                    category: str, geohash: str, seller_id: str,
                    seller_rep: int) -> ProductIndex:
        """创建商品索引"""
        index = ProductIndex(
            product_id=product_id,
            title=title,
            price=price,
            category=category,
            geohash_prefix=geohash[:6],
            location=geohash,
            seller_id=seller_id,
            seller_rep=seller_rep
        )

        self.local_indexes[product_id] = index
        return index

    async def publish_index(self, index: ProductIndex) -> bool:
        """发布商品索引到 DHT 网络"""
        key = f"product:{index.product_id}"
        index_data = index.__dict__.copy()

        await self.dht.store(key, index_data)

        category_key = f"category:{index.category}:{index.geohash_prefix}"
        await self.dht.store(category_key, {
            "product_id": index.product_id,
            "price": index.price,
            "geohash": index.geohash_prefix
        })

        location_key = f"location:{index.geohash_prefix}"
        await self.dht.store(location_key, {
            "product_id": index.product_id,
            "seller_rep": index.seller_rep
        })

        return True

    async def find_nearby_products(
        self,
        geohash: str,
        category: str = None,
        price_max: float = None,
        seller_rep_min: int = 0,
        limit: int = 20
    ) -> List[ProductIndex]:
        """查找附近商品"""
        results = []

        for precision in [6, 5, 4, 3]:
            prefix = geohash[:precision]
            key = f"location:{prefix}"

            value = await self.dht.find_value(key)
            if value and "product_id" in value:
                product_key = f"product:{value['product_id']}"
                product_data = await self.dht.find_value(product_key)

                if product_data:
                    index = ProductIndex(**product_data)

                    if category and index.category != category:
                        continue
                    if price_max and index.price > price_max:
                        continue
                    if index.seller_rep < seller_rep_min:
                        continue

                    results.append(index)

                    if len(results) >= limit:
                        break

        results.sort(key=lambda x: x.geohash_prefix)
        return results[:limit]

    async def find_by_category(
        self,
        category: str,
        geohash_prefix: str,
        limit: int = 20
    ) -> List[ProductIndex]:
        """按分类查找商品"""
        key = f"category:{category}:{geohash_prefix}"

        value = await self.dht.find_value(key)
        if not value:
            return []

        product_key = f"product:{value['product_id']}"
        product_data = await self.dht.find_value(product_key)

        if product_data:
            return [ProductIndex(**product_data)]

        return []

    async def remove_product(self, product_id: str) -> bool:
        """从索引中移除商品"""
        key = f"product:{product_id}"

        if product_id in self.local_indexes:
            index = self.local_indexes[product_id]

            location_key = f"location:{index.geohash_prefix}"
            await self.dht.delete(location_key)

            category_key = f"category:{index.category}:{index.geohash_prefix}"
            await self.dht.delete(category_key)

            await self.dht.delete(key)

            del self.local_indexes[product_id]

        return True
