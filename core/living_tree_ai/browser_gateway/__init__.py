"""
浏览器网关 (Browser Gateway)
===========================

内置浏览器的终极形态：双向协议网关

核心定位：
- 对内：所有内部系统（邮件、论坛）的统一渲染器
- 对外：互联网数据的抓取器、转换器和安全网关

功能：
1. 注册自定义协议 (hyperos://)
2. 网页与客户端的双向 RPC
3. 离线镜像 (CID 存储)
4. CSS 重写引擎
5. 节点验证器
"""

from .gateway import (
    BrowserGateway,
    create_browser_gateway,
    ProtocolHandler,
    RPCBridge,
)
from .hyperos_protocol import (
    HyperOSProtocol,
    HyperOSURI,
    parse_hyperos_uri,
)
from .rpc_injector import (
    RPCInjector,
    RPCMethod,
    inject_window_hyperos,
)
from .offline_mirror import (
    OfflineMirror,
    MirrorSnapshot,
    create_offline_mirror,
)
from .css_rewriter import (
    CSSRewriter,
    CSSRule,
    create_css_rewriter,
)
from .crawler_dispatcher import (
    CrawlerDispatcher,
    CrawlTask,
    create_crawler_dispatcher,
)
from .browser_use_adapter import create_browser_use_adapter
from .extensions import (
    get_extension_manager,
    get_plugin_system,
    get_user_script_manager,
    ExtensionAPI
)
from .config import (
    get_config_manager,
    ConfigOption,
    ConfigType,
    ConfigValidator
)

__all__ = [
    # 核心网关
    "BrowserGateway",
    "create_browser_gateway",
    "ProtocolHandler",
    "RPCBridge",
    # 协议
    "HyperOSProtocol",
    "HyperOSURI",
    "parse_hyperos_uri",
    # RPC注入
    "RPCInjector",
    "RPCMethod",
    "inject_window_hyperos",
    # 离线镜像
    "OfflineMirror",
    "MirrorSnapshot",
    "create_offline_mirror",
    # CSS重写
    "CSSRewriter",
    "CSSRule",
    "create_css_rewriter",
    # 爬虫调度
    "CrawlerDispatcher",
    "CrawlTask",
    "create_crawler_dispatcher",
    # 浏览器适配器
    "create_browser_use_adapter",
    # 扩展系统
    "get_extension_manager",
    "get_plugin_system",
    "get_user_script_manager",
    "ExtensionAPI",
    # 配置管理
    "get_config_manager",
    "ConfigOption",
    "ConfigType",
    "ConfigValidator",
]