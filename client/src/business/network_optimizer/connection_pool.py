"""
高性能连接池管理

- 连接复用
- 连接预热
- 智能心跳
- 质量评估
- 并发控制
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional
import time

from .models import ConnectionInfo, ConnectionQuality, NetworkTier, NodeInfo


@dataclass
class Connection:
    """
    连接对象
    
    包装底层连接，提供高级功能
    """
    conn_id: str
    peer_id: str
    address: tuple  # (host, port)
    protocol: str = "tcp"
    reader: Optional[asyncio.StreamReader] = None
    writer: Optional[asyncio.StreamWriter] = None
    info: ConnectionInfo = field(init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _heartbeat_task: Optional[asyncio.Task] = None
    _last_ping: float = field(default=0.0, init=False)
    
    def __post_init__(self):
        self.info = ConnectionInfo(
            conn_id=self.conn_id,
            peer_id=self.peer_id,
            peer_node=NodeInfo(node_id=self.peer_id),
            protocol=self.protocol,
        )
    
    async def send(self, data: bytes) -> bool:
        """发送数据"""
        if not self.writer:
            return False
        try:
            async with self._lock:
                self.writer.write(data)
                await self.writer.drain()
                self.info.bytes_sent += len(data)
                self.info.packets_sent += 1
            return True
        except Exception:
            self.info.packets_failed += 1
            return False
    
    async def receive(self, n: int = 65536) -> Optional[bytes]:
        """接收数据"""
        if not self.reader:
            return None
        try:
            data = await asyncio.wait_for(self.reader.read(n), timeout=30)
            if data:
                self.info.bytes_received += len(data)
                self.info.packets_received += 1
            return data
        except Exception:
            return None
    
    async def ping(self) -> Optional[float]:
        """发送心跳并测量延迟"""
        if not self.writer or not self.reader:
            return None
        try:
            start = time.time()
            # 发送简单的ping
            self.writer.write(b"PING")
            await self.writer.drain()
            
            # 等待pong
            data = await asyncio.wait_for(self.reader.read(4), timeout=5)
            if data == b"PONG":
                latency = (time.time() - start) * 1000  # ms
                self._last_ping = latency
                return latency
        except Exception:
            pass
        return None
    
    async def set_priority(self, priority: int):
        """设置连接优先级"""
        self.info.priority = priority
    
    async def close(self):
        """关闭连接"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
    
    @property
    def is_alive(self) -> bool:
        """检查连接是否存活"""
        return (
            self.reader is not None and 
            self.writer is not None and
            not self.writer.is_closing()
        )


