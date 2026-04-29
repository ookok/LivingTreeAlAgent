"""
CDP Helper - Chrome DevTools Protocol 辅助函数
=================================================

通过 CDP (Chrome DevTools Protocol) 与 Chrome 通信，
实现会话复用、JS 注入、反检测等功能。

核心原理：
1. Chrome 以 --remote-debugging-port=9222 启动（或由用户手动启动）
2. 通过 http://localhost:9222/json 获取可用页面列表
3. 通过 WebSocket 连接到页面的 webSocketDebuggerUrl
4. 发送 CDP 命令（JSON-RPC 格式）控制页面
"""

import json
import requests
import websockets
import asyncio
from typing import Optional, Dict, List, Any, Callable
from loguru import logger
from dataclasses import dataclass, field


@dataclass
class CDPPage:
    """CDP 页面信息"""
    id: str
    title: str
    url: str
    web_socket_url: str
    type: str = "page"

    @classmethod
    def from_json(cls, data: Dict) -> "CDPPage":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            url=data.get("url", ""),
            web_socket_url=data.get("webSocketDebuggerUrl", ""),
            type=data.get("type", "page")
        )


class CDPHelper:
    """
    CDP 协议辅助类

    提供 Chrome DevTools Protocol 的底层通信能力，
    包括页面发现、WebSocket 连接、命令发送等。
    """

    def __init__(self, debug_port: int = 9222):
        """
        初始化 CDP 辅助器

        Args:
            debug_port: Chrome 远程调试端口（默认 9222）
        """
        self.debug_port = debug_port
        self._base_url = f"http://localhost:{debug_port}"
        self._ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._cmd_id = 0
        self._loop = None

    # ============================================================
    # 页面发现
    # ============================================================

    def discover_pages(self) -> List[CDPPage]:
        """
        发现所有可用的 Chrome 页面

        Returns:
            CDPPage 列表

        Raises:
            ConnectionError: 无法连接到 Chrome（未启动或端口不对）
        """
        try:
            resp = requests.get(f"{self._base_url}/json", timeout=3)
            resp.raise_for_status()
            pages_data = resp.json()
            return [CDPPage.from_json(p) for p in pages_data if p.get("type") == "page"]
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"无法连接到 Chrome (localhost:{self.debug_port})。"
                f"请确保 Chrome 已启动并开启远程调试：\n"
                f"  chrome.exe --remote-debugging-port={self.debug_port}"
            )
        except Exception as e:
            raise RuntimeError(f"发现 Chrome 页面失败: {e}")

    def discover_version(self) -> Dict[str, Any]:
        """
        获取 Chrome 版本信息

        Returns:
            版本信息字典（包含 browser、webSocketDebuggerUrl 等）
        """
        try:
            resp = requests.get(f"{self._base_url}/json/version", timeout=3)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"获取 Chrome 版本信息失败: {e}")
            return {}

    def get_page_by_url(self, url_pattern: str) -> Optional[CDPPage]:
        """
        根据 URL 模式查找页面

        Args:
            url_pattern: URL 模式（支持部分匹配）

        Returns:
            匹配的 CDPPage，未找到返回 None
        """
        pages = self.discover_pages()
        for page in pages:
            if url_pattern in page.url:
                return page
        return None

    def get_or_create_page(self, target_url: str) -> CDPPage:
        """
        获取或创建页面

        Args:
            target_url: 目标 URL

        Returns:
            CDPPage 对象
        """
        # 先查找是否已有该 URL 的页面
        existing = self.get_page_by_url(target_url)
        if existing:
            return existing

        # 创建新标签页
        try:
            resp = requests.get(f"{self._base_url}/json/new?{target_url}", timeout=5)
            resp.raise_for_status()
            return CDPPage.from_json(resp.json())
        except Exception as e:
            raise RuntimeError(f"创建新标签页失败: {e}")

    # ============================================================
    # WebSocket CDP 通信（异步）
    # ============================================================

    async def connect_page(self, page: CDPPage) -> str:
        """
        连接到页面 WebSocket

        Args:
            page: CDPPage 对象

        Returns:
            连接 ID（用于后续发送命令）
        """
        if page.id in self._ws_connections:
            return page.id

        ws_url = page.web_socket_url
        if not ws_url:
            raise ValueError(f"页面 {page.id} 没有 webSocketDebuggerUrl")

        ws = await websockets.connect(ws_url)
        self._ws_connections[page.id] = ws
        return page.id

    async def disconnect_page(self, page_id: str):
        """断开页面连接"""
        if page_id in self._ws_connections:
            await self._ws_connections[page_id].close()
            del self._ws_connections[page_id]

    async def send_cdp_command(
        self,
        page_id: str,
        method: str,
        params: Dict[str, Any] = None,
        timeout: float = 10.0
    ) -> Dict[str, Any]:
        """
        发送 CDP 命令

        Args:
            page_id: 页面 ID
            method: CDP 方法名（如 "Runtime.evaluate"）
            params: 方法参数
            timeout: 超时时间（秒）

        Returns:
            CDP 响应结果
        """
        if page_id not in self._ws_connections:
            raise ValueError(f"页面 {page_id} 未连接，请先调用 connect_page()")

        self._cmd_id += 1
        cmd_id = self._cmd_id

        message = {
            "id": cmd_id,
            "method": method,
        }
        if params:
            message["params"] = params

        ws = self._ws_connections[page_id]
        await ws.send(json.dumps(message))

        # 等待响应
        try:
            while True:
                response_raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                response = json.loads(response_raw)

                if response.get("id") == cmd_id:
                    return response
                # 处理事件（非响应）
                elif "method" in response:
                    self._handle_cdp_event(response)
        except asyncio.TimeoutError:
            raise TimeoutError(f"CDP 命令 {method} 超时（{timeout}s）")

    async def send_cdp_command_batch(
        self,
        page_id: str,
        commands: List[Dict[str, Any]],
        timeout: float = 15.0
    ) -> List[Dict[str, Any]]:
        """
        批量发送 CDP 命令（性能优化）

        Args:
            page_id: 页面 ID
            commands: 命令列表，每个元素为 {"method": "...", "params": {...}}
            timeout: 超时时间（秒）

        Returns:
            响应列表（按发送顺序）
        """
        if page_id not in self._ws_connections:
            raise ValueError(f"页面 {page_id} 未连接")

        self._cmd_id += 1
        base_id = self._cmd_id
        messages = []
        for i, cmd in enumerate(commands):
            msg = {"id": base_id + i, "method": cmd["method"]}
            if "params" in cmd:
                msg["params"] = cmd["params"]
            messages.append(msg)

        ws = self._ws_connections[page_id]
        for msg in messages:
            await ws.send(json.dumps(msg))

        # 收集响应
        results = [None] * len(messages)
        try:
            while None in results:
                response_raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                response = json.loads(response_raw)
                if "id" in response:
                    idx = response["id"] - base_id
                    if 0 <= idx < len(results):
                        results[idx] = response
                elif "method" in response:
                    self._handle_cdp_event(response)
        except asyncio.TimeoutError:
            pass

        return [r if r is not None else {"error": "timeout"} for r in results]

    # ============================================================
    # 高级封装：页面操作
    # ============================================================

    async def navigate(self, page_id: str, url: str, timeout: float = 15.0):
        """导航到指定 URL"""
        return await self.send_cdp_command(
            page_id, "Page.navigate", {"url": url}, timeout=timeout
        )

    async def evaluate(self, page_id: str, expression: str, timeout: float = 10.0) -> Any:
        """
        在页面中执行 JavaScript

        Returns:
            JS 执行结果（Python 对象）
        """
        result = await self.send_cdp_command(
            page_id,
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
            timeout=timeout
        )
        result_data = result.get("result", {})
        if "result" in result_data:
            return result_data["result"].get("value")
        if "exceptionDetails" in result_data:
            raise RuntimeError(f"JS 执行异常: {result_data['exceptionDetails']}")
        return None

    async def evaluate_on_new_document(self, page_id: str, expression: str):
        """
        在页面加载前注入 JS（相当于 Playwright 的 add_init_script）

        通过 CDP Runtime.addBinding + Page.addScriptToEvaluateOnNewDocument 实现。
        """
        await self.send_cdp_command(
            page_id,
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": expression}
        )

    async def get_content(self, page_id: str) -> str:
        """获取页面 HTML 内容"""
        return await self.evaluate(
            page_id,
            "document.documentElement.outerHTML"
        )

    async def get_text(self, page_id: str) -> str:
        """获取页面文本内容（去除 HTML 标签）"""
        return await self.evaluate(
            page_id,
            "document.body.innerText"
        )

    async def take_screenshot(self, page_id: str, format: str = "png") -> bytes:
        """
        截图

        Args:
            page_id: 页面 ID
            format: 图片格式（"png" 或 "jpeg"）

        Returns:
            图片二进制数据（base64 解码后）
        """
        result = await self.send_cdp_command(
            page_id,
            "Page.captureScreenshot",
            {"format": format}
        )
        import base64
        return base64.b64decode(result.get("result", {}).get("data", ""))

    async def set_cookies(self, page_id: str, cookies: List[Dict]):
        """设置 Cookie（复用登录状态）"""
        for cookie in cookies:
            await self.send_cdp_command(
                page_id,
                "Network.setCookie",
                cookie
            )

    async def get_cookies(self, page_id: str, urls: List[str] = None) -> List[Dict]:
        """获取 Cookie"""
        params = {}
        if urls:
            params["urls"] = urls
        result = await self.send_cdp_command(
            page_id, "Network.getCookies", params
        )
        return result.get("result", {}).get("cookies", [])

    # ============================================================
    # 事件处理
    # ============================================================

    def _handle_cdp_event(self, event: Dict):
        """处理 CDP 事件"""
        method = event.get("method", "")
        handlers = self._event_handlers.get(method, [])
        for handler in handlers:
            try:
                handler(event.get("params", {}))
            except Exception as e:
                logger.error(f"CDP 事件处理失败 {method}: {e}")

    def register_event_handler(self, event_name: str, handler: Callable):
        """注册 CDP 事件处理器"""
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)

    def unregister_event_handler(self, event_name: str, handler: Callable):
        """取消注册 CDP 事件处理器"""
        if event_name in self._event_handlers:
            try:
                self._event_handlers[event_name].remove(handler)
            except ValueError:
                pass

    # ============================================================
    # 清理
    # ============================================================

    async def close_all(self):
        """关闭所有 WebSocket 连接"""
        for page_id in list(self._ws_connections.keys()):
            await self.disconnect_page(page_id)


# ============================================================
# 全局单例
# ============================================================

_cdp_helper_instance: Optional[CDPHelper] = None


def get_cdp_helper(debug_port: int = 9222) -> CDPHelper:
    """获取全局 CDPHelper 实例"""
    global _cdp_helper_instance
    if _cdp_helper_instance is None or _cdp_helper_instance.debug_port != debug_port:
        _cdp_helper_instance = CDPHelper(debug_port=debug_port)
    return _cdp_helper_instance
