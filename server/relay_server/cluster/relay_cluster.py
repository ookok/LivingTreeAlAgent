"""
Relay Cluster - 零配置分布式中继集群
=============================

核心理念：
1. 零配置 - 节点启动时只需知道集群名，不需要指定其他节点IP
2. 自动发现 - 通过 DHT风格的种子节点机制发现其他节点
3. 消息同步 - Gossip协议实现最终一致性
4. 负载均衡 - 客户端随机选择在线节点

架构：
  ┌──────────────────────────────────────────────────┐
  │              Global Registry (轻量)               │
  │     (只存节点ID列表，不存消息，无单点瓶颈)         │
  │                                                  │
  │   节点注册：/register?node_id=X&cluster=Y       │
  │   节点列表：/nodes?cluster=X                     │
  │   心跳保活：/heartbeat?node_id=X                 │
  └──────────────────────────────────────────────────┘
           │                    ▲
           ▼                    │
  ┌──────────────────────────────────────────────────┐
  │              Relay Cluster                       │
  │                                                  │
  │  每个节点包含：                                   │
  │  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
  │  │ P2P层   │  │ 消息层  │  │ WebSocket │        │
  │  │(节点发现)│  │(Gossip) │  │  (客户端) │        │
  │  └─────────┘  └─────────┘  └─────────┘         │
  │                                                  │
  │  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
  │  │ 存储层   │  │ 路由层  │  │ 统计层   │         │
  │  │(SQLite) │  │(消息路由)│  │ (监控)   │         │
  │  └─────────┘  └─────────┘  └─────────┘         │
  └──────────────────────────────────────────────────┘
                         ▲
                         │
              ┌──────────┴──────────┐
              │     Clients         │
              │  (桌面/Web/移动端)    │
              └─────────────────────┘
"""

import asyncio
import hashlib
import json
import random
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Any
from collections import defaultdict
import logging

from client.src.business.config import UnifiedConfig

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RelayCluster")


# ============================================================
# 1. 节点发现层 - DHT 风格种子节点
# ============================================================

@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str                    # 全局唯一节点ID
    cluster: str                    # 集群名称
    host: str                       # 节点 host
    port: int                       # 节点 port
    public_host: str = ""           # 公网地址（供其他节点连接）
    public_port: int = 0            # 公网端口
    version: str = "2.0"            # 软件版本
    status: str = "online"         # online/offline
    last_heartbeat: float = 0      # 最后心跳时间
    peers: List[str] = field(default_factory=list)  # 直接相连的节点ID列表
    load: int = 0                   # 当前负载（连接数）
    score: float = 1.0              # 选举权重


class NodeRegistry:
    """
    轻量级节点注册表
    - 不存储消息，只存储节点列表
    - 支持多集群隔离
    - 节点 TTL 自动过期
    """

    def __init__(self):
        self.nodes: Dict[str, NodeInfo] = {}  # node_id -> NodeInfo
        self.clusters: Dict[str, Set[str]] = defaultdict(set)  # cluster -> set of node_ids
        self._lock = asyncio.Lock()

    async def register(self, node_info: NodeInfo) -> bool:
        """注册节点"""
        async with self._lock:
            # 检查集群名是否匹配
            if node_info.cluster not in ["default", "hermes"]:
                logger.warning(f"未知集群: {node_info.cluster}")
                return False

            node_info.last_heartbeat = time.time()
            self.nodes[node_info.node_id] = node_info
            self.clusters[node_info.cluster].add(node_info.node_id)
            logger.info(f"节点注册成功: {node_info.node_id} @ {node_info.host}:{node_info.port}")
            return True

    async def unregister(self, node_id: str) -> bool:
        """注销节点"""
        async with self._lock:
            if node_id in self.nodes:
                cluster = self.nodes[node_id].cluster
                self.clusters[cluster].discard(node_id)
                del self.nodes[node_id]
                logger.info(f"节点注销: {node_id}")
                return True
            return False

    async def heartbeat(self, node_id: str) -> bool:
        """节点心跳"""
        async with self._lock:
            if node_id in self.nodes:
                self.nodes[node_id].last_heartbeat = time.time()
                self.nodes[node_id].status = "online"
                return True
            return False

    async def get_nodes(self, cluster: str = "default", status: str = "online") -> List[NodeInfo]:
        """获取集群节点列表"""
        async with self._lock:
            now = time.time()
            result = []
            for node_id in self.clusters.get(cluster, set()):
                node = self.nodes.get(node_id)
                if not node:
                    continue
                # TTL 120秒
                if now - node.last_heartbeat > 120:
                    node.status = "offline"
                if status == "all" or node.status == status:
                    result.append(node)
            return result

    async def get_random_node(self, cluster: str = "default") -> Optional[NodeInfo]:
        """随机获取一个可用节点（用于客户端路由）"""
        nodes = await self.get_nodes(cluster, "online")
        if not nodes:
            return None
        # 按负载加权随机
        weights = [max(1, 100 - n.load) for n in nodes]
        total = sum(weights)
        r = random.uniform(0, total)
        cumulative = 0
        for node in nodes:
            cumulative += max(1, 100 - node.load)
            if r <= cumulative:
                return node
        return nodes[-1]


