"""
智能中继路由器 (Smart Relay Router)
===================================

基于上下文的智能路径选择：
1. 延迟评分
2. 成本评分
3. 可靠性评分
4. 隐私评分
5. 带宽评分

Author: Hermes Desktop AI Assistant
"""

import os
import time
import logging
import threading
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PathStatus(Enum):
    """路径状态"""
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    TESTING = "testing"


@dataclass
class PathScore:
    """路径评分"""
    path_name: str
    total_score: float = 0

    # 各维度得分
    latency_score: float = 0    # 延迟得分 (0-1)
    cost_score: float = 0      # 成本得分 (0-1, 免费=1)
    reliability_score: float = 0  # 可靠性得分 (0-1)
    privacy_score: float = 0    # 隐私得分 (0-1, 私有=1)
    bandwidth_score: float = 0  # 带宽得分 (0-1)

    # 原始数据
    latency_ms: float = 0
    is_free: bool = True
    is_private: bool = False
    success_rate: float = 1.0

    # 元数据
    relay_type: str = ""
    endpoint_url: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path_name,
            "total_score": self.total_score,
            "latency_score": self.latency_score,
            "cost_score": self.cost_score,
            "reliability_score": self.reliability_score,
            "privacy_score": self.privacy_score,
            "bandwidth_score": self.bandwidth_score,
            "latency_ms": self.latency_ms,
            "is_free": self.is_free,
            "is_private": self.is_private,
            "success_rate": self.success_rate
        }


@dataclass
class RelayPath:
    """
    中继路径

    代表一个可用的中继传输路径
    """
    name: str
    relay_type: str
    endpoint_url: str
    status: PathStatus = PathStatus.AVAILABLE
    score: Optional[PathScore] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "relay_type": self.relay_type,
            "endpoint_url": self.endpoint_url,
            "status": self.status.value,
            "score": self.score.to_dict() if self.score else None,
            "metadata": self.metadata
        }


