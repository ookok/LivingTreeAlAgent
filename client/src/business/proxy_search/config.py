# -*- coding: utf-8 -*-
"""
代理搜索配置
"""

from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProxySource:
    """代理源配置"""
    name: str
    url: str
    protocol: str = "http"  # http, socks4, socks5, all
    timeout: int = 10
    enabled: bool = True
    priority: int = 1  # 1=最高优先级
    country: str = "all"  # 国家筛选
    anonymity: str = "all"  # 匿名级别


@dataclass
class ValidatorConfig:
    """验证器配置"""
    # 基础连通性验证
    basic_timeout: int = 5
    basic_test_url: str = "http://httpbin.org/ip"

    # 匿名性验证
    check_anonymity: bool = True

    # 目标站点验证
    target_timeout: int = 10
    target_urls: List[str] = field(default_factory=lambda: [
        "https://www.google.com",
        "https://scholar.google.com",
        "https://arxiv.org",
    ])

    # 批量验证并发数
    max_workers: int = 20


@dataclass
class ProxyPoolConfig:
    """代理池配置"""
    # 刷新策略
    refresh_interval: int = 3600  # 秒（每小时刷新）
    min_pool_size: int = 5  # 最小可用代理数
    max_pool_size: int = 100  # 最大保留代理数

    # 使用策略
    max_retries: int = 3  # 最大重试次数
    retry_delay: float = 1.0  # 重试延迟（秒）

    # 淘汰机制
    max_failures: int = 3  # 连续失败次数阈值
    failure_window: int = 300  # 失败计数窗口（秒）


@dataclass
class WhiteListConfig:
    """白名单配置 - 控制哪些网站允许使用代理访问"""
    # 开发相关
    search_engines: Set[str] = field(default_factory=lambda: {
        # 搜索引擎
        "google.com", "bing.com", "duckduckgo.com", "yahoo.com",
        "baidu.com", "sogou.com", "360.cn", "so.com",
        "startpage.com", "searxng.com", "metager.de",
        # 学术搜索
        "scholar.google.com", "scholar.google.com.hk",
        "academia.edu", "researchgate.net", "semanticscholar.org",
        "connectedpapers.com", "paperpile.com",
    })

    coding_qa: Set[str] = field(default_factory=lambda: {
        # 编程问答
        "stackoverflow.com", "stackexchange.com",
        "github.com", "gitlab.com", "bitbucket.org",
        "dev.to", "hashnode.com", "reddit.com/r/programming",
        "codeproject.com", "codelib.com",
        # 代码片段
        "github.com/gists", "pastebin.com", "hastebin.com",
        "replit.com", "codepen.io", "jsfiddle.net",
        "glitch.com", "codesandbox.io",
    })

    dev_docs: Set[str] = field(default_factory=lambda: {
        # 官方文档
        "docs.python.org", "docs.microsoft.com", "developer.mozilla.org",
        "devdocs.io", "readthedocs.io",
        "java.sun.com", "docs.oracle.com",
        "kotlinlang.org", "swift.org", "rust-lang.org",
        "nodejs.org", "npmjs.com",
        "pypi.org", "npmjs.com/package",
        "crates.io", "mvnrepository.com",
        "docker.com", "kubernetes.io",
        # API文档
        "api.mongodb.com", "docs.mongodb.com",
        "dev.mysql.com", "postgresql.org/docs",
        "redis.io/docs", "redis-py.readthedocs.io",
        "platform.openai.com", "api.anthropic.com",
        "cloud.google.com/ai-platform",
    })

    ai_ml: Set[str] = field(default_factory=lambda: {
        # AI/ML平台
        "huggingface.co", "huggingface.co/models",
        "arxiv.org", "arxiv.org/abs", "arxiv.org/pdf",
        "paperswithcode.com", "openreview.net",
        "deepmind.com", "ai.googleblog.com",
        "openai.com", "anthropic.com",
        "ai.meta.com", "developer.nvidia.com",
        # 模型托管
        "replicate.com", "modal.com", "gradientedge.com",
        "langchain.com", "llamaindex.ai",
    })

    knowledge: Set[str] = field(default_factory=lambda: {
        # 知识库
        "wikipedia.org", "wikimedia.org",
        "wolframalpha.com", "wolfram.com",
        "britannica.com", "encyclopedia.com",
        "quora.com", "answers.google.com",
        "europeana.eu", "archive.org",
        "kaggle.com", "kaggle.org",
    })

    # 视频网站（禁止）
    video_blocked: Set[str] = field(default_factory=lambda: {
        "youtube.com", "youtu.be",
        "bilibili.com", "b23.tv",
        "vimeo.com", "dailymotion.com",
        "twitch.tv", "afreecatv.com",
        "netflix.com", "hulu.com",
        "primevideo.com", "disneyplus.com",
        "hbogo.com", "peacocktv.com",
        "iQiyi.com", "iqiyi.com",
        "tencent video", "video.qq.com",
    })

    # 社交媒体（部分允许）
    social_media: Set[str] = field(default_factory=lambda: {
        # 允许的社交媒体
        "twitter.com", "x.com",
        "linkedin.com", "medium.com",
        "towardsdatascience.com",
        # 禁止的社交媒体
        "facebook.com", "instagram.com",
        "tiktok.com", "snapchat.com",
        "pinterest.com", "tumblr.com",
    })


