# -*- coding: utf-8 -*-
"""
代理请求中间件
将代理池集成到网络请求中
"""

import logging
import time
from typing import Optional, Dict, Callable, Any
from functools import wraps

import requests
from requests.exceptions import (
    ProxyError,
    ConnectionError as RequestsConnectionError,
    Timeout,
    SSLError
)

from .proxy_pool import get_proxy_pool, PooledProxy
from .proxy_sources import Proxy
from .config import get_config

logger = logging.getLogger(__name__)


class ProxyMiddleware:
    """
    代理请求中间件
    
    功能：
    - 自动从代理池获取代理
    - 失败自动重试（使用其他代理）
    - 记录代理使用情况
    - 代理不可用时自动切换
    """
    
    def __init__(self):
        self.pool = get_proxy_pool()
        self.config = get_config()
        self._session: Optional[requests.Session] = None
    
    @property
    def session(self) -> requests.Session:
        """获取请求会话"""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": self.config.user_agent,
            })
        return self._session
    
    def request(
        self,
        method: str,
        url: str,
        max_retries: int = None,
        timeout: int = 30,
        **kwargs
    ) -> requests.Response:
        """
        使用代理发送请求
        
        Args:
            method: HTTP 方法
            url: 请求 URL
            max_retries: 最大重试次数
            timeout: 超时时间
            **kwargs: 其他请求参数
            
        Returns:
            响应对象
            
        Raises:
            requests.exceptions.RequestException: 请求失败
        """
        max_retries = max_retries or self.config.pool.max_retries
        last_error = None
        
        for attempt in range(max_retries):
            # 从代理池获取代理
            pooled_proxy = self.pool.get_proxy()
            
            if pooled_proxy is None:
                logger.warning(f"无可用代理，尝试 {attempt + 1}/{max_retries}")
                time.sleep(self.config.pool.retry_delay)
                continue
            
            proxy = pooled_proxy.proxy
            start_time = time.time()
            
            try:
                # 准备代理
                proxies = {
                    'http': proxy.full_address,
                    'https': proxy.full_address,
                }
                
                # 合并 kwargs
                request_kwargs = {
                    'method': method,
                    'url': url,
                    'proxies': proxies,
                    'timeout': timeout,
                }
                request_kwargs.update(kwargs)
                
                # 发送请求
                response = self.session.request(**request_kwargs)
                
                # 记录成功
                latency = time.time() - start_time
                self.pool.record_proxy_success(proxy, latency)
                
                logger.debug(f"请求成功: {url} via {proxy.address} ({latency:.2f}s)")
                return response
                
            except (ProxyError, RequestsConnectionError, SSLError) as e:
                latency = time.time() - start_time
                self.pool.record_proxy_failure(proxy)
                last_error = e
                
                logger.warning(
                    f"代理 {proxy.address} 请求失败: {type(e).__name__}, "
                    f"尝试 {attempt + 1}/{max_retries}"
                )
                
            except Timeout as e:
                latency = time.time() - start_time
                self.pool.record_proxy_failure(proxy)
                last_error = e
                
                logger.warning(
                    f"代理 {proxy.address} 超时 ({timeout}s), "
                    f"尝试 {attempt + 1}/{max_retries}"
                )
            
            # 重试前等待
            if attempt < max_retries - 1:
                time.sleep(self.config.pool.retry_delay)
        
        # 所有重试都失败
        logger.error(f"请求 {url} 最终失败: {last_error}")
        raise last_error or requests.exceptions.RequestException("请求失败")
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """GET 请求"""
        return self.request("GET", url, **kwargs)
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """POST 请求"""
        return self.request("POST", url, **kwargs)
    
    def head(self, url: str, **kwargs) -> requests.Response:
        """HEAD 请求"""
        return self.request("HEAD", url, **kwargs)

    def direct_request(
        self,
        method: str,
        url: str,
        timeout: int = 30,
        **kwargs
    ) -> requests.Response:
        """
        直连请求（不使用代理）

        Args:
            method: HTTP 方法
            url: 请求 URL
            timeout: 超时时间
            **kwargs: 其他请求参数

        Returns:
            响应对象
        """
        request_kwargs = {
            'method': method,
            'url': url,
            'timeout': timeout,
        }
        request_kwargs.update(kwargs)

        response = self.session.request(**request_kwargs)
        logger.debug(f"直连请求成功: {url}")
        return response

    def direct_get(self, url: str, **kwargs) -> requests.Response:
        """直连 GET 请求"""
        return self.direct_request("GET", url, **kwargs)

    def direct_post(self, url: str, **kwargs) -> requests.Response:
        """直连 POST 请求"""
        return self.direct_request("POST", url, **kwargs)


# 便捷装饰器
def with_proxy(func: Callable) -> Callable:
    """
    代理请求装饰器
    
    使用方式：
    ```python
    @with_proxy
    def fetch_data(url):
        return requests.get(url)
    ```
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        middleware = ProxyMiddleware()
        
        # 如果函数有 proxies 参数，保留
        if 'proxies' not in kwargs:
            pooled = middleware.pool.get_proxy()
            if pooled:
                kwargs['proxies'] = {
                    'http': pooled.proxy.full_address,
                    'https': pooled.proxy.full_address,
                }
        
        return func(*args, **kwargs)
    
    return wrapper


# 全局实例
_middleware: Optional[ProxyMiddleware] = None


def get_middleware() -> ProxyMiddleware:
    """获取中间件实例"""
    global _middleware
    if _middleware is None:
        _middleware = ProxyMiddleware()
    return _middleware


def proxy_get(url: str, **kwargs) -> requests.Response:
    """使用代理的 GET 请求"""
    middleware = get_middleware()
    return middleware.get(url, **kwargs)


def proxy_post(url: str, **kwargs) -> requests.Response:
    """使用代理的 POST 请求"""
    middleware = get_middleware()
    return middleware.post(url, **kwargs)


def proxy_request(method: str, url: str, **kwargs) -> requests.Response:
    """使用代理的通用请求"""
    middleware = get_middleware()
    return middleware.request(method, url, **kwargs)
