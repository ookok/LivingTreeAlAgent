"""
中继服务器模块

提供节点注册、消息转发、穿透辅助服务
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from typing import Optional

from .models import (
    PeerNode, NetworkAddress, NodeRole, RelayServer,
    Message, DEFAULT_RELAY_PORT, RELAY_HEARTBEAT_INTERVAL, RELAY_TIMEOUT
)

logger = logging.getLogger(__name__)


class RelayHandler:
    """中继消息处理器"""
    
    def __init__(self, server: RelayService):
        self.server = server
    
    async def handle_register(self, node_id: str, addr: tuple[str, int], data: dict) -> str:
        """处理节点注册"""
        node = PeerNode(
            node_id=node_id,
            public_addr=NetworkAddress(ip=addr[0], port=addr[1]),
            role=NodeRole(data.get("role", 0)),
            is_online=True
        )
        
        await self.server.register_node(node)
        bootstrap_nodes = self.server.get_bootstrap_nodes()
        node_list = "|".join([f"{n.public_addr}" for n in bootstrap_nodes[:5]])
        return f"REGISTERED|{node.node_id}|{node_list}"
    
    async def handle_unregister(self, node_id: str) -> str:
        """处理节点注销"""
        await self.server.unregister_node(node_id)
        return "UNREGISTERED"
    
    async def handle_relay(
        self,
        source_id: str,
        target_id: str,
        data: bytes
    ) -> bool:
        """处理消息中继"""
        target_node = await self.server.get_node(target_id)
        
        if not target_node or not target_node.is_online:
            await self.server.store_pending_message(source_id, target_id, data)
            return False
        
        return await self.server.forward_to_node(target_id, data)
    
    async def handle_find_node(self, node_id: str, target_id: str) -> list[str]:
        """处理节点查找请求"""
        nodes = await self.server.find_nearest_nodes(target_id)
        return [f"{n.node_id}:{n.public_addr}" for n in nodes]
    
    async def handle_heartbeat(self, node_id: str) -> str:
        """处理心跳"""
        await self.server.update_heartbeat(node_id)
        return f"ALIVE|{time.time()}"
    
    async def handle_announce(self, node_id: str, addr: tuple[str, int]) -> str:
        """处理节点宣告"""
        await self.server.announce_node(node_id, addr)
        return "ANNOUNCED"


class RelayService:
    """中继服务"""
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = DEFAULT_RELAY_PORT,
        max_connections: int = 1000
    ):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        
        self.nodes: dict[str, PeerNode] = {}
        self.node_addresses: dict[str, tuple[str, int]] = {}
        self.pending_messages: dict[str, list[tuple[bytes, float]]] = {}
        self.active_connections: dict[str, float] = {}
        self.connection_limit = max_connections
        self.relay_servers: list[RelayServer] = []
        self.bootstrap_nodes: list[PeerNode] = []
        
        self.stats = {
            "total_connections": 0,
            "total_messages_relayed": 0,
            "total_bytes_relayed": 0,
            "peak_connections": 0
        }
        
        self.handler = RelayHandler(self)
        self.server: Optional[asyncio.Server] = None
        self.running = False
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动中继服务器"""
        self.running = True
        
        async def client_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            addr = writer.get_extra_info('peername')
            conn_id = f"{addr[0]}:{addr[1]}:{time.time()}"
            self.stats["total_connections"] += 1
            
            try:
                self.active_connections[conn_id] = time.time()
                
                if len(self.active_connections) > self.connection_limit:
                    writer.write(b"ERROR|SERVER_FULL\n")
                    await writer.drain()
                    return
                
                await self._handle_client(reader, writer, addr)
                
            except Exception as e:
                logger.error(f"Client handler error: {e}")
            finally:
                if conn_id in self.active_connections:
                    del self.active_connections[conn_id]
                writer.close()
                await writer.wait_closed()
        
        self.server = await asyncio.start_server(client_handler, host=self.host, port=self.port)
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info(f"Relay server started on {self.host}:{self.port}")
    
    async def stop(self):
        """停止中继服务器"""
        self.running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("Relay server stopped")
    
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        addr: tuple[str, int]
    ):
        """处理客户端连接"""
        while self.running:
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=300)
                if not line:
                    break
                
                line = line.decode().strip()
                parts = line.split('|', 1)
                cmd = parts[0]
                
                if cmd == "REGISTER":
                    node_id = parts[1].split('|')[0] if '|' in parts[1] else parts[1]
                    role = int(parts[1].split('|')[1]) if '|' in parts[1] else 0
                    response = await self.handler.handle_register(node_id, addr, {"role": role})
                    writer.write(f"{response}\n".encode())
                
                elif cmd == "UNREGISTER":
                    node_id = parts[1]
                    response = await self.handler.handle_unregister(node_id)
                    writer.write(f"{response}\n".encode())
                
                elif cmd == "RELAY":
                    meta = parts[1].split('|')
                    target_id = meta[0]
                    data_len = int(meta[1])
                    data = await reader.read(data_len)
                    success = await self.handler.handle_relay(addr[0], target_id, data)
                    writer.write(f"RELAYED|{success}\n".encode())
                    self.stats["total_messages_relayed"] += 1
                    self.stats["total_bytes_relayed"] += data_len
                
                elif cmd == "FIND_NODE":
                    target_id = parts[1]
                    nodes = await self.handler.handle_find_node(addr[0], target_id)
                    response = f"NODES|{','.join(nodes)}"
                    writer.write(f"{response}\n".encode())
                
                elif cmd == "PING":
                    response = f"PONG|{time.time()}"
                    writer.write(f"{response}\n".encode())
                
                elif cmd == "ANNOUNCE":
                    node_id = parts[1]
                    response = await self.handler.handle_announce(node_id, addr)
                    writer.write(f"{response}\n".encode())
                
                elif cmd == "GET_PENDING":
                    node_id = parts[1]
                    messages = await self.get_pending_messages(node_id)
                    writer.write(f"PENDING_COUNT|{len(messages)}\n".encode())
                    for msg_data in messages:
                        writer.write(f"MESSAGE|{len(msg_data)}\n".encode())
                        writer.write(msg_data)
                
                else:
                    writer.write(b"UNKNOWN_COMMAND\n")
                
                await writer.drain()
                
            except asyncio.TimeoutError:
                break
            except Exception as e:
                logger.error(f"Client error: {e}")
                break
    
    async def register_node(self, node: PeerNode):
        """注册节点"""
        self.nodes[node.node_id] = node
        self.node_addresses[node.node_id] = (node.public_addr.ip, node.public_addr.port)
        node.last_heartbeat = time.time()
        node.is_online = True
        self.stats["peak_connections"] = max(self.stats["peak_connections"], len(self.active_connections))
        logger.debug(f"Node registered: {node.node_id}")
    
    async def unregister_node(self, node_id: str):
        """注销节点"""
        if node_id in self.nodes:
            self.nodes[node_id].is_online = False
            del self.nodes[node_id]
        if node_id in self.node_addresses:
            del self.node_addresses[node_id]
        logger.debug(f"Node unregistered: {node_id}")
    
    async def update_heartbeat(self, node_id: str):
        """更新节点心跳"""
        if node_id in self.nodes:
            self.nodes[node_id].touch()
    
    async def announce_node(self, node_id: str, addr: tuple[str, int]):
        """宣告节点存在"""
        if node_id in self.nodes:
            self.nodes[node_id].public_addr = NetworkAddress(ip=addr[0], port=addr[1])
            self.nodes[node_id].touch()
    
    async def get_node(self, node_id: str) -> Optional[PeerNode]:
        """获取节点信息"""
        return self.nodes.get(node_id)
    
    async def find_nearest_nodes(self, target_id: str, limit: int = 8) -> list[PeerNode]:
        """查找最近的节点"""
        if not self.nodes:
            return []
        
        def distance(n1: str, n2: str) -> int:
            try:
                return int(n1, 16) ^ int(n2, 16)
            except ValueError:
                return len(n1) ^ len(n2)
        
        online_nodes = [n for n in self.nodes.values() if n.is_online]
        sorted_nodes = sorted(online_nodes, key=lambda n: distance(n.node_id, target_id))
        return sorted_nodes[:limit]
    
    async def forward_to_node(self, node_id: str, data: bytes) -> bool:
        """转发数据到节点"""
        if node_id not in self.node_addresses:
            return False
        
        addr = self.node_addresses[node_id]
        
        try:
            reader, writer = await asyncio.open_connection(addr[0], addr[1])
            header = f"RELAY_FROM|{len(data)}\n"
            writer.write(header.encode() + data)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:
            logger.error(f"Forward to {node_id} failed: {e}")
            return False
    
    async def store_pending_message(self, source_id: str, target_id: str, data: bytes):
        """存储待转发消息"""
        if target_id not in self.pending_messages:
            self.pending_messages[target_id] = []
        self.pending_messages[target_id].append((data, time.time()))
        if len(self.pending_messages[target_id]) > 100:
            self.pending_messages[target_id] = self.pending_messages[target_id][-100:]
    
    async def get_pending_messages(self, node_id: str) -> list[bytes]:
        """获取待转发消息"""
        messages = self.pending_messages.get(node_id, [])
        self.pending_messages[node_id] = []
        return [m[0] for m in messages]
    
    def get_bootstrap_nodes(self) -> list[PeerNode]:
        """获取引导节点列表"""
        return [n for n in self.nodes.values() if n.role == NodeRole.BOOTSTRAP]
    
    async def _cleanup_loop(self):
        """清理过期节点"""
        while self.running:
            try:
                await asyncio.sleep(RELAY_HEARTBEAT_INTERVAL)
                now = time.time()
                expired = [nid for nid, n in self.nodes.items() if now - n.last_heartbeat > RELAY_TIMEOUT]
                for node_id in expired:
                    await self.unregister_node(node_id)
                
                for node_id in list(self.pending_messages.keys()):
                    self.pending_messages[node_id] = [(d, ts) for d, ts in self.pending_messages[node_id] if now - ts < 3600]
                    if not self.pending_messages[node_id]:
                        del self.pending_messages[node_id]
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    def get_stats(self) -> dict:
        """获取服务器统计"""
        return {
            **self.stats,
            "online_nodes": len(self.nodes),
            "active_connections": len(self.active_connections),
            "pending_messages": sum(len(m) for m in self.pending_messages.values())
        }


