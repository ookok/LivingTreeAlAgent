"""
P2P节点通信模块

实现对等节点之间的直接通信
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
import time
from typing import Any, Callable, Optional

from .models import (
    Message, PeerNode, NetworkAddress, NatType, NodeRole,
    PROTOCOL_VERSION, DEFAULT_UDP_PORT, DEFAULT_TCP_PORT
)

logger = logging.getLogger(__name__)


class P2PProtocol:
    """P2P通信协议"""
    
    # 消息类型常量
    MSG_HANDSHAKE = "handshake"
    MSG_HANDSHAKE_ACK = "handshake_ack"
    MSG_PING = "ping"
    MSG_PONG = "pong"
    MSG_FIND_NODE = "find_node"
    MSG_NODES = "nodes"
    MSG_STORE = "store"
    MSG_FIND_VALUE = "find_value"
    MSG_RELAY = "relay"
    MSG_DISCONNECT = "disconnect"
    MSG_SYNC_REQUEST = "sync_request"
    MSG_SYNC_RESPONSE = "sync_response"
    MSG_DATA = "data"
    MSG_ACK = "ack"
    
    def __init__(self, node_id: str, udp_port: int = DEFAULT_UDP_PORT):
        self.node_id = node_id
        self.udp_port = udp_port
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.protocol: Optional[asyncio.DatagramProtocol] = None
        self.running = False
        self._message_handlers: dict[str, Callable] = {}
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._node_registry: dict[str, PeerNode] = {}
        self._lock = asyncio.Lock()
    
    async def start(self):
        """启动P2P协议栈"""
        loop = asyncio.get_event_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: P2PProtocolHandler(self),
            local_addr=('0.0.0.0', self.udp_port)
        )
        self.running = True
        logger.info(f"P2P protocol started on UDP port {self.udp_port}")
    
    async def stop(self):
        """停止P2P协议栈"""
        self.running = False
        if self.transport:
            self.transport.close()
            self.transport = None
            self.protocol = None
        logger.info("P2P protocol stopped")
    
    def register_handler(self, msg_type: str, handler: Callable):
        """注册消息处理器"""
        self._message_handlers[msg_type] = handler
    
    async def send_message(self, addr: tuple[str, int], message: Message) -> bool:
        """发送消息到指定地址"""
        if not self.transport or not self.running:
            return False
        
        try:
            data = message.to_bytes()
            self.transport.sendto(data, addr)
            logger.debug(f"Sent {message.msg_type} to {addr[0]}:{addr[1]}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    async def broadcast(self, message: Message, exclude: Optional[tuple[str, int]] = None):
        """广播消息到所有已知节点"""
        async with self._lock:
            for node_id, node in self._node_registry.items():
                if node.public_addr:
                    addr = (node.public_addr.ip, node.public_addr.port)
                    if exclude and addr == exclude:
                        continue
                    await self.send_message(addr, message)
    
    async def find_node(self, target_id: str) -> list[PeerNode]:
        """查找最近的节点 (Kademlia风格)"""
        async with self._lock:
            all_nodes = list(self._node_registry.values())
        
        # 计算距离并排序
        def distance(n1: str, n2: str) -> int:
            # 简化的XOR距离
            return int(n1, 16) ^ int(n2, 16)
        
        sorted_nodes = sorted(all_nodes, key=lambda n: distance(n.node_id, target_id))
        return sorted_nodes[:8]  # 返回最近的8个节点
    
    def handle_message(self, message: Message, addr: tuple[str, int]):
        """处理接收到的消息"""
        logger.debug(f"Received {message.msg_type} from {addr}")
        
        # 调用注册的处理器
        handler = self._message_handlers.get(message.msg_type)
        if handler:
            try:
                asyncio.create_task(handler(message, addr))
            except Exception as e:
                logger.error(f"Handler error for {message.msg_type}: {e}")
    
    async def create_handshake(self, target: NetworkAddress) -> Message:
        """创建握手消息"""
        return Message(
            msg_type=self.MSG_HANDSHAKE,
            source_id=self.node_id,
            payload={
                "version": PROTOCOL_VERSION,
                "timestamp": time.time()
            }
        )
    
    async def create_ping(self) -> Message:
        """创建ping消息"""
        return Message(
            msg_type=self.MSG_PING,
            source_id=self.node_id,
            payload={"timestamp": time.time()}
        )
    
    async def relay_message(self, target_id: str, message: Message) -> bool:
        """通过中继发送消息"""
        # 查找目标节点
        target_nodes = await self.find_node(target_id)
        if not target_nodes:
            logger.warning(f"No route to {target_id}")
            return False
        
        # 转发到最近的节点
        relay_msg = Message(
            msg_type=self.MSG_RELAY,
            source_id=self.node_id,
            target_id=target_id,
            payload={
                "original_msg": message.to_bytes().decode('latin-1'),
                "target_id": target_id
            }
        )
        
        for node in target_nodes:
            if node.public_addr:
                return await self.send_message(
                    (node.public_addr.ip, node.public_addr.port),
                    relay_msg
                )
        
        return False


class P2PProtocolHandler(asyncio.DatagramProtocol):
    """P2P协议处理器"""
    
    def __init__(self, protocol: P2PProtocol):
        super().__init__()
        self.protocol = protocol
    
    def datagram_received(self, data: bytes, addr: tuple[str, int]):
        """处理接收到的UDP数据报"""
        try:
            message = Message.from_bytes(data)
            self.protocol.handle_message(message, addr)
        except Exception as e:
            logger.error(f"Failed to parse message from {addr}: {e}")
    
    def error_received(self, exc):
        """处理套接字错误"""
        logger.error(f"Socket error: {exc}")


class P2PNode:
    """P2P节点封装"""
    
    def __init__(
        self,
        node_id: str,
        user_id: Optional[str] = None,
        udp_port: int = DEFAULT_UDP_PORT,
        tcp_port: int = DEFAULT_TCP_PORT
    ):
        self.node_id = node_id
        self.user_id = user_id
        self.udp_port = udp_port
        self.tcp_port = tcp_port
        
        self.protocol = P2PProtocol(node_id, udp_port)
        self.local_addr: Optional[NetworkAddress] = None
        self.public_addr: Optional[NetworkAddress] = None
        self.is_running = False
        
        # 连接状态
        self.connected_peers: dict[str, PeerNode] = {}
        self._connection_lock = asyncio.Lock()
        
        # TCP服务器（用于接收连接）
        self.tcp_server: Optional[asyncio.Server] = None
    
    async def start(self):
        """启动节点"""
        await self.protocol.start()
        self.is_running = True
        
        # 获取本地地址
        self.local_addr = NetworkAddress(
            ip=self._get_local_ip(),
            port=self.udp_port
        )
        
        # 启动TCP监听
        await self._start_tcp_server()
        
        logger.info(f"P2P Node {self.node_id} started")
        logger.info(f"  Local: {self.local_addr}")
    
    async def stop(self):
        """停止节点"""
        self.is_running = False
        
        # 关闭TCP服务器
        if self.tcp_server:
            self.tcp_server.close()
            await self.tcp_server.wait_closed()
        
        # 停止协议
        await self.protocol.stop()
        
        logger.info(f"P2P Node {self.node_id} stopped")
    
    async def connect_to_peer(self, addr: NetworkAddress) -> bool:
        """连接到对等节点"""
        try:
            # 发送握手
            handshake = await self.protocol.create_handshake(addr)
            success = await self.protocol.send_message(
                (addr.ip, addr.port),
                handshake
            )
            
            if success:
                logger.info(f"Handshake sent to {addr}")
            
            return success
        except Exception as e:
            logger.error(f"Failed to connect to {addr}: {e}")
            return False
    
    async def disconnect_peer(self, peer_id: str):
        """断开与对等节点的连接"""
        async with self._connection_lock:
            if peer_id in self.connected_peers:
                del self.connected_peers[peer_id]
                logger.info(f"Disconnected from peer {peer_id}")
    
    async def send_to_peer(self, peer_id: str, message: Message) -> bool:
        """发送消息到指定对等节点"""
        async with self._connection_lock:
            peer = self.connected_peers.get(peer_id)
        
        if not peer or not peer.public_addr:
            # 尝试通过路由发送
            return await self.protocol.relay_message(peer_id, message)
        
        return await self.protocol.send_message(
            (peer.public_addr.ip, peer.public_addr.port),
            message
        )
    
    async def broadcast_to_peers(self, message: Message):
        """广播消息到所有对等节点"""
        await self.protocol.broadcast(message)
    
    async def _start_tcp_server(self):
        """启动TCP服务器"""
        async def tcp_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            addr = writer.get_extra_info('peername')
            logger.debug(f"TCP connection from {addr}")
            
            try:
                # 读取数据
                data = await reader.read(1024 * 1024)  # 最大1MB
                if data:
                    await self._handle_tcp_data(data, addr, writer)
            except Exception as e:
                logger.error(f"TCP handler error: {e}")
            finally:
                writer.close()
                await writer.wait_closed()
        
        self.tcp_server = await asyncio.start_server(
            tcp_handler,
            host='0.0.0.0',
            port=self.tcp_port
        )
        logger.info(f"TCP server listening on port {self.tcp_port}")
    
    async def _handle_tcp_data(
        self,
        data: bytes,
        addr: tuple[str, int],
        writer: asyncio.StreamWriter
    ):
        """处理TCP数据"""
        # 这里可以处理文件传输等大块数据
        pass
    
    def _get_local_ip(self) -> str:
        """获取本地IP地址"""
        try:
            # 创建UDP套接字连接到外部地址来获取本地IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def get_peer_count(self) -> int:
        """获取连接的对等节点数量"""
        return len(self.connected_peers)
    
    def get_stats(self) -> dict:
        """获取节点统计信息"""
        return {
            "node_id": self.node_id,
            "user_id": self.user_id,
            "local_addr": str(self.local_addr) if self.local_addr else None,
            "public_addr": str(self.public_addr) if self.public_addr else None,
            "peer_count": self.get_peer_count(),
            "is_running": self.is_running
        }


# ============= 便捷函数 =============

async def create_node(
    node_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> P2PNode:
    """创建并启动P2P节点"""
    import uuid
    
    node = P2PNode(
        node_id=node_id or uuid.uuid4().hex[:12],
        user_id=user_id
    )
    await node.start()
    return node
