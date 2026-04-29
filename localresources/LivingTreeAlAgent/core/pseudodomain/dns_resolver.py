"""
去中心化伪域名 - DNS 解析器 (生命之树版本)
客户端 DNS 拦截与解析

功能:
- 拦截 .tree/.leaf/.root/.wood 后缀的域名请求
- 本地解析生命之树伪域名
- DHT/目录服务查询
- 缓存管理
"""

import time
import asyncio
import logging
from typing import Optional, Dict, Callable, List
from dataclasses import dataclass, field
from collections import OrderedDict
import threading

from .models import (
    DomainType, ResolutionStatus, ContentSource, TreeSuffix,
    PseudoDomain, DomainResolution, NodeEndpoint,
    parse_pseudo_domain, is_pseudo_domain, is_tree_domain,
    get_tree_suffix, TREE_SUFFIXES, ALL_SUFFIXES
)

logger = logging.getLogger(__name__)


# LRU 缓存
class LRUCache:
    """简单 LRU 缓存"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[DomainResolution]:
        """获取缓存"""
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                # 检查过期
                if time.time() - entry.cache_time < 3600:
                    self._cache.move_to_end(key)
                    return entry
                else:
                    del self._cache[key]
        return None

    def set(self, key: str, value: DomainResolution):
        """设置缓存"""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            # 清理过期
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def invalidate(self, key: str):
        """使缓存失效"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()


@dataclass
class DNSResolverConfig:
    """DNS 解析器配置"""
    intercept_suffixes: List[str] = field(default_factory=lambda: TREE_SUFFIXES)
    local_port: int = 53           # 本地 DNS 端口
    upstream_dns: List[str] = field(default_factory=lambda: ["8.8.8.8", "1.1.1.1"])
    cache_enabled: bool = True
    cache_ttl: int = 3600         # 缓存 TTL (秒)
    timeout: float = 3.0          # 解析超时 (秒)
    # 本地节点 ID (用于判断是否是本地域名)
    local_node_id: Optional[str] = None


