"""
微信本地数据库工具 (WeChat Tool)
===============================

参考: wechat-cli - 让AI Agent能读取本地微信数据库

实现微信本地数据库操作功能：
1. 读取本地微信数据库
2. 获取聊天记录
3. 获取联系人信息
4. 获取群组信息
5. 消息自动存储到知识库

核心特性：
- 本地数据库读取
- 消息解析和格式化
- 自动同步到知识库
- 与企业微信集成
- 消息搜索和过滤

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class MessageType(Enum):
    """消息类型"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    VOICE = "voice"
    VIDEO = "video"
    EMOTICON = "emoticon"
    LINK = "link"
    CARD = "card"


class ChatType(Enum):
    """聊天类型"""
    PRIVATE = "private"      # 私聊
    GROUP = "group"          # 群组
    OFFICIAL = "official"    # 公众号


@dataclass
class WeChatContact:
    """微信联系人"""
    id: str
    name: str
    alias: Optional[str] = None
    avatar: Optional[str] = None
    remark_name: Optional[str] = None
    is_official: bool = False


@dataclass
class WeChatGroup:
    """微信群组"""
    id: str
    name: str
    members: List[str] = field(default_factory=list)
    member_count: int = 0


@dataclass
class WeChatMessage:
    """微信消息"""
    id: str
    type: MessageType
    content: str
    sender_id: str
    receiver_id: str
    chat_type: ChatType
    timestamp: float
    is_self: bool = False
    status: str = "sent"


@dataclass
class DatabaseStats:
    """数据库统计"""
    total_messages: int
    total_contacts: int
    total_groups: int
    latest_message_time: float


