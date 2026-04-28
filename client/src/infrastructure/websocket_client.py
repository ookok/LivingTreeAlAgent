"""
WebSocketClient - WebSocket 客户端

实现客户端与服务器的实时通信。

功能：
1. 连接到 WebSocket 服务器
2. 发送和接收消息
3. 处理同步数据
4. 自动重连机制
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum

try:
    import websockets
    from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK
except ImportError:
    websockets = None


class MessageType(Enum):
    """消息类型"""
    PING = "ping"
    PONG = "pong"
    AUTH = "auth"
    SYNC = "sync"
    BROADCAST = "broadcast"
    CHANNEL = "channel"
    USER = "user"
    ERROR = "error"


class SyncType(Enum):
    """同步类型"""
    WORKSPACE = "workspace"
    CHAT = "chat"
    TASK = "task"
    SKILL = "skill"
    CONFIG = "config"


@dataclass
class SyncEvent:
    """同步事件"""
    sync_type: SyncType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class WebSocketClient:
    """
    WebSocket 客户端
    
    核心功能：
    1. 连接到 WebSocket 服务器
    2. 发送和接收消息
    3. 处理同步数据
    4. 自动重连机制
    """
    
    def __init__(self, server_url: str = "ws://localhost:8765"):
        self._server_url = server_url
        self._websocket = None
        self._connected = False
        self._reconnecting = False
        self._reconnect_delay = 5
        self._max_reconnect_delay = 60
        self._user_id = None
        self._device_id = self._generate_device_id()
        self._device_type = self._detect_device_type()
        
        self._sync_handlers: Dict[SyncType, List[Callable]] = {}
        self._message_handlers: Dict[MessageType, List[Callable]] = {}
        
        self._logger = logger.bind(component="WebSocketClient")
        
        if websockets is None:
            self._logger.warning("websockets 库未安装，WebSocket 功能将不可用")
    
    def _generate_device_id(self) -> str:
        """生成设备唯一标识"""
        return str(uuid.uuid4())
    
    def _detect_device_type(self) -> str:
        """检测设备类型"""
        try:
            import sys
            if sys.platform == "android" or sys.platform == "ios":
                return "mobile"
            elif "tablet" in sys.platform.lower():
                return "tablet"
            else:
                return "desktop"
        except:
            return "desktop"
    
    def on_sync(self, sync_type: SyncType, handler: Callable):
        """
        注册同步事件处理器
        
        Args:
            sync_type: 同步类型
            handler: 处理函数，接收 SyncEvent 参数
        """
        if sync_type not in self._sync_handlers:
            self._sync_handlers[sync_type] = []
        self._sync_handlers[sync_type].append(handler)
    
    def on_message(self, message_type: MessageType, handler: Callable):
        """
        注册消息处理器
        
        Args:
            message_type: 消息类型
            handler: 处理函数，接收消息数据
        """
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)
    
    async def connect(self, user_id: Optional[str] = None):
        """连接到服务器"""
        if websockets is None:
            self._logger.error("无法连接：缺少 websockets 依赖")
            return False
        
        self._user_id = user_id
        
        while not self._connected:
            try:
                self._logger.info(f"正在连接到 {self._server_url}")
                self._websocket = await websockets.connect(self._server_url)
                self._connected = True
                self._reconnect_delay = 5
                self._logger.info("连接成功")
                
                # 发送认证消息
                if self._user_id:
                    await self._send_auth()
                
                # 启动消息接收循环
                asyncio.create_task(self._receive_loop())
                
                return True
            except Exception as e:
                self._logger.error(f"连接失败: {e}")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)
        
        return True
    
    async def disconnect(self):
        """断开连接"""
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception as e:
                self._logger.error(f"断开连接失败: {e}")
            finally:
                self._websocket = None
                self._connected = False
                self._logger.info("已断开连接")
    
    async def _send_auth(self):
        """发送认证消息"""
        await self._send_message(MessageType.AUTH, {
            "user_id": self._user_id,
            "device_id": self._device_id,
            "device_type": self._device_type
        })
    
    async def _receive_loop(self):
        """消息接收循环"""
        try:
            async for message in self._websocket:
                await self._handle_message(message)
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK):
            self._logger.info("连接已关闭")
        except Exception as e:
            self._logger.error(f"接收消息失败: {e}")
        finally:
            self._connected = False
            if not self._reconnecting:
                asyncio.create_task(self.connect(self._user_id))
    
    async def _handle_message(self, message: str):
        """处理收到的消息"""
        try:
            data = json.loads(message)
            message_type = MessageType(data.get("type", "error"))
            
            # 调用消息处理器
            if message_type in self._message_handlers:
                for handler in self._message_handlers[message_type]:
                    try:
                        handler(data)
                    except Exception as e:
                        self._logger.error(f"消息处理器失败: {e}")
            
            # 处理同步消息
            if message_type == MessageType.SYNC:
                await self._handle_sync(data)
            
        except json.JSONDecodeError:
            self._logger.error("无效的 JSON 消息")
    
    async def _handle_sync(self, data: Dict[str, Any]):
        """处理同步消息"""
        content = data.get("content", {})
        sync_type = content.get("sync_type")
        sync_data = content.get("data")
        
        # 如果是确认消息（没有实际数据），只记录日志
        if sync_data is None:
            if content.get("success"):
                self._logger.debug(f"同步确认: {sync_type}")
            return
        
        try:
            sync_enum = SyncType(sync_type)
        except ValueError:
            self._logger.error(f"未知同步类型: {sync_type}")
            return
        
        event = SyncEvent(sync_type=sync_enum, data=sync_data)
        
        if sync_enum in self._sync_handlers:
            for handler in self._sync_handlers[sync_enum]:
                try:
                    handler(event)
                except Exception as e:
                    self._logger.error(f"同步处理器失败: {e}")
    
    async def _send_message(self, message_type: MessageType, content: Dict[str, Any]):
        """发送消息"""
        if not self._connected or not self._websocket:
            self._logger.warning("未连接到服务器")
            return
        
        try:
            message = {
                "message_id": str(uuid.uuid4()),
                "type": message_type.value,
                "content": content,
                "timestamp": datetime.now().isoformat()
            }
            await self._websocket.send(json.dumps(message))
        except Exception as e:
            self._logger.error(f"发送消息失败: {e}")
    
    async def send_ping(self):
        """发送心跳"""
        await self._send_message(MessageType.PING, {"timestamp": datetime.now().isoformat()})
    
    async def send_sync(self, sync_type: SyncType, data: Dict[str, Any]):
        """
        发送同步消息
        
        Args:
            sync_type: 同步类型
            data: 同步数据
        """
        await self._send_message(MessageType.SYNC, {
            "sync_type": sync_type.value,
            "data": data
        })
    
    async def send_broadcast(self, content: Dict[str, Any], target_users: Optional[List[str]] = None):
        """
        发送广播消息
        
        Args:
            content: 消息内容
            target_users: 目标用户列表（可选，为空则全局广播）
        """
        message = {"content": content}
        if target_users:
            message["target_users"] = target_users
        
        await self._send_message(MessageType.BROADCAST, message)
    
    async def join_channel(self, channel_name: str):
        """加入频道"""
        await self._send_message(MessageType.CHANNEL, {
            "action": "join",
            "channel": channel_name
        })
    
    async def leave_channel(self, channel_name: str):
        """离开频道"""
        await self._send_message(MessageType.CHANNEL, {
            "action": "leave",
            "channel": channel_name
        })
    
    async def send_to_channel(self, channel_name: str, content: Dict[str, Any]):
        """发送消息到频道"""
        await self._send_message(MessageType.CHANNEL, {
            "action": "send",
            "channel": channel_name,
            "content": content
        })
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected
    
    def get_stats(self) -> Dict[str, Any]:
        """获取客户端状态"""
        return {
            "connected": self._connected,
            "user_id": self._user_id,
            "device_id": self._device_id,
            "device_type": self._device_type,
            "server_url": self._server_url
        }