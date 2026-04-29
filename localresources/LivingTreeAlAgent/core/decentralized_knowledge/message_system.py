"""
消息通信系统
Message Communication System
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
import queue

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型"""
    TEXT = "text"
    FILE = "file"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    SYSTEM = "system"


class MessageStatus(Enum):
    """消息状态"""
    DRAFT = "draft"           # 草稿
    PENDING = "pending"        # 待发送
    SENDING = "sending"        # 发送中
    SENT = "sent"             # 已发送
    DELIVERED = "delivered"    # 已送达
    READ = "read"             # 已读
    FAILED = "failed"          # 发送失败


class MessageFolder(Enum):
    """消息文件夹"""
    INBOX = "inbox"
    SENT = "sent"
    OUTBOX = "outbox"          # 待发送队列
    DRAFTS = "drafts"
    TRASH = "trash"


@dataclass
class Message:
    """消息"""
    msg_id: str
    sender_id: str
    recipient_id: str
    content: str
    msg_type: MessageType = MessageType.TEXT
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    
    # 状态
    status: MessageStatus = MessageStatus.DRAFT
    
    # 附件
    attachments: List[str] = field(default_factory=list)  # 文件路径列表
    
    # 引用
    reply_to: Optional[str] = None
    thread_id: Optional[str] = None
    
    # 其他
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # P2P传输信息
    via_relay: bool = False
    relay_server: Optional[str] = None


@dataclass
class Conversation:
    """对话会话"""
    conv_id: str
    participants: List[str]
    
    # 消息
    last_message: Optional[Message] = None
    unread_count: int = 0
    
    # 状态
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_muted: bool = False
    is_pinned: bool = False
    
    # 草稿
    draft_content: Optional[str] = None