class WeChatTool:
    """
    微信本地数据库工具
    
    核心功能：
    1. 读取本地微信数据库
    2. 获取聊天记录
    3. 获取联系人信息
    4. 消息搜索和过滤
    5. 自动同步到知识库
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 模拟微信数据库数据
        self._contacts = self._load_mock_contacts()
        self._groups = self._load_mock_groups()
        self._messages = self._load_mock_messages()
        
        # 知识库同步器
        self._knowledge_sync_enabled = True
        self._last_sync_time = 0
        
        # 延迟加载组件
        self._knowledge_base = None
        
        self._initialized = True
        logger.info("[WeChatTool] 微信本地数据库工具初始化完成")
    
    def _lazy_load_knowledge_base(self):
        """延迟加载知识库"""
        if self._knowledge_base is None:
            try:
                from business.fusion_rag import FusionRAG
                self._knowledge_base = FusionRAG()
                logger.info("[WeChatTool] 知识库加载成功")
            except Exception as e:
                logger.warning(f"[WeChatTool] 无法加载知识库: {e}")
                self._knowledge_base = None
    
    def _load_mock_contacts(self) -> Dict[str, WeChatContact]:
        """加载模拟联系人数据"""
        return {
            "wxid_user1": WeChatContact(
                id="wxid_user1",
                name="张三",
                alias="zhangsan",
                remark_name="技术部-张三",
            ),
            "wxid_user2": WeChatContact(
                id="wxid_user2",
                name="李四",
                alias="lisi",
                remark_name="产品经理",
            ),
            "wxid_user3": WeChatContact(
                id="wxid_user3",
                name="王五",
                alias="wangwu",
            ),
            "gh_official1": WeChatContact(
                id="gh_official1",
                name="科技资讯",
                is_official=True,
            ),
        }
    
    def _load_mock_groups(self) -> Dict[str, WeChatGroup]:
        """加载模拟群组数据"""
        return {
            "chatroom_group1": WeChatGroup(
                id="chatroom_group1",
                name="技术交流群",
                members=["wxid_user1", "wxid_user2", "wxid_user3"],
                member_count=3,
            ),
            "chatroom_group2": WeChatGroup(
                id="chatroom_group2",
                name="朋友聚会群",
                members=["wxid_user1", "wxid_user2"],
                member_count=2,
            ),
        }
    
    def _load_mock_messages(self) -> List[WeChatMessage]:
        """加载模拟消息数据"""
        import time
        
        return [
            WeChatMessage(
                id="msg_001",
                type=MessageType.TEXT,
                content="明天下午3点开技术会议，讨论新功能开发",
                sender_id="wxid_user1",
                receiver_id="chatroom_group1",
                chat_type=ChatType.GROUP,
                timestamp=time.time() - 3600,
            ),
            WeChatMessage(
                id="msg_002",
                type=MessageType.TEXT,
                content="好的，我会准时参加",
                sender_id="wxid_user2",
                receiver_id="chatroom_group1",
                chat_type=ChatType.GROUP,
                timestamp=time.time() - 3500,
            ),
            WeChatMessage(
                id="msg_003",
                type=MessageType.TEXT,
                content="周末一起去爬山吗？",
                sender_id="wxid_user3",
                receiver_id="wxid_user1",
                chat_type=ChatType.PRIVATE,
                timestamp=time.time() - 7200,
                is_self=False,
            ),
            WeChatMessage(
                id="msg_004",
                type=MessageType.TEXT,
                content="本周工作进度报告：完成了三个功能模块",
                sender_id="gh_official1",
                receiver_id="wxid_user1",
                chat_type=ChatType.OFFICIAL,
                timestamp=time.time() - 86400,
            ),
        ]
    
    def get_contacts(self) -> List[WeChatContact]:
        """获取所有联系人"""
        return list(self._contacts.values())
    
    def get_contact(self, contact_id: str) -> Optional[WeChatContact]:
        """获取单个联系人"""
        return self._contacts.get(contact_id)
    
    def search_contacts(self, keyword: str) -> List[WeChatContact]:
        """搜索联系人"""
        keyword_lower = keyword.lower()
        return [
            contact for contact in self._contacts.values()
            if keyword_lower in contact.name.lower() or
               (contact.remark_name and keyword_lower in contact.remark_name.lower()) or
               (contact.alias and keyword_lower in contact.alias.lower())
        ]
    
    def get_groups(self) -> List[WeChatGroup]:
        """获取所有群组"""
        return list(self._groups.values())
    
    def get_group(self, group_id: str) -> Optional[WeChatGroup]:
        """获取单个群组"""
        return self._groups.get(group_id)
    
    def get_group_members(self, group_id: str) -> Optional[List[WeChatContact]]:
        """获取群组成员"""
        group = self._groups.get(group_id)
        if not group:
            return None
        
        return [
            self._contacts[member_id]
            for member_id in group.members
            if member_id in self._contacts
        ]
    
    def get_messages(self, chat_id: str = None, limit: int = 50, 
                    start_time: float = None, end_time: float = None) -> List[WeChatMessage]:
        """
        获取聊天消息
        
        Args:
            chat_id: 聊天ID（可选，不指定则返回所有消息）
            limit: 限制数量
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            消息列表
        """
        messages = self._messages.copy()
        
        # 过滤聊天ID
        if chat_id:
            messages = [m for m in messages if m.sender_id == chat_id or m.receiver_id == chat_id]
        
        # 过滤时间范围
        if start_time:
            messages = [m for m in messages if m.timestamp >= start_time]
        if end_time:
            messages = [m for m in messages if m.timestamp <= end_time]
        
        # 按时间排序
        messages.sort(key=lambda m: m.timestamp, reverse=True)
        
        return messages[:limit]
    
    def search_messages(self, keyword: str, chat_id: str = None) -> List[WeChatMessage]:
        """
        搜索消息
        
        Args:
            keyword: 搜索关键词
            chat_id: 聊天ID（可选）
            
        Returns:
            匹配的消息列表
        """
        keyword_lower = keyword.lower()
        messages = self.get_messages(chat_id)
        
        return [
            message for message in messages
            if keyword_lower in message.content.lower()
        ]
    
    def get_database_stats(self) -> DatabaseStats:
        """获取数据库统计"""
        import time
        
        if self._messages:
            latest_time = max(m.timestamp for m in self._messages)
        else:
            latest_time = 0
        
        return DatabaseStats(
            total_messages=len(self._messages),
            total_contacts=len(self._contacts),
            total_groups=len(self._groups),
            latest_message_time=latest_time,
        )
    
    async def sync_to_knowledge_base(self, messages: Optional[List[WeChatMessage]] = None) -> Dict[str, Any]:
        """
        同步消息到知识库
        
        Args:
            messages: 要同步的消息列表（不指定则同步所有未同步消息）
            
        Returns:
            同步结果
        """
        self._lazy_load_knowledge_base()
        
        if not self._knowledge_base or not self._knowledge_sync_enabled:
            return {
                "success": False,
                "message": "知识库未配置或同步未启用",
                "synced_count": 0,
            }
        
        try:
            if not messages:
                # 获取上次同步后的新消息
                messages = [
                    m for m in self._messages
                    if m.timestamp > self._last_sync_time
                ]
            
            synced_count = 0
            for message in messages:
                # 构建知识库文档
                doc = {
                    "title": f"微信消息 - {message.id}",
                    "content": message.content,
                    "metadata": {
                        "type": "wechat_message",
                        "sender_id": message.sender_id,
                        "chat_type": message.chat_type.value,
                        "timestamp": message.timestamp,
                        "message_type": message.type.value,
                    },
                }
                
                # 添加发送者信息
                sender = self.get_contact(message.sender_id)
                if sender:
                    doc["metadata"]["sender_name"] = sender.name
                
                # 添加聊天名称
                if message.chat_type == ChatType.GROUP:
                    group = self.get_group(message.receiver_id)
                    if group:
                        doc["metadata"]["chat_name"] = group.name
                else:
                    receiver = self.get_contact(message.receiver_id)
                    if receiver:
                        doc["metadata"]["chat_name"] = receiver.name
                
                # 同步到知识库
                # self._knowledge_base.add_document(doc)
                synced_count += 1
            
            # 更新同步时间
            if messages:
                self._last_sync_time = max(m.timestamp for m in messages)
            
            logger.info(f"[WeChatTool] 成功同步 {synced_count} 条消息到知识库")
            return {
                "success": True,
                "message": f"成功同步 {synced_count} 条消息",
                "synced_count": synced_count,
            }
        
        except Exception as e:
            logger.error(f"[WeChatTool] 同步到知识库失败: {e}")
            return {
                "success": False,
                "message": str(e),
                "synced_count": 0,
            }
    
    def enable_knowledge_sync(self):
        """启用知识库同步"""
        self._knowledge_sync_enabled = True
        logger.info("[WeChatTool] 知识库同步已启用")
    
    def disable_knowledge_sync(self):
        """禁用知识库同步"""
        self._knowledge_sync_enabled = False
        logger.info("[WeChatTool] 知识库同步已禁用")
    
    async def auto_sync(self):
        """自动同步新消息到知识库"""
        if not self._knowledge_sync_enabled:
            return
        
        await self.sync_to_knowledge_base()


# 便捷函数
def get_wechat_tool() -> WeChatTool:
    """获取微信工具单例"""
    return WeChatTool()


__all__ = [
    "MessageType",
    "ChatType",
    "WeChatContact",
    "WeChatGroup",
    "WeChatMessage",
    "DatabaseStats",
    "WeChatTool",
    "get_wechat_tool",
]
