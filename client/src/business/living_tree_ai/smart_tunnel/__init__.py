"""
智能伪装隧道系统 (Smart Tunnel System)
========================================

三层伪装架构：
1. 检测层 (Detection) - 实时检测连接状态
2. 伪装层 (Camouflage) - 选择最优节点建立加密隧道
3. 透明层 (Transparent) - 在 Qt 浏览器中无缝切换代理

核心特性：
- TLS 指纹随机化
- 专长路由策略
- 预测性预热
- PyQt 无缝集成
"""

from .tunnel_system import SmartTunnelSystem, TunnelConfig, create_tunnel_system
from .proxy_selector import ProxySelector, NodeScore, SpecialtyType
from .proxy_selector import create_proxy_selector, RoutingStrategy
from .local_proxy import LocalProxy, ProxyPool
from .local_proxy import create_local_proxy, ProxyProtocol

__all__ = [
    # 核心系统
    "SmartTunnelSystem",
    "TunnelConfig",
    "create_tunnel_system",
    # 代理选择器
    "ProxySelector",
    "NodeScore",
    "SpecialtyType",
    "create_proxy_selector",
    "RoutingStrategy",
    # 本地代理
    "LocalProxy",
    "ProxyPool",
    "create_local_proxy",
    "ProxyProtocol",
]