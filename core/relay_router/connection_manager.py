"""
连接状态机 (Connection State Machine)
=====================================

自动降级与升级策略：

启动 → 尝试私有 → 失败 → 公共信令 → 失败 → P2P直连 → 失败 → TURN兜底 → 失败 → 存储中继 → 离线模式

Author: Hermes Desktop AI Assistant
"""

import os
import time
import asyncio
import logging
import threading
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum

# 导入配置
try:
    from core.config.unified_config import get_config
except ImportError:
    get_config = None

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """连接状态"""
    INIT = "init"                        # 初始化
    CONNECTING = "connecting"            # 连接中
    CONNECTED = "connected"              # 已连接
    DEGRADED = "degraded"                # 降级运行
    RECONNECTING = "reconnecting"        # 重新连接
    DISCONNECTED = "disconnected"        # 断开连接
    OFFLINE = "offline"                  # 离线模式
    FAILED = "failed"                    # 失败


class ConnectionStage(Enum):
    """连接阶段（降级路径）"""
    # 阶段列表，按优先级排序
    PRIVATE_SERVER = "private_server"     # 私有服务器（最高优先级）
    PUBLIC_SIGNALING = "public_signaling" # 公共信令（野狗）
    PUBLIC_STUN = "public_stun"           # 公共STUN
    P2P_DIRECT = "p2p_direct"             # P2P直连尝试
    PUBLIC_TURN = "public_turn"           # 公共TURN兜底
    STORAGE_RELAY = "storage_relay"       # 存储中继（最终方案）
    OFFLINE_MODE = "offline_mode"        # 离线模式（最终兜底）


@dataclass
class StageInfo:
    """阶段信息"""
    stage: ConnectionStage
    status: ConnectionState = ConnectionState.INIT
    endpoint_name: str = ""
    endpoint_url: str = ""
    latency_ms: float = 0
    error_message: str = ""
    retry_count: int = 0
    last_attempt: float = 0
    entered_at: float = 0

    def to_dict(self) -> dict:
        return {
            "stage": self.stage.value,
            "status": self.status.value,
            "endpoint": self.endpoint_name,
            "latency_ms": self.latency_ms,
            "error": self.error_message,
            "retry_count": self.retry_count,
            "entered_at": self.entered_at
        }


@dataclass
class ConnectionAttempt:
    """连接尝试记录"""
    timestamp: float
    stage: str
    endpoint: str
    success: bool
    latency_ms: float
    error: str = ""


