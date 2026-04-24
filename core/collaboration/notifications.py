# -*- coding: utf-8 -*-
"""
通知系统 - Notification System
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable
import uuid


class NotificationType(Enum):
    """通知类型"""
    MENTION = "mention"           # 被 @ 提及
    COMMENT = "comment"          # 评论
    ASSIGNMENT = "assignment"    # 任务分配
    DUE_DATE = "due_date"        # 截止日期提醒
    STATUS_CHANGE = "status_change"  # 状态变更
    SHARE = "share"              # 分享
    UPDATE = "update"            # 更新
    WELCOME = "welcome"          # 欢迎


class NotificationPriority(Enum):
    """优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """通知"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    type: NotificationType = NotificationType.UPDATE
    priority: NotificationPriority = NotificationPriority.NORMAL
    recipient_id: str = ""
    sender_id: str = ""
    sender_name: str = ""
    title: str = ""
    content: str = ""
    workspace_id: Optional[str] = None
    document_id: Optional[str] = None
    thread_id: Optional[str] = None
    task_id: Optional[str] = None
    action_url: str = ""
    read: bool = False
    archived: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)
    
    def mark_read(self):
        """标记已读"""
        self.read = True
    
    def archive(self):
        """归档"""
        self.archived = True
    
    def to_dict(self) -> Dict:
        """转字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "priority": self.priority.value,
            "recipient_id": self.recipient_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "title": self.title,
            "content": self.content,
            "workspace_id": self.workspace_id,
            "document_id": self.document_id,
            "thread_id": self.thread_id,
            "task_id": self.task_id,
            "action_url": self.action_url,
            "read": self.read,
            "archived": self.archived,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }


class NotificationManager:
    """
    通知管理器
    
    管理用户通知的创建、存储和推送
    """
    
    def __init__(self):
        self._notifications: Dict[str, List[Notification]] = {}  # user_id -> notifications
        self._listeners: Dict[str, List[Callable]] = {}  # event_type -> callbacks
    
    # ── 创建通知 ──────────────────────────────────────────────────────────────
    
    def create(
        self,
        notification_type: NotificationType,
        recipient_id: str,
        sender_id: str,
        sender_name: str,
        title: str,
        content: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        **kwargs
    ) -> Notification:
        """创建通知"""
        notification = Notification(
            type=notification_type,
            recipient_id=recipient_id,
            sender_id=sender_id,
            sender_name=sender_name,
            title=title,
            content=content,
            priority=priority,
            workspace_id=kwargs.get('workspace_id'),
            document_id=kwargs.get('document_id'),
            thread_id=kwargs.get('thread_id'),
            task_id=kwargs.get('task_id'),
            action_url=kwargs.get('action_url', ''),
            expires_at=kwargs.get('expires_at')
        )
        
        self._add_notification(notification)
        self._emit('notification', notification)
        
        return notification
    
    def _add_notification(self, notification: Notification):
        """添加通知到用户"""
        user_id = notification.recipient_id
        
        if user_id not in self._notifications:
            self._notifications[user_id] = []
        
        self._notifications[user_id].insert(0, notification)  # 新通知在前
        
        # 限制通知数量
        if len(self._notifications[user_id]) > 100:
            self._notifications[user_id] = self._notifications[user_id][:100]
    
    # ── 查询通知 ──────────────────────────────────────────────────────────────
    
    def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Notification]:
        """获取用户通知"""
        notifications = self._notifications.get(user_id, [])
        
        if unread_only:
            notifications = [n for n in notifications if not n.read]
        
        return notifications[:limit]
    
    def get_unread_count(self, user_id: str) -> int:
        """获取未读数量"""
        notifications = self._notifications.get(user_id, [])
        return sum(1 for n in notifications if not n.read)
    
    def mark_read(self, user_id: str, notification_id: str) -> bool:
        """标记已读"""
        notifications = self._notifications.get(user_id, [])
        for n in notifications:
            if n.id == notification_id:
                n.mark_read()
                self._emit('read', n)
                return True
        return False
    
    def mark_all_read(self, user_id: str):
        """全部标记已读"""
        notifications = self._notifications.get(user_id, [])
        for n in notifications:
            n.read = True
        self._emit('all_read', user_id)
    
    def archive(self, user_id: str, notification_id: str) -> bool:
        """归档通知"""
        notifications = self._notifications.get(user_id, [])
        for n in notifications:
            if n.id == notification_id:
                n.archive()
                return True
        return False
    
    def delete(self, user_id: str, notification_id: str) -> bool:
        """删除通知"""
        if user_id not in self._notifications:
            return False
        
        notifications = self._notifications[user_id]
        for i, n in enumerate(notifications):
            if n.id == notification_id:
                del notifications[i]
                return True
        return False
    
    # ── 快捷创建 ──────────────────────────────────────────────────────────────
    
    def notify_mention(
        self,
        recipient_id: str,
        sender_id: str,
        sender_name: str,
        document_id: str,
        thread_id: str,
        content: str
    ) -> Notification:
        """通知被 @ 提及"""
        return self.create(
            notification_type=NotificationType.MENTION,
            recipient_id=recipient_id,
            sender_id=sender_id,
            sender_name=sender_name,
            title=f"{sender_name} 提到了你",
            content=content[:100],
            document_id=document_id,
            thread_id=thread_id,
            action_url=f"/document/{document_id}/thread/{thread_id}"
        )
    
    def notify_comment(
        self,
        recipient_id: str,
        sender_id: str,
        sender_name: str,
        document_id: str,
        thread_id: str
    ) -> Notification:
        """通知新评论"""
        return self.create(
            notification_type=NotificationType.COMMENT,
            recipient_id=recipient_id,
            sender_id=sender_id,
            sender_name=sender_name,
            title=f"{sender_name} 评论了文档",
            content="查看评论内容",
            document_id=document_id,
            thread_id=thread_id,
            action_url=f"/document/{document_id}/thread/{thread_id}"
        )
    
    def notify_assignment(
        self,
        recipient_id: str,
        sender_id: str,
        sender_name: str,
        task_id: str,
        task_title: str
    ) -> Notification:
        """通知任务分配"""
        return self.create(
            notification_type=NotificationType.ASSIGNMENT,
            recipient_id=recipient_id,
            sender_id=sender_id,
            sender_name=sender_name,
            title="新任务分配",
            content=task_title,
            task_id=task_id,
            action_url=f"/task/{task_id}",
            priority=NotificationPriority.HIGH
        )
    
    # ── 事件监听 ──────────────────────────────────────────────────────────────
    
    def add_listener(self, event_type: str, callback: Callable):
        """添加事件监听"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)
    
    def _emit(self, event_type: str, *args):
        """触发事件"""
        for callback in self._listeners.get(event_type, []):
            try:
                callback(*args)
            except Exception:
                pass


# ── 全局实例 ──────────────────────────────────────────────────────────────────

_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """获取通知管理器"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
