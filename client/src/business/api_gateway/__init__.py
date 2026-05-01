"""
统一API网关 - Unified API Gateway

功能：
1. 统一入口管理所有系统API
2. 请求路由和分发
3. 请求日志和监控
4. 统一错误处理
5. API版本管理
"""

from .api_gateway import APIGateway, get_api_gateway
from .api_response import APIResponse, ErrorResponse
from .api_request import APIRequest

__all__ = [
    'APIGateway',
    'get_api_gateway',
    'APIResponse',
    'ErrorResponse',
    'APIRequest',
]


def api_call(endpoint: str, **kwargs) -> dict:
    """
    统一API调用入口
    
    Args:
        endpoint: API端点
        **kwargs: 请求参数
    
    Returns:
        响应结果
    """
    gateway = get_api_gateway()
    return gateway.call(endpoint, **kwargs)