class MessageSystem:
    """
    去中心化消息通信系统
    
    功能：
    - 分级消息传输（P2P/中继/离线）
    - 消息状态追踪
    - 发件箱队列管理
    - 离线消息存储
    """
    
    def __init__(self, identity, p2p_node=None, relay_client=None):
        self.identity = identity
        self.p2p_node = p2p_node
        self.relay_client = relay_client
        
        # 存储路径
        self._storage_path = Path.home() / ".hermes-desktop" / "messages"
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存
        self._messages: Dict[str, Message] = {}
        self._conversations: Dict[str, Conversation] = {}
        self._outbox: queue.Queue = queue.Queue()
        
        # 待发送消息（离线支持）
        self._pending_file = self._storage_path / "pending.json"
        self._load_pending_messages()
        
        # 回调
        self._message_callbacks: List[Callable[[Message], None]] = []
        
        # 锁
        self._lock = asyncio.Lock()
        
        # 统计
        self._sent_today = 0
        self._last_reset = datetime.now()
        
        logger.info("消息系统初始化完成")
    
    def _get_message_path(self, msg_id: str) -> Path:
        """获取消息存储路径"""
        return self._storage_path / f"{msg_id}.json"
    
    def _load_pending_messages(self) -> None:
        """加载待发送消息"""
        if self._pending_file.exists():
            try:
                with open(self._pending_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for msg_data in data:
                    msg = self._deserialize_message(msg_data)
                    self._outbox.put(msg)
                    self._messages[msg.msg_id] = msg
                
                logger.info(f"加载了 {len(data)} 条待发送消息")
                
            except Exception as e:
                logger.error(f"加载待发送消息失败: {e}")
    
    def _save_pending_messages(self) -> None:
        """保存待发送消息"""
        try:
            pending = [self._serialize_message(msg) 
                      for msg in self._messages.values()
                      if msg.status in [MessageStatus.PENDING, MessageStatus.FAILED]]
            
            with open(self._pending_file, 'w', encoding='utf-8') as f:
                json.dump(pending, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存待发送消息失败: {e}")
    
    def _serialize_message(self, msg: Message) -> Dict[str, Any]:
        """序列化消息"""
        return {
            'msg_id': msg.msg_id,
            'sender_id': msg.sender_id,
            'recipient_id': msg.recipient_id,
            'content': msg.content,
            'msg_type': msg.msg_type.value,
            'created_at': msg.created_at.isoformat(),
            'sent_at': msg.sent_at.isoformat() if msg.sent_at else None,
            'delivered_at': msg.delivered_at.isoformat() if msg.delivered_at else None,
            'read_at': msg.read_at.isoformat() if msg.read_at else None,
            'status': msg.status.value,
            'attachments': msg.attachments,
            'reply_to': msg.reply_to,
            'thread_id': msg.thread_id,
            'metadata': msg.metadata
        }
    
    def _deserialize_message(self, data: Dict[str, Any]) -> Message:
        """反序列化消息"""
        return Message(
            msg_id=data['msg_id'],
            sender_id=data['sender_id'],
            recipient_id=data['recipient_id'],
            content=data['content'],
            msg_type=MessageType(data.get('msg_type', 'text')),
            created_at=datetime.fromisoformat(data['created_at']),
            sent_at=datetime.fromisoformat(data['sent_at']) if data.get('sent_at') else None,
            delivered_at=datetime.fromisoformat(data['delivered_at']) if data.get('delivered_at') else None,
            read_at=datetime.fromisoformat(data['read_at']) if data.get('read_at') else None,
            status=MessageStatus(data.get('status', 'draft')),
            attachments=data.get('attachments', []),
            reply_to=data.get('reply_to'),
            thread_id=data.get('thread_id'),
            metadata=data.get('metadata', {})
        )
    
    async def start(self) -> None:
        """启动消息系统"""
        # 启动发送循环
        asyncio.create_task(self._send_loop())
        logger.info("消息系统已启动")
    
    async def stop(self) -> None:
        """停止消息系统"""
        # 保存待发送消息
        self._save_pending_messages()
        logger.info("消息系统已停止")
    
    async def _send_loop(self) -> None:
        """消息发送循环"""
        while True:
            try:
                # 获取待发送消息
                try:
                    msg = self._outbox.get(timeout=1)
                except queue.Empty:
                    continue
                
                # 尝试发送
                success = await self._send_message_impl(msg)
                
                if success:
                    msg.status = MessageStatus.SENT
                    msg.sent_at = datetime.now()
                    self._sent_today += 1
                else:
                    # 重试逻辑
                    retry_count = msg.metadata.get('retry_count', 0)
                    if retry_count < 5:
                        msg.metadata['retry_count'] = retry_count + 1
                        msg.status = MessageStatus.PENDING
                        # 延迟重试
                        await asyncio.sleep(min(30 * (2 ** retry_count), 300))
                        self._outbox.put(msg)
                    else:
                        msg.status = MessageStatus.FAILED
                
                self._save_pending_messages()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"消息发送循环错误: {e}")
    
    async def _send_message_impl(self, msg: Message) -> bool:
        """实际发送消息"""
        msg.status = MessageStatus.SENDING
        
        # 优先尝试P2P直连
        if self.p2p_node:
            try:
                success = await self.p2p_node.send_message(
                    target_id=msg.recipient_id,
                    message=self._serialize_message(msg)
                )
                if success:
                    return True
            except Exception as e:
                logger.debug(f"P2P发送失败: {e}")
        
        # 尝试中继服务器
        if self.relay_client:
            try:
                success = await self.relay_client.forward_message(
                    recipient=msg.recipient_id,
                    message=msg.content
                )
                if success:
                    msg.via_relay = True
                    return True
            except Exception as e:
                logger.debug(f"中继发送失败: {e}")
        
        return False
    
    async def send_message(self, sender_id: str, recipient_id: str,
                          content: str, msg_type: str = "text",
                          attachments: Optional[List[str]] = None) -> Optional[Message]:
        """
        发送消息
        
        Args:
            sender_id: 发送者ID
            recipient_id: 接收者ID
            content: 消息内容
            msg_type: 消息类型
            attachments: 附件列表
        
        Returns:
            Message: 发送的消息
        """
        import secrets
        
        msg = Message(
            msg_id=secrets.token_urlsafe(16),
            sender_id=sender_id,
            recipient_id=recipient_id,
            content=content,
            msg_type=MessageType(msg_type),
            attachments=attachments or [],
            status=MessageStatus.PENDING
        )
        
        async with self._lock:
            self._messages[msg.msg_id] = msg
        
        # 添加到发送队列
        self._outbox.put(msg)
        
        # 如果是离线模式，立即返回
        if not self.p2p_node and not self.relay_client:
            logger.info(f"离线模式，消息已加入发件箱: {msg.msg_id}")
        
        return msg
    
    async def receive_message(self, msg: Message) -> None:
        """
        接收消息
        
        Args:
            msg: 收到的消息
        """
        async with self._lock:
            self._messages[msg.msg_id] = msg
        
        # 通知回调
        for callback in self._message_callbacks:
            try:
                callback(msg)
            except Exception as e:
                logger.error(f"消息回调执行失败: {e}")
        
        logger.info(f"收到消息: {msg.msg_id} from {msg.sender_id}")
    
    async def get_messages(self, user_id: str, folder: str = "inbox",
                          unread_only: bool = False,
                          limit: int = 100) -> List[Message]:
        """
        获取消息
        
        Args:
            user_id: 用户ID
            folder: 文件夹
            unread_only: 仅未读
            limit: 限制数量
        
        Returns:
            List[Message]: 消息列表
        """
        messages = []
        
        for msg in self._messages.values():
            # 判断消息是否属于该用户
            if folder == MessageFolder.INBOX.value:
                if msg.recipient_id != user_id:
                    continue
                if unread_only and msg.read_at:
                    continue
            elif folder == MessageFolder.SENT.value:
                if msg.sender_id != user_id:
                    continue
            elif folder == MessageFolder.OUTBOX.value:
                if msg.sender_id != user_id:
                    continue
                if msg.status not in [MessageStatus.PENDING, MessageStatus.FAILED]:
                    continue
            else:
                continue
            
            messages.append(msg)
        
        # 排序（最新的在前）
        messages.sort(key=lambda m: m.created_at, reverse=True)
        
        return messages[:limit]
    
    async def get_pending_messages(self) -> List[Message]:
        """获取待发送消息"""
        return [msg for msg in self._messages.values()
                if msg.status in [MessageStatus.PENDING, MessageStatus.FAILED]]
    
    async def mark_as_read(self, msg_id: str) -> bool:
        """标记消息为已读"""
        async with self._lock:
            msg = self._messages.get(msg_id)
            if not msg:
                return False
            
            msg.read_at = datetime.now()
            msg.status = MessageStatus.READ
            return True
    
    async def mark_all_as_read(self, user_id: str, sender_id: str) -> int:
        """标记所有消息为已读"""
        count = 0
        async with self._lock:
            for msg in self._messages.values():
                if msg.recipient_id == user_id and msg.sender_id == sender_id:
                    if not msg.read_at:
                        msg.read_at = datetime.now()
                        msg.status = MessageStatus.READ
                        count += 1
        return count
    
    async def delete_message(self, msg_id: str) -> bool:
        """删除消息"""
        async with self._lock:
            msg = self._messages.get(msg_id)
            if not msg:
                return False
            
            # 从文件删除
            file_path = self._get_message_path(msg_id)
            if file_path.exists():
                file_path.unlink()
            
            # 从内存删除
            self._messages.pop(msg_id, None)
            return True
    
    async def retry_failed(self, msg_ids: List[str]) -> int:
        """重试发送失败的消息"""
        count = 0
        for msg_id in msg_ids:
            msg = self._messages.get(msg_id)
            if msg and msg.status == MessageStatus.FAILED:
                msg.status = MessageStatus.PENDING
                msg.metadata['retry_count'] = 0
                self._outbox.put(msg)
                count += 1
        
        self._save_pending_messages()
        return count
    
    def add_message_callback(self, callback: Callable[[Message], None]) -> None:
        """添加消息回调"""
        self._message_callbacks.append(callback)
    
    def remove_message_callback(self, callback: Callable[[Message], None]) -> None:
        """移除消息回调"""
        if callback in self._message_callbacks:
            self._message_callbacks.remove(callback)
    
    def get_stats(self) -> tuple:
        """获取统计信息"""
        # 重置每日计数
        if (datetime.now() - self._last_reset).days >= 1:
            self._sent_today = 0
            self._last_reset = datetime.now()
        
        pending = sum(1 for msg in self._messages.values()
                      if msg.status == MessageStatus.PENDING)
        
        return pending, self._sent_today
    
    async def get_conversations(self, user_id: str) -> List[Conversation]:
        """获取会话列表"""
        conversations = []
        
        # 按对话分组
        conv_map: Dict[str, List[Message]] = {}
        
        for msg in self._messages.values():
            if msg.sender_id == user_id or msg.recipient_id == user_id:
                other = msg.recipient_id if msg.sender_id == user_id else msg.sender_id
                
                if other not in conv_map:
                    conv_map[other] = []
                conv_map[other].append(msg)
        
        # 构建会话对象
        for participant, msgs in conv_map.items():
            latest = max(msgs, key=lambda m: m.created_at)
            
            conv = Conversation(
                conv_id=participant,
                participants=[user_id, participant],
                last_message=latest,
                unread_count=sum(1 for m in msgs 
                                if m.recipient_id == user_id and not m.read_at)
            )
            conversations.append(conv)
        
        # 排序
        conversations.sort(key=lambda c: c.updated_at, reverse=True)
        
        return conversations
