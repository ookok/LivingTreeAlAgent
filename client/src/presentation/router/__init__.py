"""
路由系统 - 统一管理模块切换

解决原有200个panel平铺、导航混乱问题。
"""

from .router import Router, Route, get_router
from .routes import register_default_routes

__all__ = [
    "Router",
    "Route",
    "get_router",
    "register_default_routes",
]
