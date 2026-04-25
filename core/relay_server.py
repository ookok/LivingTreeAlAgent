"""
WebSocket 中继服务器
WebSocket Relay Server

功能：
- 桌面客户端和移动端/网页端之间的消息中继
- 会话管理（创建/加入/销毁）
- 心跳检测与自动重连
- 消息确认与可靠性保证

架构：
┌─────────────────────────────────────────────────────────────┐
│                    WebSocket Relay Server                  │
├─────────────────────────────────────────────────────────────┤
│  桌面客户端 ──WebSocket──→ 中继服务器 ←─WebSocket── 移动端  │
│    (PyQt6)           (Python asyncio)          (Flutter/网页) │
└─────────────────────────────────────────────────────────────┘
"""

import os
import json
import time
import uuid
import asyncio
import logging
import hashlib
import secrets
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import argparse

from core.logger import get_logger

logger = get_logger('relay_server')

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# WebSocket support
try:
    import websockets
    from websockets.server import WebSocketServerProtocol, serve
    from websockets.exceptions import ConnectionClosed, WebSocketException
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.info("Warning: websockets library not found. Install with: pip install websockets")


class MessageType(Enum):
    """消息类型枚举"""
    # 控制消息
    PING = "ping"
    PONG = "pong"
    REGISTER = "register"
    UNREGISTER = "unregister"
    
    # 会话消息
    CREATE_SESSION = "create_session"
    JOIN_SESSION = "join_session"
    LEAVE_SESSION = "leave_session"
    SESSION_CREATED = "session_created"
    SESSION_JOINED = "session_joined"
    SESSION_LEFT = "session_left"
    SESSION_ERROR = "session_error"
    
    # 数据消息
    REQUEST_DATA = "request_data"
    RESPONSE_DATA = "response_data"
    TRANSFER_DATA = "transfer_data"
    TRANSFER_PROGRESS = "transfer_progress"
    TRANSFER_COMPLETE = "transfer_complete"
    
    # 状态消息
    ONLINE_STATUS = "online_status"
    TYPING_STATUS = "typing_status"
    CURSOR_POSITION = "cursor_position"
    ERROR = "error"
    NOTIFICATION = "notification"
    
    # 中继消息（核心功能）
    RELAY_MESSAGE = "relay_message"
    BROADCAST = "broadcast"


@dataclass
class Client:
    """客户端连接"""
    id: str                    # 客户端唯一ID
    websocket: Any              # WebSocket连接
    name: str = ""             # 客户端名称
    client_type: str = "desktop"  # desktop/mobile/web
    sessions: Set[str] = field(default_factory=set)  # 所属会话
    is_authenticated: bool = False  # 是否认证
    last_ping: float = field(default_factory=time.time)  # 最后心跳时间
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据


@dataclass
class Session:
    """会话"""
    id: str                     # 会话唯一ID
    name: str = ""              # 会话名称
    host_id: str = ""           # 主持人ID
    created_at: float = field(default_factory=time.time)  # 创建时间
    max_clients: int = 10      # 最大客户端数
    password: str = ""          # 会话密码（可选）
    clients: Set[str] = field(default_factory=set)  # 客户端ID集合
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外数据


