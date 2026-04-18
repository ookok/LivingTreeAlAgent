"""
环境感知引擎 (Awareness Engine)
===============================

检测浏览器运行环境，自动切换行为模式：

- online: 正常在线，直连外部网站
- offline: 完全离线，回退到本地 CID 缓存
- metro: 地铁模式，禁用图片预加载，激进缓存
- node: 节点模式，发现对方也是 P2P 节点，建立加密直连
"""

import asyncio
import time
from enum import Enum
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger(__name__)


class EnvironmentMode(Enum):
    """浏览器运行环境模式"""
    ONLINE = "online"           # 正常在线
    OFFLINE = "offline"         # 完全离线
    METRO = "metro"            # 地铁/低带宽模式
    NODE = "node"              # P2P 节点模式
    UNKNOWN = "unknown"


class NetworkQuality(Enum):
    """网络质量"""
    EXCELLENT = "excellent"    # < 50ms
    GOOD = "good"              # 50-200ms
    FAIR = "fair"              # 200-500ms
    POOR = "poor"              # 500-1000ms
    VERY_POOR = "very_poor"    # > 1000ms 或离线


@dataclass
class AwarenessConfig:
    """感知引擎配置"""
    # 网络检测
    ping_interval: float = 30.0          # Ping 间隔（秒）
    ping_timeout: float = 5.0            # Ping 超时（秒）
    ping_targets: List[str] = None       # Ping 目标列表

    # 模式切换阈值
    offline_threshold: float = 0.1       # 丢包率 > 10% 判定离线
    metro_threshold: float = 0.3         # 丢包率 > 30% 判定地铁模式
    metro_latency: float = 500.0         # 延迟 > 500ms 判定地铁模式

    # 节点发现
    node_discovery_enabled: bool = True
    node_dns_check: bool = True         # 检查 DNS TXT 记录
    node_meta_check: bool = True        # 检查网页 meta 标签

    # 预测性行为
    preload_on_prediction: bool = True   # 预测成功后预加载

    def __post_init__(self):
        if self.ping_targets is None:
            self.ping_targets = [
                "8.8.8.8",              # Google DNS
                "1.1.1.1",              # Cloudflare DNS
                "114.114.114.114",      # 腾讯 DNS
            ]


@dataclass
class EnvironmentState:
    """当前环境状态"""
    mode: EnvironmentMode = EnvironmentMode.UNKNOWN
    quality: NetworkQuality = NetworkQuality.UNKNOWN
    latency_ms: float = 0.0
    packet_loss: float = 0.0              # 0.0 - 1.0
    bandwidth_mbps: float = 0.0
    is_charging: bool = True
    battery_level: float = 1.0           # 0.0 - 1.0
    is_online: bool = True

    # 节点相关
    is_node_mode: bool = False
    peer_node_id: Optional[str] = None
    peer_endpoint: Optional[str] = None

    # 时间戳
    last_update: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "quality": self.quality.value,
            "latency_ms": self.latency_ms,
            "packet_loss": self.packet_loss,
            "bandwidth_mbps": self.bandwidth_mbps,
            "is_charging": self.is_charging,
            "battery_level": self.battery_level,
            "is_online": self.is_online,
            "is_node_mode": self.is_node_mode,
            "peer_node_id": self.peer_node_id,
            "peer_endpoint": self.peer_endpoint,
            "last_update": self.last_update,
        }


