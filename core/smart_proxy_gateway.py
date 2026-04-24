"""
SmartProxyGateway - 智能代理网关
=================================

整体架构：
1. ProxySourceManager - 代理源管理器（支持API/网页/本地源，自动翻页）
2. ProxyPool - 代理池（统一代理存储和分发）
3. WhiteListRouter - 白名单路由器（开发/Git/AI/ML/IDE）
4. GitProxyConfig - Git代理配置（全局+白名单）
5. ProxyMonitor - 代理健康监测

使用方式：
    from core.smart_proxy_gateway import get_gateway, SmartProxyGateway

    gateway = get_gateway()

    # 获取代理
    proxy = gateway.get_proxy()

    # 检查URL是否需要代理
    should_proxy = gateway.should_proxy("https://github.com/user/repo")

    # 检查URL是否在白名单
    is_allowed, category = gateway.check_whitelist("https://huggingface.co/...")
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse
import requests

logger = logging.getLogger(__name__)


class ProxySourceType(Enum):
    """代理源类型"""
    API = "api"           # API接口
    WEB_SCRAPE = "web"    # 网页爬取
    LOCAL = "local"       # 本地文件/数据库


class ProxyProtocol(Enum):
    """代理协议"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


@dataclass
class ProxyInfo:
    """代理信息"""
    ip: str
    port: int
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    country: Optional[str] = None
    latency: Optional[float] = None
    source: str = ""
    last_checked: float = field(default_factory=lambda: asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0)

    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"

    def __str__(self) -> str:
        return f"{self.protocol.value}://{self.address}"


@dataclass
class ProxySource:
    """代理源配置"""
    id: str
    name: str
    source_type: ProxySourceType
    url: str
    enabled: bool = True
    priority: int = 100  # 越小优先级越高
    max_count: int = 20  # 单次最大获取数量
    supports_pagination: bool = False  # 是否支持翻页
    pagination_pattern: Optional[str] = None  # 翻页URL模式
    headers: Optional[Dict[str, str]] = None
    parse_method: str = "json"  # json, html, text

    def build_url(self, page: int = 1, count: int = 20) -> str:
        """构建带分页的URL"""
        if not self.supports_pagination or page <= 1:
            return self.url

        if self.pagination_pattern:
            return self.pagination_pattern.format(
                base=self.url.rstrip('/'),
                page=page,
                count=count
            )
        return self.url


class WhiteListCategory(Enum):
    """白名单分类"""
    SEARCH_ENGINE = "search_engine"      # 搜索引擎
    DEV_Q_A = "dev_qa"                   # 开发问答
    DEV_DOCS = "dev_docs"                # 开发文档
    AI_ML = "ai_ml"                      # AI/ML平台
    KNOWLEDGE = "knowledge"              # 知识库
    GIT_HOSTING = "git_hosting"          # Git托管（GitHub/GitLab）
    MODEL_MARKET = "model_market"        # 模型市场
    SKILL_MARKET = "skill_market"        # Skills市场
    IDE_MODULE = "ide_module"            # IDE模块（智能IDE需要的服务）
    VIDEO_BLOCKED = "video_blocked"     # 视频禁止


@dataclass
class WhiteListRule:
    """白名单规则"""
    domain: str
    category: WhiteListCategory
    description: str = ""
    use_proxy: bool = True  # 是否使用代理


