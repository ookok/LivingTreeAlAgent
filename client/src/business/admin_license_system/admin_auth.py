"""
管理员认证模块
Admin Authentication Module

功能：
1. 管理员注册、登录、登出
2. 作者身份自动识别
3. 权限验证
4. 会话管理
"""

import sqlite3
import hashlib
import uuid
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Callable
from enum import Flag, auto

from .author_config import AuthorConfigManager, get_author_config_manager


class AdminPermission(Flag):
    """管理员权限"""
    NONE = 0
    VIEW = auto()              # 查看
    GENERATE_LICENSE = auto()  # 生成序列号
    MANAGE_ADMINS = auto()     # 管理管理员
    VIEW_LOGS = auto()         # 查看日志
    SYSTEM_CONFIG = auto()      # 系统配置
    FULL = VIEW | GENERATE_LICENSE | MANAGE_ADMINS | VIEW_LOGS | SYSTEM_CONFIG


class AdminRole:
    """管理员角色"""
    AUTHOR = "author"           # 作者（发布者）
    SUPER_ADMIN = "super_admin" # 超级管理员
    ADMIN = "admin"             # 普通管理员
    OPERATOR = "operator"       # 操作员

    @staticmethod
    def get_permissions(role: str) -> AdminPermission:
        """获取角色默认权限"""
        permissions_map = {
            AdminRole.AUTHOR: AdminPermission.FULL,
            AdminRole.SUPER_ADMIN: AdminPermission.FULL,
            AdminRole.ADMIN: AdminPermission.VIEW | AdminPermission.GENERATE_LICENSE | AdminPermission.VIEW_LOGS,
            AdminRole.OPERATOR: AdminPermission.VIEW,
        }
        return permissions_map.get(role, AdminPermission.NONE)


@dataclass
class AdminUser:
    """管理员用户"""
    id: str
    username: str
    email: str = ""
    display_name: str = ""
    role: str = AdminRole.ADMIN
    permissions: int = 0  # AdminPermission 位掩码
    is_author: bool = False  # 是否为作者
    author_id: str = ""   # 作者ID（如果是作者）
    created_at: str = ""
    last_login: str = ""
    is_active: bool = True

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AdminUser":
        return cls(**data)

    def has_permission(self, permission: AdminPermission) -> bool:
        """检查是否有指定权限"""
        return bool(self.permissions & permission)

    def is_super_admin(self) -> bool:
        """是否为超级管理员或作者"""
        return self.role in (AdminRole.AUTHOR, AdminRole.SUPER_ADMIN)

    def can_generate_license(self) -> bool:
        """是否可以生成序列号"""
        return self.has_permission(AdminPermission.GENERATE_LICENSE)

    def can_manage_admins(self) -> bool:
        """是否可以管理管理员"""
        return self.has_permission(AdminPermission.MANAGE_ADMINS)


@dataclass
class AuthResult:
    """认证结果"""
    success: bool
    message: str = ""
    user: Optional[AdminUser] = None
    token: str = ""


