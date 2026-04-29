"""
HyperOS 主控制器
=================

核心架构：整合所有服务，为PyQt浏览器提供智能增强能力

┌─────────────────────────────────────────────────────────────┐
│                    HyperOS Controller                       │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  服务层                                                │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐ │ │
│  │  │ SmartProxy │ │BrowserBridge│ │InjectionEngine │ │ │
│  │  │  代理服务器  │ │  WebSocket  │ │   脚本注入      │ │ │
│  │  └──────┬──────┘ └──────┬──────┘ └────────┬────────┘ │ │
│  │         └───────────────┼─────────────────┘          │ │
│  │                         ▼                            │ │
│  │  ┌─────────────────────────────────────────────────┐│ │
│  │  │          EIA Enhancement Service                 ││ │
│  │  │   智能填表 │ 文档上传 │ 数据提取 │ 审批跟踪      ││ │
│  │  └─────────────────────────────────────────────────┘│ │
│  └───────────────────────────────────────────────────────┘ │
│                            │                                │
│  ┌─────────────────────────▼─────────────────────────────┐│
│  │  协议层                                                ││
│  │  WebSocket │ HTTP Server │ PyQt Signal/Slot          ││
│  └─────────────────────────┬─────────────────────────────┘│
│                            │                              │
│  ┌─────────────────────────▼─────────────────────────────┐│
│  │  浏览器层 (PyQt)                                      ││
│  │  QWebEngineView (纯净未修改)                         ││
│  └───────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .smart_proxy import SmartProxy, get_smart_proxy
from .browser_bridge import BrowserBridge, BrowserMessage, MessageType, get_browser_bridge
from .injection_engine import InjectionEngine, get_injection_engine
from .eia_enhancement_service import EIAEnhancementService, get_eia_enhancement_service


class HyperOSMode(Enum):
    """运行模式"""
    STANDALONE = "standalone"      # 独立模式（仅本地服务）
    INTEGRATED = "integrated"     # 集成模式（与PyQt浏览器结合）
    DISTRIBUTED = "distributed"  # 分布式模式（P2P网络）


@dataclass
class HyperOSConfig:
    """HyperOS配置"""
    # 端口配置
    proxy_port: int = 8888
    websocket_port: int = 8765
    http_port: int = 5000
    injection_port: int = 9999

    # 模式
    mode: HyperOSMode = HyperOSMode.INTEGRATED

    # 功能开关
    enable_proxy: bool = True
    enable_websocket: bool = True
    enable_injection: bool = True
    enable_eia_service: bool = True

    # 代理配置
    proxy_rules: List[Dict] = field(default_factory=list)

    # 注入配置
    injection_rules: List[Dict] = field(default_factory=list)


class HyperOSController:
    """
    HyperOS 主控制器

    整合所有服务，提供统一的控制接口
    """

    def __init__(self, config: Optional[HyperOSConfig] = None):
        self.config = config or HyperOSConfig()

        # 服务实例
        self.smart_proxy: Optional[SmartProxy] = None
        self.browser_bridge: Optional[BrowserBridge] = None
        self.injection_engine: Optional[InjectionEngine] = None
        self.eia_service: Optional[EIAEnhancementService] = None

        # 状态
        self.is_running = False
        self.started_services: List[str] = []

        # PyQt回调
        self.pyqt_callback: Optional[Callable] = None

        # 初始化服务
        self._init_services()

    def _init_services(self):
        """初始化服务"""
        # 代理服务
        if self.config.enable_proxy:
            self.smart_proxy = get_smart_proxy(self.config.proxy_port)

        # WebSocket桥接
        if self.config.enable_websocket:
            self.browser_bridge = get_browser_bridge(self.config.websocket_port)
            # 注册消息处理器
            self._register_bridge_handlers()

        # 注入引擎
        if self.config.enable_injection:
            self.injection_engine = get_injection_engine()

        # 环评增强服务
        if self.config.enable_eia_service:
            self.eia_service = get_eia_enhancement_service()

    def _register_bridge_handlers(self):
        """注册桥接消息处理器"""
        if not self.browser_bridge:
            return

        # 注册页面内容处理器
        async def handle_page_content(msg: BrowserMessage):
            if self.eia_service:
                # 提取页面数据
                data = await self.eia_service.extract_page_data(
                    msg.payload.get("url", ""),
                    msg.payload.get("html", "")
                )
                return {
                    "type": "page_extracted",
                    "data": data
                }
            return {"type": "error", "message": "Service not available"}

        # 注册表单数据处理器
        async def handle_form_data(msg: BrowserMessage):
            if self.eia_service:
                autofill = await self.eia_service.get_autofill_data(
                    msg.payload.get("url", ""),
                    msg.payload
                )
                return {
                    "type": "autofill",
                    "fields": autofill.fields,
                    "confidence": autofill.confidence
                }
            return {"type": "error", "message": "Service not available"}

        self.browser_bridge.register_handler(MessageType.PAGE_CONTENT, handle_page_content)
        self.browser_bridge.register_handler(MessageType.FORM_DATA, handle_form_data)

    async def start(self):
        """启动所有服务"""
        if self.is_running:
            return

        print("Starting HyperOS...")

        # 启动代理服务
        if self.smart_proxy and self.config.enable_proxy:
            await self.smart_proxy.start()
            self.started_services.append("smart_proxy")
            print(f"  ✓ SmartProxy on port {self.config.proxy_port}")

        # 启动WebSocket服务
        if self.browser_bridge and self.config.enable_websocket:
            await self.browser_bridge.start()
            self.started_services.append("browser_bridge")
            print(f"  ✓ BrowserBridge on port {self.config.websocket_port}")

        self.is_running = True
        print("HyperOS started successfully!")

    async def stop(self):
        """停止所有服务"""
        if not self.is_running:
            return

        print("Stopping HyperOS...")

        # 停止代理服务
        if self.smart_proxy and "smart_proxy" in self.started_services:
            await self.smart_proxy.stop()

        # 停止WebSocket服务
        if self.browser_bridge and "browser_bridge" in self.started_services:
            await self.browser_bridge.stop()

        self.is_running = False
        self.started_services = []
        print("HyperOS stopped.")

    # ============ 浏览器控制 ============

    async def send_to_browser(self, session_id: str, message: Dict):
        """发送消息到浏览器"""
        if not self.browser_bridge:
            return

        msg_type = MessageType(message.get("type", "notification"))
        msg = BrowserMessage(type=msg_type, payload=message)
        await self.browser_bridge.clients[session_id].send(msg.to_json())

    async def inject_script(self, session_id: str, script: str):
        """向指定会话注入脚本"""
        if not self.browser_bridge:
            return

        msg = BrowserMessage(
            type=MessageType.DRAW_COMMAND,
            payload={"type": "inject_script", "script": script}
        )
        await self.browser_bridge.clients[session_id].send(msg.to_json())

    # ============ 环评增强 ============

    async def autofill_form(self, session_id: str, form_id: str, fields: List[Dict]):
        """自动填表"""
        if not self.browser_bridge:
            return

        msg = BrowserMessage(
            type=MessageType.AUTOFILL,
            payload={"form_id": form_id, "fields": fields}
        )
        await self.browser_bridge.clients[session_id].send(msg.to_json())

    async def analyze_page(self, session_id: str):
        """分析页面"""
        # 发送分析命令
        msg = BrowserMessage(
            type=MessageType.ANALYZE_RESULT,
            payload={"command": "get_page_content"}
        )
        await self.browser_bridge.clients[session_id].send(msg.to_json())

    # ============ 状态查询 ============

    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "is_running": self.is_running,
            "services": self.started_services,
            "config": {
                "proxy_port": self.config.proxy_port,
                "websocket_port": self.config.websocket_port,
                "mode": self.config.mode.value,
            },
            "proxy_stats": self.smart_proxy.get_cache_stats() if self.smart_proxy else {},
            "active_sessions": len(self.browser_bridge.sessions) if self.browser_bridge else 0,
        }


# 全局实例
_hyper_os_instance: Optional[HyperOSController] = None


def create_hyper_os(config: Optional[HyperOSConfig] = None) -> HyperOSController:
    """创建HyperOS控制器"""
    global _hyper_os_instance
    _hyper_os_instance = HyperOSController(config)
    return _hyper_os_instance


def get_hyper_os() -> Optional[HyperOSController]:
    """获取HyperOS控制器"""
    return _hyper_os_instance


# ============ PyQt集成辅助 ============

class HyperOSQtBridge:
    """
    HyperOS PyQt桥接

    用于在PyQt环境中集成HyperOS
    """

    def __init__(self, controller: HyperOSController):
        self.controller = controller
        self.web_view = None  # QWebEngineView

    def configure_browser(self, web_view):
        """
        配置浏览器

        Args:
            web_view: QWebEngineView实例
        """
        from PyQt6.QtNetwork import QNetworkProxy

        self.web_view = web_view

        # 配置代理
        if self.controller.smart_proxy:
            profile = web_view.page().profile()
            profile.setHttpProxy(QNetworkProxy(
                QNetworkProxy.HttpProxy,
                "127.0.0.1",
                self.controller.config.proxy_port
            ))

    def connect_signals(self):
        """连接信号"""
        # 连接浏览器的JavaScript调用
        if self.web_view:
            self.web_view.page().javaScriptConsoleMessage.connect(
                self._handle_js_console
            )

    def _handle_js_console(self, level: int, message: str, line: int):
        """处理JS控制台消息"""
        # 可以将重要消息转发到Python日志
        if level >= 2:  # Error level
            print(f"JS Error: {message} at line {line}")

    async def evaluate_js(self, script: str):
        """在浏览器中执行JS"""
        if self.web_view:
            await self.web_view.page().runJavaScript(script)


# 需要添加Enum导入
from enum import Enum