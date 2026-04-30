# -*- coding: utf-8 -*-
"""
深度搜索代理集成模块

集成到 ui/deep_search_panel.py 的搜索功能：
1. URL识别与路由
2. 代理/直连自动选择
3. 白名单控制
4. AI增强浏览器调用
5. 搜索结果处理
"""

import asyncio
import logging
import re
from typing import Optional, Dict, Any, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse, quote_plus

logger = logging.getLogger(__name__)


class InputType(Enum):
    """输入类型"""
    SEARCH_QUERY = "search_query"  # 搜索查询
    DIRECT_URL = "direct_url"  # 直接URL
    BLOCKED_URL = "blocked_url"  # 被阻止的URL
    LOCAL_FILE = "local_file"  # 本地文件
    UNKNOWN = "unknown"  # 未知


class SearchEngine(Enum):
    """搜索引擎"""
    GOOGLE = ("Google", "https://www.google.com/search?q={q}")
    BING = ("Bing", "https://www.bing.com/search?q={q}")
    SCHOLAR = ("Scholar", "https://scholar.google.com/scholar?q={q}")
    ARXIV = ("ArXiv", "https://arxiv.org/search/?search-type=all&query={q}")
    BAIDU = ("Baidu", "https://www.baidu.com/s?wd={q}")
    BING_SCHOLAR = ("Bing Scholar", "https://academic.bing.com/search?q={q}")

    @property
    def display_name(self) -> str:
        """显示名称"""
        return self.value[0]

    @property
    def url_template(self) -> str:
        """URL模板"""
        return self.value[1]

    def build_url(self, query: str) -> str:
        """构建搜索URL"""
        return self.url_template.format(q=quote_plus(query))


@dataclass
class SearchRequest:
    """搜索请求"""
    raw_input: str  # 原始输入
    input_type: InputType
    final_url: str  # 处理后的URL
    use_proxy: bool  # 是否使用代理
    engine: Optional[SearchEngine]  # 使用的搜索引擎
    metadata: Dict[str, Any] = None  # 元数据


@dataclass
class SearchResult:
    """搜索结果"""
    success: bool
    content: Any = None  # HTML、文本等
    url: str = ""
    status_code: int = 0
    error: str = ""
    routing_info: Dict = None  # 路由信息


