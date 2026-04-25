"""
WebSocket Relay Service - WebSocket 中继服务
==========================================

提供实时消息中继、频道管理、消息广播等功能
"""

import json
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Set, Optional, Any, List
from collections import defaultdict
from dataclasses import dataclass, field

from core.config.unified_config import UnifiedConfig

try:
    from fastapi import WebSocket, WebSocketDisconnect
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@dataclass
class ConnectionInfo:
    """连接信息"""
    connection_id: str
    websocket: WebSocket
    user_id: Optional[str] = None
    username: Optional[str] = None
    channel: str = "default"
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    is_authenticated: bool = False
    joined_at: datetime = field(default_factory=datetime.utcnow)
    last_ping: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 统计
    messages_sent: int = 0
    messages_received: int = 0


class Channel:
    """频道"""
    
    def __init__(self, name: str):
        self.name = name
        self.connections: Dict[str, ConnectionInfo] = {}
        self.created_at = datetime.utcnow()
        self.history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def add_connection(self, conn: ConnectionInfo):
        """添加连接"""
        self.connections[conn.connection_id] = conn
    
    def remove_connection(self, connection_id: str) -> Optional[ConnectionInfo]:
        """移除连接"""
        return self.connections.pop(connection_id, None)
    
    def get_connection(self, connection_id: str) -> Optional[ConnectionInfo]:
        """获取连接"""
        return self.connections.get(connection_id)
    
    def broadcast(self, message: Dict[str, Any], exclude: Optional[Set[str]] = None):
        """广播消息"""
        exclude = exclude or set()
        for conn_id, conn in self.connections.items():
            if conn_id not in exclude:
                asyncio.create_task(self._send(conn, message))
    
    async def _send(self, conn: ConnectionInfo, message: Dict[str, Any]):
        """发送消息到连接"""
        try:
            await conn.websocket.send_json(message)
            conn.messages_sent += 1
        except Exception:
            pass  # 连接可能已断开
    
    def add_history(self, message: Dict[str, Any]):
        """添加历史消息"""
        self.history.append(message)
        if len(self.history) > self.max_history:
            self.history.pop(0)
    
    @property
    def connection_count(self) -> int:
        """连接数"""
        return len(self.connections)
    
    def get_info(self) -> Dict[str, Any]:
        """获取频道信息"""
        return {
            "name": self.name,
            "connection_count": self.connection_count,
            "created_at": self.created_at.isoformat(),
        }


