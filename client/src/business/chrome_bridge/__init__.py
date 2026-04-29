"""
Chrome Bridge - Chrome 浏览器桥接系统
==========================================

直接利用用户已登录的 Chrome 浏览器会话，通过 CDP (Chrome DevTools Protocol)
实现无感复用登录状态，内置反检测机制，支持 80+ 网站适配器。

核心特性：
- 会话复用：连接本地已运行的 Chrome，复用所有登录状态
- 反检测：自动清理 navigator.webdriver 等指纹，绕过反爬虫
- 双模式：支持 headed（有界面）和 headless（无界面）两种模式
- 80+ 适配器：覆盖开发平台、技术社区、云服务、AI 平台等主流网站

参考：
- OpenCLI 的会话复用思想
- 项目已有 browser_automation_guide.py 的 CDP 基础
"""

__version__ = "1.0.0"

from client.src.business.chrome_bridge.chrome_bridge import ChromeBridge, get_chrome_bridge
from client.src.business.chrome_bridge.browser_launcher import BrowserLauncher, get_browser_launcher
from client.src.business.chrome_bridge.anti_detection import AntiDetectionEngine, get_anti_detection_engine
from client.src.business.chrome_bridge.website_adapter_registry import WebsiteAdapterRegistry, get_adapter_registry

__all__ = [
    "ChromeBridge",
    "get_chrome_bridge",
    "BrowserLauncher",
    "get_browser_launcher",
    "AntiDetectionEngine",
    "get_anti_detection_engine",
    "WebsiteAdapterRegistry",
    "get_adapter_registry",
]
