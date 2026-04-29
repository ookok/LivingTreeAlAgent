"""
智能创作与专业审核增强系统 - 协同创作系统
"""

import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum


class Permission(Enum):
    VIEW = "view"
    COMMENT = "comment"
    EDIT = "edit"
    REVIEW = "review"
    MANAGE = "manage"
    ADMIN = "admin"


class ActivityType(Enum):
    CREATE = "create"
    EDIT = "edit"
    COMMENT = "comment"
    REVIEW = "review"
    SHARE = "share"
    APPROVE = "approve"


@dataclass
class User:
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    email: str = ""
    role: str = "member"
    avatar: str = ""
    skills: List[str] = field(default_factory=list)
    reputation: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Workspace:
    workspace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    owner_id: str = ""
    members: Dict[str, str] = field(default_factory=dict)  # user_id -> role
    permissions: Dict[str, List[str]] = field(default_factory=dict)  # user_id -> [permissions]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Document:
    doc_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    workspace_id: str = ""
    owner_id: str = ""
    version: int = 1
    status: str = "draft"
    collaborators: Dict[str, str] = field(default_factory=dict)  # user_id -> permission
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Version:
    version_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str = ""
    version: int = 1
    content: str = ""
    author_id: str = ""
    changes_summary: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Comment:
    comment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str = ""
    user_id: str = ""
    content: str = ""
    position: Dict = field(default_factory=dict)  # {"line": 10, "offset": 5}
    reply_to: Optional[str] = None
    resolved: bool = False
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Activity:
    activity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str = ""
    doc_id: str = ""
    user_id: str = ""
    activity_type: ActivityType = ActivityType.EDIT
    content: str = ""
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


class OTAlgorithm:
    """操作转换算法 (Operational Transformation)"""
    
    @staticmethod
    def transform(op1: Dict, op2: Dict) -> tuple:
        """转换操作"""
        if op1["type"] == "insert" and op2["type"] == "insert":
            if op1["position"] <= op2["position"]:
                op2["position"] += len(op1["text"])
            else:
                op1["position"] += len(op2["text"])
        
        elif op1["type"] == "delete" and op2["type"] == "delete":
            # 处理重叠删除
            pass
        
        return op1, op2
    
    @staticmethod
    def compose(ops: List[Dict]) -> Dict:
        """组合操作"""
        if not ops:
            return {"type": "none"}
        
        result = ops[0].copy()
        for op in ops[1:]:
            if result["type"] == "insert" and op["type"] == "insert":
                if op["position"] == result["position"] + len(result["text"]):
                    result["text"] += op["text"]
        
        return result


class CursorManager:
    """多人光标管理"""
    
    def __init__(self):
        self.cursors: Dict[str, Dict] = {}  # doc_id -> {user_id -> cursor_info}
    
    def update_cursor(self, doc_id: str, user_id: str, position: Dict):
        """更新光标"""
        if doc_id not in self.cursors:
            self.cursors[doc_id] = {}
        
        self.cursors[doc_id][user_id] = {
            "position": position,
            "timestamp": datetime.now().isoformat(),
            "selection": position.get("selection", {})
        }
    
    def get_cursors(self, doc_id: str) -> Dict:
        """获取所有光标"""
        return self.cursors.get(doc_id, {})
    
    def remove_cursor(self, doc_id: str, user_id: str):
        """移除光标"""
        if doc_id in self.cursors:
            self.cursors[doc_id].pop(user_id, None)


