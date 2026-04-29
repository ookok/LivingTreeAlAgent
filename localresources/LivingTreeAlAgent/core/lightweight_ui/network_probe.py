"""
智能网络探测系统

网络环境评估、连接方式选择、NAT类型检测
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
import asyncio
import socket
import struct
import random
import logging
import threading
import time

logger = logging.getLogger(__name__)


class NetworkType(Enum):
    """网络类型"""
    LAN = "lan"           # 局域网直连
    P2P = "p2p"          # P2P内网穿透
    RELAY = "relay"       # 中继服务器
    CLOUD = "cloud"       # 云服务
    OFFLINE = "offline"   # 离线模式
    UNKNOWN = "unknown"   # 未知


class NATType(Enum):
    """NAT类型"""
    OPEN = "open"              # 开放网络
    FULL_CONE = "full_cone"   # 全锥型
    RESTRICTED = "restricted" # 受限锥型
    PORT_RESTRICTED = "port_restricted"  # 端口受限锥型
    SYMMETRIC = "symmetric"   # 对称型
    UNKNOWN = "unknown"       # 未知


class ConnectionQuality(Enum):
    """连接质量"""
    EXCELLENT = "excellent"    # < 10ms
    GOOD = "good"              # < 50ms
    FAIR = "fair"              # < 200ms
    POOR = "poor"              # < 500ms
    BAD = "bad"                # >= 500ms


@dataclass
class NetworkProbe:
    """网络探测结果"""
    network_type: NetworkType = NetworkType.UNKNOWN
    nat_type: NATType = NATType.UNKNOWN
    latency: float = 0  # ms
    bandwidth: float = 0  # Mbps
    stability: float = 1.0  # 0-1
    is_available: bool = True
    local_ip: str = ""
    public_ip: str = ""
    isp: str = ""
    city: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_score(self) -> float:
        """计算综合评分"""
        # 延迟评分 (40%)
        if self.latency < 10:
            latency_score = 1.0
        elif self.latency < 50:
            latency_score = 0.8
        elif self.latency < 200:
            latency_score = 0.6
        elif self.latency < 500:
            latency_score = 0.4
        else:
            latency_score = 0.2
        
        # 带宽评分 (30%)
        bandwidth_score = min(self.bandwidth / 10, 1.0)
        
        # 稳定性评分 (20%)
        stability_score = self.stability
        
        # 网络类型评分 (10%)
        type_scores = {
            NetworkType.LAN: 1.0,
            NetworkType.P2P: 0.8,
            NetworkType.RELAY: 0.6,
            NetworkType.CLOUD: 0.5,
            NetworkType.OFFLINE: 0.0,
        }
        type_score = type_scores.get(self.network_type, 0.3)
        
        return latency_score * 0.4 + bandwidth_score * 0.3 + stability_score * 0.2 + type_score * 0.1


@dataclass
class ProbeTarget:
    """探测目标"""
    host: str
    port: int
    priority: int = 0
    timeout: float = 3.0


class NetworkProbeManager:
    """
    网络探测管理器
    
    智能探测网络环境，选择最优连接方式
    """
    
    def __init__(self):
        self._probe_results: Dict[str, NetworkProbe] = {}
        self._probe_targets: List[ProbeTarget] = []
        self._lock = threading.Lock()
        self._running = False
        self._last_full_probe: Optional[datetime] = None
        self._probe_interval = 60  # 秒
        
        # STUN服务器
        self._stun_servers = [
            ("stun.l.google.com", 19302),
            ("stun1.l.google.com", 19302),
            ("stun.voip.a有任何争议，一切以实际测试为准", 3478),
        ]
        
        # 初始化默认探测目标
        self._init_default_targets()
    
    def _init_default_targets(self):
        """初始化默认探测目标"""
        self._probe_targets = [
            ProbeTarget("8.8.8.8", 53, priority=10),
            ProbeTarget("114.114.114.114", 53, priority=10),
            ProbeTarget("1.1.1.1", 53, priority=8),
        ]
    
    async def start(self):
        """启动探测"""
        self._running = True
        await self.full_probe()
    
    def stop(self):
        """停止探测"""
        self._running = False
    
    async def full_probe(self) -> NetworkProbe:
        """
        完整网络探测
        
        Returns:
            NetworkProbe: 探测结果
        """
        logger.info("Starting full network probe...")
        
        probe = NetworkProbe()
        
        # 1. 获取本地IP
        probe.local_ip = self._get_local_ip()
        
        # 2. 延迟探测
        probe.latency = await self._probe_latency()
        
        # 3. 带宽探测
        probe.bandwidth = await self._probe_bandwidth()
        
        # 4. NAT类型检测
        probe.nat_type = await self._detect_nat_type()
        
        # 5. 网络可用性
        probe.is_available = probe.latency < 5000
        
        # 6. 确定网络类型
        probe.network_type = self._determine_network_type(probe)
        
        # 7. 获取公网IP（可选，耗时较长）
        # probe.public_ip = await self._get_public_ip()
        
        self._last_full_probe = datetime.now()
        
        # 保存结果
        with self._lock:
            key = probe.local_ip
            self._probe_results[key] = probe
        
        logger.info(f"Network probe complete: {probe.network_type.value}, latency={probe.latency:.1f}ms")
        
        return probe
    
    async def quick_probe(self) -> Optional[NetworkProbe]:
        """
        快速探测（使用缓存）
        
        Returns:
            NetworkProbe: 探测结果
        """
        local_ip = self._get_local_ip()
        
        with self._lock:
            probe = self._probe_results.get(local_ip)
        
        if probe and (datetime.now() - probe.timestamp).total_seconds() < self._probe_interval:
            return probe
        
        # 缓存过期，执行快速探测
        probe = NetworkProbe()
        probe.local_ip = local_ip
        probe.latency = await self._probe_latency()
        probe.is_available = probe.latency < 5000
        probe.network_type = self._determine_network_type(probe)
        
        return probe
    
    async def _probe_latency(self) -> float:
        """探测延迟"""
        latencies = []
        
        for target in self._probe_targets[:3]:  # 只探测前3个
            try:
                lat = await self._measure_tcp_latency(target.host, target.port, timeout=2.0)
                if lat > 0:
                    latencies.append(lat)
            except Exception as e:
                logger.debug(f"Latency probe failed for {target.host}: {e}")
        
        if latencies:
            # 返回中位数
            latencies.sort()
            return latencies[len(latencies) // 2]
        
        return 9999.0  # 无法探测
    
    async def _measure_tcp_latency(self, host: str, port: int, timeout: float = 2.0) -> float:
        """TCP延迟测量"""
        start = time.perf_counter()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed
        except Exception:
            return 9999.0
    
    async def _probe_bandwidth(self) -> float:
        """探测带宽（简化版）"""
        # 简化实现：通过延迟估算带宽
        # 实际应该通过下载测试来估算
        latency = await self._probe_latency()
        
        if latency < 10:
            return 100.0  # 假设局域网
        elif latency < 50:
            return 50.0
        elif latency < 200:
            return 20.0
        else:
            return 5.0
    
    async def _detect_nat_type(self) -> NATType:
        """检测NAT类型（简化实现）"""
        # 简化实现：假设大多数是受限锥型NAT
        try:
            for stun_server in self._stun_servers[:1]:
                result = await self._stun_request(stun_server[0], stun_server[1])
                if result:
                    return result
        except Exception as e:
            logger.debug(f"NAT detection failed: {e}")
        
        return NATType.UNKNOWN
    
    async def _stun_request(self, server: str, port: int) -> Optional[NATType]:
        """STUN请求（简化）"""
        # 简化实现：实际应该发送STUN绑定请求
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3.0)
            
            # STUN binding request (simplified)
            # 实际应该使用完整的STUN协议
            sock.sendto(b'\x00\x01\x00\x00\x21\x12\xa4\x42', (server, port))
            
            try:
                data, addr = sock.recvfrom(1024)
                if data:
                    return NATType.RESTRICTED  # 简化
            except socket.timeout:
                pass
            finally:
                sock.close()
        except Exception:
            pass
        
        return None
    
    def _determine_network_type(self, probe: NetworkProbe) -> NetworkType:
        """确定网络类型"""
        if not probe.is_available:
            return NetworkType.OFFLINE
        
        # 基于延迟判断
        if probe.latency < 10:
            return NetworkType.LAN
        elif probe.latency < 100:
            return NetworkType.P2P
        elif probe.latency < 500:
            return NetworkType.RELAY
        else:
            return NetworkType.CLOUD
    
    def _get_local_ip(self) -> str:
        """获取本机IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    async def _get_public_ip(self) -> str:
        """获取公网IP"""
        try:
            import urllib.request
            response = urllib.request.urlopen("https://api.ipify.org", timeout=5)
            return response.read().decode()
        except Exception:
            return ""
    
    def get_best_connection_method(self, probe: Optional[NetworkProbe] = None) -> List[Tuple[str, float]]:
        """
        获取最优连接方式列表
        
        Args:
            probe: 可选，探测结果
            
        Returns:
            [(method_name, score), ...] 按分数排序
        """
        if probe is None:
            probe = self.quick_probe()
        
        if probe is None:
            return [("relay", 0.5)]  # 默认使用中继
        
        methods = []
        
        # 局域网
        if probe.network_type == NetworkType.LAN:
            methods.append(("lan", 1.0))
            methods.append(("p2p", 0.8))
            methods.append(("relay", 0.6))
        
        # P2P可用
        elif probe.nat_type in [NATType.OPEN, NATType.FULL_CONE]:
            methods.append(("p2p", 0.9))
            methods.append(("relay", 0.7))
        
        # 受限NAT
        elif probe.nat_type in [NATType.RESTRICTED, NATType.PORT_RESTRICTED]:
            methods.append(("p2p", 0.6))
            methods.append(("relay", 0.8))
        
        # 对称型NAT
        elif probe.nat_type == NATType.SYMMETRIC:
            methods.append(("relay", 0.9))
            methods.append(("p2p", 0.3))
        
        # 离线
        else:
            methods.append(("offline", 1.0))
        
        methods.sort(key=lambda x: x[1], reverse=True)
        return methods
    
    def add_probe_target(self, host: str, port: int, priority: int = 0):
        """添加探测目标"""
        target = ProbeTarget(host=host, port=port, priority=priority)
        self._probe_targets.append(target)
        self._probe_targets.sort(key=lambda x: x.priority, reverse=True)
    
    def get_probe_history(self) -> List[NetworkProbe]:
        """获取探测历史"""
        with self._lock:
            return list(self._probe_results.values())


# 单例实例
_probe_manager: Optional[NetworkProbeManager] = None


def get_network_probe_manager() -> NetworkProbeManager:
    """获取网络探测管理器"""
    global _probe_manager
    if _probe_manager is None:
        _probe_manager = NetworkProbeManager()
    return _probe_manager


__all__ = [
    "NetworkType",
    "NATType",
    "ConnectionQuality",
    "NetworkProbe",
    "ProbeTarget",
    "NetworkProbeManager",
    "get_network_probe_manager",
]