class AwarenessEngine:
    """
    浏览器环境感知引擎

    检测网络质量、电池状态、节点发现，自动切换运行模式
    """

    def __init__(self, config: Optional[AwarenessConfig] = None):
        self.config = config or AwarenessConfig()
        self.state = EnvironmentState()
        self._callbacks: List[Callable[[EnvironmentState, EnvironmentState], None]] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # 历史数据（用于趋势分析）
        self._latency_history = deque(maxlen=30)
        self._packet_loss_history = deque(maxlen=30)

    def add_mode_change_callback(
        self,
        callback: Callable[[EnvironmentState, EnvironmentState], None]
    ) -> None:
        """添加模式切换回调"""
        self._callbacks.append(callback)

    async def start(self) -> None:
        """启动感知引擎"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._awareness_loop())
        logger.info("Awareness Engine started")

    async def stop(self) -> None:
        """停止感知引擎"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Awareness Engine stopped")

    async def detect_environment(self) -> EnvironmentState:
        """
        检测当前环境（单次检测）

        检测流程：
        1. 网络连通性检测
        2. 延迟和丢包率测量
        3. 电池状态检测
        4. 节点发现（可选）
        5. 综合判断模式
        """
        old_state = self.state

        # 1. 网络连通性
        is_online = await self._check_connectivity()

        if not is_online:
            self.state.mode = EnvironmentMode.OFFLINE
            self.state.quality = NetworkQuality.VERY_POOR
            self.state.is_online = False
            self.state.latency_ms = 0
            self.state.packet_loss = 1.0
        else:
            self.state.is_online = True

            # 2. 延迟和丢包率
            latency, packet_loss = await self._measure_network()
            self.state.latency_ms = latency
            self.state.packet_loss = packet_loss
            self._latency_history.append(latency)
            self._packet_loss_history.append(packet_loss)

            # 3. 网络质量评估
            self.state.quality = self._assess_quality(latency, packet_loss)

            # 4. 电池状态
            await self._check_battery()

            # 5. 节点发现
            if self.config.node_discovery_enabled:
                await self._discover_nodes()

            # 6. 综合判断模式
            self._determine_mode()

        self.state.last_update = time.time()
        self._notify_change(old_state)

        return self.state

    async def _check_connectivity(self) -> bool:
        """检查网络连通性"""
        # 尝试连接多个目标
        for target in self.config.ping_targets:
            try:
                # 使用 asyncio 的 open_connection 进行轻量级连通性检测
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(target, 53),
                    timeout=self.config.ping_timeout
                )
                writer.close()
                await writer.wait_closed()
                return True
            except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
                continue

        return False

    async def _measure_network(self) -> tuple[float, float]:
        """测量网络延迟和丢包率"""
        latencies = []
        successful = 0
        total = len(self.config.ping_targets)

        for target in self.config.ping_targets:
            try:
                start = time.perf_counter()
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(target, 53),
                    timeout=self.config.ping_timeout
                )
                end = time.perf_counter()
                writer.close()
                await writer.wait_closed()
                latencies.append((end - start) * 1000)  # 转换为毫秒
                successful += 1
            except (asyncio.TimeoutError, OSError):
                continue

        if not latencies:
            return 0.0, 1.0  # 完全丢包

        avg_latency = sum(latencies) / len(latencies)
        packet_loss = 1.0 - (successful / total)

        return avg_latency, packet_loss

    async def _check_battery(self) -> None:
        """检查电池状态（跨平台）"""
        try:
            # 尝试使用 psutil（如果可用）
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                self.state.battery_level = battery.percent / 100.0
                self.state.is_charging = battery.power_plugged
        except ImportError:
            # 降级：返回默认值
            self.state.battery_level = 1.0
            self.state.is_charging = True

    async def _discover_nodes(self) -> None:
        """发现 P2P 节点"""
        # 注意：这里需要与当前访问的网站交互
        # 实际实现中需要传入当前 URL
        pass

    def check_site_is_node(self, url: str, html_content: str) -> Optional[str]:
        """
        检查网站是否是 P2P 节点

        Args:
            url: 网站 URL
            html_content: 网页 HTML 内容

        Returns:
            节点 ID 如果是节点，否则 None
        """
        if not self.config.node_meta_check:
            return None

        # 检查 <meta name="hyperos-node" content="node-id">
        import re
        match = re.search(
            r'<meta\s+name=["\']hyperos-node["\']\s+content=["\']([^"\']+)["\']',
            html_content,
            re.IGNORECASE
        )

        if match:
            node_id = match.group(1)
            logger.info(f"Discovered HyperOS node: {node_id}")
            return node_id

        return None

    def _assess_quality(self, latency: float, packet_loss: float) -> NetworkQuality:
        """评估网络质量"""
        if packet_loss > 0.5:
            return NetworkQuality.VERY_POOR

        if latency < 50:
            return NetworkQuality.EXCELLENT
        elif latency < 200:
            return NetworkQuality.GOOD
        elif latency < 500:
            return NetworkQuality.FAIR
        elif latency < 1000:
            return NetworkQuality.POOR
        else:
            return NetworkQuality.VERY_POOR

    def _determine_mode(self) -> None:
        """综合判断运行模式"""
        # 离线模式
        if not self.state.is_online:
            self.state.mode = EnvironmentMode.OFFLINE
            return

        # 节点模式优先
        if self.state.is_node_mode:
            self.state.mode = EnvironmentMode.NODE
            return

        # 地铁/低带宽模式判断
        if (self.state.packet_loss > self.config.metro_threshold or
            self.state.latency_ms > self.config.metro_latency or
            (self.state.battery_level < 0.2 and not self.state.is_charging)):
            self.state.mode = EnvironmentMode.METRO
            return

        # 默认在线模式
        self.state.mode = EnvironmentMode.ONLINE

    async def _awareness_loop(self) -> None:
        """感知主循环"""
        while self._running:
            try:
                await self.detect_environment()
                await asyncio.sleep(self.config.ping_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Awareness loop error: {e}")
                await asyncio.sleep(5)

    def _notify_change(self, old_state: EnvironmentState) -> None:
        """通知模式变化"""
        if old_state.mode != self.state.mode:
            for callback in self._callbacks:
                try:
                    callback(old_state, self.state)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

    def get_state(self) -> EnvironmentState:
        """获取当前状态"""
        return self.state

    def get_trend(self) -> Dict[str, Any]:
        """获取网络质量趋势"""
        return {
            "latency_trend": list(self._latency_history),
            "packet_loss_trend": list(self._packet_loss_history),
            "avg_latency": sum(self._latency_history) / len(self._latency_history) if self._latency_history else 0,
            "avg_packet_loss": sum(self._packet_loss_history) / len(self._packet_loss_history) if self._packet_loss_history else 0,
        }

    # ========== 快捷方法 ==========

    async def is_online(self) -> bool:
        """快速检查是否在线"""
        if self.state.mode != EnvironmentMode.UNKNOWN:
            return self.state.mode != EnvironmentMode.OFFLINE
        return await self._check_connectivity()

    async def get_recommended_cache_strategy(self) -> str:
        """
        获取推荐的缓存策略

        Returns:
            缓存策略名称
        """
        state = await self.detect_environment()

        if state.mode == EnvironmentMode.OFFLINE:
            return "cache-only"           # 只使用缓存
        elif state.mode == EnvironmentMode.METRO:
            return "aggressive-cache"     # 激进缓存
        elif state.mode == EnvironmentMode.NODE:
            return "p2p-prefer"           # 优先 P2P
        else:
            return "normal"               # 正常策略


def create_awareness_engine(config: Optional[AwarenessConfig] = None) -> AwarenessEngine:
    """创建感知引擎工厂函数"""
    return AwarenessEngine(config)