class ConnectionStateMachine:
    """
    连接状态机

    实现自动降级与升级策略：
    1. 优先尝试私有服务器
    2. 失败后自动切换到公共信令
    3. 尝试P2P直连
    4. NAT穿透失败使用TURN兜底
    5. 最终使用存储中继
    6. 完全失败进入离线模式
    """

    # 阶段顺序
    STAGE_ORDER = [
        ConnectionStage.PRIVATE_SERVER,
        ConnectionStage.PUBLIC_SIGNALING,
        ConnectionStage.PUBLIC_STUN,
        ConnectionStage.P2P_DIRECT,
        ConnectionStage.PUBLIC_TURN,
        ConnectionStage.STORAGE_RELAY,
        ConnectionStage.OFFLINE_MODE,
    ]

    # 各阶段超时（秒）- 从配置读取
    STAGE_TIMEOUTS: Dict[ConnectionStage, int] = None
    
    # 重试次数 - 从配置读取
    MAX_RETRIES: Dict[ConnectionStage, int] = None

    def __init__(self, relay_config, smart_router, health_monitor):
        # 从配置读取超时和重试配置
        self._load_config()
        
        self.config = relay_config
        self.router = smart_router
        self.health_monitor = health_monitor

        # 当前状态
        self.state = ConnectionState.INIT
        self.current_stage: Optional[ConnectionStage] = None
        self.current_endpoint: Optional[str] = None

        # 各阶段信息
        self.stages: Dict[ConnectionStage, StageInfo] = {}
        for stage in self.STAGE_ORDER:
            self.stages[stage] = StageInfo(stage=stage)

        # 连接历史
        self.connection_history: List[ConnectionAttempt] = []
        self.max_history = 50

        # 回调
        self._state_callbacks: List[Callable] = []
        self._stage_callbacks: List[Callable] = []

        # 线程控制
        self._running = False
        self._connect_thread: Optional[threading.Thread] = None

        # 升级检测 - 从配置读取
        self._upgrade_check_interval = self._get_config_value("relay.upgrade_check_interval", 60)
        self._last_upgrade_check = 0
        
    def _load_config(self):
        """从配置加载超时和重试配置"""
        if ConnectionStateMachine.STAGE_TIMEOUTS is None:
            config = get_config() if get_config else None
            
            if config:
                ConnectionStateMachine.STAGE_TIMEOUTS = {
                    ConnectionStage.PRIVATE_SERVER: config.get("relay.stage_timeout.private_server", 5),
                    ConnectionStage.PUBLIC_SIGNALING: config.get("relay.stage_timeout.public_signaling", 10),
                    ConnectionStage.PUBLIC_STUN: config.get("relay.stage_timeout.public_stun", 5),
                    ConnectionStage.P2P_DIRECT: config.get("relay.stage_timeout.p2p_direct", 15),
                    ConnectionStage.PUBLIC_TURN: config.get("relay.stage_timeout.public_turn", 10),
                    ConnectionStage.STORAGE_RELAY: config.get("relay.stage_timeout.storage_relay", 30),
                }
                ConnectionStateMachine.MAX_RETRIES = {
                    ConnectionStage.PRIVATE_SERVER: config.get("relay.max_retries.private_server", 2),
                    ConnectionStage.PUBLIC_SIGNALING: config.get("relay.max_retries.public_signaling", 3),
                    ConnectionStage.PUBLIC_STUN: config.get("relay.max_retries.public_stun", 2),
                    ConnectionStage.P2P_DIRECT: config.get("relay.max_retries.p2p_direct", 1),
                    ConnectionStage.PUBLIC_TURN: config.get("relay.max_retries.public_turn", 2),
                    ConnectionStage.STORAGE_RELAY: config.get("relay.max_retries.storage_relay", 1),
                }
            else:
                # 默认值
                ConnectionStateMachine.STAGE_TIMEOUTS = {
                    ConnectionStage.PRIVATE_SERVER: 5,
                    ConnectionStage.PUBLIC_SIGNALING: 10,
                    ConnectionStage.PUBLIC_STUN: 5,
                    ConnectionStage.P2P_DIRECT: 15,
                    ConnectionStage.PUBLIC_TURN: 10,
                    ConnectionStage.STORAGE_RELAY: 30,
                }
                ConnectionStateMachine.MAX_RETRIES = {
                    ConnectionStage.PRIVATE_SERVER: 2,
                    ConnectionStage.PUBLIC_SIGNALING: 3,
                    ConnectionStage.PUBLIC_STUN: 2,
                    ConnectionStage.P2P_DIRECT: 1,
                    ConnectionStage.PUBLIC_TURN: 2,
                    ConnectionStage.STORAGE_RELAY: 1,
                }
    
    def _get_config_value(self, key: str, default: Any) -> Any:
        """获取配置值"""
        if get_config:
            return get_config().get(key, default)
        return default

    def start(self):
        """启动连接状态机"""
        if self._running:
            return

        self._running = True
        self._connect_thread = threading.Thread(target=self._connect_loop, daemon=True)
        self._connect_thread.start()
        logger.info("Connection state machine started")

    def stop(self):
        """停止状态机"""
        self._running = False
        if self._connect_thread:
            self._connect_thread.join(timeout=5)
        logger.info("Connection state machine stopped")

    def _connect_loop(self):
        """连接循环"""
        # 从配置读取间隔
        health_check_interval = self._get_config_value("relay.health_check_interval", 5)
        degraded_recover_interval = self._get_config_value("relay.degraded_recover_interval", 10)
        offline_check_interval = self._get_config_value("relay.offline_check_interval", 30)
        reconnect_wait = self._get_config_value("relay.reconnect_wait", 5)
        
        while self._running:
            try:
                if self.state in (ConnectionState.INIT, ConnectionState.DISCONNECTED):
                    self._start_connection()

                elif self.state == ConnectionState.CONNECTED:
                    # 保持连接，定期检查
                    self._check_connection_health()
                    time.sleep(health_check_interval)

                elif self.state == ConnectionState.DEGRADED:
                    # 尝试恢复
                    self._attempt_upgrade()
                    time.sleep(degraded_recover_interval)

                elif self.state in (ConnectionState.RECONNECTING, ConnectionState.FAILED):
                    # 等待后重试
                    time.sleep(reconnect_wait)
                    self._start_connection()

                elif self.state == ConnectionState.OFFLINE:
                    # 离线模式，定期检查恢复可能
                    self._check_offline_recovery()
                    time.sleep(offline_check_interval)

            except Exception as e:
                logger.error(f"Connection loop error: {e}")
                time.sleep(reconnect_wait)

    def _start_connection(self):
        """开始连接流程"""
        self.state = ConnectionState.CONNECTING

        # 按阶段顺序尝试
        for stage in self.STAGE_ORDER:
            if not self._running:
                break

            stage_info = self.stages[stage]
            stage_info.entered_at = time.time()
            stage_info.status = ConnectionState.CONNECTING
            self.current_stage = stage

            # 获取该阶段的最佳端点
            endpoint = self._get_endpoint_for_stage(stage)
            if not endpoint:
                stage_info.status = ConnectionState.DISCONNECTED
                stage_info.error_message = "No available endpoint"
                continue

            stage_info.endpoint_name = endpoint.name
            stage_info.endpoint_url = endpoint.url
            self.current_endpoint = endpoint.name

            # 通知阶段变化
            self._notify_stage_change(stage, endpoint.name)

            # 尝试连接
            success, latency, error = self._attempt_connect(endpoint, stage)

            self._record_attempt(stage.value, endpoint.name, success, latency, error)

            if success:
                self.state = ConnectionState.CONNECTED
                stage_info.status = ConnectionState.CONNECTED
                stage_info.latency_ms = latency
                self._notify_state_change(ConnectionState.CONNECTED)
                logger.info(f"Connected via {stage.value}: {endpoint.name}")
                return

            else:
                stage_info.status = ConnectionState.FAILED
                stage_info.error_message = error
                stage_info.retry_count += 1

                # 报告失败给路由器
                self.router.report_failure(endpoint.name)

                # 如果重试次数用完，继续下一个阶段
                if stage_info.retry_count >= self.MAX_RETRIES.get(stage, 1):
                    logger.info(f"Stage {stage.value} exhausted, moving to next")
                    continue

        # 所有阶段都失败
        self.state = ConnectionState.OFFLINE
        self._notify_state_change(ConnectionState.OFFLINE)
        logger.warning("All connection stages failed, entering offline mode")

    def _get_endpoint_for_stage(self, stage: ConnectionStage) -> Optional[Any]:
        """获取指定阶段的端点"""
        endpoints = self.config.get_available_endpoints()

        if stage == ConnectionStage.PRIVATE_SERVER:
            # 私有服务器优先
            for ep in endpoints:
                if ep.is_private and ep.enabled:
                    return ep
            # 如果私有服务器不可用，检查是否已配置
            private_ep = self.config.get_endpoint("private_signaling")
            if private_ep and private_ep.url:
                return private_ep
            return None

        elif stage == ConnectionStage.PUBLIC_SIGNALING:
            for ep in endpoints:
                if ep.relay_type.value == "public_signaling":
                    return ep

        elif stage == ConnectionStage.PUBLIC_STUN:
            for ep in endpoints:
                if ep.relay_type.value == "public_stun":
                    return ep

        elif stage == ConnectionStage.P2P_DIRECT:
            # P2P直连不需要中继
            return None

        elif stage == ConnectionStage.PUBLIC_TURN:
            for ep in endpoints:
                if ep.relay_type.value == "public_turn":
                    return ep

        elif stage == ConnectionStage.STORAGE_RELAY:
            for ep in endpoints:
                if ep.relay_type.value == "storage_relay":
                    return ep

        return None

    def _attempt_connect(self, endpoint, stage: ConnectionStage) -> Tuple[bool, float, str]:
        """
        尝试连接

        Returns:
            (success, latency_ms, error_message)
        """
        timeout = self.STAGE_TIMEOUTS.get(stage, 10)
        start_time = time.time()

        try:
            # 根据阶段执行不同的连接逻辑
            if stage == ConnectionStage.P2P_DIRECT:
                # P2P直连需要NAT穿透
                return self._attempt_p2p_direct(timeout)
            else:
                # 中继连接
                return self._attempt_relay_connect(endpoint, timeout)

        except Exception as e:
            return False, 0, str(e)

    def _attempt_relay_connect(self, endpoint, timeout: int) -> Tuple[bool, float, str]:
        """尝试中继连接"""
        # 简单的连接测试
        try:
            import socket

            url = endpoint.url.replace("wss://", "").replace("ws://", "")
            url = url.replace("turn:", "").replace("stun:", "")
            if "/" in url:
                url = url.split("/")[0]
            if ":" in url:
                host, port_str = url.split(":")
                port = int(port_str)
            else:
                host = url
                port = 80 if "ws" in endpoint.url else 3478

            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            latency = (time.time() - start) * 1000

            return True, latency, ""

        except socket.timeout:
            return False, 0, "Connection timeout"
        except Exception as e:
            return False, 0, str(e)

    def _attempt_p2p_direct(self, timeout: int) -> Tuple[bool, float, str]:
        """尝试P2P直连（NAT穿透）"""
        # 这里应该实现STUN穿透逻辑
        # 简化版本：直接返回失败，触发TURN兜底
        logger.info("Attempting P2P direct connection (NAT traversal)")

        # 模拟NAT穿透尝试
        nat_traverse_delay = self._get_config_value("relay.nat_traverse_delay", 1)
        time.sleep(nat_traverse_delay)

        # 返回失败，让状态机继续到TURN阶段
        return False, 0, "NAT traversal failed"

    def _check_connection_health(self):
        """检查连接健康状态"""
        if not self.current_endpoint:
            return

        health = self.health_monitor.force_check(self.current_endpoint)
        if not health:
            return

        # 检查是否需要降级
        if health.status.value == "unhealthy":
            logger.warning(f"Current endpoint {self.current_endpoint} is unhealthy")
            self.state = ConnectionState.DEGRADED
            self._notify_state_change(ConnectionState.DEGRADED)

    def _attempt_upgrade(self):
        """尝试升级到更好的连接"""
        now = time.time()

        # 限制检查频率
        if now - self._last_upgrade_check < self._upgrade_check_interval:
            return

        self._last_upgrade_check = now

        # 检查私有服务器是否恢复
        if self.current_stage != ConnectionStage.PRIVATE_SERVER:
            if self.config.is_private_server_available():
                health = self.health_monitor.force_check("private_signaling")
                if health and health.status.value == "healthy":
                    logger.info("Private server available, attempting upgrade")
                    self.state = ConnectionState.RECONNECTING
                    self.current_stage = ConnectionStage.PRIVATE_SERVER
                    self._notify_stage_change(ConnectionStage.PRIVATE_SERVER, "private_signaling")

    def _check_offline_recovery(self):
        """检查离线模式恢复可能"""
        # 定期检查是否有可用的连接方式
        self.health_monitor.check_all_relays()

        best = self.health_monitor.get_best_endpoint()
        if best:
            logger.info(f"Recovery possible via {best}")
            self.state = ConnectionState.RECONNECTING

    def _record_attempt(
        self,
        stage: str,
        endpoint: str,
        success: bool,
        latency_ms: float,
        error: str
    ):
        """记录连接尝试"""
        attempt = ConnectionAttempt(
            timestamp=time.time(),
            stage=stage,
            endpoint=endpoint,
            success=success,
            latency_ms=latency_ms,
            error=error
        )

        self.connection_history.append(attempt)
        if len(self.connection_history) > self.max_history:
            self.connection_history.pop(0)

    def register_state_callback(self, callback: Callable):
        """注册状态变化回调"""
        self._state_callbacks.append(callback)

    def register_stage_callback(self, callback: Callable):
        """注册阶段变化回调"""
        self._stage_callbacks.append(callback)

    def _notify_state_change(self, new_state: ConnectionState):
        """通知状态变化"""
        for callback in self._state_callbacks:
            try:
                callback(new_state, self.current_stage, self.current_endpoint)
            except Exception as e:
                logger.error(f"State callback error: {e}")

    def _notify_stage_change(self, stage: ConnectionStage, endpoint: str):
        """通知阶段变化"""
        for callback in self._stage_callbacks:
            try:
                callback(stage, endpoint)
            except Exception as e:
                logger.error(f"Stage callback error: {e}")

    def get_status(self) -> Dict[str, Any]:
        """获取连接状态"""
        return {
            "state": self.state.value,
            "current_stage": self.current_stage.value if self.current_stage else None,
            "current_endpoint": self.current_endpoint,
            "stages": {stage.value: info.to_dict() for stage, info in self.stages.items()},
            "history_count": len(self.connection_history),
            "last_attempts": [
                {
                    "stage": a.stage,
                    "endpoint": a.endpoint,
                    "success": a.success,
                    "latency_ms": a.latency_ms,
                    "timestamp": a.timestamp
                }
                for a in self.connection_history[-5:]
            ]
        }

    def force_reconnect(self):
        """强制重连"""
        self.state = ConnectionState.RECONNECTING
        # 重置所有阶段的重试计数
        for stage_info in self.stages.values():
            stage_info.retry_count = 0

    def get_current_path(self) -> Optional[str]:
        """获取当前使用的路径"""
        return self.current_endpoint

    def is_connected(self) -> bool:
        """是否已连接"""
        return self.state == ConnectionState.CONNECTED

    def is_offline(self) -> bool:
        """是否离线"""
        return self.state == ConnectionState.OFFLINE


# ============================================================
# 全局单例
# ============================================================

_connection_manager: Optional[ConnectionStateMachine] = None


def get_connection_manager() -> ConnectionStateMachine:
    """获取全局连接管理器"""
    global _connection_manager
    if _connection_manager is None:
        from .relay_config import get_relay_config
        from .health_monitor import get_health_monitor
        from .smart_router import get_smart_router

        _connection_manager = ConnectionStateMachine(
            get_relay_config(),
            get_smart_router(),
            get_health_monitor()
        )
    return _connection_manager


def reset_connection_manager():
    """重置全局连接管理器"""
    global _connection_manager
    if _connection_manager:
        _connection_manager.stop()
    _connection_manager = None