class WhiteListManager:
    """
    白名单管理器
    =============

    支持的白名单分类：

    1. 开发/问答
       - GitHub, GitLab, BitBucket
       - StackOverflow, Dev.to, Reddit

    2. AI/ML
       - HuggingFace, ArXiv, PapersWithCode
       - OpenRouter, Groq, Anthropic

    3. Git/SSH
       - GitHub, GitLab, BitBucket
       - SSH代理配置

    4. 模型市场
       - HuggingFace Models
       - OpenRouter, Groq

    5. Skills市场
       - WorkBuddy Skills
       - MCP Servers

    6. IDE插件市场
       - VSCode Marketplace
       - JetBrains Marketplace
       - GitHub API
    """

    # 完整白名单配置
    RULES: List[WhiteListRule] = [
        # ===== 开发/问答 =====
        WhiteListRule("github.com", WhiteListCategory.DEV_Q_A, "GitHub"),
        WhiteListRule("githubusercontent.com", WhiteListCategory.DEV_Q_A, "GitHub Raw"),
        WhiteListRule("gitlab.com", WhiteListCategory.GIT_HOSTING, "GitLab"),
        WhiteListRule("bitbucket.org", WhiteListCategory.GIT_HOSTING, "BitBucket"),
        WhiteListRule("stackoverflow.com", WhiteListCategory.DEV_Q_A, "StackOverflow"),
        WhiteListRule("stackexchange.com", WhiteListCategory.DEV_Q_A, "StackExchange"),
        WhiteListRule("dev.to", WhiteListCategory.DEV_Q_A, "Dev.to"),
        WhiteListRule("reddit.com", WhiteListCategory.DEV_Q_A, "Reddit"),
        WhiteListRule("npmjs.com", WhiteListCategory.DEV_DOCS, "npm"),
        WhiteListRule("pypi.org", WhiteListCategory.DEV_DOCS, "PyPI"),
        WhiteListRule("crates.io", WhiteListCategory.DEV_DOCS, "crates.io"),
        WhiteListRule("packagist.org", WhiteListCategory.DEV_DOCS, "Packagist"),

        # ===== 开发文档 =====
        WhiteListRule("python.org", WhiteListCategory.DEV_DOCS, "Python"),
        WhiteListRule("docs.python.org", WhiteListCategory.DEV_DOCS, "Python Docs"),
        WhiteListRule("mozilla.org", WhiteListCategory.DEV_DOCS, "MDN"),
        WhiteListRule("developer.mozilla.org", WhiteListCategory.DEV_DOCS, "MDN"),
        WhiteListRule("nodejs.org", WhiteListCategory.DEV_DOCS, "Node.js"),
        WhiteListRule("rust-lang.org", WhiteListCategory.DEV_DOCS, "Rust"),
        WhiteListRule("go.dev", WhiteListCategory.DEV_DOCS, "Go"),
        WhiteListRule("java.com", WhiteListCategory.DEV_DOCS, "Java"),
        WhiteListRule("spring.io", WhiteListCategory.DEV_DOCS, "Spring"),
        WhiteListRule("devdocs.io", WhiteListCategory.DEV_DOCS, "DevDocs"),
        WhiteListRule("readthedocs.io", WhiteListCategory.DEV_DOCS, "ReadTheDocs"),
        WhiteListRule("swagger.io", WhiteListCategory.DEV_DOCS, "Swagger"),
        WhiteListRule("openapi.org", WhiteListCategory.DEV_DOCS, "OpenAPI"),

        # ===== AI/ML =====
        WhiteListRule("huggingface.co", WhiteListCategory.AI_ML, "HuggingFace"),
        WhiteListRule("arxiv.org", WhiteListCategory.AI_ML, "ArXiv"),
        WhiteListRule("paperswithcode.com", WhiteListCategory.AI_ML, "PapersWithCode"),
        WhiteListRule("openrouter.ai", WhiteListCategory.MODEL_MARKET, "OpenRouter"),
        WhiteListRule("groq.com", WhiteListCategory.MODEL_MARKET, "Groq"),
        WhiteListRule("anthropic.com", WhiteListCategory.AI_ML, "Anthropic"),
        WhiteListRule("openai.com", WhiteListCategory.AI_ML, "OpenAI"),
        WhiteListRule("mistral.ai", WhiteListCategory.AI_ML, "Mistral"),
        WhiteListRule("cohere.com", WhiteListCategory.AI_ML, "Cohere"),
        WhiteListRule("ai.google.com", WhiteListCategory.AI_ML, "Google AI"),
        WhiteListRule("llamaparse.com", WhiteListCategory.AI_ML, "LLaMA Parse"),

        # ===== 模型市场 =====
        WhiteListRule("models.huggingface.co", WhiteListCategory.MODEL_MARKET, "HF Models"),
        WhiteListRule("openai.com", WhiteListCategory.MODEL_MARKET, "OpenAI API"),
        WhiteListRule("api.openai.com", WhiteListCategory.MODEL_MARKET, "OpenAI API"),
        WhiteListRule("generativelanguage.googleapis.com", WhiteListCategory.MODEL_MARKET, "Google AI API"),
        WhiteListRule("api.cohere.ai", WhiteListCategory.MODEL_MARKET, "Cohere API"),
        WhiteListRule("api.mistral.ai", WhiteListCategory.MODEL_MARKET, "Mistral API"),

        # ===== Skills市场 & IDE插件 =====
        # IDE模块（智能IDE需要的服务）
        WhiteListRule("api.github.com", WhiteListCategory.IDE_MODULE, "GitHub API"),
        WhiteListRule("github.com", WhiteListCategory.GIT_HOSTING, "GitHub"),

        # Skills市场
        WhiteListRule("workbuddy.com", WhiteListCategory.SKILL_MARKET, "WorkBuddy"),
        WhiteListRule("codebuddy.cn", WhiteListCategory.SKILL_MARKET, "CodeBuddy"),

        # ===== 知识库 =====
        WhiteListRule("wikipedia.org", WhiteListCategory.KNOWLEDGE, "Wikipedia"),
        WhiteListRule("wikimedia.org", WhiteListCategory.KNOWLEDGE, "Wikimedia"),
        WhiteListRule("archive.org", WhiteListCategory.KNOWLEDGE, "Archive.org"),

        # ===== 搜索引擎 =====
        WhiteListRule("google.com", WhiteListCategory.SEARCH_ENGINE, "Google"),
        WhiteListRule("bing.com", WhiteListCategory.SEARCH_ENGINE, "Bing"),
        WhiteListRule("duckduckgo.com", WhiteListCategory.SEARCH_ENGINE, "DuckDuckGo"),

        # ===== 视频禁止 =====
        WhiteListRule("youtube.com", WhiteListCategory.VIDEO_BLOCKED, "YouTube"),
        WhiteListRule("youtu.be", WhiteListCategory.VIDEO_BLOCKED, "YouTube Shorts"),
        WhiteListRule("bilibili.com", WhiteListCategory.VIDEO_BLOCKED, "Bilibili"),
        WhiteListRule("netflix.com", WhiteListCategory.VIDEO_BLOCKED, "Netflix"),
        WhiteListRule("twitch.tv", WhiteListCategory.VIDEO_BLOCKED, "Twitch"),
    ]

    def __init__(self):
        # 构建域名到规则的快速映射
        self._domain_map: Dict[str, WhiteListRule] = {}
        for rule in self.RULES:
            self._domain_map[rule.domain] = rule

    def check(self, url: str) -> Tuple[bool, Optional[WhiteListRule], Optional[str]]:
        """
        检查URL是否在白名单中

        Returns:
            (是否允许, 匹配的规则, 规范化域名)
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # 移除端口
        if ":" in domain:
            domain = domain.split(":")[0]

        # 精确匹配
        if domain in self._domain_map:
            rule = self._domain_map[domain]
            return rule.category != WhiteListCategory.VIDEO_BLOCKED, rule, domain

        # 前缀匹配（支持 *.github.com）
        parts = domain.split(".")
        for i in range(len(parts)):
            sub_domain = ".".join(parts[i:])
            if sub_domain in self._domain_map:
                rule = self._domain_map[sub_domain]
                return rule.category != WhiteListCategory.VIDEO_BLOCKED, rule, domain

        return True, None, domain  # 不在白名单中，默认允许

    def should_proxy(self, url: str) -> Optional[bool]:
        """
        判断URL是否应该使用代理

        Returns:
            True: 使用代理
            False: 直连
            None: 拒绝访问
        """
        allowed, rule, domain = self.check(url)

        if not allowed:
            logger.warning(f"URL在禁止名单中: {url}")
            return None

        # 不在白名单中，检查配置决定
        if rule is None:
            return None  # 不在白名单，返回None让上层决定

        return rule.use_proxy

    def get_category(self, url: str) -> Optional[WhiteListCategory]:
        """获取URL所属的分类"""
        _, rule, _ = self.check(url)
        return rule.category if rule else None

    def get_all_rules(self) -> List[WhiteListRule]:
        """获取所有规则"""
        return self.RULES.copy()

    def get_rules_by_category(self, category: WhiteListCategory) -> List[WhiteListRule]:
        """获取指定分类的规则"""
        return [r for r in self.RULES if r.category == category]


class SmartProxyGateway:
    """
    智能代理网关主类

    使用方式：
        gateway = SmartProxyGateway()

        # 获取代理
        proxy = gateway.get_proxy(protocol=ProxyProtocol.HTTPS)

        # 检查是否需要代理
        should = gateway.should_proxy("https://github.com/user/repo")

        # 获取Git代理配置
        git_config = gateway.get_git_proxy_config()
    """

    def __init__(self):
        self._initialized = False
        self._sources: List[ProxySource] = []
        self._pool: List[ProxyInfo] = []
        self._whitelist = WhiteListManager()
        self._config = self._load_default_config()

    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置"""
        return {
            "enable_proxy": False,
            "proxy_mode": "smart",  # always, never, smart
            "default_protocol": "http",
            "max_pool_size": 100,
            "health_check_interval": 300,  # 5分钟
            "auto_reload_interval": 1800,  # 30分钟
        }

    def _lazy_init(self):
        """延迟初始化"""
        if self._initialized:
            return

        # 加载代理源
        self._load_proxy_sources()

        self._initialized = True
        logger.info("SmartProxyGateway 初始化完成")

    def _load_proxy_sources(self):
        """加载代理源配置"""
        # ===== API源 =====
        self._sources.append(ProxySource(
            id="scdn",
            name="SCDN代理池",
            source_type=ProxySourceType.API,
            url="https://proxy.scdn.io/api/get_proxy.php",
            enabled=True,
            priority=10,
            max_count=20,
            supports_pagination=False,
            parse_method="json"
        ))

        self._sources.append(ProxySource(
            id="proxyscrape",
            name="ProxyScrape",
            source_type=ProxySourceType.API,
            url="https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all&simplified=true",
            enabled=True,
            priority=20,
            max_count=100,
            supports_pagination=False,
            parse_method="text"
        ))

        # ===== 网页爬取源（支持翻页）=====
        self._sources.append(ProxySource(
            id="89ip",
            name="89免费代理",
            source_type=ProxySourceType.WEB_SCRAPE,
            url="https://www.89ip.cn/index_{page}.html",
            enabled=True,
            priority=50,
            max_count=20,
            supports_pagination=True,
            pagination_pattern="https://www.89ip.cn/index_{page}.html",
            parse_method="html"
        ))

        self._sources.append(ProxySource(
            id="kuaidaili",
            name="快代理",
            source_type=ProxySourceType.WEB_SCRAPE,
            url="https://www.kuaidaili.com/free/inha/{page}/",
            enabled=True,
            priority=60,
            max_count=20,
            supports_pagination=True,
            pagination_pattern="https://www.kuaidaili.com/free/inha/{page}/",
            parse_method="html"
        ))

        self._sources.append(ProxySource(
            id="geonode",
            name="Geonode",
            source_type=ProxySourceType.API,
            url="https://proxyscrape.pro/api/v2/free-proxy-list?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
            enabled=True,
            priority=30,
            max_count=100,
            supports_pagination=False,
            parse_method="text"
        ))

        # 按优先级排序
        self._sources.sort(key=lambda s: s.priority)

    def get_sources(self) -> List[ProxySource]:
        """获取所有代理源"""
        return self._sources.copy()

    def get_enabled_sources(self) -> List[ProxySource]:
        """获取启用的代理源"""
        return [s for s in self._sources if s.enabled]

    def add_source(self, source: ProxySource):
        """添加代理源"""
        self._sources.append(source)
        self._sources.sort(key=lambda s: s.priority)
        logger.info(f"添加代理源: {source.name}")

    def remove_source(self, source_id: str):
        """移除代理源"""
        self._sources = [s for s in self._sources if s.id != source_id]
        logger.info(f"移除代理源: {source_id}")

    def enable_source(self, source_id: str, enabled: bool = True):
        """启用/禁用代理源"""
        for source in self._sources:
            if source.id == source_id:
                source.enabled = enabled
                logger.info(f"{'启用' if enabled else '禁用'}代理源: {source.name}")

    def should_proxy(self, url: str) -> Optional[bool]:
        """判断URL是否应该使用代理"""
        return self._whitelist.should_proxy(url)

    def check_whitelist(self, url: str) -> Tuple[bool, Optional[WhiteListCategory], Optional[str]]:
        """
        检查URL白名单

        Returns:
            (是否允许, 分类, 域名)
        """
        allowed, rule, domain = self._whitelist.check(url)
        category = rule.category if rule else None
        return allowed, category, domain

    def get_git_proxy_config(self) -> Dict[str, str]:
        """
        获取Git代理配置

        Returns:
            Git配置字典
        """
        if not self._config.get("enable_proxy"):
            return {}

        proxy = self.get_proxy()
        if not proxy:
            return {}

        return {
            "http.proxy": str(proxy),
            "https.proxy": str(proxy),
        }

    def get_gitconfig_snippet(self) -> str:
        """
        获取Git配置片段（用于白名单Git配置）

        这个配置允许对特定域名使用代理
        """
        proxy = self.get_proxy()
        if not proxy:
            return ""

        proxy_str = str(proxy)

        # 构建Git配置
        domains = [
            "github.com",
            "gitlab.com",
            "bitbucket.org",
            "huggingface.co",
        ]

        lines = [
            "[http]",
            f"    proxy = {proxy_str}",
            "",
        ]

        # 添加特定域名的代理配置
        for domain in domains:
            lines.extend([
                f"[http \"https://{domain}/\"]",
                f"    proxy = {proxy_str}",
                "",
            ])

        return "\n".join(lines)

    def get_proxy(self, protocol: ProxyProtocol = None) -> Optional[ProxyInfo]:
        """获取一个可用的代理"""
        self._lazy_init()

        if not self._config.get("enable_proxy"):
            return None

        # 从池中获取
        for proxy in self._pool:
            if protocol is None or proxy.protocol == protocol:
                return proxy

        # 池为空，尝试获取新的
        self.reload_proxies()
        for proxy in self._pool:
            if protocol is None or proxy.protocol == protocol:
                return proxy

        return None

    def reload_proxies(self):
        """重新加载代理"""
        self._lazy_init()

        new_proxies: List[ProxyInfo] = []

        for source in self.get_enabled_sources():
            try:
                proxies = self._fetch_from_source(source)
                new_proxies.extend(proxies)
                logger.info(f"从 {source.name} 获取 {len(proxies)} 个代理")
            except Exception as e:
                logger.error(f"从 {source.name} 获取代理失败: {e}")

        self._pool = new_proxies

    def _fetch_from_source(self, source: ProxySource) -> List[ProxyInfo]:
        """从指定源获取代理"""
        proxies: List[ProxyInfo] = []

        if source.source_type == ProxySourceType.API:
            proxies = self._fetch_from_api(source)
        elif source.source_type == ProxySourceType.WEB_SCRAPE:
            proxies = self._fetch_from_web(source)

        return proxies

    def _fetch_from_api(self, source: ProxySource) -> List[ProxyInfo]:
        """从API源获取代理"""
        proxies: List[ProxyInfo] = []

        # SCDN特殊处理
        if source.id == "scdn":
            params = {
                "protocol": "http",
                "count": source.max_count
            }
            try:
                response = requests.get(source.url, params=params, timeout=10)
                data = response.json()

                if data.get("code") == 200:
                    proxy_list = data.get("data", {}).get("proxies", [])
                    for addr in proxy_list:
                        if ":" in addr:
                            ip, port = addr.split(":")
                            proxies.append(ProxyInfo(
                                ip=ip,
                                port=int(port),
                                protocol=ProxyProtocol.HTTP,
                                source=source.id
                            ))
            except Exception as e:
                logger.error(f"SCDN API获取失败: {e}")

            return proxies

        # 普通文本格式
        try:
            response = requests.get(source.url, timeout=15)
            text = response.text

            for line in text.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # 解析 IP:PORT 或 IP:PORT:PROTOCOL
                parts = line.split(":")
                if len(parts) >= 2:
                    ip = parts[0]
                    port = int(parts[1])
                    protocol = ProxyProtocol.HTTP

                    if len(parts) >= 3:
                        protocol_str = parts[2].lower()
                        if protocol_str == "socks5":
                            protocol = ProxyProtocol.SOCKS5
                        elif protocol_str == "socks4":
                            protocol = ProxyProtocol.SOCKS4
                        elif protocol_str == "https":
                            protocol = ProxyProtocol.HTTPS

                    proxies.append(ProxyInfo(
                        ip=ip,
                        port=port,
                        protocol=protocol,
                        source=source.id
                    ))

        except Exception as e:
            logger.error(f"API获取失败: {e}")

        return proxies

    def _fetch_from_web(self, source: ProxySource) -> List[ProxyInfo]:
        """从网页源获取代理（支持翻页）"""
        from bs4 import BeautifulSoup

        proxies: List[ProxyInfo] = []
        max_pages = 5  # 最多翻5页

        for page in range(1, max_pages + 1):
            try:
                url = source.build_url(page=page)
                response = requests.get(url, timeout=15)
                soup = BeautifulSoup(response.text, "html.parser")

                # 查找表格
                table = soup.find("table")
                if not table:
                    break

                rows = table.find_all("tr")[1:]  # 跳过表头
                if not rows:
                    break

                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 2:
                        ip = cols[0].get_text(strip=True)
                        port = cols[1].get_text(strip=True)

                        # 尝试解析协议
                        protocol = ProxyProtocol.HTTP
                        if len(cols) > 3:
                            protocol_text = cols[3].get_text(strip=True).lower()
                            if "https" in protocol_text:
                                protocol = ProxyProtocol.HTTPS
                            elif "socks5" in protocol_text:
                                protocol = ProxyProtocol.SOCKS5
                            elif "socks4" in protocol_text:
                                protocol = ProxyProtocol.SOCKS4

                        proxies.append(ProxyInfo(
                            ip=ip,
                            port=int(port),
                            protocol=protocol,
                            source=source.id
                        ))

                # 如果没有翻到更多代理，停止
                if len(rows) < 10:
                    break

            except Exception as e:
                logger.error(f"网页翻页失败 (page={page}): {e}")
                break

        return proxies

    def get_whitelist_stats(self) -> Dict[str, int]:
        """获取白名单统计"""
        stats = {}
        for category in WhiteListCategory:
            rules = self._whitelist.get_rules_by_category(category)
            stats[category.value] = len(rules)
        return stats

    def get_pool_stats(self) -> Dict[str, Any]:
        """获取代理池统计"""
        by_protocol = {}
        for proxy in self._pool:
            proto_name = proxy.protocol.value
            by_protocol[proto_name] = by_protocol.get(proto_name, 0) + 1

        return {
            "total": len(self._pool),
            "by_protocol": by_protocol,
            "enabled_sources": len(self.get_enabled_sources()),
            "total_sources": len(self._sources),
        }


# 单例
_gateway: Optional[SmartProxyGateway] = None


def get_gateway() -> SmartProxyGateway:
    """获取网关单例"""
    global _gateway
    if _gateway is None:
        _gateway = SmartProxyGateway()
    return _gateway
