"""
消息投递与路由

实现P2P消息路由、中继转发、离线存储
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Dict, List

from .models import MailMessage, MailboxAddress, MessageStatus, DeliveryReceipt

# 导入配置
try:
    from core.config.unified_config import get_config
except ImportError:
    get_config = None

logger = logging.getLogger(__name__)


class DeliveryStatus(Enum):
    """投递状态"""
    PENDING = "pending"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    FAILED = "failed"
    OFFLINE_QUEUED = "offline_queued"


@dataclass
class RouteResult:
    """路由结果"""
    success: bool
    status: DeliveryStatus
    delivery_time: float = 0
    relay_node: Optional[str] = None
    direct_connection: bool = False
    error_message: Optional[str] = None


@dataclass
class PendingMessage:
    """待投递消息"""
    message: MailMessage
    recipient: MailboxAddress
    attempts: int = 0
    max_attempts: int = None  # 从配置读取
    next_retry: float = 0
    status: DeliveryStatus = DeliveryStatus.PENDING
    receipts: list[DeliveryReceipt] = field(default_factory=list)
    
    def __post_init__(self):
        if self.max_attempts is None:
            if get_config:
                self.max_attempts = get_config().get("message.max_delivery_attempts", 3)
            else:
                self.max_attempts = 3


class MessageRouter:
    """
    消息路由与投递
    
    功能:
    - P2P直接投递
    - 中继节点转发
    - 离线消息队列
    - 投递回执
    """
    
    # 中继服务器配置
    DEFAULT_RELAY_HOST = "139.199.124.242"
    DEFAULT_RELAY_PORT = 8888
    
    def __init__(self, node_id: str, relay_config: dict = None):
        self.node_id = node_id
        
        # 中继配置
        self.relay_config = relay_config or {
            "host": self.DEFAULT_RELAY_HOST,
            "port": self.DEFAULT_RELAY_PORT,
            "use_ssl": False,
            "websocket_mode": True
        }
        
        # 投递队列
        self._pending_queue: dict[str, PendingMessage] = {}
        self._offline_queue: dict[str, list[PendingMessage]] = {}  # node_id -> messages
        
        # 连接状态
        self._relay_connected = False
        self._direct_peers: dict[str, tuple[str, int]] = {}  # node_id -> (host, port)
        
        # 回调函数
        self._on_message_delivered: Optional[Callable] = None
        self._on_message_failed: Optional[Callable] = None
        self._on_peer_online: Optional[Callable] = None
        self._on_peer_offline: Optional[Callable] = None
        
        # 投递任务
        self._delivery_task: Optional[asyncio.Task] = None
        self._running = False
        
        # P2P通信 (复用现有组件)
        self._p2p_protocol = None
        self._relay_client = None
    
    async def start(self):
        """启动路由服务"""
        self._running = True
        self._delivery_task = asyncio.create_task(self._delivery_loop())
        logger.info("Message router started")
    
    async def stop(self):
        """停止路由服务"""
        self._running = False
        if self._delivery_task:
            self._delivery_task.cancel()
            try:
                await self._delivery_task
            except asyncio.CancelledError:
                pass
        logger.info("Message router stopped")
    
    def set_callbacks(self, **kwargs):
        """设置回调函数"""
        self._on_message_delivered = kwargs.get("on_delivered")
        self._on_message_failed = kwargs.get("on_failed")
        self._on_peer_online = kwargs.get("on_peer_online")
        self._on_peer_offline = kwargs.get("on_peer_offline")
    
    # ========== 消息投递 ==========
    
    async def send_message(self, message: MailMessage, recipient: MailboxAddress) -> RouteResult:
        """
        发送消息到指定收件人
        
        Args:
            message: 邮件消息
            recipient: 收件人地址
            
        Returns:
            RouteResult: 投递结果
        """
        start_time = time.time()
        
        # 检查目标是否在线
        if self._is_peer_online(recipient.node_id):
            # 直接P2P投递
            return await self._direct_delivery(message, recipient, start_time)
        else:
            # 通过中继转发
            return await self._relay_delivery(message, recipient, start_time)
    
    async def _direct_delivery(self, message: MailMessage, recipient: MailboxAddress, 
                               start_time: float) -> RouteResult:
        """直接P2P投递"""
        try:
            if recipient.node_id in self._direct_peers:
                host, port = self._direct_peers[recipient.node_id]
                
                # 构建消息包
                packet = self._build_message_packet(message, recipient)
                
                # 发送 (使用asyncio UDP)
                success = await self._send_udp_packet(host, port, packet)
                
                if success:
                    delivery_time = time.time() - start_time
                    logger.info(f"Direct delivery to {recipient} succeeded in {delivery_time:.2f}s")
                    
                    return RouteResult(
                        success=True,
                        status=DeliveryStatus.DELIVERED,
                        delivery_time=delivery_time,
                        direct_connection=True
                    )
            
            # 回退到中继
            return await self._relay_delivery(message, recipient, start_time)
            
        except Exception as e:
            logger.error(f"Direct delivery failed: {e}")
            return await self._relay_delivery(message, recipient, start_time)
    
    async def _relay_delivery(self, message: MailMessage, recipient: MailboxAddress,
                             start_time: float) -> RouteResult:
        """通过中继节点转发"""
        try:
            # 构建中继消息
            relay_packet = {
                "type": "mail_message",
                "from_node": self.node_id,
                "to_node": recipient.node_id,
                "to_address": str(recipient),
                "message_id": message.message_id,
                "encrypted_payload": message.body,  # 加密内容
                "metadata": {
                    "subject": message.subject[:100],  # 不加密主题
                    "timestamp": message.created_at,
                    "has_attachments": message.has_attachments
                }
            }
            
            # 发送到中继服务器
            success = await self._send_to_relay(relay_packet)
            
            if success:
                delivery_time = time.time() - start_time
                
                # 检查目标是否在线, 如果不在线则加入离线队列
                if not self._is_peer_online(recipient.node_id):
                    self._queue_offline_message(message, recipient)
                    return RouteResult(
                        success=True,
                        status=DeliveryStatus.OFFLINE_QUEUED,
                        delivery_time=delivery_time,
                        relay_node=f"{self.relay_config['host']}:{self.relay_config['port']}"
                    )
                
                logger.info(f"Relay delivery to {recipient} succeeded in {delivery_time:.2f}s")
                return RouteResult(
                    success=True,
                    status=DeliveryStatus.DELIVERED,
                    delivery_time=delivery_time,
                    relay_node=f"{self.relay_config['host']}:{self.relay_config['port']}"
                )
            else:
                # 添加到待投递队列
                self._queue_message(message, recipient)
                
                return RouteResult(
                    success=False,
                    status=DeliveryStatus.PENDING,
                    error_message="Relay delivery failed, queued for retry"
                )
                
        except Exception as e:
            logger.error(f"Relay delivery failed: {e}")
            self._queue_message(message, recipient)
            
            return RouteResult(
                success=False,
                status=DeliveryStatus.FAILED,
                error_message=str(e)
            )
    
    def _build_message_packet(self, message: MailMessage, recipient: MailboxAddress) -> dict:
        """构建消息包"""
        return {
            "type": "p2p_mail",
            "version": "1.0",
            "message_id": message.message_id,
            "from_node": self.node_id,
            "to_node": recipient.node_id,
            "timestamp": time.time(),
            "payload": {
                "subject": message.subject,
                "body_encrypted": message.body,
                "from": str(message.from_addr) if message.from_addr else None,
                "priority": message.priority,
                "has_attachments": message.has_attachments
            }
        }
    
    async def _send_udp_packet(self, host: str, port: int, packet: dict) -> bool:
        """发送UDP数据包"""
        try:
            import socket
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            data = json.dumps(packet).encode('utf-8')
            
            loop = asyncio.get_event_loop()
            await loop.sock_sendall(sock, data)
            sock.close()
            
            return True
        except Exception as e:
            logger.error(f"UDP send failed: {e}")
            return False
    
    async def _send_to_relay(self, packet: dict) -> bool:
        """发送到中继服务器"""
        try:
            # 复用 lightweight_ui 的 relay_client
            if self._relay_client is None:
                from core.lightweight_ui.relay_client import RelayClient, RelayServerConfig
                
                config = RelayServerConfig(
                    host=self.relay_config["host"],
                    port=self.relay_config["port"],
                    use_ssl=self.relay_config.get("use_ssl", False),
                    websocket_mode=self.relay_config.get("websocket_mode", True)
                )
                self._relay_client = RelayClient(config)
                await self._relay_client.connect()
            
            # 发送消息
            await self._relay_client.send_peer_message(
                peer_id=packet["to_node"],
                message=packet
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Relay send failed: {e}")
            return False
    
    # ========== 离线消息队列 ==========
    
    def _queue_offline_message(self, message: MailMessage, recipient: MailboxAddress):
        """队列离线消息"""
        if recipient.node_id not in self._offline_queue:
            self._offline_queue[recipient.node_id] = []
        
        pending = PendingMessage(
            message=message,
            recipient=recipient,
            status=DeliveryStatus.OFFLINE_QUEUED
        )
        self._offline_queue[recipient.node_id].append(pending)
        logger.debug(f"Queued offline message for {recipient}")
    
    async def flush_offline_queue(self, node_id: str) -> int:
        """
        刷新离线队列
        
        Args:
            node_id: 目标节点ID
            
        Returns:
            int: 成功投递数量
        """
        if node_id not in self._offline_queue:
            return 0
        
        messages = self._offline_queue.pop(node_id)
        success_count = 0
        
        for pending in messages:
            result = await self.send_message(pending.message, pending.recipient)
            if result.success:
                success_count += 1
        
        logger.info(f"Flushed offline queue for {node_id}: {success_count}/{len(messages)}")
        return success_count
    
    def _queue_message(self, message: MailMessage, recipient: MailboxAddress):
        """添加到待投递队列"""
        key = f"{message.message_id}:{recipient.node_id}"
        self._pending_queue[key] = PendingMessage(
            message=message,
            recipient=recipient
        )
    
    async def _delivery_loop(self):
        """投递循环 - 重试待投递消息"""
        while self._running:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次
                
                now = time.time()
                for key, pending in list(self._pending_queue.items()):
                    if pending.next_retry > now:
                        continue
                    
                    if pending.attempts >= pending.max_attempts:
                        # 超过最大重试次数
                        logger.warning(f"Message delivery failed after {pending.max_attempts} attempts: {key}")
                        if self._on_message_failed:
                            self._on_message_failed(pending.message, pending.recipient)
                        del self._pending_queue[key]
                        continue
                    
                    # 重试 (指数退避)
                    pending.attempts += 1
                    base_delay = 5
                    if get_config:
                        base_delay = get_config().get("message.retry_base_delay", 5)
                    pending.next_retry = now + (2 ** pending.attempts) * base_delay
                    
                    result = await self.send_message(pending.message, pending.recipient)
                    
                    if result.success:
                        if self._on_message_delivered:
                            self._on_message_delivered(pending.message, pending.recipient)
                        del self._pending_queue[key]
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Delivery loop error: {e}")
    
    # ========== 节点状态 ==========
    
    def _is_peer_online(self, node_id: str) -> bool:
        """检查节点是否在线"""
        # 检查直连peer
        if node_id in self._direct_peers:
            return True
        
        # TODO: 检查中继服务器上的节点状态
        return False
    
    async def notify_peer_online(self, node_id: str, host: str = None, port: int = None):
        """通知节点上线"""
        if host and port:
            self._direct_peers[node_id] = (host, port)
        
        if self._on_peer_online:
            self._on_peer_online(node_id)
        
        # 刷新离线队列
        await self.flush_offline_queue(node_id)
    
    async def notify_peer_offline(self, node_id: str):
        """通知节点下线"""
        self._direct_peers.pop(node_id, None)
        
        if self._on_peer_offline:
            self._on_peer_offline(node_id)
    
    # ========== 接收消息 ==========
    
    async def receive_message(self, packet: dict) -> Optional[MailMessage]:
        """
        接收消息
        
        Args:
            packet: 消息数据包
            
        Returns:
            MailMessage or None
        """
        try:
            if packet.get("type") == "p2p_mail":
                return self._parse_p2p_message(packet)
            elif packet.get("type") == "relay_mail":
                return self._parse_relay_message(packet)
            
            return None
        except Exception as e:
            logger.error(f"Receive message failed: {e}")
            return None
    
    def _parse_p2p_message(self, packet: dict) -> MailMessage:
        """解析P2P消息"""
        payload = packet["payload"]
        
        return MailMessage(
            message_id=packet["message_id"],
            subject=payload["subject"],
            body=payload["body_encrypted"],
            body_plain="",  # 需要解密
            created_at=packet["timestamp"],
            sent_at=packet["timestamp"],
            delivered_at=time.time(),
            status=MessageStatus.DELIVERED
        )
    
    def _parse_relay_message(self, packet: dict) -> MailMessage:
        """解析中继消息"""
        return MailMessage(
            message_id=packet["message_id"],
            subject=packet.get("metadata", {}).get("subject", ""),
            body=packet.get("encrypted_payload", ""),
            created_at=packet.get("timestamp", time.time()),
            status=MessageStatus.DELIVERED
        )
    
    # ========== 投递回执 ==========
    
    def create_receipt(self, message_id: str, recipient: str, 
                      status: MessageStatus) -> DeliveryReceipt:
        """创建投递回执"""
        receipt = DeliveryReceipt(
            message_id=message_id,
            recipient=recipient,
            status=status,
            delivered_at=time.time() if status == MessageStatus.DELIVERED else None
        )
        return receipt
    
    # ========== 状态查询 ==========
    
    def get_pending_count(self) -> int:
        """获取待投递消息数"""
        return len(self._pending_queue)
    
    def get_offline_queue_count(self, node_id: str = None) -> int:
        """获取离线队列消息数"""
        if node_id:
            return len(self._offline_queue.get(node_id, []))
        return sum(len(q) for q in self._offline_queue.values())
    
    def is_relay_connected(self) -> bool:
        """检查中继连接状态"""
        return self._relay_connected
    
    async def check_relay_connection(self) -> bool:
        """检查并重连中继"""
        try:
            if self._relay_client:
                if not self._relay_client.is_connected():
                    await self._relay_client.connect()
                    self._relay_connected = self._relay_client.is_connected()
            return self._relay_connected
        except Exception as e:
            logger.error(f"Check relay connection failed: {e}")
            return False
