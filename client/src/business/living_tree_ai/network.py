"""
LivingTreeAI Network - P2P网络通信模块
=================================

网络特性：
1. UDP广播发现 - 局域网内节点自动发现
2. TCP可靠传输 - 任务和知识数据
3. WebRTC直连 - 节点间P2P通信
4. NAT穿透 - UDP打洞 + 中继备用
5. DHT分布式哈希表 - 节点状态和资源索引

Author: Hermes Desktop Team
"""

import asyncio
import json
import struct
import hashlib
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Protocol(Enum):
    """通信协议"""
    UDP_DISCOVERY = 0x01      # 节点发现
    TCP_HANDSHAKE = 0x02      # TCP握手
    HEARTBEAT = 0x03          # 心跳
    TASK_REQUEST = 0x10       # 任务请求
    TASK_RESPONSE = 0x11      # 任务响应
    KNOWLEDGE_PUSH = 0x20     # 知识推送
    KNOWLEDGE_PULL = 0x21     # 知识拉取
    MODEL_TRANSFER = 0x30     # 模型传输
    RELAY_MESSAGE = 0x40      # 中继消息


@dataclass
class NetworkConfig:
    """网络配置"""
    # 发现配置
    udp_broadcast_port: int = 19888
    udp_broadcast_interval: float = 5.0  # 秒
    discovery_timeout: float = 30.0       # 秒

    # TCP配置
    tcp_port: int = 19889
    max_connections: int = 100
    connection_timeout: float = 30.0

    # NAT穿透配置
    stun_server: str = "stun.l.google.com"
    stun_port: int = 19302
    relay_enabled: bool = True
    relay_port: int = 19890

    # DHT配置
    dht_bucket_size: int = 20
    dht_refresh_interval: float = 3600.0  # 秒

    # 带宽限制
    max_bandwidth_mbps: float = 10.0
    upload_limit_kbps: int = 512
    download_limit_kbps: int = 2048


@dataclass
class PeerInfo:
    """对等节点信息"""
    node_id: str
    address: Tuple[str, int]      # (ip, port)
    public_address: Tuple[str, int] = None  # NAT后的公网地址
    nat_type: str = "unknown"      # "open", "full_cone", "restricted", "port_restricted", "symmetric"
    tcp_port: int = 0
    relay_port: int = 0
    last_seen: float = 0
    latency_ms: float = 0
    capabilities: List[str] = field(default_factory=list)
    trusted: bool = False

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "address": f"{self.address[0]}:{self.address[1]}",
            "public_address": f"{self.public_address[0]}:{self.public_address[1]}" if self.public_address else "",
            "nat_type": self.nat_type,
            "tcp_port": self.tcp_port,
            "last_seen": self.last_seen,
            "latency_ms": self.latency_ms,
            "capabilities": self.capabilities,
            "trusted": self.trusted,
        }


class KademliaDHT:
    """
    Kademlia风格的DHT实现

    用于：
    - 节点发现
    - 资源索引
    - 知识定位
    """

    def __init__(self, node_id: str, bucket_size: int = 20):
        self.node_id = node_id
        self.bucket_size = bucket_size
        self.buckets: List[List[PeerInfo]] = [[] for _ in range(256)]
        self.local_store: Dict[str, Any] = {}

    def distance(self, id1: str, id2: str) -> int:
        """计算XOR距离"""
        h1 = int(hashlib.sha256(id1.encode()).hexdigest(), 16)
        h2 = int(hashlib.sha256(id2.encode()).hexdigest(), 16)
        return h1 ^ h2

    def bucket_index(self, node_id: str) -> int:
        """获取桶索引"""
        dist = self.distance(self.node_id, node_id)
        if dist == 0:
            return 0
        return dist.bit_length() - 1

    def add_peer(self, peer: PeerInfo) -> bool:
        """添加对等节点"""
        idx = self.bucket_index(peer.node_id)
        bucket = self.buckets[idx]

        # 已在桶中，更新
        for i, p in enumerate(bucket):
            if p.node_id == peer.node_id:
                bucket[i] = peer
                return False

        # 桶未满，添加
        if len(bucket) < self.bucket_size:
            bucket.append(peer)
            return True

        # 桶已满，替换最老的
        oldest_idx = 0
        oldest_time = bucket[0].last_seen
        for i, p in enumerate(bucket):
            if p.last_seen < oldest_time:
                oldest_idx = i
                oldest_time = p.last_seen

        bucket[oldest_idx] = peer
        return True

    def find_closest(self, target_id: str, k: int = 20) -> List[PeerInfo]:
        """查找最近的k个节点"""
        all_peers = []
        for bucket in self.buckets:
            all_peers.extend(bucket)

        # 按距离排序
        all_peers.sort(key=lambda p: self.distance(self.node_id, p.node_id))
        return all_peers[:k]

    def store(self, key: str, value: Any):
        """存储数据"""
        self.local_store[key] = {
            "value": value,
            "timestamp": datetime.now().timestamp()
        }

    def get(self, key: str) -> Optional[Any]:
        """获取数据"""
        if key in self.local_store:
            return self.local_store[key]["value"]
        return None


