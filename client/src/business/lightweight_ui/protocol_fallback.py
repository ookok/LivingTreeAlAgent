"""
多协议降级策略

智能协议选择、自动降级、优雅恢复
from __future__ import annotations
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
import asyncio
import logging
import threading
import time

logger = logging.getLogger(__name__)


class ProtocolType(Enum):
    """协议类型"""
    TCP = "tcp"
    UDP = "udp"
    WEBSOCKET = "websocket"
    HTTP2 = "http2"
    QUIC = "quic"
    RELAY_HTTP = "relay_http"
    RELAY_WS = "relay_ws"


class ConnectionState(Enum):
    """连接状态"""
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    CLOSED = "closed"


class FallbackLevel(Enum):
    """降级级别"""
    NONE = 0           # 保持当前协议
    GRACEFUL = 1       # 优雅降级
    MINIMAL = 2        # 最小可用
    OFFLINE = 3       # 离线模式


@dataclass
class RelayEndpoint:
    """中继服务器端点"""
    host: str = "139.199.124.242"
    port: int = 8888
    name: str = ""
    region: str = ""
    priority: int = 0
    enabled: bool = True
    max_connections: int = 100
    current_connections: int = 0
    latency: float = 0
    success_rate: float = 1.0
    last_check: datetime = field(default_factory=datetime.now)
    api_key: str = ""
    ws_path: str = "/ws"
    
    @property
    def is_available(self) -> bool:
        """是否可用"""
        return (
            self.enabled and
            self.current_connections < self.max_connections and
            self.latency < 5000 and
            self.success_rate > 0.3
        )
    
    @property
    def quality_score(self) -> float:
        """质量分数"""
        score = 100
        score -= min(self.latency / 50, 40)  # 延迟扣分
        score -= (1 - self.success_rate) * 30  # 成功率扣分
        if self.current_connections >= self.max_connections * 0.9:
            score -= 20
        return max(0, min(100, score))


@dataclass
class ProtocolConfig:
    """协议配置"""
    protocol: ProtocolType
    priority: int = 0
    enabled: bool = True
    timeout: float = 5.0
    max_retries: int = 3
    retry_delay: float = 1.0
    keepalive_interval: float = 30.0
    compress: bool = True
    
    # 中继配置
    relay_endpoints: List[RelayEndpoint] = field(default_factory=list)
    
    def get_weight(self) -> float:
        """获取权重分数"""
        if not self.enabled:
            return 0.0
        return (self.priority + 1) / 10.0
    
    def get_best_relay(self) -> Optional[RelayEndpoint]:
        """获取最佳中继服务器"""
        available = [r for r in self.relay_endpoints if r.is_available]
        if not available:
            return None
        return max(available, key=lambda r: r.quality_score)


@dataclass
class ConnectionAttempt:
    """连接尝试记录"""
    protocol: ProtocolType
    start_time: datetime
    end_time: Optional[datetime] = None
    success: bool = False
    latency: float = 0
    error: Optional[str] = None


@dataclass
class FallbackStrategy:
    """降级策略配置"""
    # 降级触发条件
    latency_threshold: float = 500  # ms
    packet_loss_threshold: float = 0.1  # 10%
    error_rate_threshold: float = 0.3  # 30%
    timeout_threshold: int = 3  # 连续超时次数
    
    # 降级行为
    auto_fallback: bool = True
    fallback_delay: float = 2.0  # 降级前等待时间
    recovery_attempts: int = 3  # 恢复尝试次数
    recovery_interval: float = 30.0  # 恢复尝试间隔
    
    # 优先级配置
    priority_order: List[ProtocolType] = field(default_factory=lambda: [
        ProtocolType.TCP,
        ProtocolType.UDP,
        ProtocolType.WEBSOCKET,
        ProtocolType.HTTP2,
        ProtocolType.QUIC,
        ProtocolType.RELAY_HTTP,
    ])


class ProtocolFallbackManager:
    """
    协议降级管理器
    
    智能选择协议，处理连接失败自动降级
    """
    
    def __init__(self, strategy: FallbackStrategy = None):
        self.strategy = strategy or FallbackStrategy()
        self._protocols: Dict[ProtocolType, ProtocolConfig] = {}
        self._connection_history: List[ConnectionAttempt] = []
        self._lock = threading.Lock()
        self._current_protocol: Optional[ProtocolType] = None
        self._state = ConnectionState.IDLE
        
        # 统计信息
        self._stats = {
            "total_attempts": 0,
            "successful_attempts": 0,
            "failed_attempts": 0,
            "fallback_count": 0,
            "recovery_count": 0,
        }
        
        # 初始化默认协议
        self._init_default_protocols()
    
    def _init_default_protocols(self):
        """初始化默认协议"""
        self._protocols = {
            ProtocolType.TCP: ProtocolConfig(ProtocolType.TCP, priority=10),
            ProtocolType.UDP: ProtocolConfig(ProtocolType.UDP, priority=8),
            ProtocolType.WEBSOCKET: ProtocolConfig(ProtocolType.WEBSOCKET, priority=6),
            ProtocolType.HTTP2: ProtocolConfig(ProtocolType.HTTP2, priority=5),
            ProtocolType.QUIC: ProtocolConfig(ProtocolType.QUIC, priority=4),
            ProtocolType.RELAY_HTTP: ProtocolConfig(ProtocolType.RELAY_HTTP, priority=2),
            ProtocolType.RELAY_WS: ProtocolConfig(ProtocolType.RELAY_WS, priority=1),
        }
    
    def set_protocol_config(self, protocol: ProtocolType, config: ProtocolConfig):
        """设置协议配置"""
        self._protocols[protocol] = config
    
    def add_relay_endpoint(
        self,
        host: str,
        port: int = 8888,
        name: str = "",
        region: str = "",
        api_key: str = "",
    ) -> RelayEndpoint:
        """
        添加中继服务器端点
        
        Args:
            host: 主机地址
            port: 端口
            name: 名称
            region: 区域
            api_key: API密钥
            
        Returns:
            RelayEndpoint
        """
        endpoint = RelayEndpoint(
            host=host,
            port=port,
            name=name or f"Relay-{host}",
            region=region,
            api_key=api_key,
        )
        
        # 添加到所有中继协议配置
        for proto in [ProtocolType.RELAY_HTTP, ProtocolType.RELAY_WS]:
            config = self._protocols.get(proto)
            if config:
                config.relay_endpoints.append(endpoint)
        
        return endpoint
    
    def remove_relay_endpoint(self, host: str, port: int = 8888):
        """移除中继服务器端点"""
        for proto in [ProtocolType.RELAY_HTTP, ProtocolType.RELAY_WS]:
            config = self._protocols.get(proto)
            if config:
                config.relay_endpoints = [
                    r for r in config.relay_endpoints
                    if not (r.host == host and r.port == port)
                ]
    
    def get_best_relay_endpoint(self) -> Optional[RelayEndpoint]:
        """获取最佳中继服务器"""
        # 优先使用 RELAY_WS
        config = self._protocols.get(ProtocolType.RELAY_WS)
        if config:
            best = config.get_best_relay()
            if best:
                return best
        
        # 尝试 RELAY_HTTP
        config = self._protocols.get(ProtocolType.RELAY_HTTP)
        if config:
            return config.get_best_relay()
        
        return None
    
    def get_all_relay_endpoints(self) -> List[RelayEndpoint]:
        """获取所有中继服务器"""
        endpoints = []
        for proto in [ProtocolType.RELAY_HTTP, ProtocolType.RELAY_WS]:
            config = self._protocols.get(proto)
            if config:
                endpoints.extend(config.relay_endpoints)
        return endpoints
    
    def update_relay_stats(
        self,
        host: str,
        port: int,
        latency: float = None,
        success: bool = None,
        connection_count: int = None,
    ):
        """更新中继服务器统计"""
        for endpoint in self.get_all_relay_endpoints():
            if endpoint.host == host and endpoint.port == port:
                if latency is not None:
                    # 使用指数移动平均更新延迟
                    if endpoint.latency > 0:
                        endpoint.latency = endpoint.latency * 0.7 + latency * 0.3
                    else:
                        endpoint.latency = latency
                
                if success is not None:
                    # 更新成功率
                    if success:
                        endpoint.success_rate = endpoint.success_rate * 0.9 + 0.1
                    else:
                        endpoint.success_rate = endpoint.success_rate * 0.9
                
                if connection_count is not None:
                    endpoint.current_connections = connection_count
                
                endpoint.last_check = datetime.now()
                break
    
    def get_best_protocol(self, network_type: str = "lan") -> ProtocolType:
        """
        获取最佳协议
        
        Args:
            network_type: 网络类型 (lan/p2p/relay/cloud)
            
        Returns:
            ProtocolType: 最佳协议
        """
        # 根据网络类型调整优先级
        priority_boost = {
            "lan": {ProtocolType.TCP: 10, ProtocolType.UDP: 8},
            "p2p": {ProtocolType.UDP: 10, ProtocolType.TCP: 6},
            "relay": {ProtocolType.WEBSOCKET: 10, ProtocolType.HTTP2: 8},
            "cloud": {ProtocolType.QUIC: 10, ProtocolType.HTTP2: 8},
        }
        
        boosts = priority_boost.get(network_type, {})
        candidates = []
        
        for proto, config in self._protocols.items():
            if not config.enabled:
                continue
            
            weight = config.get_weight()
            weight += boosts.get(proto, 0) / 100.0
            
            # 历史成功率调整
            success_rate = self._get_protocol_success_rate(proto)
            weight *= (0.5 + success_rate * 0.5)
            
            candidates.append((proto, weight))
        
        # 按权重排序
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        if candidates:
            return candidates[0][0]
        
        return ProtocolType.TCP  # 默认
    
    def record_attempt(self, attempt: ConnectionAttempt):
        """记录连接尝试"""
        with self._lock:
            self._connection_history.append(attempt)
            
            # 保持历史记录数量
            if len(self._connection_history) > 100:
                self._connection_history = self._connection_history[-100:]
        
        # 更新统计
        self._stats["total_attempts"] += 1
        if attempt.success:
            self._stats["successful_attempts"] += 1
        else:
            self._stats["failed_attempts"] += 1
        
        # 更新当前协议状态
        if attempt.success:
            self._state = ConnectionState.CONNECTED
            self._current_protocol = attempt.protocol
        else:
            if self._state == ConnectionState.CONNECTED:
                self._state = ConnectionState.RECONNECTING
    
    def _get_protocol_success_rate(self, protocol: ProtocolType) -> float:
        """获取协议成功率"""
        attempts = [a for a in self._connection_history if a.protocol == protocol]
        
        if not attempts:
            return 1.0  # 新协议默认全成功
        
        success_count = sum(1 for a in attempts if a.success)
        return success_count / len(attempts)
    
    def should_fallback(self) -> Tuple[bool, FallbackLevel, Optional[ProtocolType]]:
        """
        判断是否需要降级
        
        Returns:
            (should_fallback, level, target_protocol)
        """
        if not self.strategy.auto_fallback:
            return False, FallbackLevel.NONE, None
        
        # 检查连续失败
        recent = self._connection_history[-self.strategy.timeout_threshold:]
        if len(recent) < self.strategy.timeout_threshold:
            return False, FallbackLevel.NONE, None
        
        # 所有最近尝试都失败
        if not any(a.success for a in recent):
            target = self._get_next_protocol()
            if target:
                self._stats["fallback_count"] += 1
                return True, FallbackLevel.GRACEFUL, target
        
        # 检查错误率
        total = len(self._connection_history)
        if total < 10:
            return False, FallbackLevel.NONE, None
        
        recent_100 = self._connection_history[-100:]
        errors = sum(1 for a in recent_100 if not a.success)
        error_rate = errors / len(recent_100)
        
        if error_rate > self.strategy.error_rate_threshold:
            target = self._get_next_protocol()
            if target:
                self._stats["fallback_count"] += 1
                return True, FallbackLevel.GRACEFUL, target
        
        return False, FallbackLevel.NONE, None
    
    def _get_next_protocol(self) -> Optional[ProtocolType]:
        """获取下一个可用协议"""
        if self._current_protocol is None:
            return self.get_best_protocol()
        
        # 在优先级列表中找到当前位置
        try:
            current_idx = self.strategy.priority_order.index(self._current_protocol)
            
            # 返回下一个（跳过不可用的）
            for i in range(current_idx + 1, len(self.strategy.priority_order)):
                proto = self.strategy.priority_order[i]
                config = self._protocols.get(proto)
                
                if config and config.enabled:
                    return proto
        except ValueError:
            pass
        
        # 如果当前是最高优先级，尝试降级到中继
        relay = ProtocolType.RELAY_HTTP
        if self._protocols.get(relay) and self._protocols[relay].enabled:
            return relay
        
        return None
    
    def should_recover(self) -> Tuple[bool, Optional[ProtocolType]]:
        """
        判断是否应该尝试恢复更高优先级协议
        
        Returns:
            (should_try_recovery, target_protocol)
        """
        if self._current_protocol is None:
            return False, None
        
        # 检查是否在恢复间隔内
        last_attempts = [a for a in self._connection_history[-10:] if a.success]
        if not last_attempts:
            return False, None
        
        last_success = last_attempts[-1]
        time_since_success = (datetime.now() - last_success.end_time).total_seconds() if last_success.end_time else 0
        
        if time_since_success < self.strategy.recovery_interval:
            return False, None
        
        # 检查连续成功次数
        recent = self._connection_history[-self.strategy.recovery_attempts:]
        if len(recent) >= self.strategy.recovery_attempts and all(a.success for a in recent):
            # 尝试恢复更高优先级
            try:
                current_idx = self.strategy.priority_order.index(self._current_protocol)
                
                for i in range(current_idx):
                    proto = self.strategy.priority_order[i]
                    config = self._protocols.get(proto)
                    
                    if config and config.enabled:
                        # 检查历史成功率
                        if self._get_protocol_success_rate(proto) > 0.7:
                            self._stats["recovery_count"] += 1
                            return True, proto
            except ValueError:
                pass
        
        return False, None
    
    def get_state(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "current_protocol": self._current_protocol.value if self._current_protocol else None,
            "state": self._state.value,
            "stats": self._stats.copy(),
            "protocols": {
                proto.value: {
                    "enabled": config.enabled,
                    "priority": config.priority,
                    "success_rate": self._get_protocol_success_rate(proto),
                }
                for proto, config in self._protocols.items()
            },
        }
    
    def reset(self):
        """重置状态"""
        with self._lock:
            self._connection_history.clear()
            self._current_protocol = None
            self._state = ConnectionState.IDLE
            self._stats = {
                "total_attempts": 0,
                "successful_attempts": 0,
                "failed_attempts": 0,
                "fallback_count": 0,
                "recovery_count": 0,
            }


# 单例实例
_fallback_manager: Optional[ProtocolFallbackManager] = None


def get_protocol_fallback_manager() -> ProtocolFallbackManager:
    """获取协议降级管理器"""
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = ProtocolFallbackManager()
    return _fallback_manager


__all__ = [
    "ProtocolType",
    "ConnectionState",
    "FallbackLevel",
    "ProtocolConfig",
    "ConnectionAttempt",
    "FallbackStrategy",
    "ProtocolFallbackManager",
    "get_protocol_fallback_manager",
]