class DNSResolver:
    """
    DNS 解析器

    功能:
    - 拦截特定后缀的域名请求
    - 解析伪域名到节点地址
    - 缓存解析结果
    - 回退到公共 DNS
    """

    def __init__(self, config: DNSResolverConfig = None):
        self.config = config or DNSResolverConfig()
        self._cache = LRUCache() if self.config.cache_enabled else None

        # 回调函数
        self._lookup_callback: Optional[Callable] = None  # 节点查询
        self._content_callback: Optional[Callable] = None  # 内容获取

        # 统计
        self._stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "local_resolved": 0,
            "upstream_queries": 0,
            "failures": 0
        }

    def set_lookup_callback(self, callback: Callable):
        """设置节点查询回调"""
        self._lookup_callback = callback

    def set_content_callback(self, callback: Callable):
        """设置内容获取回调"""
        self._content_callback = callback

    async def resolve(self, domain: str) -> DomainResolution:
        """
        解析域名

        Args:
            domain: 要解析的域名

        Returns:
            DomainResolution: 解析结果
        """
        start_time = time.time()
        self._stats["total_queries"] += 1

        # 检查缓存
        if self._cache:
            cached = self._cache.get(domain)
            if cached:
                self._stats["cache_hits"] += 1
                cached.resolution_time = (time.time() - start_time) * 1000
                return cached

        # 检查是否需要拦截
        if not is_pseudo_domain(domain):
            # 公共域名, 返回无效让系统处理
            self._stats["upstream_queries"] += 1
            return DomainResolution(
                original_domain=domain,
                status=ResolutionStatus.INVALID,
                resolution_time=(time.time() - start_time) * 1000,
                error_message="Not a pseudo domain"
            )

        # 解析伪域名
        result = await self._resolve_pseudo_domain(domain)

        # 缓存结果
        if self._cache and result.status == ResolutionStatus.SUCCESS:
            result.cache_time = time.time()
            self._cache.set(domain, result)

        result.resolution_time = (time.time() - start_time) * 1000
        return result

    async def _resolve_pseudo_domain(self, domain: str) -> DomainResolution:
        """解析伪域名 (生命之树版本)"""
        # 解析域名结构
        domain_type, node_id, subdomain, tree_suffix = parse_pseudo_domain(domain)

        if domain_type is None:
            return DomainResolution(
                original_domain=domain,
                status=ResolutionStatus.INVALID,
                error_message="Invalid pseudo domain format"
            )

        # 查找节点地址
        node_address = None
        if self._lookup_callback:
            try:
                endpoint = await asyncio.wait_for(
                    asyncio.to_thread(self._lookup_callback, node_id),
                    timeout=self.config.timeout
                )
                if endpoint:
                    node_address = endpoint.relay_address or endpoint.direct_address
            except asyncio.TimeoutError:
                return DomainResolution(
                    original_domain=domain,
                    status=ResolutionStatus.TIMEOUT,
                    tree_suffix=tree_suffix,
                    domain_type=domain_type,
                    node_id=node_id,
                    error_message="Node lookup timeout"
                )
            except Exception as e:
                logger.error(f"Node lookup error: {e}")

        # 如果是自己
        if self._is_local_node(node_id):
            return DomainResolution(
                original_domain=domain,
                status=ResolutionStatus.SUCCESS,
                tree_suffix=tree_suffix,
                domain_type=domain_type,
                node_id=node_id,
                node_address="127.0.0.1",
                content_source=self._get_content_source(domain_type, subdomain),
                content_path=f"/{subdomain}",
                resolution_time=0
            )

        # 远程节点
        if node_address:
            return DomainResolution(
                original_domain=domain,
                status=ResolutionStatus.SUCCESS,
                tree_suffix=tree_suffix,
                domain_type=domain_type,
                node_id=node_id,
                node_address=node_address,
                content_source=self._get_content_source(domain_type, subdomain),
                content_path=f"/{subdomain}",
                resolution_time=0
            )
        else:
            # 节点离线
            return DomainResolution(
                original_domain=domain,
                status=ResolutionStatus.OFFLINE,
                tree_suffix=tree_suffix,
                domain_type=domain_type,
                node_id=node_id,
                error_message=f"Node {node_id} is offline"
            )

    def _is_local_node(self, node_id: str) -> bool:
        """检查是否是本地节点"""
        if self.config.local_node_id and node_id == self.config.local_node_id:
            return True
        # TODO: 与系统大脑中的 node_id 比较
        return False

    def _get_content_source(self, domain_type: DomainType, subdomain: str) -> ContentSource:
        """获取内容来源"""
        if subdomain in ["forum", "topic"]:
            return ContentSource.LOCAL_SQLITE
        elif subdomain in ["blog", "wiki"]:
            return ContentSource.CLOUD_STORAGE
        elif subdomain in ["chat", "mail"]:
            return ContentSource.DYNAMIC
        else:
            return ContentSource.DYNAMIC

    def resolve_sync(self, domain: str) -> DomainResolution:
        """同步解析 (兼容非异步环境)"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在异步环境中, 创建新任务
                future = asyncio.ensure_future(self.resolve(domain))
                return future.result()
            else:
                return loop.run_until_complete(self.resolve(domain))
        except Exception as e:
            logger.error(f"Resolve sync error: {e}")
            return DomainResolution(
                original_domain=domain,
                status=ResolutionStatus.INVALID,
                error_message=str(e)
            )

    def resolve_batch(self, domains: List[str]) -> Dict[str, DomainResolution]:
        """批量解析"""
        results = {}
        for domain in domains:
            results[domain] = self.resolve_sync(domain)
        return results

    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = self._stats.copy()
        if self._cache:
            stats["cache_size"] = len(self._cache._cache)
        return stats

    def clear_cache(self):
        """清空缓存"""
        if self._cache:
            self._cache.clear()


class DNSServer:
    """
    本地 DNS 服务器

    在本地端口监听 DNS 请求, 拦截伪域名解析
    """

    def __init__(self, resolver: DNSResolver, port: int = 53):
        self.resolver = resolver
        self.port = port
        self._server = None
        self._running = False

    async def start(self):
        """启动 DNS 服务器"""
        try:
            import aiohttp
        except ImportError:
            logger.warning("aiohttp not available, DNS server disabled")
            return

        # TODO: 实现 UDP DNS 服务器
        # 使用 aiohttp 实现简单的 DNS 拦截
        logger.info(f"DNS server would listen on port {self.port}")
        self._running = True

    async def stop(self):
        """停止 DNS 服务器"""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()


def create_default_resolver(local_node_id: str = None) -> DNSResolver:
    """创建默认解析器 (生命之树版本)"""
    config = DNSResolverConfig(
        intercept_suffixes=TREE_SUFFIXES,
        cache_enabled=True,
        cache_ttl=3600,
        timeout=3.0,
        local_node_id=local_node_id
    )
    return DNSResolver(config)
