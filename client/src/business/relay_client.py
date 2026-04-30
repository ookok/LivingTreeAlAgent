"""
WebSocket 中继客户端 SDK
WebSocket Relay Client SDK

功能：
- 连接中继服务器
- 创建/加入/离开会话
- 消息发送与接收
- 心跳检测与自动重连
- 桌面端、移动端、网页端统一接口

支持环境：
- 桌面端：PyQt6 (Python)
- 移动端：Flutter/React Native
- 网页端：JavaScript/TypeScript

配置来源：NanochatConfig (client/src/business/nanochat_config.py)
"""

import os
import json
import time
import asyncio
import logging
import threading
import uuid
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum

from business.nanochat_config import config

# WebSocket support
try:
    import websockets
    from websockets.client import connect, WebSocket
    from websockets.exceptions import ConnectionClosed, WebSocketException
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

# PyQt6 support
try:
    from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
    from PyQt6.QtNetwork import QTcpSocket
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

logger = logging.getLogger(__name__)


class ClientType(Enum):
    """客户端类型"""
    DESKTOP = "desktop"
    MOBILE = "mobile"
    WEB = "web"


class ConnectionState(Enum):
    """连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    ERROR = "error"


@dataclass
class Message:
    """消息"""
    type: str
    data: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    from_id: Optional[str] = None
    to_id: Optional[str] = None
    session_id: Optional[str] = None


class RelayClientBase:
    """中继客户端基类"""
    
    # 消息类型常量
    PING = "ping"
    PONG = "pong"
    REGISTER = "register"
    REGISTERED = "registered"
    CREATE_SESSION = "create_session"
    SESSION_CREATED = "session_created"
    JOIN_SESSION = "join_session"
    SESSION_JOINED = "session_joined"
    LEAVE_SESSION = "leave_session"
    SESSION_LEFT = "session_left"
    RELAY_MESSAGE = "relay_message"
    ERROR = "error"
    NOTIFICATION = "notification"
    
    def __init__(
        self,
        server_url: str,
        client_name: str = "",
        client_type: ClientType = ClientType.DESKTOP,
        auto_reconnect: bool = True,
        reconnect_interval: int = 5,
        ping_interval: int = 30
    ):
        self.server_url = server_url
        self.client_name = client_name
        self.client_type = client_type
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.ping_interval = ping_interval
        
        # 连接状态
        self.state = ConnectionState.DISCONNECTED
        self.client_id: Optional[str] = None
        
        # 会话信息
        self.current_session: Optional[str] = None
        self.session_members: List[Dict[str, Any]] = []
        
        # 回调函数
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.on_message: Optional[Callable] = None
        self.on_session_created: Optional[Callable] = None
        self.on_session_joined: Optional[Callable] = None
        self.on_session_left: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_notification: Optional[Callable] = None
    
    def create_message(
        self,
        msg_type: str,
        data: Dict[str, Any],
        msg_id: Optional[str] = None,
        to_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """创建JSON消息"""
        message = {
            "type": msg_type,
            "id": msg_id or str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "data": data
        }
        
        if to_id:
            message["to"] = to_id
        if session_id:
            message["session"] = session_id
            
        return json.dumps(message, ensure_ascii=False)
    
    def parse_message(self, raw: str) -> Optional[Dict[str, Any]]:
        """解析JSON消息"""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse message: {raw[:100]}")
            return None
    
    async def send_message(self, msg_type: str, data: Dict[str, Any], **kwargs):
        """发送消息（子类实现）"""
        raise NotImplementedError
    
    async def handle_message(self, message: Dict[str, Any]):
        """处理接收到的消息"""
        msg_type = message.get("type", "")
        data = message.get("data", {})
        
        if msg_type == self.PONG:
            pass  # 心跳响应
        
        elif msg_type == self.REGISTERED:
            self.client_id = data.get("client_id")
            self.state = ConnectionState.AUTHENTICATED
            if self.on_connected:
                await self._call_callback(self.on_connected, data)
        
        elif msg_type == self.SESSION_CREATED:
            self.current_session = data.get("session_id")
            if self.on_session_created:
                await self._call_callback(self.on_session_created, data)
        
        elif msg_type == self.SESSION_JOINED:
            self.current_session = data.get("session_id")
            self.session_members = data.get("members", [])
            if self.on_session_joined:
                await self._call_callback(self.on_session_joined, data)
        
        elif msg_type == self.SESSION_LEFT:
            self.current_session = None
            self.session_members = []
            if self.on_session_left:
                await self._call_callback(self.on_session_left, data)
        
        elif msg_type == self.RELAY_MESSAGE:
            if self.on_message:
                await self._call_callback(self.on_message, data)
        
        elif msg_type == self.ERROR:
            if self.on_error:
                await self._call_callback(self.on_error, data)
        
        elif msg_type == self.NOTIFICATION:
            if self.on_notification:
                await self._call_callback(self.on_notification, data)
    
    async def _call_callback(self, callback: Callable, *args):
        """调用回调函数"""
        if asyncio.iscoroutinefunction(callback):
            await callback(*args)
        else:
            callback(*args)


class AsyncRelayClient(RelayClientBase):
    """异步中继客户端"""
    
    def __init__(self, server_url: str, **kwargs):
        super().__init__(server_url, **kwargs)
        self.websocket: Optional[Any] = None
        self._running = False
    
    async def connect(self):
        """连接到服务器"""
        if not WEBSOCKETS_AVAILABLE:
            raise RuntimeError("websockets library not available. Install with: pip install websockets")
        
        self.state = ConnectionState.CONNECTING
        
        try:
            self.websocket = await connect(self.server_url)
            self._running = True
            
            # 发送注册消息
            await self.send_message(self.REGISTER, {
                "name": self.client_name,
                "client_type": self.client_type.value
            })
            
            # 启动接收循环
            asyncio.create_task(self._receive_loop())
            
            # 启动心跳
            asyncio.create_task(self._heartbeat_loop())
            
        except Exception as e:
            self.state = ConnectionState.ERROR
            logger.error(f"Connection failed: {e}")
            raise
    
    async def disconnect(self):
        """断开连接"""
        self._running = False
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        self.state = ConnectionState.DISCONNECTED
    
    async def _receive_loop(self):
        """接收消息循环"""
        try:
            async for message in self.websocket:
                parsed = self.parse_message(message)
                if parsed:
                    await self.handle_message(parsed)
        except ConnectionClosed:
            logger.info("Connection closed by server")
        except Exception as e:
            logger.error(f"Receive error: {e}")
        finally:
            self._running = False
            self.state = ConnectionState.DISCONNECTED
            if self.on_disconnected:
                await self._call_callback(self.on_disconnected)
    
    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._running:
            await asyncio.sleep(self.ping_interval)
            if self._running and self.websocket:
                try:
                    await self.send_message(self.PING, {})
                except Exception as e:
                    logger.warning(f"Heartbeat failed: {e}")
                    break
    
    async def send_message(self, msg_type: str, data: Dict[str, Any], **kwargs):
        """发送消息"""
        if not self.websocket:
            raise RuntimeError("Not connected")
        
        message = self.create_message(msg_type, data, **kwargs)
        await self.websocket.send(message)
    
    async def create_session(self, name: str = "", password: str = "", max_clients: int = 10):
        """创建会话"""
        await self.send_message(self.CREATE_SESSION, {
            "name": name,
            "password": password,
            "max_clients": max_clients
        })
    
    async def join_session(self, session_id: str, password: str = ""):
        """加入会话"""
        await self.send_message(self.JOIN_SESSION, {
            "session_id": session_id,
            "password": password
        })
    
    async def leave_session(self, session_id: Optional[str] = None):
        """离开会话"""
        session_id = session_id or self.current_session
        if session_id:
            await self.send_message(self.LEAVE_SESSION, {
                "session_id": session_id
            })
    
    async def send(self, data: Dict[str, Any], to_id: Optional[str] = None):
        """发送数据"""
        await self.send_message(self.RELAY_MESSAGE, {
            "data": data,
            "to": to_id
        }, to_id=to_id, session_id=self.current_session)
    
    async def broadcast(self, data: Dict[str, Any]):
        """广播到会话内所有成员"""
        await self.send(data)


class SyncRelayClient(RelayClientBase):
    """同步中继客户端（用于非异步环境）"""
    
    def __init__(self, server_url: str, **kwargs):
        super().__init__(server_url, **kwargs)
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.new_event_loop] = None
        self._async_client: Optional[AsyncRelayClient] = None
    
    def connect(self, timeout: float = 10.0):
        """连接到服务器（同步接口）"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        self._async_client = AsyncRelayClient(
            self.server_url,
            client_name=self.client_name,
            client_type=self.client_type,
            auto_reconnect=self.auto_reconnect,
            reconnect_interval=self.reconnect_interval,
            ping_interval=self.ping_interval
        )
        
        # 复制回调
        self._async_client.on_connected = self.on_connected
        self._async_client.on_disconnected = self.on_disconnected
        self._async_client.on_message = self.on_message
        self._async_client.on_session_created = self.on_session_created
        self._async_client.on_session_joined = self.on_session_joined
        self._async_client.on_session_left = self.on_session_left
        self._async_client.on_error = self.on_error
        self._async_client.on_notification = self.on_notification
        
        # 在新线程中运行
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        # 等待连接
        start = time.time()
        while self._async_client.state not in [ConnectionState.AUTHENTICATED, ConnectionState.ERROR]:
            if time.time() - start > timeout:
                raise TimeoutError("Connection timeout")
            time.sleep(0.1)
        
        if self._async_client.state == ConnectionState.ERROR:
            raise RuntimeError("Connection failed")
    
    def _run_loop(self):
        """运行事件循环"""
        try:
            self._loop.run_until_complete(self._async_client.connect())
            self._loop.run_forever()
        except Exception as e:
            logger.error(f"Async loop error: {e}")
    
    def disconnect(self):
        """断开连接"""
        if self._async_client and self._loop:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._async_client.disconnect())
            )
        if self._thread:
            self._thread.join(timeout=2.0)
    
    def create_session(self, name: str = "", password: str = "", max_clients: int = 10):
        """创建会话"""
        if self._async_client and self._loop:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(
                    self._async_client.create_session(name, password, max_clients)
                )
            )
    
    def join_session(self, session_id: str, password: str = ""):
        """加入会话"""
        if self._async_client and self._loop:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(
                    self._async_client.join_session(session_id, password)
                )
            )
    
    def leave_session(self, session_id: Optional[str] = None):
        """离开会话"""
        if self._async_client and self._loop:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(
                    self._async_client.leave_session(session_id)
                )
            )
    
    def send(self, data: Dict[str, Any], to_id: Optional[str] = None):
        """发送数据"""
        if self._async_client and self._loop:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._async_client.send(data, to_id))
            )
    
    def broadcast(self, data: Dict[str, Any]):
        """广播"""
        self.send(data)


