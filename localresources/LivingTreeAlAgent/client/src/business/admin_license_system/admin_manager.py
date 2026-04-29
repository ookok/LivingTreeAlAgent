"""
管理员管理系统
Admin Management System

功能：
1. 管理员的添加、删除、禁用
2. 管理员数量限制（最多100个）
3. 管理员角色和权限管理
4. 管理员操作审计日志
"""

import sqlite3
import json
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from .admin_auth import AdminAuth, AdminUser, AdminRole, AdminPermission, get_admin_auth


class AdminAddResult:
    """管理员添加结果"""
    def __init__(self, success: bool, message: str = "", admin: AdminUser = None):
        self.success = success
        self.message = message
        self.admin = admin


class AdminRemoveResult:
    """管理员移除结果"""
    def __init__(self, success: bool, message: str = ""):
        self.success = success
        self.message = message


@dataclass
class AdminAuditLog:
    """管理员审计日志"""
    id: str
    admin_id: str
    admin_username: str
    action: str
    target_id: str = ""
    target_username: str = ""
    details: str = ""
    ip_address: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


class AdminManager:
    """
    管理员管理系统

    功能：
    1. 管理员CRUD操作
    2. 管理员数量限制
    3. 权限验证
    4. 审计日志
    """

    MAX_ADMINS = 100  # 默认最大管理员数

    def __init__(self, db_path: str = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path.home() / ".hermes-desktop" / "admin_manager.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._admin_auth = get_admin_auth()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化数据库"""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS admin_audit_log (
                    id TEXT PRIMARY KEY,
                    admin_id TEXT NOT NULL,
                    admin_username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_id TEXT DEFAULT '',
                    target_username TEXT DEFAULT '',
                    details TEXT DEFAULT '',
                    ip_address TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_audit_admin ON admin_audit_log(admin_id);
                CREATE INDEX IF NOT EXISTS idx_audit_action ON admin_audit_log(action);
                CREATE INDEX IF NOT EXISTS idx_audit_created ON admin_audit_log(created_at);
            """)
            conn.commit()

    def _log_action(
        self,
        admin_id: str,
        admin_username: str,
        action: str,
        target_id: str = "",
        target_username: str = "",
        details: str = "",
        ip_address: str = ""
    ):
        """记录操作日志"""
        log_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO admin_audit_log
                   (id, admin_id, admin_username, action, target_id, target_username, details, ip_address, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (log_id, admin_id, admin_username, action, target_id, target_username, details, ip_address, datetime.now().isoformat())
            )
            conn.commit()

    def get_max_admins(self) -> int:
        """获取最大管理员数量"""
        from .author_config import get_author_config_manager
        config_manager = get_author_config_manager()
        if config_manager.config:
            return config_manager.config.author_info.max_admins
        return self.MAX_ADMINS

    def can_add_admin(self) -> tuple:
        """
        检查是否可以添加管理员

        Returns:
            (can_add, current_count, max_count, message)
        """
        current_count = self._admin_auth.get_admin_count()
        max_count = self.get_max_admins()

        if current_count >= max_count:
            return False, current_count, max_count, f"管理员数量已达上限（{max_count}人）"
        return True, current_count, max_count, ""

    def add_admin(
        self,
        username: str,
        password: str,
        email: str = "",
        display_name: str = "",
        role: str = AdminRole.ADMIN,
        created_by: str = ""
    ) -> AdminAddResult:
        """
        添加管理员

        Args:
            username: 用户名
            password: 密码
            email: 邮箱
            display_name: 显示名称
            role: 角色
            created_by: 创建者ID

        Returns:
            AdminAddResult: 添加结果
        """
        current_user = self._admin_auth.current_user
        if not current_user:
            return AdminAddResult(False, "需要登录")

        # 检查权限
        if role == AdminRole.AUTHOR and not current_user.is_author:
            return AdminAddResult(False, "只有作者才能创建作者账号")

        if role == AdminRole.SUPER_ADMIN and not current_user.is_super_admin():
            return AdminAddResult(False, "只有超级管理员才能创建超级管理员")

        # 检查数量限制
        can_add, current, max_count, msg = self.can_add_admin()
        if not can_add:
            return AdminAddResult(False, msg)

        # 注册管理员
        result = self._admin_auth.register(
            username=username,
            password=password,
            email=email,
            display_name=display_name,
            role=role
        )

        if result.success:
            # 记录审计日志
            self._log_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action="ADD_ADMIN",
                target_id=result.user.id,
                target_username=username,
                details=f"创建了管理员 {username}，角色: {role}"
            )

        return AdminAddResult(result.success, result.message, result.user)

    def remove_admin(self, admin_id: str, reason: str = "") -> AdminRemoveResult:
        """
        删除管理员

        Args:
            admin_id: 管理员ID
            reason: 删除原因

        Returns:
            AdminRemoveResult: 删除结果
        """
        current_user = self._admin_auth.current_user
        if not current_user:
            return AdminRemoveResult(False, "需要登录")

        # 获取目标管理员
        target = self._admin_auth.get_admin(admin_id)
        if not target:
            return AdminRemoveResult(False, "管理员不存在")

        # 不能删除自己
        if target.id == current_user.id:
            return AdminRemoveResult(False, "不能删除自己")

        # 不能删除作者
        if target.is_author:
            return AdminRemoveResult(False, "不能删除作者账号")

        # 检查权限
        if target.role == AdminRole.SUPER_ADMIN and not current_user.is_super_admin():
            return AdminRemoveResult(False, "权限不足")

        # 删除管理员
        if self._admin_auth.delete_admin(admin_id):
            # 记录审计日志
            self._log_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action="REMOVE_ADMIN",
                target_id=admin_id,
                target_username=target.username,
                details=f"删除了管理员 {target.username}，原因: {reason}"
            )
            return AdminRemoveResult(True, "删除成功")

        return AdminRemoveResult(False, "删除失败")

    def disable_admin(self, admin_id: str, reason: str = "") -> AdminRemoveResult:
        """
        禁用管理员

        Args:
            admin_id: 管理员ID
            reason: 禁用原因

        Returns:
            AdminRemoveResult: 结果
        """
        current_user = self._admin_auth.current_user
        if not current_user:
            return AdminRemoveResult(False, "需要登录")

        target = self._admin_auth.get_admin(admin_id)
        if not target:
            return AdminRemoveResult(False, "管理员不存在")

        if target.id == current_user.id:
            return AdminRemoveResult(False, "不能禁用自己")

        if target.is_author:
            return AdminRemoveResult(False, "不能禁用作者账号")

        if self._admin_auth.disable_admin(admin_id):
            self._log_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action="DISABLE_ADMIN",
                target_id=admin_id,
                target_username=target.username,
                details=f"禁用了管理员 {target.username}，原因: {reason}"
            )
            return AdminRemoveResult(True, "禁用成功")

        return AdminRemoveResult(False, "禁用失败")

    def enable_admin(self, admin_id: str) -> AdminRemoveResult:
        """启用管理员"""
        current_user = self._admin_auth.current_user
        if not current_user:
            return AdminRemoveResult(False, "需要登录")

        target = self._admin_auth.get_admin(admin_id)
        if not target:
            return AdminRemoveResult(False, "管理员不存在")

        if self._admin_auth.enable_admin(admin_id):
            self._log_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action="ENABLE_ADMIN",
                target_id=admin_id,
                target_username=target.username,
                details=f"启用了管理员 {target.username}"
            )
            return AdminRemoveResult(True, "启用成功")

        return AdminRemoveResult(False, "启用失败")

    def update_admin(
        self,
        admin_id: str,
        email: str = None,
        display_name: str = None,
        role: str = None
    ) -> AdminAddResult:
        """
        更新管理员信息

        Args:
            admin_id: 管理员ID
            email: 邮箱
            display_name: 显示名称
            role: 角色

        Returns:
            AdminAddResult: 结果
        """
        current_user = self._admin_auth.current_user
        if not current_user:
            return AdminAddResult(False, "需要登录")

        target = self._admin_auth.get_admin(admin_id)
        if not target:
            return AdminAddResult(False, "管理员不存在")

        # 更新邮箱和显示名
        if email is not None or display_name is not None:
            updates = {}
            if email is not None:
                updates['email'] = email
            if display_name is not None:
                updates['display_name'] = display_name

        # 更新角色
        if role is not None and role != target.role:
            # 检查权限
            if role == AdminRole.AUTHOR and not current_user.is_author:
                return AdminAddResult(False, "只有作者才能修改为作者角色")

            if role == AdminRole.SUPER_ADMIN and not current_user.is_super_admin():
                return AdminAddResult(False, "权限不足")

            if not self._admin_auth.update_admin_role(admin_id, role):
                return AdminAddResult(False, "更新角色失败")

            self._log_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action="UPDATE_ADMIN_ROLE",
                target_id=admin_id,
                target_username=target.username,
                details=f"将角色从 {target.role} 修改为 {role}"
            )

        return AdminAddResult(True, "更新成功", target)

    def get_audit_logs(
        self,
        admin_id: str = None,
        action: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AdminAuditLog]:
        """
        获取审计日志

        Args:
            admin_id: 管理员ID（可选，筛选）
            action: 操作类型（可选，筛选）
            limit: 返回数量
            offset: 偏移量

        Returns:
            List[AdminAuditLog]: 审计日志列表
        """
        query = "SELECT * FROM admin_audit_log WHERE 1=1"
        params = []

        if admin_id:
            query += " AND admin_id = ?"
            params.append(admin_id)

        if action:
            query += " AND action = ?"
            params.append(action)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        return [
            AdminAuditLog(
                id=row["id"],
                admin_id=row["admin_id"],
                admin_username=row["admin_username"],
                action=row["action"],
                target_id=row["target_id"] or "",
                target_username=row["target_username"] or "",
                details=row["details"] or "",
                ip_address=row["ip_address"] or "",
                created_at=row["created_at"]
            )
            for row in rows
        ]

    def get_admin_stats(self) -> Dict[str, Any]:
        """获取管理员统计"""
        all_admins = self._admin_auth.get_all_admins()
        active_count = len([a for a in all_admins if a.is_active])
        author_count = len([a for a in all_admins if a.is_author])
        super_admin_count = len([a for a in all_admins if a.role == AdminRole.SUPER_ADMIN])
        admin_count = len([a for a in all_admins if a.role == AdminRole.ADMIN])
        operator_count = len([a for a in all_admins if a.role == AdminRole.OPERATOR])

        return {
            'total': len(all_admins),
            'active': active_count,
            'max_allowed': self.get_max_admins(),
            'by_role': {
                'author': author_count,
                'super_admin': super_admin_count,
                'admin': admin_count,
                'operator': operator_count,
            }
        }

    def search_admins(self, keyword: str) -> List[AdminUser]:
        """搜索管理员"""
        all_admins = self._admin_auth.get_all_admins()
        keyword = keyword.lower()

        return [
            admin for admin in all_admins
            if keyword in admin.username.lower() or
               keyword in admin.email.lower() or
               keyword in admin.display_name.lower()
        ]


# 单例
_admin_manager: Optional[AdminManager] = None


def get_admin_manager() -> AdminManager:
    """获取管理员管理器单例"""
    global _admin_manager
    if _admin_manager is None:
        _admin_manager = AdminManager()
    return _admin_manager