# 全局注册表实例
_registry = NodeRegistry()


# ============================================================
# 2. 消息同步层 - Gossip 协议
# ============================================================

class GossipState:
    """Gossip 协议状态"""

    VERSION = 1
    FANOUT = 3          # 每轮传播节点数
    
    # 传播间隔（秒）- 从配置读取
    @staticmethod
    def get_interval() -> float:
        try:
            config = UnifiedConfig.get_instance()
            return config.get("server.gossip_interval", 2.0)
        except Exception:
            return 2.0
    
    TTL = 10            # 消息 TTL


@dataclass
class Message:
    """跨节点消息"""
    msg_id: str         # 消息全局唯一ID
    channel: str        # 频道
    sender: str         # 发送者 client_id
    relay_node: str     # 最初接收的节点ID
    content: Any        # 消息内容
    timestamp: float    # 时间戳
    ttl: int = GossipState.TTL  # 剩余传播轮数

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "Message":
        return cls(**json.loads(data))


class GossipProtocol:
    """
    Gossip 协议实现
    - 特点：最终一致性、去中心化、容错
    - 适合场景：群组消息、状态同步
    """

    def __init__(self, node_id: str, registry: NodeRegistry):
        self.node_id = node_id
        self.registry = registry
        self.known_messages: Set[str] = set()  # 已收到的消息ID集合
        self.pending_messages: Dict[str, Message] = {}  # 待传播的消息
        self.message_history: Dict[str, List[Message]] = defaultdict(list)  # channel -> 消息历史
        self.max_history = 200  # 每频道保留最近200条

    async def broadcast(self, channel: str, sender: str, content: Any) -> Message:
        """广播消息到频道"""
        msg = Message(
            msg_id = f"{self.node_id}_{uuid.uuid4().hex[:12]}",
            channel = channel,
            sender = sender,
            relay_node = self.node_id,
            content = content,
            timestamp = time.time()
        )

        # 记录本地
        self.known_messages.add(msg.msg_id)
        self._add_to_history(msg)

        # 存入待传播队列
        self.pending_messages[msg.msg_id] = msg

        logger.debug(f"Gossip: 广播消息 {msg.msg_id} 到频道 {channel}")
        return msg

    async def spread(self) -> int:
        """Gossip 传播轮次 - 随机选择节点传播待处理消息"""
        if not self.pending_messages:
            return 0

        nodes = await self.registry.get_nodes(status="online")
        if len(nodes) <= 1:
            return 0

        spread_count = 0
        to_remove = []

        for msg_id, msg in list(self.pending_messages.items()):
            if msg.ttl <= 0:
                to_remove.append(msg_id)
                continue

            # 选择随机节点传播
            targets = random.sample(
                [n for n in nodes if n.node_id != self.node_id],
                min(GossipState.FANOUT, len(nodes) - 1)
            )

            for target in targets:
                # 模拟发送到 target（实际由 HTTP/WebSocket 调用）
                asyncio.create_task(self._send_to_node(target, msg))
                spread_count += 1

            # TTL 递减
            msg.ttl -= 1
            if msg.ttl <= 0:
                to_remove.append(msg_id)

        # 清理已过期的消息
        for msg_id in to_remove:
            del self.pending_messages[msg_id]

        return spread_count

    async def receive(self, msg: Message) -> bool:
        """接收来自其他节点的消息"""
        if msg.msg_id in self.known_messages:
            return False  # 已处理过

        self.known_messages.add(msg.msg_id)
        self._add_to_history(msg)

        # 自己也继续传播
        if msg.ttl > 0:
            msg.ttl -= 1
            self.pending_messages[msg.msg_id] = msg

        logger.debug(f"Gossip: 收到消息 {msg.msg_id}")
        return True

    def _add_to_history(self, msg: Message):
        """添加到历史记录"""
        self.message_history[msg.channel].append(msg)
        # 限制历史长度
        if len(self.message_history[msg.channel]) > self.max_history:
            self.message_history[msg.channel] = self.message_history[msg.channel][-self.max_history:]

    async def get_history(self, channel: str, limit: int = 100) -> List[Message]:
        """获取频道历史"""
        return self.message_history.get(channel, [])[-limit:]

    async def _send_to_node(self, target: NodeInfo, msg: Message):
        """模拟发送到目标节点（实际通过 HTTP API）"""
        # TODO: 实现实际的网络传输
        pass


