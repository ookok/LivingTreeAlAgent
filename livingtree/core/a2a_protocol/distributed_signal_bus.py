"""
分布式信号总线集群
==================
支持多节点信号总线的分布式部署，实现跨节点信号同步和联邦匹配。

特性：
1. Redis/NATS 支持 - 高性能消息队列
2. 节点自动发现 - 去中心化集群
3. 联邦匹配 - 跨节点信号路由
4. 故障转移 - 自动节点切换
5. 负载均衡 - 智能信号分发

Author: LivingTree AI Agent
Date: 2026-04-29
"""

import asyncio
import hashlib
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import threading
import socket
import struct

try:
    import redis.asyncio as redis
    import redis
    HAS_REDIS = True
except ImportError:
    try:
        import redis
        HAS_REDIS = True
    except ImportError:
        HAS_REDIS = False

# ==================== 配置 ====================

@dataclass
class ClusterConfig:
    """集群配置"""
    node_id: str = ""                          # 本节点 ID
    cluster_name: str = "eigenflux_cluster"    # 集群名称
    
    # 传输层配置
    transport: str = "memory"                  # memory, redis, nats
    redis_url: str = "redis://localhost:6379"  # Redis URL
    redis_channel: str = "eigenflux_signals"   # Redis 频道
    
    # 网络配置
    bind_host: str = "0.0.0.0"
    bind_port: int = 8765
    advertise_host: str = ""                    # 对外暴露的地址
    advertise_port: int = 8765
    
    # 集群配置
    seed_nodes: List[str] = []                  # 种子节点
    heartbeat_interval: float = 5.0             # 心跳间隔
    node_timeout: float = 30.0                  # 节点超时
    gossip_interval: float = 2.0                # 八卦协议间隔
    
    # 联邦匹配
    enable_federation: bool = True             # 启用联邦匹配
    federation_threshold: float = 0.6           # 联邦匹配阈值
    max_federation_hops: int = 3                # 最大联邦跳数


# ==================== 节点状态 ====================

class NodeState(Enum):
    """节点状态"""
    ALIVE = "alive"
    SUSPECTED = "suspected"
    DEAD = "dead"
    LEAVING = "leaving"


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    host: str
    port: int
    state: NodeState = NodeState.ALIVE
    last_seen: float = field(default_factory=time.time)
    capabilities: Set[str] = field(default_factory=set)
    load: float = 0.0                          # 负载指标
    
    def is_alive(self) -> bool:
        """检查节点是否存活"""
        return self.state == NodeState.ALIVE
    
    def is_expired(self, timeout: float) -> bool:
        """检查是否超时"""
        return time.time() - self.last_seen > timeout


# ==================== 消息类型 ====================

class ClusterMessageType(Enum):
    """集群消息类型"""
    GOSSIP = "gossip"                          # 八卦协议
    SIGNAL_RELAY = "signal_relay"             # 信号转发
    SIGNAL_SYNC = "signal_sync"               # 信号同步
    HEARTBEAT = "heartbeat"                   # 心跳
    JOIN = "join"                             # 加入集群
    LEAVE = "leave"                           # 离开集群
    FEDERATE = "federate"                     # 联邦请求


@dataclass
class ClusterMessage:
    """集群消息"""
    message_type: ClusterMessageType
    sender_id: str
    timestamp: float
    payload: Dict[str, Any]
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ttl: int = 5                               # 消息 TTL（跳数）
    
    def to_bytes(self) -> bytes:
        """序列化为字节"""
        data = {
            "type": self.message_type.value,
            "sender": self.sender_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "id": self.message_id,
            "ttl": self.ttl,
        }
        return json.dumps(data).encode("utf-8")
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "ClusterMessage":
        """从字节反序列化"""
        obj = json.loads(data.decode("utf-8"))
        return cls(
            message_type=ClusterMessageType(obj["type"]),
            sender_id=obj["sender"],
            timestamp=obj["timestamp"],
            payload=obj["payload"],
            message_id=obj["id"],
            ttl=obj.get("ttl", 5),
        )


# ==================== 传输层抽象 ====================

class Transport(ABC):
    """传输层抽象基类"""
    
    @abstractmethod
    async def start(self):
        """启动传输层"""
        pass
    
    @abstractmethod
    async def stop(self):
        """停止传输层"""
        pass
    
    @abstractmethod
    async def send_to(self, node_id: str, message: ClusterMessage):
        """发送消息到指定节点"""
        pass
    
    @abstractmethod
    async def broadcast(self, message: ClusterMessage):
        """广播消息"""
        pass
    
    @abstractmethod
    async def receive(self) -> Optional[ClusterMessage]:
        """接收消息"""
        pass


