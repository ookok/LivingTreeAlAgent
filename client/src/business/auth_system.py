"""
用户认证系统
User Authentication System

支持本地 SQLite 数据库的用户注册、登录、个人资料管理、密码重置、会话管理。

配置来源：NanochatConfig (client/src/business/nanochat_config.py)
"""

import sqlite3
import hashlib
import uuid
import json
import os
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Callable, Dict
from enum import Enum

from client.src.business.nanochat_config import config


class UserRole(Enum):
    """用户角色"""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


@dataclass
class UserProfile:
    """用户资料"""
    id: str
    username: str
    email: str = ""
    display_name: str = ""
    role: UserRole = UserRole.USER
    created_at: str = ""
    last_login: str = ""
    preferences: dict = field(default_factory=dict)
    avatar: str = ""
    bio: str = ""
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role.value,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "preferences": self.preferences,
            "avatar": self.avatar,
            "bio": self.bio
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        return cls(
            id=data.get("id", ""),
            username=data.get("username", ""),
            email=data.get("email", ""),
            display_name=data.get("display_name", ""),
            role=UserRole(data.get("role", "user")),
            created_at=data.get("created_at", ""),
            last_login=data.get("last_login", ""),
            preferences=data.get("preferences", {}),
            avatar=data.get("avatar", ""),
            bio=data.get("bio", "")
        )


class AuthResult:
    """认证结果"""
    def __init__(self, success: bool, message: str = "", user: UserProfile = None):
        self.success = success
        self.message = message
        self.user = user