# ============================================================
# 3. 负载均衡层 - 客户端路由
# ============================================================

class LoadBalancer:
    """
    零配置负载均衡
    - 客户端随机选择节点
    - 支持权重（基于负载、延迟）
    - 自动重连失败的节点
    """

    def __init__(self, registry: NodeRegistry):
        self.registry = registry
        self.failed_nodes: Set[str] = set()  # 失败的节点（临时黑名单）
        self.client_preferences: Dict[str, str] = {}  # client_id -> node_id (偏好)

    async def select_node(self, cluster: str = "default") -> Optional[NodeInfo]:
        """为客户端选择最优节点"""
        nodes = await self.registry.get_nodes(cluster, "online")
        if not nodes:
            return None

        # 过滤失败的节点
        available = [n for n in nodes if n.node_id not in self.failed_nodes]
        if not available:
            self.failed_nodes.clear()  # 重试
            available = nodes

        # 按负载排序，选择最空闲的
        available.sort(key=lambda n: n.load)
        return available[0]

    async def select_for_client(self, client_id: str, cluster: str = "default") -> Optional[NodeInfo]:
        """为特定客户端选择节点（保持偏好）"""
        # 检查偏好节点是否还可用
        preferred = self.client_preferences.get(client_id)
        if preferred:
            nodes = await self.registry.get_nodes(cluster, "online")
            if preferred in [n.node_id for n in nodes]:
                return next(n for n in nodes if n.node_id == preferred)

        # 选择新节点
        node = await self.select_node(cluster)
        if node:
            self.client_preferences[client_id] = node.node_id
        return node

    def record_failure(self, node_id: str):
        """记录节点失败"""
        self.failed_nodes.add(node_id)
        logger.warning(f"节点失败: {node_id}")

    def record_success(self, node_id: str):
        """记录节点成功"""
        self.failed_nodes.discard(node_id)


# ============================================================
# 4. Relay Node - 单个中继节点实现
# ============================================================