@dataclass
class ProxySearchConfig:
    """全局配置"""
    # 代理源
    sources: List[ProxySource] = field(default_factory=lambda: [
        # === 聚合API源（推荐） ===
        ProxySource(
            name="proxyscrape",
            url="https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all&simplified=true",
            protocol="http",
            priority=1,
        ),
        ProxySource(
            name="proxy-scdn",
            url="https://proxy.scdn.io/api/v1/proxies",
            protocol="http",
            priority=1,
        ),

        # === 网页抓取源 ===
        ProxySource(
            name="free-proxy-list",
            url="https://free-proxy-list.net/",
            protocol="http",
            priority=2,
        ),
        ProxySource(
            name="proxylistplus",
            url="https://list.proxylistplus.com/Fresh-HTTP-Proxy-List",
            protocol="http",
            priority=2,
        ),
        ProxySource(
            name="geonode",
            url="https://geonode.com/free-proxy-list",
            protocol="http",
            priority=2,
        ),
        ProxySource(
            name="proxy-list-download",
            url="https://www.proxy-list.download/api/v1/geta?type=http",
            protocol="http",
            priority=2,
        ),

        # === 国内源 ===
        ProxySource(
            name="89ip-cn",
            url="http://www.89ip.cn/index.html",
            protocol="http",
            priority=1,
        ),
        ProxySource(
            name="kuaidaili",
            url="https://www.kuaidaili.com/free/",
            protocol="http",
            priority=2,
        ),
        ProxySource(
            name="yun-ip",
            url="http://www.ip3366.net/",
            protocol="http",
            priority=2,
        ),
        ProxySource(
            name="uu-proxy",
            url="https://uu-proxy.com/",
            protocol="http",
            priority=3,
        ),
    ])

    # 验证配置
    validator: ValidatorConfig = field(default_factory=ValidatorConfig)

    # 代理池配置
    pool: ProxyPoolConfig = field(default_factory=ProxyPoolConfig)

    # 白名单配置
    whitelist: WhiteListConfig = field(default_factory=WhiteListConfig)

    # 功能开关
    enable_proxy: bool = False  # 是否启用代理
    proxy_mode: str = "smart"  # smart=智能路由, always=总是代理, never=从不代理

    # User-Agent
    user_agent: str = "Academic-Research/1.0 (LivingTreeAlAgent; mailto:research@example.edu)"

    # 日志
    log_level: str = "INFO"

    # 监测配置
    enable_monitoring: bool = False  # 是否启用定时监测
    monitor_interval: int = 300  # 监测间隔（秒）