@dataclass
class ConnectionPool:
    """
    高性能连接池
    
    Features:
    - 连接复用
    - 连接预热
    - 智能心跳
    - 质量评估
    - 自动清理
    """
    
    max_connections: int = 100
    _connections: dict[str, Connection] = field(default_factory=dict, init=False)
    _peer_connections: dict[str, list[str]] = field(default_factory=dict, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _cleanup_task: Optional[asyncio.Task] = None
    _running: bool = field(default=False, init=False)
    
    @property
    def connections(self) -> list[Connection]:
        return list(self._connections.values())
    
    async def start(self):
        """启动连接池"""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self):
        """停止连接池"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
        await self.close_all()
    
    async def create_connection(
        self,
        peer_id: str,
        address: tuple,
        protocol: str = "tcp",
    ) -> Optional[Connection]:
        """
        创建到目标节点的连接
        
        Args:
            peer_id: 对等节点ID
            address: (host, port)
            protocol: 协议类型 (tcp, udp, quic)
            
        Returns:
            Connection: 新建的连接
        """
        async with self._lock:
            # 检查是否已达上限
            if len(self._connections) >= self.max_connections:
                # 关闭最老的连接
                await self._evict_oldest()
            
            # 创建新连接
            conn_id = str(uuid.uuid4())
            conn = Connection(
                conn_id=conn_id,
                peer_id=peer_id,
                address=address,
                protocol=protocol,
            )
            
            try:
                # 建立TCP连接
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(address[0], address[1]),
                    timeout=10,
                )
                conn.reader = reader
                conn.writer = writer
                
                # 记录连接
                self._connections[conn_id] = conn
                if peer_id not in self._peer_connections:
                    self._peer_connections[peer_id] = []
                self._peer_connections[peer_id].append(conn_id)
                
                # 启动心跳
                conn._heartbeat_task = asyncio.create_task(conn._heartbeat())
                
                return conn
            except Exception:
                return None
    
    async def _heartbeat(self):
        """心跳检测"""
        while self._running and self.is_alive:
            try:
                await asyncio.sleep(30)  # 30秒心跳间隔
                if not self.is_alive:
                    break
                latency = await self.ping()
                if latency is None or latency > 5000:
                    # 连接超时，标记为不活跃
                    self.info.is_active = False
                    break
            except asyncio.CancelledError:
                break
            except Exception:
                pass
    
    async def get_connection(self, peer_id: str) -> Optional[Connection]:
        """
        获取到指定节点的连接
        
        Args:
            peer_id: 对等节点ID
            
        Returns:
            Connection: 可用的连接
        """
        async with self._lock:
            conn_ids = self._peer_connections.get(peer_id, [])
            for conn_id in conn_ids:
                conn = self._connections.get(conn_id)
                if conn and conn.is_alive:
                    return conn
            return None
    
    async def assess_connection_quality(self, address: tuple) -> ConnectionQuality:
        """
        评估到地址的连接质量
        
        Args:
            address: (host, port)
            
        Returns:
            ConnectionQuality: 连接质量
        """
        try:
            start = time.time()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(address[0], address[1]),
                timeout=3,
            )
            latency = (time.time() - start) * 1000
            
            writer.close()
            await writer.wait_closed()
            
            if latency < 50:
                return ConnectionQuality.EXCELLENT
            elif latency < 100:
                return ConnectionQuality.GOOD
            elif latency < 200:
                return ConnectionQuality.FAIR
            elif latency < 500:
                return ConnectionQuality.POOR
            else:
                return ConnectionQuality.BAD
        except Exception:
            return ConnectionQuality.BAD
    
    async def close_connection(self, conn_id: str):
        """关闭指定连接"""
        async with self._lock:
            conn = self._connections.pop(conn_id, None)
            if conn:
                peer_id = conn.peer_id
                if peer_id in self._peer_connections:
                    self._peer_connections[peer_id].remove(conn_id)
                await conn.close()
    
    async def close_all(self):
        """关闭所有连接"""
        async with self._lock:
            for conn in self._connections.values():
                await conn.close()
            self._connections.clear()
            self._peer_connections.clear()
    
    async def _evict_oldest(self):
        """驱逐最老的连接"""
        if not self._connections:
            return
        oldest = min(
            self._connections.values(),
            key=lambda c: c.info.last_active
        )
        await self.close_connection(oldest.conn_id)
    
    async def _cleanup_loop(self):
        """定期清理不活跃连接"""
        while self._running:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self._cleanup_idle()
            except asyncio.CancelledError:
                break
            except Exception:
                pass
    
    async def _cleanup_idle(self):
        """清理不活跃的连接"""
        now = time.time()
        idle_threshold = 300  # 5分钟不活跃
        async with self._lock:
            to_remove = []
            for conn_id, conn in self._connections.items():
                if now - conn.info.last_active > idle_threshold:
                    to_remove.append(conn_id)
            for conn_id in to_remove:
                await self.close_connection(conn_id)
    
    def get_pool_stats(self) -> dict:
        """获取连接池统计"""
        return {
            "total": len(self._connections),
            "max": self.max_connections,
            "active": sum(1 for c in self._connections.values() if c.info.is_active),
            "avg_latency": sum(c.info.avg_latency_ms for c in self._connections.values()) / max(1, len(self._connections)),
            "total_sent": sum(c.info.bytes_sent for c in self._connections.values()),
            "total_received": sum(c.info.bytes_received for c in self._connections.values()),
        }
