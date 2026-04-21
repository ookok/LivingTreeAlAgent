"""
去中心化伪域名 - 生命之树 (Living Tree AI) 版本
定义去中心化 URI 命名规则和解析规则

顶级伪域 (.tree 家族):
- .tree: 主命名空间，寓意"生命之树的一片叶子/一个果实"
- .leaf: 轻量服务/个人内容
- .root: 核心节点/路由/系统服务
- .wood: 社区/论坛/多人协作

命名格式:
- 个人域: {name}.{node-id}.tree (如 shop.8848993321.tree)
- 服务域: {service}.{node-id}.tree (如 blog.8848993321.tree)
- 社区域: {community}.{node-id}.wood (如 forum.8848993321.wood)
- 根域: {service}.living.root (如 registry.living.root)
- 话题域: topic.seed{hash}.tree (如 topic.seed12345.tree)
- 邮箱域: @{node-id}.leaf (如 @8848993321.leaf)
"""

import time
import hashlib
import re
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ==================== 枚举 ====================

class TreeSuffix(Enum):
    """生命之树顶级域名后缀"""
    TREE = ".tree"       # 主命名空间: 生命之树的一片叶子/果实
    LEAF = ".leaf"       # 轻量服务: 个人内容/轻量服务
    ROOT = ".root"       # 核心节点: 系统服务/路由/注册表
    WOOD = ".wood"       # 社区: 论坛/多人协作

    @property
    def emoji(self) -> str:
        """后缀对应的 Emoji"""
        return {
            TreeSuffix.TREE: "🌳",
            TreeSuffix.LEAF: "🍃",
            TreeSuffix.ROOT: "🌱",
            TreeSuffix.WOOD: "🌲"
        }.get(self, "🌐")

    @property
    def description(self) -> str:
        """后缀描述"""
        return {
            TreeSuffix.TREE: "个人主页/商店/博客",
            TreeSuffix.LEAF: "轻量服务/邮箱/便签",
            TreeSuffix.ROOT: "核心系统/路由/注册",
            TreeSuffix.WOOD: "社区/论坛/协作空间"
        }.get(self, "")

    @classmethod
    def from_string(cls, suffix: str) -> Optional['TreeSuffix']:
        """从字符串获取后缀枚举"""
        suffix = suffix.lower().strip()
        for s in cls:
            if s.value == suffix or s.value == "." + suffix:
                return s
        return None


class DomainType(Enum):
    """域名类型"""
    PERSONAL = "personal"      # 个人域: shop.8848993321.tree
    TOPIC = "topic"           # 频道域: topic.seed123.tree
    MAIL = "mail"             # 邮箱域: @8848993321.leaf
    SERVICE = "service"        # 服务域: blog.8848993321.tree
    COMMUNITY = "community"    # 社区域: forum.8855.wood
    SYSTEM = "system"          # 系统域: registry.living.root
    UNKNOWN = "unknown"


class ResolutionStatus(Enum):
    """解析状态"""
    SUCCESS = "success"        # 解析成功
    NOT_FOUND = "not_found"    # 未找到
    OFFLINE = "offline"        # 节点离线
    TIMEOUT = "timeout"        # 解析超时
    INVALID = "invalid"        # 无效格式


class ContentSource(Enum):
    """内容来源"""
    LOCAL_SQLITE = "local_sqlite"    # 本地 SQLite (论坛/帖子)
    CLOUD_STORAGE = "cloud_storage"  # 云盘 (文件/Markdown)
    DYNAMIC = "dynamic"              # 动态生成 (AI写作)
    RELAY = "relay"                # 中继转发


# ==================== 数据模型 ====================

