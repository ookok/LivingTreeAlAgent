"""
ProxySourceManager - 代理源管理器

功能：
1. 自动检测网络访问失败
2. 从代理池中选择最佳代理
3. 测试代理可用性（速度、稳定性）
4. 自动切换代理（当前不可用时）
5. 记录代理性能历史
6. 与已有 BaseProxyManager 集成
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger


@dataclass
class ProxyInfo:
    """代理信息"""
    url: str
    protocol: str = "http"  # http / https / socks5
    country: str = ""  # 代理所在国家（如果能检测）
    avg_speed_ms: float = 0.0  # 平均响应时间（ms）
    success_rate: float = 0.0  # 成功率 (0-1)
    total_tests: int = 0
    success_tests: int = 0
    last_test_at: float = 0.0
    is_alive: bool = False
    blacklisted: bool = False

    def update_stats(self, success: bool, latency_ms: float):
        """更新统计信息"""
        self.total_tests += 1
        if success:
            self.success_tests += 1
        self.success_rate = self.success_tests / self.total_tests
        # 加权移动平均（最近的测试权重更高）
        alpha = 0.3
        if self.avg_speed_ms == 0:
            self.avg_speed_ms = latency_ms
        else:
            self.avg_speed_ms = alpha * latency_ms + (1 - alpha) * self.avg_speed_ms
        self.last_test_at = time.time()
        self.is_alive = success


@dataclass
class ProxyTestResult:
    """代理测试结果"""
    proxy: ProxyInfo
    success: bool
    latency_ms: float
    error: str = ""


class ProxySourceManager:
    """
    代理源管理器

    功能：
    1. 从多个来源加载代理列表
    2. 自动测试代理可用性
    3. 选择最佳代理
    4. 自动切换代理
    5. 记录性能历史

    用法：
        manager = ProxySourceManager()
        proxy = await manager.get_best_proxy()
        # 使用代理...
        # 如果失败：
        await manager.report_failure(proxy_url)
        # 自动切换
        new_proxy = await manager.get_best_proxy()
    """

    def __init__(self, config=None):
        """
        初始化代理源管理器

        Args:
            config: 配置字典（可选）
        """
        self._proxies: Dict[str, ProxyInfo] = {}  # url -> ProxyInfo
        self._current_proxy: Optional[str] = None  # 当前使用的代理
        self._test_url = "https://www.baidu.com"  # 测试 URL（国内可达）
        self._test_timeout = 10  # 测试超时（秒）
        self._max_retries = 3  # 最大重试次数
        self._auto_switch = True  # 自动切换
        self._stats: Dict[str, Any] = {
            "total_requests": 0,
            "proxy_requests": 0,
            "direct_requests": 0,
            "proxy_failures": 0,
            "auto_switches": 0,
        }
        self._logger = logger.bind(component="ProxySourceManager")

        # 从配置加载
        if config:
            self._load_from_config(config)

    # ── 代理加载 ──────────────────────────────────────────

    def _load_from_config(self, config: dict):
        """从配置加载代理列表"""
        proxy_list = config.get("proxy_pool", [])
        for proxy_url in proxy_list:
            self._add_proxy(proxy_url)
        self._logger.info(f"从配置加载了 {len(proxy_list)} 个代理")

    def _add_proxy(self, url: str, protocol: str = "http") -> ProxyInfo:
        """添加代理"""
        url = url.strip()
        if url in self._proxies:
            return self._proxies[url]

        proxy = ProxyInfo(url=url, protocol=protocol)
        self._proxies[url] = proxy
        return proxy

    async def load_from_proxy_manager(self):
        """从已有的 BaseProxyManager 加载代理列表"""
        try:
            from business.base_proxy_manager import BaseProxyManager
            manager = BaseProxyManager()
            if hasattr(manager, 'get_all_proxies'):
                proxies = manager.get_all_proxies()
                for p in proxies:
                    url = p if isinstance(p, str) else getattr(p, 'url', str(p))
                    self._add_proxy(url)
                self._logger.info(f"从 BaseProxyManager 加载了 {len(proxies)} 个代理")
            elif hasattr(manager, 'get_proxy'):
                proxy = manager.get_proxy()
                if proxy:
                    url = proxy if isinstance(proxy, str) else getattr(proxy, 'url', str(proxy))
                    self._add_proxy(url)
                    self._logger.info("从 BaseProxyManager 加载了 1 个代理")
        except Exception as e:
            self._logger.warning(f"从 BaseProxyManager 加载代理失败: {e}")

    async def load_from_api(self, api_url: str):
        """从代理 API 加载代理列表"""
        try:
            import urllib.request
            import json

            req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        self._add_proxy(item)
                    elif isinstance(item, dict):
                        self._add_proxy(item.get("url", ""), item.get("protocol", "http"))
                self._logger.info(f"从 API 加载了 {len(data)} 个代理")
        except Exception as e:
            self._logger.warning(f"从 API 加载代理失败: {e}")

    # ── 代理测试 ──────────────────────────────────────────

    async def test_proxy(self, proxy: ProxyInfo) -> ProxyTestResult:
        """
        测试单个代理的可用性

        Returns:
            ProxyTestResult
        """
        try:
            import urllib.request

            start_time = time.time()
            req = urllib.request.Request(
                self._test_url,
                headers={"User-Agent": "Mozilla/5.0"},
            )

            # 添加代理
            handler = urllib.request.ProxyHandler({
                proxy.protocol: proxy.url
            })
            opener = urllib.request.build_opener(handler)

            resp = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: opener.open(req, timeout=self._test_timeout)
            )
            latency = (time.time() - start_time) * 1000  # ms
            resp.read()

            proxy.update_stats(success=True, latency_ms=latency)
            return ProxyTestResult(proxy=proxy, success=True, latency_ms=latency)

        except Exception as e:
            latency = self._test_timeout * 1000
            proxy.update_stats(success=False, latency_ms=latency)
            return ProxyTestResult(
                proxy=proxy, success=False, latency_ms=latency, error=str(e)
            )

    async def test_all_proxies(self) -> List[ProxyTestResult]:
        """测试所有代理"""
        self._logger.info(f"开始测试 {len(self._proxies)} 个代理...")

        tasks = []
        for proxy in self._proxies.values():
            if not proxy.blacklisted:
                tasks.append(self.test_proxy(proxy))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []
        for r in results:
            if isinstance(r, ProxyTestResult):
                valid_results.append(r)

        alive_count = sum(1 for r in valid_results if r.success)
        self._logger.info(
            f"测试完成: {alive_count}/{len(valid_results)} 个代理可用"
        )

        return valid_results

    # ── 代理选择 ──────────────────────────────────────────

    def _select_best_proxy(self) -> Optional[ProxyInfo]:
        """选择最佳代理（基于速度和成功率）"""
        alive_proxies = [
            p for p in self._proxies.values()
            if p.is_alive and not p.blacklisted
        ]

        if not alive_proxies:
            return None

        # 综合评分：速度权重 0.4，成功率权重 0.6
        def score(p: ProxyInfo) -> float:
            # 速度越低越好（归一化到 0-1）
            speed_score = max(0, 1 - p.avg_speed_ms / 5000)
            reliability_score = p.success_rate
            return 0.4 * speed_score + 0.6 * reliability_score

        return max(alive_proxies, key=score)

    async def get_best_proxy(self) -> Optional[str]:
        """
        获取最佳代理 URL

        Returns:
            代理 URL，如果没有可用代理则返回 None
        """
        # 1. 尝试使用当前代理
        if self._current_proxy:
            current = self._proxies.get(self._current_proxy)
            if current and current.is_alive and not current.blacklisted:
                return self._current_proxy

        # 2. 选择最佳代理
        best = self._select_best_proxy()
        if best:
            self._current_proxy = best.url
            return best.url

        # 3. 没有可用代理，尝试加载
        self._logger.info("没有可用代理，尝试加载...")
        await self.load_from_proxy_manager()

        best = self._select_best_proxy()
        if best:
            self._current_proxy = best.url
            return best.url

        self._logger.warning("没有可用代理")
        return None

    def report_failure(self, proxy_url: str):
        """报告代理失败"""
        proxy = self._proxies.get(proxy_url)
        if proxy:
            proxy.update_stats(success=False, latency_ms=self._test_timeout * 1000)
            self._stats["proxy_failures"] += 1

            # 如果失败次数过多，暂时拉黑
            if proxy.total_tests >= 3 and proxy.success_rate < 0.2:
                proxy.blacklisted = True
                self._logger.warning(f"代理已拉黑（成功率过低）: {proxy_url}")

            # 自动切换
            if self._auto_switch and self._current_proxy == proxy_url:
                self._current_proxy = None
                self._stats["auto_switches"] += 1
                self._logger.info("代理已自动切换")

    def report_success(self, proxy_url: str, latency_ms: float = 0):
        """报告代理成功"""
        proxy = self._proxies.get(proxy_url)
        if proxy:
            proxy.update_stats(success=True, latency_ms=latency_ms)

    # ── 工具方法 ──────────────────────────────────────────

    def list_proxies(self) -> List[Dict[str, Any]]:
        """列出所有代理"""
        return [
            {
                "url": p.url,
                "alive": p.is_alive,
                "speed_ms": round(p.avg_speed_ms, 1),
                "success_rate": round(p.success_rate, 2),
                "tests": p.total_tests,
                "blacklisted": p.blacklisted,
                "current": p.url == self._current_proxy,
            }
            for p in self._proxies.values()
        ]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        alive_count = sum(1 for p in self._proxies.values() if p.is_alive)
        return {
            **self._stats,
            "total_proxies": len(self._proxies),
            "alive_proxies": alive_count,
            "blacklisted_proxies": sum(1 for p in self._proxies.values() if p.blacklisted),
            "current_proxy": self._current_proxy,
        }

    async def refresh_proxies(self):
        """刷新代理列表（重新加载 + 测试）"""
        self._logger.info("刷新代理列表...")
        await self.load_from_proxy_manager()
        await self.test_all_proxies()
        self._logger.info(f"刷新完成: {self.get_stats()['alive_proxies']} 个代理可用")
