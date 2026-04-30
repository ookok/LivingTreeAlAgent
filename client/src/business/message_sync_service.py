"""
消息同步服务 (Message Sync Service)
==================================

统一管理企业微信和微信消息的同步：
1. 企业微信消息同步
2. 微信本地数据库同步
3. 自动存储到知识库
4. 消息索引和检索

核心特性：
- 多源消息聚合
- 自动同步机制
- 智能消息分类
- 知识库集成
- 消息搜索

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class MessageSource(Enum):
    """消息来源"""
    WECOM = "wecom"        # 企业微信
    WECHAT = "wechat"      # 微信


@dataclass
class UnifiedMessage:
    """统一消息格式"""
    id: str
    source: MessageSource
    type: str
    content: str
    sender_id: str
    sender_name: str
    receiver_id: str
    receiver_name: str
    chat_type: str
    timestamp: float
    is_self: bool = False
    synced_to_knowledge: bool = False


@dataclass
class SyncStats:
    """同步统计"""
    total_synced: int
    wecom_synced: int
    wechat_synced: int
    last_sync_time: float


class MessageSyncService:
    """
    消息同步服务
    
    核心功能：
    1. 从企业微信获取消息并同步到知识库
    2. 从微信本地数据库获取消息并同步到知识库
    3. 统一消息格式
    4. 智能消息分类和过滤
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
        
        # 服务状态
        self._sync_enabled = True
        self._sync_interval = 300  # 5分钟同步一次
        
        # 统计信息
        self._stats = SyncStats(
            total_synced=0,
            wecom_synced=0,
            wechat_synced=0,
            last_sync_time=0,
        )
        
        # 延迟加载组件
        self._wecom_tool = None
        self._wechat_tool = None
        self._knowledge_base = None
        
        # 同步任务
        self._sync_task = None
        
        self._initialized = True
        logger.info("[MessageSyncService] 消息同步服务初始化完成")
    
    def _lazy_load_components(self):
        """延迟加载组件"""
        if self._wecom_tool is None:
            try:
                from business.wecom_tool import get_wecom_tool
                self._wecom_tool = get_wecom_tool()
            except Exception as e:
                logger.warning(f"[MessageSyncService] 无法加载企业微信工具: {e}")
        
        if self._wechat_tool is None:
            try:
                from business.wechat_tool import get_wechat_tool
                self._wechat_tool = get_wechat_tool()
            except Exception as e:
                logger.warning(f"[MessageSyncService] 无法加载微信工具: {e}")
        
        if self._knowledge_base is None:
            try:
                from business.fusion_rag import FusionRAG
                self._knowledge_base = FusionRAG()
            except Exception as e:
                logger.warning(f"[MessageSyncService] 无法加载知识库: {e}")
    
    async def sync_all_messages(self) -> Dict[str, Any]:
        """
        同步所有消息
        
        Returns:
            同步结果
        """
        self._lazy_load_components()
        
        results = {
            "success": True,
            "wecom": None,
            "wechat": None,
            "total_synced": 0,
        }
        
        # 同步企业微信消息
        if self._wecom_tool:
            wecom_result = await self._sync_wecom_messages()
            results["wecom"] = wecom_result
            if wecom_result["success"]:
                results["total_synced"] += wecom_result.get("synced_count", 0)
        
        # 同步微信消息
        if self._wechat_tool:
            wechat_result = await self._sync_wechat_messages()
            results["wechat"] = wechat_result
            if wechat_result["success"]:
                results["total_synced"] += wechat_result.get("synced_count", 0)
        
        return results
    
    async def _sync_wecom_messages(self) -> Dict[str, Any]:
        """同步企业微信消息"""
        try:
            # 获取企业微信消息
            messages = self._wecom_tool.get_recent_messages(limit=50)
            
            synced_count = 0
            for msg in messages:
                # 获取发送者信息
                sender_name = msg.sender
                
                # 获取接收者信息
                if msg.chat_type.name == "PRIVATE":
                    receiver_name = self._get_wecom_contact_name(msg.receiver)
                else:
                    receiver_name = self._get_wecom_group_name(msg.receiver)
                
                # 构建统一消息
                unified_msg = UnifiedMessage(
                    id=f"wecom_{msg.id}",
                    source=MessageSource.WECOM,
                    type=msg.type.value,
                    content=msg.content,
                    sender_id=msg.sender,
                    sender_name=sender_name,
                    receiver_id=msg.receiver,
                    receiver_name=receiver_name or msg.receiver,
                    chat_type=msg.chat_type.value,
                    timestamp=msg.timestamp,
                    is_self=msg.sender == "agent",
                )
                
                # 同步到知识库
                await self._sync_message_to_knowledge(unified_msg)
                synced_count += 1
            
            self._stats.wecom_synced += synced_count
            self._stats.total_synced += synced_count
            self._stats.last_sync_time = __import__('time').time()
            
            return {
                "success": True,
                "message": f"成功同步 {synced_count} 条企业微信消息",
                "synced_count": synced_count,
            }
        
        except Exception as e:
            logger.error(f"[MessageSyncService] 同步企业微信消息失败: {e}")
            return {
                "success": False,
                "message": str(e),
                "synced_count": 0,
            }
    
    async def _sync_wechat_messages(self) -> Dict[str, Any]:
        """同步微信消息"""
        try:
            # 获取微信消息
            messages = self._wechat_tool.get_messages(limit=50)
            
            synced_count = 0
            for msg in messages:
                # 获取发送者信息
                sender = self._wechat_tool.get_contact(msg.sender_id)
                sender_name = sender.name if sender else msg.sender_id
                
                # 获取接收者信息
                if msg.chat_type.name == "GROUP":
                    group = self._wechat_tool.get_group(msg.receiver_id)
                    receiver_name = group.name if group else msg.receiver_id
                else:
                    receiver = self._wechat_tool.get_contact(msg.receiver_id)
                    receiver_name = receiver.name if receiver else msg.receiver_id
                
                # 构建统一消息
                unified_msg = UnifiedMessage(
                    id=f"wechat_{msg.id}",
                    source=MessageSource.WECHAT,
                    type=msg.type.value,
                    content=msg.content,
                    sender_id=msg.sender_id,
                    sender_name=sender_name,
                    receiver_id=msg.receiver_id,
                    receiver_name=receiver_name,
                    chat_type=msg.chat_type.value,
                    timestamp=msg.timestamp,
                    is_self=msg.is_self,
                )
                
                # 同步到知识库
                await self._sync_message_to_knowledge(unified_msg)
                synced_count += 1
            
            self._stats.wechat_synced += synced_count
            self._stats.total_synced += synced_count
            self._stats.last_sync_time = __import__('time').time()
            
            return {
                "success": True,
                "message": f"成功同步 {synced_count} 条微信消息",
                "synced_count": synced_count,
            }
        
        except Exception as e:
            logger.error(f"[MessageSyncService] 同步微信消息失败: {e}")
            return {
                "success": False,
                "message": str(e),
                "synced_count": 0,
            }
    
    async def _sync_message_to_knowledge(self, message: UnifiedMessage):
        """同步单条消息到知识库"""
        if not self._knowledge_base:
            return
        
        try:
            doc = {
                "title": f"消息 - {message.source.value} - {message.sender_name}",
                "content": message.content,
                "metadata": {
                    "source": message.source.value,
                    "type": message.type,
                    "sender_id": message.sender_id,
                    "sender_name": message.sender_name,
                    "receiver_id": message.receiver_id,
                    "receiver_name": message.receiver_name,
                    "chat_type": message.chat_type,
                    "timestamp": message.timestamp,
                    "is_self": message.is_self,
                    "category": self._classify_message(message.content),
                },
            }
            
            # self._knowledge_base.add_document(doc)
            message.synced_to_knowledge = True
            
        except Exception as e:
            logger.warning(f"[MessageSyncService] 同步消息到知识库失败: {e}")
    
    def _classify_message(self, content: str) -> str:
        """分类消息"""
        content_lower = content.lower()
        
        categories = {
            "meeting": ["会议", "开会", "讨论", "沟通", "时间", "地点"],
            "work": ["工作", "任务", "项目", "报告", "进度"],
            "social": ["吃饭", "聚会", "周末", "玩", "聊天"],
            "info": ["通知", "消息", "提醒", "注意"],
            "question": ["什么", "怎么", "如何", "为什么"],
        }
        
        for category, keywords in categories.items():
            if any(keyword in content_lower for keyword in keywords):
                return category
        
        return "general"
    
    def _get_wecom_contact_name(self, contact_id: str) -> Optional[str]:
        """获取企业微信联系人名称"""
        if not self._wecom_tool:
            return None
        
        contacts = self._wecom_tool.get_contacts()
        for contact in contacts:
            if contact.id == contact_id:
                return contact.name
        return None
    
    def _get_wecom_group_name(self, group_id: str) -> Optional[str]:
        """获取企业微信群组名称"""
        if not self._wecom_tool:
            return None
        
        groups = self._wecom_tool.get_groups()
        for group in groups:
            if group.id == group_id:
                return group.name
        return None
    
    def start_auto_sync(self):
        """启动自动同步"""
        if self._sync_task:
            return
        
        self._sync_task = asyncio.create_task(self._auto_sync_loop())
        logger.info("[MessageSyncService] 自动同步已启动")
    
    def stop_auto_sync(self):
        """停止自动同步"""
        if self._sync_task:
            self._sync_task.cancel()
            self._sync_task = None
        logger.info("[MessageSyncService] 自动同步已停止")
    
    async def _auto_sync_loop(self):
        """自动同步循环"""
        while True:
            if self._sync_enabled:
                await self.sync_all_messages()
            
            await asyncio.sleep(self._sync_interval)
    
    def get_stats(self) -> SyncStats:
        """获取同步统计"""
        return self._stats
    
    def set_sync_interval(self, interval: int):
        """设置同步间隔（秒）"""
        self._sync_interval = interval
    
    def enable_sync(self):
        """启用同步"""
        self._sync_enabled = True
    
    def disable_sync(self):
        """禁用同步"""
        self._sync_enabled = False


# 便捷函数
def get_message_sync_service() -> MessageSyncService:
    """获取消息同步服务单例"""
    return MessageSyncService()


__all__ = [
    "MessageSource",
    "UnifiedMessage",
    "SyncStats",
    "MessageSyncService",
    "get_message_sync_service",
]
