"""
多通道通信管理器

管理不同类型的通信通道: 文本/文件/语音/视频/直播/邮件

配置来源：NanochatConfig (client/src/business/nanochat_config.py)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Dict, List

from .models import (ChannelType, ChannelSession, P2PConnection, 
                    ConnectionStatus, NodeProfile)
from business.nanochat_config import config

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """通信消息"""
    msg_id: str
    channel_type: ChannelType
    sender_id: str
    recipient_id: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)
    
    # 文件传输
    file_name: Optional[str] = None
    file_size: int = 0
    file_path: Optional[str] = None
    
    # 状态
    delivered: bool = False
    read: bool = False


class MultiChannelManager:
    """
    多通道通信管理器
    
    功能:
    - 通道创建与关闭
    - 消息路由
    - 文件/大附件传输
    - 音视频流管理
    - 直播流推送
    """
    
    def __init__(self, node_id: str, crypto=None):
        self.node_id = node_id
        self.crypto = crypto  # 加密器
        
        # 连接管理
        self._connections: Dict[str, P2PConnection] = {}  # connection_id -> connection
        self._peer_connections: Dict[str, str] = {}  # peer_node_id -> connection_id
        
        # 通道会话
        self._channels: Dict[str, ChannelSession] = {}  # session_id -> session
        
        # 消息队列
        self._message_queue: Dict[str, List[Message]] = {}  # connection_id -> messages
        
        # 回调函数
        self._on_message: Optional[Callable] = None
        self._on_file_progress: Optional[Callable] = None
        self._on_connection_status: Optional[Callable] = None
        self._on_channel_status: Optional[Callable] = None
        
        # 传输配置
        self._file_chunk_size = 64 * 1024  # 64KB
        self._max_retries = 3
        
        # P2P通信 (复用)
        self._p2p_protocol = None
        self._relay_client = None
    
    # ========== 连接管理 ==========
    
    async def create_connection(self, peer: NodeProfile) -> str:
        """
        创建到对端的连接
        
        Args:
            peer: 对端节点档案
            
        Returns:
            str: connection_id
        """
        import secrets
        
        connection_id = secrets.token_hex(8)
        
        # 创建连接对象
        connection = P2PConnection(
            connection_id=connection_id,
            peer_node_id=peer.node_id,
            peer_short_id=peer.short_id,
            active_channels=[],
            status=ConnectionStatus.CONNECTING,
            peer_addr=f"{peer.public_ip}:{peer.public_port}" if peer.public_ip else None,
            via_relay=len(peer.relay_hosts) > 0
        )
        
        self._connections[connection_id] = connection
        self._peer_connections[peer.node_id] = connection_id
        
        # 选择最佳通道建立连接
        success = await self._establish_connection(connection, peer)
        
        if success:
            connection.status = ConnectionStatus.CONNECTED
            connection.connected_at = time.time()
        else:
            connection.status = ConnectionStatus.ERROR
        
        if self._on_connection_status:
            self._on_connection_status(connection_id, connection.status)
        
        return connection_id
    
    async def _establish_connection(self, connection: P2PConnection, 
                                    peer: NodeProfile) -> bool:
        """建立连接"""
        # 1. 尝试直连
        if peer.public_ip and peer.public_port:
            success = await self._try_direct_connect(connection, peer)
            if success:
                logger.info(f"Direct connection established to {peer.short_id}")
                return True
        
        # 2. 尝试P2P穿透
        success = await self._try_p2p_connect(connection, peer)
        if success:
            logger.info(f"P2P connection established to {peer.short_id}")
            return True
        
        # 3. 回退到中继
        success = await self._try_relay_connect(connection, peer)
        if success:
            logger.info(f"Relay connection established to {peer.short_id}")
            return True
        
        logger.warning(f"All connection attempts failed for {peer.short_id}")
        return False
    
    async def _try_direct_connect(self, connection: P2PConnection, 
                                   peer: NodeProfile) -> bool:
        """尝试直连"""
        try:
            import socket
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            
            loop = asyncio.get_event_loop()
            await loop.sock_connect(sock, (peer.public_ip, peer.public_port))
            
            # 发送握手
            handshake = json.dumps({
                "type": "connect",
                "node_id": self.node_id,
                "connection_id": connection.connection_id,
                "timestamp": time.time()
            })
            
            await loop.sock_sendall(sock, handshake.encode())
            
            # 等待响应
            response = await loop.sock_recv(sock, 1024)
            
            if response:
                connection.peer_addr = f"{peer.public_ip}:{peer.public_port}"
                connection.via_relay = False
                sock.close()
                return True
            
            sock.close()
            
        except Exception as e:
            logger.debug(f"Direct connect failed: {e}")
        
        return False
    
    async def _try_p2p_connect(self, connection: P2PConnection,
                               peer: NodeProfile) -> bool:
        """尝试P2P穿透连接"""
        try:
            from business.p2p_knowledge.nat_traversal import NATTraversal
            
            nat = NATTraversal()
            result = await nat.try_hole_punch(peer.public_ip, peer.public_port)
            
            if result.success:
                connection.peer_addr = f"{result.mapped_addr[0]}:{result.mapped_addr[1]}"
                connection.via_relay = False
                return True
                
        except Exception as e:
            logger.debug(f"P2P connect failed: {e}")
        
        return False
    
    async def _try_relay_connect(self, connection: P2PConnection,
                                 peer: NodeProfile) -> bool:
        """尝试中继连接"""
        try:
            if not peer.relay_hosts:
                return False
            
            from business.relay_client import AsyncRelayClient
            
            relay_host = peer.relay_hosts[0].split(":")
            host = relay_host[0]
            port = int(relay_host[1]) if len(relay_host) > 1 else 8888
            
            server_url = f"ws://{host}:{port}"
            client = AsyncRelayClient(server_url)
            
            await client.connect()
            
            if client.state == "connected" or client.state.value == "connected":
                connection.relay_server = f"{host}:{port}"
                connection.via_relay = True
                
                await client.send({
                    "type": "connect_request",
                    "connection_id": connection.connection_id,
                    "from_node": self.node_id
                })
                
                return True
                
        except Exception as e:
            logger.debug(f"Relay connect failed: {e}")
        
        return False
    
    async def close_connection(self, connection_id: str):
        """关闭连接"""
        if connection_id in self._connections:
            conn = self._connections[connection_id]
            peer_id = conn.peer_node_id
            
            # 关闭所有通道
            for channel in conn.active_channels:
                await self.close_channel(f"{connection_id}:{channel.value}")
            
            # 清理
            self._peer_connections.pop(peer_id, None)
            self._connections.pop(connection_id, None)
            
            logger.info(f"Connection closed: {connection_id}")
    
    def get_connection(self, connection_id: str = None, 
                       peer_node_id: str = None) -> Optional[P2PConnection]:
        """获取连接"""
        if connection_id:
            return self._connections.get(connection_id)
        if peer_node_id:
            conn_id = self._peer_connections.get(peer_node_id)
            return self._connections.get(conn_id)
        return None
    
    # ========== 通道管理 ==========
    
    async def open_channel(self, connection_id: str, 
                           channel_type: ChannelType) -> Optional[str]:
        """
        打开通信通道
        
        Args:
            connection_id: 连接ID
            channel_type: 通道类型
            
        Returns:
            str: session_id or None
        """
        import secrets
        
        connection = self._connections.get(connection_id)
        if not connection:
            logger.error(f"Connection not found: {connection_id}")
            return None
        
        session_id = f"{connection_id}:{channel_type.value}"
        
        # 检查是否已存在
        if session_id in self._channels:
            return session_id
        
        # 创建通道会话
        session = ChannelSession(
            session_id=session_id,
            connection_id=connection_id,
            channel_type=channel_type,
            status="active"
        )
        
        self._channels[session_id] = session
        connection.active_channels.append(channel_type)
        
        # 根据通道类型初始化
        if channel_type == ChannelType.FILE:
            pass  # 文件传输不需要额外初始化
        
        elif channel_type in (ChannelType.VOICE, ChannelType.VIDEO):
            # TODO: 初始化音视频
            pass
        
        elif channel_type == ChannelType.LIVE:
            session.status = "pending"
            # TODO: 初始化直播
        
        if self._on_channel_status:
            self._on_channel_status(session_id, "opened")
        
        logger.info(f"Channel opened: {session_id}")
        return session_id
    
    async def close_channel(self, session_id: str):
        """关闭通道"""
        if session_id in self._channels:
            session = self._channels[session_id]
            connection = self._connections.get(session.connection_id)
            
            if connection:
                if session.channel_type in connection.active_channels:
                    connection.active_channels.remove(session.channel_type)
            
            self._channels.pop(session_id)
            
            if self._on_channel_status:
                self._on_channel_status(session_id, "closed")
            
            logger.info(f"Channel closed: {session_id}")
    
    # ========== 消息发送 ==========
    
    async def send_message(self, recipient_id: str, content: str,
                          channel_type: ChannelType = ChannelType.TEXT,
                          metadata: dict = None) -> Optional[str]:
        """
        发送消息
        
        Args:
            recipient_id: 收件人节点ID
            content: 消息内容
            channel_type: 通道类型
            metadata: 元数据
            
        Returns:
            str: msg_id or None
        """
        import secrets
        
        # 获取或创建连接
        connection = self.get_connection(peer_node_id=recipient_id)
        
        if not connection:
            # 需要先解析短ID获取节点信息
            # 这里简化处理, 假设已有节点档案
            logger.warning(f"No connection to {recipient_id[:16]}...")
            return None
        
        # 创建消息
        msg_id = secrets.token_hex(8)
        message = Message(
            msg_id=msg_id,
            channel_type=channel_type,
            sender_id=self.node_id,
            recipient_id=recipient_id,
            content=content,
            metadata=metadata or {}
        )
        
        # 根据通道类型发送
        if channel_type == ChannelType.TEXT:
            success = await self._send_text_message(connection, message)
        elif channel_type == ChannelType.FILE:
            success = await self._send_file_message(connection, message)
        elif channel_type in (ChannelType.VOICE, ChannelType.VIDEO):
            success = await self._send_media_message(connection, message)
        else:
            success = False
        
        if success:
            return msg_id
        
        return None
    
    async def _send_text_message(self, connection: P2PConnection,
                                  message: Message) -> bool:
        """发送文本消息"""
        try:
            payload = {
                "type": "message",
                "msg_id": message.msg_id,
                "channel": "text",
                "content": message.content,
                "timestamp": message.timestamp,
                "metadata": message.metadata
            }
            
            return await self._send_payload(connection, payload)
            
        except Exception as e:
            logger.error(f"Send text message failed: {e}")
            return False
    
    async def _send_file_message(self, connection: P2PConnection,
                                 message: Message) -> bool:
        """发送文件消息"""
        try:
            # 分片发送
            if message.file_path:
                from pathlib import Path
                import hashlib
                
                file_data = Path(message.file_path).read_bytes()
                file_hash = hashlib.sha256(file_data).hexdigest()
                
                total_chunks = (len(file_data) + self._file_chunk_size - 1) // self._file_chunk_size
                
                # 发送文件头
                header = {
                    "type": "file_header",
                    "msg_id": message.msg_id,
                    "file_name": message.file_name,
                    "file_size": len(file_data),
                    "file_hash": file_hash,
                    "total_chunks": total_chunks
                }
                
                await self._send_payload(connection, header)
                
                # 分片发送
                for i in range(total_chunks):
                    chunk = file_data[i * self._file_chunk_size:(i + 1) * self._file_chunk_size]
                    
                    chunk_payload = {
                        "type": "file_chunk",
                        "msg_id": message.msg_id,
                        "chunk_index": i,
                        "data": chunk.hex(),
                        "hash": hashlib.sha256(chunk).hexdigest()
                    }
                    
                    await self._send_payload(connection, chunk_payload)
                    
                    # 更新进度
                    if self._on_file_progress:
                        self._on_file_progress(message.msg_id, i + 1, total_chunks)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Send file message failed: {e}")
            return False
    
    async def _send_media_message(self, connection: P2PConnection,
                                  message: Message) -> bool:
        """发送音视频消息"""
        # TODO: 实现音视频流
        return False
    
    async def _send_payload(self, connection: P2PConnection, 
                            payload: dict) -> bool:
        """发送数据负载"""
        try:
            data = json.dumps(payload).encode()
            
            if connection.via_relay and connection.relay_server:
                # 通过中继发送
                # TODO: 使用 relay_client
                pass
            else:
                # 直接发送
                # TODO: 使用 socket
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"Send payload failed: {e}")
            return False
    
    # ========== 消息接收 ==========
    
    async def handleIncomingMessage(self, connection_id: str, data: dict):
        """处理收到的消息"""
        msg_type = data.get("type")
        
        if msg_type == "message":
            message = Message(
                msg_id=data["msg_id"],
                channel_type=ChannelType.TEXT,
                sender_id=data.get("sender_id", ""),
                recipient_id=self.node_id,
                content=data.get("content", ""),
                timestamp=data.get("timestamp", time.time())
            )
            
            if self._on_message:
                self._on_message(message)
        
        elif msg_type == "file_header":
            # 接收文件头
            session_id = f"{connection_id}:file"
            if session_id in self._channels:
                session = self._channels[session_id]
                session.file_name = data.get("file_name")
                session.file_size = data.get("file_size")
        
        elif msg_type == "file_chunk":
            # 接收文件分片
            # TODO: 组装文件
            pass
        
        elif msg_type == "connect_request":
            # 处理连接请求
            await self._handle_connect_request(connection_id, data)
    
    async def _handle_connect_request(self, connection_id: str, data: dict):
        """处理连接请求"""
        from_node = data.get("from_node")
        
        # 发送确认
        payload = {
            "type": "connect_ack",
            "connection_id": connection_id,
            "from_node": self.node_id
        }
        
        connection = self._connections.get(connection_id)
        if connection:
            await self._send_payload(connection, payload)
    
    # ========== 回调设置 ==========
    
    def set_callbacks(self, **kwargs):
        """设置回调函数"""
        self._on_message = kwargs.get("on_message")
        self._on_file_progress = kwargs.get("on_file_progress")
        self._on_connection_status = kwargs.get("on_connection_status")
        self._on_channel_status = kwargs.get("on_channel_status")
    
    # ========== 状态查询 ==========
    
    def get_active_connections(self) -> List[P2PConnection]:
        """获取所有活跃连接"""
        return [c for c in self._connections.values() if c.is_active]
    
    def get_connection_channels(self, connection_id: str) -> List[ChannelSession]:
        """获取连接的所有通道"""
        return [s for s in self._channels.values() 
                if s.connection_id == connection_id]