# 全局配置实例
_config: Optional[ProxySearchConfig] = None


def get_config() -> ProxySearchConfig:
    """获取全局配置"""
    global _config
    if _config is None:
        _config = ProxySearchConfig()
    return _config


def update_config(**kwargs):
    """更新配置"""
    global _config
    config = get_config()
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, value)


def add_source(name: str, url: str, protocol: str = "http", priority: int = 10, enabled: bool = True):
    """添加代理源"""
    config = get_config()
    # 检查是否已存在
    for src in config.sources:
        if src.url == url:
            logger.warning(f"代理源已存在: {url}")
            return
    source = ProxySource(
        name=name,
        url=url,
        protocol=protocol,
        priority=priority,
        enabled=enabled
    )
    config.sources.append(source)
    config.sources.sort(key=lambda x: x.priority)
    logger.info(f"添加代理源: {name} -> {url}")


def remove_source(name: str = None, url: str = None):
    """删除代理源"""
    config = get_config()
    original_count = len(config.sources)
    if name:
        config.sources = [s for s in config.sources if s.name != name]
    elif url:
        config.sources = [s for s in config.sources if s.url != url]
    removed = original_count - len(config.sources)
    if removed > 0:
        logger.info(f"删除代理源: {name or url}, 移除 {removed} 条")
    return removed


def enable_source(name: str, enabled: bool = True):
    """启用/禁用代理源"""
    config = get_config()
    for src in config.sources:
        if src.name == name:
            src.enabled = enabled
            logger.info(f"代理源 {'启用' if enabled else '禁用'}: {name}")
            return True
    return False


def add_target_url(url: str):
    """添加目标验证站点"""
    config = get_config()
    if url not in config.validator.target_urls:
        config.validator.target_urls.append(url)
        logger.info(f"添加验证站点: {url}")


def should_use_proxy(url: str) -> Optional[bool]:
    """
    判断URL是否应该使用代理

    Returns:
        True: 使用代理
        False: 直连
        None: 拒绝访问（不在白名单）
    """
    config = get_config()

    # 先检查视频黑名单（即使代理未启用也要检查）
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # 移除端口
    if ":" in domain:
        domain = domain.split(":")[0]

    whitelist = config.whitelist

    # 1. 检查视频类（禁止）- 始终生效
    for blocked in whitelist.video_blocked:
        if blocked in domain:
            logger.warning(f"URL在视频黑名单，拒绝: {url}")
            return None

    # 2. 检查功能开关
    if not config.enable_proxy:
        return False

    if config.proxy_mode == "always":
        return True
    elif config.proxy_mode == "never":
        return False

    # Smart模式：检查白名单
    # 3. 检查搜索引擎
    for allowed in whitelist.search_engines:
        if allowed in domain:
            return True

    # 3. 检查编程问答
    for allowed in whitelist.coding_qa:
        if allowed in domain:
            return True

    # 4. 检查开发文档
    for allowed in whitelist.dev_docs:
        if allowed in domain:
            return True

    # 5. 检查AI/ML
    for allowed in whitelist.ai_ml:
        if allowed in domain:
            return True

    # 6. 检查知识库
    for allowed in whitelist.knowledge:
        if allowed in domain:
            return True

    # 7. 检查社交媒体
    allowed_social = {"twitter.com", "x.com", "linkedin.com", "medium.com",
                       "towardsdatascience.com"}
    for allowed in allowed_social:
        if allowed in domain:
            return True

    # 默认直连
    return False


def get_allowed_domains() -> Dict[str, List[str]]:
    """获取所有允许代理的域名分类"""
    config = get_config()
    whitelist = config.whitelist
    return {
        "搜索引擎": sorted(whitelist.search_engines),
        "编程问答": sorted(whitelist.coding_qa),
        "开发文档": sorted(whitelist.dev_docs),
        "AI/机器学习": sorted(whitelist.ai_ml),
        "知识库": sorted(whitelist.knowledge),
        "视频类（禁止）": sorted(whitelist.video_blocked),
    }