class CollaborationSystem:
    """协同创作系统"""
    
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.workspaces: Dict[str, Workspace] = {}
        self.documents: Dict[str, Document] = {}
        self.versions: Dict[str, List[Version]] = {}  # doc_id -> versions
        self.comments: Dict[str, List[Comment]] = {}  # doc_id -> comments
        self.activities: List[Activity] = []
        
        self.ot = OTAlgorithm()
        self.cursor_manager = CursorManager()
        
        # 在线状态
        self.online_users: Dict[str, Set[str]] = {}  # doc_id -> {user_ids}
    
    def create_workspace(self, name: str, owner_id: str) -> Workspace:
        """创建工作空间"""
        workspace = Workspace(name=name, owner_id=owner_id)
        self.workspaces[workspace.workspace_id] = workspace
        return workspace
    
    def add_member(self, workspace_id: str, user_id: str, role: str = "member"):
        """添加成员"""
        workspace = self.workspaces.get(workspace_id)
        if workspace:
            workspace.members[user_id] = role
    
    def create_document(self, workspace_id: str, title: str, owner_id: str) -> Document:
        """创建文档"""
        doc = Document(
            title=title,
            workspace_id=workspace_id,
            owner_id=owner_id
        )
        self.documents[doc.doc_id] = doc
        self.versions[doc.doc_id] = []
        self.comments[doc.doc_id] = []
        self.online_users[doc.doc_id] = set()
        
        # 创建初始版本
        self.save_version(doc.doc_id, owner_id, "Initial version")
        
        return doc
    
    def update_document(self, doc_id: str, content: str, user_id: str) -> Version:
        """更新文档"""
        doc = self.documents.get(doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found")
        
        doc.content = content
        doc.version += 1
        doc.updated_at = datetime.now()
        
        return self.save_version(doc_id, user_id, f"Version {doc.version}")
    
    def save_version(self, doc_id: str, user_id: str, summary: str) -> Version:
        """保存版本"""
        doc = self.documents.get(doc_id)
        version = Version(
            doc_id=doc_id,
            version=doc.version if doc else 1,
            content=doc.content if doc else "",
            author_id=user_id,
            changes_summary=summary
        )
        
        if doc_id not in self.versions:
            self.versions[doc_id] = []
        self.versions[doc_id].append(version)
        
        # 限制版本数量
        if len(self.versions[doc_id]) > 100:
            self.versions[doc_id] = self.versions[doc_id][-100:]
        
        return version
    
    def get_version_history(self, doc_id: str) -> List[Version]:
        """获取版本历史"""
        return self.versions.get(doc_id, [])
    
    def add_comment(self, doc_id: str, user_id: str, content: str, position: Dict = None) -> Comment:
        """添加评论"""
        comment = Comment(
            doc_id=doc_id,
            user_id=user_id,
            content=content,
            position=position or {}
        )
        
        if doc_id not in self.comments:
            self.comments[doc_id] = []
        self.comments[doc_id].append(comment)
        
        self._log_activity(doc_id, user_id, ActivityType.COMMENT, f"Added comment: {content[:50]}")
        
        return comment
    
    def resolve_comment(self, doc_id: str, comment_id: str):
        """解决评论"""
        for comment in self.comments.get(doc_id, []):
            if comment.comment_id == comment_id:
                comment.resolved = True
    
    def get_comments(self, doc_id: str, unresolved_only: bool = False) -> List[Comment]:
        """获取评论"""
        comments = self.comments.get(doc_id, [])
        if unresolved_only:
            comments = [c for c in comments if not c.resolved]
        return comments
    
    def join_document(self, doc_id: str, user_id: str):
        """加入文档编辑"""
        if doc_id not in self.online_users:
            self.online_users[doc_id] = set()
        self.online_users[doc_id].add(user_id)
    
    def leave_document(self, doc_id: str, user_id: str):
        """离开文档编辑"""
        if doc_id in self.online_users:
            self.online_users[doc_id].discard(user_id)
    
    def get_online_users(self, doc_id: str) -> Set[str]:
        """获取在线用户"""
        return self.online_users.get(doc_id, set())
    
    def transform_operation(self, doc_id: str, op1: Dict, op2: Dict) -> tuple:
        """转换操作"""
        return self.ot.transform(op1, op2)
    
    def _log_activity(self, doc_id: str, user_id: str, activity_type: ActivityType, content: str):
        """记录活动"""
        activity = Activity(
            doc_id=doc_id,
            user_id=user_id,
            activity_type=activity_type,
            content=content
        )
        self.activities.append(activity)
        
        # 限制活动数量
        if len(self.activities) > 1000:
            self.activities = self.activities[-1000:]
    
    def get_activities(self, doc_id: str = None, limit: int = 50) -> List[Activity]:
        """获取活动"""
        activities = self.activities
        if doc_id:
            activities = [a for a in activities if a.doc_id == doc_id]
        return activities[-limit:]
    
    def share_document(self, doc_id: str, target_user_ids: List[str], permission: str = "view"):
        """分享文档"""
        doc = self.documents.get(doc_id)
        if doc:
            for uid in target_user_ids:
                doc.collaborators[uid] = permission


def create_collaboration_system() -> CollaborationSystem:
    return CollaborationSystem()