async def create_relay_server(host: str = "0.0.0.0", port: int = DEFAULT_RELAY_PORT, max_connections: int = 1000) -> RelayService:
    """创建并启动中继服务器"""
    server = RelayService(host, port, max_connections)
    await server.start()
    return server


class RelayClient:
    """中继客户端"""
    
    def __init__(self, relay_server: str, relay_port: int = DEFAULT_RELAY_PORT):
        self.relay_server = relay_server
        self.relay_port = relay_port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.node_id: Optional[str] = None
        self.is_connected = False
    
    async def connect(self, node_id: str) -> bool:
        """连接到中继服务器"""
        try:
            self.node_id = node_id
            self.reader, self.writer = await asyncio.open_connection(self.relay_server, self.relay_port)
            self.writer.write(f"REGISTER|{node_id}|0\n".encode())
            await self.writer.drain()
            response = await asyncio.wait_for(self.reader.readline(), timeout=5.0)
            response = response.decode().strip()
            if response.startswith("REGISTERED"):
                self.is_connected = True
                logger.info(f"Connected to relay server: {self.relay_server}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to connect to relay: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self.node_id and self.writer:
            try:
                self.writer.write(f"UNREGISTER|{self.node_id}\n".encode())
                await self.writer.drain()
            except Exception:
                pass
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.is_connected = False
    
    async def relay_message(self, target_id: str, data: bytes) -> bool:
        """通过中继发送消息"""
        if not self.is_connected:
            return False
        try:
            header = f"RELAY|{target_id}|{len(data)}\n"
            self.writer.write(header.encode() + data)
            await self.writer.drain()
            response = await asyncio.wait_for(self.reader.readline(), timeout=10.0)
            return response.decode().strip().startswith("RELAYED|True")
        except Exception as e:
            logger.error(f"Relay message failed: {e}")
            return False
    
    async def find_nodes(self, target_id: str) -> list[str]:
        """请求查找节点"""
        if not self.is_connected:
            return []
        try:
            self.writer.write(f"FIND_NODE|{target_id}\n".encode())
            await self.writer.drain()
            response = await asyncio.wait_for(self.reader.readline(), timeout=5.0)
            data = response.decode().strip()
            if data.startswith("NODES|"):
                nodes_str = data[6:]
                return nodes_str.split(',') if nodes_str else []
            return []
        except Exception as e:
            logger.error(f"Find nodes failed: {e}")
            return []
    
    async def get_pending_messages(self) -> list[bytes]:
        """获取待接收的消息"""
        if not self.is_connected or not self.node_id:
            return []
        try:
            self.writer.write(f"GET_PENDING|{self.node_id}\n".encode())
            await self.writer.drain()
            response = await asyncio.wait_for(self.reader.readline(), timeout=5.0)
            data = response.decode().strip()
            if data.startswith("PENDING_COUNT|"):
                count = int(data.split('|')[1])
                messages = []
                for _ in range(count):
                    msg_header = await self.reader.readline()
                    if msg_header.decode().startswith("MESSAGE|"):
                        msg_len = int(msg_header.decode().split('|')[1])
                        msg_data = await self.reader.read(msg_len)
                        messages.append(msg_data)
                return messages
            return []
        except Exception as e:
            logger.error(f"Get pending messages failed: {e}")
            return []
