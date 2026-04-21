"""
NodeRPC - MessagePack RPC会话层
===============================

基于MessagePack的RPC协议实现：
- 请求/响应模式
- 消息路由
- 方法注册与调用

Author: LivingTreeAI Community
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import asyncio
import logging
import msgpack
import uuid

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"


@dataclass
class RPCRequest:
    """RPC请求"""
    method: str
    params: List[Any]
    request_id: int
    msgpackrpc_version: int = 2

    def to_bytes(self) -> bytes:
        return msgpack.packb({
            "msgpackrpc_version": self.msgpackrpc_version,
            "method": self.method,
            "params": self.params,
            "request_id": self.request_id,
        })

    @classmethod
    def from_bytes(cls, data: bytes) -> "RPCRequest":
        unpacked = msgpack.unpackb(data, raw=False)
        return cls(
            msgpackrpc_version=unpacked.get("msgpackrpc_version", 2),
            method=unpacked["method"],
            params=unpacked.get("params", []),
            request_id=unpacked["request_id"],
        )


@dataclass
class RPCResponse:
    """RPC响应"""
    result: Any = None
    error: Any = None
    request_id: int
    msgpackrpc_version: int = 2

    def to_bytes(self) -> bytes:
        return msgpack.packb({
            "msgpackrpc_version": self.msgpackrpc_version,
            "result": self.result,
            "error": self.error,
            "request_id": self.request_id,
        })

    @classmethod
    def from_bytes(cls, data: bytes) -> "RPCResponse":
        unpacked = msgpack.unpackb(data, raw=False)
        return cls(
            msgpackrpc_version=unpacked.get("msgpackrpc_version", 2),
            result=unpacked.get("result"),
            error=unpacked.get("error"),
            request_id=unpacked["request_id"],
        )


class RPCError(Exception):
    """RPC错误"""
    def __init__(self, message: str, code: int = -1):
        self.message = message
        self.code = code
        super().__init__(message)


class NodeRPCServer:
    """
    RPC服务器

    功能：
    - 注册RPC方法
    - 处理传入消息
    - 返回RPC响应
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._methods: Dict[str, Callable] = {}
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._listeners: List[Callable] = []

        # 注册内置方法
        self._register_builtin_methods()

        logger.info(f"RPCServer 初始化: node_id={node_id}")

    def _register_builtin_methods(self):
        """注册内置方法"""
        self._methods["ping"] = self._handle_ping
        self._methods["node_info"] = self._handle_node_info
        self._methods["list_methods"] = self._handle_list_methods

    def register_method(self, name: str, handler: Callable):
        """注册RPC方法"""
        self._methods[name] = handler
        logger.debug(f"注册RPC方法: {name}")

    def unregister_method(self, name: str):
        """注销RPC方法"""
        if name in self._methods and name not in ["ping", "node_info", "list_methods"]:
            del self._methods[name]

    async def handle_message(self, raw_data: bytes, sender_id: str = None) -> Optional[bytes]:
        """
        处理传入的RPC消息

        Args:
            raw_data: 原始消息数据
            sender_id: 发送者ID

        Returns:
            响应数据（如果是请求），否则返回None
        """
        try:
            unpacked = msgpack.unpackb(raw_data, raw=False)

            # 判断是请求还是响应
            if "method" in unpacked:
                # RPC请求
                request = RPCRequest(
                    method=unpacked["method"],
                    params=unpacked.get("params", []),
                    request_id=unpacked["request_id"],
                )

                result = await self.execute_method(request)

                response = RPCResponse(
                    result=result,
                    request_id=request.request_id,
                )

                return response.to_bytes()

            else:
                # RPC响应
                response = RPCResponse(
                    result=unpacked.get("result"),
                    error=unpacked.get("error"),
                    request_id=unpacked["request_id"],
                )

                # 找到对应的Future并设置结果
                if response.request_id in self._pending_requests:
                    future = self._pending_requests.pop(response.request_id)
                    future.set_result(response)

                return None

        except Exception as e:
            logger.error(f"处理RPC消息错误: {e}")
            return None

    async def execute_method(self, request: RPCRequest) -> Any:
        """执行RPC方法"""
        method_name = request.method
        params = request.params

        if method_name not in self._methods:
            raise RPCError(f"未知方法: {method_name}", -32601)

        handler = self._methods[method_name]

        try:
            # 支持异步和同步方法
            if asyncio.iscoroutinefunction(handler):
                return await handler(*params)
            else:
                return handler(*params)

        except Exception as e:
            logger.error(f"RPC方法执行错误: {method_name} - {e}")
            raise RPCError(str(e), -32603)

    # ==================== 内置方法 ====================

    async def _handle_ping(self) -> Dict:
        """ping方法"""
        return {
            "pong": True,
            "timestamp": datetime.now().isoformat(),
            "node_id": self.node_id,
        }

    async def _handle_node_info(self) -> Dict:
        """返回节点信息"""
        return {
            "node_id": self.node_id,
            "methods": list(self._methods.keys()),
            "timestamp": datetime.now().isoformat(),
        }

    async def _handle_list_methods(self) -> List[str]:
        """列出所有可用方法"""
        return list(self._methods.keys())

    # ==================== 事件监听 ====================

    def subscribe(self, callback: Callable):
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)

    def _notify_listeners(self, event: str, data: Any):
        for listener in self._listeners:
            try:
                listener(event, data)
            except Exception as e:
                logger.error(f"监听器回调错误: {e}")


