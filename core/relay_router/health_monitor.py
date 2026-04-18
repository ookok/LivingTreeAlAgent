"""
中继健康监控 (Relay Health Monitor)
====================================

监控所有中继端点的健康状态：
1. 延迟检测
2. 成功率追踪
3. 故障告警
4. 自动恢复检测

Author: Hermes Desktop AI Assistant
"""

import os
import time
import socket
import asyncio
import logging
import threading
import statistics
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class RelayHealthStatus:
    """中继健康状态"""
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    latency_ms: float = 0
    success_rate: float = 1.0
    last_check: float = 0
    consecutive_failures: int = 0
    total_checks: int = 0
    total_failures: int = 0

    # 历史数据（用于趋势分析）
    recent_latencies: List[float] = field(default_factory=list)
    recent_results: List[bool] = field(default_factory=list)

    # 告警状态
    alert_triggered: bool = False
    alert_message: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "success_rate": self.success_rate,
            "last_check": self.last_check,
            "consecutive_failures": self.consecutive_failures,
            "total_checks": self.total_checks,
            "total_failures": self.total_failures,
            "alert_triggered": self.alert_triggered
        }


class RelayHealthMonitor:
    """
    中继健康监控器

    功能：
    1. 定期健康检查（ICMP ping / TCP探测 / HTTP探测）
    2. 延迟和成功率统计
    3. 故障检测与告警
    4. 自动恢复检测
    5. 历史数据维护
    """

    # 检查间隔
    DEFAULT_CHECK_INTERVAL = 30  # 秒
    FAST_CHECK_INTERVAL = 5    # 故障后快速检查间隔

    # 阈值
    LATENCY_THRESHOLD_MS = 500     # 延迟告警阈值
    SUCCESS_RATE_THRESHOLD = 0.8   # 成功率告警阈值
    CONSECUTIVE_FAILURE_THRESHOLD = 3  # 连续失败告警阈值
    RECOVERY_CHECK_COUNT = 3        # 恢复检查次数

    MAX_HISTORY_SIZE = 100  # 历史数据保留条数

    def __init__(self, relay_config):
        self.config = relay_config

        # 健康状态
        self.health_status: Dict[str, RelayHealthStatus] = {}

        # 回调函数
        self._callbacks: List[Callable] = []

        # 监控线程
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._check_interval = self.DEFAULT_CHECK_INTERVAL

        # 告警历史（防止重复告警）
        self._alert_cooldown = 300  # 5分钟内不重复告警
        self._last_alert_time: Dict[str, float] = {}

    def start(self):
        """启动监控"""
        if self._running:
            return

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Relay health monitor started")

    def stop(self):
        """停止监控"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Relay health monitor stopped")

    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                self.check_all_relays()
            except Exception as e:
                logger.error(f"Health check error: {e}")

            # 根据状态调整检查间隔
            has_failures = any(
                s.consecutive_failures > 0
                for s in self.health_status.values()
            )
            self._check_interval = (
                self.FAST_CHECK_INTERVAL if has_failures
                else self.DEFAULT_CHECK_INTERVAL
            )

            time.sleep(self._check_interval)

    def check_all_relays(self) -> Dict[str, RelayHealthStatus]:
        """
        检查所有中继的健康状态

        Returns:
            {端点名称: 健康状态}
        """
        endpoints = self.config.endpoints.values()
        results = {}

        for endpoint in endpoints:
            if not endpoint.enabled:
                continue

            health = self._check_endpoint(endpoint)
            self.health_status[endpoint.name] = health
            results[endpoint.name] = health

            # 更新配置中的端点状态
            if health.status == HealthStatus.UNHEALTHY:
                self.config.update_endpoint_health(endpoint.name, health.latency_ms, False)
            elif health.status == HealthStatus.HEALTHY:
                self.config.update_endpoint_health(endpoint.name, health.latency_ms, True)

        # 检查是否需要告警
        self._check_alerts(results)

        return results

    def _check_endpoint(self, endpoint) -> RelayHealthStatus:
        """检查单个端点"""
        status = RelayHealthStatus(name=endpoint.name)
        status.last_check = time.time()

        try:
            # 根据端点类型选择检查方式
            if endpoint.relay_type.value.endswith("_stun"):
                latency, success = self._check_stun(endpoint)
            elif endpoint.relay_type.value.endswith("_signaling"):
                latency, success = self._check_signaling(endpoint)
            elif endpoint.relay_type.value.endswith("_turn"):
                latency, success = self._check_turn(endpoint)
            elif endpoint.relay_type == "storage_relay":
                latency, success = self._check_storage(endpoint)
            else:
                latency, success = self._check_tcp(endpoint)

            status.latency_ms = latency
            status.consecutive_failures = 0 if success else status.consecutive_failures + 1
            status.total_checks += 1
            if not success:
                status.total_failures += 1

            # 更新历史
            status.recent_latencies.append(latency)
            status.recent_results.append(success)
            if len(status.recent_latencies) > self.MAX_HISTORY_SIZE:
                status.recent_latencies.pop(0)
                status.recent_results.pop(0)

            # 计算成功率
            status.success_rate = (
                (status.total_checks - status.total_failures) / status.total_checks
                if status.total_checks > 0 else 1.0
            )

            # 判断状态
            if success:
                if status.latency_ms > self.LATENCY_THRESHOLD_MS:
                    status.status = HealthStatus.DEGRADED
                else:
                    status.status = HealthStatus.HEALTHY
            else:
                if status.consecutive_failures >= self.CONSECUTIVE_FAILURE_THRESHOLD:
                    status.status = HealthStatus.UNHEALTHY
                else:
                    status.status = HealthStatus.DEGRADED

        except Exception as e:
            logger.debug(f"Check {endpoint.name} failed: {e}")
            status.status = HealthStatus.UNHEALTHY
            status.consecutive_failures += 1
            status.total_checks += 1
            status.total_failures += 1
            status.recent_results.append(False)
            if len(status.recent_results) > self.MAX_HISTORY_SIZE:
                status.recent_results.pop(0)

        return status

    def _check_stun(self, endpoint) -> tuple:
        """检查STUN服务器"""
        try:
            # 简单TCP连接测试
            host = endpoint.url.replace("stun:", "").split(":")[0]
            port = int(endpoint.url.split(":")[-1])

            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            sock.close()
            latency = (time.time() - start) * 1000

            return latency, True
        except Exception:
            return 0, False

    def _check_signaling(self, endpoint) -> tuple:
        """检查信令服务器（WebSocket）"""
        try:
            # 使用HTTP(s)探测
            url = endpoint.url
            if not url.startswith("http"):
                url = "https://" + url

            start = time.time()
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=5) as resp:
                latency = (time.time() - start) * 1000
                return latency, resp.status < 400
        except Exception:
            return 0, False

    def _check_turn(self, endpoint) -> tuple:
        """检查TURN服务器"""
        try:
            # 尝试TCP连接
            url = endpoint.url.replace("turn:", "").replace("tls:", "")
            if "//" in url:
                url = url.split("//")[1]
            parts = url.split(":")
            host = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 3478

            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            sock.close()
            latency = (time.time() - start) * 1000

            return latency, True
        except Exception:
            return 0, False

    def _check_storage(self, endpoint) -> tuple:
        """检查存储服务"""
        try:
            # HEAD请求检查可用性
            url = endpoint.url
            if not url.startswith("http"):
                url = "https://" + url

            start = time.time()
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=10) as resp:
                latency = (time.time() - start) * 1000
                return latency, resp.status < 400
        except Exception:
            return 0, False

    def _check_tcp(self, endpoint) -> tuple:
        """通用TCP检查"""
        try:
            url = endpoint.url.replace("ws://", "").replace("wss://", "")
            if "/" in url:
                url = url.split("/")[0]
            if ":" in url:
                parts = url.split(":")
                host = parts[0]
                port = int(parts[1])
            else:
                host = url
                port = 80

            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            sock.close()
            latency = (time.time() - start) * 1000

            return latency, True
        except Exception:
            return 0, False

    def _check_alerts(self, results: Dict[str, RelayHealthStatus]):
        """检查是否需要告警"""
        now = time.time()

        for name, health in results.items():
            if health.status == HealthStatus.UNHEALTHY:
                # 检查是否在冷却期
                last_alert = self._last_alert_time.get(name, 0)
                if now - last_alert > self._alert_cooldown:
                    self._trigger_alert(name, health)
                    self._last_alert_time[name] = now

    def _trigger_alert(self, name: str, health: RelayHealthStatus):
        """触发告警"""
        health.alert_triggered = True
        health.alert_message = (
            f"中继 {name} 健康检查失败！"
            f"连续失败: {health.consecutive_failures}次, "
            f"成功率: {health.success_rate*100:.1f}%"
        )

        logger.warning(health.alert_message)

        # 调用回调
        for callback in self._callbacks:
            try:
                callback(name, health)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    def register_callback(self, callback: Callable):
        """注册告警回调"""
        self._callbacks.append(callback)

    def get_health_summary(self) -> Dict[str, Any]:
        """获取健康状态摘要"""
        total = len(self.health_status)
        healthy = sum(1 for h in self.health_status.values() if h.status == HealthStatus.HEALTHY)
        degraded = sum(1 for h in self.health_status.values() if h.status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for h in self.health_status.values() if h.status == HealthStatus.UNHEALTHY)

        avg_latency = statistics.mean(
            h.latency_ms for h in self.health_status.values()
            if h.latency_ms > 0
        ) if self.health_status else 0

        return {
            "total": total,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "average_latency_ms": avg_latency,
            "details": {name: h.to_dict() for name, h in self.health_status.items()}
        }

    def get_best_endpoint(self, relay_type_filter: List[str] = None) -> Optional[str]:
        """
        获取最健康的端点

        Args:
            relay_type_filter: 中继类型过滤

        Returns:
            最佳端点名称
        """
        candidates = []

        for name, health in self.health_status.items():
            if health.status == HealthStatus.UNHEALTHY:
                continue
            if health.latency_ms > self.LATENCY_THRESHOLD_MS * 2:
                continue

            endpoint = self.config.get_endpoint(name)
            if not endpoint or not endpoint.enabled:
                continue

            if relay_type_filter:
                if endpoint.relay_type.value not in relay_type_filter:
                    continue

            # 计算健康分数
            score = (
                (1.0 - health.latency_ms / 1000) * 0.3 +
                health.success_rate * 0.5 +
                (1.0 if endpoint.is_private else 0.3) * 0.2
            )
            candidates.append((score, name))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def force_check(self, endpoint_name: str) -> Optional[RelayHealthStatus]:
        """强制检查指定端点"""
        endpoint = self.config.get_endpoint(endpoint_name)
        if not endpoint:
            return None

        health = self._check_endpoint(endpoint)
        self.health_status[endpoint_name] = health
        return health


# ============================================================
# 全局单例
# ============================================================

_health_monitor: Optional[RelayHealthMonitor] = None


def get_health_monitor() -> RelayHealthMonitor:
    """获取全局健康监控器"""
    global _health_monitor
    if _health_monitor is None:
        from .relay_config import get_relay_config
        _health_monitor = RelayHealthMonitor(get_relay_config())
        _health_monitor.start()
    return _health_monitor


def reset_health_monitor():
    """重置全局健康监控器"""
    global _health_monitor
    if _health_monitor:
        _health_monitor.stop()
    _health_monitor = None