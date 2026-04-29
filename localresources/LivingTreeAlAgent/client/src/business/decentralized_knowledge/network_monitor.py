"""
网络状态监控
Network State Monitor
"""

import asyncio
import logging
import socket
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, List, Dict, Any

logger = logging.getLogger(__name__)


class NetworkState(Enum):
    """网络状态"""
    UNKNOWN = "unknown"
    OFFLINE = "offline"
    P2P_ONLY = "p2p_only"      # 仅P2P可用
    RELAY_ONLY = "relay_only"  # 仅中继可用
    FULL = "full"             # 完全连接


class ConnectionQuality(Enum):
    """连接质量"""
    UNKNOWN = "unknown"
    EXCELLENT = "excellent"   # < 50ms
    GOOD = "good"            # 50-150ms
    FAIR = "fair"            # 150-300ms
    POOR = "poor"            # > 300ms


@dataclass
class ServerInfo:
    """服务器信息"""
    host: str
    port: int
    name: str = ""
    region: str = ""
    latency_ms: float = 0.0
    load: float = 0.0  # 0-1
    is_online: bool = True
    last_check: datetime = None


@dataclass
class NetworkStats:
    """网络统计"""
    state: NetworkState = NetworkState.UNKNOWN
    quality: ConnectionQuality = ConnectionQuality.UNKNOWN
    avg_latency_ms: float = 0.0
    bandwidth_mbps: float = 0.0
    packets_lost: int = 0
    packets_total: int = 0
    connected_peers: int = 0
    active_server: Optional[str] = None


