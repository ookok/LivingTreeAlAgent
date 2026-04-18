"""
浏览器网关核心 (Browser Gateway Core)
=====================================

双向协议网关：
- 注册自定义协议 (hyperos://)
- 双向 RPC 桥接
- 协议处理器
"""

import asyncio
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

# 导入相关模块
from ..internal_mail import MailManager
from ..standalone import get_runtime, StandaloneRuntime


class ProtocolType(Enum):
    """协议类型"""
    HYPEROS = "hyperos"           # hyperos:// 内部协议
    HTTP = "http"                 # HTTP/HTTPS
    FILE = "file"                 # file:// 本地文件
    IPFS = "ipfs"                 # ipfs:// IPFS协议


@dataclass
class ProtocolHandler:
    """协议处理器"""
    protocol: str                  # 协议名 (如 "hyperos")
    handler: Callable              # 处理函数
    description: str = ""


@dataclass
class RPCRequest:
    """RPC 请求"""
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None


@dataclass
class RPCResponse:
    """RPC 响应"""
    success: bool
    result: Any = None
    error: Optional[str] = None
    request_id: Optional[str] = None


class RPCBridge:
    """
    RPC 桥接器

    实现网页与客户端的双向通信
    """

    def __init__(self, gateway: "BrowserGateway"):
        self.gateway = gateway
        self._handlers: dict[str, Callable] = {}
        self._lock = threading.Lock()

    def register_handler(self, name: str, handler: Callable):
        """注册 RPC 处理函数"""
        with self._lock:
            self._handlers[name] = handler

    def handle_request(self, request: RPCRequest) -> RPCResponse:
        """处理 RPC 请求"""
        try:
            handler = self._handlers.get(request.method)
            if not handler:
                return RPCResponse(
                    success=False,
                    error=f"Unknown method: {request.method}",
                    request_id=request.request_id
                )

            # 执行处理函数
            result = handler(**request.params)
            return RPCResponse(
                success=True,
                result=result,
                request_id=request.request_id
            )

        except Exception as e:
            return RPCResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )

    async def handle_request_async(self, request: RPCRequest) -> RPCResponse:
        """异步处理 RPC 请求"""
        try:
            handler = self._handlers.get(request.method)
            if not handler:
                return RPCResponse(
                    success=False,
                    error=f"Unknown method: {request.method}",
                    request_id=request.request_id
                )

            # 异步执行
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**request.params)
            else:
                result = handler(**request.params)

            return RPCResponse(
                success=True,
                result=result,
                request_id=request.request_id
            )

        except Exception as e:
            return RPCResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )


