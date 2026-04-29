"""
RPC 注入器 (RPC Injector)
=========================

向网页注入 window.hyperos 对象，实现双向通信

注入能力：
- getNodeStatus(): 获取节点状态
- sendMail(): 发送邮件
- getMails(): 获取邮件
- search(): 统一搜索
- open(): 打开内部内容
- publishToForum(): 发布到论坛
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import hashlib


@dataclass
class RPCMethod:
    """RPC 方法定义"""
    name: str
    handler: Callable
    description: str = ""
    params: list[str] = field(default_factory=list)


class RPCInjector:
    """
    RPC 注入器

    为浏览器网页生成并注入 window.hyperos 对象
    """

    def __init__(self, gateway: "BrowserGateway"):
        self.gateway = gateway
        self._methods: dict[str, RPCMethod] = {}

        # 注册内置方法
        self._register_builtin_methods()

    def _register_builtin_methods(self):
        """注册内置方法"""
        self.register_method(RPCMethod(
            name="getNodeStatus",
            handler=self._handle_get_node_status,
            description="获取当前节点状态"
        ))

        self.register_method(RPCMethod(
            name="sendMail",
            handler=self._handle_send_mail,
            description="发送内部邮件",
            params=["to", "subject", "content", "attachments"]
        ))

        self.register_method(RPCMethod(
            name="getMails",
            handler=self._handle_get_mails,
            description="获取邮件列表",
            params=["limit", "unreadOnly"]
        ))

        self.register_method(RPCMethod(
            name="search",
            handler=self._handle_search,
            description="统一搜索",
            params=["query", "sources"]
        ))

        self.register_method(RPCMethod(
            name="getRuntimeInfo",
            handler=self._handle_get_runtime_info,
            description="获取运行时信息"
        ))

        self.register_method(RPCMethod(
            name="open",
            handler=self._handle_open,
            description="打开内部内容",
            params=["url"]
        ))

        self.register_method(RPCMethod(
            name="publishToForum",
            handler=self._handle_publish_to_forum,
            description="发布到内部论坛",
            params=["title", "content", "tags"]
        ))

    def register_method(self, method: RPCMethod):
        """注册 RPC 方法"""
        self._methods[method.name] = method

    async def handle_rpc_call(
        self,
        method: str,
        params: dict[str, Any]
    ) -> dict[str, Any]:
        """处理 RPC 调用"""
        if method not in self._methods:
            return {"success": False, "error": f"Unknown method: {method}"}

        try:
            handler = self._methods[method].handler
            result = await handler(**params) if asyncio_iscoro(handler) else handler(**params)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== 内置方法实现 ==========

    def _handle_get_node_status(self) -> dict[str, Any]:
        """获取节点状态"""
        if self.gateway.runtime:
            return self.gateway.runtime.get_status()
        return {"mode": "offline"}

    def _handle_send_mail(
        self,
        to: str,
        subject: str,
        content: str,
        attachments: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """发送邮件"""
        if self.gateway.runtime:
            return asyncio.run(
                self.gateway.runtime.send_mail(to, subject, content, attachments)
            )
        return {"success": False, "error": "Runtime not available"}

    def _handle_get_mails(
        self,
        limit: int = 20,
        unread_only: bool = False
    ) -> list[dict[str, Any]]:
        """获取邮件"""
        # TODO: 调用实际邮件系统
        return []

    def _handle_search(
        self,
        query: str,
        sources: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """统一搜索"""
        return {
            "query": query,
            "sources": sources or ["all"],
            "results": []
        }

    def _handle_get_runtime_info(self) -> dict[str, Any]:
        """获取运行时信息"""
        if self.gateway.runtime:
            return self.gateway.runtime.get_runtime_info()
        return {"mode": "offline"}

    def _handle_open(self, url: str) -> dict[str, Any]:
        """打开内部内容"""
        return {"url": url, "opened": True}

    def _handle_publish_to_forum(
        self,
        title: str,
        content: str,
        tags: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """发布到论坛"""
        # TODO: 调用实际论坛系统
        return {
            "success": True,
            "post_id": hashlib.md5(title.encode()).hexdigest()[:8],
            "title": title
        }


def asyncio_iscoro(func) -> bool:
    """检查是否为异步函数"""
    import asyncio
    return asyncio.iscoroutinefunction(func)


def inject_window_hyperos(gateway: "BrowserGateway") -> str:
    """
    生成注入脚本

    Returns:
        要注入到网页的 JavaScript 代码
    """
    return f"""
