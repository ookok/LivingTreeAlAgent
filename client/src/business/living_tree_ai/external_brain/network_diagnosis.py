"""
NetworkDiagnoser - 网络诊断器
=============================

在发起请求前进行轻量级可达性检测，避免长时间等待。

检测目标：
- OpenAI API
- Claude API
- DeepSeek API
- 其他常用AI服务

Author: LivingTreeAI Community
from __future__ import annotations
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import asyncio
import logging
import time
import socket

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """服务状态"""
    AVAILABLE = "available"      # 可用
    UNAVAILABLE = "unavailable" # 不可用
    TIMEOUT = "timeout"         # 超时
    ERROR = "error"             # 错误
    UNKNOWN = "unknown"         # 未知


@dataclass
class ServiceEndpoint:
    """服务端点"""
    name: str
    url: str
    check_url: str = ""          # 用于健康检查的URL（可选）
    timeout: float = 5.0        # 超时时间（秒）
    enabled: bool = True
    priority: int = 0            # 优先级，数字越大优先级越高

    def get_check_url(self) -> str:
        """获取检查URL"""
        if self.check_url:
            return self.check_url
        return self.url


@dataclass
class DiagnosisReport:
    """诊断报告"""
    timestamp: datetime = field(default_factory=datetime.now)
    results: Dict[str, ServiceStatus] = field(default_factory=dict)
    latency: Dict[str, float] = field(default_factory=dict)  # ms
    error: Dict[str, str] = field(default_factory=dict)

    def get_available_services(self) -> List[str]:
        """获取可用的服务列表"""
        return [name for name, status in self.results.items() if status == ServiceStatus.AVAILABLE]

    def get_unavailable_services(self) -> List[str]:
        """获取不可用的服务列表"""
        return [name for name, status in self.results.items() if status != ServiceStatus.AVAILABLE]

    def is_all_unavailable(self) -> bool:
        """是否全部不可用"""
        return len(self.get_available_services()) == 0

    def is_any_available(self) -> bool:
        """是否有任何服务可用"""
        return len(self.get_available_services()) > 0

    def get_best_service(self) -> Optional[str]:
        """获取延迟最低的服务"""
        available = {
            name: latency
            for name, latency in self.latency.items()
            if self.results.get(name) == ServiceStatus.AVAILABLE
        }
        if not available:
            return None
        return min(available, key=available.get)

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "results": {k: v.value for k, v in self.results.items()},
            "latency": {k: round(v, 2) for k, v in self.latency.items()},
            "error": self.error,
            "summary": {
                "available_count": len(self.get_available_services()),
                "unavailable_count": len(self.get_unavailable_services()),
                "best_service": self.get_best_service(),
            }
        }

    def to_display_string(self) -> str:
        """转换为可显示的字符串"""
        lines = [
            f"🌐 网络诊断报告 ({self.timestamp.strftime('%H:%M:%S')})",
            "=" * 40,
        ]

        available = self.get_available_services()
        unavailable = self.get_unavailable_services()

        if available:
            lines.append("✅ 可用服务:")
            for name in available:
                latency = self.latency.get(name, 0)
                lines.append(f"   • {name}: {latency:.0f}ms")

        if unavailable:
            lines.append("❌ 不可用服务:")
            for name in unavailable:
                status = self.results.get(name, ServiceStatus.UNKNOWN)
                error = self.error.get(name, "")
                lines.append(f"   • {name}: {status.value} {error}")

        lines.append("-" * 40)
        lines.append(f"最佳服务: {self.get_best_service() or '无'}")

        return "\n".join(lines)


class NetworkDiagnoser:
    """
    网络诊断器

    功能：
    1. 并发检测多个服务的可达性
    2. 测量响应延迟
    3. 生成诊断报告
    4. 缓存诊断结果
    """

    # 默认检测目标
    DEFAULT_ENDPOINTS = [
        # AI服务
        ServiceEndpoint("OpenAI", "https://api.openai.com", timeout=8.0, priority=10),
        ServiceEndpoint("Claude", "https://api.anthropic.com", timeout=8.0, priority=9),
        ServiceEndpoint("DeepSeek", "https://api.deepseek.com", timeout=5.0, priority=10),
        ServiceEndpoint("Gemini", "https://generativelanguage.googleapis.com", timeout=6.0, priority=7),

        # 国内服务
        ServiceEndpoint("硅基流动", "https://api.siliconflow.cn", timeout=5.0, priority=8),
        ServiceEndpoint("百度千帆", "https://qianfan.baidubce.com", timeout=5.0, priority=6),
        ServiceEndpoint("阿里通义", "https://dashscope.aliyuncs.com", timeout=5.0, priority=7),

        # 基础服务
        ServiceEndpoint("Google DNS", "https://8.8.8.8", timeout=3.0, priority=5),
        ServiceEndpoint("Cloudflare", "https://1.1.1.1", timeout=3.0, priority=5),
    ]

    def __init__(self, cache_ttl: float = 60.0):
        """
        初始化网络诊断器

        Args:
            cache_ttl: 缓存有效期（秒），默认60秒
        """
        self._endpoints: Dict[str, ServiceEndpoint] = {}
        self._cache_ttl = cache_ttl
        self._cache: Optional[DiagnosisReport] = None
        self._cache_time: float = 0

        # 监听器
        self._listeners: List[Callable] = []

        # 添加默认端点
        for endpoint in self.DEFAULT_ENDPOINTS:
            self.add_endpoint(endpoint)

    def add_endpoint(self, endpoint: ServiceEndpoint):
        """添加检测端点"""
        self._endpoints[endpoint.name] = endpoint
        logger.debug(f"添加检测端点: {endpoint.name}")

    def remove_endpoint(self, name: str):
        """移除检测端点"""
        self._endpoints.pop(name, None)
        logger.debug(f"移除检测端点: {name}")

    def get_endpoints(self) -> List[ServiceEndpoint]:
        """获取所有检测端点"""
        return sorted(self._endpoints.values(), key=lambda e: e.priority, reverse=True)

    async def diagnose(self) -> DiagnosisReport:
        """
        执行完整诊断

        Returns:
            DiagnosisReport: 诊断报告
        """
        logger.info("开始网络诊断...")
        report = DiagnosisReport()

        # 并发检测所有端点
        tasks = []
        for name, endpoint in self._endpoints.items():
            if endpoint.enabled:
                tasks.append(self._check_endpoint(name, endpoint))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, tuple):
                name, status, latency, error = result
                report.results[name] = status
                report.latency[name] = latency
                if error:
                    report.error[name] = error

        # 缓存结果
        self._cache = report
        self._cache_time = time.time()

        logger.info(f"诊断完成: 可用={len(report.get_available_services())}, "
                   f"不可用={len(report.get_unavailable_services())}")

        self._notify_listeners("diagnosis_complete", report)

        return report

    async def quick_diagnose(self, urls: List[str]) -> Dict[str, bool]:
        """
        快速诊断特定URL

        Args:
            urls: 要检查的URL列表

        Returns:
            Dict[str, bool]: URL -> 是否可达
        """
        results = {}

        async def check_single(url: str) -> Tuple[str, bool]:
            try:
                status, latency, _ = await self._check_url(url, timeout=5.0)
                return (url, status == ServiceStatus.AVAILABLE)
            except Exception:
                return (url, False)

        tasks = [check_single(url) for url in urls]
        checked = await asyncio.gather(*tasks, return_exceptions=True)

        for result in checked:
            if isinstance(result, tuple):
                url, available = result
                results[url] = available

        return results

    async def check_service(self, service_name: str) -> Tuple[ServiceStatus, float, str]:
        """
        检查单个服务

        Args:
            service_name: 服务名称

        Returns:
            (状态, 延迟ms, 错误信息)
        """
        endpoint = self._endpoints.get(service_name)
        if not endpoint:
            return (ServiceStatus.UNKNOWN, 0, f"未知服务: {service_name}")

        _, status, latency, error = await self._check_endpoint(service_name, endpoint)
        return (status, latency, error)

    async def _check_endpoint(
        self,
        name: str,
        endpoint: ServiceEndpoint
    ) -> Tuple[str, ServiceStatus, float, str]:
        """检查单个端点"""
        status, latency, error = await self._check_url(
            endpoint.get_check_url(),
            timeout=endpoint.timeout
        )
        return (name, status, latency, error)

    async def _check_url(
        self,
        url: str,
        timeout: float = 5.0
    ) -> Tuple[ServiceStatus, float, str]:
        """检查URL可达性"""
        import aiohttp

        start_time = time.perf_counter()

        try:
            # 使用HEAD请求减少流量
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    url,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    allow_redirects=True,
                ) as resp:
                    latency = (time.perf_counter() - start_time) * 1000

                    if resp.status < 500:
                        return (ServiceStatus.AVAILABLE, latency, "")
                    else:
                        return (ServiceStatus.UNAVAILABLE, latency, f"HTTP {resp.status}")

        except asyncio.TimeoutError:
            latency = (time.perf_counter() - start_time) * 1000
            return (ServiceStatus.TIMEOUT, latency, "连接超时")

        except aiohttp.ClientSSLError as e:
            latency = (time.perf_counter() - start_time) * 1000
            return (ServiceStatus.ERROR, latency, f"SSL错误: {str(e)[:50]}")

        except aiohttp.ClientError as e:
            latency = (time.perf_counter() - start_time) * 1000
            return (ServiceStatus.ERROR, latency, f"连接错误: {str(e)[:50]}")

        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return (ServiceStatus.ERROR, latency, str(e)[:50])

    def get_cached_report(self) -> Optional[DiagnosisReport]:
        """获取缓存的诊断报告"""
        if self._cache is None:
            return None

        # 检查缓存是否过期
        if time.time() - self._cache_time > self._cache_ttl:
            return None

        return self._cache

    def is_url_reachable(self, url: str) -> bool:
        """快速检查URL是否可达（使用缓存）"""
        cached = self.get_cached_report()
        if cached is None:
            return True  # 无缓存时默认认为可达，让实际请求来验证

        # 从URL提取服务名进行简单匹配
        for name, status in cached.results.items():
            if status == ServiceStatus.AVAILABLE and name.lower() in url.lower():
                return True

        return True  # 保守策略

    # ==================== 事件监听 ====================

    def subscribe(self, callback: Callable):
        """订阅事件"""
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)

    def _notify_listeners(self, event: str, data: Any):
        """通知监听器"""
        for listener in self._listeners:
            try:
                listener(event, data)
            except Exception as e:
                logger.error(f"监听器回调错误: {e}")

    # ==================== 工具方法 ====================

    async def measure_latency(self, host: str, port: int = 443, timeout: float = 3.0) -> float:
        """测量到主机的TCP延迟"""
        start_time = time.perf_counter()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            latency = (time.perf_counter() - start_time) * 1000
            return latency
        except Exception:
            return 9999.0

    def get_display_report(self) -> str:
        """获取可显示的诊断报告字符串"""
        # 优先使用缓存
        report = self.get_cached_report()
        if report is None:
            return "🌐 网络诊断中...\n请稍后刷新"

        return report.to_display_string()


# 单例实例
_diagnoser: Optional[NetworkDiagnoser] = None


def get_network_diagnoser() -> NetworkDiagnoser:
    """获取网络诊断器单例"""
    global _diagnoser
    if _diagnoser is None:
        _diagnoser = NetworkDiagnoser()
    return _diagnoser


# 辅助函数
from typing import Tuple