class NetworkMonitor:
    """
    网络状态监控器
    
    功能：
    - 网络状态检测
    - 连接质量评估
    - 服务器健康检查
    - 自动故障转移
    """
    
    # 内置公共STUN服务器
    PUBLIC_STUN_SERVERS = [
        ("stun.l.google.com", 19302),
        ("stun1.l.google.com", 19302),
        ("stun2.l.google.com", 19302),
    ]
    
    # 内置备用中继服务器
    BACKUP_RELAY_SERVERS = [
        ("relay1.hermes-p2p.net", 18890, "Global-1"),
        ("relay2.hermes-p2p.net", 18890, "Global-2"),
    ]
    
    def __init__(self, config: Optional[Any] = None):
        self.config = config
        
        # 状态
        self._state: NetworkState = NetworkState.UNKNOWN
        self._quality: ConnectionQuality = ConnectionQuality.UNKNOWN
        self._running = False
        
        # 服务器列表
        self._servers: Dict[str, ServerInfo] = {}
        self._active_server: Optional[str] = None
        
        # 统计
        self._latency_history: List[float] = []
        self._packet_stats: Dict[str, int] = {'lost': 0, 'total': 0}
        
        # 回调
        self._callbacks: List[Callable[[NetworkState, NetworkState], None]] = []
        
        # 锁
        self._lock = asyncio.Lock()
        
        logger.info("网络监控器初始化完成")
    
    @property
    def state(self) -> NetworkState:
        return self._state
    
    @property
    def quality(self) -> ConnectionQuality:
        return self._quality
    
    async def start_monitoring(self) -> None:
        """启动监控"""
        if self._running:
            return
        
        self._running = True
        
        # 初始化服务器列表
        for host, port, region in self.BACKUP_RELAY_SERVERS:
            self._servers[f"{host}:{port}"] = ServerInfo(
                host=host, port=port, region=region
            )
        
        # 启动监控循环
        asyncio.create_task(self._monitor_loop())
        
        logger.info("网络监控已启动")
    
    async def stop(self) -> None:
        """停止监控"""
        self._running = False
        logger.info("网络监控已停止")
    
    async def check_network_state(self) -> NetworkState:
        """
        检测网络状态
        
        Returns:
            NetworkState: 网络状态
        """
        # 检查互联网连接
        has_internet = await self._check_internet_connection()
        
        if not has_internet:
            new_state = NetworkState.OFFLINE
        else:
            # 检查NAT类型
            nat_type = await self._detect_nat_type()
            
            if nat_type == "public":
                new_state = NetworkState.P2P_ONLY
            elif nat_type == "full_cone":
                new_state = NetworkState.P2P_ONLY
            else:
                # 需要中继服务器
                has_relay = await self._check_relay_servers()
                if has_relay:
                    new_state = NetworkState.FULL
                else:
                    new_state = NetworkState.P2P_ONLY
        
        old_state = self._state
        self._state = new_state
        
        if old_state != new_state:
            logger.info(f"网络状态变化: {old_state} -> {new_state}")
            await self._notify_state_change(old_state, new_state)
        
        return new_state
    
    async def _check_internet_connection(self) -> bool:
        """检查互联网连接"""
        try:
            # 尝试连接DNS服务器
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(
                ("8.8.8.8", 53)
            )
            return True
        except Exception:
            try:
                # 备用方案：连接百度
                socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(
                    ("202.108.22.5", 80)
                )
                return True
            except Exception:
                return False
    
    async def _detect_nat_type(self) -> str:
        """
        检测NAT类型
        
        Returns:
            str: 'public', 'full_cone', 'restricted', 'port_restricted', 'symmetric'
        """
        for host, port in self.PUBLIC_STUN_SERVERS:
            try:
                result = await self._stun_request(host, port)
                if result:
                    return result
            except Exception as e:
                logger.debug(f"STUN检测失败 {host}: {e}")
        
        # 默认返回受限类型
        return "restricted"
    
    async def _stun_request(self, host: str, port: int) -> Optional[str]:
        """发送STUN请求"""
        # 简化的STUN检测
        # 实际应该实现完整的STUN协议
        import struct
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)
            
            # STUN Binding Request
            # 注意：这是简化的实现
            request = b'\x00\x01\x00\x00'  # 类型: Binding Request
            request += b'\x21\x12\xa4\x42'  # Magic Cookie
            request += secrets.token_bytes(12)  # Transaction ID
            
            sock.sendto(request, (host, port))
            
            try:
                data, addr = sock.recvfrom(1024)
                if data:
                    # 简化的响应解析
                    return "restricted"
            except socket.timeout:
                return "symmetric"
            
        except Exception as e:
            logger.debug(f"STUN请求异常: {e}")
        finally:
            sock.close()
        
        return None
    
    async def _check_relay_servers(self) -> bool:
        """检查中继服务器可用性"""
        for server_id, server in self._servers.items():
            try:
                start = datetime.now()
                
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((server.host, server.port))
                
                latency = (datetime.now() - start).total_seconds() * 1000
                
                server.latency_ms = latency
                server.is_online = True
                server.last_check = datetime.now()
                
                self._active_server = server_id
                sock.close()
                
                logger.info(f"中继服务器可用: {server_id}, 延迟: {latency:.1f}ms")
                return True
                
            except Exception as e:
                logger.debug(f"中继服务器不可用: {server_id}, {e}")
                server.is_online = False
        
        return False
    
    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                # 每30秒检测一次网络状态
                await asyncio.sleep(30)
                
                # 检测网络变化
                old_state = self._state
                await self.check_network_state()
                
                if old_state != self._state:
                    continue
                
                # 检查服务器健康
                await self._check_server_health()
                
                # 更新连接质量
                await self._update_connection_quality()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
    
    async def _check_server_health(self) -> None:
        """检查服务器健康状态"""
        for server_id, server in self._servers.items():
            try:
                start = datetime.now()
                
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((server.host, server.port))
                
                latency = (datetime.now() - start).total_seconds() * 1000
                
                server.latency_ms = latency
                server.is_online = True
                server.last_check = datetime.now()
                
                # 更新活跃服务器
                if self._active_server != server_id:
                    # 选择延迟最低的服务器
                    current = self._servers.get(self._active_server)
                    if not current or server.latency_ms < current.latency_ms:
                        self._active_server = server_id
                
                sock.close()
                
            except Exception:
                server.is_online = False
    
    async def _update_connection_quality(self) -> None:
        """更新连接质量评估"""
        if not self._latency_history:
            return
        
        avg_latency = sum(self._latency_history) / len(self._latency_history)
        
        if avg_latency < 50:
            self._quality = ConnectionQuality.EXCELLENT
        elif avg_latency < 150:
            self._quality = ConnectionQuality.GOOD
        elif avg_latency < 300:
            self._quality = ConnectionQuality.FAIR
        else:
            self._quality = ConnectionQuality.POOR
    
    async def measure_latency(self, host: str, port: int = 80) -> Optional[float]:
        """
        测量到主机的延迟
        
        Args:
            host: 主机
            port: 端口
        
        Returns:
            float: 延迟（毫秒）
        """
        try:
            start = datetime.now()
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            sock.close()
            
            latency = (datetime.now() - start).total_seconds() * 1000
            
            # 更新历史
            self._latency_history.append(latency)
            if len(self._latency_history) > 100:
                self._latency_history.pop(0)
            
            return latency
            
        except Exception as e:
            logger.debug(f"延迟测量失败 {host}: {e}")
            return None
    
    def add_callback(self, callback: Callable[[NetworkState, NetworkState], None]) -> None:
        """添加状态变化回调"""
        self._callbacks.append(callback)
    
    async def _notify_state_change(self, old_state: NetworkState, 
                                   new_state: NetworkState) -> None:
        """通知状态变化"""
        for callback in self._callbacks:
            try:
                await callback(old_state, new_state)
            except Exception as e:
                logger.error(f"状态变化回调失败: {e}")
    
    def get_connection_quality(self) -> ConnectionQuality:
        """获取连接质量"""
        return self._quality
    
    def get_avg_latency(self) -> float:
        """获取平均延迟"""
        if not self._latency_history:
            return 0.0
        return sum(self._latency_history) / len(self._latency_history)
    
    def get_stats(self) -> NetworkStats:
        """获取网络统计"""
        return NetworkStats(
            state=self._state,
            quality=self._quality,
            avg_latency_ms=self.get_avg_latency(),
            packets_lost=self._packet_stats['lost'],
            packets_total=self._packet_stats['total'],
            active_server=self._active_server
        )
    
    def get_available_servers(self) -> List[ServerInfo]:
        """获取可用服务器列表"""
        return [s for s in self._servers.values() if s.is_online]
    
    def get_best_server(self) -> Optional[ServerInfo]:
        """获取最佳服务器"""
        available = self.get_available_servers()
        if not available:
            return None
        
        return min(available, key=lambda s: s.latency_ms)


import secrets  # 添加到顶部
