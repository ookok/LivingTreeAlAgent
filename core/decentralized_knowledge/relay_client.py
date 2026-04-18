"""
中继客户端
Relay Client for P2P Network
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, Callable
import secrets

logger = logging.getLogger(__name__)


class RelayMessageType(Enum):
    """中继消息类型"""
    REGISTER = "register"
    UNREGISTER = "unregister"
    PING = "ping"
    PONG = "pong"
    FORWARD = "forward"
    BROADCAST = "broadcast"
    PEER_DISCOVER = "peer_discover"
    PEER_RESPONSE = "peer_response"


@dataclass
class RelayMessage:
    """中继消息"""
    msg_type: RelayMessageType
    sender_id: str
    payload: Dict[str, Any]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class RelayClient:
    """
    中继客户端
    
    功能：
    - 节点注册
    - 消息转发
    - P2P穿透辅助
    - 心跳检测
    """
    
    HEARTBEAT_INTERVAL = 30  # 秒
    HEARTBEAT_TIMEOUT = 90  # 秒
    RECONNECT_DELAY = 5     # 秒
    
    def __init__(self, config):
        self.config = config
        
        # 连接状态
        self._connected = False
        self._running = False
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        
        # 节点信息
        self._node_id = config.node_id or secrets.token_urlsafe(16)
        self._server_addr: Optional[tuple] = None
        
        # 心跳
        self._last_pong: Optional[datetime] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # 回调
        self._message_callbacks: Dict[str, Callable] = {}
        
        # 锁
        self._lock = asyncio.Lock()
        
        logger.info(f"中继客户端初始化完成，节点ID: {self._node_id[:8]}...")
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    async def connect(self) -> bool:
        """
        连接到中继服务器
        
        Returns:
            bool: 是否成功
        """
        if self._connected:
            logger.warning("已经连接到中继服务器")
            return True
        
        # 获取服务器地址
        server = self._select_server()
        if not server:
            logger.error("没有可用的中继服务器")
            return False
        
        try:
            host = server['host']
            port = server['port']
            
            logger.info(f"正在连接中继服务器: {host}:{port}")
            
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=10
            )
            
            self._server_addr = (host, port)
            
            # 注册节点
            success = await self._register()
            
            if success:
                self._connected = True
                self._running = True
                
                # 启动心跳
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                
                # 启动消息接收循环
                asyncio.create_task(self._receive_loop())
                
                logger.info(f"成功连接到中继服务器: {host}:{port}")
                return True
            else:
                await self._disconnect()
                return False
                
        except asyncio.TimeoutError:
            logger.error("连接中继服务器超时")
            return False
        except Exception as e:
            logger.error(f"连接中继服务器失败: {e}")
            return False
    
    async def _disconnect(self) -> None:
        """断开连接"""
        if self._writer:
            try:
                await self._unregister()
            except:
                pass
            
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None
        
        self._connected = False
        self._server_addr = None
    
    def _select_server(self) -> Optional[Dict[str, Any]]:
        """选择最佳服务器"""
        servers = self.config.relay_servers
        if not servers:
            return None
        
        # 简单实现：返回第一个
        # 实际应该根据延迟、负载等选择
        return servers[0] if servers else None
    
    async def _send_message(self, message: RelayMessage) -> bool:
        """发送消息"""
        if not self._writer or not self._connected:
            return False
        
        try:
            data = json.dumps({
                'type': message.msg_type.value,
                'sender_id': message.sender_id,
                'payload': message.payload,
                'timestamp': message.timestamp.isoformat()
            })
            
            self._writer.write(f"{data}\n".encode('utf-8'))
            await self._writer.drain()
            return True
            
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False
    
    async def _receive_loop(self) -> None:
        """接收消息循环"""
        while self._running and self._connected:
            try:
                if not self._reader:
                    break
                
                line = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=30
                )
                
                if not line:
                    break
                
                try:
                    data = json.loads(line.decode('utf-8'))
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"无效的JSON消息: {line}")
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"接收消息错误: {e}")
                break
        
        # 连接断开
        self._connected = False
        logger.warning("与中继服务器的连接已断开")
        
        # 尝试重连
        if self._running:
            asyncio.create_task(self._reconnect())
    
    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """处理接收到的消息"""
        msg_type = data.get('type')
        payload = data.get('payload', {})
        
        if msg_type == RelayMessageType.PONG.value:
            self._last_pong = datetime.now()
        
        elif msg_type == RelayMessageType.FORWARD.value:
            # 收到转发的消息
            sender_id = data.get('sender_id')
            content = payload.get('content', {})
            
            # 触发回调
            callback = self._message_callbacks.get('forward')
            if callback:
                try:
                    await callback(sender_id, content)
                except Exception as e:
                    logger.error(f"消息回调失败: {e}")
        
        elif msg_type == RelayMessageType.PEER_RESPONSE.value:
            # 收到节点发现响应
            peers = payload.get('peers', [])
            callback = self._message_callbacks.get('peer_discover')
            if callback:
                try:
                    await callback(peers)
                except Exception as e:
                    logger.error(f"节点发现回调失败: {e}")
    
    async def _register(self) -> bool:
        """注册节点"""
        message = RelayMessage(
            msg_type=RelayMessageType.REGISTER,
            sender_id=self._node_id,
            payload={
                'node_id': self._node_id,
                'timestamp': datetime.now().isoformat()
            }
        )
        
        success = await self._send_message(message)
        
        if success:
            logger.info(f"节点注册成功: {self._node_id[:8]}...")
        
        return success
    
    async def _unregister(self) -> None:
        """注销节点"""
        message = RelayMessage(
            msg_type=RelayMessageType.UNREGISTER,
            sender_id=self._node_id,
            payload={'node_id': self._node_id}
        )
        
        try:
            await self._send_message(message)
        except:
            pass
    
    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        while self._running and self._connected:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                
                message = RelayMessage(
                    msg_type=RelayMessageType.PING,
                    sender_id=self._node_id,
                    payload={}
                )
                
                if not await self._send_message(message):
                    logger.warning("心跳发送失败")
                    break
                
                # 检查超时
                if self._last_pong:
                    elapsed = (datetime.now() - self._last_pong).total_seconds()
                    if elapsed > self.HEARTBEAT_TIMEOUT:
                        logger.warning("心跳超时，断开连接")
                        break
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳循环错误: {e}")
                break
        
        self._connected = False
    
    async def _reconnect(self) -> None:
        """重连"""
        logger.info(f"等待 {self.RECONNECT_DELAY} 秒后尝试重连...")
        
        for attempt in range(10):
            if not self._running:
                break
            
            await asyncio.sleep(self.RECONNECT_DELAY)
            
            logger.info(f"尝试重连 (第 {attempt + 1} 次)...")
            
            if await self.connect():
                logger.info("重连成功")
                return
        
        logger.error("重连失败，停止重试")
    
    async def disconnect(self) -> None:
        """断开与中继服务器的连接"""
        self._running = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        await self._disconnect()
        
        logger.info("已断开与中继服务器的连接")
    
    async def forward_message(self, recipient: str, content: Any) -> bool:
        """
        转发消息到指定节点
        
        Args:
            recipient: 接收者ID
            content: 消息内容
        
        Returns:
            bool: 是否成功
        """
        message = RelayMessage(
            msg_type=RelayMessageType.FORWARD,
            sender_id=self._node_id,
            payload={
                'recipient': recipient,
                'content': content
            }
        )
        
        return await self._send_message(message)
    
    async def broadcast(self, content: Any) -> bool:
        """
        广播消息
        
        Args:
            content: 消息内容
        
        Returns:
            bool: 是否成功
        """
        message = RelayMessage(
            msg_type=RelayMessageType.BROADCAST,
            sender_id=self._node_id,
            payload={'content': content}
        )
        
        return await self._send_message(message)
    
    async def discover_peers(self) -> bool:
        """
        发现其他节点
        
        Returns:
            bool: 请求是否成功
        """
        message = RelayMessage(
            msg_type=RelayMessageType.PEER_DISCOVER,
            sender_id=self._node_id,
            payload={}
        )
        
        return await self._send_message(message)
    
    def add_message_callback(self, msg_type: str, 
                             callback: Callable) -> None:
        """添加消息回调"""
        self._message_callbacks[msg_type] = callback
    
    def remove_message_callback(self, msg_type: str) -> None:
        """移除消息回调"""
        self._message_callbacks.pop(msg_type, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'connected': self._connected,
            'server': f"{self._server_addr[0]}:{self._server_addr[1]}" if self._server_addr else None,
            'node_id': self._node_id,
            'last_pong': self._last_pong.isoformat() if self._last_pong else None,
            'uptime': (datetime.now() - self._last_pong).total_seconds() if self._last_pong else 0
        }