@dataclass
class PseudoDomain:
    """伪域名 (生命之树版本)"""
    domain: str                    # 完整域名
    domain_type: DomainType        # 域名类型
    tree_suffix: TreeSuffix        # 顶级域名后缀
    node_id: str                   # 节点 ID
    subdomain: str                 # 子域名/服务名
    owner_name: str               # 所有者名称
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    ttl: int = 3600               # 缓存时间 (秒)
    is_public: bool = True        # 是否公开
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def emoji(self) -> str:
        """获取域名对应的 Emoji"""
        # 服务类型 Emoji
        service_emoji = {
            "blog": "📝", "shop": "🛒", "store": "🏪",
            "forum": "🏛️", "talk": "💬", "chat": "💭",
            "mail": "✉️", "email": "📧", "note": "📌",
            "file": "📁", "cloud": "☁️", "wiki": "📚",
            "photo": "📷", "music": "🎵", "video": "🎬",
            "code": "💻", "ai": "🤖", "game": "🎮"
        }
        suffix_emoji = self.tree_suffix.emoji if self.tree_suffix else "🌐"

        # 子域名匹配
        if self.subdomain in service_emoji:
            return service_emoji[self.subdomain]
        # 系统域
        if self.domain_type == DomainType.SYSTEM:
            return "⚙️"
        # 话题域
        if self.domain_type == DomainType.TOPIC:
            return "🌰"
        # 默认
        return suffix_emoji

    @property
    def display_name(self) -> str:
        """人类可读的域名展示名"""
        return f"{self.emoji} {self.subdomain}.{self.node_id}{self.tree_suffix.value}"

    @property
    def is_online(self) -> bool:
        """是否在线 (元数据中获取)"""
        return self.metadata.get("is_online", False)

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "domain_type": self.domain_type.value,
            "tree_suffix": self.tree_suffix.value if self.tree_suffix else None,
            "node_id": self.node_id,
            "subdomain": self.subdomain,
            "owner_name": self.owner_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "ttl": self.ttl,
            "is_public": self.is_public,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PseudoDomain':
        data = dict(data)
        data["domain_type"] = DomainType(data.get("domain_type", "unknown"))
        tree_suffix_str = data.get("tree_suffix")
        if tree_suffix_str:
            data["tree_suffix"] = TreeSuffix.from_string(tree_suffix_str) or TreeSuffix.TREE
        else:
            data["tree_suffix"] = TreeSuffix.TREE
        return cls(**data)


@dataclass
class DomainResolution:
    """域名解析结果"""
    original_domain: str           # 原始域名
    status: ResolutionStatus       # 解析状态
    tree_suffix: Optional[TreeSuffix] = None  # 顶级域名后缀
    domain_type: Optional[DomainType] = None  # 域名类型
    node_id: Optional[str] = None  # 解析到的节点 ID
    node_address: Optional[str] = None  # 节点地址 (IP/Relay)
    content_source: Optional[ContentSource] = None  # 内容来源
    content_path: Optional[str] = None  # 内容路径
    redirect_url: Optional[str] = None  # 重定向 URL (用于外部)
    cache_time: float = 0         # 缓存时间
    resolution_time: float = 0     # 解析耗时 (毫秒)
    error_message: Optional[str] = None

    @property
    def emoji(self) -> str:
        """解析结果 Emoji"""
        if self.status == ResolutionStatus.SUCCESS:
            if self.tree_suffix:
                return self.tree_suffix.emoji
            return "✅"
        elif self.status == ResolutionStatus.OFFLINE:
            return "🍂"  # 落叶 = 离线
        elif self.status == ResolutionStatus.NOT_FOUND:
            return "🔍"
        elif self.status == ResolutionStatus.TIMEOUT:
            return "⏱️"
        return "❌"

    def to_dict(self) -> dict:
        return {
            "original_domain": self.original_domain,
            "status": self.status.value,
            "tree_suffix": self.tree_suffix.value if self.tree_suffix else None,
            "domain_type": self.domain_type.value if self.domain_type else None,
            "node_id": self.node_id,
            "node_address": self.node_address,
            "content_source": self.content_source.value if self.content_source else None,
            "content_path": self.content_path,
            "redirect_url": self.redirect_url,
            "cache_time": self.cache_time,
            "resolution_time": self.resolution_time,
            "error_message": self.error_message
        }


@dataclass
class DomainRegistration:
    """域名注册"""
    domain: str
    domain_type: DomainType
    tree_suffix: TreeSuffix = TreeSuffix.TREE
    node_id: str = ""
    owner_name: str = ""
    content_type: str = ""              # "blog" / "forum" / "file" / "mail"
    content_path: str = ""              # 内容路径或规则
    public_key: Optional[str] = None  # 用于验证的公钥
    signature: Optional[str] = None   # 注册签名
    registered_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None  # 过期时间

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "domain_type": self.domain_type.value,
            "tree_suffix": self.tree_suffix.value if self.tree_suffix else None,
            "node_id": self.node_id,
            "owner_name": self.owner_name,
            "content_type": self.content_type,
            "content_path": self.content_path,
            "public_key": self.public_key,
            "signature": self.signature,
            "registered_at": self.registered_at,
            "expires_at": self.expires_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DomainRegistration':
        data = dict(data)
        data["domain_type"] = DomainType(data.get("domain_type", "unknown"))
        tree_suffix_str = data.get("tree_suffix")
        if tree_suffix_str:
            data["tree_suffix"] = TreeSuffix.from_string(tree_suffix_str) or TreeSuffix.TREE
        else:
            data["tree_suffix"] = TreeSuffix.TREE
        return cls(**data)


@dataclass
class NodeEndpoint:
    """节点端点"""
    node_id: str
    relay_address: Optional[str] = None  # 中继服务器地址
    direct_address: Optional[str] = None   # 直连地址
    last_seen: float = field(default_factory=time.time)
    is_online: bool = False
    latency: int = 0  # 延迟 (毫秒)
    port: int = 0     # 端口

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "relay_address": self.relay_address,
            "direct_address": self.direct_address,
            "last_seen": self.last_seen,
            "is_online": self.is_online,
            "latency": self.latency,
            "port": self.port
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NodeEndpoint':
        return cls(**data)


