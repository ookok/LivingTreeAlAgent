# -*- coding: utf-8 -*-
"""
工作空间管理 - Workspace Management
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set
import uuid
import json


class WorkspaceRole(Enum):
    """工作空间角色"""
    OWNER = "owner"          # 所有者
    ADMIN = "admin"          # 管理员
    EDITOR = "editor"        # 编辑者
    COMMENTER = "commenter"  # 评论者
    VIEWER = "viewer"        # 查看者


@dataclass
class WorkspaceMember:
    """工作空间成员"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_id: str = ""
    name: str = ""
    email: str = ""
    role: WorkspaceRole = WorkspaceRole.VIEWER
    joined_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    avatar_url: Optional[str] = None
    is_online: bool = False
    
    def can_edit(self) -> bool:
        """是否可以编辑"""
        return self.role in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.EDITOR]
    
    def can_comment(self) -> bool:
        """是否可以评论"""
        return self.role in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.EDITOR, WorkspaceRole.COMMENTER]
    
    def can_manage(self) -> bool:
        """是否可以管理"""
        return self.role in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]


@dataclass
class Workspace:
    """工作空间"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    description: str = ""
    owner_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    members: Dict[str, WorkspaceMember] = field(default_factory=dict)
    settings: Dict = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    is_public: bool = False
    max_members: int = 50
    
    def add_member(self, member: WorkspaceMember) -> bool:
        """添加成员"""
        if len(self.members) >= self.max_members:
            return False
        
        if member.user_id in self.members:
            return False
        
        self.members[member.user_id] = member
        
        # 如果是所有者
        if member.role == WorkspaceRole.OWNER:
            self.owner_id = member.user_id
        
        self.updated_at = datetime.now()
        return True
    
    def remove_member(self, user_id: str) -> bool:
        """移除成员"""
        if user_id not in self.members:
            return False
        
        member = self.members[user_id]
        if member.role == WorkspaceRole.OWNER:
            return False  # 不能移除所有者
        
        del self.members[user_id]
        self.updated_at = datetime.now()
        return True
    
    def update_member_role(self, user_id: str, new_role: WorkspaceRole) -> bool:
        """更新成员角色"""
        if user_id not in self.members:
            return False
        
        member = self.members[user_id]
        if member.role == WorkspaceRole.OWNER:
            return False  # 不能修改所有者角色
        
        member.role = new_role
        self.updated_at = datetime.now()
        return True
    
    def get_member(self, user_id: str) -> Optional[WorkspaceMember]:
        """获取成员"""
        return self.members.get(user_id)
    
    def get_online_members(self) -> List[WorkspaceMember]:
        """获取在线成员"""
        return [m for m in self.members.values() if m.is_online]
    
    def to_dict(self) -> Dict:
        """转字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "members": {
                uid: {
                    "id": m.id,
                    "user_id": m.user_id,
                    "name": m.name,
                    "role": m.role.value,
                    "is_online": m.is_online
                }
                for uid, m in self.members.items()
            },
            "settings": self.settings,
            "tags": self.tags,
            "is_public": self.is_public,
            "member_count": len(self.members)
        }


class WorkspaceManager:
    """工作空间管理器"""
    
    def __init__(self):
        self._workspaces: Dict[str, Workspace] = {}
        self._user_workspaces: Dict[str, Set[str]] = {}  # user_id -> workspace_ids
    
    def create_workspace(
        self,
        name: str,
        owner_id: str,
        owner_name: str,
        description: str = "",
        is_public: bool = False
    ) -> Workspace:
        """创建工作空间"""
        workspace = Workspace(
            name=name,
            description=description,
            owner_id=owner_id,
            is_public=is_public
        )
        
        # 添加所有者
        owner = WorkspaceMember(
            user_id=owner_id,
            name=owner_name,
            role=WorkspaceRole.OWNER,
            is_online=True
        )
        workspace.add_member(owner)
        
        self._workspaces[workspace.id] = workspace
        self._track_user_workspace(owner_id, workspace.id)
        
        return workspace
    
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """获取工作空间"""
        return self._workspaces.get(workspace_id)
    
    def delete_workspace(self, workspace_id: str) -> bool:
        """删除工作空间"""
        if workspace_id not in self._workspaces:
            return False
        
        workspace = self._workspaces[workspace_id]
        
        # 移除所有成员的跟踪
        for member in workspace.members.values():
            if member.user_id in self._user_workspaces:
                self._user_workspaces[member.user_id].discard(workspace_id)
        
        del self._workspaces[workspace_id]
        return True
    
    def get_user_workspaces(self, user_id: str) -> List[Workspace]:
        """获取用户的工作空间"""
        workspace_ids = self._user_workspaces.get(user_id, set())
        return [self._workspaces[wid] for wid in workspace_ids if wid in self._workspaces]
    
    def add_member(
        self,
        workspace_id: str,
        user_id: str,
        name: str,
        role: WorkspaceRole = WorkspaceRole.VIEWER
    ) -> bool:
        """添加成员"""
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return False
        
        member = WorkspaceMember(
            user_id=user_id,
            name=name,
            role=role
        )
        
        if workspace.add_member(member):
            self._track_user_workspace(user_id, workspace_id)
            return True
        
        return False
    
    def remove_member(self, workspace_id: str, user_id: str) -> bool:
        """移除成员"""
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return False
        
        if workspace.remove_member(user_id):
            if user_id in self._user_workspaces:
                self._user_workspaces[user_id].discard(workspace_id)
            return True
        
        return False
    
    def _track_user_workspace(self, user_id: str, workspace_id: str):
        """跟踪用户的工作空间"""
        if user_id not in self._user_workspaces:
            self._user_workspaces[user_id] = set()
        self._user_workspaces[user_id].add(workspace_id)
    
    def update_member_online_status(self, workspace_id: str, user_id: str, is_online: bool):
        """更新成员在线状态"""
        workspace = self._workspaces.get(workspace_id)
        if workspace:
            member = workspace.get_member(user_id)
            if member:
                member.is_online = is_online
                member.last_active = datetime.now()


# ── 全局实例 ──────────────────────────────────────────────────────────────────

_workspace_manager: Optional[WorkspaceManager] = None


def get_workspace_manager() -> WorkspaceManager:
    """获取工作空间管理器"""
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
    return _workspace_manager
