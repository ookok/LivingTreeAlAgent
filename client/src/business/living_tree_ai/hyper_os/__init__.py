"""
HyperOS 增强服务层
====================

核心架构：将浏览器"组件化"，所有智能增强都在Python应用层实现

┌─────────────────────────────────────────────────────────────┐
│                  HyperOS 环评智能客户端                      │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  增强服务层 (Python)                                   │ │
│  │  • SmartProxy        - 智能代理服务器                   │ │
│  │  • BrowserBridge     - 浏览器双向通信                   │ │
│  │  • InjectionEngine  - 脚本注入引擎                     │ │
│  │  • EIAEnhancement    - 环评增强服务                     │ │
│  │  • P2PNetwork        - P2P缓存网络                      │ │
│  └───────────────────────────┬───────────────────────────┘ │
│                              │ IPC / WebSocket / HTTP       │
│  ┌───────────────────────────▼───────────────────────────┐ │
│  │  浏览器控制层 (PyQt)                                    │ │
│  │  • QWebEngineView (纯净未修改)                        │ │
│  │  • 仅负责：加载URL、渲染、基本交互                     │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

三大核心技术方案：
1. SmartProxy - 本地代理服务器（网络层拦截）
2. BrowserBridge - WebSocket双向通信（实时控制）
3. HTTP API - 功能调用（异步增强）
"""

from .smart_proxy import SmartProxy, SmartProxyHandler
from .browser_bridge import BrowserBridge, BrowserMessage
from .injection_engine import InjectionEngine, InjectionRule
from .eia_enhancement_service import EIAEnhancementService, FormAutoFill
from .hyper_os_controller import HyperOSController, create_hyper_os

__all__ = [
    # 智能代理
    "SmartProxy",
    "SmartProxyHandler",
    # 浏览器桥接
    "BrowserBridge",
    "BrowserMessage",
    # 注入引擎
    "InjectionEngine",
    "InjectionRule",
    # 环评增强
    "EIAEnhancementService",
    "FormAutoFill",
    # 主控制器
    "HyperOSController",
    "create_hyper_os",
]