class BrowserGateway:
    """
    浏览器网关

    核心功能：
    1. 管理协议处理器
    2. 处理 hyperos:// 等自定义协议
    3. 提供 RPC 桥接能力
    4. 管理离线镜像
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        runtime: Optional[StandaloneRuntime] = None
    ):
        self.data_dir = data_dir or Path.home() / ".hermes-desktop" / "browser_gateway"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.runtime = runtime or get_runtime()

        # 协议处理器
        self._protocols: dict[str, ProtocolHandler] = {}

        # RPC 桥接
        self.rpc = RPCBridge(self)

        # 离线镜像
        self._offline_mirror = None

        # CSS 重写器
        self._css_rewriter = None

        # 爬虫调度器
        self._crawler_dispatcher = None

        # 初始化内置协议
        self._init_builtin_protocols()

        # 注册内置 RPC 方法
        self._register_builtin_rpc()

    def _init_builtin_protocols(self):
        """初始化内置协议"""
        # hyperos:// 协议
        self.register_protocol(ProtocolHandler(
            protocol="hyperos",
            handler=self._handle_hyperos,
            description="HyperOS 内部协议，用于访问节点、邮件、内容等"
        ))

        # ipfs:// 协议
        self.register_protocol(ProtocolHandler(
            protocol="ipfs",
            handler=self._handle_ipfs,
            description="IPFS 协议，用于访问分布式内容"
        ))

    def _register_builtin_rpc(self):
        """注册内置 RPC 方法"""
        # 节点状态
        self.rpc.register_handler("getNodeStatus", self._rpc_get_node_status)

        # 发送邮件
        self.rpc.register_handler("sendMail", self._rpc_send_mail)

        # 获取邮件
        self.rpc.register_handler("getMails", self._rpc_get_mails)

        # 搜索内容
        self.rpc.register_handler("search", self._rpc_search)

        # 获取运行时信息
        self.rpc.register_handler("getRuntimeInfo", self._rpc_get_runtime_info)

    # ========== 内置 RPC 方法 ==========

    def _rpc_get_node_status(self) -> dict[str, Any]:
        """获取节点状态"""
        if self.runtime:
            return self.runtime.get_status()
        return {"status": "offline", "mode": "unknown"}

    def _rpc_send_mail(
        self,
        to: str,
        subject: str,
        content: str,
        attachments: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """发送邮件"""
        if self.runtime:
            return asyncio.run(self.runtime.send_mail(to, subject, content, attachments))
        return {"success": False, "error": "Runtime not available"}

    def _rpc_get_mails(
        self,
        limit: int = 20,
        unread_only: bool = False
    ) -> list[dict[str, Any]]:
        """获取邮件列表"""
        # 简化实现
        return []

    def _rpc_search(
        self,
        query: str,
        sources: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """统一搜索"""
        results = {
            "query": query,
            "sources": sources or ["all"],
            "results": []
        }

        # TODO: 实现统一搜索（邮件、文件、代码、知识库）
        return results

    def _rpc_get_runtime_info(self) -> dict[str, Any]:
        """获取运行时信息"""
        if self.runtime:
            return self.runtime.get_runtime_info()
        return {"mode": "offline"}

    # ========== 协议处理 ==========

    def register_protocol(self, handler: ProtocolHandler):
        """注册协议处理器"""
        self._protocols[handler.protocol] = handler

    async def handle_url(self, url: str) -> dict[str, Any]:
        """
        处理 URL

        根据协议类型分发到对应的处理器
        """
        # 解析协议
        if "://" in url:
            protocol = url.split("://")[0]
        else:
            protocol = "file"

        handler = self._protocols.get(protocol)
        if not handler:
            return {
                "success": False,
                "error": f"Unknown protocol: {protocol}",
                "url": url
            }

        try:
            result = await handler.handler(url)
            return {"success": True, "result": result, "protocol": protocol}
        except Exception as e:
            return {"success": False, "error": str(e), "protocol": protocol}

    async def _handle_hyperos(self, url: str) -> dict[str, Any]:
        """处理 hyperos:// 协议"""
        # 解析 URI
        from .hyperos_protocol import parse_hyperos_uri
        uri = parse_hyperos_uri(url)

        if not uri:
            return {"error": "Invalid hyperos:// URI"}

        # 根据路径分发
        path = uri.path
        if path.startswith("/node/"):
            # 节点相关
            node_id = path.split("/node/")[1].split("/")[0]
            return await self._handle_node_action(node_id, uri.action)
        elif path.startswith("/mail/"):
            # 邮件相关
            return await self._handle_mail_action(path, uri.action, uri.params)
        elif path.startswith("/content/"):
            # 内容相关
            content_id = path.split("/content/")[1]
            return await self._handle_content_action(content_id)
        elif path.startswith("/cid/"):
            # CID 相关
            cid = path.split("/cid/")[1]
            return await self._handle_cid(cid)

        return {"error": "Unknown path"}

    async def _handle_ipfs(self, url: str) -> dict[str, Any]:
        """处理 ipfs:// 协议"""
        # 提取 CID
        cid = url.replace("ipfs://", "")
        return await self._handle_cid(cid)

    async def _handle_node_action(self, node_id: str, action: str) -> dict[str, Any]:
        """处理节点操作"""
        return {
            "node_id": node_id,
            "action": action,
            "status": "online"  # TODO: 实际检查节点状态
        }

    async def _handle_mail_action(
        self,
        path: str,
        action: str,
        params: dict[str, Any]
    ) -> dict[str, Any]:
        """处理邮件操作"""
        # TODO: 调用内部邮件系统
        return {
            "path": path,
            "action": action,
            "params": params
        }

    async def _handle_content_action(self, content_id: str) -> dict[str, Any]:
        """处理内容操作"""
        return {
            "content_id": content_id,
            "found": True  # TODO: 实际查找内容
        }

    async def _handle_cid(self, cid: str) -> dict[str, Any]:
        """处理 CID 请求"""
        # 查找离线镜像
        if self._offline_mirror:
            snapshot = await self._offline_mirror.get_snapshot(cid)
            if snapshot:
                return {
                    "cid": cid,
                    "found": True,
                    "snapshot": snapshot
                }

        return {
            "cid": cid,
            "found": False,
            "error": "CID not found in local mirror"
        }

    # ========== JavaScript 注入 ==========

    def generate_injection_script(self) -> str:
        """
        生成注入脚本

        返回要注入到网页的 JavaScript 代码
        """
        return f"""
(function() {{
    // HyperOS Browser Gateway Injection
    window.hyperos = {{
        version: "1.0.0",
        gateway: "browser_gateway",

        // RPC 调用
        async function rpc(method, params = {{}}) {{
            const requestId = Math.random().toString(36).substr(2, 9);
            const response = await fetch("hyperos://rpc", {{
                method: "POST",
                headers: {{"Content-Type": "application/json"}},
                body: JSON.stringify({{method, params, requestId}})
            }});
            return response.json();
        }}

        // 节点状态
        getNodeStatus: function() {{
            return rpc("getNodeStatus");
        }},

        // 发送邮件
        sendMail: function(to, subject, content, attachments) {{
            return rpc("sendMail", {{to, subject, content, attachments}});
        }},

        // 获取邮件
        getMails: function(limit, unreadOnly) {{
            return rpc("getMails", {{limit, unreadOnly}});
        }},

        // 统一搜索
        search: function(query, sources) {{
            return rpc("search", {{query, sources}});
        }},

        // 获取运行时信息
        getRuntimeInfo: function() {{
            return rpc("getRuntimeInfo");
        }},

        // 打开内部内容
        open: function(url) {{
            window.location.href = url;
        }},

        // 发布到内部论坛
        publishToForum: function(title, content, tags) {{
            return rpc("publishToForum", {{title, content, tags}});
        }}
    }};

    // 协议处理器
    window.hyperosProtocol = {{
        register: function(protocol, handler) {{
            // 注册自定义协议处理器
        }}
    }};

    console.log("[HyperOS] Browser Gateway injected, version:", window.hyperos.version);
}})();
"""

    def get_protocols(self) -> list[dict[str, str]]:
        """获取已注册的协议列表"""
        return [
            {"protocol": p.protocol, "description": p.description}
            for p in self._protocols.values()
        ]

    def get_csp_header(self) -> str:
        """
        获取 Content Security Policy 头

        允许内联脚本和 hyperos:// 协议
        """
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "connect-src 'self' hyperos:// ipfs://; "
            "frame-src 'self' hyperos://; "
            "object-src 'self'; "
            "style-src 'self' 'unsafe-inline';"
        )


def create_browser_gateway(
    data_dir: Optional[Path] = None,
    runtime: Optional[StandaloneRuntime] = None
) -> BrowserGateway:
    """创建浏览器网关"""
    return BrowserGateway(data_dir=data_dir, runtime=runtime)