# -*- coding: utf-8 -*-
"""
深度搜索代理集成

处理深度搜索界面中的：
1. URL识别与路由
2. 代理/直连自动选择
3. AI增强浏览器集成
"""

import re
import logging
from typing import Optional, Dict, Any, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

from .config import get_config, should_use_proxy
from .url_router import get_router, URLRouteResult, URLType, get_access_info
from .proxy_middleware import get_middleware, ProxyMiddleware
from .monitor import get_monitor

logger = logging.getLogger(__name__)


class SearchMode(Enum):
    """搜索模式"""
    DIRECT = "direct"  # 直接搜索（输入即为URL或本地查询）
    SEARCH = "search"  # 搜索引擎搜索
    RESEARCH = "research"  # 深度研究模式
    URL_OPEN = "url_open"  # 打开URL


@dataclass
class DeepSearchRequest:
    """深度搜索请求"""
    raw_input: str  # 原始输入
    mode: SearchMode
    url: str  # 处理后的URL
    use_proxy: bool  # 是否使用代理
    headers: Dict[str, str] = None  # 请求头
    metadata: Dict[str, Any] = None  # 元数据


@dataclass
class DeepSearchResponse:
    """深度搜索响应"""
    success: bool
    content: Any = None  # 内容（HTML、文本、JSON等）
    url: str = ""  # 实际访问的URL
    headers: Dict = None
    status_code: int = 0
    error: str = ""
    routing_info: Dict = None  # 路由信息


class DeepSearchProxyIntegration:
    """
    深度搜索代理集成

    功能：
    1. 自动识别输入类型（URL/搜索查询/本地文件）
    2. 智能路由（代理/直连）
    3. 代理池负载均衡
    4. 异常处理与重试
    5. AI增强浏览器集成
    """

    def __init__(self):
        self._router = get_router()
        self._middleware = get_middleware()
        self._monitor = get_monitor()
        self._config = get_config()

    def prepare_request(self, user_input: str) -> DeepSearchRequest:
        """
        准备请求

        Args:
            user_input: 用户输入

        Returns:
            DeepSearchRequest: 准备好的请求
        """
        # 路由分析
        route_result = self._router.route(user_input)
        access_info = get_access_info(user_input)

        # 确定搜索模式
        mode = self._determine_mode(user_input, route_result)

        # 构建请求
        request = DeepSearchRequest(
            raw_input=user_input,
            mode=mode,
            url=access_info["final_url"],
            use_proxy=access_info["use_proxy"],
            headers=self._build_headers(),
            metadata={
                "route_info": access_info,
                "timestamp": self._get_timestamp(),
            }
        )

        return request

    def _determine_mode(self, user_input: str, route_result: URLRouteResult) -> SearchMode:
        """确定搜索模式"""
        if route_result.url_type == URLType.LOCAL_FILE:
            return SearchMode.DIRECT
        elif route_result.url_type == URLType.BLOCKED:
            return SearchMode.DIRECT  # 被阻止时降级为直接模式
        elif route_result.url_type == URLType.SEARCH_QUERY:
            return SearchMode.SEARCH
        elif route_result.url_type == URLType.DIRECT_URL:
            # 检查是否是学术资源
            academic_domains = ["arxiv.org", "scholar.google.com", "pubmed.ncbi.nlm.nih.gov",
                                "ieee.org", "acm.org", "springer.com"]
            parsed = urlparse(route_result.final_url)
            if any(domain in parsed.netloc.lower() for domain in academic_domains):
                return SearchMode.RESEARCH
            return SearchMode.URL_OPEN
        else:
            return SearchMode.SEARCH

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "User-Agent": self._config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()

    async def execute_request(self, request: DeepSearchRequest) -> DeepSearchResponse:
        """
        执行请求

        Args:
            request: 准备好的请求

        Returns:
            DeepSearchResponse: 响应
        """
        # 检查是否在线
        if not self._monitor.is_online() and request.use_proxy:
            return DeepSearchResponse(
                success=False,
                error="网络已断开，无法使用代理访问",
                routing_info=request.metadata.get("route_info"),
            )

        # 检查是否被阻止
        if request.mode == SearchMode.DIRECT and not request.url:
            return DeepSearchResponse(
                success=False,
                error="输入被白名单阻止",
                routing_info=request.metadata.get("route_info"),
            )

        try:
            if request.use_proxy:
                # 使用代理
                response = await self._middleware.proxy_get(
                    request.url,
                    headers=request.headers,
                )
            else:
                # 直连
                response = await self._middleware.direct_get(
                    request.url,
                    headers=request.headers,
                )

            return DeepSearchResponse(
                success=response.status_code < 400,
                content=response.content,
                url=str(response.url),
                headers=dict(response.headers),
                status_code=response.status_code,
                routing_info=request.metadata.get("route_info"),
            )

        except Exception as e:
            logger.error(f"请求执行失败: {e}")
            return DeepSearchResponse(
                success=False,
                error=str(e),
                url=request.url,
                routing_info=request.metadata.get("route_info"),
            )

    def get_routing_preview(self, user_input: str) -> Dict[str, Any]:
        """
        获取路由预览（不执行请求）

        Args:
            user_input: 用户输入

        Returns:
            Dict: 路由预览信息
        """
        access_info = get_access_info(user_input)
        route_result = self._router.route(user_input)
        mode = self._determine_mode(user_input, route_result)

        return {
            "input": user_input,
            "type_detected": route_result.url_type.value,
            "mode": mode.value,
            "final_url": access_info["final_url"],
            "use_proxy": access_info["use_proxy"],
            "proxy_reason": access_info["reason"],
            "category": access_info["category"],
            "allowed": access_info["allowed"],
            "blocked": not access_info["allowed"],
        }

    def is_url(self, text: str) -> bool:
        """快速判断输入是否为URL"""
        return self._router._is_url(text)

    def is_blocked(self, url: str) -> bool:
        """快速判断URL是否被阻止"""
        return self._router.is_blocked(url)


# 全局实例
_integration: Optional[DeepSearchProxyIntegration] = None


def get_integration() -> DeepSearchProxyIntegration:
    """获取全局集成实例"""
    global _integration
    if _integration is None:
        _integration = DeepSearchProxyIntegration()
    return _integration


async def initialize_integration() -> DeepSearchProxyIntegration:
    """初始化集成"""
    integration = get_integration()
    return integration


def route_input(user_input: str) -> Dict[str, Any]:
    """快捷函数：路由用户输入"""
    return get_integration().get_routing_preview(user_input)


def is_blocked(url: str) -> bool:
    """快捷函数：检查URL是否被阻止"""
    return get_integration().is_blocked(url)
