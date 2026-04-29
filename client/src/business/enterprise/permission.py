"""
权限管理模块
Permission Management Module

实现细粒度的权限管理系统
from __future__ import annotations
"""


from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field


class PermissionAction:
    """权限操作"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    SHARE = "share"
    MANAGE = "manage"


class PermissionType:
    """权限类型"""
    USER = "user"
    GROUP = "group"
    ROLE = "role"


@dataclass
class Permission:
    """权限模型"""
    id: str
    subject_type: str  # user, group, role
    subject_id: str
    resource_id: str
    actions: Set[str]
    is_deny: bool = False
    expires_at: Optional[int] = None

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "resource_id": self.resource_id,
            "actions": list(self.actions),
            "is_deny": self.is_deny,
            "expires_at": self.expires_at
        }

    @classmethod
    def from_dict(cls, data: Dict) -> Permission:
        """从字典创建"""
        return cls(
            id=data.get("id"),
            subject_type=data.get("subject_type"),
            subject_id=data.get("subject_id"),
            resource_id=data.get("resource_id"),
            actions=set(data.get("actions", [])),
            is_deny=data.get("is_deny", False),
            expires_at=data.get("expires_at")
        )


class PermissionManager:
    """权限管理器"""

    def __init__(self):
        self.permissions: Dict[str, List[Permission]] = {}  # {resource_id: [permissions]}
        self.groups: Dict[str, Set[str]] = {}  # {group_id: [user_ids]}
        self.roles: Dict[str, Set[str]] = {}  # {role_id: [actions]}

    def add_permission(self, permission: Permission):
        """添加权限"""
        if permission.resource_id not in self.permissions:
            self.permissions[permission.resource_id] = []
        self.permissions[permission.resource_id].append(permission)

    def remove_permission(self, permission_id: str):
        """删除权限"""
        for resource_id, permissions in self.permissions.items():
            new_permissions = [p for p in permissions if p.id != permission_id]
            if len(new_permissions) < len(permissions):
                self.permissions[resource_id] = new_permissions
                return True
        return False

    def get_permissions(self, resource_id: str) -> List[Permission]:
        """获取资源的所有权限"""
        return self.permissions.get(resource_id, [])

    def check_permission(self, user_id: str, resource_id: str, action: str) -> bool:
        """检查用户是否有执行操作的权限"""
        # 获取资源的所有权限
        resource_permissions = self.permissions.get(resource_id, [])

        # 按优先级排序：拒绝权限优先于允许权限
        deny_permissions = [p for p in resource_permissions if p.is_deny]
        allow_permissions = [p for p in resource_permissions if not p.is_deny]

        # 检查拒绝权限
        for perm in deny_permissions:
            if self._is_subject_match(perm, user_id):
                if action in perm.actions:
                    return False

        # 检查允许权限
        for perm in allow_permissions:
            if self._is_subject_match(perm, user_id):
                if action in perm.actions:
                    return True

        # 默认拒绝
        return False

    def _is_subject_match(self, permission: Permission, user_id: str) -> bool:
        """检查用户是否与权限主体匹配"""
        if permission.subject_type == PermissionType.USER:
            return permission.subject_id == user_id
        elif permission.subject_type == PermissionType.GROUP:
            return user_id in self.groups.get(permission.subject_id, set())
        elif permission.subject_type == PermissionType.ROLE:
            # 这里简化处理，实际应该检查用户是否拥有该角色
            return False
        return False

    def add_user_to_group(self, user_id: str, group_id: str):
        """添加用户到组"""
        if group_id not in self.groups:
            self.groups[group_id] = set()
        self.groups[group_id].add(user_id)

    def remove_user_from_group(self, user_id: str, group_id: str):
        """从组中移除用户"""
        if group_id in self.groups:
            self.groups[group_id].discard(user_id)

    def create_role(self, role_id: str, actions: Set[str]):
        """创建角色"""
        self.roles[role_id] = actions

    def get_role_actions(self, role_id: str) -> Set[str]:
        """获取角色的权限"""
        return self.roles.get(role_id, set())

    def grant_permission(self, subject_type: str, subject_id: str, resource_id: str, actions: Set[str]):
        """授予权限"""
        import uuid
        permission = Permission(
            id=str(uuid.uuid4()),
            subject_type=subject_type,
            subject_id=subject_id,
            resource_id=resource_id,
            actions=actions,
            is_deny=False
        )
        self.add_permission(permission)
        return permission

    def deny_permission(self, subject_type: str, subject_id: str, resource_id: str, actions: Set[str]):
        """拒绝权限"""
        import uuid
        permission = Permission(
            id=str(uuid.uuid4()),
            subject_type=subject_type,
            subject_id=subject_id,
            resource_id=resource_id,
            actions=actions,
            is_deny=True
        )
        self.add_permission(permission)
        return permission

    def get_user_permissions(self, user_id: str) -> List[Permission]:
        """获取用户的所有权限"""
        user_permissions = []
        for resource_id, permissions in self.permissions.items():
            for perm in permissions:
                if self._is_subject_match(perm, user_id):
                    user_permissions.append(perm)
        return user_permissions

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_permissions = sum(len(perms) for perms in self.permissions.values())
        return {
            "total_resources": len(self.permissions),
            "total_permissions": total_permissions,
            "total_groups": len(self.groups),
            "total_roles": len(self.roles)
        }


# 单例
permission_manager = PermissionManager()


def get_permission_manager() -> PermissionManager:
    """获取权限管理器"""
    return permission_manager
