"""
自适应连接管理系统

连接池管理、智能心跳、负载均衡
from __future__ import annotations
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from collections import deque
import asyncio
import threading
import time
import logging
import random

logger = logging.getLogger(__name__)


class ConnectionType(Enum):
    """连接类型"""
    DIRECT = "direct"           # 直连
    PROXY = "proxy"             # 代理
    RELAY = "relay"             # 中继
    TUNNEL = "tunnel"           # 隧道


@dataclass
class RelayConfig:
    """中继服务器配置"""
    host: str = "139.199.124.242"
    port: int = 8888
    name: str = "腾讯云服务器"
    region: str = "华南"
    enabled: bool = True
    use_websocket: bool = True
    ssl_enabled: bool = False
    api_key: str = ""
    
    # 连接参数
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    heartbeat_interval: float = 30.0
    
    # 负载限制
    max_connections: int = 100
    current_connections: int = 0
    
    # 统计
    latency: float = 0
    success_rate: float = 1.0
    last_check: datetime = field(default_factory=datetime.now)
    
    @property
    def is_available(self) -> bool:
        """是否可用"""
        return (
            self.enabled and
            self.current_connections < self.max_connections and
            self.success_rate > 0.3
        )
    
    @property
    def quality_score(self) -> float:
        """质量分数"""
        score = 100
        score -= min(self.latency / 50, 40)
        score -= (1 - self.success_rate) * 30
        if self.current_connections >= self.max_connections * 0.9:
            score -= 20
        return max(0, min(100, score))


class ConnectionStatus(Enum):
    """连接状态"""
    IDLE = "idle"
    CONNECTING = "connecting"
    ACTIVE = "active"
    BUSY = "busy"
    WARMING = "warming"         # 预热中
    COOLING = "cooling"         # 冷却中
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class ConnectionInfo:
    """连接信息"""
    connection_id: str
    connection_type: ConnectionType
    remote_host: str
    remote_port: int
    local_host: str = ""
    local_port: int = 0
    
    status: ConnectionStatus = ConnectionStatus.IDLE
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    
    # 统计
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    error_count: int = 0
    
    # 质量指标
    avg_latency: float = 0
    success_rate: float = 1.0
    
    # 优先级
    priority: int = 0
    in_pool: bool = False
    
    # 扩展数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectionPoolConfig:
    """连接池配置"""
    min_size: int = 5           # 最小连接数
    max_size: int = 50          # 最大连接数
    max_idle_time: float = 300  # 最大空闲时间（秒）
    max_lifetime: float = 3600  # 最大生命周期（秒）
    acquire_timeout: float = 10  # 获取连接超时（秒）
    idle_timeout: float = 60    # 空闲超时（秒）
    health_check_interval: float = 30  # 健康检查间隔（秒）
    warmup_enabled: bool = True  # 预热启用
    cooldown_enabled: bool = True  # 冷却启用


class AdaptiveConnectionPool:
    """
    自适应连接池
    
    Features:
    - 动态池大小调整
    - 连接预热与冷却
    - 智能心跳
    - 负载均衡
    """
    
    def __init__(self, config: ConnectionPoolConfig = None):
        self.config = config or ConnectionPoolConfig()
        self._lock = threading.RLock()
        self._running = False
        
        # 连接存储
        self._connections: Dict[str, ConnectionInfo] = {}
        self._available: deque = deque()  # 可用连接队列
        self._busy: set = set()           # 忙碌连接
        self._warming: Dict[str, ConnectionInfo] = {}  # 预热中
        self._cooling: Dict[str, ConnectionInfo] = {}   # 冷却中
        
        # 中继服务器配置
        self._relay_configs: Dict[str, RelayConfig] = {}
        
        # 统计
        self._stats = {
            "total_created": 0,
            "total_closed": 0,
            "total_acquired": 0,
            "total_released": 0,
            "total_errors": 0,
            "peak_size": 0,
        }
        
        # 监听器
        self._listeners: List[Callable] = []
        
        # 心跳任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        
        # 初始化默认中继服务器
        self._init_default_relay_server()
    
    def _init_default_relay_server(self):
        """初始化默认中继服务器"""
        self._relay_configs["139.199.124.242"] = RelayConfig(
            host="139.199.124.242",
            port=8888,
            name="腾讯云服务器",
            region="华南",
        )
    
    async def start(self):
        """启动连接池"""
        self._running = True
        
        # 初始化连接
        await self._initialize_connections()
        
        # 启动心跳
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        # 启动健康检查
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info(f"Connection pool started with {len(self._connections)} connections")
    
    async def stop(self):
        """停止连接池"""
        self._running = False
        
        # 取消任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._health_check_task:
            self._health_check_task.cancel()
        
        # 关闭所有连接
        with self._lock:
            for conn in self._connections.values():
                conn.status = ConnectionStatus.CLOSING
                await self._close_connection(conn)
            
            self._connections.clear()
            self._available.clear()
            self._busy.clear()
            self._warming.clear()
            self._cooling.clear()
        
        logger.info("Connection pool stopped")
    
    async def _initialize_connections(self):
        """初始化连接"""
        for i in range(self.config.min_size):
            conn = await self._create_connection()
            if conn:
                self._available.append(conn.connection_id)
    
    async def _create_connection(
        self,
        connection_type: ConnectionType = ConnectionType.DIRECT,
        remote_host: str = "",
        remote_port: int = 0
    ) -> Optional[ConnectionInfo]:
        """创建新连接"""
        conn_id = f"conn_{self._stats['total_created'] + 1}_{int(time.time() * 1000)}"
        
        conn = ConnectionInfo(
            connection_id=conn_id,
            connection_type=connection_type,
            remote_host=remote_host,
            remote_port=remote_port,
            status=ConnectionStatus.CONNECTING,
        )
        
        try:
            # 实际创建连接（简化实现）
            await asyncio.sleep(0.01)
            
            conn.status = ConnectionStatus.ACTIVE
            conn.last_active = datetime.now()
            conn.last_heartbeat = datetime.now()
            
            with self._lock:
                self._connections[conn_id] = conn
                self._stats["total_created"] += 1
                self._stats["peak_size"] = max(self._stats["peak_size"], len(self._connections))
            
            return conn
            
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            conn.status = ConnectionStatus.ERROR
            conn.error_count += 1
            return None
    
    async def _close_connection(self, conn: ConnectionInfo):
        """关闭连接"""
        conn.status = ConnectionStatus.CLOSING
        try:
            # 实际关闭连接
            await asyncio.sleep(0.01)
            
            conn.status = ConnectionStatus.CLOSED
            self._stats["total_closed"] += 1
            
        except Exception as e:
            logger.error(f"Failed to close connection {conn.connection_id}: {e}")
    
    async def acquire(self, timeout: float = None) -> Optional[ConnectionInfo]:
        """
        获取连接
        
        Args:
            timeout: 超时时间
            
        Returns:
            ConnectionInfo or None
        """
        timeout = timeout or self.config.acquire_timeout
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            conn = await self._get_available_connection()
            if conn:
                self._stats["total_acquired"] += 1
                return conn
            
            # 尝试创建新连接
            if len(self._connections) < self.config.max_size:
                conn = await self._create_connection()
                if conn:
                    self._stats["total_acquired"] += 1
                    return conn
            
            await asyncio.sleep(0.1)
        
        logger.warning("Failed to acquire connection within timeout")
        return None
    
    async def _get_available_connection(self) -> Optional[ConnectionInfo]:
        """获取可用连接"""
        with self._lock:
            # 检查可用队列
            while self._available:
                conn_id = self._available.popleft()
                conn = self._connections.get(conn_id)
                
                if conn and conn.status in [ConnectionStatus.IDLE, ConnectionStatus.ACTIVE]:
                    conn.last_active = datetime.now()
                    self._busy.add(conn_id)
                    return conn
            
            return None
    
    async def release(self, conn: ConnectionInfo):
        """释放连接回池"""
        conn_id = conn.connection_id
        
        with self._lock:
            if conn_id in self._busy:
                self._busy.remove(conn_id)
            
            # 检查是否应该关闭
            if self._should_close(conn):
                await self._close_connection(conn)
                return
            
            # 返回可用队列
            conn.status = ConnectionStatus.IDLE
            self._available.append(conn_id)
            self._stats["total_released"] += 1
        
        self._notify_listeners("release", conn)
    
    def _should_close(self, conn: ConnectionInfo) -> bool:
        """判断是否应该关闭连接"""
        now = datetime.now()
        
        # 超过最大生命周期
        lifetime = (now - conn.created_at).total_seconds()
        if lifetime > self.config.max_lifetime:
            return True
        
        # 错误率过高
        if conn.packets_sent > 10 and conn.success_rate < 0.5:
            return True
        
        # 连接池过大
        if len(self._connections) > self.config.max_size:
            return True
        
        return False
    
    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._running:
            try:
                await self._send_heartbeats()
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
            
            await asyncio.sleep(30)  # 每30秒心跳
    
    async def _send_heartbeats(self):
        """发送心跳"""
        now = datetime.now()
        
        with self._lock:
            for conn in self._connections.values():
                if conn.status == ConnectionStatus.ACTIVE:
                    elapsed = (now - conn.last_heartbeat).total_seconds()
                    if elapsed > 60:  # 超过1分钟没心跳
                        try:
                            # 发送心跳
                            conn.last_heartbeat = now
                        except Exception as e:
                            conn.error_count += 1
                            self._stats["total_errors"] += 1
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self._running:
            try:
                await self._do_health_check()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            await asyncio.sleep(self.config.health_check_interval)
    
    async def _do_health_check(self):
        """执行健康检查"""
        with self._lock:
            to_remove = []
            
            for conn in self._connections.values():
                now = datetime.now()
                
                # 检查空闲超时
                if conn.status == ConnectionStatus.IDLE:
                    idle_time = (now - conn.last_active).total_seconds()
                    if idle_time > self.config.max_idle_time:
                        if len(self._connections) > self.config.min_size:
                            to_remove.append(conn)
                            continue
                
                # 检查错误率
                if conn.error_count > 10:
                    to_remove.append(conn)
                    continue
            
            # 关闭不需要的连接
            for conn in to_remove:
                await self._close_connection(conn)
    
    def get_connection(self, connection_id: str) -> Optional[ConnectionInfo]:
        """获取连接信息"""
        with self._lock:
            return self._connections.get(connection_id)
    
    def get_all_connections(self) -> List[ConnectionInfo]:
        """获取所有连接"""
        with self._lock:
            return list(self._connections.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "pool_size": len(self._connections),
                "available": len(self._available),
                "busy": len(self._busy),
                "warming": len(self._warming),
                "cooling": len(self._cooling),
                "stats": self._stats.copy(),
            }
    
    def subscribe(self, callback: Callable):
        """订阅事件"""
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)
    
    def _notify_listeners(self, event: str, data: Any):
        """通知监听器"""
        for listener in self._listeners:
            try:
                listener(event, data)
            except Exception as e:
                logger.error(f"Listener error: {e}")
    
    # ==================== 中继连接 ====================
    
    def add_relay_server(
        self,
        host: str,
        port: int = 8888,
        name: str = "",
        region: str = "",
        api_key: str = "",
    ) -> RelayConfig:
        """
        添加中继服务器
        
        Args:
            host: 主机地址
            port: 端口
            name: 名称
            region: 区域
            api_key: API密钥
            
        Returns:
            RelayConfig
        """
        relay = RelayConfig(
            host=host,
            port=port,
            name=name or f"Relay-{host}",
            region=region,
            api_key=api_key,
        )
        
        with self._lock:
            self._relay_configs[host] = relay
        
        logger.info(f"Added relay server: {relay.name} ({host}:{port})")
        return relay
    
    def remove_relay_server(self, host: str):
        """移除中继服务器"""
        with self._lock:
            if host in self._relay_configs:
                del self._relay_configs[host]
                logger.info(f"Removed relay server: {host}")
    
    def get_relay_server(self, host: str) -> Optional[RelayConfig]:
        """获取中继服务器配置"""
        with self._lock:
            return self._relay_configs.get(host)
    
    def get_all_relay_servers(self) -> List[RelayConfig]:
        """获取所有中继服务器"""
        with self._lock:
            return list(self._relay_configs.values())
    
    def get_best_relay_server(self) -> Optional[RelayConfig]:
        """获取最佳中继服务器"""
        with self._lock:
            available = [r for r in self._relay_configs.values() if r.is_available]
            if not available:
                return None
            return max(available, key=lambda r: r.quality_score)
    
    async def create_relay_connection(
        self,
        relay: RelayConfig = None,
    ) -> Optional[ConnectionInfo]:
        """
        创建中继连接
        
        Args:
            relay: 中继服务器配置（None表示自动选择）
            
        Returns:
            ConnectionInfo 或 None
        """
        if relay is None:
            relay = self.get_best_relay_server()
        
        if not relay:
            logger.warning("No available relay server")
            return None
        
        conn = await self._create_connection(
            connection_type=ConnectionType.RELAY,
            remote_host=relay.host,
            remote_port=relay.port,
        )
        
        if conn:
            conn.metadata = {"relay_config": relay}
            relay.current_connections += 1
        
        return conn
    
    async def connect_to_relay(
        self,
        peer_id: str,
        relay: RelayConfig = None,
    ) -> bool:
        """
        连接到中继服务器
        
        Args:
            peer_id: 节点ID
            relay: 中继服务器（None表示自动选择）
            
        Returns:
            是否成功
        """
        if relay is None:
            relay = self.get_best_relay_server()
        
        if not relay:
            return False
        
        try:
            # 根据协议选择连接方式
            if relay.use_websocket:
                # WebSocket 连接
                pass  # 实际实现使用 websockets 库
            else:
                # TCP 连接
                pass  # 实际实现使用 asyncio
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect to relay: {e}")
            return False
    
    def update_relay_stats(
        self,
        host: str,
        latency: float = None,
        success: bool = None,
    ):
        """
        更新中继服务器统计
        
        Args:
            host: 服务器地址
            latency: 延迟
            success: 是否成功
        """
        with self._lock:
            relay = self._relay_configs.get(host)
            if relay:
                if latency is not None:
                    if relay.latency > 0:
                        relay.latency = relay.latency * 0.7 + latency * 0.3
                    else:
                        relay.latency = latency
                
                if success is not None:
                    if success:
                        relay.success_rate = relay.success_rate * 0.9 + 0.1
                    else:
                        relay.success_rate = relay.success_rate * 0.9
                
                relay.last_check = datetime.now()


@dataclass
class LoadBalancerConfig:
    """负载均衡配置"""
    strategy: str = "round_robin"  # round_robin, weighted, least_connections, ip_hash
    health_check_enabled: bool = True
    retry_enabled: bool = True
    max_retries: int = 3


class ConnectionLoadBalancer:
    """
    连接负载均衡器
    
    在多个连接/节点之间分配负载
    """
    
    def __init__(self, config: LoadBalancerConfig = None):
        self.config = config or LoadBalancerConfig()
        self._lock = threading.Lock()
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._current_index = 0
        self._request_counts: Dict[str, int] = {}
    
    def add_node(
        self,
        node_id: str,
        host: str,
        port: int,
        weight: int = 1,
        max_connections: int = 100
    ):
        """添加节点"""
        with self._lock:
            self._nodes[node_id] = {
                "node_id": node_id,
                "host": host,
                "port": port,
                "weight": weight,
                "max_connections": max_connections,
                "current_connections": 0,
                "healthy": True,
                "last_check": datetime.now(),
            }
            self._request_counts[node_id] = 0
    
    def remove_node(self, node_id: str):
        """移除节点"""
        with self._lock:
            self._nodes.pop(node_id, None)
            self._request_counts.pop(node_id, None)
    
    def get_best_node(self) -> Optional[Tuple[str, str, int]]:
        """
        获取最优节点
        
        Returns:
            (node_id, host, port) or None
        """
        with self._lock:
            healthy_nodes = [n for n in self._nodes.values() if n["healthy"]]
            
            if not healthy_nodes:
                return None
            
            if self.config.strategy == "round_robin":
                return self._round_robin(healthy_nodes)
            elif self.config.strategy == "weighted":
                return self._weighted(healthy_nodes)
            elif self.config.strategy == "least_connections":
                return self._least_connections(healthy_nodes)
            else:
                return self._round_robin(healthy_nodes)
    
    def _round_robin(self, nodes: List[Dict]) -> Optional[Tuple]:
        """轮询策略"""
        if not nodes:
            return None
        
        node = nodes[self._current_index % len(nodes)]
        self._current_index += 1
        return (node["node_id"], node["host"], node["port"])
    
    def _weighted(self, nodes: List[Dict]) -> Optional[Tuple]:
        """加权策略"""
        if not nodes:
            return None
        
        total_weight = sum(n["weight"] for n in nodes)
        rand = random.randint(1, total_weight)
        
        cumulative = 0
        for node in nodes:
            cumulative += node["weight"]
            if rand <= cumulative:
                return (node["node_id"], node["host"], node["port"])
        
        return (nodes[0]["node_id"], nodes[0]["host"], nodes[0]["port"])
    
    def _least_connections(self, nodes: List[Dict]) -> Optional[Tuple]:
        """最小连接数策略"""
        if not nodes:
            return None
        
        node = min(nodes, key=lambda n: n["current_connections"])
        return (node["node_id"], node["host"], node["port"])
    
    def record_request(self, node_id: str):
        """记录请求"""
        with self._lock:
            if node_id in self._request_counts:
                self._request_counts[node_id] += 1
            if node_id in self._nodes:
                self._nodes[node_id]["current_connections"] += 1
    
    def record_response(self, node_id: str, success: bool = True):
        """记录响应"""
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id]["current_connections"] = max(0, self._nodes[node_id]["current_connections"] - 1)
                if not success:
                    self._nodes[node_id]["healthy"] = False
    
    def set_node_healthy(self, node_id: str, healthy: bool):
        """设置节点健康状态"""
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id]["healthy"] = healthy
                self._nodes[node_id]["last_check"] = datetime.now()


# 单例实例
_connection_pool: Optional[AdaptiveConnectionPool] = None
_load_balancer: Optional[ConnectionLoadBalancer] = None


def get_connection_pool() -> AdaptiveConnectionPool:
    """获取连接池"""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = AdaptiveConnectionPool()
    return _connection_pool


def get_load_balancer() -> ConnectionLoadBalancer:
    """获取负载均衡器"""
    global _load_balancer
    if _load_balancer is None:
        _load_balancer = ConnectionLoadBalancer()
    return _load_balancer


__all__ = [
    "ConnectionType",
    "ConnectionStatus",
    "ConnectionInfo",
    "ConnectionPoolConfig",
    "RelayConfig",
    "AdaptiveConnectionPool",
    "LoadBalancerConfig",
    "ConnectionLoadBalancer",
    "get_connection_pool",
    "get_load_balancer",
]