class NodeRPCClient:
    """
    RPC客户端

    功能：
    - 发起RPC调用
    - 处理RPC响应
    - 支持异步调用
    """

    def __init__(self, node_id: str, send_func: Callable):
        """
        初始化RPC客户端

        Args:
            node_id: 本节点ID
            send_func: 发送数据的函数，签名: async def send_func(node_id: str, data: bytes) -> int
        """
        self.node_id = node_id
        self._send_func = send_func
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._request_counter = 0
        self._lock = asyncio.Lock()

        logger.info(f"RPCClient 初始化: node_id={node_id}")

    async def call(self, target_node: str, method: str, *params, timeout: float = 30.0) -> Any:
        """
        发起RPC调用

        Args:
            target_node: 目标节点ID
            method: 方法名
            params: 方法参数
            timeout: 超时时间（秒）

        Returns:
            方法返回值

        Raises:
            RPCError: RPC执行错误
            asyncio.TimeoutError: 调用超时
        """
        async with self._lock:
            self._request_counter += 1
            request_id = self._request_counter

        # 创建Future
        future = asyncio.Future()
        self._pending_requests[request_id] = future

        # 发送请求
        request = RPCRequest(
            method=method,
            params=list(params),
            request_id=request_id,
        )

        try:
            data = request.to_bytes()
            await self._send_func(target_node, data)

            # 等待响应
            response = await asyncio.wait_for(future, timeout=timeout)

            if response.error is not None:
                raise RPCError(str(response.error))

            return response.result

        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise

        except Exception as e:
            self._pending_requests.pop(request_id, None)
            raise

    async def notify(self, target_node: str, method: str, *params):
        """
        发送通知（不需要响应）

        Args:
            target_node: 目标节点ID
            method: 方法名
            params: 方法参数
        """
        request = RPCRequest(
            method=method,
            params=list(params),
            request_id=0,  # 通知的request_id为0
        )

        data = request.to_bytes()
        await self._send_func(target_node, data)

    async def handle_response(self, raw_data: bytes):
        """处理收到的响应数据"""
        try:
            response = RPCResponse.from_bytes(raw_data)

            if response.request_id in self._pending_requests:
                future = self._pending_requests.pop(response.request_id)
                future.set_result(response)

        except Exception as e:
            logger.error(f"处理RPC响应错误: {e}")


class MessageRouter:
    """
    消息路由器

    功能：
    - 路由消息到对应的处理函数
    - 支持多节点消息转发
    """

    def __init__(self, rpc_server: NodeRPCServer):
        self.rpc_server = rpc_server
        self._routes: Dict[str, str] = {}  # prefix -> target_node

    def add_route(self, prefix: str, target_node: str):
        """添加路由规则"""
        self._routes[prefix] = target_node

    def remove_route(self, prefix: str):
        """移除路由规则"""
        self._routes.pop(prefix, None)

    async def route_message(self, raw_data: bytes, sender_id: str, send_func: Callable) -> bool:
        """
        路由消息

        Args:
            raw_data: 原始消息数据
            sender_id: 发送者ID
            send_func: 发送函数

        Returns:
            消息是否被路由
        """
        try:
            unpacked = msgpack.unpackb(raw_data, raw=False)

            if "method" not in unpacked:
                return False

            method = unpacked.get("method", "")

            # 检查是否有匹配的路由
            for prefix, target_node in self._routes.items():
                if method.startswith(prefix):
                    # 转发到目标节点
                    await send_func(target_node, raw_data)
                    return True

            return False

        except Exception as e:
            logger.error(f"路由消息错误: {e}")
            return False


# 单例实例
_rpc_server: Optional[NodeRPCServer] = None


def get_rpc_server(node_id: str = None) -> NodeRPCServer:
    global _rpc_server
    if _rpc_server is None:
        _rpc_server = NodeRPCServer(node_id=node_id or "anonymous")
    return _rpc_server