class AuthSystem:
    """
    用户认证系统
    
    功能：
    1. 用户注册、登录、登出
    2. 密码加密存储
    3. 用户资料管理
    4. 会话管理
    5. 角色权限控制
    """
    
    def __init__(self, db_path: str = None):
        """
        初始化认证系统
        
        Args:
            db_path: 数据库路径（使用默认路径如果为None）
        """
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = self._get_default_db_path()
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # 当前登录用户
        self._current_user: Optional[UserProfile] = None
        self._session_token: Optional[str] = None
    
    def _get_default_db_path(self) -> Path:
        """获取默认数据库路径"""
        user_dir = Path.home() / ".hermes-desktop"
        if os.access(str(Path.home()), os.W_OK):
            return user_dir / "users.db"
        
        # 兜底
        return Path(__file__).parent.parent / "users.db"
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """初始化数据库"""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    email TEXT,
                    display_name TEXT,
                    role TEXT DEFAULT 'user',
                    created_at TEXT NOT NULL,
                    last_login TEXT,
                    preferences TEXT DEFAULT '{}',
                    avatar TEXT DEFAULT '',
                    bio TEXT DEFAULT '',
                    failed_attempts INTEGER DEFAULT 0,
                    locked_until TEXT
                );
                
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_reset_tokens_user ON password_reset_tokens(user_id);
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
        display_name: str = ""
    ) -> AuthResult:
        """
        注册新用户
        
        Args:
            username: 用户名
            password: 密码
            email: 邮箱
            display_name: 显示名称
            
        Returns:
            AuthResult: 注册结果
        """
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
                "SELECT id FROM users WHERE username = ?",
                (username,)
            )
            if cursor.fetchone():
                return AuthResult(False, "用户名已存在")
        
        # 创建用户
        user_id = str(uuid.uuid4())
        password_hash, salt = self._hash_password(password)
        created_at = datetime.now().isoformat()
        
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT INTO users 
                       (id, username, password_hash, salt, email, display_name, created_at, role)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, username, password_hash, salt, email, display_name or username, created_at, UserRole.USER.value)
                )
                conn.commit()
            
            user = UserProfile(
                id=user_id,
                username=username,
                email=email,
                display_name=display_name or username,
                role=UserRole.USER,
                created_at=created_at
            )
            
            return AuthResult(True, "注册成功", user)
            
        except Exception as e:
            return AuthResult(False, f"注册失败: {e}")
    
    def login(self, username: str, password: str, ip_address: str = "", user_agent: str = "") -> AuthResult:
        """
        用户登录
        
        Args:
            username: 用户名
            password: 密码
            ip_address: 客户端IP地址（可选）
            user_agent: 客户端User-Agent（可选）
            
        Returns:
            AuthResult: 登录结果
        """
        # 检查账户是否被锁定
        lock_message = self._check_account_locked(username)
        if lock_message:
            return AuthResult(False, lock_message)
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, username, password_hash, salt, email, display_name, 
                          role, created_at, last_login, preferences, avatar, bio
                   FROM users WHERE username = ?""",
                (username,)
            )
            row = cursor.fetchone()
        
        if not row:
            # 记录失败尝试（即使用户名不存在，防止枚举攻击）
            self._record_failed_attempt(username)
            return AuthResult(False, "用户名或密码错误")
        
        # 验证密码
        if not self._verify_password(password, row["password_hash"], row["salt"]):
            self._record_failed_attempt(username)
            return AuthResult(False, "用户名或密码错误")
        
        # 重置失败尝试次数
        self._reset_failed_attempts(row["id"])
        
        # 更新最后登录时间
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (datetime.now().isoformat(), row["id"])
            )
            conn.commit()
        
        # 创建会话
        session_token = self._create_session(row["id"], ip_address, user_agent)
        
        # 创建用户对象
        user = UserProfile(
            id=row["id"],
            username=row["username"],
            email=row["email"] or "",
            display_name=row["display_name"] or row["username"],
            role=UserRole(row["role"]),
            created_at=row["created_at"],
            last_login=datetime.now().isoformat(),
            preferences=json.loads(row["preferences"] or "{}"),
            avatar=row["avatar"] or "",
            bio=row["bio"] or ""
        )
        
        self._current_user = user
        self._session_token = session_token
        
        return AuthResult(True, "登录成功", user)
    
    def logout(self):
        """用户登出"""
        if self._session_token:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM sessions WHERE token = ?", (self._session_token,))
                conn.commit()
        
        self._current_user = None
        self._session_token = None
    
    def _create_session(self, user_id: str) -> str:
        """创建会话"""
        token = uuid.uuid4().hex
        created_at = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
                (token, user_id, created_at)
            )
            conn.commit()
        
        return token
    
    @property
    def current_user(self) -> Optional[UserProfile]:
        """当前登录用户"""
        return self._current_user
    
    @property
    def is_logged_in(self) -> bool:
        """是否已登录"""
        return self._current_user is not None
    
    def get_user(self, user_id: str) -> Optional[UserProfile]:
        """获取用户资料"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, username, email, display_name, role, 
                          created_at, last_login, preferences, avatar, bio
                   FROM users WHERE id = ?""",
                (user_id,)
            )
            row = cursor.fetchone()
        
        if not row:
            return None
        
        return UserProfile(
            id=row["id"],
            username=row["username"],
            email=row["email"] or "",
            display_name=row["display_name"] or row["username"],
            role=UserRole(row["role"]),
            created_at=row["created_at"],
            last_login=row["last_login"] or "",
            preferences=json.loads(row["preferences"] or "{}"),
            avatar=row["avatar"] or "",
            bio=row["bio"] or ""
        )
    
    def update_profile(self, user_id: str, **kwargs) -> bool:
        """
        更新用户资料
        
        Args:
            user_id: 用户ID
            **kwargs: 要更新的字段
            
        Returns:
            是否更新成功
        """
        allowed_fields = ["email", "display_name", "preferences", "avatar", "bio"]
        
        updates = {}
        for key, value in kwargs.items():
            if key in allowed_fields:
                if key == "preferences" and isinstance(value, dict):
                    updates[key] = json.dumps(value)
                else:
                    updates[key] = value
        
        if not updates:
            return False
        
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [user_id]
        
        try:
            with self._get_connection() as conn:
                conn.execute(
                    f"UPDATE users SET {set_clause} WHERE id = ?",
                    values
                )
                conn.commit()
            return True
        except Exception:
            return False
    
    def change_password(self, user_id: str, old_password: str, new_password: str) -> AuthResult:
        """
        修改密码
        
        Args:
            user_id: 用户ID
            old_password: 旧密码
            new_password: 新密码
            
        Returns:
            AuthResult: 修改结果
        """
        if len(new_password) < 6:
            return AuthResult(False, "新密码至少需要6个字符")
        
        # 获取当前密码
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT password_hash, salt FROM users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
        
        if not row:
            return AuthResult(False, "用户不存在")
        
        # 验证旧密码
        if not self._verify_password(old_password, row["password_hash"], row["salt"]):
            return AuthResult(False, "旧密码错误")
        
        # 更新密码
        new_hash, new_salt = self._hash_password(new_password)
        
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
                    (new_hash, new_salt, user_id)
                )
                conn.commit()
            return AuthResult(True, "密码修改成功")
        except Exception as e:
            return AuthResult(False, f"修改失败: {e}")
    
    def delete_user(self, user_id: str, password: str) -> AuthResult:
        """
        删除用户（谨慎操作）
        
        Args:
            user_id: 用户ID
            password: 密码确认
            
        Returns:
            AuthResult: 删除结果
        """
        # 获取用户
        user = self.get_user(user_id)
        if not user:
            return AuthResult(False, "用户不存在")
        
        # 验证密码
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT password_hash, salt FROM users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
        
        if not self._verify_password(password, row["password_hash"], row["salt"]):
            return AuthResult(False, "密码错误")
        
        # 删除用户
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
            
            # 如果是当前用户，登出
            if self._current_user and self._current_user.id == user_id:
                self.logout()
            
            return AuthResult(True, "用户已删除")
        except Exception as e:
            return AuthResult(False, f"删除失败: {e}")
    
    # ========== 密码重置功能 ==========
    
    def generate_reset_token(self, email: str) -> Optional[str]:
        """
        生成密码重置令牌
        
        Args:
            email: 用户邮箱
            
        Returns:
            重置令牌（如果找到用户）
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id FROM users WHERE email = ?",
                (email,)
            )
            row = cursor.fetchone()
        
        if not row:
            return None
        
        user_id = row["id"]
        token = uuid.uuid4().hex
        created_at = datetime.now().isoformat()
        expires_at = (datetime.now() + timedelta(hours=2)).isoformat()
        
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM password_reset_tokens WHERE user_id = ?",
                    (user_id,)
                )
                conn.execute(
                    """INSERT INTO password_reset_tokens 
                       (token, user_id, created_at, expires_at) 
                       VALUES (?, ?, ?, ?)""",
                    (token, user_id, created_at, expires_at)
                )
                conn.commit()
            
            return token
        except Exception:
            return None
    
    def validate_reset_token(self, token: str) -> Optional[str]:
        """
        验证密码重置令牌
        
        Args:
            token: 重置令牌
            
        Returns:
            用户ID（如果令牌有效）
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT user_id, expires_at FROM password_reset_tokens WHERE token = ?",
                (token,)
            )
            row = cursor.fetchone()
        
        if not row:
            return None
        
        # 检查是否过期
        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now() > expires_at:
            # 删除过期令牌
            with self._get_connection() as conn:
                conn.execute("DELETE FROM password_reset_tokens WHERE token = ?", (token,))
                conn.commit()
            return None
        
        return row["user_id"]
    
    def reset_password(self, token: str, new_password: str) -> AuthResult:
        """
        使用令牌重置密码
        
        Args:
            token: 重置令牌
            new_password: 新密码
            
        Returns:
            AuthResult: 重置结果
        """
        if len(new_password) < 6:
            return AuthResult(False, "新密码至少需要6个字符")
        
        user_id = self.validate_reset_token(token)
        if not user_id:
            return AuthResult(False, "无效或过期的重置令牌")
        
        # 更新密码
        new_hash, new_salt = self._hash_password(new_password)
        
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE users SET password_hash = ?, salt = ?, failed_attempts = 0 WHERE id = ?",
                    (new_hash, new_salt, user_id)
                )
                conn.execute("DELETE FROM password_reset_tokens WHERE token = ?", (token,))
                conn.commit()
            
            return AuthResult(True, "密码重置成功")
        except Exception as e:
            return AuthResult(False, f"重置失败: {e}")
    
    # ========== 会话管理 ==========
    
    def _create_session(self, user_id: str, ip_address: str = "", user_agent: str = "") -> str:
        """创建会话"""
        token = uuid.uuid4().hex
        created_at = datetime.now().isoformat()
        expires_at = (datetime.now() + timedelta(hours=24)).isoformat()
        
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO sessions 
                   (token, user_id, created_at, expires_at, ip_address, user_agent) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (token, user_id, created_at, expires_at, ip_address, user_agent)
            )
            conn.commit()
        
        return token
    
    def validate_session(self, token: str) -> Optional[UserProfile]:
        """
        验证会话令牌
        
        Args:
            token: 会话令牌
            
        Returns:
            用户对象（如果会话有效）
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT u.id, u.username, u.email, u.display_name, u.role, 
                          u.created_at, u.last_login, u.preferences, u.avatar, u.bio,
                          s.expires_at
                   FROM sessions s
                   JOIN users u ON s.user_id = u.id
                   WHERE s.token = ?""",
                (token,)
            )
            row = cursor.fetchone()
        
        if not row:
            return None
        
        # 检查是否过期
        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now() > expires_at:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
            return None
        
        # 刷新会话过期时间
        new_expires_at = (datetime.now() + timedelta(hours=24)).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET expires_at = ? WHERE token = ?",
                (new_expires_at, token)
            )
            conn.commit()
        
        return UserProfile(
            id=row["id"],
            username=row["username"],
            email=row["email"] or "",
            display_name=row["display_name"] or row["username"],
            role=UserRole(row["role"]),
            created_at=row["created_at"],
            last_login=row["last_login"] or "",
            preferences=json.loads(row["preferences"] or "{}"),
            avatar=row["avatar"] or "",
            bio=row["bio"] or ""
        )
    
    def login_with_session(self, token: str) -> AuthResult:
        """
        使用会话令牌登录
        
        Args:
            token: 会话令牌
            
        Returns:
            AuthResult: 登录结果
        """
        user = self.validate_session(token)
        if user:
            self._current_user = user
            self._session_token = token
            return AuthResult(True, "会话验证成功", user)
        
        return AuthResult(False, "无效或过期的会话")
    
    def clear_user_sessions(self, user_id: str):
        """
        清除用户所有会话（强制登出所有设备）
        
        Args:
            user_id: 用户ID
        """
        with self._get_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.commit()
        
        # 如果当前用户被强制登出
        if self._current_user and self._current_user.id == user_id:
            self.logout()
    
    def cleanup_expired_sessions(self):
        """清理过期会话"""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            conn.commit()
    
    # ========== 权限检查 ==========
    
    def has_role(self, user_id: str, required_role: UserRole) -> bool:
        """
        检查用户是否具有指定角色
        
        Args:
            user_id: 用户ID
            required_role: 所需角色
            
        Returns:
            是否具有该角色
        """
        user = self.get_user(user_id)
        if not user:
            return False
        
        role_order = {UserRole.GUEST: 0, UserRole.USER: 1, UserRole.ADMIN: 2}
        return role_order[user.role] >= role_order[required_role]
    
    def is_admin(self, user_id: str) -> bool:
        """检查用户是否为管理员"""
        return self.has_role(user_id, UserRole.ADMIN)
    
    def require_admin(self, user_id: str) -> bool:
        """
        要求管理员权限
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否为管理员
        """
        return self.is_admin(user_id)
    
    def can_access(self, user_id: str, resource: str) -> bool:
        """
        检查用户是否有权限访问资源
        
        Args:
            user_id: 用户ID
            resource: 资源标识符
            
        Returns:
            是否有权限
        """
        user = self.get_user(user_id)
        if not user:
            return False
        
        # 管理员可以访问所有资源
        if user.role == UserRole.ADMIN:
            return True
        
        # 用户可以访问自己的资源
        if resource.startswith(f"user/{user_id}/"):
            return True
        
        # 公共资源
        public_resources = ["public/", "shared/"]
        for prefix in public_resources:
            if resource.startswith(prefix):
                return True
        
        return False
    
    # ========== 账户安全 ==========
    
    def _check_account_locked(self, username: str) -> Optional[str]:
        """检查账户是否被锁定"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT locked_until FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
        
        if not row or not row["locked_until"]:
            return None
        
        locked_until = datetime.fromisoformat(row["locked_until"])
        if datetime.now() < locked_until:
            remaining = (locked_until - datetime.now()).seconds // 60
            return f"账户已被锁定，请 {remaining} 分钟后重试"
        
        # 锁定时间已过，解锁账户
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE users SET locked_until = NULL, failed_attempts = 0 WHERE username = ?",
                (username,)
            )
            conn.commit()
        
        return None
    
    def _record_failed_attempt(self, username: str):
        """记录登录失败尝试"""
        max_attempts = 5
        lock_duration = 15  # 分钟
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT failed_attempts FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            
            if row:
                attempts = row["failed_attempts"] + 1
                
                if attempts >= max_attempts:
                    locked_until = (datetime.now() + timedelta(minutes=lock_duration)).isoformat()
                    conn.execute(
                        "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE username = ?",
                        (attempts, locked_until, username)
                    )
                else:
                    conn.execute(
                        "UPDATE users SET failed_attempts = ? WHERE username = ?",
                        (attempts, username)
                    )
                conn.commit()
    
    def _reset_failed_attempts(self, user_id: str):
        """重置登录失败尝试次数"""
        with self._get_connection() as conn:
            conn.execute("UPDATE users SET failed_attempts = 0 WHERE id = ?", (user_id,))
            conn.commit()
    
    # ========== 批量操作 ==========
    
    def get_users_with_role(self, role: UserRole) -> List[UserProfile]:
        """获取指定角色的所有用户"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, username, email, display_name, role, 
                          created_at, last_login, preferences, avatar, bio
                   FROM users WHERE role = ? ORDER BY created_at DESC""",
                (role.value,)
            )
            rows = cursor.fetchall()
        
        return [
            UserProfile(
                id=row["id"],
                username=row["username"],
                email=row["email"] or "",
                display_name=row["display_name"] or row["username"],
                role=UserRole(row["role"]),
                created_at=row["created_at"],
                last_login=row["last_login"] or "",
                preferences=json.loads(row["preferences"] or "{}"),
                avatar=row["avatar"] or "",
                bio=row["bio"] or ""
            )
            for row in rows
        ]
    
    def update_user_role(self, user_id: str, new_role: UserRole) -> bool:
        """更新用户角色"""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE users SET role = ? WHERE id = ?",
                    (new_role.value, user_id)
                )
                conn.commit()
            return True
        except Exception:
            return False
    
    def list_users(self) -> List[UserProfile]:
        """列出所有用户（仅管理员）"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, username, email, display_name, role, 
                          created_at, last_login, preferences, avatar, bio
                   FROM users ORDER BY created_at DESC"""
            )
            rows = cursor.fetchall()
        
        return [
            UserProfile(
                id=row["id"],
                username=row["username"],
                email=row["email"] or "",
                display_name=row["display_name"] or row["username"],
                role=UserRole(row["role"]),
                created_at=row["created_at"],
                last_login=row["last_login"] or "",
                preferences=json.loads(row["preferences"] or "{}"),
                avatar=row["avatar"] or "",
                bio=row["bio"] or ""
            )
            for row in rows
        ]
    
    def get_user_count(self) -> int:
        """获取用户数量"""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]


# 单例
_auth_system: Optional[AuthSystem] = None


def get_auth_system() -> AuthSystem:
    """获取认证系统单例"""
    global _auth_system
    if _auth_system is None:
        _auth_system = AuthSystem()
    return _auth_system
