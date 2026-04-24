"""
统一 API 客户端
================

三端统一的 API 客户端，支持桌面/Web/移动端

架构:
- REST API (同步请求)
- WebSocket (实时通信)
- SSE (服务端推送)
"""

import json
import time
import asyncio
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import threading


class ClientType(Enum):
    """客户端类型"""
    DESKTOP = "desktop"
    WEB = "web"
    MOBILE = "mobile"


@dataclass
class APIConfig:
    """API 配置"""
    base_url: str = "http://localhost:8000"
    ws_url: str = "ws://localhost:8000"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    client_type: ClientType = ClientType.DESKTOP


@dataclass
class APIResponse:
    """API 响应"""
    success: bool
    data: Any = None
    error: str = ""
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)


class UnifiedAPIClient:
    """
    统一 API 客户端

    支持:
    - REST API 调用
    - WebSocket 实时通信
    - 自动重试
    - 离线队列
    """

    def __init__(self, config: APIConfig = None):
        self.config = config or APIConfig()
        self._ws: Optional[Any] = None
        self._ws_connected = False
        self._listeners: Dict[str, List[Callable]] = {}
        self._request_lock = threading.Lock()
        self._offline_queue: List[Dict] = []
        self._is_online = True

    # ==================== REST API ====================

    async def get(self, path: str, params: Dict = None) -> APIResponse:
        """GET 请求"""
        return await self._request("GET", path, params=params)

    async def post(self, path: str, data: Dict = None) -> APIResponse:
        """POST 请求"""
        return await self._request("POST", path, data=data)

    async def put(self, path: str, data: Dict = None) -> APIResponse:
        """PUT 请求"""
        return await self._request("PUT", path, data=data)

    async def delete(self, path: str) -> APIResponse:
        """DELETE 请求"""
        return await self._request("DELETE", path)

    async def _request(
        self,
        method: str,
        path: str,
        params: Dict = None,
        data: Dict = None,
        retry_count: int = 0
    ) -> APIResponse:
        """执行 HTTP 请求"""
        import urllib.request
        import urllib.error

        url = f"{self.config.base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "X-Client-Type": self.config.client_type.value,
        }

        try:
            # 构造请求
            if method == "GET" and params:
                query = "&".join([f"{k}={v}" for k, v in params.items()])
                url = f"{url}?{query}" if query else url
                req_data = None
            elif data:
                req_data = json.dumps(data).encode("utf-8")
            else:
                req_data = None

            req = urllib.request.Request(
                url,
                data=req_data,
                headers=headers,
                method=method
            )

            # 执行请求
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                response_data = resp.read().decode("utf-8")
                try:
                    result = json.loads(response_data)
                except json.JSONDecodeError:
                    result = response_data

                return APIResponse(
                    success=True,
                    data=result,
                    status_code=resp.status,
                    headers=dict(resp.headers)
                )

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            return APIResponse(
                success=False,
                error=f"HTTP {e.code}: {error_body}",
                status_code=e.code
            )

        except urllib.error.URLError as e:
            # 网络错误，尝试重试
            if retry_count < self.config.max_retries:
                await asyncio.sleep(self.config.retry_delay)
                return await self._request(
                    method, path, params, data, retry_count + 1
                )
            return APIResponse(
                success=False,
                error=f"Network error: {e.reason}",
                status_code=0
            )

        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0
            )

    # ==================== WebSocket ====================

    async def connect_websocket(self, path: str = "/ws/v1/chat") -> bool:
        """连接 WebSocket"""
        import websocket

        url = f"{self.config.ws_url}{path}"

        def on_message(ws, message):
            try:
                data = json.loads(message)
                msg_type = data.get("type", "")
                if msg_type in self._listeners:
                    for callback in self._listeners[msg_type]:
                        asyncio.create_task(callback(data))
            except Exception as e:
                logger.info(f"WebSocket message error: {e}")

        def on_error(ws, error):
            logger.info(f"WebSocket error: {error}")
            self._ws_connected = False

        def on_close(ws, close_status_code, close_msg):
            self._ws_connected = False

        def on_open(ws):
            self._ws_connected = True

        try:
            self._ws = websocket.WebSocketApp(
                url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )

            # 在新线程中运行
            thread = threading.Thread(target=self._ws.run_forever)
            thread.daemon = True
            thread.start()

            # 等待连接建立
            for _ in range(50):  # 5秒超时
                if self._ws_connected:
                    return True
                await asyncio.sleep(0.1)

            return False

        except Exception as e:
            logger.info(f"WebSocket connection error: {e}")
            return False

    async def disconnect_websocket(self):
        """断开 WebSocket"""
        if self._ws:
            self._ws.close()
            self._ws = None
            self._ws_connected = False

    def add_listener(self, event_type: str, callback: Callable):
        """添加事件监听器"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def remove_listener(self, event_type: str, callback: Callable):
        """移除事件监听器"""
        if event_type in self._listeners:
            self._listeners[event_type].remove(callback)

    async def ws_send(self, data: Dict) -> bool:
        """发送 WebSocket 消息"""
        if not self._ws or not self._ws_connected:
            return False
        try:
            self._ws.send(json.dumps(data))
            return True
        except Exception as e:
            logger.info(f"WebSocket send error: {e}")
            return False

    # ==================== 离线支持 ====================

    async def queue_offline_request(self, method: str, path: str, data: Dict = None):
        """队列化离线请求"""
        self._offline_queue.append({
            "method": method,
            "path": path,
            "data": data,
            "timestamp": time.time()
        })

    async def sync_offline_queue(self):
        """同步离线队列"""
        if not self._is_online or not self._offline_queue:
            return

        failed_requests = []
        for request in self._offline_queue:
            method = request["method"]
            path = request["path"]
            data = request["data"]

            response = await self._request(method, path, data=data)
            if not response.success:
                failed_requests.append(request)

        self._offline_queue = failed_requests

    def set_online_status(self, is_online: bool):
        """设置在线状态"""
        self._is_online = is_online
        if is_online:
            asyncio.create_task(self.sync_offline_queue())


# ==================== 业务 API ====================

class HermesAPI(UnifiedAPIClient):
    """
    Hermes 业务 API

    提供与桌面端一致的 API 接口
    """

    def __init__(self, config: APIConfig = None):
        super().__init__(config)

    # ==================== 聊天 ====================

    async def chat(self, message: str, session_id: str = None) -> APIResponse:
        """
        发送聊天消息

        Args:
            message: 消息内容
            session_id: 会话 ID

        Returns:
            APIResponse with chat response
        """
        data = {
            "message": message,
            "session_id": session_id or "",
        }
        return await self.post("/api/v1/chat/completions", data)

    async def get_chat_history(self, session_id: str, limit: int = 50) -> APIResponse:
        """获取聊天历史"""
        return await self.get(
            f"/api/v1/chat/history/{session_id}",
            params={"limit": limit}
        )

    # ==================== 记忆 ====================

    async def search_memory(self, query: str, limit: int = 10) -> APIResponse:
        """
        搜索记忆

        Args:
            query: 搜索查询
            limit: 返回数量

        Returns:
            APIResponse with memory results
        """
        return await self.get(
            "/api/v1/memory/search",
            params={"query": query, "limit": limit}
        )

    async def store_memory(
        self,
        content: str,
        memory_type: str = "permanent",
        metadata: Dict = None
    ) -> APIResponse:
        """
        存储记忆

        Args:
            content: 记忆内容
            memory_type: 记忆类型 (permanent/session/working)
            metadata: 元数据

        Returns:
            APIResponse with stored memory ID
        """
        data = {
            "content": content,
            "memory_type": memory_type,
            "metadata": metadata or {}
        }
        return await self.post("/api/v1/memory/store", data)

    async def forget_memory(self, memory_id: str) -> APIResponse:
        """删除记忆"""
        return await self.delete(f"/api/v1/memory/{memory_id}")

    # ==================== 技能 ====================

    async def list_skills(self, category: str = None) -> APIResponse:
        """获取技能列表"""
        params = {"category": category} if category else {}
        return await self.get("/api/v1/skills/list", params)

    async def execute_skill(
        self,
        skill_id: str,
        params: Dict = None,
        stream: bool = False
    ) -> APIResponse:
        """
        执行技能

        Args:
            skill_id: 技能 ID
            params: 技能参数
            stream: 是否流式输出

        Returns:
            APIResponse with skill execution result
        """
        data = {
            "skill_id": skill_id,
            "params": params or {},
            "stream": stream
        }
        return await self.post("/api/v1/skills/execute", data)

    # ==================== 文件 ====================

    async def upload_file(
        self,
        file_path: str,
        category: str = "general"
    ) -> APIResponse:
        """
        上传文件

        Args:
            file_path: 文件路径
            category: 文件分类

        Returns:
            APIResponse with file ID
        """
        import mimetypes

        mime_type, _ = mimetypes.guess_type(file_path)
        filename = file_path.split("/")[-1].split("\\")[-1]

        with open(file_path, "rb") as f:
            import base64
            content = base64.b64encode(f.read()).decode()

        data = {
            "filename": filename,
            "mime_type": mime_type or "application/octet-stream",
            "category": category,
            "content": content
        }
        return await self.post("/api/v1/upload", data)

    async def download_file(self, file_id: str, save_path: str) -> APIResponse:
        """下载文件"""
        response = await self.get(f"/api/v1/files/{file_id}")
        if response.success and response.data:
            with open(save_path, "wb") as f:
                import base64
from core.logger import get_logger
logger = get_logger('unified_api')

                f.write(base64.b64decode(response.data["content"]))
        return response

    # ==================== 系统 ====================

    async def get_status(self) -> APIResponse:
        """获取系统状态"""
        return await self.get("/api/v1/status")

    async def get_health(self) -> APIResponse:
        """健康检查"""
        return await self.get("/api/v1/health")


# ==================== 单例全局实例 ====================

_global_client: Optional[HermesAPI] = None


def get_hermes_api(config: APIConfig = None) -> HermesAPI:
    """获取全局 API 客户端实例"""
    global _global_client
    if _global_client is None:
        _global_client = HermesAPI(config)
    return _global_client
