"""
中继配置 (Relay Configuration)
===============================

管理三层中继网络的配置：
1. 公共层 - 免费服务
2. 私有层 - 用户自有服务器
3. 存储层 - 聚合网盘

Author: Hermes Desktop AI Assistant
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RelayType(Enum):
    """中继类型"""
    # 公共层（零成本）
    PUBLIC_SIGNALING = "public_signaling"    # 野狗/微信云开发
    PUBLIC_STUN = "public_stun"              # 腾讯云STUN
    PUBLIC_TURN = "public_turn"              # GoodLink/SakuraFrp

    # 私有层（增强）
    PRIVATE_SIGNALING = "private_signaling"  # 自建P2P信令
    PRIVATE_TURN = "private_turn"            # 自建TURN

    # 存储层
    STORAGE_RELAY = "storage_relay"         # OSS/COS网盘暂存


class ConnectionType(Enum):
    """连接类型"""
    P2P_SIGNALING = "p2p_signaling"   # P2P信令
    P2P_DIRECT = "p2p_direct"         # P2P直连
    FILE_SYNC = "file_sync"           # 文件同步
    STATE_SYNC = "state_sync"         # 状态同步
    BACKUP = "backup"                 # 数据备份
    BLOG_API = "blog_api"             # 博客API


@dataclass
class RelayEndpoint:
    """
    中继端点

    代表一个可用的中继服务
    """
    name: str
    relay_type: RelayType
    url: str
    enabled: bool = True
    priority: int = 100               # 优先级 (1-100, 越小越高)
    weight: float = 1.0              # 负载权重
    latency_ms: float = 0            # 当前延迟
    success_rate: float = 1.0        # 历史成功率
    is_free: bool = True             # 是否免费
    is_private: bool = False          # 是否私有服务器
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 认证信息（可选）
    username: str = ""
    password: str = ""
    token: str = ""

    # 健康状态
    last_check: float = 0
    consecutive_failures: int = 0
    status: str = "unknown"  # unknown/healthy/degraded/unavailable

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "relay_type": self.relay_type.value,
            "url": self.url,
            "enabled": self.enabled,
            "priority": self.priority,
            "latency_ms": self.latency_ms,
            "success_rate": self.success_rate,
            "is_free": self.is_free,
            "is_private": self.is_private,
            "status": self.status,
            "last_check": self.last_check
        }


@dataclass
class RelayConfig:
    """
    中继配置管理器

    管理所有中继端点的配置，支持：
    1. 自动发现可用端点
    2. 动态优先级调整
    3. 配置持久化
    """

    # 默认公共端点（零成本）
    DEFAULT_PUBLIC_ENDPOINTS = [
        # 野狗信令服务（免费WebSocket）
        RelayEndpoint(
            name="wilddog_signaling",
            relay_type=RelayType.PUBLIC_SIGNALING,
            url="wss://service.grap.sh/react-cloud/ws",
            enabled=True,
            priority=50,
            is_free=True,
            metadata={"provider": "wilddog", "region": "cn"}
        ),

        # 腾讯云STUN（NAT穿透）
        RelayEndpoint(
            name="tencent_stun",
            relay_type=RelayType.PUBLIC_STUN,
            url="stun:stun.qq.com:3478",
            enabled=True,
            priority=30,
            is_free=True,
            metadata={"provider": "tencent", "region": "cn"}
        ),

        # 公共STUN备用
        RelayEndpoint(
            name="google_stun",
            relay_type=RelayType.PUBLIC_STUN,
            url="stun:stun.l.google.com:19302",
            enabled=True,
            priority=40,
            is_free=True,
            metadata={"provider": "google", "region": "global"}
        ),

        # GoodLink TURN（NAT穿透失败兜底）
        RelayEndpoint(
            name="goodlink_turn",
            relay_type=RelayType.PUBLIC_TURN,
            url="turn:turn.goodlink.me:3478",
            enabled=True,
            priority=80,
            is_free=True,
            username="free",
            password="free",
            metadata={"provider": "goodlink", "region": "cn"}
        ),
    ]

    # 默认私有端点占位（需要用户配置）
    DEFAULT_PRIVATE_ENDPOINTS = [
        RelayEndpoint(
            name="private_signaling",
            relay_type=RelayType.PRIVATE_SIGNALING,
            url="",
            enabled=False,
            priority=10,  # 最高优先级
            is_private=True,
            metadata={"port": 8081}
        ),
        RelayEndpoint(
            name="private_turn",
            relay_type=RelayType.PRIVATE_TURN,
            url="",
            enabled=False,
            priority=20,
            is_private=True,
            username="",
            password="",
            metadata={"port": 8082}
        ),
    ]

    # 存储中继
    STORAGE_ENDPOINTS = [
        RelayEndpoint(
            name="aliyun_oss",
            relay_type=RelayType.STORAGE_RELAY,
            url="https://your-bucket.oss-cn-hangzhou.aliyuncs.com",
            enabled=True,
            priority=60,
            is_free=True,
            metadata={"provider": "aliyun", "region": "cn-hangzhou"}
        ),
        RelayEndpoint(
            name="tencent_cos",
            relay_type=RelayType.STORAGE_RELAY,
            url="https://your-bucket.cos.ap-shanghai.myqcloud.com",
            enabled=True,
            priority=70,
            is_free=True,
            metadata={"provider": "tencent", "region": "ap-shanghai"}
        ),
    ]

    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir) if config_dir else Path.home() / ".hermes" / "relay"
        self.config_file = self.config_dir / "relay_config.json"

        # 所有端点
        self.endpoints: Dict[str, RelayEndpoint] = {}
        self._initialized = False

        # 负载均衡
        self._current_weights: Dict[str, float] = {}

        # 加载配置
        self._load_config()

    def _load_config(self):
        """加载配置"""
        # 初始化默认端点
        for ep in self.DEFAULT_PUBLIC_ENDPOINTS + self.DEFAULT_PRIVATE_ENDPOINTS:
            self.endpoints[ep.name] = ep

        # 从文件加载用户配置
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 更新端点配置
                for ep_data in data.get("endpoints", []):
                    name = ep_data.get("name")
                    if name in self.endpoints:
                        self._update_endpoint(self.endpoints[name], ep_data)

                # 更新私有服务器配置
                if "private_server" in data:
                    self._configure_private_server(data["private_server"])

                self._initialized = True
                logger.info(f"Loaded relay config from {self.config_file}")

            except Exception as e:
                logger.error(f"Failed to load relay config: {e}")

    def _update_endpoint(self, endpoint: RelayEndpoint, data: dict):
        """更新端点配置"""
        endpoint.enabled = data.get("enabled", endpoint.enabled)
        endpoint.url = data.get("url", endpoint.url)
        endpoint.priority = data.get("priority", endpoint.priority)
        endpoint.username = data.get("username", endpoint.username)
        endpoint.password = data.get("password", endpoint.password)
        endpoint.token = data.get("token", endpoint.token)
        endpoint.enabled = data.get("enabled", endpoint.enabled)

    def _configure_private_server(self, private_config: dict):
        """配置私有服务器"""
        domain = private_config.get("domain")
        ports = private_config.get("ports", {})

        if not domain:
            return

        # 配置私有信令
        signaling_port = ports.get("signaling", 8081)
        if signaling_port:
            ep = self.endpoints.get("private_signaling")
            if ep:
                ep.url = f"ws://{domain}:{signaling_port}/ws"
                ep.enabled = True
                ep.username = private_config.get("username", "")
                ep.password = private_config.get("password", "")
                ep.token = private_config.get("token", "")

        # 配置私有TURN
        turn_port = ports.get("turn", 8082)
        if turn_port:
            ep = self.endpoints.get("private_turn")
            if ep:
                ep.url = f"turn:{domain}:{turn_port}"
                ep.enabled = True
                ep.username = private_config.get("turn_username", "relay")
                ep.password = private_config.get("turn_password", "")

    def save_config(self):
        """保存配置"""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # 收集非默认配置的端点
        endpoints_data = []
        for ep in self.endpoints.values():
            # 只保存用户修改过的配置
            if ep.url or ep.username or ep.password or ep.token:
                endpoints_data.append(ep.to_dict())

        # 提取私有服务器配置
        private_config = {}
        for ep in self.endpoints.values():
            if ep.is_private and ep.enabled:
                if "domain" not in private_config:
                    url = ep.url
                    if url:
                        # 从URL提取domain
                        domain = url.replace("ws://", "").replace("turn:", "").split(":")[0]
                        private_config["domain"] = domain

        data = {
            "version": "1.0",
            "updated_at": time.time(),
            "endpoints": endpoints_data,
            "private_server": private_config
        }

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved relay config to {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to save relay config: {e}")

    def get_endpoint(self, name: str) -> Optional[RelayEndpoint]:
        """获取端点"""
        return self.endpoints.get(name)

    def get_endpoints_by_type(self, relay_type: RelayType) -> List[RelayEndpoint]:
        """获取指定类型的端点"""
        return [
            ep for ep in self.endpoints.values()
            if ep.relay_type == relay_type and ep.enabled
        ]

    def get_available_endpoints(self, connection_type: ConnectionType = None) -> List[RelayEndpoint]:
        """
        获取可用的端点

        Args:
            connection_type: 连接类型过滤

        Returns:
            按优先级排序的可用端点列表
        """
        available = []

        for ep in self.endpoints.values():
            if not ep.enabled:
                continue
            if ep.status == "unavailable":
                continue
            if ep.consecutive_failures >= 5:
                continue

            # 根据连接类型过滤
            if connection_type:
                if not self._is_endpoint_suitable(ep, connection_type):
                    continue

            available.append(ep)

        # 按优先级和健康状态排序
        available.sort(key=lambda x: (
            x.priority,
            -x.success_rate,
            x.latency_ms
        ))

        return available

    def _is_endpoint_suitable(self, endpoint: RelayEndpoint, conn_type: ConnectionType) -> bool:
        """判断端点是否适合特定连接类型"""
        if conn_type == ConnectionType.P2P_SIGNALING:
            return endpoint.relay_type in [
                RelayType.PRIVATE_SIGNALING,
                RelayType.PUBLIC_SIGNALING
            ]
        elif conn_type in [ConnectionType.FILE_SYNC, ConnectionType.STATE_SYNC]:
            return endpoint.relay_type in [
                RelayType.PRIVATE_SIGNALING,
                RelayType.PUBLIC_SIGNALING,
                RelayType.PRIVATE_TURN,
                RelayType.PUBLIC_TURN
            ]
        elif conn_type == ConnectionType.BACKUP:
            return endpoint.relay_type in [
                RelayType.STORAGE_RELAY,
                RelayType.PRIVATE_TURN,
                RelayType.PUBLIC_TURN
            ]
        elif conn_type == ConnectionType.BLOG_API:
            # 博客API走HTTP，不是中继
            return False

        return True

    def update_endpoint_health(self, name: str, latency_ms: float, success: bool):
        """更新端点健康状态"""
        ep = self.endpoints.get(name)
        if not ep:
            return

        ep.last_check = time.time()
        ep.latency_ms = latency_ms

        if success:
            ep.consecutive_failures = 0
            # 滑动平均更新成功率
            ep.success_rate = 0.95 * ep.success_rate + 0.05 * 1.0
            if ep.status != "healthy" and ep.success_rate > 0.9:
                ep.status = "healthy"
        else:
            ep.consecutive_failures += 1
            ep.success_rate = 0.95 * ep.success_rate + 0.05 * 0.0
            if ep.consecutive_failures >= 3:
                ep.status = "degraded"
            if ep.consecutive_failures >= 5:
                ep.status = "unavailable"

    def configure_private_server(
        self,
        domain: str,
        signaling_port: int = 8081,
        turn_port: int = 8082,
        username: str = "",
        password: str = "",
        token: str = ""
    ):
        """配置私有服务器"""
        # 信令端点
        signaling_ep = self.endpoints.get("private_signaling")
        if signaling_ep:
            signaling_ep.url = f"ws://{domain}:{signaling_port}/ws"
            signaling_ep.enabled = True
            signaling_ep.username = username
            signaling_ep.password = password
            signaling_ep.token = token

        # TURN端点
        turn_ep = self.endpoints.get("private_turn")
        if turn_ep:
            turn_ep.url = f"turn:{domain}:{turn_port}"
            turn_ep.enabled = True
            turn_ep.username = username or "relay"
            turn_ep.password = password

        # 保存配置
        self.save_config()

    def disable_private_server(self):
        """禁用私有服务器"""
        for ep in self.endpoints.values():
            if ep.is_private:
                ep.enabled = False
                ep.status = "unavailable"
        self.save_config()

    def is_private_server_available(self) -> bool:
        """检查私有服务器是否可用"""
        ep = self.endpoints.get("private_signaling")
        return ep and ep.enabled and ep.status != "unavailable"

    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息摘要"""
        return {
            "private_available": self.is_private_server_available(),
            "endpoints": {
                name: ep.to_dict()
                for name, ep in self.endpoints.items()
                if ep.enabled
            }
        }


# ============================================================
# 全局单例
# ============================================================

_relay_config: Optional[RelayConfig] = None


def get_relay_config() -> RelayConfig:
    """获取全局中继配置"""
    global _relay_config
    if _relay_config is None:
        _relay_config = RelayConfig()
    return _relay_config


def reset_relay_config():
    """重置全局中继配置"""
    global _relay_config
    _relay_config = None