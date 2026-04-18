"""
去中心化邮箱核心调度器

整合所有子模块, 提供统一的邮箱服务接口
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional, List, Callable

from .models import (MailMessage, MailboxAddress, Contact, MessageStatus,
                    Attachment, InboxFolder, DeliveryReceipt)
from .address_manager import AddressManager
from .crypto import MailCrypto
from .message_store import MessageStore
from .message_router import MessageRouter, RouteResult, DeliveryStatus
from .attachment_handler import AttachmentHandler

logger = logging.getLogger(__name__)


class MailboxHub:
    """
    去中心化邮箱核心调度器 (单例模式)
    
    整合:
    - AddressManager: 地址与身份管理
    - MailCrypto: 加密服务
    - MessageStore: 消息存储
    - MessageRouter: 消息路由
    - AttachmentHandler: 附件处理
    """
    
    _instance: Optional[MailboxHub] = None
    _lock = asyncio.Lock()
    
    def __init__(self, data_dir: str = "~/.hermes-desktop/mailbox"):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 子模块
        self.address_manager = AddressManager(str(self.data_dir))
        self.crypto = MailCrypto()
        self.message_store = MessageStore(str(self.data_dir))
        self.router: Optional[MessageRouter] = None  # 延迟初始化
        self.attachment_handler = AttachmentHandler(str(self.data_dir), self.crypto)
        
        # 状态
        self._initialized = False
        self._running = False
        
        # 事件回调
        self._on_new_message: Optional[Callable] = None
        self._on_delivery_status: Optional[Callable] = None
        self._on_peer_status: Optional[Callable] = None
        
        # 待发送队列 (已加密待投递)
        self._outbox: list[MailMessage] = []
    
    @classmethod
    async def get_instance(cls, data_dir: str = None) -> "MailboxHub":
        """获取单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(data_dir)
                    await cls._instance.initialize()
        return cls._instance
    
    @classmethod
    def get_instance_sync(cls, data_dir: str = None) -> "MailboxHub":
        """同步获取单例 (用于非async上下文)"""
        if cls._instance is None:
            cls._instance = cls(data_dir)
            # 注意: 这不会调用 initialize()
        return cls._instance
    
    async def initialize(self):
        """初始化"""
        if self._initialized:
            return
        
        logger.info("Initializing MailboxHub...")
        
        # 加载或生成身份
        if not self.address_manager.load_node_identity():
            # 需要新身份
            logger.info("No existing identity, please create one")
        
        # 初始化路由
        self.router = MessageRouter(
            node_id=self.address_manager.node_id or "unknown"
        )
        self.router.set_callbacks(
            on_delivered=self._handle_message_delivered,
            on_failed=self._handle_message_failed,
            on_peer_online=self._handle_peer_online,
            on_peer_offline=self._handle_peer_offline
        )
        await self.router.start()
        
        # 加载待发送队列
        await self._load_outbox()
        
        self._initialized = True
        logger.info("MailboxHub initialized")
    
    async def shutdown(self):
        """关闭"""
        self._running = False
        
        if self.router:
            await self.router.stop()
        
        # 保存待发送队列
        await self._save_outbox()
        
        logger.info("MailboxHub shutdown")
    
    # ========== 身份管理 ==========
    
    def create_identity(self, username: str) -> MailboxAddress:
        """创建新身份"""
        addr = self.address_manager.generate_node_identity(username)
        self.crypto.generate_keypair()
        logger.info(f"Created identity: {addr}")
        return addr
    
    def get_my_address(self) -> Optional[MailboxAddress]:
        """获取我的地址"""
        return self.address_manager.current_address
    
    def get_my_full_address(self) -> str:
        """获取我的完整地址字符串"""
        return self.address_manager.get_my_full_address()
    
    # ========== 发送邮件 ==========
    
    async def send_message(self, 
                          to_addrs: List[str],
                          subject: str,
                          body: str,
                          cc_addrs: List[str] = None,
                          bcc_addrs: List[str] = None,
                          attachments: List[str] = None,
                          encrypt: bool = True,
                          priority: int = 0
                          ) -> Optional[str]:
        """
        发送邮件
        
        Args:
            to_addrs: 收件人地址列表
            cc_addrs: 抄送地址列表
            bcc_addrs: 密送地址列表
            subject: 主题
            body: 正文
            attachments: 附件路径列表
            encrypt: 是否加密
            priority: 优先级
            
        Returns:
            str: 消息ID 或 None
        """
        # 解析收件人
        recipients = []
        for addr_str in to_addrs:
            addr = self.address_manager.parse_address(addr_str)
            if addr:
                recipients.append(addr)
            else:
                logger.warning(f"Invalid address: {addr_str}")
        
        if not recipients:
            logger.error("No valid recipients")
            return None
        
        # 创建消息
        message_id = self.crypto.generate_message_id()
        
        # 加密正文
        encrypted_body = body
        if encrypt:
            # 获取第一个收件人的公钥进行加密
            recipient = recipients[0]
            if recipient.public_key:
                shared_key = self.crypto.derive_shared_key(recipient.public_key)
                if shared_key:
                    ciphertext, iv, salt = self.crypto.encrypt_message(body, shared_key)
                    encrypted_body = json.dumps({
                        "ciphertext": ciphertext.hex(),
                        "iv": iv.hex(),
                        "salt": salt.hex()
                    })
        
        # 处理附件
        attachment_list = []
        if attachments:
            for file_path in attachments:
                atts = await self.attachment_handler.upload_attachment(
                    file_path, message_id
                )
                if atts:
                    attachment_list.extend(atts)
        
        # 构建消息
        message = MailMessage(
            message_id=message_id,
            subject=subject,
            body=encrypted_body,
            body_plain=body[:200] if not encrypt else "",  # 明文预览
            from_addr=self.address_manager.current_address,
            to_addrs=recipients,
            cc_addrs=[self.address_manager.parse_address(a) for a in (cc_addrs or [])],
            bcc_addrs=[self.address_manager.parse_address(a) for a in (bcc_addrs or [])],
            created_at=time.time(),
            status=MessageStatus.SENDING,
            is_encrypted=encrypt,
            attachments=attachment_list,
            has_large_attachment=any(a.total_chunks > 1 for a in attachment_list),
            priority=priority
        )
        
        # 保存到发件箱
        self.message_store.save_message(message)
        
        # 投递
        results = []
        for recipient in recipients:
            result = await self.router.send_message(message, recipient)
            results.append(result)
            
            # 更新联系人统计
            self.address_manager.update_contact_stats(recipient, sent=True)
            
            # 创建回执
            receipt = self.router.create_receipt(
                message_id,
                str(recipient),
                MessageStatus.SENT if result.success else MessageStatus.FAILED
            )
            self.message_store.add_delivery_receipt(receipt)
        
        # 更新状态
        all_success = all(r.success for r in results)
        self.message_store.mark_as_sent(message_id) if all_success else None
        
        logger.info(f"Message {message_id} sent to {len(recipients)} recipients")
        return message_id
    
    async def _deliver_to_recipient(self, message: MailMessage, 
                                   recipient: MailboxAddress) -> RouteResult:
        """投递消息到单个收件人"""
        return await self.router.send_message(message, recipient)
    
    # ========== 接收邮件 ==========
    
    async def receive_messages(self, check_interval: int = 30):
        """
        接收消息循环
        
        Args:
            check_interval: 检查间隔 (秒)
        """
        self._running = True
        
        while self._running:
            try:
                # TODO: 从本地存储/中继检查新消息
                await asyncio.sleep(check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Receive messages error: {e}")
                await asyncio.sleep(5)
    
    def add_received_message(self, message: MailMessage):
        """
        添加收到的消息 (由底层调用)
        
        Args:
            message: 收到的消息
        """
        # 保存到收件箱
        message.status = MessageStatus.DELIVERED
        self.message_store.save_message(message)
        
        # 更新联系人
        if message.from_addr:
            self.address_manager.update_contact_stats(message.from_addr, received=True)
        
        # 触发回调
        if self._on_new_message:
            self._on_new_message(message)
        
        logger.info(f"Received message: {message.message_id}")
    
    # ========== 邮件管理 ==========
    
    def get_inbox(self, limit: int = 50, offset: int = 0) -> List[MailMessage]:
        """获取收件箱"""
        return self.message_store.get_inbox(limit, offset)
    
    def get_sent(self, limit: int = 50, offset: int = 0) -> List[MailMessage]:
        """获取已发送"""
        return self.message_store.get_sent(limit, offset)
    
    def get_drafts(self, limit: int = 50, offset: int = 0) -> List[MailMessage]:
        """获取草稿箱"""
        return self.message_store.get_drafts(limit, offset)
    
    def get_trash(self, limit: int = 50, offset: int = 0) -> List[MailMessage]:
        """获取垃圾箱"""
        return self.message_store.get_trash(limit, offset)
    
    def get_outbox(self, limit: int = 50, offset: int = 0) -> List[MailMessage]:
        """获取发件箱"""
        return self.message_store.get_outbox(limit, offset)
    
    def get_message(self, message_id: str) -> Optional[MailMessage]:
        """获取消息"""
        return self.message_store.get_message(message_id)
    
    def delete_message(self, message_id: str, hard: bool = False):
        """删除消息"""
        return self.message_store.delete_message(message_id, hard)
    
    def mark_as_read(self, message_id: str):
        """标记为已读"""
        return self.message_store.mark_as_read(message_id)
    
    def search_messages(self, query: str, limit: int = 50) -> List[MailMessage]:
        """搜索消息"""
        my_addr = self.get_my_full_address()
        return self.message_store.search_messages(query, my_addr, limit)
    
    def get_folders(self) -> List[InboxFolder]:
        """获取文件夹列表"""
        return self.message_store.get_folders()
    
    def get_unread_count(self) -> int:
        """获取未读数"""
        return self.message_store.get_unread_count()
    
    # ========== 联系人管理 ==========
    
    def add_contact(self, address: str, display_name: str = "") -> bool:
        """添加联系人"""
        addr = self.address_manager.parse_address(address)
        if not addr:
            logger.error(f"Invalid address: {address}")
            return False
        
        contact = Contact(
            address=addr,
            display_name=display_name or addr.username
        )
        return self.address_manager.add_contact(contact)
    
    def get_contacts(self) -> List[Contact]:
        """获取联系人列表"""
        return self.address_manager.get_all_contacts()
    
    def get_contact(self, address: str) -> Optional[Contact]:
        """获取联系人"""
        addr = self.address_manager.parse_address(address)
        if addr:
            return self.address_manager.get_contact(addr)
        return None
    
    def block_contact(self, address: str):
        """拉黑联系人"""
        addr = self.address_manager.parse_address(address)
        if addr:
            self.address_manager.block_address(addr)
    
    # ========== 附件处理 ==========
    
    async def download_attachment(self, attachment: Attachment, 
                                  output_path: str,
                                  progress_callback: Callable = None) -> bool:
        """下载附件"""
        return await self.attachment_handler.download_attachment(
            attachment, output_path, progress_callback
        )
    
    # ========== 事件处理 ==========
    
    def set_event_callbacks(self, **kwargs):
        """设置事件回调"""
        self._on_new_message = kwargs.get("on_new_message")
        self._on_delivery_status = kwargs.get("on_delivery_status")
        self._on_peer_status = kwargs.get("on_peer_status")
    
    def _handle_message_delivered(self, message: MailMessage, recipient: MailboxAddress):
        """消息投递成功"""
        if self._on_delivery_status:
            self._on_delivery_status(message.message_id, str(recipient), True)
    
    def _handle_message_failed(self, message: MailMessage, recipient: MailboxAddress):
        """消息投递失败"""
        if self._on_delivery_status:
            self._on_delivery_status(message.message_id, str(recipient), False)
    
    def _handle_peer_online(self, node_id: str):
        """节点上线"""
        logger.info(f"Peer online: {node_id}")
        if self._on_peer_status:
            self._on_peer_status(node_id, True)
    
    def _handle_peer_offline(self, node_id: str):
        """节点下线"""
        logger.info(f"Peer offline: {node_id}")
        if self._on_peer_status:
            self._on_peer_status(node_id, False)
    
    # ========== 待发送队列 ==========
    
    async def _load_outbox(self):
        """加载待发送队列"""
        outbox_path = self.data_dir / "outbox.json"
        if outbox_path.exists():
            try:
                data = json.loads(outbox_path.read_text())
                self._outbox = [self._deserialize_message(m) for m in data]
            except Exception as e:
                logger.error(f"Load outbox failed: {e}")
    
    async def _save_outbox(self):
        """保存待发送队列"""
        outbox_path = self.data_dir / "outbox.json"
        try:
            data = [self._serialize_message(m) for m in self._outbox]
            outbox_path.write_text(json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Save outbox failed: {e}")
    
    def _serialize_message(self, message: MailMessage) -> dict:
        """序列化消息"""
        return {
            "message_id": message.message_id,
            "subject": message.subject,
            "body": message.body,
            "to_addrs": [str(a) for a in message.to_addrs]
        }
    
    def _deserialize_message(self, data: dict) -> MailMessage:
        """反序列化消息"""
        return MailMessage(
            message_id=data["message_id"],
            subject=data["subject"],
            body=data["body"],
            to_addrs=[self.address_manager.parse_address(a) for a in data.get("to_addrs", [])]
        )
    
    # ========== 状态查询 ==========
    
    def get_status(self) -> dict:
        """获取状态"""
        return {
            "initialized": self._initialized,
            "running": self._running,
            "my_address": str(self.get_my_address()) if self.get_my_address() else None,
            "unread_count": self.get_unread_count(),
            "pending_messages": self.router.get_pending_count() if self.router else 0,
            "relay_connected": self.router.is_relay_connected() if self.router else False
        }
    
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized


# 全局获取函数
async def get_mailbox_hub() -> MailboxHub:
    """获取邮箱核心实例"""
    return await MailboxHub.get_instance()


def get_mailbox_hub_sync() -> MailboxHub:
    """同步获取邮箱核心实例"""
    return MailboxHub.get_instance_sync()