# PyQt6 集成
if PYQT6_AVAILABLE:
    class PyQt6RelayClient(QObject, RelayClientBase):
        """PyQt6 中继客户端"""
        
        # Qt 信号
        connected = pyqtSignal(dict)
        disconnected = pyqtSignal()
        message_received = pyqtSignal(dict)
        session_created = pyqtSignal(dict)
        session_joined = pyqtSignal(dict)
        session_left = pyqtSignal(dict)
        error_occurred = pyqtSignal(dict)
        notification = pyqtSignal(dict)
        
        def __init__(self, server_url: str, **kwargs):
            QObject.__init__(self)
            RelayClientBase.__init__(self, server_url, **kwargs)
            
            self._async_client: Optional[AsyncRelayClient] = None
            self._worker: Optional[threading.Thread] = None
        
        def connect(self):
            """连接到服务器"""
            # 设置回调
            self.on_connected = lambda d: self.connected.emit(d)
            self.on_disconnected = lambda: self.disconnected.emit()
            self.on_message = lambda d: self.message_received.emit(d)
            self.on_session_created = lambda d: self.session_created.emit(d)
            self.on_session_joined = lambda d: self.session_joined.emit(d)
            self.on_session_left = lambda d: self.session_left.emit(d)
            self.on_error = lambda d: self.error_occurred.emit(d)
            self.on_notification = lambda d: self.notification.emit(d)
            
            # 创建异步客户端
            self._async_client = AsyncRelayClient(
                self.server_url,
                client_name=self.client_name,
                client_type=self.client_type,
                auto_reconnect=self.auto_reconnect,
                reconnect_interval=self.reconnect_interval,
                ping_interval=self.ping_interval
            )
            
            # 复制回调
            self._async_client.on_connected = self.on_connected
            self._async_client.on_disconnected = self.on_disconnected
            self._async_client.on_message = self.on_message
            self._async_client.on_session_created = self.on_session_created
            self._async_client.on_session_joined = self.on_session_joined
            self._async_client.on_session_left = self.on_session_left
            self._async_client.on_error = self.on_error
            self._async_client.on_notification = self.on_notification
            
            # 启动工作线程
            self._worker = threading.Thread(target=self._run_async, daemon=True)
            self._worker.start()
        
        def _run_async(self):
            """运行异步客户端"""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._async_client.connect())
                loop.run_forever()
            except Exception as e:
                logger.error(f"PyQt6 relay client error: {e}")
        
        def disconnect(self):
            """断开连接"""
            if self._async_client:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self._async_client.disconnect())
                except:
                    pass
        
        def create_session(self, name: str = "", password: str = "", max_clients: int = 10):
            """创建会话"""
            if self._async_client:
                asyncio.create_task(self._async_client.create_session(name, password, max_clients))
        
        def join_session(self, session_id: str, password: str = ""):
            """加入会话"""
            if self._async_client:
                asyncio.create_task(self._async_client.join_session(session_id, password))
        
        def leave_session(self, session_id: Optional[str] = None):
            """离开会话"""
            if self._async_client:
                asyncio.create_task(self._async_client.leave_session(session_id))
        
        def send(self, data: Dict[str, Any], to_id: Optional[str] = None):
            """发送数据"""
            if self._async_client:
                asyncio.create_task(self._async_client.send(data, to_id))
        
        def broadcast(self, data: Dict[str, Any]):
            """广播"""
            self.send(data)