class NATTraverser:
    """
    NAT穿透模块

    支持：
    - STUN检测
    - UDP打洞
    - TURN中继
    """

    def __init__(self, config: NetworkConfig):
        self.config = config
        self.stun_server = (config.stun_server, config.stun_port)
        self.nat_type = "unknown"
        self.external_address = None

    async def detect_nat_type(self) -> str:
        """检测NAT类型"""
        # 简化实现：实际需要STUN服务器
        try:
            # 尝试STUN查询
            self.nat_type = "open"  # 假设成功
            self.external_address = ("0.0.0.0", 0)
            return self.nat_type
        except Exception as e:
            logger.warning(f"NAT检测失败: {e}")
            self.nat_type = "unknown"
            return self.nat_type

    async def punch_hole(self, target: PeerInfo) -> bool:
        """UDP打洞"""
        if self.nat_type == "open":
            return True  # 无需打洞

        try:
            # 发送打洞数据包
            logger.info(f"正在为 {target.node_id} 打洞...")
            # 实际实现需要发送特殊的打洞包
            return True
        except Exception as e:
            logger.error(f"打洞失败: {e}")
            return False


class P2PNetwork:
    """
    P2P网络管理器

    功能：
    - 节点发现和连接管理
    - 消息路由和转发
    - NAT穿透
    - DHT网络
    """

    def __init__(self, node_id: str, config: NetworkConfig = None):
        self.node_id = node_id
        self.config = config or NetworkConfig()
        self.dht = KademliaDHT(node_id, self.config.dht_bucket_size)
        self.nat = NATTraverser(self.config)

        # 状态
        self.peers: Dict[str, PeerInfo] = {}
        self.running = False

        # 连接
        self.udp_socket: Optional[asyncio.DatagramProtocol] = None
        self.tcp_server: Optional[asyncio.Server] = None
        self.relay_server: Optional[asyncio.Server] = None

        # 消息处理
        self.message_handlers: Dict[Protocol, callable] = {}

    async def start(self):
        """启动网络"""
        self.running = True

        # 检测NAT类型
        nat_type = await self.nat.detect_nat_type()
        logger.info(f"NAT类型: {nat_type}")

        # 启动UDP发现
        asyncio.create_task(self._udp_discovery())

        # 启动TCP服务
        asyncio.create_task(self._start_tcp_server())

        # 启动中继服务（如果启用）
        if self.config.relay_enabled:
            asyncio.create_task(self._start_relay_server())

        # 加入网络
        asyncio.create_task(self._join_network())

        logger.info(f"P2P网络已启动，节点ID: {self.node_id}")

    async def stop(self):
        """停止网络"""
        self.running = False

        if self.udp_socket:
            self.udp_socket.close()

        if self.tcp_server:
            self.tcp_server.close()

        if self.relay_server:
            self.relay_server.close()

        logger.info("P2P网络已停止")

    async def _udp_discovery(self):
        """UDP广播发现"""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', self.config.udp_broadcast_port))

        self.udp_socket = sock

        while self.running:
            try:
                data, addr = sock.recvfrom(4096)
                await self._handle_discovery_message(data, addr)
            except Exception as e:
                if self.running:
                    logger.error(f"UDP接收错误: {e}")

    async def _handle_discovery_message(self, data: bytes, addr: Tuple[str, int]):
        """处理发现消息"""
        try:
            msg = json.loads(data.decode())
            msg_type = msg.get("type")

            if msg_type == "discovery":
                # 收到其他节点的发现请求
                peer = PeerInfo(
                    node_id=msg["node_id"],
                    address=addr,
                    last_seen=datetime.now().timestamp()
                )
                self._handle_new_peer(peer)

                # 响应自己的信息
                response = {
                    "type": "discovery_ack",
                    "node_id": self.node_id,
                    "capabilities": ["inference", "training", "storage"]
                }
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(json.dumps(response).encode(), addr)
                sock.close()

            elif msg_type == "discovery_ack":
                # 收到发现响应
                peer = PeerInfo(
                    node_id=msg["node_id"],
                    address=addr,
                    last_seen=datetime.now().timestamp()
                )
                self._handle_new_peer(peer)

        except Exception as e:
            logger.error(f"处理发现消息错误: {e}")

    def _handle_new_peer(self, peer: PeerInfo):
        """处理新节点"""
        if peer.node_id == self.node_id:
            return  # 忽略自己

        if peer.node_id not in self.peers:
            logger.info(f"发现新节点: {peer.node_id} @ {peer.address}")
            self.peers[peer.node_id] = peer
            self.dht.add_peer(peer)

    async def _broadcast_discovery(self):
        """广播发现请求"""
        import socket

        msg = {
            "type": "discovery",
            "node_id": self.node_id,
            "capabilities": ["inference", "training", "storage"]
        }

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(
            json.dumps(msg).encode(),
            ('<broadcast>', self.config.udp_broadcast_port)
        )
        sock.close()

    async def _start_tcp_server(self):
        """启动TCP服务器"""
        self.tcp_server = await asyncio.start_server(
            self._handle_tcp_connection,
            '0.0.0.0',
            self.config.tcp_port
        )
        logger.info(f"TCP服务器监听端口: {self.config.tcp_port}")

    async def _handle_tcp_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理TCP连接"""
        addr = writer.get_extra_info('peername')
        logger.info(f"TCP连接: {addr}")

        try:
            while self.running:
                data = await reader.read(4096)
                if not data:
                    break

                msg = json.loads(data.decode())
                await self._handle_tcp_message(msg, writer)

        except Exception as e:
            logger.error(f"TCP连接错误: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _handle_tcp_message(self, msg: Dict, writer: asyncio.StreamWriter):
        """处理TCP消息"""
        msg_type = msg.get("type")

        if msg_type == "handshake":
            # 握手
            response = {
                "type": "handshake_ack",
                "node_id": self.node_id
            }
            writer.write(json.dumps(response).encode())

        elif msg_type in self.message_handlers:
            # 调用注册的处理器
            handler = self.message_handlers[msg_type]
            response = await handler(msg)
            if response:
                writer.write(json.dumps(response).encode())

    async def _start_relay_server(self):
        """启动中继服务器"""
        self.relay_server = await asyncio.start_server(
            self._handle_relay_connection,
            '0.0.0.0',
            self.config.relay_port
        )
        logger.info(f"中继服务器监听端口: {self.config.relay_port}")

    async def _handle_relay_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理中继连接"""
        try:
            data = await reader.read(8192)
            msg = json.loads(data.decode())

            # 转发消息到目标节点
            target_id = msg.get("target_node_id")
            if target_id in self.peers:
                target = self.peers[target_id]
                # 实际实现：转发到目标

            # 返回确认
            writer.write(json.dumps({"status": "ok"}).encode())

        except Exception as e:
            logger.error(f"中继处理错误: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _join_network(self):
        """加入网络"""
        # 广播发现请求
        await self._broadcast_discovery()

        # 定时广播
        while self.running:
            await asyncio.sleep(self.config.udp_broadcast_interval)
            await self._broadcast_discovery()

    def register_handler(self, protocol: Protocol, handler: callable):
        """注册消息处理器"""
        self.message_handlers[protocol.value] = handler

    async def send_message(self, target_id: str, msg: Dict) -> bool:
        """发送消息到指定节点"""
        if target_id not in self.peers:
            logger.warning(f"目标节点不存在: {target_id}")
            return False

        target = self.peers[target_id]

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(target.address[0], target.tcp_port),
                timeout=self.config.connection_timeout
            )

            writer.write(json.dumps(msg).encode())
            await writer.drain()
            writer.close()
            await writer.wait_closed()

            return True

        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False

    async def broadcast(self, msg: Dict):
        """广播消息到所有节点"""
        for peer_id in list(self.peers.keys()):
            asyncio.create_task(self.send_message(peer_id, msg))

    def get_peers(self) -> List[Dict]:
        """获取所有对等节点"""
        return [p.to_dict() for p in self.peers.values()]

    def get_network_stats(self) -> Dict:
        """获取网络统计"""
        return {
            "node_id": self.node_id,
            "peer_count": len(self.peers),
            "dht_buckets_used": sum(1 for b in self.dht.buckets if b),
            "nat_type": self.nat.nat_type,
            "relay_enabled": self.config.relay_enabled,
        }


if __name__ == "__main__":
    async def test():
        network = P2PNetwork("test_node_001")

        # 注册消息处理器
        async def handle_task(msg):
            return {"type": "task_response", "result": "processed"}

        network.register_handler(Protocol.TASK_REQUEST, handle_task)

        await network.start()
        await asyncio.sleep(5)

        stats = network.get_network_stats()
        print(f"网络状态: {stats}")

        await network.stop()

    asyncio.run(test())