class AdminAuth:
    """
    管理员认证系统

    功能：
    1. 管理员注册、登录、登出
    2. 作者身份验证
    3. 权限管理
    4. 会话管理
    """

    def __init__(self, db_path: str = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path.home() / ".hermes-desktop" / "admin_auth.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._author_config_manager = get_author_config_manager()
        self._current_user: Optional[AdminUser] = None
        self._session_token: Optional[str] = None

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
                CREATE TABLE IF NOT EXISTS admins (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    email TEXT,
                    display_name TEXT,
                    role TEXT DEFAULT 'admin',
                    permissions INTEGER DEFAULT 0,
                    is_author INTEGER DEFAULT 0,
                    author_id TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    last_login TEXT,
                    is_active INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS admin_sessions (
                    token TEXT PRIMARY KEY,
                    admin_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    FOREIGN KEY (admin_id) REFERENCES admins(id)
                );

                CREATE INDEX IF NOT EXISTS idx_admins_username ON admins(username);
                CREATE INDEX IF NOT EXISTS idx_admins_email ON admins(email);
                CREATE INDEX IF NOT EXISTS idx_sessions_admin ON admin_sessions(admin_id);
            """)
            conn.commit()

    def _hash_password(self, password: str, salt: str = None) -> tuple:
        """哈希密码"""
        if salt is None:
            salt = uuid.uuid4().hex[:16]

        hash_obj = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return hash_obj.hex(), salt

    def _verify_password(self, password: str, password_hash: str, salt: str) -> bool:
        """验证密码"""
        computed_hash, _ = self._hash_password(password, salt)
        return computed_hash == password_hash

    def register(
        self,
        username: str,
        password: str,
        email: str = "",
        display_name: str = "",
        role: str = AdminRole.ADMIN
    ) -> AuthResult:
        """
        注册管理员

        Args:
            username: 用户名
            password: 密码
            email: 邮箱
            display_name: 显示名称
            role: 角色（仅作者或超级管理员可创建更高权限角色）

        Returns:
            AuthResult: 注册结果
        """
        # 验证当前用户权限
        if not self._current_user:
            return AuthResult(False, "需要管理员权限")

        # 检查管理员数量限制
        admin_count = self.get_admin_count()
        max_admins = 100
        if self._author_config_manager.config:
            max_admins = self._author_config_manager.config.author_info.max_admins

        if admin_count >= max_admins:
            return AuthResult(False, f"管理员数量已达上限（{max_admins}人）")

        # 验证用户名
        if len(username) < 3:
            return AuthResult(False, "用户名至少需要3个字符")

        if not username.isalnum() and '_' not in username:
            return AuthResult(False, "用户名只能包含字母、数字和下划线")

        # 验证密码
        if len(password) < 6:
            return AuthResult(False, "密码至少需要6个字符")

        # 检查用户名是否存在
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id FROM admins WHERE username = ?",
                (username,)
            )
            if cursor.fetchone():
                return AuthResult(False, "用户名已存在")

        # 创建管理员
        admin_id = str(uuid.uuid4())
        password_hash, salt = self._hash_password(password)
        created_at = datetime.now().isoformat()

        # 获取默认权限
        permissions = AdminRole.get_permissions(role).value

        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT INTO admins
                       (id, username, password_hash, salt, email, display_name, role, permissions, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (admin_id, username, password_hash, salt, email, display_name or username, role, permissions, created_at)
                )
                conn.commit()

            user = AdminUser(
                id=admin_id,
                username=username,
                email=email,
                display_name=display_name or username,
                role=role,
                permissions=permissions,
                created_at=created_at
            )

            return AuthResult(True, "注册成功", user)

        except Exception as e:
            return AuthResult(False, f"注册失败: {e}")

    def login(self, username: str, password: str) -> AuthResult:
        """
        管理员登录

        Args:
            username: 用户名
            password: 密码

        Returns:
            AuthResult: 登录结果
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, username, password_hash, salt, email, display_name,
                          role, permissions, is_author, author_id, created_at, last_login, is_active
                   FROM admins WHERE username = ?""",
                (username,)
            )
            row = cursor.fetchone()

        if not row:
            return AuthResult(False, "用户名或密码错误")

        if not row["is_active"]:
            return AuthResult(False, "账号已被禁用")

        # 验证密码
        if not self._verify_password(password, row["password_hash"], row["salt"]):
            return AuthResult(False, "用户名或密码错误")

        # 更新最后登录时间
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE admins SET last_login = ? WHERE id = ?",
                (datetime.now().isoformat(), row["id"])
            )
            conn.commit()

        # 检查是否为作者
        is_author = False
        author_id = row["author_id"] or ""
        if self._author_config_manager.is_author(row["id"], row["email"] or ""):
            is_author = True
            author_id = self._author_config_manager.config.author_info.author_id

        # 创建会话
        session_token = self._create_session(row["id"])

        # 创建用户对象
        user = AdminUser(
            id=row["id"],
            username=row["username"],
            email=row["email"] or "",
            display_name=row["display_name"] or row["username"],
            role=row["role"],
            permissions=row["permissions"],
            is_author=is_author,
            author_id=author_id,
            created_at=row["created_at"],
            last_login=datetime.now().isoformat(),
            is_active=bool(row["is_active"])
        )

        self._current_user = user
        self._session_token = session_token

        return AuthResult(True, "登录成功", user, session_token)

    def author_login(self, author_id: str = None, email: str = None) -> AuthResult:
        """
        作者登录（无需密码，作者身份验证）

        Args:
            author_id: 作者ID
            email: 作者邮箱

        Returns:
            AuthResult: 登录结果
        """
        if not self._author_config_manager.config:
            return AuthResult(False, "未配置作者信息")

        author_info = self._author_config_manager.config.author_info

        # 验证作者身份
        if author_id and author_info.author_id != author_id:
            return AuthResult(False, "作者ID无效")

        if email and author_info.email != email:
            return AuthResult(False, "作者邮箱无效")

        # 检查是否已有作者账号
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, username, email, display_name, role, permissions, is_author, author_id, created_at, last_login, is_active FROM admins WHERE is_author = 1"
            )
            row = cursor.fetchone()

        if row:
            # 更新最后登录
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE admins SET last_login = ? WHERE id = ?",
                    (datetime.now().isoformat(), row["id"])
                )
                conn.commit()

            user = AdminUser(
                id=row["id"],
                username=row["username"],
                email=row["email"] or "",
                display_name=row["display_name"] or row["username"],
                role=AdminRole.AUTHOR,
                permissions=AdminPermission.FULL.value,
                is_author=True,
                author_id=author_info.author_id,
                created_at=row["created_at"],
                last_login=datetime.now().isoformat(),
                is_active=bool(row["is_active"])
            )
        else:
            # 创建作者账号
            admin_id = str(uuid.uuid4())
            session_token = self._create_session(admin_id)
            created_at = datetime.now().isoformat()

            with self._get_connection() as conn:
                conn.execute(
                    """INSERT INTO admins
                       (id, username, password_hash, salt, email, display_name, role, permissions, is_author, author_id, created_at, last_login, is_active)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (admin_id, f"author_{author_info.author_id[:8]}", "", "", author_info.email,
                     author_info.name, AdminRole.AUTHOR, AdminPermission.FULL.value, 1, author_info.author_id,
                     created_at, datetime.now().isoformat(), 1)
                )
                conn.commit()

            user = AdminUser(
                id=admin_id,
                username=f"author_{author_info.author_id[:8]}",
                email=author_info.email,
                display_name=author_info.name,
                role=AdminRole.AUTHOR,
                permissions=AdminPermission.FULL.value,
                is_author=True,
                author_id=author_info.author_id,
                created_at=created_at,
                last_login=datetime.now().isoformat(),
                is_active=True
            )

        self._current_user = user
        self._session_token = session_token

        return AuthResult(True, "作者登录成功", user, session_token)

    def logout(self):
        """登出"""
        if self._session_token:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM admin_sessions WHERE token = ?", (self._session_token,))
                conn.commit()

        self._current_user = None
        self._session_token = None

    def _create_session(self, admin_id: str) -> str:
        """创建会话"""
        token = uuid.uuid4().hex
        created_at = datetime.now().isoformat()

        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO admin_sessions (token, admin_id, created_at) VALUES (?, ?, ?)",
                (token, admin_id, created_at)
            )
            conn.commit()

        return token

    @property
    def current_user(self) -> Optional[AdminUser]:
        """当前登录用户"""
        return self._current_user

    @property
    def is_logged_in(self) -> bool:
        """是否已登录"""
        return self._current_user is not None

    @property
    def is_author(self) -> bool:
        """是否为作者"""
        return self._current_user is not None and self._current_user.is_author

    def get_admin_count(self) -> int:
        """获取管理员数量"""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM admins WHERE is_active = 1")
            return cursor.fetchone()[0]

    def get_all_admins(self) -> List[AdminUser]:
        """获取所有管理员"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, username, email, display_name, role, permissions,
                          is_author, author_id, created_at, last_login, is_active
                   FROM admins ORDER BY created_at DESC"""
            )
            rows = cursor.fetchall()

        return [
            AdminUser(
                id=row["id"],
                username=row["username"],
                email=row["email"] or "",
                display_name=row["display_name"] or row["username"],
                role=row["role"],
                permissions=row["permissions"],
                is_author=bool(row["is_author"]),
                author_id=row["author_id"] or "",
                created_at=row["created_at"],
                last_login=row["last_login"] or "",
                is_active=bool(row["is_active"])
            )
            for row in rows
        ]

    def get_admin(self, admin_id: str) -> Optional[AdminUser]:
        """获取管理员"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, username, email, display_name, role, permissions,
                          is_author, author_id, created_at, last_login, is_active
                   FROM admins WHERE id = ?""",
                (admin_id,)
            )
            row = cursor.fetchone()

        if not row:
            return None

        return AdminUser(
            id=row["id"],
            username=row["username"],
            email=row["email"] or "",
            display_name=row["display_name"] or row["username"],
            role=row["role"],
            permissions=row["permissions"],
            is_author=bool(row["is_author"]),
            author_id=row["author_id"] or "",
            created_at=row["created_at"],
            last_login=row["last_login"] or "",
            is_active=bool(row["is_active"])
        )

    def update_admin_permissions(self, admin_id: str, permissions: int) -> bool:
        """更新管理员权限"""
        if not self._current_user or not self._current_user.can_manage_admins():
            return False

        with self._get_connection() as conn:
            conn.execute(
                "UPDATE admins SET permissions = ? WHERE id = ?",
                (permissions, admin_id)
            )
            conn.commit()
        return True

    def update_admin_role(self, admin_id: str, role: str) -> bool:
        """更新管理员角色"""
        if not self._current_user or not self._current_user.can_manage_admins():
            return False

        permissions = AdminRole.get_permissions(role).value
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE admins SET role = ?, permissions = ? WHERE id = ?",
                (role, permissions, admin_id)
            )
            conn.commit()
        return True

    def disable_admin(self, admin_id: str) -> bool:
        """禁用管理员"""
        if not self._current_user or not self._current_user.can_manage_admins():
            return False

        # 不能禁用自己
        if self._current_user.id == admin_id:
            return False

        with self._get_connection() as conn:
            conn.execute(
                "UPDATE admins SET is_active = 0 WHERE id = ?",
                (admin_id,)
            )
            conn.commit()
        return True

    def enable_admin(self, admin_id: str) -> bool:
        """启用管理员"""
        if not self._current_user or not self._current_user.can_manage_admins():
            return False

        with self._get_connection() as conn:
            conn.execute(
                "UPDATE admins SET is_active = 1 WHERE id = ?",
                (admin_id,)
            )
            conn.commit()
        return True

    def delete_admin(self, admin_id: str) -> bool:
        """删除管理员"""
        if not self._current_user or not self._current_user.is_super_admin():
            return False

        # 不能删除自己
        if self._current_user.id == admin_id:
            return False

        with self._get_connection() as conn:
            conn.execute("DELETE FROM admin_sessions WHERE admin_id = ?", (admin_id,))
            conn.execute("DELETE FROM admins WHERE id = ?", (admin_id,))
            conn.commit()
        return True

    def check_permission(self, permission: AdminPermission) -> bool:
        """检查当前用户权限"""
        if not self._current_user:
            return False
        return self._current_user.has_permission(permission)


# 单例
_admin_auth: Optional[AdminAuth] = None


def get_admin_auth() -> AdminAuth:
    """获取管理员认证单例"""
    global _admin_auth
    if _admin_auth is None:
        _admin_auth = AdminAuth()
    return _admin_auth