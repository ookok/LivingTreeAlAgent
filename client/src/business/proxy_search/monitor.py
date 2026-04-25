# -*- coding: utf-8 -*-
"""
代理池定时监测与健康检查
"""

import asyncio
import time
import logging
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .config import get_config
from .proxy_pool import get_proxy_pool
from .validator import get_validator, ValidationResult

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"  # 健康
    DEGRADED = "degraded"  # 降级
    UNHEALTHY = "unhealthy"  # 不健康
    DISCONNECTED = "disconnected"  # 断网


@dataclass
class HealthReport:
    """健康报告"""
    status: HealthStatus
    total_proxies: int
    healthy_proxies: int
    avg_response_time: float  # 毫秒
    last_check: datetime
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class NetworkStatus:
    """网络状态"""
    is_online: bool
    proxy_available: bool
    last_online_time: Optional[datetime]
    consecutive_failures: int = 0


class ProxyMonitor:
    """
    代理池监测器

    功能：
    1. 定时检查代理池健康状态
    2. 监测网络连接
    3. 异常时自动断网保护
    4. 生成健康报告
    """

    def __init__(
        self,
        interval: int = 300,  # 5分钟
        health_check_targets: List[str] = None,
        auto_disconnect_threshold: int = 5,  # 连续失败5次自动断网
    ):
        """
        初始化监测器

        Args:
            interval: 检查间隔（秒）
            health_check_targets: 健康检查目标URL列表
            auto_disconnect_threshold: 自动断网阈值
        """
        self.interval = interval
        self.health_check_targets = health_check_targets or [
            "https://www.google.com",
            "https://scholar.google.com",
        ]
        self.auto_disconnect_threshold = auto_disconnect_threshold

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._network_status = NetworkStatus(
            is_online=True,
            proxy_available=True,
            last_online_time=datetime.now(),
            consecutive_failures=0,
        )
        self._last_report: Optional[HealthReport] = None
        self._callbacks: List[Callable] = []

    async def start(self):
        """启动监测"""
        if self._running:
            logger.warning("监测器已在运行")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"代理监测器启动，间隔 {self.interval} 秒")

    async def stop(self):
        """停止监测"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("代理监测器已停止")

    def add_callback(self, callback: Callable[[HealthReport], None]):
        """添加健康报告回调"""
        self._callbacks.append(callback)

    async def _monitor_loop(self):
        """监测循环"""
        while self._running:
            try:
                await self._check_health()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监测循环异常: {e}")
                await asyncio.sleep(self.interval)

    async def _check_health(self):
        """执行健康检查"""
        logger.debug("执行健康检查...")

        pool = get_proxy_pool()
        validator = get_validator()

        issues = []
        recommendations = []

        # 1. 检查代理池大小
        total = pool.size()
        healthy = pool.get_healthy_count()
        healthy_ratio = healthy / max(total, 1)

        if total == 0:
            issues.append("代理池为空")
            recommendations.append("重新获取代理源")
        elif healthy_ratio < 0.3:
            issues.append(f"可用代理比例过低: {healthy_ratio:.1%}")
            recommendations.append("刷新代理池")

        # 2. 检查网络连通性
        network_ok = await self._check_network_connectivity()
        if not network_ok:
            self._network_status.consecutive_failures += 1
            issues.append(f"网络连接失败 (连续 {self._network_status.consecutive_failures} 次)")

            # 自动断网保护
            if self._network_status.consecutive_failures >= self.auto_disconnect_threshold:
                await self._trigger_disconnect()
                return
        else:
            self._network_status.consecutive_failures = 0
            self._network_status.last_online_time = datetime.now()

        # 3. 计算平均响应时间
        avg_response_time = pool.get_avg_response_time()

        # 4. 确定健康状态
        if total == 0 or not network_ok:
            status = HealthStatus.UNHEALTHY
        elif healthy_ratio < 0.5 or avg_response_time > 5000:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        # 5. 生成报告
        self._last_report = HealthReport(
            status=status,
            total_proxies=total,
            healthy_proxies=healthy,
            avg_response_time=avg_response_time,
            last_check=datetime.now(),
            issues=issues,
            recommendations=recommendations,
        )

        self._network_status.is_online = status != HealthStatus.DISCONNECTED

        # 6. 通知回调
        for callback in self._callbacks:
            try:
                callback(self._last_report)
            except Exception as e:
                logger.error(f"回调执行异常: {e}")

        logger.info(
            f"健康检查完成: {status.value}, "
            f"代理 {healthy}/{total}, "
            f"响应 {avg_response_time:.0f}ms"
        )

    async def _check_network_connectivity(self) -> bool:
        """检查网络连通性"""
        import aiohttp

        for target in self.health_check_targets:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(target, timeout=5) as resp:
                        if resp.status < 500:
                            return True
            except Exception:
                continue
        return False

    async def _trigger_disconnect(self):
        """触发断网保护"""
        logger.warning("触发自动断网保护！")
        self._network_status.is_online = False
        self._network_status.proxy_available = False

        # 禁用代理
        config = get_config()
        config.enable_proxy = False

        # 通知回调
        for callback in self._callbacks:
            try:
                callback(self._last_report)
            except Exception as e:
                logger.error(f"断网回调异常: {e}")

    async def manual_disconnect(self, reason: str = ""):
        """
        手动断网

        Args:
            reason: 断网原因
        """
        logger.warning(f"手动断网: {reason}")
        self._network_status.is_online = False
        self._network_status.proxy_available = False

        config = get_config()
        config.enable_proxy = False

    async def reconnect(self):
        """重新连接"""
        logger.info("重新连接...")
        self._network_status.is_online = True
        self._network_status.consecutive_failures = 0

        config = get_config()
        config.enable_proxy = True

    def get_health_report(self) -> Optional[HealthReport]:
        """获取最新健康报告"""
        return self._last_report

    def get_network_status(self) -> NetworkStatus:
        """获取网络状态"""
        return self._network_status

    def is_online(self) -> bool:
        """检查是否在线"""
        return self._network_status.is_online

    def is_proxy_available(self) -> bool:
        """检查代理是否可用"""
        return self._network_status.proxy_available


# 全局监测实例
_monitor: Optional[ProxyMonitor] = None


def get_monitor() -> ProxyMonitor:
    """获取全局监测器"""
    global _monitor
    if _monitor is None:
        config = get_config()
        _monitor = ProxyMonitor(
            interval=config.monitor_interval,
            auto_disconnect_threshold=5,
        )
    return _monitor


async def start_monitoring(interval: int = None):
    """启动监测"""
    monitor = get_monitor()
    if interval:
        monitor.interval = interval
    await monitor.start()


async def stop_monitoring():
    """停止监测"""
    monitor = get_monitor()
    await monitor.stop()


def get_latest_report() -> Optional[HealthReport]:
    """获取最新健康报告"""
    return get_monitor().get_health_report()


def get_status_summary() -> Dict[str, Any]:
    """获取状态摘要"""
    monitor = get_monitor()
    network = monitor.get_network_status()
    report = monitor.get_health_report()

    return {
        "online": network.is_online,
        "proxy_available": network.proxy_available,
        "consecutive_failures": network.consecutive_failures,
        "last_online": network.last_online_time.isoformat() if network.last_online_time else None,
        "health_status": report.status.value if report else None,
        "total_proxies": report.total_proxies if report else 0,
        "healthy_proxies": report.healthy_proxies if report else 0,
    }