@dataclass
class WebContent:
    """网页内容"""
    url: str                       # 原始 URL
    title: str                     # 标题
    html_content: str              # HTML 内容
    css_styles: Optional[str] = None  # 自定义 CSS
    js_scripts: Optional[str] = None  # 自定义 JS
    template: Optional[str] = None    # 模板名称
    data: Dict[str, Any] = field(default_factory=dict)  # 模板数据
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_html(self) -> str:
        """渲染为 HTML"""
        if self.template:
            return self._render_template()
        return self.html_content

    def _render_template(self) -> str:
        """简单模板渲染"""
        html = self.html_content
        for key, value in self.data.items():
            html = html.replace("{{" + key + "}}", str(value))
        return html


# ==================== 解析函数 ====================

# 生命之树域名后缀 (.tree 家族)
TREE_SUFFIXES = [".tree", ".leaf", ".root", ".wood"]

# 兼容旧版后缀 (用于迁移)
P2P_SUFFIXES = [".p2p", ".p2pnet", ".localnet", ".p2p.io"]
ALL_SUFFIXES = TREE_SUFFIXES + P2P_SUFFIXES

# 解析正则 (生命之树版本)
TREE_DOMAIN_RE = re.compile(r'^([^.]+)\.([^.]+)\.(tree|leaf|root|wood)$')
TOPIC_TREE_RE = re.compile(r'^(topic|seed)\.([a-f0-9]+)\.(tree|leaf|root|wood)$')
MAIL_TREE_RE = re.compile(r'^@([^.]+)\.(leaf|tree)$')
SYSTEM_TREE_RE = re.compile(r'^([^.]+)\.living\.(root|tree)$')
COMMUNITY_TREE_RE = re.compile(r'^([^.]+)\.([^.]+)\.(wood)$')

# 旧版正则 (兼容)
PERSONAL_DOMAIN_RE = re.compile(r'^([^.]+)\.([^.]+)\.(p2p|p2pnet|localnet|p2p\.io)$')
TOPIC_DOMAIN_RE = re.compile(r'^topic\.([a-f0-9]+)\.(p2p|p2pnet|localnet|p2p\.io)$')
MAIL_DOMAIN_RE = re.compile(r'^@([^.]+)\.(mail)\.(p2p|p2pnet|localnet|p2p\.io)$')


def parse_pseudo_domain(domain: str) -> Tuple[Optional[DomainType], Optional[str], Optional[str], Optional[TreeSuffix]]:
    """
    解析伪域名 (生命之树版本)

    Returns:
        (domain_type, node_id, subdomain, tree_suffix) 或 (None, None, None, None)
    """
    domain = domain.lower().strip()

    # 检查是否为生命之树域名
    has_tree_suffix = any(domain.endswith(suffix) for suffix in TREE_SUFFIXES)
    has_p2p_suffix = any(domain.endswith(suffix) for suffix in P2P_SUFFIXES)

    # 系统域: service.living.root / service.living.tree
    system_match = SYSTEM_TREE_RE.match(domain)
    if system_match:
        service = system_match.group(1)
        suffix_str = system_match.group(2)  # group 2 is (root|tree)
        tree_suffix = TreeSuffix.from_string(suffix_str)
        return DomainType.SYSTEM, "living", service, tree_suffix

    # 邮箱域: @node.leaf 或 @node.tree
    mail_match = MAIL_TREE_RE.match(domain)
    if mail_match:
        node_id = mail_match.group(1)
        suffix_str = mail_match.group(2)
        tree_suffix = TreeSuffix.from_string(suffix_str)
        return DomainType.MAIL, node_id, f"@{node_id}", tree_suffix

    # 话题域: topic.hash.tree / seed.hash.leaf
    topic_match = TOPIC_TREE_RE.match(domain)
    if topic_match:
        prefix = topic_match.group(1)
        topic_hash = topic_match.group(2)
        suffix_str = topic_match.group(3)
        tree_suffix = TreeSuffix.from_string(suffix_str)
        return DomainType.TOPIC, topic_hash, prefix, tree_suffix

    # 个人域/服务域/社区域: name.node.suffix
    tree_match = TREE_DOMAIN_RE.match(domain)
    if tree_match:
        subdomain = tree_match.group(1)
        node_id = tree_match.group(2)
        suffix_str = tree_match.group(3)
        tree_suffix = TreeSuffix.from_string(suffix_str)

        # 社区 (.wood): forum.node.wood, chat.node.wood
        if tree_suffix == TreeSuffix.WOOD:
            return DomainType.COMMUNITY, node_id, subdomain, tree_suffix

        # 服务关键词
        service_keywords = {
            "blog": DomainType.SERVICE, "shop": DomainType.SERVICE,
            "store": DomainType.SERVICE, "file": DomainType.SERVICE,
            "wiki": DomainType.SERVICE, "chat": DomainType.SERVICE,
            "talk": DomainType.SERVICE, "forum": DomainType.SERVICE,
            "mail": DomainType.SERVICE, "note": DomainType.SERVICE,
            "photo": DomainType.SERVICE, "music": DomainType.SERVICE,
            "video": DomainType.SERVICE, "code": DomainType.SERVICE,
            "ai": DomainType.SERVICE, "game": DomainType.SERVICE,
            "cloud": DomainType.SERVICE, "note": DomainType.SERVICE
        }

        if subdomain in service_keywords:
            return service_keywords[subdomain], node_id, subdomain, tree_suffix

        return DomainType.PERSONAL, node_id, subdomain, tree_suffix

    # 兼容旧版 .p2p 域名
    if has_p2p_suffix:
        # 邮箱域: @node.mail.p2p
        mail_match = MAIL_DOMAIN_RE.match(domain)
        if mail_match:
            return DomainType.MAIL, mail_match.group(1), "@" + mail_match.group(1), None

        # 频道域: topic.hash.p2p
        topic_match = TOPIC_DOMAIN_RE.match(domain)
        if topic_match:
            return DomainType.TOPIC, topic_match.group(1), "topic", None

        # 个人域: name.node.p2p
        personal_match = PERSONAL_DOMAIN_RE.match(domain)
        if personal_match:
            subdomain = personal_match.group(1)
            node_id = personal_match.group(2)
            service_keywords = ["blog", "forum", "file", "wiki", "chat", "mail", "cloud"]
            if subdomain in service_keywords:
                return DomainType.SERVICE, node_id, subdomain, None
            return DomainType.PERSONAL, node_id, subdomain, None

    return None, None, None, None


