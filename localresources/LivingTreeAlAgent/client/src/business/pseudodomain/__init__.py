"""
去中心化伪域名 - 核心模块 (生命之树版本)

基于 P2P 穿透网络、ID 寻址的去中心化域名系统

顶级伪域 (.tree 家族):
- .tree: 主命名空间，寓意"生命之树的一片叶子/一个果实"
- .leaf: 轻量服务/个人内容
- .root: 核心节点/路由/系统服务
- .wood: 社区/论坛/多人协作

命名格式:
- 个人域: {name}.{node-id}.tree (如 shop.8848993321.tree)
- 服务域: {service}.{node-id}.tree (如 blog.8848993321.tree)
- 社区域: {community}.{node-id}.wood (如 forum.8855.wood)
- 根域: {service}.living.root (如 registry.living.root)
- 话题域: topic.seed{hash}.tree (如 topic.seed12345.tree)
- 邮箱域: @{node-id}.leaf (如 @8848993321.leaf)

参考: Unstoppable Domains / IPFS 网关 / LocalSend
"""

from .models import (
    # 枚举
    DomainType,
    ResolutionStatus,
    ContentSource,
    TreeSuffix,
    # 数据模型
    PseudoDomain,
    DomainResolution,
    DomainRegistration,
    NodeEndpoint,
    WebContent,
    # 函数
    parse_pseudo_domain,
    build_personal_domain,
    build_topic_domain,
    build_seed_domain,
    build_mail_domain,
    build_service_domain,
    build_community_domain,
    build_system_domain,
    compute_topic_hash,
    is_pseudo_domain,
    is_tree_domain,
    get_tree_suffix,
    TREE_SUFFIXES,
    ALL_SUFFIXES,
)

from .dns_resolver import (
    DNSResolver,
    DNSResolverConfig,
    DNSServer,
    create_default_resolver,
)

from .web_server import (
    HTTPRequest,
    HTTPResponse,
    WebServer,
    BlogHandler,
    ForumHandler,
    StaticHandler,
    create_default_server,
)

from .content_service import (
    BlogPost,
    ForumTopic,
    ContentService,
    ContentServiceHub,
    create_content_service,
    create_content_service_hub,
)

from .domain_hub import (
    PseudodomainHubConfig,
    PseudodomainHub,
    get_pseudodomain_hub,
    get_pseudodomain_hub_async,
)

__all__ = [
    # 枚举
    "DomainType",
    "ResolutionStatus",
    "ContentSource",
    "TreeSuffix",

    # 数据模型
    "PseudoDomain",
    "DomainResolution",
    "DomainRegistration",
    "NodeEndpoint",
    "WebContent",

    # 函数
    "parse_pseudo_domain",
    "build_personal_domain",
    "build_topic_domain",
    "build_seed_domain",
    "build_mail_domain",
    "build_service_domain",
    "build_community_domain",
    "build_system_domain",
    "compute_topic_hash",
    "is_pseudo_domain",
    "is_tree_domain",
    "get_tree_suffix",
    "TREE_SUFFIXES",
    "ALL_SUFFIXES",

    # DNS
    "DNSResolver",
    "DNSResolverConfig",
    "DNSServer",
    "create_default_resolver",

    # Web
    "HTTPRequest",
    "HTTPResponse",
    "WebServer",
    "BlogHandler",
    "ForumHandler",
    "StaticHandler",
    "create_default_server",

    # 内容服务
    "BlogPost",
    "ForumTopic",
    "ContentService",
    "ContentServiceHub",
    "create_content_service",
    "create_content_service_hub",

    # 核心调度器
    "PseudodomainHubConfig",
    "PseudodomainHub",
    "get_pseudodomain_hub",
    "get_pseudodomain_hub_async",
]