def create_relay_client(
    server_url: str = None,
    client_name: str = "",
    client_type: ClientType = ClientType.DESKTOP,
    use_qt: bool = False,
    **kwargs
) -> RelayClientBase:
    """工厂函数：创建合适的客户端
    
    Args:
        server_url: 服务器URL，默认为配置中的 relay.url
        client_name: 客户端名称
        client_type: 客户端类型
        use_qt: 是否使用 PyQt6 版本
        **kwargs: 其他参数（auto_reconnect, reconnect_interval, ping_interval）
    
    Returns:
        RelayClientBase: 中继客户端实例
    """
    # 使用配置中的默认值
    if server_url is None:
        server_url = config.relay.url
    
    # 设置默认参数
    if "auto_reconnect" not in kwargs:
        kwargs["auto_reconnect"] = True
    if "reconnect_interval" not in kwargs:
        kwargs["reconnect_interval"] = config.retries.default
    if "ping_interval" not in kwargs:
        kwargs["ping_interval"] = config.delays.heartbeat
    
    if use_qt and PYQT6_AVAILABLE:
        return PyQt6RelayClient(server_url, client_name=client_name, client_type=client_type, **kwargs)
    elif asyncio.get_event_loop().is_running():
        return AsyncRelayClient(server_url, client_name=client_name, client_type=client_type, **kwargs)
    else:
        return SyncRelayClient(server_url, client_name=client_name, client_type=client_type, **kwargs)


# 导出
__all__ = [
    'RelayServer', 'RelayClientBase', 'AsyncRelayClient', 'SyncRelayClient',
    'PyQt6RelayClient', 'create_relay_client', 'ClientType', 'ConnectionState', 'Message'
]