class MemoryTransport(Transport):
    """内存传输层（单机测试用）"""
    
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._connections: Dict[str, "MemoryTransport"] = {}
        self._running = False
    
    def connect_peer(self, peer: "MemoryTransport"):
        """连接对等节点"""
        self._connections[id(peer)] = peer
    
    async def start(self):
        self._running = True
    
    async def stop(self):
        self._running = False
    
    async def send_to(self, node_id: str, message: ClusterMessage):
        # 内存传输，忽略 node_id
        for peer in self._connections.values():
            await peer._queue.put(message)
    
    async def broadcast(self, message: ClusterMessage):
        for peer in self._connections.values():
            await peer._queue.put(message)
    
    async def receive(self) -> Optional[ClusterMessage]:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None


class RedisTransport(Transport):
    """Redis 传输层（分布式生产用）"""
    
    def __init__(self, config: ClusterConfig):
        self.config = config
        self._client: Optional[Any] = None
        self._pubsub: Optional[Any] = None
        self._channel: str = config.redis_channel
        self._running = False
        self._queue: asyncio.Queue = asyncio.Queue()
    
    async def start(self):
        if not HAS_REDIS:
            raise ImportError("redis package required: pip install redis")
        
        self._client = redis.from_url(
            self.config.redis_url,
            encoding="utf-8",
            decode_responses=False
        )
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(self._channel)
        self._running = True
        
        # 启动订阅任务
        asyncio.create_task(self._subscribe_loop())
    
    async def stop(self):
        self._running = False
        if self._pubsub:
            await self._pubsub.unsubscribe(self._channel)
            self._pubsub.close()
        if self._client:
            await self._client.close()
    
    async def _subscribe_loop(self):
        """订阅循环"""
        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )
                if message and message["type"] == "message":
                    data = message["data"]
                    cluster_msg = ClusterMessage.from_bytes(data)
                    await self._queue.put(cluster_msg)
            except Exception as e:
                print(f"[RedisTransport] Subscribe error: {e}")
                await asyncio.sleep(1)
    
    async def send_to(self, node_id: str, message: ClusterMessage):
        """发送到指定节点的频道"""
        channel = f"{self._channel}:{node_id}"
        await self._client.publish(channel, message.to_bytes())
    
    async def broadcast(self, message: ClusterMessage):
        """广播到集群频道"""
        await self._client.publish(self._channel, message.to_bytes())
    
    async def receive(self) -> Optional[ClusterMessage]:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None


# ==================== 集群成员管理 ====================

