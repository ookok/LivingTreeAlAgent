# -*- coding: utf-8 -*-
"""
评论与反馈 - Comments and Feedback
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import uuid


class ReactionType(Enum):
    """表情反应"""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    HEART = "heart"
    LAUGH = "laugh"
    THINKING = "thinking"
    EYES = "eyes"


@dataclass
class Reaction:
    """表情反应"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_id: str = ""
    user_name: str = ""
    type: ReactionType = ReactionType.THUMBS_UP
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Comment:
    """评论"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    thread_id: str = ""
    content: str = ""
    author_id: str = ""
    author_name: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_edited: bool = False
    is_resolved: bool = False
    reactions: List[Reaction] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)  # @的用户
    attachments: List[Dict] = field(default_factory=list)
    
    def add_reaction(self, user_id: str, user_name: str, reaction_type: ReactionType):
        """添加反应"""
        # 检查是否已有
        for r in self.reactions:
            if r.user_id == user_id:
                return False
        
        reaction = Reaction(
            user_id=user_id,
            user_name=user_name,
            type=reaction_type
        )
        self.reactions.append(reaction)
        return True
    
    def remove_reaction(self, user_id: str) -> bool:
        """移除反应"""
        for i, r in enumerate(self.reactions):
            if r.user_id == user_id:
                del self.reactions[i]
                return True
        return False
    
    def get_reaction_counts(self) -> Dict[str, int]:
        """获取反应统计"""
        counts = {}
        for r in self.reactions:
            type_str = r.type.value
            counts[type_str] = counts.get(type_str, 0) + 1
        return counts
    
    def to_dict(self) -> Dict:
        """转字典"""
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "content": self.content,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_edited": self.is_edited,
            "is_resolved": self.is_resolved,
            "reactions": [
                {"id": r.id, "user_id": r.user_id, "type": r.type.value}
                for r in self.reactions
            ],
            "mentions": self.mentions,
            "reaction_counts": self.get_reaction_counts()
        }


@dataclass
class CommentThread:
    """评论线程"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    workspace_id: str = ""
    document_id: str = ""
    document_type: str = ""  # document, task, etc.
    anchor: Dict = field(default_factory=dict)  # 锚定位置 {type: "paragraph", id: "xxx"}
    subject: str = ""  # 主题（可为空）
    comments: List[Comment] = field(default_factory=list)
    resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_comment(
        self,
        content: str,
        author_id: str,
        author_name: str,
        mentions: Optional[List[str]] = None
    ) -> Comment:
        """添加评论"""
        # 提取 @mentions
        if mentions is None:
            mentions = self._extract_mentions(content)
        
        comment = Comment(
            thread_id=self.id,
            content=content,
            author_id=author_id,
            author_name=author_name,
            mentions=mentions
        )
        
        self.comments.append(comment)
        self.updated_at = datetime.now()
        
        return comment
    
    def resolve(self, user_id: str) -> bool:
        """解决线程"""
        self.resolved = True
        self.resolved_by = user_id
        self.resolved_at = datetime.now()
        self.updated_at = datetime.now()
        
        for comment in self.comments:
            comment.is_resolved = True
        
        return True
    
    def unresolve(self) -> bool:
        """取消解决"""
        self.resolved = False
        self.resolved_by = None
        self.resolved_at = None
        self.updated_at = datetime.now()
        return True
    
    def _extract_mentions(self, content: str) -> List[str]:
        """提取 @mentions"""
        mentions = []
        words = content.split()
        for word in words:
            if word.startswith('@') and len(word) > 1:
                mentions.append(word[1:])
        return mentions
    
    def to_dict(self) -> Dict:
        """转字典"""
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "document_id": self.document_id,
            "document_type": self.document_type,
            "anchor": self.anchor,
            "subject": self.subject,
            "comments": [c.to_dict() for c in self.comments],
            "resolved": self.resolved,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "comment_count": len(self.comments)
        }


class CommentManager:
    """评论管理器"""
    
    def __init__(self):
        self._threads: Dict[str, CommentThread] = {}  # thread_id -> thread
        self._document_threads: Dict[str, List[str]] = {}  # document_id -> [thread_ids]
        self._user_threads: Dict[str, List[str]] = {}  # user_id -> [thread_ids]
    
    def create_thread(
        self,
        workspace_id: str,
        document_id: str,
        document_type: str,
        creator_id: str,
        anchor: Optional[Dict] = None,
        subject: str = "",
        initial_comment: Optional[str] = None
    ) -> CommentThread:
        """创建评论线程"""
        thread = CommentThread(
            workspace_id=workspace_id,
            document_id=document_id,
            document_type=document_type,
            anchor=anchor or {},
            subject=subject,
            created_by=creator_id
        )
        
        self._threads[thread.id] = thread
        
        # 跟踪文档
        if document_id not in self._document_threads:
            self._document_threads[document_id] = []
        self._document_threads[document_id].append(thread.id)
        
        # 跟踪用户
        if creator_id not in self._user_threads:
            self._user_threads[creator_id] = []
        self._user_threads[creator_id].append(thread.id)
        
        # 添加初始评论
        if initial_comment:
            thread.add_comment(
                content=initial_comment,
                author_id=creator_id,
                author_name=creator_id  # 简化
            )
        
        return thread
    
    def get_thread(self, thread_id: str) -> Optional[CommentThread]:
        """获取线程"""
        return self._threads.get(thread_id)
    
    def get_document_threads(self, document_id: str) -> List[CommentThread]:
        """获取文档的所有线程"""
        thread_ids = self._document_threads.get(document_id, [])
        return [self._threads[tid] for tid in thread_ids if tid in self._threads]
    
    def get_user_threads(self, user_id: str) -> List[CommentThread]:
        """获取用户的线程"""
        thread_ids = self._user_threads.get(user_id, [])
        return [self._threads[tid] for tid in thread_ids if tid in self._threads]
    
    def delete_thread(self, thread_id: str) -> bool:
        """删除线程"""
        if thread_id not in self._threads:
            return False
        
        thread = self._threads[thread_id]
        
        # 清理跟踪
        doc_id = thread.document_id
        if doc_id in self._document_threads:
            self._document_threads[doc_id].remove(thread_id)
        
        for user_id in self._user_threads:
            if thread_id in self._user_threads[user_id]:
                self._user_threads[user_id].remove(thread_id)
        
        del self._threads[thread_id]
        return True


# ── 全局实例 ──────────────────────────────────────────────────────────────────

_comment_manager: Optional[CommentManager] = None


def get_comment_manager() -> CommentManager:
    """获取评论管理器"""
    global _comment_manager
    if _comment_manager is None:
        _comment_manager = CommentManager()
    return _comment_manager
