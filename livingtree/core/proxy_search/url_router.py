# -*- coding: utf-8 -*-
"""
URL路由与白名单验证
"""

import re
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse
from dataclasses import dataclass
from enum import Enum

from .config import get_config, should_use_proxy, get_allowed_domains


class URLType(Enum):
    """URL类型枚举"""
    SEARCH_QUERY = "search_query"  # 搜索查询
    DIRECT_URL = "direct_url"  # 直接URL
    BLOCKED = "blocked"  # 被阻止
    LOCAL_FILE = "local_file"  # 本地文件


@dataclass
class URLRouteResult:
    """URL路由结果"""
    url_type: URLType
    final_url: str
    use_proxy: bool
    reason: str
    category: str = ""


class URLRouter:
    """
    URL路由与白名单验证器

    功能：
    1. 识别输入是搜索查询还是URL
    2. 检查白名单，决定是否使用代理
    3. 提供详细的路由信息
    """

    # URL正则表达式
    URL_PATTERN = re.compile(
        r'^https?://'  # http:// 或 https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )

    # 本地文件路径
    FILE_PATTERN = re.compile(
        r'^(?:[a-zA-Z]:\\|/)?(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*$'
    )

    def __init__(self):
        self.config = get_config()

    def route(self, user_input: str) -> URLRouteResult:
        """
        路由用户输入

        Args:
            user_input: 用户输入（可能是URL、搜索查询、或本地文件路径）

        Returns:
            URLRouteResult: 路由结果
        """
        # 1. 检查是否为空
        if not user_input or not user_input.strip():
            return URLRouteResult(
                url_type=URLType.SEARCH_QUERY,
                final_url="",
                use_proxy=False,
                reason="空输入"
            )

        user_input = user_input.strip()

        # 2. 检查是否是本地文件
        if self._is_local_file(user_input):
            return URLRouteResult(
                url_type=URLType.LOCAL_FILE,
                final_url=user_input,
                use_proxy=False,
                reason="本地文件"
            )

        # 3. 检查是否是URL
        if self._is_url(user_input):
            return self._route_url(user_input)

        # 4. 否则作为搜索查询处理
        return self._route_search_query(user_input)

    def _is_url(self, text: str) -> bool:
        """判断是否是URL"""
        # 直接匹配URL模式
        if self.URL_PATTERN.match(text):
            return True

        # 检查是否以协议开头
        if text.startswith(('http://', 'https://', 'ftp://', 'file://')):
            return True

        # 检查是否包含域名模式
        url_patterns = [
            r'\.[a-z]{2,}\b',  # .com, .org, .cn 等
            r'localhost\b',
        ]
        for pattern in url_patterns:
            if re.search(pattern, text):
                return True

        return False

    def _is_local_file(self, text: str) -> bool:
        """判断是否是本地文件路径"""
        # Windows路径
        if re.match(r'^[a-zA-Z]:\\', text):
            return True
        # Unix路径
        if text.startswith('/') and not text.startswith('//'):
            return True
        # 文件协议
        if text.startswith('file://'):
            return True
        return False

    def _route_url(self, url: str) -> URLRouteResult:
        """路由URL输入"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # 检查代理决策
        use_proxy = should_use_proxy(url)

        # 确定URL类型
        if use_proxy is None:
            # 被阻止
            return URLRouteResult(
                url_type=URLType.BLOCKED,
                final_url=url,
                use_proxy=False,
                reason="不在白名单，拒绝访问",
                category="blocked"
            )

        if use_proxy:
            # 查找匹配的分类
            category = self._get_url_category(domain)
            return URLRouteResult(
                url_type=URLType.DIRECT_URL,
                final_url=url,
                use_proxy=True,
                reason=f"代理访问 - {category}",
                category=category
            )
        else:
            return URLRouteResult(
                url_type=URLType.DIRECT_URL,
                final_url=url,
                use_proxy=False,
                reason="直连",
                category="direct"
            )

    def _route_search_query(self, query: str) -> URLRouteResult:
        """路由搜索查询"""
        # 检查是否包含搜索引擎
        search_engines = self.config.whitelist.search_engines

        # 尝试检测用户意图的搜索引擎
        detected_engine = None
        detected_domain = None

        query_lower = query.lower()
        for engine_domain in search_engines:
            if engine_domain.replace("google.com", "").replace("bing.com", "") in query_lower:
                detected_domain = engine_domain
                break

        # 构建搜索URL
        if detected_domain:
            # 用户指定了搜索引擎
            if "google" in detected_domain:
                search_url = f"https://www.google.com/search?q={self._encode_query(query)}"
            elif "bing" in detected_domain:
                search_url = f"https://www.bing.com/search?q={self._encode_query(query)}"
            else:
                search_url = f"https://{detected_domain}/search?q={self._encode_query(query)}"

            return URLRouteResult(
                url_type=URLType.SEARCH_QUERY,
                final_url=search_url,
                use_proxy=True,
                reason=f"使用 {detected_domain}",
                category="search"
            )

        # 默认使用Google
        search_url = f"https://www.google.com/search?q={self._encode_query(query)}"

        return URLRouteResult(
            url_type=URLType.SEARCH_QUERY,
            final_url=search_url,
            use_proxy=True,
            reason="智能选择搜索引擎",
            category="search"
        )

    def _encode_query(self, query: str) -> str:
        """URL编码查询"""
        import urllib.parse
        return urllib.parse.quote_plus(query)

    def _get_url_category(self, domain: str) -> str:
        """获取URL所属分类"""
        whitelist = self.config.whitelist

        for category_name, domains in [
            ("搜索引擎", whitelist.search_engines),
            ("编程问答", whitelist.coding_qa),
            ("开发文档", whitelist.dev_docs),
            ("AI/机器学习", whitelist.ai_ml),
            ("知识库", whitelist.knowledge),
        ]:
            for allowed_domain in domains:
                if allowed_domain in domain:
                    return category_name

        return "其他"

    def is_blocked(self, url: str) -> bool:
        """快速检查URL是否被阻止"""
        result = self.route(url)
        return result.url_type == URLType.BLOCKED

    def get_access_info(self, url: str) -> Dict[str, Any]:
        """获取URL的完整访问信息"""
        result = self.route(url)

        return {
            "original_url": url,
            "final_url": result.final_url,
            "type": result.url_type.value,
            "use_proxy": result.use_proxy,
            "reason": result.reason,
            "category": result.category,
            "allowed": result.url_type != URLType.BLOCKED,
        }


# 全局路由实例
_router: Optional[URLRouter] = None


def get_router() -> URLRouter:
    """获取全局路由实例"""
    global _router
    if _router is None:
        _router = URLRouter()
    return _router


def route_url(url: str) -> URLRouteResult:
    """快捷函数：路由URL"""
    return get_router().route(url)


def is_blocked(url: str) -> bool:
    """快捷函数：检查URL是否被阻止"""
    return get_router().is_blocked(url)


def get_access_info(url: str) -> Dict[str, Any]:
    """快捷函数：获取访问信息"""
    return get_router().get_access_info(url)