class SmartRelayRouter:
    """
    智能中继路由器

    根据连接类型和上下文，自动选择最佳中继路径

    评分权重（按连接类型）：
    - p2p_signaling: latency=0.4, reliability=0.4, privacy=0.2
    - file_sync: bandwidth=0.5, cost=0.3, latency=0.2
    - backup: reliability=0.6, cost=0.4
    - state_sync: latency=0.5, reliability=0.3, privacy=0.2
    """

    # 连接类型权重配置
    CONNECTION_WEIGHTS = {
        "p2p_signaling": {
            "latency": 0.4,
            "reliability": 0.4,
            "privacy": 0.2,
            "cost": 0.0,
            "bandwidth": 0.0
        },
        "p2p_direct": {
            "latency": 0.5,
            "reliability": 0.3,
            "privacy": 0.2,
            "cost": 0.0,
            "bandwidth": 0.0
        },
        "file_sync": {
            "latency": 0.2,
            "reliability": 0.2,
            "privacy": 0.1,
            "cost": 0.2,
            "bandwidth": 0.3
        },
        "state_sync": {
            "latency": 0.5,
            "reliability": 0.3,
            "privacy": 0.2,
            "cost": 0.0,
            "bandwidth": 0.0
        },
        "backup": {
            "latency": 0.0,
            "reliability": 0.6,
            "privacy": 0.1,
            "cost": 0.3,
            "bandwidth": 0.0
        }
    }

    # 默认权重
    DEFAULT_WEIGHTS = {
        "latency": 0.3,
        "reliability": 0.3,
        "privacy": 0.2,
        "cost": 0.1,
        "bandwidth": 0.1
    }

    def __init__(self, relay_config, health_monitor):
        self.config = relay_config
        self.health_monitor = health_monitor

        # 路由缓存
        self._path_cache: Dict[str, Tuple[RelayPath, float]] = {}
        self._cache_ttl = 10  # 缓存有效期（秒）

        # 失败历史（用于回避有问题的路径）
        self._failure_history: Dict[str, int] = {}
        self._max_failure_history = 10

    def get_best_path(
        self,
        connection_type: str,
        context: Dict[str, Any] = None
    ) -> Optional[RelayPath]:
        """
        获取最佳中继路径

        Args:
            connection_type: 连接类型 (p2p_signaling/file_sync/backup/state_sync)
            context: 额外上下文 (data_size/priority/privacy_requirement)

        Returns:
            最佳路径或None
        """
        if context is None:
            context = {}

        cache_key = f"{connection_type}"
        cached = self._get_cached_path(cache_key)
        if cached:
            return cached

        # 1. 获取可用路径
        available_paths = self._find_available_paths(connection_type)
        if not available_paths:
            logger.warning(f"No available paths for {connection_type}")
            return None

        # 2. 评分
        scored_paths = []
        for path in available_paths:
            score = self._score_path(path, connection_type, context)
            path.score = score
            scored_paths.append((score.total_score, path))

        # 3. 排序选择
        scored_paths.sort(key=lambda x: x[0], reverse=True)

        best_path = scored_paths[0][1] if scored_paths else None

        # 4. 缓存结果
        if best_path:
            self._path_cache[cache_key] = (best_path, time.time())

        return best_path

    def _get_cached_path(self, cache_key: str) -> Optional[RelayPath]:
        """获取缓存的路径"""
        if cache_key not in self._path_cache:
            return None

        path, cached_time = self._path_cache[cache_key]
        if time.time() - cached_time > self._cache_ttl:
            del self._path_cache[cache_key]
            return None

        return path

    def _find_available_paths(self, connection_type: str) -> List[RelayPath]:
        """查找可用路径"""
        paths = []

        # 获取对应类型的端点
        available_endpoints = self.config.get_available_endpoints()

        for ep in available_endpoints:
            # 过滤不适合的端点
            if not self._is_path_suitable(ep, connection_type):
                continue

            # 检查失败历史
            failures = self._failure_history.get(ep.name, 0)
            if failures >= self._max_failure_history:
                # 连续失败太多，降级使用
                if ep.is_private:
                    continue  # 私有路径失败太多就跳过

            health = self.health_monitor.health_status.get(ep.name)

            path = RelayPath(
                name=ep.name,
                relay_type=ep.relay_type.value,
                endpoint_url=ep.url,
                status=PathStatus.AVAILABLE if health and health.status.value != "unhealthy" else PathStatus.DEGRADED,
                metadata={
                    "priority": ep.priority,
                    "is_private": ep.is_private,
                    "is_free": ep.is_free
                }
            )
            paths.append(path)

        # 优先私有路径
        paths.sort(key=lambda x: (
            0 if x.metadata.get("is_private") else 1,
            x.metadata.get("priority", 100)
        ))

        return paths

    def _is_path_suitable(self, endpoint, connection_type: str) -> bool:
        """判断路径是否适合特定连接类型"""
        if connection_type in ("p2p_signaling", "p2p_direct"):
            return endpoint.relay_type.value.endswith("_signaling")
        elif connection_type in ("file_sync", "state_sync"):
            return endpoint.relay_type.value.endswith(("_signaling", "_turn"))
        elif connection_type == "backup":
            return True  # 备份可以使用任何路径

        return True

    def _score_path(
        self,
        path: RelayPath,
        connection_type: str,
        context: Dict[str, Any]
    ) -> PathScore:
        """
        计算路径评分

        评分维度：
        1. 延迟得分 (越低越好)
        2. 成本得分 (免费=1, 付费<1)
        3. 可靠性得分 (成功率越高越好)
        4. 隐私得分 (私有=1, 公共<1)
        5. 带宽得分 (大文件传输时考虑)
        """
        endpoint = self.config.get_endpoint(path.name)
        if not endpoint:
            return PathScore(path_name=path.name)

        health = self.health_monitor.health_status.get(path.name)

        # 获取权重
        weights = self.CONNECTION_WEIGHTS.get(connection_type, self.DEFAULT_WEIGHTS)

        # 计算各维度得分
        # 1. 延迟得分 (0-1, 延迟越低越高)
        latency_ms = health.latency_ms if health else endpoint.latency_ms
        if latency_ms < 50:
            latency_score = 1.0
        elif latency_ms < 200:
            latency_score = 0.8
        elif latency_ms < 500:
            latency_score = 0.5
        elif latency_ms < 1000:
            latency_score = 0.3
        else:
            latency_score = 0.1

        # 2. 成本得分
        cost_score = 1.0 if endpoint.is_free else 0.7

        # 3. 可靠性得分
        success_rate = health.success_rate if health else endpoint.success_rate
        reliability_score = success_rate

        # 4. 隐私得分
        privacy_score = 1.0 if endpoint.is_private else 0.5

        # 5. 带宽得分 (根据数据大小和连接类型)
        bandwidth_score = 0.5
        data_size = context.get("data_size", 0)
        if connection_type == "file_sync" and data_size > 10 * 1024 * 1024:  # >10MB
            # 大文件优先选择私有/免费高带宽路径
            if endpoint.is_private or endpoint.is_free:
                bandwidth_score = 0.8
        else:
            bandwidth_score = 0.6

        # 考虑失败历史
        failures = self._failure_history.get(path.name, 0)
        if failures > 0:
            penalty = min(failures * 0.1, 0.5)
            reliability_score *= (1 - penalty)

        # 计算总分
        total_score = (
            latency_score * weights.get("latency", 0) +
            cost_score * weights.get("cost", 0) +
            reliability_score * weights.get("reliability", 0) +
            privacy_score * weights.get("privacy", 0) +
            bandwidth_score * weights.get("bandwidth", 0)
        )

        return PathScore(
            path_name=path.name,
            total_score=total_score,
            latency_score=latency_score,
            cost_score=cost_score,
            reliability_score=reliability_score,
            privacy_score=privacy_score,
            bandwidth_score=bandwidth_score,
            latency_ms=latency_ms,
            is_free=endpoint.is_free,
            is_private=endpoint.is_private,
            success_rate=success_rate,
            relay_type=endpoint.relay_type.value,
            endpoint_url=endpoint.url
        )

    def report_failure(self, path_name: str):
        """报告路径失败"""
        self._failure_history[path_name] = self._failure_history.get(path_name, 0) + 1

        # 清除缓存
        self._path_cache.clear()

        logger.info(f"Path {path_name} failure count: {self._failure_history[path_name]}")

    def report_success(self, path_name: str):
        """报告路径成功"""
        if path_name in self._failure_history:
            self._failure_history[path_name] = max(0, self._failure_history[path_name] - 1)

        # 清除缓存
        self._path_cache.clear()

    def get_all_paths(self, connection_type: str) -> List[RelayPath]:
        """获取所有路径（带评分）"""
        available_paths = self._find_available_paths(connection_type)
        scored_paths = []

        for path in available_paths:
            score = self._score_path(path, connection_type, {})
            path.score = score
            scored_paths.append(path)

        scored_paths.sort(key=lambda x: x.score.total_score if x.score else 0, reverse=True)
        return scored_paths

    def get_route_table(self) -> Dict[str, Any]:
        """获取路由表（用于调试）"""
        result = {
            "timestamp": time.time(),
            "cache_ttl": self._cache_ttl,
            "failure_history": dict(self._failure_history),
            "paths_by_type": {}
        }

        for conn_type in self.CONNECTION_WEIGHTS.keys():
            paths = self.get_all_paths(conn_type)
            result["paths_by_type"][conn_type] = [p.to_dict() for p in paths]

        return result


# ============================================================
# 全局单例
# ============================================================

_smart_router: Optional[SmartRelayRouter] = None


def get_smart_router() -> SmartRelayRouter:
    """获取全局智能路由器"""
    global _smart_router
    if _smart_router is None:
        from .relay_config import get_relay_config
        from .health_monitor import get_health_monitor

        _smart_router = SmartRelayRouter(
            get_relay_config(),
            get_health_monitor()
        )
    return _smart_router


def reset_smart_router():
    """重置全局智能路由器"""
    global _smart_router
    _smart_router = None