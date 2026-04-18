"""
AI驱动的网络优化系统
AI-Driven Network Optimization System

核心功能:
1. 智能镜像发现与验证
2. 预测性网络优化
3. 自适应路由选择
4. 网络质量监测

Author: Hermes Desktop Team
"""

import asyncio
import time
import socket
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import threading
import re


# ============================================================
# 第一部分：配置与枚举
# ============================================================

class RouteStrategy(Enum):
    """路由策略"""
    DIRECT = "direct"           # 直接访问
    PROXY = "proxy"            # 代理访问
    MIRROR = "mirror"          # 镜像访问
    FALLBACK = "fallback"       # 兜底访问


class MirrorSource(Enum):
    """镜像来源"""
    KNOWN = "known"            # 已知镜像
    DISCOVERED = "discovered"  # 自动发现
    PREDICTED = "predicted"    # AI预测
    USER_CONFIG = "user"        # 用户配置


@dataclass
class MirrorInfo:
    """镜像信息"""
    url: str
    source: MirrorSource
    latency_ms: float = 0.0
    success_rate: float = 1.0  # 0-1
    last_check: float = field(default_factory=time.time)
    score: float = 0.0
    is_available: bool = True
    freshness: float = 1.0  # 内容新鲜度
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutePlan:
    """路由方案"""
    strategy: RouteStrategy
    primary_url: str
    fallback_urls: List[str] = field(default_factory=list)
    estimated_latency_ms: float = 0.0
    cost_score: float = 0.0  # 综合成本评分
    reasoning: str = ""


# ============================================================
# 第二部分：镜像模式库
# ============================================================

class MirrorPatternLibrary:
    """镜像模式库"""

    PATTERNS = {
        "github.com": [
            {"url": "https://github.com", "type": "official"},
            {"url": "https://hub.fastgit.xyz", "type": "fastgit"},
            {"url": "https://github.com.cnpmjs.org", "type": "cnpmjs"},
            {"url": "https://ghproxy.net", "type": "proxy"},
            {"url": "https://mirror.ghproxy.com", "type": "proxy"},
        ],
        "pypi.org": [
            {"url": "https://pypi.org", "type": "official"},
            {"url": "https://pypi.tuna.tsinghua.edu.cn", "type": "tsinghua"},
            {"url": "https://mirrors.aliyun.com/pypi", "type": "aliyun"},
            {"url": "https://pypi.mirrors.ustc.edu.cn", "type": "ustc"},
        ],
        "npmjs.com": [
            {"url": "https://www.npmjs.com", "type": "official"},
            {"url": "https://registry.npmmirror.com", "type": "npmmirror"},
            {"url": "https://registry.cnpmjs.org", "type": "cnpmjs"},
        ],
        "docker.io": [
            {"url": "https://docker.io", "type": "official"},
            {"url": "https://docker.mirrors.ustc.edu.cn", "type": "ustc"},
        ],
        "raw.githubusercontent.com": [
            {"url": "https://raw.githubusercontent.com", "type": "official"},
            {"url": "https://raw.fastgit.xyz", "type": "fastgit"},
            {"url": "https://ghproxy.net/https://raw.githubusercontent.com", "type": "proxy"},
        ],
        "huggingface.co": [
            {"url": "https://huggingface.co", "type": "official"},
            {"url": "https://hf-mirror.com", "type": "mirror"},
        ],
    }

    REPLACE_RULES = [
        (r"github\.com", "hub.fastgit.xyz"),
        (r"github\.com", "github.com.cnpmjs.org"),
        (r"raw\.githubusercontent\.com", "raw.fastgit.xyz"),
        (r"pypi\.org/simple", "pypi.tuna.tsinghua.edu.cn/simple"),
        (r"pypi\.org", "pypi.tuna.tsinghua.edu.cn"),
        (r"registry\.npmjs\.org", "registry.npmmirror.com"),
    ]

    @classmethod
    def get_mirror_candidates(cls, url: str) -> List[str]:
        """获取镜像候选列表"""
        candidates = [url]

        for base_url, mirrors in cls.PATTERNS.items():
            if base_url in url:
                for mirror in mirrors:
                    if mirror["type"] != "official":
                        mirror_url = url.replace(base_url, mirror["url"].replace("https://", ""))
                        candidates.append(mirror_url)
                break

        for pattern, replacement in cls.REPLACE_RULES:
            if re.search(pattern, url):
                candidate = re.sub(pattern, replacement, url)
                if candidate not in candidates:
                    candidates.append(candidate)

        return candidates

    @classmethod
    def get_all_mirrors_for_service(cls, service: str) -> List[Dict]:
        """获取服务的所有已知镜像"""
        return cls.PATTERNS.get(service, [])


# ============================================================
# 第三部分：镜像发现器
# ============================================================