class WebSocketRelayService:
    """WebSocket 中继服务"""
    
    _instance: Optional["WebSocketRelayService"] = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        
        self._initialized = True
        self.channels: Dict[str, Channel] = defaultdict(Channel)
        self.all_connections: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[str, Set[str]] = defaultdict(set)  # user_id -> {connection_ids}
        
        # 消息路由规则
        self.routing_rules: Dict[str, str] = {}  # pattern -> channel
        self.message_handlers: Dict[str, callable] = {}
        
        # 配置
        config = UnifiedConfig.get_instance()
        self.max_channels = 100
        self.max_connections_per_channel = 1000
        self.ping_interval = config.get("server.ws_ping_interval", 30)  # 秒
        self.ping_timeout = config.get("server.ws_ping_timeout", 60)  # 秒
    
    def generate_connection_id(self) -> str:
        """生成连接 ID"""
        return f"conn_{uuid.uuid4().hex[:16]}"
    
    async def connect(
        self,
        websocket: WebSocket,
        channel: str = "default",
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """
        建立 WebSocket 连接
        
        Returns:
            connection_id
        """
        await websocket.accept()
        
        connection_id = self.generate_connection_id()
        
        conn_info = ConnectionInfo(
            connection_id=connection_id,
            websocket=websocket,
            user_id=user_id,
            username=username,
            channel=channel,
            client_ip=client_ip,
            user_agent=user_agent,
            is_authenticated=user_id is not None,
        )
        
        # 添加到频道
        ch = self.channels[channel]
        ch.add_connection(conn_info)
        
        # 添加到全局连接
        self.all_connections[connection_id] = conn_info
        
        # 添加到用户连接映射
        if user_id:
            self.user_connections[user_id].add(connection_id)
        
        # 发送连接成功消息
        await websocket.send_json({
            "type": "connected",
            "connection_id": connection_id,
            "channel": channel,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return connection_id
    
    async def disconnect(self, connection_id: str, code: int = 1000, reason: str = ""):
        """断开连接"""
        conn = self.all_connections.pop(connection_id, None)
        if conn is None:
            return
        
        # 从频道移除
        ch = self.channels.get(conn.channel)
        if ch:
            ch.remove_connection(connection_id)
            if ch.connection_count == 0:
                # 空频道可以保留或删除
                pass
        
        # 从用户连接映射移除
        if conn.user_id:
            user_conns = self.user_connections.get(conn.user_id)
            if user_conns:
                user_conns.discard(connection_id)
                if not user_conns:
                    del self.user_connections[conn.user_id]
        
        # 广播离开消息
        self.channels[conn.channel].broadcast({
            "type": "member_left",
            "connection_id": connection_id,
            "user_id": conn.user_id,
            "username": conn.username,
            "timestamp": datetime.utcnow().isoformat(),
        }, exclude={connection_id})
    
    async def send_to_connection(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """发送消息到指定连接"""
        conn = self.all_connections.get(connection_id)
        if conn is None:
            return False
        
        try:
            await conn.websocket.send_json(message)
            conn.messages_sent += 1
            return True
        except Exception:
            await self.disconnect(connection_id, reason="Send failed")
            return False
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> int:
        """发送消息到用户的所有连接"""
        sent = 0
        for conn_id in self.user_connections.get(user_id, set()):
            if await self.send_to_connection(conn_id, message):
                sent += 1
        return sent
    
    def broadcast_to_channel(
        self, 
        channel: str, 
        message: Dict[str, Any],
        exclude_connections: Optional[Set[str]] = None
    ):
        """广播到频道"""
        ch = self.channels.get(channel)
        if ch:
            ch.broadcast(message, exclude=exclude_connections or set())
            if message.get("type") in ("chat", "message"):
                ch.add_history(message)
    
    def broadcast_all(self, message: Dict[str, Any]):
        """广播到所有频道"""
        for channel in self.channels.values():
            channel.broadcast(message)
    
    async def route_message(
        self,
        connection_id: str,
        message: Dict[str, Any],
    ) -> bool:
        """
        路由消息
        
        支持的消息类型:
        - chat: 聊天消息
        - broadcast: 广播
        - direct: 私聊
        - channel: 频道消息
        """
        msg_type = message.get("type")
        
        if msg_type == "ping":
            # 心跳
            conn = self.all_connections.get(connection_id)
            if conn:
                conn.last_ping = datetime.utcnow()
            await self.send_to_connection(connection_id, {
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat(),
            })
            return True
        
        elif msg_type == "chat":
            # 聊天消息
            return await self._handle_chat(connection_id, message)
        
        elif msg_type == "broadcast":
            # 广播消息
            self.broadcast_all({
                "type": "broadcast",
                "from": connection_id,
                "content": message.get("content"),
                "metadata": message.get("metadata", {}),
                "timestamp": datetime.utcnow().isoformat(),
            })
            return True
        
        elif msg_type == "direct":
            # 私聊消息
            return await self._handle_direct(connection_id, message)
        
        elif msg_type == "join":
            # 加入频道
            return await self._handle_join(connection_id, message)
        
        elif msg_type == "leave":
            # 离开频道
            return await self._handle_leave(connection_id, message)
        
        elif msg_type == "subscribe":
            # 订阅主题
            return await self._handle_subscribe(connection_id, message)
        
        else:
            # 自定义消息，尝试路由
            handler = self.message_handlers.get(msg_type)
            if handler:
                return await handler(connection_id, message)
            
            # 默认：广播到同频道
            conn = self.all_connections.get(connection_id)
            if conn:
                self.broadcast_to_channel(conn.channel, {
                    "type": msg_type,
                    "from": connection_id,
                    "content": message,
                    "timestamp": datetime.utcnow().isoformat(),
                }, exclude={connection_id})
            return True
    
    async def _handle_chat(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """处理聊天消息"""
        conn = self.all_connections.get(connection_id)
        if conn is None:
            return False
        
        chat_message = {
            "type": "chat",
            "from": connection_id,
            "user_id": conn.user_id,
            "username": conn.username,
            "content": message.get("content"),
            "metadata": message.get("metadata", {}),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # 发送到同频道
        self.broadcast_to_channel(conn.channel, chat_message, exclude={connection_id})
        
        # 保存历史
        ch = self.channels.get(conn.channel)
        if ch:
            ch.add_history(chat_message)
        
        return True
    
    async def _handle_direct(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """处理私聊消息"""
        target_connection_id = message.get("to")
        if not target_connection_id:
            return False
        
        conn = self.all_connections.get(connection_id)
        if conn is None:
            return False
        
        direct_message = {
            "type": "direct",
            "from": connection_id,
            "user_id": conn.user_id,
            "username": conn.username,
            "content": message.get("content"),
            "metadata": message.get("metadata", {}),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        return await self.send_to_connection(target_connection_id, direct_message)
    
    async def _handle_join(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """处理加入频道"""
        channel = message.get("channel")
        if not channel:
            return False
        
        conn = self.all_connections.get(connection_id)
        if conn is None:
            return False
        
        # 从旧频道移除
        old_channel = conn.channel
        if old_channel != channel:
            old_ch = self.channels.get(old_channel)
            if old_ch:
                old_ch.remove_connection(connection_id)
                old_ch.broadcast({
                    "type": "member_left",
                    "connection_id": connection_id,
                    "user_id": conn.user_id,
                    "username": conn.username,
                    "timestamp": datetime.utcnow().isoformat(),
                }, exclude={connection_id})
        
        # 加入新频道
        conn.channel = channel
        ch = self.channels[channel]
        ch.add_connection(conn)
        
        # 发送成功消息
        await self.send_to_connection(connection_id, {
            "type": "joined",
            "channel": channel,
            "history": ch.history[-20:],  # 最近 20 条消息
            "members": [c.connection_id for c in ch.connections.values()],
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        # 广播新成员加入
        ch.broadcast({
            "type": "member_joined",
            "connection_id": connection_id,
            "user_id": conn.user_id,
            "username": conn.username,
            "timestamp": datetime.utcnow().isoformat(),
        }, exclude={connection_id})
        
        return True
    
    async def _handle_leave(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """处理离开频道"""
        channel = message.get("channel")
        
        conn = self.all_connections.get(connection_id)
        if conn is None:
            return False
        
        if channel:
            # 离开指定频道
            ch = self.channels.get(channel)
            if ch:
                ch.remove_connection(connection_id)
                ch.broadcast({
                    "type": "member_left",
                    "connection_id": connection_id,
                    "user_id": conn.user_id,
                    "username": conn.username,
                    "timestamp": datetime.utcnow().isoformat(),
                }, exclude={connection_id})
        else:
            # 断开连接
            await self.disconnect(connection_id, reason="User left")
        
        return True
    
    async def _handle_subscribe(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """处理订阅主题"""
        topic = message.get("topic")
        
        conn = self.all_connections.get(connection_id)
        if conn is None:
            return False
        
        # 简单实现：将连接标记为订阅了某个主题
        if not hasattr(conn, 'subscriptions'):
            conn.subscriptions = set()
        conn.subscriptions.add(topic)
        
        await self.send_to_connection(connection_id, {
            "type": "subscribed",
            "topic": topic,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return True
    
    # ============ 管理接口 ============
    
    def get_channel_info(self, channel: str) -> Optional[Dict[str, Any]]:
        """获取频道信息"""
        ch = self.channels.get(channel)
        if ch is None:
            return None
        
        return {
            "name": ch.name,
            "connection_count": ch.connection_count,
            "connections": [
                {
                    "connection_id": c.connection_id,
                    "user_id": c.user_id,
                    "username": c.username,
                    "is_authenticated": c.is_authenticated,
                    "connected_at": c.joined_at.isoformat(),
                }
                for c in ch.connections.values()
            ],
            "history_count": len(ch.history),
        }
    
    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """获取连接信息"""
        conn = self.all_connections.get(connection_id)
        if conn is None:
            return None
        
        return {
            "connection_id": conn.connection_id,
            "user_id": conn.user_id,
            "username": conn.username,
            "channel": conn.channel,
            "is_authenticated": conn.is_authenticated,
            "connected_at": conn.joined_at.isoformat(),
            "messages_sent": conn.messages_sent,
            "messages_received": conn.messages_received,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_connections = len(self.all_connections)
        authenticated = sum(1 for c in self.all_connections.values() if c.is_authenticated)
        anonymous = total_connections - authenticated
        
        channel_stats = {
            name: ch.connection_count 
            for name, ch in self.channels.items()
        }
        
        return {
            "total_connections": total_connections,
            "authenticated_connections": authenticated,
            "anonymous_connections": anonymous,
            "total_channels": len(self.channels),
            "channel_stats": channel_stats,
            "top_channels": sorted(
                channel_stats.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10],
        }


# 全局实例
_ws_relay_service: Optional[WebSocketRelayService] = None


def get_ws_relay_service() -> WebSocketRelayService:
    """获取 WebSocket 中继服务单例"""
    global _ws_relay_service
    if _ws_relay_service is None:
        _ws_relay_service = WebSocketRelayService()
    return _ws_relay_service


# ============ FastAPI 集成 ============

if FASTAPI_AVAILABLE:
    
    async def websocket_endpoint(
        websocket: WebSocket,
        channel: str = "default",
        token: Optional[str] = None,
    ):
        """
        WebSocket 端点处理函数
        
        使用方式:
        @app.websocket("/ws/{channel}")
        async def ws_handler(websocket: WebSocket, channel: str):
            await websocket_endpoint(websocket, channel)
        """
        service = get_ws_relay_service()
        
        # 验证 token（如果提供）
        user_id = None
        username = None
        if token:
            from .auth_service import get_auth_service
            auth_service = get_auth_service()
            payload = auth_service.verify_token(token)
            if payload:
                user_id = payload.get("sub")
                username = payload.get("username")
        
        # 获取客户端信息
        client_ip = websocket.client.host if websocket.client else None
        user_agent = websocket.headers.get("user-agent")
        
        # 建立连接
        connection_id = await service.connect(
            websocket=websocket,
            channel=channel,
            user_id=user_id,
            username=username,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        
        try:
            while True:
                # 接收消息
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    await service.send_to_connection(connection_id, {
                        "type": "error",
                        "error": "Invalid JSON",
                    })
                    continue
                
                # 路由消息
                await service.route_message(connection_id, message)
                
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            await service.disconnect(connection_id)