class RelayNode:
    """
    中继节点（完整实现）
    - 对等节点，可独立运行
    - 自动注册到集群
    - 支持 WebSocket 客户端连接
    """

    def __init__(
        self,
        cluster: str = "default",
        host: str = "0.0.0.0",
        port: int = 8080,
        public_host: str = "",
        public_port: int = 0
    ):
        self.node_id = hashlib.sha256(f"{host}:{port}:{uuid.uuid4()}".encode()).hexdigest()[:16]
        self.cluster = cluster
        self.host = host
        self.port = port
        self.public_host = public_host or host
        self.public_port = public_port or port

        # 核心组件
        self.registry = _registry
        self.gossip = GossipProtocol(self.node_id, self.registry)
        self.lb = LoadBalancer(self.registry)

        # 客户端连接管理
        self.clients: Dict[str, Set[str]] = defaultdict(set)  # channel -> set of client_ids
        self.client_sockets: Dict[str, Any] = {}  # client_id -> websocket

        # 统计
        self.stats = {
            "start_time": time.time(),
            "messages_total": 0,
            "clients_total": 0,
            "bytes_transferred": 0,
        }

        self._running = False

    async def start(self):
        """启动节点"""
        self._running = True

        # 注册到集群
        node_info = NodeInfo(
            node_id=self.node_id,
            cluster=self.cluster,
            host=self.host,
            port=self.port,
            public_host=self.public_host,
            public_port=self.public_port
        )
        await self.registry.register(node_info)

        # 启动后台任务
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._gossip_loop())
        asyncio.create_task(self._cleanup_loop())

        logger.info(f"Relay节点启动: {self.node_id} @ {self.host}:{self.port}")
        logger.info(f"  集群: {self.cluster}")
        logger.info(f"  Registry: {id(self.registry)}")

    async def stop(self):
        """停止节点"""
        self._running = False
        await self.registry.unregister(self.node_id)
        logger.info(f"Relay节点停止: {self.node_id}")

    async def connect_client(self, client_id: str, channel: str, websocket: Any) -> bool:
        """客户端连接"""
        self.clients[channel].add(client_id)
        self.client_sockets[client_id] = websocket
        self.stats["clients_total"] += 1

        # 更新节点负载
        nodes = await self.registry.get_nodes(self.cluster, "online")
        for n in nodes:
            if n.node_id == self.node_id:
                n.load = len(self.client_sockets)
                break

        # 发送频道历史
        history = await self.gossip.get_history(channel)
        if history:
            await self._send_to_client(client_id, {
                "type": "history",
                "channel": channel,
                "messages": [
                    {"msg_id": m.msg_id, "sender": m.sender, "content": m.content, "timestamp": m.timestamp}
                    for m in history[-50:]
                ]
            })

        logger.info(f"客户端连接: {client_id} -> {channel}")
        return True

    async def disconnect_client(self, client_id: str, channel: str):
        """客户端断开"""
        self.clients[channel].discard(client_id)
        self.client_sockets.pop(client_id, None)
        logger.info(f"客户端断开: {client_id}")

    async def relay_message(self, channel: str, sender: str, content: Any) -> bool:
        """中继消息"""
        # Gossip 广播
        msg = await self.gossip.broadcast(channel, sender, content)
        self.stats["messages_total"] += 1

        # 直接投递给本地客户端
        await self._deliver_to_channel(channel, msg)

        return True

    async def _deliver_to_channel(self, channel: str, msg: Message):
        """投递消息到频道内的所有本地客户端"""
        for client_id in self.clients.get(channel, set()):
            await self._send_to_client(client_id, {
                "type": "message",
                "msg_id": msg.msg_id,
                "channel": msg.channel,
                "sender": msg.sender,
                "content": msg.content,
                "timestamp": msg.timestamp
            })

    async def _send_to_client(self, client_id: str, data: dict):
        """发送数据到客户端"""
        ws = self.client_sockets.get(client_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.error(f"发送失败 {client_id}: {e}")

    # ---- 后台任务 ----

    async def _heartbeat_loop(self):
        """心跳保活"""
        while self._running:
            await asyncio.sleep(30)
            await self.registry.heartbeat(self.node_id)
            logger.debug(f"心跳: {self.node_id}")

    async def _gossip_loop(self):
        """Gossip 传播循环"""
        while self._running:
            await asyncio.sleep(GossipState.get_interval())
            count = await self.gossip.spread()
            if count > 0:
                logger.debug(f"Gossip: 传播了 {count} 条消息")

    async def _cleanup_loop(self):
        """清理过期数据"""
        while self._running:
            await asyncio.sleep(60)
            # 清理过期的历史消息（已在 GossipProtocol 中处理）
            # 清理断开的客户端
            dead_clients = [
                cid for cid, ws in self.client_sockets.items()
                if ws.closed
            ]
            for cid in dead_clients:
                self.client_sockets.pop(cid, None)


# ============================================================
# 5. 全局入口点
# ============================================================

# 全局节点实例
_node: Optional[RelayNode] = None


async def create_node(
    cluster: str = "default",
    host: str = "0.0.0.0",
    port: int = 8080,
    **kwargs
) -> RelayNode:
    """创建并启动中继节点"""
    global _node
    _node = RelayNode(
        cluster=cluster,
        host=host,
        port=port,
        **kwargs
    )
    await _node.start()
    return _node


def get_node() -> Optional[RelayNode]:
    """获取当前节点实例"""
    return _node


# ============================================================
# 6. 启动脚本
# ============================================================

async def main():
    """启动示例"""
    node = await create_node(
        cluster="hermes",
        host="0.0.0.0",
        port=8080
    )

    print(f"""
╔══════════════════════════════════════════════════════════╗
║           Hermes Relay Cluster Node V2.0                  ║
╠══════════════════════════════════════════════════════════╣
║  Node ID: {node.node_id}
║  Cluster: {node.cluster}
║  Address: {node.host}:{node.port}
║  Public:  {node.public_host}:{node.public_port}
╚══════════════════════════════════════════════════════════╝
    """)

    # 保持运行
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n节点关闭...")