class DeepSearchProxyIntegration:
    """
    深度搜索代理集成

    集成到 DeepSearchPanel 的搜索功能
    """

    # URL正则
    URL_PATTERN = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?'
        r'|localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?(?:/?|[/?]\S+)$',
        re.IGNORECASE
    )

    # 搜索引擎检测关键词
    ENGINE_KEYWORDS = {
        "google": ["google", "gstatic"],
        "bing": ["bing.com"],
        "scholar": ["scholar.google"],
        "arxiv": ["arxiv.org"],
        "baidu": ["baidu.com", "baike.baidu"],
    }

    def __init__(self):
        self._config = None
        self._router = None
        self._browser_adapter = None
        self._initialized = False

    def _lazy_init(self):
        """延迟初始化"""
        if self._initialized:
            return

        try:
            from client.src.business.proxy_search.config import get_config
            from client.src.business.proxy_search.url_router import get_router

            self._config = get_config()
            self._router = get_router()

            # 尝试导入浏览器适配器
            try:
                from client.src.business.browser_gateway.browser_use_adapter import BrowserUseAdapter
                self._browser_adapter = BrowserUseAdapter()
            except ImportError:
                self._browser_adapter = None
                logger.warning("browser-use 适配器未安装，浏览器功能不可用")

            self._initialized = True
            logger.info("深度搜索代理集成初始化成功")
        except ImportError as e:
            logger.warning(f"代理搜索模块部分功能不可用: {e}")
            self._initialized = True  # 避免重复尝试

    def is_url(self, text: str) -> bool:
        """判断输入是否为URL"""
        return bool(self.URL_PATTERN.match(text.strip()))

    def detect_input_type(self, user_input: str) -> InputType:
        """
        检测输入类型

        Args:
            user_input: 用户输入

        Returns:
            InputType: 输入类型
        """
        if not user_input or not user_input.strip():
            return InputType.UNKNOWN

        text = user_input.strip()

        # 检查是否是URL
        if self.is_url(text):
            # 检查是否被阻止
            if self._is_blocked(text):
                return InputType.BLOCKED_URL
            return InputType.DIRECT_URL

        # 检查是否包含URL
        if re.search(r'https?://', text):
            return InputType.BLOCKED_URL if self._is_blocked(text) else InputType.DIRECT_URL

        # 默认为搜索查询
        return InputType.SEARCH_QUERY

    def _is_blocked(self, url: str) -> bool:
        """检查URL是否被阻止"""
        self._lazy_init()
        if self._router:
            try:
                from client.src.business.proxy_search.config import should_use_proxy
                result = should_use_proxy(url)
                return result is None  # None 表示被阻止
            except Exception:
                pass
        return False

    def detect_search_engine(self, user_input: str) -> SearchEngine:
        """
        检测用户意图的搜索引擎

        Args:
            user_input: 用户输入

        Returns:
            SearchEngine: 搜索引擎
        """
        text_lower = user_input.lower()

        for engine_name, keywords in self.ENGINE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    try:
                        return SearchEngine[engine_name.upper()]
                    except KeyError:
                        continue

        return SearchEngine.GOOGLE  # 默认使用Google

    def prepare_request(self, user_input: str) -> SearchRequest:
        """
        准备搜索请求

        Args:
            user_input: 用户输入

        Returns:
            SearchRequest: 准备好的请求
        """
        self._lazy_init()
        input_type = self.detect_input_type(user_input)

        request = SearchRequest(
            raw_input=user_input,
            input_type=input_type,
            final_url="",
            use_proxy=False,
            engine=None,
            metadata={}
        )

        if input_type == InputType.SEARCH_QUERY:
            # 搜索查询
            engine = self.detect_search_engine(user_input)
            request.final_url = engine.build_url(user_input)
            request.use_proxy = True  # 学术搜索使用代理
            request.engine = engine
            request.metadata["search_engine"] = engine.name

        elif input_type == InputType.DIRECT_URL:
            # 直接URL
            request.final_url = user_input.strip()
            request.use_proxy = self._should_use_proxy_for_url(request.final_url)

        elif input_type == InputType.BLOCKED_URL:
            # 被阻止的URL
            request.final_url = user_input.strip()
            request.use_proxy = False
            request.metadata["warning"] = "URL在黑名单中"

        return request

    def _should_use_proxy_for_url(self, url: str) -> bool:
        """判断URL是否应使用代理"""
        self._lazy_init()
        try:
            from client.src.business.proxy_search.config import should_use_proxy
            result = should_use_proxy(url)
            return result is True
        except Exception:
            pass

        # 默认逻辑：学术域名使用代理
        academic_domains = [
            "arxiv.org", "scholar.google.com", "pubmed.ncbi.nlm.nih.gov",
            "ieee.org", "acm.org", "springer.com", "nature.com",
            "science.org", "cell.com", "jstor.org",
        ]
        parsed = urlparse(url)
        return any(domain in parsed.netloc.lower() for domain in academic_domains)

    async def execute_search(self, request: SearchRequest) -> SearchResult:
        """
        执行搜索

        Args:
            request: 搜索请求

        Returns:
            SearchResult: 搜索结果
        """
        self._lazy_init()

        if request.input_type == InputType.BLOCKED_URL:
            return SearchResult(
                success=False,
                error="该URL不在白名单中，不允许访问",
                url=request.final_url,
                routing_info=request.metadata
            )

        if request.input_type == InputType.UNKNOWN:
            return SearchResult(
                success=False,
                error="空输入"
            )

        try:
            if request.use_proxy:
                # 使用代理
                result = await self._proxy_request(request.final_url)
            else:
                # 直连
                result = await self._direct_request(request.final_url)

            return result

        except Exception as e:
            logger.error(f"搜索执行失败: {e}")
            return SearchResult(
                success=False,
                error=str(e),
                url=request.final_url,
                routing_info=request.metadata
            )

    async def _proxy_request(self, url: str) -> SearchResult:
        """使用代理请求"""
        try:
            from client.src.business.proxy_search.proxy_middleware import get_middleware
            middleware = get_middleware()
            response = middleware.get(url, timeout=30)
            return SearchResult(
                success=True,
                content=response.text,
                url=str(response.url),
                status_code=response.status_code,
                routing_info={"method": "proxy"}
            )
        except Exception as e:
            logger.error(f"代理请求失败: {e}")
            return SearchResult(
                success=False,
                error=f"代理请求失败: {e}",
                url=url
            )

    async def _direct_request(self, url: str) -> SearchResult:
        """直连请求"""
        try:
            import requests
            response = requests.get(url, timeout=30)
            return SearchResult(
                success=True,
                content=response.text,
                url=str(response.url),
                status_code=response.status_code,
                routing_info={"method": "direct"}
            )
        except Exception as e:
            logger.error(f"直连请求失败: {e}")
            return SearchResult(
                success=False,
                error=f"直连请求失败: {e}",
                url=url
            )

    async def open_in_browser(self, url: str, use_proxy: bool = None) -> bool:
        """
        在AI增强浏览器中打开URL

        Args:
            url: URL
            use_proxy: 是否使用代理（None=自动）

        Returns:
            bool: 是否成功
        """
        self._lazy_init()

        # 自动判断
        if use_proxy is None:
            use_proxy = self._should_use_proxy_for_url(url)

        # 检查是否被阻止
        if self._is_blocked(url):
            logger.warning(f"URL被阻止: {url}")
            return False

        try:
            if self._browser_adapter:
                # 使用browser-use适配器
                result = await self._browser_adapter.navigate(url)
                return result.get("success", False)
            else:
                # 回退：使用系统默认浏览器
                import webbrowser
                webbrowser.open(url)
                return True

        except Exception as e:
            logger.error(f"浏览器打开失败: {e}")
            return False

    def get_routing_preview(self, user_input: str) -> Dict[str, Any]:
        """
        获取路由预览

        Args:
            user_input: 用户输入

        Returns:
            Dict: 路由预览
        """
        request = self.prepare_request(user_input)
        input_type = request.input_type

        return {
            "input": user_input,
            "type": input_type.value,
            "final_url": request.final_url,
            "use_proxy": request.use_proxy,
            "engine": request.engine.name if request.engine else None,
            "allowed": input_type != InputType.BLOCKED_URL,
            "blocked": input_type == InputType.BLOCKED_URL,
            "description": self._get_type_description(input_type),
        }

    def _get_type_description(self, input_type: InputType) -> str:
        """获取类型描述"""
        descriptions = {
            InputType.SEARCH_QUERY: "将作为搜索查询处理",
            InputType.DIRECT_URL: "将直接访问URL",
            InputType.BLOCKED_URL: "URL在黑名单中，拒绝访问",
            InputType.LOCAL_FILE: "将打开本地文件",
            InputType.UNKNOWN: "无法识别的输入",
        }
        return descriptions.get(input_type, "")


# 全局实例
_integration: Optional[DeepSearchProxyIntegration] = None


def get_deep_search_integration() -> DeepSearchProxyIntegration:
    """获取全局集成实例"""
    global _integration
    if _integration is None:
        _integration = DeepSearchProxyIntegration()
    return _integration


def is_blocked_url(url: str) -> bool:
    """快捷函数：检查URL是否被阻止"""
    return get_deep_search_integration()._is_blocked(url)


def get_input_preview(user_input: str) -> Dict[str, Any]:
    """快捷函数：获取输入预览"""
    return get_deep_search_integration().get_routing_preview(user_input)
