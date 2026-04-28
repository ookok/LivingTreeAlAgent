"""
WebSocketServer - WebSocket 实时通信服务器

实现跨设备同步和多用户协作功能。

功能：
1. 支持跨设备同步（手机/平板/电脑）
2. 多用户协作（未来扩展）
3. 实时消息推送
4. 房间/频道机制
5. 用户认证和会话管理
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    from websockets.exceptions import ConnectionClosed
except ImportError:
    websockets = None
    WebSocketServerProtocol = None
    ConnectionClosed = Exception


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
class ClientSession:
    """客户端会话"""
    session_id: str
    user_id: Optional[str]
    device_id: str
    device_type: str  # mobile/tablet/desktop
    websocket: Any
    joined_channels: List[str] = field(default_factory=list)
    last_active: datetime = field(default_factory=datetime.now)
    authenticated: bool = False


@dataclass
class Message:
    """消息对象"""
    message_id: str
    type: MessageType
    sender_id: str
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    channel: Optional[str] = None
    target_user_id: Optional[str] = None


class WebSocketServer:
    """
    WebSocket 实时通信服务器
    
    核心功能：
    1. 支持跨设备同步（手机/平板/电脑）
    2. 多用户协作
    3. 实时消息推送
    4. 房间/频道机制
    5. 用户认证和会话管理
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self._host = host
        self._port = port
        self._server = None
        self._sessions: Dict[str, ClientSession] = {}  # session_id -> session
        self._user_sessions: Dict[str, List[str]] = {}  # user_id -> [session_ids]
        self._channels: Dict[str, List[str]] = {}  # channel_name -> [session_ids]
        self._message_handlers: Dict[MessageType, Callable] = {}
        self._sync_callbacks: Dict[SyncType, List[Callable]] = {}
        
        self._logger = logger.bind(component="WebSocketServer")
        
        if websockets is None:
            self._logger.warning("websockets 库未安装，WebSocket 功能将不可用")
        
        self._register_handlers()
    
    def _register_handlers(self):
        """注册消息处理器"""
        self._message_handlers[MessageType.PING] = self._handle_ping
        self._message_handlers[MessageType.AUTH] = self._handle_auth
        self._message_handlers[MessageType.SYNC] = self._handle_sync
        self._message_handlers[MessageType.BROADCAST] = self._handle_broadcast
        self._message_handlers[MessageType.CHANNEL] = self._handle_channel
    
    def register_sync_callback(self, sync_type: SyncType, callback: Callable):
        """
        注册同步回调
        
        Args:
            sync_type: 同步类型
            callback: 回调函数，接收 (user_id, data) 参数
        """
        if sync_type not in self._sync_callbacks:
            self._sync_callbacks[sync_type] = []
        self._sync_callbacks[sync_type].append(callback)
    
    async def start(self):
        """启动 WebSocket 服务器"""
        if websockets is None:
            self._logger.error("无法启动 WebSocket 服务器：缺少 websockets 依赖")
            return
        
        try:
            self._server = await websockets.serve(
                self._handle_connection,
                self._host,
                self._port,
                ping_interval=30,
                ping_timeout=60
            )
            self._logger.info(f"WebSocket 服务器已启动: ws://{self._host}:{self._port}")
            await self._server.wait_closed()
        except Exception as e:
            self._logger.error(f"WebSocket 服务器启动失败: {e}")
    
    async def stop(self):
        """停止 WebSocket 服务器"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._logger.info("WebSocket 服务器已停止")
    
    async def _handle_connection(self, websocket):
        """处理新连接"""
        session_id = str(uuid.uuid4())
        session = ClientSession(
            session_id=session_id,
            user_id=None,
            device_id="",
            device_type="unknown",
            websocket=websocket
        )
        self._sessions[session_id] = session
        
        self._logger.info(f"新连接: {session_id}")
        
        try:
            async for message in websocket:
                await self._handle_message(session_id, message)
        except ConnectionClosed:
            self._logger.info(f"连接关闭: {session_id}")
        except Exception as e:
            self._logger.error(f"连接错误 {session_id}: {e}")
        finally:
            await self._cleanup_session(session_id)
    
    async def _handle_message(self, session_id: str, message: str):
        """处理消息"""
        try:
            data = json.loads(message)
            message_type = MessageType(data.get("type", "error"))
            handler = self._message_handlers.get(message_type)
            
            if handler:
                await handler(session_id, data)
            else:
                await self._send_error(session_id, f"未知消息类型: {message_type}")
        except json.JSONDecodeError:
            await self._send_error(session_id, "无效的 JSON 消息")
        except Exception as e:
            await self._send_error(session_id, str(e))
    
    async def _handle_ping(self, session_id: str, data: Dict[str, Any]):
        """处理心跳"""
        await self._send_message(session_id, MessageType.PONG, {"timestamp": datetime.now().isoformat()})
    
    async def _handle_auth(self, session_id: str, data: Dict[str, Any]):
        """处理认证"""
        content = data.get("content", {})
        user_id = content.get("user_id")
        device_id = content.get("device_id")
        device_type = content.get("device_type", "unknown")
        
        if not user_id:
            await self._send_error(session_id, "缺少 user_id")
            return
        
        session = self._sessions.get(session_id)
        if session:
            session.user_id = user_id
            session.device_id = device_id
            session.device_type = device_type
            session.authenticated = True
            session.last_active = datetime.now()
            
            # 添加到用户会话列表
            if user_id not in self._user_sessions:
                self._user_sessions[user_id] = []
            if session_id not in self._user_sessions[user_id]:
                self._user_sessions[user_id].append(session_id)
            
            self._logger.info(f"用户认证成功: {user_id} ({device_type})")
            await self._send_message(session_id, MessageType.AUTH, {"success": True, "user_id": user_id})
    
    async def _handle_sync(self, session_id: str, data: Dict[str, Any]):
        """处理同步请求"""
        session = self._sessions.get(session_id)
        if not session or not session.authenticated:
            await self._send_error(session_id, "未认证")
            return
        
        content = data.get("content", {})
        sync_type = content.get("sync_type")
        sync_data = content.get("data", {})
        
        self._logger.info(f"收到同步请求: user_id={session.user_id}, sync_type={sync_type}")
        
        try:
            sync_enum = SyncType(sync_type)
        except ValueError:
            await self._send_error(session_id, f"未知同步类型: {sync_type}")
            return
        
        # 通知其他设备
        await self._sync_to_other_devices(session.user_id, session_id, sync_enum, sync_data)
        
        # 调用同步回调
        if sync_enum in self._sync_callbacks:
            for callback in self._sync_callbacks[sync_enum]:
                try:
                    callback(session.user_id, sync_data)
                except Exception as e:
                    self._logger.error(f"同步回调失败: {e}")
        
        await self._send_message(session_id, MessageType.SYNC, {"success": True, "sync_type": sync_type})
    
    async def _sync_to_other_devices(self, user_id: str, exclude_session_id: str,
                                     sync_type: SyncType, data: Dict[str, Any]):
        """同步数据到用户的其他设备"""
        sessions = self._user_sessions.get(user_id, [])
        
        for session_id in sessions:
            if session_id == exclude_session_id:
                continue
            
            session = self._sessions.get(session_id)
            if session and session.authenticated:
                try:
                    await self._send_message(
                        session_id,
                        MessageType.SYNC,
                        {
                            "sync_type": sync_type.value,
                            "data": data,
                            "from_device": "server"
                        }
                    )
                    self._logger.info(f"同步消息已发送到设备: {session_id}")
                except Exception as e:
                    self._logger.error(f"同步到设备失败 {session_id}: {e}")
    
    async def _handle_broadcast(self, session_id: str, data: Dict[str, Any]):
        """处理广播消息"""
        session = self._sessions.get(session_id)
        if not session or not session.authenticated:
            await self._send_error(session_id, "未认证")
            return
        
        content = data.get("content", {})
        target_users = content.get("target_users", [])
        
        if target_users:
            # 定向广播
            for target_user_id in target_users:
                await self._send_to_user(target_user_id, content)
        else:
            # 全局广播（仅已认证用户）
            await self._broadcast_to_all(content)
    
    async def _handle_channel(self, session_id: str, data: Dict[str, Any]):
        """处理频道操作"""
        session = self._sessions.get(session_id)
        if not session or not session.authenticated:
            await self._send_error(session_id, "未认证")
            return
        
        content = data.get("content", {})
        action = content.get("action")
        channel_name = content.get("channel")
        
        if action == "join":
            await self._join_channel(session_id, channel_name)
        elif action == "leave":
            await self._leave_channel(session_id, channel_name)
        elif action == "send":
            message_content = content.get("content", {})
            await self._send_to_channel(channel_name, message_content, session_id)
        else:
            await self._send_error(session_id, f"未知频道操作: {action}")
    
    async def _join_channel(self, session_id: str, channel_name: str):
        """加入频道"""
        session = self._sessions.get(session_id)
        if not session:
            return
        
        if channel_name not in self._channels:
            self._channels[channel_name] = []
        
        if session_id not in self._channels[channel_name]:
            self._channels[channel_name].append(session_id)
            session.joined_channels.append(channel_name)
        
        await self._send_message(session_id, MessageType.CHANNEL, {
            "action": "joined",
            "channel": channel_name
        })
    
    async def _leave_channel(self, session_id: str, channel_name: str):
        """离开频道"""
        session = self._sessions.get(session_id)
        if not session:
            return
        
        if channel_name in self._channels and session_id in self._channels[channel_name]:
            self._channels[channel_name].remove(session_id)
        
        if channel_name in session.joined_channels:
            session.joined_channels.remove(channel_name)
        
        await self._send_message(session_id, MessageType.CHANNEL, {
            "action": "left",
            "channel": channel_name
        })
    
    async def _send_to_channel(self, channel_name: str, content: Dict[str, Any], sender_session_id: str):
        """发送消息到频道"""
        if channel_name not in self._channels:
            return
        
        session = self._sessions.get(sender_session_id)
        sender_user_id = session.user_id if session else "unknown"
        
        for session_id in self._channels[channel_name]:
            if session_id == sender_session_id:
                continue
            
            try:
                await self._send_message(session_id, MessageType.CHANNEL, {
                    "action": "message",
                    "channel": channel_name,
                    "sender": sender_user_id,
                    "content": content,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                self._logger.error(f"发送到频道失败 {session_id}: {e}")
    
    async def _send_message(self, session_id: str, message_type: MessageType, content: Dict[str, Any]):
        """发送消息给单个客户端"""
        session = self._sessions.get(session_id)
        if not session:
            return
        
        try:
            message = {
                "message_id": str(uuid.uuid4()),
                "type": message_type.value,
                "content": content,
                "timestamp": datetime.now().isoformat()
            }
            await session.websocket.send(json.dumps(message))
            session.last_active = datetime.now()
        except Exception as e:
            self._logger.error(f"发送消息失败 {session_id}: {e}")
    
    async def _send_error(self, session_id: str, error_message: str):
        """发送错误消息"""
        await self._send_message(session_id, MessageType.ERROR, {"error": error_message})
    
    async def _send_to_user(self, user_id: str, content: Dict[str, Any]):
        """发送消息给用户的所有设备"""
        sessions = self._user_sessions.get(user_id, [])
        for session_id in sessions:
            await self._send_message(session_id, MessageType.USER, content)
    
    async def _broadcast_to_all(self, content: Dict[str, Any]):
        """广播消息给所有已认证用户"""
        for session_id, session in self._sessions.items():
            if session.authenticated:
                await self._send_message(session_id, MessageType.BROADCAST, content)
    
    async def _cleanup_session(self, session_id: str):
        """清理会话"""
        session = self._sessions.pop(session_id, None)
        if not session:
            return
        
        # 从用户会话列表移除
        if session.user_id and session.user_id in self._user_sessions:
            if session_id in self._user_sessions[session.user_id]:
                self._user_sessions[session.user_id].remove(session_id)
        
        # 从频道移除
        for channel_name in session.joined_channels:
            if channel_name in self._channels and session_id in self._channels[channel_name]:
                self._channels[channel_name].remove(session_id)
        
        self._logger.info(f"会话已清理: {session_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        authenticated_count = sum(1 for s in self._sessions.values() if s.authenticated)
        device_counts = {}
        
        for session in self._sessions.values():
            device_counts[session.device_type] = device_counts.get(session.device_type, 0) + 1
        
        return {
            "total_connections": len(self._sessions),
            "authenticated_users": len(self._user_sessions),
            "authenticated_connections": authenticated_count,
            "channels": len(self._channels),
            "device_distribution": device_counts
        }
    
    def sync_workspace(self, user_id: str, workspace_data: Dict[str, Any]):
        """同步工作区数据到用户的所有设备"""
        asyncio.create_task(self._sync_to_other_devices(
            user_id,
            "",  # 空字符串表示不排除任何会话
            SyncType.WORKSPACE,
            workspace_data
        ))
    
    def sync_chat(self, user_id: str, chat_data: Dict[str, Any]):
        """同步聊天数据到用户的所有设备"""
        asyncio.create_task(self._sync_to_other_devices(
            user_id,
            "",
            SyncType.CHAT,
            chat_data
        ))
    
    def sync_task(self, user_id: str, task_data: Dict[str, Any]):
        """同步任务数据到用户的所有设备"""
        asyncio.create_task(self._sync_to_other_devices(
            user_id,
            "",
            SyncType.TASK,
            task_data
        ))