class MembershipService:
    """
    集群成员服务
    ==================
    管理集群中的节点成员关系
    """
    
    def __init__(self, config: ClusterConfig):
        self.config = config
        self._my_node: NodeInfo = NodeInfo(
            node_id=config.node_id,
            host=config.advertise_host or config.bind_host,
            port=config.advertise_port,
            capabilities={"signal_relay", "federation"},
        )
        self._nodes: Dict[str, NodeInfo] = {}
        self._lock = threading.RLock()
        
        # 八卦协议状态
        self._gossip_messages: Dict[str, Tuple[float, ClusterMessage]] = {}
        self._max_gossip_history = 1000
    
    @property
    def node_id(self) -> str:
        return self._my_node.node_id
    
    def add_node(self, node: NodeInfo):
        """添加节点"""
        with self._lock:
            existing = self._nodes.get(node.node_id)
            if existing:
                existing.last_seen = node.last_seen
                existing.state = node.state
                existing.capabilities = node.capabilities
                existing.load = node.load
            else:
                self._nodes[node.node_id] = node
    
    def remove_node(self, node_id: str):
        """移除节点"""
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
    
    def get_alive_nodes(self) -> List[NodeInfo]:
        """获取所有存活节点"""
        with self._lock:
            return [n for n in self._nodes.values() if n.is_alive()]
    
    def get_node(self, node_id: str) -> Optional[NodeInfo]:
        """获取指定节点"""
        return self._nodes.get(node_id)
    
    def update_load(self, load: float):
        """更新本节点负载"""
        self._my_node.load = load
    
    def get_lowest_load_node(self) -> Optional[NodeInfo]:
        """获取负载最低的节点"""
        alive = self.get_alive_nodes()
        if not alive:
            return self._my_node
        return min(alive, key=lambda n: n.load)
    
    def handle_gossip(self, message: ClusterMessage) -> bool:
        """
        处理八卦消息
        返回 True 表示消息是新的
        """
        msg_id = message.message_id
        
        with self._lock:
            if msg_id in self._gossip_messages:
                return False  # 已处理过
            
            # 存储八卦
            self._gossip_messages[msg_id] = (time.time(), message)
            
            # 清理过期八卦
            if len(self._gossip_messages) > self._max_gossip_history:
                oldest = sorted(
                    self._gossip_messages.items(),
                    key=lambda x: x[1][0]
                )[:len(self._gossip_messages) // 2]
                for k, _ in oldest:
                    del self._gossip_messages[k]
        
        # 更新节点信息
        payload = message.payload
        if "node_info" in payload:
            node = NodeInfo(
                node_id=payload["node_info"].get("node_id", ""),
                host=payload["node_info"].get("host", ""),
                port=payload["node_info"].get("port", 0),
                state=NodeState(payload["node_info"].get("state", "alive")),
                last_seen=message.timestamp,
                capabilities=set(payload["node_info"].get("capabilities", [])),
                load=payload["node_info"].get("load", 0.0),
            )
            self.add_node(node)
        
        return True
    
    def create_gossip(self, payload: Dict = None) -> ClusterMessage:
        """创建八卦消息"""
        return ClusterMessage(
            message_type=ClusterMessageType.GOSSIP,
            sender_id=self.node_id,
            timestamp=time.time(),
            payload=payload or {},
        )
    
    def create_join(self) -> ClusterMessage:
        """创建加入消息"""
        return ClusterMessage(
            message_type=ClusterMessageType.JOIN,
            sender_id=self.node_id,
            timestamp=time.time(),
            payload={
                "node_info": {
                    "node_id": self._my_node.node_id,
                    "host": self._my_node.host,
                    "port": self._my_node.port,
                    "capabilities": list(self._my_node.capabilities),
                    "state": self._my_node.state.value,
                }
            },
        )


# ==================== 联邦匹配引擎 ====================

class FederationEngine:
    """
    联邦匹配引擎
    ==================
    跨节点信号匹配和路由
    """
    
    def __init__(self, config: ClusterConfig, membership: MembershipService):
        self.config = config
        self._membership = membership
        self._federation_cache: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.Lock()
    
    def should_federate(self, signal: Any) -> bool:
        """
        判断信号是否需要联邦匹配
        """
        if not self.config.enable_federation:
            return False
        
        # 检查本地是否有匹配
        # 如果没有，尝试联邦
        return True  # 简化版，始终尝试联邦
    
    def get_federation_targets(self, signal: Any) -> List[str]:
        """
        获取联邦目标节点列表
        """
        targets = []
        signal_key = self._get_signal_key(signal)
        
        with self._lock:
            # 优先使用缓存的目标
            if signal_key in self._federation_cache:
                cached = self._federation_cache[signal_key]
                targets.extend(cached)
            
            # 添加其他存活节点
            alive = self._membership.get_alive_nodes()
            for node in alive:
                if node.node_id not in targets:
                    targets.append(node.node_id)
        
        return targets[:self.config.max_federation_hops]
    
    def record_federation_result(self, signal: Any, node_id: str, matched: bool):
        """记录联邦结果"""
        if matched:
            signal_key = self._get_signal_key(signal)
            with self._lock:
                self._federation_cache[signal_key].add(node_id)
    
    def _get_signal_key(self, signal: Any) -> str:
        """生成信号键"""
        content = json.dumps({
            "type": signal.metadata.signal_type.value,
            "sender": signal.metadata.sender_id,
            "keywords": sorted(signal.metadata.keywords),
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# ==================== 分布式信号总线 ====================

class DistributedSignalBus:
    """
    分布式信号总线
    ==================
    支持多节点集群的信号总线
    """
    
    def __init__(self, config: ClusterConfig):
        self.config = config
        self._membership = MembershipService(config)
        self._federation = FederationEngine(config, self._membership)
        self._transport: Optional[Transport] = None
        self._running = False
        
        # 信号缓存
        self._signal_cache: Dict[str, Any] = {}
        self._cache_lock = threading.Lock()
        
        # 回调
        self._callbacks: List[Callable] = []
        
        # 统计
        self._stats = {
            "signals_sent": 0,
            "signals_received": 0,
            "signals_federated": 0,
            "signals_cached": 0,
            "messages_broadcast": 0,
        }
    
    async def start(self):
        """启动分布式信号总线"""
        # 创建传输层
        if self.config.transport == "redis":
            self._transport = RedisTransport(self.config)
        else:
            self._transport = MemoryTransport()
        
        await self._transport.start()
        self._running = True
        
        # 发送加入消息
        join_msg = self._membership.create_join()
        await self._transport.broadcast(join_msg)
        
        # 启动后台任务
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._gossip_loop())
        asyncio.create_task(self._receive_loop())
    
    async def stop(self):
        """停止分布式信号总线"""
        self._running = False
        
        # 发送离开消息
        leave_msg = ClusterMessage(
            message_type=ClusterMessageType.LEAVE,
            sender_id=self._membership.node_id,
            timestamp=time.time(),
            payload={},
        )
        await self._transport.broadcast(leave_msg)
        
        await self._transport.stop()
    
    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._running:
            await asyncio.sleep(self.config.heartbeat_interval)
            
            # 发送心跳
            heartbeat = ClusterMessage(
                message_type=ClusterMessageType.HEARTBEAT,
                sender_id=self._membership.node_id,
                timestamp=time.time(),
                payload={"load": 0.5},  # TODO: 真实负载
            )
            await self._transport.broadcast(heartbeat)
            
            # 检查超时节点
            self._check_node_timeouts()
    
    async def _gossip_loop(self):
        """八卦协议循环"""
        while self._running:
            await asyncio.sleep(self.config.gossip_interval)
            
            # 创建八卦消息
            alive_nodes = self._membership.get_alive_nodes()
            gossip = self._membership.create_gossip({
                "nodes": [n.node_id for n in alive_nodes],
                "node_info": {
                    "node_id": self._membership.node_id,
                    "host": self.config.advertise_host,
                    "port": self.config.advertise_port,
                    "capabilities": list(self._membership._my_node.capabilities),
                }
            })
            await self._transport.broadcast(gossip)
    
    async def _receive_loop(self):
        """接收循环"""
        while self._running:
            message = await self._transport.receive()
            if message:
                await self._handle_message(message)
    
    async def _handle_message(self, message: ClusterMessage):
        """处理接收到的消息"""
        if message.sender_id == self._membership.node_id:
            return  # 忽略自己发送的消息
        
        if message.message_type == ClusterMessageType.SIGNAL_RELAY:
            # 信号转发
            self._handle_signal_relay(message)
        
        elif message.message_type == ClusterMessageType.SIGNAL_SYNC:
            # 信号同步
            self._handle_signal_sync(message)
        
        elif message.message_type == ClusterMessageType.GOSSIP:
            # 八卦消息
            if self._membership.handle_gossip(message):
                # 新八卦，转发给其他节点
                message.ttl -= 1
                if message.ttl > 0:
                    await self._transport.broadcast(message)
        
        elif message.message_type == ClusterMessageType.HEARTBEAT:
            # 心跳
            node = self._membership.get_node(message.sender_id)
            if node:
                node.last_seen = message.timestamp
        
        elif message.message_type == ClusterMessageType.FEDERATE:
            # 联邦请求
            await self._handle_federate(message)
    
    def _handle_signal_relay(self, message: ClusterMessage):
        """处理信号转发"""
        self._stats["signals_received"] += 1
        
        # 触发本地回调
        for callback in self._callbacks:
            try:
                callback(message.payload.get("signal"))
            except Exception as e:
                print(f"[DistributedSignalBus] Callback error: {e}")
    
    def _handle_signal_sync(self, message: ClusterMessage):
        """处理信号同步"""
        signal_data = message.payload.get("signal")
        if signal_data:
            cache_key = signal_data.get("signal_id", "")
            with self._cache_lock:
                self._signal_cache[cache_key] = signal_data
    
    async def _handle_federate(self, message: ClusterMessage):
        """处理联邦请求"""
        signal = message.payload.get("signal")
        if not signal:
            return
        
        # 检查本地是否匹配
        matched = True  # TODO: 实现本地匹配检查
        
        # 发送结果回去
        result = ClusterMessage(
            message_type=ClusterMessageType.FEDERATE,
            sender_id=self._membership.node_id,
            timestamp=time.time(),
            payload={
                "original_sender": message.payload.get("sender"),
                "matched": matched,
                "signal_id": signal.get("signal_id"),
            },
        )
        await self._transport.send_to(message.sender_id, result)
    
    def _check_node_timeouts(self):
        """检查节点超时"""
        for node_id, node in list(self._membership._nodes.items()):
            if node.is_expired(self.config.node_timeout):
                if node.state == NodeState.ALIVE:
                    node.state = NodeState.SUSPECTED
                elif node.state == NodeState.SUSPECTED:
                    node.state = NodeState.DEAD
                    self._membership.remove_node(node_id)
    
    async def broadcast_signal(self, signal: Any) -> int:
        """
        广播信号到集群
        
        返回：接收到的节点数
        """
        self._stats["signals_sent"] += 1
        
        # 检查是否需要联邦
        if self._federation.should_federate(signal):
            return await self._federate_signal(signal)
        
        # 直接广播
        message = ClusterMessage(
            message_type=ClusterMessageType.SIGNAL_RELAY,
            sender_id=self._membership.node_id,
            timestamp=time.time(),
            payload={"signal": signal.to_dict() if hasattr(signal, 'to_dict') else signal},
        )
        await self._transport.broadcast(message)
        
        self._stats["messages_broadcast"] += 1
        return len(self._membership.get_alive_nodes())
    
    async def _federate_signal(self, signal: Any) -> int:
        """联邦信号"""
        targets = self._federation.get_federation_targets(signal)
        delivered = 0
        
        for node_id in targets:
            message = ClusterMessage(
                message_type=ClusterMessageType.SIGNAL_RELAY,
                sender_id=self._membership.node_id,
                timestamp=time.time(),
                payload={"signal": signal.to_dict() if hasattr(signal, 'to_dict') else signal},
            )
            await self._transport.send_to(node_id, message)
            delivered += 1
        
        self._stats["signals_federated"] += delivered
        return delivered
    
    def on_signal(self, callback: Callable):
        """注册信号回调"""
        self._callbacks.append(callback)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self._stats,
            "nodes": len(self._membership.get_alive_nodes()),
            "cache_size": len(self._signal_cache),
            "callbacks": len(self._callbacks),
        }
    
    def get_cluster_status(self) -> Dict:
        """获取集群状态"""
        return {
            "node_id": self._membership.node_id,
            "nodes": {
                n.node_id: {
                    "state": n.state.value,
                    "last_seen": n.last_seen,
                    "load": n.load,
                }
                for n in self._membership.get_alive_nodes()
            },
            "config": {
                "transport": self.config.transport,
                "federation_enabled": self.config.enable_federation,
            }
        }


# ==================== 使用示例 ====================

async def example_distributed_bus():
    """分布式信号总线示例"""
    
    # 节点 A 配置
    config_a = ClusterConfig(
        node_id="node_a",
        cluster_name="test_cluster",
        transport="memory",  # 使用内存传输测试
        seed_nodes=[],
    )
    
    # 节点 B 配置
    config_b = ClusterConfig(
        node_id="node_b",
        cluster_name="test_cluster",
        transport="memory",
        seed_nodes=[],
    )
    
    # 创建分布式信号总线
    bus_a = DistributedSignalBus(config_a)
    bus_b = DistributedSignalBus(config_b)
    
    # 连接对等节点（内存传输）
    if isinstance(bus_a._transport, MemoryTransport) and \
       isinstance(bus_b._transport, MemoryTransport):
        bus_a._transport.connect_peer(bus_b._transport)
        bus_b._transport.connect_peer(bus_a._transport)
    
    # 注册回调
    received_signals = []
    
    def on_signal_a(signal):
        received_signals.append(("A", signal))
    
    bus_a.on_signal(on_signal_a)
    
    # 启动
    await bus_a.start()
    await bus_b.start()
    
    # 等待节点发现
    await asyncio.sleep(1)
    
    # 广播信号
    await bus_a.broadcast_signal({"type": "test", "data": "hello"})
    
    # 等待传递
    await asyncio.sleep(1)
    
    # 检查结果
    print(f"Node A stats: {bus_a.get_stats()}")
    print(f"Node B stats: {bus_b.get_stats()}")
    print(f"Received: {received_signals}")
    
    # 集群状态
    print(f"Cluster status: {bus_a.get_cluster_status()}")
    
    # 停止
    await bus_a.stop()
    await bus_b.stop()


if __name__ == "__main__":
    asyncio.run(example_distributed_bus())
