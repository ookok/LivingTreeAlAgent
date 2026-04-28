"""
ToolPermissions - 工具权限控制

实现工具访问权限控制，某些工具只允许特定智能体调用。

功能：
1. 定义角色和权限
2. 检查工具访问权限
3. 权限验证和授权
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class PermissionLevel(Enum):
    """权限级别"""
    READ = "read"
    EXECUTE = "execute"
    ADMIN = "admin"


class AgentRole(Enum):
    """智能体角色"""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    SYSTEM = "system"


@dataclass
class ToolPermission:
    """工具权限"""
    tool_name: str
    role: AgentRole
    permission: PermissionLevel


@dataclass
class AgentIdentity:
    """智能体身份"""
    agent_id: str
    role: AgentRole
    permissions: List[str] = field(default_factory=list)


class ToolPermissionManager:
    """
    工具权限管理器
    
    功能：
    1. 定义角色和权限
    2. 检查工具访问权限
    3. 权限验证和授权
    """
    
    def __init__(self):
        self._logger = logger.bind(component="ToolPermissionManager")
        self._permissions: List[ToolPermission] = []
        self._default_permissions = self._load_default_permissions()
    
    def _load_default_permissions(self) -> Dict[str, Dict[AgentRole, PermissionLevel]]:
        """加载默认权限"""
        return {
            "admin_tool": {
                AgentRole.ADMIN: PermissionLevel.ADMIN,
                AgentRole.SYSTEM: PermissionLevel.ADMIN
            },
            "web_crawler": {
                AgentRole.ADMIN: PermissionLevel.EXECUTE,
                AgentRole.USER: PermissionLevel.EXECUTE,
                AgentRole.GUEST: PermissionLevel.READ,
                AgentRole.SYSTEM: PermissionLevel.EXECUTE
            },
            "deep_search": {
                AgentRole.ADMIN: PermissionLevel.EXECUTE,
                AgentRole.USER: PermissionLevel.EXECUTE,
                AgentRole.GUEST: PermissionLevel.READ,
                AgentRole.SYSTEM: PermissionLevel.EXECUTE
            },
            "vector_database": {
                AgentRole.ADMIN: PermissionLevel.EXECUTE,
                AgentRole.USER: PermissionLevel.EXECUTE,
                AgentRole.GUEST: PermissionLevel.READ,
                AgentRole.SYSTEM: PermissionLevel.EXECUTE
            },
            "knowledge_graph": {
                AgentRole.ADMIN: PermissionLevel.EXECUTE,
                AgentRole.USER: PermissionLevel.EXECUTE,
                AgentRole.GUEST: PermissionLevel.READ,
                AgentRole.SYSTEM: PermissionLevel.EXECUTE
            },
            "task_queue": {
                AgentRole.ADMIN: PermissionLevel.ADMIN,
                AgentRole.USER: PermissionLevel.EXECUTE,
                AgentRole.GUEST: PermissionLevel.READ,
                AgentRole.SYSTEM: PermissionLevel.ADMIN
            },
            "skill_evolution": {
                AgentRole.ADMIN: PermissionLevel.EXECUTE,
                AgentRole.USER: PermissionLevel.READ,
                AgentRole.GUEST: PermissionLevel.READ,
                AgentRole.SYSTEM: PermissionLevel.EXECUTE
            }
        }
    
    def set_permission(self, tool_name: str, role: AgentRole, permission: PermissionLevel):
        """
        设置工具权限
        
        Args:
            tool_name: 工具名称
            role: 角色
            permission: 权限级别
        """
        # 移除旧权限
        self._permissions = [
            p for p in self._permissions 
            if not (p.tool_name == tool_name and p.role == role)
        ]
        
        # 添加新权限
        self._permissions.append(ToolPermission(
            tool_name=tool_name,
            role=role,
            permission=permission
        ))
        
        self._logger.info(f"设置权限: {tool_name} -> {role.value} -> {permission.value}")
    
    def check_permission(self, tool_name: str, agent_identity: AgentIdentity) -> bool:
        """
        检查权限
        
        Args:
            tool_name: 工具名称
            agent_identity: 智能体身份
            
        Returns:
            是否有权限
        """
        # 系统角色拥有所有权限
        if agent_identity.role == AgentRole.SYSTEM:
            return True
        
        # 管理员角色拥有所有权限
        if agent_identity.role == AgentRole.ADMIN:
            return True
        
        # 检查自定义权限
        for perm in self._permissions:
            if perm.tool_name == tool_name and perm.role == agent_identity.role:
                return perm.permission in [PermissionLevel.EXECUTE, PermissionLevel.ADMIN]
        
        # 检查默认权限
        if tool_name in self._default_permissions:
            default_perm = self._default_permissions[tool_name].get(agent_identity.role)
            if default_perm in [PermissionLevel.EXECUTE, PermissionLevel.ADMIN]:
                return True
        
        return False
    
    def can_read(self, tool_name: str, agent_identity: AgentIdentity) -> bool:
        """检查是否有读取权限"""
        if agent_identity.role == AgentRole.SYSTEM or agent_identity.role == AgentRole.ADMIN:
            return True
        
        for perm in self._permissions:
            if perm.tool_name == tool_name and perm.role == agent_identity.role:
                return perm.permission in [PermissionLevel.READ, PermissionLevel.EXECUTE, PermissionLevel.ADMIN]
        
        if tool_name in self._default_permissions:
            default_perm = self._default_permissions[tool_name].get(agent_identity.role)
            return default_perm in [PermissionLevel.READ, PermissionLevel.EXECUTE, PermissionLevel.ADMIN]
        
        return False
    
    def get_permissions_for_role(self, role: AgentRole) -> List[Dict[str, Any]]:
        """获取角色的所有权限"""
        permissions = []
        
        # 获取自定义权限
        for perm in self._permissions:
            if perm.role == role:
                permissions.append({
                    "tool_name": perm.tool_name,
                    "permission": perm.permission.value
                })
        
        # 获取默认权限
        for tool_name, role_perms in self._default_permissions.items():
            if role in role_perms:
                permissions.append({
                    "tool_name": tool_name,
                    "permission": role_perms[role].value
                })
        
        return permissions
    
    def get_allowed_tools(self, agent_identity: AgentIdentity) -> List[str]:
        """获取智能体允许使用的工具列表"""
        allowed_tools = []
        
        # 系统和管理员拥有所有权限
        if agent_identity.role in [AgentRole.SYSTEM, AgentRole.ADMIN]:
            return ["all"]
        
        # 检查自定义权限
        for perm in self._permissions:
            if perm.role == agent_identity.role:
                if perm.permission in [PermissionLevel.EXECUTE, PermissionLevel.ADMIN]:
                    allowed_tools.append(perm.tool_name)
        
        # 检查默认权限
        for tool_name, role_perms in self._default_permissions.items():
            if agent_identity.role in role_perms:
                perm = role_perms[agent_identity.role]
                if perm in [PermissionLevel.EXECUTE, PermissionLevel.ADMIN]:
                    allowed_tools.append(tool_name)
        
        return list(set(allowed_tools))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        role_counts = {}
        for role in AgentRole:
            role_counts[role.value] = len([p for p in self._permissions if p.role == role])
        
        return {
            "total_custom_permissions": len(self._permissions),
            "permissions_by_role": role_counts,
            "default_permissions_count": len(self._default_permissions)
        }