def parse_pseudo_domain_legacy(domain: str) -> Tuple[Optional[DomainType], Optional[str], Optional[str]]:
    """
    解析伪域名 (旧版兼容)

    Returns:
        (domain_type, node_id, subdomain) 或 (None, None, None)
    """
    domain_type, node_id, subdomain, _ = parse_pseudo_domain(domain)
    return domain_type, node_id, subdomain


def build_personal_domain(name: str, node_id: str, suffix: TreeSuffix = TreeSuffix.TREE) -> str:
    """构建个人域"""
    return f"{name}.{node_id}{suffix.value}"


def build_topic_domain(topic_hash: str, suffix: TreeSuffix = TreeSuffix.TREE) -> str:
    """构建频道域"""
    return f"topic.{topic_hash[:12]}{suffix.value}"


def build_seed_domain(seed_name: str, suffix: TreeSuffix = TreeSuffix.TREE) -> str:
    """构建种子域 (话题别名，更友好)"""
    seed_hash = hashlib.sha256(seed_name.encode()).hexdigest()[:12]
    return f"seed.{seed_hash}.{suffix.value}"


def build_mail_domain(node_id: str, suffix: TreeSuffix = TreeSuffix.LEAF) -> str:
    """构建邮箱域"""
    suffix_str = suffix.value.lstrip('.') if hasattr(suffix, 'value') else str(suffix).lstrip('.')
    return f"@{node_id}.{suffix_str}"


def build_service_domain(service: str, node_id: str, suffix: TreeSuffix = TreeSuffix.TREE) -> str:
    """构建服务域"""
    return f"{service}.{node_id}{suffix.value}"


def build_community_domain(community: str, node_id: str) -> str:
    """构建社区域 (.wood)"""
    return f"{community}.{node_id}.wood"


def build_system_domain(service: str) -> str:
    """构建系统域"""
    return f"{service}.living.root"


def compute_topic_hash(topic_name: str) -> str:
    """计算话题哈希"""
    return hashlib.sha256(topic_name.encode()).hexdigest()


def is_pseudo_domain(domain: str) -> bool:
    """检查是否为伪域名"""
    domain = domain.lower().strip()
    return any(domain.endswith(suffix) for suffix in ALL_SUFFIXES)


def is_tree_domain(domain: str) -> bool:
    """检查是否为生命之树域名"""
    domain = domain.lower().strip()
    return any(domain.endswith(suffix) for suffix in TREE_SUFFIXES)


def get_tree_suffix(domain: str) -> Optional[TreeSuffix]:
    """获取域名对应的树后缀"""
    domain = domain.lower().strip()
    for suffix in TREE_SUFFIXES:
        if domain.endswith(suffix):
            return TreeSuffix.from_string(suffix)
    return None