class MirrorDiscoverer:
    """智能镜像发现器"""

    def __init__(self):
        self._lock = threading.Lock()
        self.mirror_cache: Dict[str, List[MirrorInfo]] = {}
        self.mirror_history: Dict[str, List[Dict]] = {}
        self.max_history = 100
        print("[MirrorDiscoverer] 初始化镜像发现器")

    async def discover_mirrors(self, url: str, max_candidates: int = 5) -> List[MirrorInfo]:
        """发现可用镜像"""
        candidates = MirrorPatternLibrary.get_mirror_candidates(url)
        candidates = candidates[:max_candidates * 2]

        tasks = [self._test_mirror(candidate) for candidate in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_mirrors = []
        for result in results:
            if isinstance(result, MirrorInfo) and result.is_available:
                valid_mirrors.append(result)

        valid_mirrors.sort(key=lambda x: x.score, reverse=True)

        if valid_mirrors:
            with self._lock:
                self.mirror_cache[url] = valid_mirrors

        return valid_mirrors[:max_candidates]

    async def _test_mirror(self, url: str) -> MirrorInfo:
        """测试单个镜像"""
        start_time = time.time()
        mirror_info = MirrorInfo(
            url=url,
            source=MirrorSource.DISCOVERED,
            last_check=time.time()
        )

        try:
            host = url.replace('https://', '').replace('http://', '').split('/')[0]
            port = 443 if url.startswith('https') else 80

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()

            latency = (time.time() - start_time) * 1000

            if result == 0:
                mirror_info.is_available = True
                mirror_info.latency_ms = latency
                mirror_info.score = self._calculate_score(latency, 1.0, 1.0)
            else:
                mirror_info.is_available = False
                mirror_info.score = 0.0

        except Exception:
            mirror_info.is_available = False
            mirror_info.score = 0.0

        return mirror_info

    def _calculate_score(self, latency_ms: float, success_rate: float,
                        freshness: float) -> float:
        """计算镜像综合评分"""
        latency_score = max(0, 1.0 - latency_ms / 1000)
        score = 0.4 * latency_score + 0.3 * success_rate + 0.3 * freshness
        return score

    def get_best_mirror(self, url: str) -> Optional[MirrorInfo]:
        """获取最佳镜像（从缓存）"""
        with self._lock:
            mirrors = self.mirror_cache.get(url, [])
            if mirrors and mirrors[0].is_available:
                return mirrors[0]
        return None

    def learn_mirror_choice(self, url: str, chosen_mirror: str, success: bool,
                           latency_ms: float):
        """从选择中学习"""
        with self._lock:
            if url not in self.mirror_history:
                self.mirror_history[url] = []

            self.mirror_history[url].append({
                "mirror": chosen_mirror,
                "success": success,
                "latency": latency_ms,
                "timestamp": time.time()
            })

            if len(self.mirror_history[url]) > self.max_history:
                self.mirror_history[url] = self.mirror_history[url][-self.max_history:]

            mirrors = self.mirror_cache.get(url, [])
            for mirror in mirrors:
                if mirror.url == chosen_mirror:
                    if success:
                        mirror.score = mirror.score * 0.8 + 0.2 * self._calculate_score(
                            latency_ms, 1.0, 1.0
                        )
                    else:
                        mirror.score *= 0.5


# ============================================================
# 第四部分：网络优化器
# ============================================================

class NetworkPatternLearner:
    """网络模式学习器"""

    def __init__(self):
        self._lock = threading.Lock()
        self.time_patterns: Dict[int, Dict[str, int]] = {}
        self.access_sequences: Dict[str, List[str]] = {}
        self.failure_patterns: Dict[str, Dict[str, int]] = {}
        print("[NetworkPatternLearner] 初始化网络模式学习器")

    def record_access(self, url: str, success: bool, latency_ms: float,
                     error: Optional[str] = None):
        """记录访问"""
        with self._lock:
            hour = datetime.now().hour
            domain = self._extract_domain(url)

            if hour not in self.time_patterns:
                self.time_patterns[hour] = {}

            if domain:
                self.time_patterns[hour][domain] = self.time_patterns[hour].get(domain, 0) + 1

            if not success and error:
                if url not in self.failure_patterns:
                    self.failure_patterns[url] = {}
                self.failure_patterns[url][error] = \
                    self.failure_patterns[url].get(error, 0) + 1

    def _extract_domain(self, url: str) -> Optional[str]:
        """提取域名"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return None

    def predict_next_access(self, current_url: str) -> List[str]:
        """预测下一次访问"""
        with self._lock:
            return self.access_sequences.get(current_url, [])[:5]

    def predict_network_condition(self, hour: int) -> Dict[str, float]:
        """预测指定时段的网络状况"""
        with self._lock:
            if hour in self.time_patterns:
                domains = self.time_patterns[hour]
                total = sum(domains.values())
                peak_domains = sorted(domains.items(), key=lambda x: x[1], reverse=True)[:3]

                return {
                    "predicted_peak": True if total > 50 else False,
                    "top_domains": [d[0] for d in peak_domains],
                    "expected_latency": 150.0 if total > 50 else 100.0
                }

            return {"predicted_peak": False, "top_domains": [], "expected_latency": 100.0}


class AI_NetworkOptimizer:
    """AI驱动的网络优化器"""

    def __init__(self):
        self.mirror_discoverer = MirrorDiscoverer()
        self.pattern_learner = NetworkPatternLearner()
        self._proxy_list: List[str] = []
        self._enabled = True
        print("[AI_NetworkOptimizer] 初始化AI网络优化器")

    async def get_route_plan(self, url: str, context: Optional[Dict] = None) -> RoutePlan:
        """获取路由方案"""
        if context is None:
            context = {}

        best_mirror = self.mirror_discoverer.get_best_mirror(url)
        if best_mirror and best_mirror.score > 0.7:
            return RoutePlan(
                strategy=RouteStrategy.MIRROR,
                primary_url=best_mirror.url,
                estimated_latency_ms=best_mirror.latency_ms,
                cost_score=best_mirror.score,
                reasoning=f"使用已知最佳镜像 (评分: {best_mirror.score:.2f})"
            )

        mirrors = await self.mirror_discoverer.discover_mirrors(url, max_candidates=5)

        if mirrors:
            best = mirrors[0]
            fallbacks = [m.url for m in mirrors[1:3]]

            return RoutePlan(
                strategy=RouteStrategy.MIRROR if best.score > 0.5 else RouteStrategy.DIRECT,
                primary_url=best.url if best.score > 0.5 else url,
                fallback_urls=fallbacks,
                estimated_latency_ms=best.latency_ms,
                cost_score=best.score,
                reasoning=f"AI发现最佳镜像 (评分: {best.score:.2f})"
            )

        return RoutePlan(
            strategy=RouteStrategy.DIRECT,
            primary_url=url,
            fallback_urls=[],
            estimated_latency_ms=500.0,
            cost_score=0.5,
            reasoning="无可用镜像，使用直接访问"
        )

    async def intelligent_fetch(self, url: str, use_proxy: bool = False) -> Dict:
        """智能获取"""
        route = await self.get_route_plan(url)

        success = True
        latency = route.estimated_latency_ms

        self.pattern_learner.record_access(url, success, latency)

        if route.primary_url != url:
            self.mirror_discoverer.learn_mirror_choice(
                url, route.primary_url, success, latency
            )

        return {
            "url": url,
            "route": route.strategy.value,
            "actual_url": route.primary_url,
            "fallbacks": route.fallback_urls,
            "estimated_latency": latency,
            "reasoning": route.reasoning
        }

    def add_proxy(self, proxy_url: str):
        """添加代理"""
        if proxy_url not in self._proxy_list:
            self._proxy_list.append(proxy_url)

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "enabled": self._enabled,
            "proxy_count": len(self._proxy_list),
            "cached_mirrors": len(self.mirror_discoverer.mirror_cache)
        }


# ============================================================
# 第五部分：工厂函数与单例
# ============================================================

_network_optimizer_instance: Optional[AI_NetworkOptimizer] = None
_optimizer_lock = threading.Lock()


def get_network_optimizer() -> AI_NetworkOptimizer:
    """获取网络优化器单例"""
    global _network_optimizer_instance

    if _network_optimizer_instance is None:
        with _optimizer_lock:
            if _network_optimizer_instance is None:
                _network_optimizer_instance = AI_NetworkOptimizer()

    return _network_optimizer_instance


# ============================================================
# 第六部分：使用示例
# ============================================================

async def example_usage():
    """使用示例"""

    print("=" * 60)
    print("AI 网络优化系统示例")
    print("=" * 60)

    optimizer = get_network_optimizer()

    print("\n1. 智能路由选择:")
    urls = [
        "https://github.com/microsoft/vscode",
        "https://pypi.org/pip",
        "https://www.npmjs.com/package/express"
    ]

    for url in urls:
        route = await optimizer.get_route_plan(url)
        print(f"\n  URL: {url}")
        print(f"    策略: {route.strategy.value}")
        print(f"    实际URL: {route.primary_url}")
        print(f"    预估延迟: {route.estimated_latency_ms:.0f}ms")
        print(f"    评分: {route.cost_score:.2f}")

    print("\n2. 网络模式学习:")
    optimizer.pattern_learner.record_access(
        "https://github.com/python/cpython", success=True, latency_ms=120
    )
    optimizer.pattern_learner.record_access(
        "https://github.com/django/django", success=True, latency_ms=150
    )

    hour = datetime.now().hour
    prediction = optimizer.pattern_learner.predict_network_condition(hour)
    print(f"  {hour}:00 网络状况:")
    print(f"    预计高峰: {prediction['predicted_peak']}")
    print(f"    预期延迟: {prediction['expected_latency']:.0f}ms")

    print("\n3. 系统统计:")
    stats = optimizer.get_statistics()
    for key, value in stats.items():
        print(f"    {key}: {value}")


if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(example_usage())