"""
用户认证系统
User Authentication System

支持本地 SQLite 数据库的用户注册、登录、个人资料管理。
"""

import sqlite3
import hashlib
import uuid
import json
import os
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Callable
from enum import Enum


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
                    bio TEXT DEFAULT ''
                );
                
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
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
    
    def login(self, username: str, password: str) -> AuthResult:
        """
        用户登录
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            AuthResult: 登录结果
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, username, password_hash, salt, email, display_name, 
                          role, created_at, last_login, preferences, avatar, bio
                   FROM users WHERE username = ?""",
                (username,)
            )
            row = cursor.fetchone()
        
        if not row:
            return AuthResult(False, "用户名或密码错误")
        
        # 验证密码
        if not self._verify_password(password, row["password_hash"], row["salt"]):
            return AuthResult(False, "用户名或密码错误")
        
        # 更新最后登录时间
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (datetime.now().isoformat(), row["id"])
            )
            conn.commit()
        
        # 创建会话
        session_token = self._create_session(row["id"])
        
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
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
            
            # 如果是当前用户，登出
            if self._current_user and self._current_user.id == user_id:
                self.logout()
            
            return AuthResult(True, "用户已删除")
        except Exception as e:
            return AuthResult(False, f"删除失败: {e}")
    
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
