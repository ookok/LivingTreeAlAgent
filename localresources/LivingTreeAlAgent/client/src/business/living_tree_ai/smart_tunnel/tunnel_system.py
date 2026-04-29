"""
智能伪装隧道核心系统
====================

检测 → 伪装 → 透明化 的自动化管道
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Dict, List, Any
from datetime import datetime, timedelta
import json
import hashlib


class ConnectionMode(Enum):
    """连接模式"""
    DIRECT = "direct"           # 直连
    PROXY = "proxy"             # 代理加速
    P2P_DIRECT = "p2p_direct"  # P2P 直连
    TUNNEL = "tunnel"          # 优化隧道
    OFFLINE = "offline"         # 离线模式


class NetworkStatus(Enum):
    """网络状态"""
    ONLINE = "online"
    POOR = "poor"
    OFFLINE = "offline"
    BLOCKED = "blocked"


class TunnelProtocol(Enum):
    """隧道协议"""
    HTTP = "http"
    SOCKS5 = "socks5"
    WEBRTC = "webrtc"
    TLS_TUNNEL = "tls_tunnel"
    QUIC = "quic"


@dataclass
class TunnelNode:
    """隧道节点"""
    node_id: str
    name: str
    host: str
    port: int
    region: str                      # 地区: Tokyo, Singapore, San Francisco...
    specialties: Dict[str, float]    # 专长: domain -> success_rate
    latency: float = 999.0          # 延迟 ms
    bandwidth: float = 0.0          # 可用带宽 Mbps
    reputation: float = 1.0         # 信誉 0-1
    cost: float = 0.0               # 成本
    is_online: bool = True
    last_heartbeat: datetime = field(default_factory=datetime.now)

    @property
    def score(self) -> float:
        """计算节点综合评分"""
        if not self.is_online:
            return 0.0

        # 多维度评分模型
        latency_score = 1.0 / (self.latency + 1) if self.latency < 1000 else 0.0
        bandwidth_score = min(self.bandwidth / 100, 1.0)  # 归一化到 100Mbps
        reputation_score = self.reputation
        cost_score = 1.0 / (self.cost + 1)

        # 加权求和
        return (
            0.3 * latency_score +
            0.2 * bandwidth_score +
            0.3 * reputation_score +
            0.1 * cost_score
        )

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "region": self.region,
            "specialties": self.specialties,
            "latency": self.latency,
            "bandwidth": self.bandwidth,
            "reputation": self.reputation,
            "is_online": self.is_online
        }


@dataclass
class TunnelSession:
    """隧道会话"""
    session_id: str
    node: TunnelNode
    protocol: TunnelProtocol
    created_at: datetime
    last_active: datetime
    bytes_transferred: int = 0
    requests_count: int = 0

    def is_expired(self, max_idle_seconds: int = 300) -> bool:
        """检查会话是否过期"""
        return (datetime.now() - self.last_activity).total_seconds() > max_idle_seconds

    @property
    def last_activity(self) -> datetime:
        return self.last_active


@dataclass
class AccessRecord:
    """访问记录（用于行为预测）"""
    url: str
    domain: str
    timestamp: datetime
    via_proxy: bool
    latency: float
    success: bool


class DetectionResult:
    """检测结果"""

    def __init__(self):
        self.status: NetworkStatus = NetworkStatus.ONLINE
        self.is_blocked: bool = False
        self.blocked_domains: List[str] = []
        self.network_quality: float = 1.0  # 0-1
        self.recommended_mode: ConnectionMode = ConnectionMode.DIRECT
        self.recommended_node: Optional[TunnelNode] = None


class SmartTunnelSystem:
    """
    智能伪装隧道系统

    工作流程：
    1. 检测层：实时检测连接状态（直连/被墙/离线）
    2. 伪装层：选择最优节点建立加密隧道
    3. 透明层：在 Qt 浏览器中无缝切换代理
    """

    def __init__(
        self,
        data_dir: str,
        enable_prediction: bool = True,
        enable_specialty_routing: bool = True
    ):
        self.data_dir = data_dir
        self.enable_prediction = enable_prediction
        self.enable_specialty_routing = enable_specialty_routing

        # 组件
        self.nodes: Dict[str, TunnelNode] = {}
        self.sessions: Dict[str, TunnelSession] = {}
        self.access_history: List[AccessRecord] = []

        # 配置
        self.config = TunnelConfig()
        self.proxy_selector: Optional['ProxySelector'] = None

        # 状态
        self.current_mode = ConnectionMode.DIRECT
        self.local_proxy_port = 7890  # 默认本地代理端口

        # 回调
        self.on_mode_changed: Optional[Callable[[ConnectionMode, str], None]] = None
        self.on_node_selected: Optional[Callable[[TunnelNode], None]] = None

        # 锁
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """初始化系统"""
        # 加载节点配置
        await self._load_nodes()

        # 初始化代理选择器
        from .proxy_selector import create_proxy_selector
        self.proxy_selector = create_proxy_selector(
            list(self.nodes.values()),
            enable_specialty=self.enable_specialty_routing
        )

    async def _load_nodes(self) -> None:
        """加载节点配置"""
        # 模拟加载，实际从配置文件或中心节点获取
        demo_nodes = [
            TunnelNode(
                node_id="node-tokyo-01",
                name="东京节点",
                host="tokyo.hyperos.node",
                port=8443,
                region="Tokyo",
                specialties={"github.com": 0.99, "youtube.com": 0.95, "arxiv.org": 0.90},
                latency=120.0,
                bandwidth=80.0,
                reputation=0.95
            ),
            TunnelNode(
                node_id="node-singapore-01",
                name="新加坡节点",
                host="singapore.hyperos.node",
                port=8443,
                region="Singapore",
                specialties={"github.com": 0.95, "youtube.com": 0.98, "google.com": 0.92},
                latency=200.0,
                bandwidth=60.0,
                reputation=0.90
            ),
            TunnelNode(
                node_id="node-sf-01",
                name="旧金山节点",
                host="sf.hyperos.node",
                port=8443,
                region="San Francisco",
                specialties={"github.com": 0.98, "openai.com": 0.99, "arxiv.org": 0.95},
                latency=180.0,
                bandwidth=100.0,
                reputation=0.98
            ),
        ]

        for node in demo_nodes:
            self.nodes[node.node_id] = node

    def detect_blocked(self, domain: str, timeout: float = 3.0) -> bool:
        """
        检测域名是否被墙

        实现思路：
        1. 尝试直连目标域名
        2. 如果超时或失败，尝试通过已知节点连接
        3. 综合判断是否被墙
        """
        import socket

        try:
            # 尝试直连
            start = time.time()
            sock = socket.create_connection((domain, 443), timeout=timeout)
            sock.close()
            return False  # 直连成功，未被墙
        except (socket.timeout, socket.error, OSError):
            return True  # 直连失败，可能被墙

    async def detect_network(self, test_domains: List[str] = None) -> DetectionResult:
        """
        检测网络状态

        返回检测结果，包含：
        - 网络状态（在线/差/离线/被墙）
        - 推荐连接模式
        - 推荐节点
        """
        result = DetectionResult()

        if test_domains is None:
            test_domains = ["github.com", "google.com", "youtube.com"]

        # 1. 检测基本网络连通性
        import socket

        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3.0)
            result.status = NetworkStatus.ONLINE
        except:
            result.status = NetworkStatus.OFFLINE
            result.recommended_mode = ConnectionMode.OFFLINE
            return result

        # 2. 检测被墙域名
        blocked_count = 0
        for domain in test_domains:
            if self.detect_blocked(domain):
                blocked_count += 1
                result.blocked_domains.append(domain)

        if blocked_count > 0:
            result.is_blocked = True
            result.network_quality = 1.0 - (blocked_count / len(test_domains))

        # 3. 选择最优模式
        if result.status == NetworkStatus.OFFLINE:
            result.recommended_mode = ConnectionMode.OFFLINE
        elif result.is_blocked:
            result.recommended_mode = ConnectionMode.PROXY
        else:
            result.recommended_mode = ConnectionMode.DIRECT

        # 4. 选择最优节点
        if result.recommended_mode == ConnectionMode.PROXY:
            # 获取专长节点
            if self.enable_specialty_routing and result.blocked_domains:
                target_domain = result.blocked_domains[0]
                result.recommended_node = await self._select_best_node_for_domain(target_domain)
            else:
                # 选择综合评分最高的节点
                result.recommended_node = await self._select_best_node()

        return result

    async def _select_best_node(self) -> Optional[TunnelNode]:
        """选择综合评分最高的节点"""
        if not self.nodes:
            return None

        online_nodes = [n for n in self.nodes.values() if n.is_online]
        if not online_nodes:
            return None

        return max(online_nodes, key=lambda n: n.score)

    async def _select_best_node_for_domain(self, domain: str) -> Optional[TunnelNode]:
        """根据域名专长选择最优节点"""
        if not self.nodes:
            return None

        online_nodes = [n for n in self.nodes.values() if n.is_online]
        if not online_nodes:
            return None

        # 策略1：优先选择对该域名有专长的节点
        specialty_nodes = [
            (n, n.specialties.get(domain, 0.0))
            for n in online_nodes
            if domain in n.specialties
        ]

        if specialty_nodes:
            # 按专长成功率排序
            specialty_nodes.sort(key=lambda x: x[1], reverse=True)
            return specialty_nodes[0][0]

        # 策略2：使用综合评分
        return await self._select_best_node()

    async def create_tunnel(
        self,
        domain: str,
        protocol: TunnelProtocol = TunnelProtocol.TLS_TUNNEL
    ) -> Optional[str]:
        """
        创建隧道

        Args:
            domain: 目标域名
            protocol: 隧道协议

        Returns:
            session_id: 隧道会话 ID，失败返回 None
        """
        async with self._lock:
            # 1. 检测网络
            detection = await self.detect_network([domain])

            if detection.status == NetworkStatus.OFFLINE:
                return None

            # 2. 选择节点
            node = detection.recommended_node
            if node is None:
                node = await self._select_best_node_for_domain(domain)

            if node is None:
                return None

            # 3. 创建会话
            session_id = hashlib.sha256(
                f"{node.node_id}:{domain}:{time.time()}".encode()
            ).hexdigest()[:16]

            session = TunnelSession(
                session_id=session_id,
                node=node,
                protocol=protocol,
                created_at=datetime.now(),
                last_active=datetime.now()
            )

            self.sessions[session_id] = session

            # 4. 记录访问
            self.access_history.append(AccessRecord(
                url=f"https://{domain}",
                domain=domain,
                timestamp=datetime.now(),
                via_proxy=True,
                latency=node.latency,
                success=True
            ))

            # 5. 触发回调
            if self.on_node_selected:
                self.on_node_selected(node)

            return session_id

    async def close_tunnel(self, session_id: str) -> bool:
        """关闭隧道"""
        async with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                return True
            return False

    def get_tunnel_info(self, session_id: str) -> Optional[dict]:
        """获取隧道信息"""
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]
        return {
            "session_id": session.session_id,
            "node": session.node.name,
            "region": session.node.region,
            "latency": session.node.latency,
            "protocol": session.protocol.value,
            "created_at": session.created_at.isoformat(),
            "bytes_transferred": session.bytes_transferred
        }

    def predict_next_access(self) -> Optional[str]:
        """
        预测下一次访问（基于历史行为）

        实现思路：
        1. 分析访问时间模式（如每天上午 9 点访问 GitHub）
        2. 分析访问序列（如打开邮箱后访问 GitHub）
        3. 返回预测的域名
        """
        if not self.access_history or not self.enable_prediction:
            return None

        # 简化实现：基于时间模式预测
        now = datetime.now()

        # 统计各域名的访问频率
        domain_counts: Dict[str, int] = {}
        for record in self.access_history:
            # 只统计最近 7 天的记录
            if (now - record.timestamp).days <= 7:
                domain_counts[record.domain] = domain_counts.get(record.domain, 0) + 1

        if not domain_counts:
            return None

        # 返回最频繁访问的域名
        return max(domain_counts.items(), key=lambda x: x[1])[0]

    async def preheat_node(self, domain: str) -> bool:
        """
        预测性预热节点

        当检测到用户即将访问被墙网站时，提前建立隧道
        """
        # 1. 预测
        predicted_domain = self.predict_next_access()

        if predicted_domain == domain:
            # 2. 提前创建隧道
            session_id = await self.create_tunnel(domain)
            return session_id is not None

        return False

    def get_connection_status(self) -> dict:
        """获取连接状态"""
        active_sessions = len([
            s for s in self.sessions.values()
            if not s.is_expired()
        ])

        return {
            "mode": self.current_mode.value,
            "active_tunnels": active_sessions,
            "online_nodes": len([n for n in self.nodes.values() if n.is_online]),
            "total_nodes": len(self.nodes),
            "prediction_enabled": self.enable_prediction
        }

    async def set_mode(self, mode: ConnectionMode) -> None:
        """设置连接模式"""
        old_mode = self.current_mode
        self.current_mode = mode

        if self.on_mode_changed and old_mode != mode:
            self.on_mode_changed(mode, f"切换到{mode.value}模式")


class TunnelConfig:
    """隧道配置"""

    def __init__(self):
        # 超时配置
        self.connect_timeout = 5.0       # 连接超时 秒
        self.read_timeout = 30.0         # 读取超时 秒
        self.max_idle_seconds = 300       # 最大空闲时间 秒

        # 重试配置
        self.max_retries = 3
        self.retry_delay = 1.0           # 秒

        # 代理配置
        self.local_proxy_host = "127.0.0.1"
        self.local_proxy_port = 7890

        # 检测配置
        self.test_domains = ["github.com", "google.com", "youtube.com"]
        self.detection_interval = 60     # 检测间隔 秒

        # 评分权重
        self.weights = {
            "latency": 0.3,
            "bandwidth": 0.2,
            "reputation": 0.3,
            "cost": 0.1
        }


def create_tunnel_system(
    data_dir: str,
    enable_prediction: bool = True,
    enable_specialty_routing: bool = True
) -> SmartTunnelSystem:
    """创建隧道系统"""
    return SmartTunnelSystem(
        data_dir=data_dir,
        enable_prediction=enable_prediction,
        enable_specialty_routing=enable_specialty_routing
    )