(function() {{
    // HyperOS Browser Gateway - Window Hyperos Injection
    // Version: 1.0.0

    const HyperOS = {{
        version: "1.0.0",
        gateway: "browser_gateway",
        rpcEndpoint: "hyperos://rpc",

        // RPC 基础调用
        async function rpc(method, params = {{}}) {{
            const requestId = Math.random().toString(36).substring(2, 11);
            try {{
                // 通过协议调用
                const result = await this._callProtocol(method, params, requestId);
                return result;
            }} catch (error) {{
                console.error("[HyperOS] RPC Error:", error);
                return {{ success: false, error: error.message }};
            }}
        }},

        // 协议调用（通过隐藏 iframe）
        async _callProtocol(method, params, requestId) {{
            return new Promise((resolve, reject) => {{
                const uri = this._buildURI(method, params);
                // 创建隐藏的 iframe 发起请求
                const iframe = document.createElement("iframe");
                iframe.style.display = "none";
                iframe.id = "hyperos_rpc_frame_" + requestId;

                // 监听消息
                window.addEventListener("message", function handler(event) {{
                    if (event.data && event.data.requestId === requestId) {{
                        window.removeEventListener("message", handler);
                        resolve(event.data);
                        setTimeout(() => iframe.remove(), 100);
                    }}
                }});

                iframe.src = uri;
                document.body.appendChild(iframe);

                // 超时处理
                setTimeout(() => {{
                    window.removeEventListener("message", handler);
                    reject(new Error("RPC timeout"));
                    iframe.remove();
                }}, 5000);
            }});
        }},

        // 构建 URI
        _buildURI(method, params) {{
            let uri = "hyperos://rpc/" + method;
            const queryParams = Object.entries(params)
                .map(([k, v]) => k + "=" + encodeURIComponent(JSON.stringify(v)))
                .join("&");
            if (queryParams) uri += "?" + queryParams;
            return uri;
        }},

        // ========== API 方法 ==========

        // 获取节点状态
        getNodeStatus: function() {{
            return this.rpc("getNodeStatus");
        }},

        // 获取运行时信息
        getRuntimeInfo: function() {{
            return this.rpc("getRuntimeInfo");
        }},

        // 发送邮件
        sendMail: function(to, subject, content, attachments) {{
            return this.rpc("sendMail", {{
                to: to,
                subject: subject || "",
                content: content || "",
                attachments: attachments || []
            }});
        }},

        // 获取邮件列表
        getMails: function(limit, unreadOnly) {{
            return this.rpc("getMails", {{
                limit: limit || 20,
                unreadOnly: unreadOnly || false
            }});
        }},

        // 统一搜索
        search: function(query, sources) {{
            return this.rpc("search", {{
                query: query,
                sources: sources || ["all"]
            }});
        }},

        // 打开内部内容
        open: function(url) {{
            window.location.href = url;
        }},

        // 发布到论坛
        publishToForum: function(title, content, tags) {{
            return this.rpc("publishToForum", {{
                title: title,
                content: content,
                tags: tags || []
            }});
        }},

        // 打开节点详情
        openNode: function(nodeId) {{
            this.open("hyperos://node/" + nodeId + "/info");
        }},

        // 打开邮件
        openMail: function(messageId) {{
            this.open("hyperos://mail/read/" + messageId);
        }},

        // 打开内容
        openContent: function(contentId) {{
            this.open("hyperos://content/" + contentId);
        }},

        // 打开 CID
        openCID: function(cid) {{
            this.open("hyperos://cid/" + cid);
        }}
    }};

    // 导出到全局
    window.hyperos = HyperOS;

    // 协议处理器扩展
    window.hyperosProtocol = {{
        register: function(protocol, handler) {{
            console.log("[HyperOS] Registering protocol handler:", protocol);
        }}
    }};

    // 初始化完成
    console.log("[HyperOS] Browser Gateway injected successfully");
    console.log("[HyperOS] Version:", HyperOS.version);
    console.log("[HyperOS] Try: hyperos.getNodeStatus()");

    // 可选：自动检测页面中的 hyperos:// 链接并增强
    if (document.readyState === "loading") {{
        document.addEventListener("DOMContentLoaded", function() {{
            enhanceHyperOSLinks();
        }});
    }} else {{
        enhanceHyperOSLinks();
    }}

    function enhanceHyperOSLinks() {{
        const links = document.querySelectorAll('a[href^="hyperos://"]');
        links.forEach(function(link) {{
            link.target = "_self";
            link.classList.add("hyperos-link");
        }});
    }}
}})();
"""