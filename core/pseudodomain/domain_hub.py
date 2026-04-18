"""
去中心化伪域名 - 核心调度器 (生命之树版本)
整合所有伪域名模块的统一入口

功能:
- 域名注册与管理
- DNS 解析
- Web 服务器
- 内容服务
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass

from .models import (
    DomainType, ResolutionStatus, ContentSource, TreeSuffix,
    PseudoDomain, DomainResolution, DomainRegistration, NodeEndpoint,
    parse_pseudo_domain, build_personal_domain, build_service_domain,
    build_topic_domain, build_seed_domain, build_mail_domain,
    build_community_domain, build_system_domain,
    is_pseudo_domain, is_tree_domain, get_tree_suffix, TREE_SUFFIXES
)
from .dns_resolver import DNSResolver, DNSResolverConfig, create_default_resolver
from .web_server import WebServer, create_default_server
from .content_service import ContentService, ContentServiceHub, create_content_service

logger = logging.getLogger(__name__)


@dataclass
class PseudodomainHubConfig:
    """伪域名配置 (生命之树版本)"""
    node_id: str = ""                    # 当前节点 ID
    display_name: str = "Anonymous"      # 显示名称
    web_server_port: int = 8080           # Web 服务器端口
    dns_enabled: bool = False            # 是否启用本地 DNS
    default_suffix: TreeSuffix = TreeSuffix.TREE  # 默认后缀


class PseudodomainHub:
    """
    伪域名核心调度器 (单例)

    整合:
    - DNSResolver: DNS 解析
    - WebServer: Web 服务
    - ContentService: 内容服务
    """

    _instance: Optional['PseudodomainHub'] = None
    _lock = asyncio.Lock()

    def __init__(self, config: PseudodomainHubConfig = None):
        self.config = config or PseudodomainHubConfig()

        # DNS 解析器
        self.dns_resolver = create_default_resolver()

        # Web 服务器
        self.web_server = create_default_server(self.config.web_server_port)

        # 内容服务
        self.content_service = create_content_service()
        self.content_hub = ContentServiceHub()
        self.content_hub.content_service = self.content_service

        # 本地域名注册表
        self._local_domains: Dict[str, DomainRegistration] = {}
        self._init_default_domains()

        # 节点端点缓存
        self._node_endpoints: Dict[str, NodeEndpoint] = {}

        # UI 回调
        self._ui_callbacks: Dict[str, List[Callable]] = {
            "domain_registered": [],
            "domain_resolved": [],
            "content_requested": [],
        }

        # 统计
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "local_served": 0,
            "remote_requests": 0
        }

        # 已初始化
        self._initialized = False

    def _init_default_domains(self):
        """初始化默认域名 (生命之树版本)"""
        if not self.config.node_id:
            return

        suffix = self.config.default_suffix

        # 个人主页: name.node.tree
        self.register_domain(
            name=self.config.display_name.lower().replace(" ", "_"),
            domain_type=DomainType.PERSONAL,
            content_type="blog",
            content_path="/",
            suffix=suffix
        )

        # 博客: blog.node.tree
        self.register_domain(
            name="blog",
            domain_type=DomainType.SERVICE,
            content_type="blog",
            content_path="/",
            suffix=suffix
        )

        # 论坛: forum.node.wood
        self.register_domain(
            name="forum",
            domain_type=DomainType.COMMUNITY,
            content_type="forum",
            content_path="/",
            suffix=TreeSuffix.WOOD
        )

        # 邮箱: @node.leaf
        self.register_domain(
            name=self.config.node_id,
            domain_type=DomainType.MAIL,
            content_type="mail",
            content_path="/inbox",
            suffix=TreeSuffix.LEAF
        )

        # 便签: note.node.leaf
        self.register_domain(
            name="note",
            domain_type=DomainType.SERVICE,
            content_type="note",
            content_path="/",
            suffix=TreeSuffix.LEAF
        )

    async def _init_async(self):
        """异步初始化"""
        if self._initialized:
            return

        # 设置内容服务回调
        self.web_server.set_content_callback(self._handle_content_request)

        # 设置 DNS 解析回调
        self.dns_resolver.set_lookup_callback(self._lookup_node)
        self.dns_resolver.set_content_callback(self._handle_content_request)

        # 启动 Web 服务器
        try:
            await self.web_server.start()
        except Exception as e:
            logger.error(f"Web server start error: {e}")

        self._initialized = True

    def ensure_initialized(self):
        """确保已初始化"""
        if not self._initialized:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._init_async())
            except RuntimeError:
                pass

    @classmethod
    def get_hub(cls) -> 'PseudodomainHub':
        """获取单例"""
        if cls._instance is None:
            cls._instance = PseudodomainHub()
        return cls._instance

    @classmethod
    async def get_hub_async(cls) -> 'PseudodomainHub':
        """异步获取单例"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = PseudodomainHub()
            await cls._instance._init_async()
            return cls._instance

    def add_ui_callback(self, event: str, callback: Callable):
        """添加 UI 回调"""
        if event in self._ui_callbacks:
            self._ui_callbacks[event].append(callback)

    def _emit(self, event: str, *args, **kwargs):
        """触发回调"""
        for callback in self._ui_callbacks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(*args, **kwargs))
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"UI callback error for {event}: {e}")

    def register_domain(self, name: str, domain_type: DomainType,
                       content_type: str, content_path: str,
                       public_key: str = None,
                       suffix: TreeSuffix = None) -> DomainRegistration:
        """注册伪域名 (生命之树版本)"""
        suffix = suffix or self.config.default_suffix

        if domain_type == DomainType.MAIL:
            domain = build_mail_domain(self.config.node_id, suffix)
        elif domain_type == DomainType.TOPIC:
            domain = build_topic_domain(name, suffix)
        elif domain_type == DomainType.COMMUNITY:
            domain = build_community_domain(name, self.config.node_id)
        elif domain_type == DomainType.SYSTEM:
            domain = build_system_domain(name)
        elif domain_type == DomainType.SERVICE:
            domain = build_service_domain(name, self.config.node_id, suffix)
        else:
            domain = build_personal_domain(name, self.config.node_id, suffix)

        registration = DomainRegistration(
            domain=domain,
            domain_type=domain_type,
            tree_suffix=suffix,
            node_id=self.config.node_id,
            owner_name=self.config.display_name,
            content_type=content_type,
            content_path=content_path,
            public_key=public_key
        )

        self._local_domains[domain] = registration
        self._emit("domain_registered", registration)

        logger.info(f"Domain registered: {domain}")
        return registration

    def get_domain(self, domain: str) -> Optional[DomainRegistration]:
        """获取域名注册信息"""
        return self._local_domains.get(domain)

    def get_my_domains(self) -> List[DomainRegistration]:
        """获取我的所有域名"""
        return list(self._local_domains.values())

    def is_my_domain(self, domain: str) -> bool:
        """检查是否是当前节点的域名"""
        if domain in self._local_domains:
            return True
        domain_type, node_id, _, _ = parse_pseudo_domain(domain)
        return node_id == self.config.node_id

    async def resolve(self, domain: str) -> DomainResolution:
        """解析域名"""
        self._stats["total_requests"] += 1

        if self.is_my_domain(domain):
            self._stats["local_served"] += 1
            resolution = await self._resolve_local(domain)
            self._emit("domain_resolved", domain, resolution)
            return resolution

        self._stats["remote_requests"] += 1
        return await self.dns_resolver.resolve(domain)

    async def _resolve_local(self, domain: str) -> DomainResolution:
        """解析本地域名 (生命之树版本)"""
        import time
        start = time.time()

        domain_type, node_id, subdomain, tree_suffix = parse_pseudo_domain(domain)

        if subdomain in ["blog", "wiki", "note"]:
            content_source = ContentSource.CLOUD_STORAGE
        elif subdomain in ["forum", "topic", "talk"]:
            content_source = ContentSource.LOCAL_SQLITE
        elif subdomain in ["chat", "mail", "email"]:
            content_source = ContentSource.DYNAMIC
        else:
            content_source = ContentSource.DYNAMIC

        return DomainResolution(
            original_domain=domain,
            status=ResolutionStatus.SUCCESS,
            tree_suffix=tree_suffix,
            domain_type=domain_type,
            node_id=self.config.node_id,
            node_address="127.0.0.1",
            content_source=content_source,
            content_path=f"/{subdomain}" if subdomain else "/",
            resolution_time=(time.time() - start) * 1000
        )

    async def _lookup_node(self, node_id: str) -> Optional[NodeEndpoint]:
        """查找节点"""
        if node_id in self._node_endpoints:
            return self._node_endpoints[node_id]
        return None

    def cache_node_endpoint(self, endpoint: NodeEndpoint):
        """缓存节点端点"""
        self._node_endpoints[endpoint.node_id] = endpoint

    async def _handle_content_request(self, content_type: str, action: str, params: Dict[str, Any]) -> Any:
        """处理内容请求"""
        self._emit("content_requested", content_type, action, params)
        if self.is_my_domain(params.get("domain", "")):
            return await self.content_service.get_content(content_type, action, params)
        return None

    async def get_blog_posts(self) -> List[Dict]:
        """获取博客文章"""
        return await self.content_service.get_content("blog", "list", {"node_id": self.config.node_id})

    async def get_forum_topics(self) -> List[Dict]:
        """获取论坛话题"""
        return await self.content_service.get_content("forum", "list_topics", {"node_id": self.config.node_id})

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        stats = self._stats.copy()
        stats["local_domains"] = len(self._local_domains)
        stats["cached_nodes"] = len(self._node_endpoints)
        stats["dns_stats"] = self.dns_resolver.get_stats()
        stats["web_server_running"] = self.web_server.is_running()
        return stats

    def get_web_server_url(self) -> str:
        """获取 Web 服务器 URL"""
        return f"http://127.0.0.1:{self.config.web_server_port}"

    def get_available_domains(self) -> List[str]:
        """获取可用的域名格式 (生命之树版本)"""
        suffix = self.config.default_suffix
        return [
            f"blog.{self.config.node_id}{suffix.value if hasattr(suffix, 'value') else suffix}",
            f"forum.{self.config.node_id}.wood",
            f"{self.config.display_name.lower()}.{self.config.node_id}{suffix.value if hasattr(suffix, 'value') else suffix}",
            f"@{self.config.node_id}.leaf",
            f"note.{self.config.node_id}.leaf",
        ]


def get_pseudodomain_hub() -> PseudodomainHub:
    """获取 PseudodomainHub 单例"""
    return PseudodomainHub.get_hub()


async def get_pseudodomain_hub_async() -> PseudodomainHub:
    """异步获取 PseudodomainHub 单例"""
    return await PseudodomainHub.get_hub_async()