class RelayProtocol:
    """消息协议工具"""
    
    @staticmethod
    def create_message(
        msg_type: MessageType,
        data: Dict[str, Any],
        msg_id: Optional[str] = None,
        from_id: Optional[str] = None,
        to_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """创建JSON消息"""
        message = {
            "type": msg_type.value,
            "id": msg_id or str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "data": data
        }
        
        if from_id:
            message["from"] = from_id
        if to_id:
            message["to"] = to_id
        if session_id:
            message["session"] = session_id
            
        return json.dumps(message, ensure_ascii=False)
    
    @staticmethod
    def parse_message(raw: str) -> Optional[Dict[str, Any]]:
        """解析JSON消息"""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse message: {raw[:100]}")
            return None
    
    @staticmethod
    def create_error(code: int, message: str) -> str:
        """创建错误消息"""
        return RelayProtocol.create_message(
            MessageType.ERROR,
            {"code": code, "message": message}
        )
    
    @staticmethod
    def create_notification(message: str, level: str = "info") -> str:
        """创建通知消息"""
        return RelayProtocol.create_message(
            MessageType.NOTIFICATION,
            {"message": message, "level": level}
        )


class RelayServer:
    """WebSocket中继服务器"""
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        max_connections: int = 1000,
        session_timeout: int = 3600,
        ping_interval: int = 30,
        ping_timeout: int = 60
    ):
        self.host = host
        self.port = port
        
        # 连接管理
        self.clients: Dict[str, Client] = {}  # client_id -> Client
        self.connections: Dict[str, str] = {}  # websocket_id -> client_id
        
        # 会话管理
        self.sessions: Dict[str, Session] = {}  # session_id -> Session
        
        # 配置
        self.max_connections = max_connections
        self.session_timeout = session_timeout
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        
        # 服务器
        self.server = None
        self.is_running = False
        
        # 统计
        self.stats = {
            "total_connections": 0,
            "total_messages": 0,
            "total_sessions": 0,
            "start_time": time.time()
        }
        
        # 回调函数
        self.on_client_connected: Optional[Callable] = None
        self.on_client_disconnected: Optional[Callable] = None
        self.on_message_received: Optional[Callable] = None
        self.on_session_created: Optional[Callable] = None
    
    def generate_session_id(self) -> str:
        """生成唯一会话ID（6位字母数字）"""
        return secrets.token_hex(3).upper()
    
    def generate_client_id(self) -> str:
        """生成唯一客户端ID"""
        return str(uuid.uuid4())
    
    async def register_client(self, websocket: Any, name: str = "", client_type: str = "desktop") -> Client:
        """注册新客户端"""
        client_id = self.generate_client_id()
        client = Client(
            id=client_id,
            websocket=websocket,
            name=name or f"User_{client_id[:8]}",
            client_type=client_type
        )
        
        self.clients[client_id] = client
        self.connections[id(websocket)] = client_id
        self.stats["total_connections"] += 1
        
        logger.info(f"Client registered: {client.name} ({client_id})")
        
        if self.on_client_connected:
            await self.on_client_connected(client)
        
        return client
    
    async def unregister_client(self, client_id: str):
        """注销客户端"""
        if client_id not in self.clients:
            return
        
        client = self.clients[client_id]
        
        # 离开所有会话
        for session_id in list(client.sessions):
            await self.leave_session(client_id, session_id)
        
        # 清理连接映射
        self.connections.pop(id(client.websocket), None)
        
        # 删除客户端
        del self.clients[client_id]
        
        logger.info(f"Client unregistered: {client.name} ({client_id})")
        
        if self.on_client_disconnected:
            await self.on_client_disconnected(client)
    
    async def create_session(self, host_id: str, name: str = "", password: str = "", max_clients: int = 10) -> Optional[Session]:
        """创建新会话"""
        if host_id not in self.clients:
            return None
        
        # 生成唯一会话ID
        attempts = 0
        while attempts < 10:
            session_id = self.generate_session_id()
            if session_id not in self.sessions:
                break
            attempts += 1
        else:
            return None
        
        session = Session(
            id=session_id,
            name=name or f"Session_{session_id}",
            host_id=host_id,
            password=password,
            max_clients=max_clients
        )
        
        self.sessions[session_id] = session
        self.stats["total_sessions"] += 1
        
        # 自动加入会话
        session.clients.add(host_id)
        self.clients[host_id].sessions.add(session_id)
        
        logger.info(f"Session created: {session_id} by {host_id}")
        
        if self.on_session_created:
            await self.on_session_created(session)
        
        return session
    
    async def join_session(self, client_id: str, session_id: str, password: str = "") -> bool:
        """加入会话"""
        if client_id not in self.clients:
            return False
        
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        client = self.clients[client_id]
        
        # 检查密码
        if session.password and session.password != password:
            return False
        
        # 检查人数限制
        if len(session.clients) >= session.max_clients:
            return False
        
        # 加入会话
        session.clients.add(client_id)
        client.sessions.add(session_id)
        
        logger.info(f"Client {client_id} joined session {session_id}")
        
        # 通知其他成员
        await self.broadcast_to_session(
            session_id,
            RelayProtocol.create_message(
                MessageType.SESSION_JOINED,
                {
                    "client_id": client_id,
                    "client_name": client.name,
                    "client_type": client.client_type
                },
                session_id=session_id
            ),
            exclude=[client_id]
        )
        
        return True
    
    async def leave_session(self, client_id: str, session_id: str):
        """离开会话"""
        if client_id not in self.clients or session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        client = self.clients[client_id]
        
        session.clients.discard(client_id)
        client.sessions.discard(session_id)
        
        logger.info(f"Client {client_id} left session {session_id}")
        
        # 如果会话为空，删除会话
        if not session.clients:
            del self.sessions[session_id]
            logger.info(f"Session {session_id} deleted (empty)")
            return
        
        # 通知其他成员
        await self.broadcast_to_session(
            session_id,
            RelayProtocol.create_message(
                MessageType.SESSION_LEFT,
                {"client_id": client_id, "client_name": client.name},
                session_id=session_id
            ),
            exclude=[client_id]
        )
    
    async def relay_message(self, from_id: str, to_id: str, data: Dict[str, Any]):
        """点对点消息转发"""
        if from_id not in self.clients or to_id not in self.clients:
            return
        
        from_client = self.clients[from_id]
        to_client = self.clients[to_id]
        
        message = RelayProtocol.create_message(
            MessageType.RELAY_MESSAGE,
            data,
            from_id=from_id,
            to_id=to_id
        )
        
        await self._send_to_client(to_client, message)
        self.stats["total_messages"] += 1
    
    async def broadcast_to_session(self, session_id: str, message: str, exclude: list = None):
        """向会话内所有客户端广播消息"""
        if session_id not in self.sessions:
            return
        
        exclude = exclude or []
        session = self.sessions[session_id]
        
        for client_id in session.clients:
            if client_id in exclude:
                continue
            if client_id in self.clients:
                await self._send_to_client(self.clients[client_id], message)
        
        self.stats["total_messages"] += len(session.clients) - len(exclude)
    
    async def send_to_client(self, client_id: str, message: str):
        """向指定客户端发送消息"""
        if client_id in self.clients:
            await self._send_to_client(self.clients[client_id], message)
    
    async def _send_to_client(self, client: Client, message: str):
        """发送消息到客户端"""
        try:
            await client.websocket.send(message)
        except Exception as e:
            logger.error(f"Failed to send to {client.id}: {e}")
    
    async def handle_ping(self, client: Client):
        """处理心跳"""
        client.last_ping = time.time()
        await self._send_to_client(
            client,
            RelayProtocol.create_message(MessageType.PONG, {"server_time": int(time.time() * 1000)})
        )
    
    async def handle_register(self, client: Client, data: Dict[str, Any]):
        """处理注册"""
        client.name = data.get("name", client.name)
        client.client_type = data.get("client_type", client.client_type)
        client.is_authenticated = True
        client.metadata = data.get("metadata", {})
        
        await self._send_to_client(
            client,
            RelayProtocol.create_message(
                MessageType.REGISTER,
                {
                    "client_id": client.id,
                    "name": client.name,
                    "client_type": client.client_type
                }
            )
        )
    
    async def handle_create_session(self, client: Client, data: Dict[str, Any]):
        """处理创建会话"""
        session = await self.create_session(
            host_id=client.id,
            name=data.get("name", ""),
            password=data.get("password", ""),
            max_clients=data.get("max_clients", 10)
        )
        
        if session:
            await self._send_to_client(
                client,
                RelayProtocol.create_message(
                    MessageType.SESSION_CREATED,
                    {
                        "session_id": session.id,
                        "session_name": session.name,
                        "max_clients": session.max_clients
                    }
                )
            )
        else:
            await self._send_to_client(
                client,
                RelayProtocol.create_error(500, "Failed to create session")
            )
    
    async def handle_join_session(self, client: Client, data: Dict[str, Any]):
        """处理加入会话"""
        session_id = data.get("session_id", "")
        password = data.get("password", "")
        
        success = await self.join_session(client.id, session_id, password)
        
        if success:
            session = self.sessions.get(session_id)
            members = []
            for cid in session.clients:
                if cid in self.clients:
                    members.append({
                        "client_id": cid,
                        "name": self.clients[cid].name,
                        "client_type": self.clients[cid].client_type
                    })
            
            await self._send_to_client(
                client,
                RelayProtocol.create_message(
                    MessageType.SESSION_JOINED,
                    {
                        "session_id": session_id,
                        "members": members
                    }
                )
            )
        else:
            await self._send_to_client(
                client,
                RelayProtocol.create_error(404, f"Session {session_id} not found or access denied")
            )
    
    async def handle_relay_message(self, client: Client, message: Dict[str, Any]):
        """处理中继消息"""
        data = message.get("data", {})
        to_id = data.get("to")
        
        if to_id:
            await self.relay_message(client.id, to_id, data)
        else:
            # 广播到所属会话
            for session_id in client.sessions:
                await self.broadcast_to_session(
                    session_id,
                    RelayProtocol.create_message(
                        MessageType.RELAY_MESSAGE,
                        {**data, "from_name": client.name},
                        from_id=client.id,
                        session_id=session_id
                    ),
                    exclude=[client.id]
                )
        
        if self.on_message_received:
            await self.on_message_received(client, message)
    
    async def handle_message(self, websocket: Any):
        """处理WebSocket消息"""
        # 获取客户端ID
        conn_id = id(websocket)
        if conn_id not in self.connections:
            # 自动注册
            client = await self.register_client(websocket)
        else:
            client = self.clients[self.connections[conn_id]]
        
        try:
            async for raw_message in websocket:
                message = RelayProtocol.parse_message(raw_message)
                if not message:
                    continue
                
                msg_type = message.get("type", "")
                
                # 处理不同类型的消息
                if msg_type == MessageType.PING.value:
                    await self.handle_ping(client)
                
                elif msg_type == MessageType.REGISTER.value:
                    await self.handle_register(client, message.get("data", {}))
                
                elif msg_type == MessageType.CREATE_SESSION.value:
                    await self.handle_create_session(client, message.get("data", {}))
                
                elif msg_type == MessageType.JOIN_SESSION.value:
                    await self.handle_join_session(client, message.get("data", {}))
                
                elif msg_type == MessageType.LEAVE_SESSION.value:
                    session_id = message.get("data", {}).get("session_id")
                    if session_id:
                        await self.leave_session(client.id, session_id)
                
                elif msg_type == MessageType.RELAY_MESSAGE.value:
                    await self.handle_relay_message(client, message)
                
                elif msg_type == MessageType.UNREGISTER.value:
                    await self.unregister_client(client.id)
                    break
                
                else:
                    logger.warning(f"Unknown message type: {msg_type}")
                    
        except ConnectionClosed as e:
            logger.info(f"Connection closed: {client.name} - {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
        finally:
            await self.unregister_client(client.id)
    
    async def check_timeout(self):
        """检查超时连接"""
        now = time.time()
        timeout_clients = []
        
        for client_id, client in self.clients.items():
            if now - client.last_ping > self.ping_timeout:
                timeout_clients.append(client_id)
        
        for client_id in timeout_clients:
            logger.warning(f"Client timeout: {client_id}")
            await self.unregister_client(client_id)
    
    async def cleanup_sessions(self):
        """清理过期会话"""
        now = time.time()
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if now - session.created_at > self.session_timeout and not session.clients:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
            logger.info(f"Session expired: {session_id}")
    
    async def heartbeat(self):
        """心跳任务"""
        while self.is_running:
            await asyncio.sleep(self.ping_interval)
            
            # 发送ping
            for client_id, client in list(self.clients.items()):
                try:
                    await self._send_to_client(
                        client,
                        RelayProtocol.create_message(MessageType.PING, {})
                    )
                except Exception as e:
                    logger.warning(f"Failed to ping {client_id}: {e}")
            
            # 检查超时
            await self.check_timeout()
    
    async def start(self):
        """启动服务器"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets library not available")
            return
        
        self.is_running = True
        
        # 启动心跳任务
        asyncio.create_task(self.heartbeat())
        
        # 启动清理任务
        asyncio.create_task(self._cleanup_loop())
        
        # 启动服务器
        logger.info(f"Starting WebSocket Relay Server on {self.host}:{self.port}")
        
        self.server = await serve(
            self.handle_message,
            self.host,
            self.port,
            ping_interval=None,  # 我们自己处理心跳
            ping_timeout=None
        )
        
        logger.info(f"Server started successfully!")
    
    async def _cleanup_loop(self):
        """定期清理任务"""
        while self.is_running:
            await asyncio.sleep(60)
            await self.cleanup_sessions()
    
    async def stop(self):
        """停止服务器"""
        self.is_running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("Server stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "online_clients": len(self.clients),
            "active_sessions": len(self.sessions),
            "uptime": time.time() - self.stats["start_time"]
        }


async def run_server(host: str = "0.0.0.0", port: int = 8765):
    """运行服务器"""
    server = RelayServer(host=host, port=port)
    
    try:
        await server.start()
        
        # 保持运行
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await server.stop()


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="Hermes WebSocket Relay Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind")
    parser.add_argument("--max-connections", type=int, default=1000, help="Max connections")
    parser.add_argument("--session-timeout", type=int, default=3600, help="Session timeout in seconds")
    
    args = parser.parse_args()
    
    asyncio.run(run_server(
        host=args.host,
        port=args.port
    ))


if __name__ == "__main__":
    main()
