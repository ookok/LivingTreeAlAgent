"""
P2P连接器核心调度器

整合所有子模块, 提供统一的连接服务接口
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
import socket
import sqlite3
import time
from pathlib import Path
from typing import Optional, List, Callable

from .models import (NodeProfile, P2PConnection, ChannelSession, Contact,
                    PeerStatus, ChannelType, ConnectionStatus)
from .short_id import ShortIDGenerator
from .directory_service import DirectoryService
from .multi_channel_manager import MultiChannelManager, Message

logger = logging.getLogger(__name__)


class ConnectorHub:
    """
    P2P连接器核心调度器 (单例模式)
    
    整合:
    - ShortIDGenerator: 短ID生成与解析
    - DirectoryService: 目录服务与节点发现
    - MultiChannelManager: 多通道通信
    """
    
    _instance: Optional["ConnectorHub"] = None
    _lock = asyncio.Lock()
    
    def __init__(self, data_dir: str = "~/.hermes-desktop/connector"):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 子模块
        self.short_id_generator = ShortIDGenerator(str(self.data_dir))
        self.directory_service = DirectoryService(str(self.data_dir))
        self.channel_manager: Optional[MultiChannelManager] = None
        
        # 我的节点信息
        self.node_id: Optional[str] = None
        self.short_id: Optional[str] = None
        self.profile: Optional[NodeProfile] = None
        
        # 状态
        self._initialized = False
        self._running = False
        
        # 联系人
        self._contacts: dict[str, Contact] = {}
        
        # 数据库
        self.db_path = self.data_dir / "connector.db"
        self._init_db()
        
        # 回调
        self._on_new_message: Optional[Callable] = None
        self._on_peer_online: Optional[Callable] = None
        self._on_peer_offline: Optional[Callable] = None
        self._on_connection_changed: Optional[Callable] = None
    
    @classmethod
    async def get_instance(cls, data_dir: str = None) -> "ConnectorHub":
        """获取单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(data_dir)
                    await cls._instance.initialize()
        return cls._instance
    
    @classmethod
    def get_instance_sync(cls, data_dir: str = None) -> "ConnectorHub":
        """同步获取单例"""
        if cls._instance is None:
            cls._instance = cls(data_dir)
        return cls._instance
    
    async def initialize(self):
        """初始化"""
        if self._initialized:
            return
        
        logger.info("Initializing ConnectorHub...")
        
        # 生成或加载节点ID
        self._load_or_create_identity()
        
        # 初始化通道管理器
        self.channel_manager = MultiChannelManager(self.node_id)
        self.channel_manager.set_callbacks(
            on_message=self._handle_message,
            on_connection_status=self._handle_connection_status
        )
        
        # 设置目录服务回调
        self.directory_service.set_callbacks(
            on_peer_online=self._handle_peer_online,
            on_peer_offline=self._handle_peer_offline
        )
        
        # 注册到目录服务
        self._register_to_directory()
        
        # 加载联系人
        self._load_contacts()
        
        self._initialized = True
        logger.info(f"ConnectorHub initialized: node_id={self.node_id[:16]}..., short_id={self.short_id}")
    
    def _load_or_create_identity(self):
        """加载或创建身份"""
        # 检查是否已有身份
        existing_short_id = self.short_id_generator.get_my_short_id()
        
        if existing_short_id:
            self.short_id = existing_short_id
            # 从数据库加载node_id
            node_id = self.short_id_generator.resolve_short_id(existing_short_id)
            if node_id:
                self.node_id = node_id
            else:
                self.node_id = self._generate_node_id()
        else:
            # 创建新身份
            self.node_id = self._generate_node_id()
            self.short_id = self.short_id_generator.generate_and_register(
                self.node_id, ShortIDGenerator.LENGTH_10
            )
        
        # 获取公网地址
        public_ip, public_port = self._get_public_address()
        
        # 创建节点档案
        self.profile = NodeProfile(
            node_id=self.node_id,
            short_id=self.short_id,
            display_name=f"用户{self.short_id[-4:]}",
            public_ip=public_ip,
            public_port=public_port,
            status=PeerStatus.ONLINE,
            capabilities=["text", "file", "voice", "video", "live", "email"],
            relay_hosts=["139.199.124.242:8888"]
        )
    
    def _generate_node_id(self) -> str:
        """生成节点ID"""
        random_bytes = secrets.token_bytes(32)
        return hashlib.sha256(random_bytes).hexdigest()
    
    def _get_public_address(self) -> tuple:
        """获取公网地址"""
        try:
            # 简单实现, 实际应使用STUN
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return (local_ip, 0)  # port需要监听后才知道
        except:
            return (None, None)
    
    def _register_to_directory(self):
        """注册到目录服务"""
        if self.profile:
            self.directory_service.set_my_profile(self.profile)
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 联系人表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                node_id TEXT PRIMARY KEY,
                short_id TEXT,
                display_name TEXT,
                avatar TEXT,
                is_friend INTEGER DEFAULT 0,
                is_blocked INTEGER DEFAULT 0,
                total_messages INTEGER DEFAULT 0,
                total_files INTEGER DEFAULT 0,
                last_contact REAL,
                tags TEXT,
                notes TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_contacts(self):
        """加载联系人"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM contacts")
        rows = cursor.fetchall()
        conn.close()
        
        for row in rows:
            contact = Contact(
                node_id=row["node_id"],
                short_id=row["short_id"] or "",
                display_name=row["display_name"] or "",
                avatar=row["avatar"],
                is_friend=bool(row["is_friend"]),
                is_blocked=bool(row["is_blocked"]),
                total_messages=row["total_messages"],
                total_files=row["total_files"],
                last_contact=row["last_contact"]
            )
            self._contacts[contact.node_id] = contact
    
    # ========== 身份管理 ==========
    
    def get_my_short_id(self) -> str:
        """获取我的短ID"""
        return self.short_id or ""
    
    def get_my_node_id(self) -> str:
        """获取我的节点ID"""
        return self.node_id or ""
    
    def get_my_profile(self) -> Optional[NodeProfile]:
        """获取我的档案"""
        return self.profile
    
    def update_my_profile(self, **kwargs):
        """更新我的档案"""
        if self.profile:
            for key, value in kwargs.items():
                if hasattr(self.profile, key):
                    setattr(self.profile, key, value)
            self.directory_service.register_profile(self.profile)
    
    # ========== 连接建立 ==========
    
    async def connect_to_peer(self, short_id_or_code: str) -> Optional[str]:
        """
        连接到对端 (通过短ID)
        
        Args:
            short_id_or_code: 对方的短ID (数字)
            
        Returns:
            str: connection_id or None
        """
        # 解析短ID
        profile = self.directory_service.resolve_short_id(short_id_or_code)
        
        if not profile:
            logger.warning(f"Short ID not found: {short_id_or_code}")
            return None
        
        # 检查是否已连接
        existing = self.channel_manager.get_connection(peer_node_id=profile.node_id)
        if existing:
            return existing.connection_id
        
        # 创建连接
        connection_id = await self.channel_manager.create_connection(profile)
        
        if self._on_connection_changed:
            self._on_connection_changed(connection_id, profile)
        
        return connection_id
    
    async def disconnect_from_peer(self, peer_node_id: str):
        """断开与对端的连接"""
        connection = self.channel_manager.get_connection(peer_node_id=peer_node_id)
        if connection:
            await self.channel_manager.close_connection(connection.connection_id)
    
    def get_connection(self, peer_node_id: str = None, 
                       connection_id: str = None) -> Optional[P2PConnection]:
        """获取连接"""
        return self.channel_manager.get_connection(connection_id, peer_node_id)
    
    # ========== 消息发送 ==========
    
    async def send_text(self, recipient_short_id: str, text: str) -> Optional[str]:
        """发送文本消息"""
        profile = self.directory_service.resolve_short_id(recipient_short_id)
        if not profile:
            logger.warning(f"Recipient not found: {recipient_short_id}")
            return None
        
        return await self.channel_manager.send_message(
            profile.node_id, text, ChannelType.TEXT
        )
    
    async def send_file(self, recipient_short_id: str, file_path: str,
                       progress_callback: Callable = None) -> Optional[str]:
        """发送文件"""
        from pathlib import Path
        
        profile = self.directory_service.resolve_short_id(recipient_short_id)
        if not profile:
            return None
        
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return None
        
        # 设置进度回调
        if progress_callback:
            self.channel_manager._on_file_progress = progress_callback
        
        import hashlib
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        
        message = Message(
            msg_id=secrets.token_hex(8),
            channel_type=ChannelType.FILE,
            sender_id=self.node_id,
            recipient_id=profile.node_id,
            content=f"[文件] {path.name}",
            file_name=path.name,
            file_size=path.stat().st_size,
            file_path=str(path)
        )
        
        # 直接使用通道管理器
        connection = self.channel_manager.get_connection(peer_node_id=profile.node_id)
        if not connection:
            connection_id = await self.channel_manager.create_connection(profile)
            connection = self.channel_manager.get_connection(connection_id=connection_id)
        
        if connection:
            await self.channel_manager._send_file_message(connection, message)
            return message.msg_id
        
        return None
    
    async def send_email(self, recipient_short_id: str, subject: str,
                        body: str, attachments: List[str] = None):
        """发送邮件 (通过邮箱通道)"""
        # 复用去中心化邮箱
        from core.decentralized_mailbox import get_mailbox_hub
        
        hub = await get_mailbox_hub()
        
        profile = self.directory_service.resolve_short_id(recipient_short_id)
        if not profile:
            return None
        
        address = f"user@{profile.node_id[:16]}.p2p"
        
        return await hub.send_message(
            to_addrs=[address],
            subject=subject,
            body=body,
            attachments=attachments
        )
    
    # ========== 联系人管理 ==========
    
    def add_contact(self, short_id: str, display_name: str = "",
                   is_friend: bool = False) -> bool:
        """添加联系人"""
        profile = self.directory_service.resolve_short_id(short_id)
        if not profile:
            # 如果本地找不到, 记录待解析
            logger.warning(f"Contact short ID not found locally: {short_id}")
        
        contact = Contact(
            node_id=profile.node_id if profile else "",
            short_id=short_id,
            display_name=display_name or f"用户{short_id[-4:]}",
            is_friend=is_friend
        )
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO contacts 
                (node_id, short_id, display_name, is_friend, last_contact)
                VALUES (?, ?, ?, ?, ?)
            """, (contact.node_id, contact.short_id, contact.display_name,
                  int(contact.is_friend), time.time()))
            
            conn.commit()
            conn.close()
            
            self._contacts[contact.node_id] = contact
            return True
            
        except Exception as e:
            logger.error(f"Add contact failed: {e}")
            return False
    
    def get_contacts(self) -> List[Contact]:
        """获取所有联系人"""
        return list(self._contacts.values())
    
    def get_contact(self, short_id: str = None, 
                   node_id: str = None) -> Optional[Contact]:
        """获取联系人"""
        if short_id:
            for contact in self._contacts.values():
                if contact.short_id == short_id:
                    return contact
        if node_id:
            return self._contacts.get(node_id)
        return None
    
    def remove_contact(self, node_id: str):
        """删除联系人"""
        self._contacts.pop(node_id, None)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contacts WHERE node_id = ?", (node_id,))
        conn.commit()
        conn.close()
    
    # ========== 节点发现 ==========
    
    def discover_peers(self, tags: List[str] = None) -> List[NodeProfile]:
        """发现节点"""
        return self.directory_service.discover_peers(tags=tags)
    
    def get_online_peers(self) -> List[NodeProfile]:
        """获取在线节点"""
        return self.directory_service.get_online_peers()
    
    # ========== 事件处理 ==========
    
    def _handle_message(self, message: Message):
        """处理收到的消息"""
        # 更新联系人统计
        sender = message.sender_id
        if sender in self._contacts:
            contact = self._contacts[sender]
            contact.total_messages += 1
            contact.last_contact = time.time()
        
        # 触发回调
        if self._on_new_message:
            self._on_new_message(message)
    
    def _handle_peer_online(self, node_id: str):
        """节点上线"""
        logger.info(f"Peer online: {node_id[:16]}...")
        if self._on_peer_online:
            self._on_peer_online(node_id)
    
    def _handle_peer_offline(self, node_id: str):
        """节点下线"""
        logger.info(f"Peer offline: {node_id[:16]}...")
        if self._on_peer_offline:
            self._on_peer_offline(node_id)
    
    def _handle_connection_status(self, connection_id: str, status: ConnectionStatus):
        """连接状态变化"""
        logger.debug(f"Connection {connection_id} status: {status}")
        if self._on_connection_changed:
            connection = self.channel_manager.get_connection(connection_id)
            if connection:
                self._on_connection_changed(connection_id, connection)
    
    # ========== 回调设置 ==========
    
    def set_callbacks(self, **kwargs):
        """设置回调函数"""
        self._on_new_message = kwargs.get("on_new_message")
        self._on_peer_online = kwargs.get("on_peer_online")
        self._on_peer_offline = kwargs.get("on_peer_offline")
        self._on_connection_changed = kwargs.get("on_connection_changed")
    
    # ========== 状态查询 ==========
    
    def get_status(self) -> dict:
        """获取状态"""
        return {
            "initialized": self._initialized,
            "running": self._running,
            "node_id": self.node_id[:16] + "..." if self.node_id else None,
            "short_id": self.short_id,
            "display_name": self.profile.display_name if self.profile else None,
            "online_peers": len(self.get_online_peers()),
            "contacts": len(self._contacts),
            "connections": len(self.channel_manager.get_active_connections())
        }


# 全局获取函数
async def get_connector_hub() -> ConnectorHub:
    """获取连接器核心实例"""
    return await ConnectorHub.get_instance()


def get_connector_hub_sync() -> ConnectorHub:
    """同步获取连接器核心实例"""
    return ConnectorHub.get_instance_sync()
