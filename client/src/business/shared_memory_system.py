"""
全局共享记忆系统 (Shared Memory System)
======================================

借鉴 Claude Managed Agents 的群体记忆能力：
1. 全局记忆池 - 存储共享知识和技能
2. 权限管理 - 控制记忆的读写权限
3. 同步机制 - 多Agent间记忆同步
4. 版本控制 - 记忆更新的版本追踪

核心特性：
- 支持多用户/多Agent共享
- 细粒度权限控制
- 自动同步和冲突解决
- 版本历史和回滚

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import json
import time
import asyncio
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

logger = __import__('logging').getLogger(__name__)


class PermissionLevel(Enum):
    """权限级别"""
    NONE = "none"           # 无权限
    READ = "read"           # 只读权限
    WRITE = "write"         # 读写权限
    ADMIN = "admin"         # 管理员权限


class SharingScope(Enum):
    """共享范围"""
    PRIVATE = "private"     # 私有（仅自己可见）
    TEAM = "team"           # 团队共享
    ORGANIZATION = "org"    # 组织共享
    PUBLIC = "public"       # 公开共享


class SyncStatus(Enum):
    """同步状态"""
    SYNCED = "synced"       # 已同步
    PENDING = "pending"     # 待同步
    CONFLICT = "conflict"   # 冲突
    ERROR = "error"         # 同步错误


@dataclass
class MemoryAccessControl:
    """记忆访问控制"""
    user_id: str
    permission: PermissionLevel
    granted_at: float
    expires_at: Optional[float] = None


@dataclass
class MemoryVersion:
    """记忆版本"""
    version_id: str
    content: str
    timestamp: float
    author_id: str
    change_type: str  # create / update / delete
    previous_version: Optional[str] = None


@dataclass
class SharedMemoryItem:
    """共享记忆项"""
    id: str
    content: str
    scope: SharingScope
    owner_id: str
    created_at: float
    updated_at: float
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    permissions: List[MemoryAccessControl] = field(default_factory=list)
    versions: List[MemoryVersion] = field(default_factory=list)
    sync_status: SyncStatus = SyncStatus.SYNCED
    sync_error: Optional[str] = None


class SharedMemorySystem:
    """
    全局共享记忆系统
    
    核心功能：
    1. 全局记忆池管理
    2. 细粒度权限控制
    3. 多Agent间同步
    4. 版本控制和回滚
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
        
        # 记忆存储
        self._memory_store: Dict[str, SharedMemoryItem] = {}
        
        # 用户权限缓存
        self._permission_cache: Dict[str, Dict[str, PermissionLevel]] = {}
        
        # 配置参数
        self._config = {
            "max_items": 10000,
            "default_scope": "private",
            "sync_interval": 60,  # 同步间隔（秒）
            "version_history_limit": 10,
            "permission_cache_ttl": 300,  # 权限缓存过期时间（秒）
        }
        
        # 同步锁
        self._sync_lock = asyncio.Lock()
        
        # 远程同步接口（可扩展）
        self._remote_sync = None
        
        # 变更监听
        self._listeners: List[Callable] = []
        
        self._initialized = True
        logger.info("[SharedMemorySystem] 全局共享记忆系统初始化完成")
    
    def configure(self, **kwargs):
        """配置共享记忆系统"""
        self._config.update(kwargs)
        logger.info(f"[SharedMemorySystem] 配置更新: {kwargs}")
    
    def set_remote_sync(self, sync_callable: Callable):
        """设置远程同步接口"""
        self._remote_sync = sync_callable
    
    def add_listener(self, listener: Callable):
        """添加变更监听器"""
        self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable):
        """移除变更监听器"""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def store(self, content: str, user_id: str, 
              scope: SharingScope = None, tags: List[str] = None,
              metadata: Dict[str, Any] = None) -> str:
        """
        存储共享记忆
        
        Args:
            content: 记忆内容
            user_id: 用户ID
            scope: 共享范围（默认私有）
            tags: 标签列表
            metadata: 元数据
            
        Returns:
            记忆ID
        """
        scope = scope or SharingScope(self._config["default_scope"])
        
        # 创建记忆项
        item_id = f"shared_{uuid4().hex[:8]}"
        now = time.time()
        
        # 创建初始版本
        initial_version = MemoryVersion(
            version_id=f"v1_{uuid4().hex[:8]}",
            content=content,
            timestamp=now,
            author_id=user_id,
            change_type="create"
        )
        
        item = SharedMemoryItem(
            id=item_id,
            content=content,
            scope=scope,
            owner_id=user_id,
            created_at=now,
            updated_at=now,
            tags=tags or [],
            metadata=metadata or {},
            permissions=[],
            versions=[initial_version],
            sync_status=SyncStatus.PENDING
        )
        
        # 设置权限
        self._set_owner_permission(item, user_id)
        
        # 存储
        self._memory_store[item_id] = item
        
        # 清理超出限制的记忆
        self._cleanup_excess()
        
        # 触发变更通知
        self._notify_change("create", item_id, user_id)
        
        logger.debug(f"[SharedMemorySystem] 存储共享记忆: {item_id}, 用户: {user_id}, 范围: {scope.value}")
        return item_id
    
    def retrieve(self, query: str, user_id: str, 
                 scope: SharingScope = None, limit: int = 10) -> List[SharedMemoryItem]:
        """
        检索共享记忆（根据权限过滤）
        
        Args:
            query: 查询文本
            user_id: 用户ID
            scope: 共享范围过滤（可选）
            limit: 结果数量限制
            
        Returns:
            记忆项列表（用户有权限访问的）
        """
        results = []
        
        for item_id, item in self._memory_store.items():
            # 检查权限
            if not self._has_permission(user_id, item_id, PermissionLevel.READ):
                continue
            
            # 检查范围
            if scope and item.scope != scope:
                continue
            
            # 简单的文本匹配
            if query.lower() in item.content.lower():
                results.append(item)
        
        # 按更新时间排序
        results.sort(key=lambda x: x.updated_at, reverse=True)
        
        return results[:limit]
    
    def update(self, item_id: str, content: str, user_id: str) -> bool:
        """
        更新共享记忆
        
        Args:
            item_id: 记忆ID
            content: 新内容
            user_id: 用户ID
            
        Returns:
            是否更新成功
        """
        if item_id not in self._memory_store:
            return False
        
        item = self._memory_store[item_id]
        
        # 检查权限
        if not self._has_permission(user_id, item_id, PermissionLevel.WRITE):
            logger.warning(f"[SharedMemorySystem] 用户 {user_id} 没有写入权限")
            return False
        
        # 创建新版本
        now = time.time()
        new_version = MemoryVersion(
            version_id=f"v{len(item.versions)+1}_{uuid4().hex[:8]}",
            content=content,
            timestamp=now,
            author_id=user_id,
            change_type="update",
            previous_version=item.versions[-1].version_id if item.versions else None
        )
        
        # 更新内容
        item.content = content
        item.updated_at = now
        item.versions.append(new_version)
        item.sync_status = SyncStatus.PENDING
        
        # 限制版本历史数量
        if len(item.versions) > self._config["version_history_limit"]:
            item.versions = item.versions[-self._config["version_history_limit"]:]
        
        # 触发变更通知
        self._notify_change("update", item_id, user_id)
        
        logger.debug(f"[SharedMemorySystem] 更新共享记忆: {item_id}, 用户: {user_id}")
        return True
    
    def delete(self, item_id: str, user_id: str) -> bool:
        """
        删除共享记忆
        
        Args:
            item_id: 记忆ID
            user_id: 用户ID
            
        Returns:
            是否删除成功
        """
        if item_id not in self._memory_store:
            return False
        
        item = self._memory_store[item_id]
        
        # 检查权限（需要管理员权限或所有权）
        if not self._has_permission(user_id, item_id, PermissionLevel.ADMIN) and item.owner_id != user_id:
            logger.warning(f"[SharedMemorySystem] 用户 {user_id} 没有删除权限")
            return False
        
        # 创建删除版本记录
        now = time.time()
        delete_version = MemoryVersion(
            version_id=f"del_{uuid4().hex[:8]}",
            content="",
            timestamp=now,
            author_id=user_id,
            change_type="delete",
            previous_version=item.versions[-1].version_id if item.versions else None
        )
        
        # 标记为删除（软删除）
        item.content = ""
        item.updated_at = now
        item.versions.append(delete_version)
        item.sync_status = SyncStatus.PENDING
        
        # 触发变更通知
        self._notify_change("delete", item_id, user_id)
        
        logger.debug(f"[SharedMemorySystem] 删除共享记忆: {item_id}, 用户: {user_id}")
        return True
    
    def grant_permission(self, item_id: str, user_id: str, 
                         permission: PermissionLevel, expires_at: float = None) -> bool:
        """
        授予用户权限
        
        Args:
            item_id: 记忆ID
            user_id: 用户ID
            permission: 权限级别
            expires_at: 过期时间（可选）
            
        Returns:
            是否成功
        """
        if item_id not in self._memory_store:
            return False
        
        item = self._memory_store[item_id]
        
        # 检查是否已存在权限
        existing = next((p for p in item.permissions if p.user_id == user_id), None)
        
        if existing:
            # 更新现有权限
            existing.permission = permission
            existing.expires_at = expires_at
        else:
            # 添加新权限
            item.permissions.append(MemoryAccessControl(
                user_id=user_id,
                permission=permission,
                granted_at=time.time(),
                expires_at=expires_at
            ))
        
        # 清除权限缓存
        self._invalidate_permission_cache(user_id, item_id)
        
        logger.debug(f"[SharedMemorySystem] 授予权限: {item_id} -> {user_id}: {permission.value}")
        return True
    
    def revoke_permission(self, item_id: str, user_id: str) -> bool:
        """
        撤销用户权限
        
        Args:
            item_id: 记忆ID
            user_id: 用户ID
            
        Returns:
            是否成功
        """
        if item_id not in self._memory_store:
            return False
        
        item = self._memory_store[item_id]
        
        # 移除权限
        item.permissions = [p for p in item.permissions if p.user_id != user_id]
        
        # 清除权限缓存
        self._invalidate_permission_cache(user_id, item_id)
        
        logger.debug(f"[SharedMemorySystem] 撤销权限: {item_id} -> {user_id}")
        return True
    
    def get_version_history(self, item_id: str, user_id: str) -> Optional[List[MemoryVersion]]:
        """
        获取版本历史
        
        Args:
            item_id: 记忆ID
            user_id: 用户ID
            
        Returns:
            版本历史列表（如果有权限）
        """
        if item_id not in self._memory_store:
            return None
        
        item = self._memory_store[item_id]
        
        if not self._has_permission(user_id, item_id, PermissionLevel.READ):
            return None
        
        return item.versions
    
    def rollback(self, item_id: str, version_id: str, user_id: str) -> bool:
        """
        回滚到指定版本
        
        Args:
            item_id: 记忆ID
            version_id: 版本ID
            user_id: 用户ID
            
        Returns:
            是否成功
        """
        if item_id not in self._memory_store:
            return False
        
        item = self._memory_store[item_id]
        
        # 检查权限
        if not self._has_permission(user_id, item_id, PermissionLevel.WRITE):
            return False
        
        # 查找版本
        version = next((v for v in item.versions if v.version_id == version_id), None)
        if not version:
            return False
        
        # 回滚内容
        item.content = version.content
        item.updated_at = time.time()
        item.sync_status = SyncStatus.PENDING
        
        # 创建回滚版本记录
        new_version = MemoryVersion(
            version_id=f"rollback_{uuid4().hex[:8]}",
            content=version.content,
            timestamp=time.time(),
            author_id=user_id,
            change_type=f"rollback_to_{version_id}",
            previous_version=item.versions[-1].version_id if item.versions else None
        )
        item.versions.append(new_version)
        
        # 触发变更通知
        self._notify_change("rollback", item_id, user_id)
        
        logger.debug(f"[SharedMemorySystem] 回滚记忆: {item_id} -> {version_id}")
        return True
    
    async def sync(self, user_id: str):
        """
        同步记忆到远程（异步）
        
        Args:
            user_id: 用户ID
        """
        async with self._sync_lock:
            if not self._remote_sync:
                logger.warning("[SharedMemorySystem] 没有配置远程同步接口")
                return
            
            try:
                # 获取待同步的项目
                pending_items = [
                    item for item in self._memory_store.values()
                    if item.sync_status == SyncStatus.PENDING
                ]
                
                if not pending_items:
                    return
                
                # 调用远程同步
                await self._remote_sync(pending_items, user_id)
                
                # 更新同步状态
                for item in pending_items:
                    item.sync_status = SyncStatus.SYNCED
                    item.sync_error = None
                
                logger.info(f"[SharedMemorySystem] 同步完成，同步了 {len(pending_items)} 个项目")
                
            except Exception as e:
                logger.error(f"[SharedMemorySystem] 同步失败: {e}")
                # 更新失败状态
                for item in self._memory_store.values():
                    if item.sync_status == SyncStatus.PENDING:
                        item.sync_status = SyncStatus.ERROR
                        item.sync_error = str(e)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        scope_counts = {}
        for item in self._memory_store.values():
            scope = item.scope.value
            scope_counts[scope] = scope_counts.get(scope, 0) + 1
        
        return {
            "total_items": len(self._memory_store),
            "scope_counts": scope_counts,
            "config": self._config,
        }
    
    # ========== 私有方法 ==========
    
    def _has_permission(self, user_id: str, item_id: str, permission: PermissionLevel) -> bool:
        """检查用户是否有权限"""
        if item_id not in self._memory_store:
            return False
        
        item = self._memory_store[item_id]
        
        # 优先检查所有者权限（所有者自动拥有 ADMIN 权限）
        if item.owner_id == user_id:
            return True
        
        # 检查权限列表
        for access in item.permissions:
            if access.user_id == user_id:
                # 检查是否过期
                if access.expires_at and access.expires_at < time.time():
                    continue
                
                return access.permission.value >= permission.value
        
        # 检查公开范围
        if item.scope == SharingScope.PUBLIC:
            return permission.value <= PermissionLevel.READ.value
        
        # 默认无权限
        return False
    
    def _set_owner_permission(self, item: SharedMemoryItem, user_id: str):
        """设置所有者权限"""
        item.permissions.append(MemoryAccessControl(
            user_id=user_id,
            permission=PermissionLevel.ADMIN,
            granted_at=time.time()
        ))
    
    def _invalidate_permission_cache(self, user_id: str, item_id: str):
        """清除权限缓存"""
        cache_key = f"{user_id}_{item_id}"
        if cache_key in self._permission_cache:
            del self._permission_cache[cache_key]
    
    def _cleanup_excess(self):
        """清理超出限制的记忆"""
        max_items = self._config["max_items"]
        
        if len(self._memory_store) <= max_items:
            return
        
        # 按更新时间排序，删除最旧的
        sorted_items = sorted(
            self._memory_store.items(),
            key=lambda x: x[1].updated_at
        )
        
        # 删除超出限制的部分
        items_to_delete = sorted_items[:-max_items]
        for item_id, _ in items_to_delete:
            del self._memory_store[item_id]
        
        logger.info(f"[SharedMemorySystem] 清理了 {len(items_to_delete)} 个旧记忆")
    
    def _notify_change(self, change_type: str, item_id: str, user_id: str):
        """通知变更"""
        for listener in self._listeners:
            try:
                listener({
                    "type": change_type,
                    "item_id": item_id,
                    "user_id": user_id,
                    "timestamp": time.time()
                })
            except Exception as e:
                logger.error(f"[SharedMemorySystem] 通知监听器失败: {e}")


# 便捷函数
def get_shared_memory() -> SharedMemorySystem:
    """获取全局共享记忆系统单例"""
    return SharedMemorySystem()


__all__ = [
    "PermissionLevel",
    "SharingScope",
    "SyncStatus",
    "MemoryAccessControl",
    "MemoryVersion",
    "SharedMemoryItem",
    "SharedMemorySystem",
    "get_shared_memory",
]