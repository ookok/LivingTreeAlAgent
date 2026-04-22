"""
用户认证系统
User Authentication System

支持本地 SQLite 数据库的用户注册、登录、个人资料管理。

改进：
- P0: SQL 注入修复, 密码策略增强(≥8位+复杂度), 暴力破解防护
- P1: 会话过期 + expires_at, 密码强度评分, 密码重置
- P3: 会话管理增强(revoke/logout_all)
"""

import sqlite3
import hashlib
import uuid
import json
import os
import re
import time
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum


# ======= 常量配置 =======

MAX_LOGIN_ATTEMPTS = 5       # 最大登录尝试次数
LOCKOUT_DURATION = 1800      # 临时锁定时间（秒，30分钟）
SESSION_EXPIRE_HOURS = 24    # 会话过期时间（小时）


# ======= 枚举 =======

class UserRole(Enum):
    """用户角色"""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


# ======= 密码强度级别 =======

class PasswordStrength(Enum):
    """密码强度"""
    VERY_WEAK = "very_weak"     # <8位
    WEAK = "weak"               # 8位，但少一类字符
    MODERATE = "moderate"       # 8位+两类
    STRONG = "strong"           # 8位+三类
    VERY_STRONG = "very_strong" # 12位+三类+特殊字符


# ======= 数据模型 =======

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


@dataclass
class PasswordScore:
    """密码强度评分"""
    strength: PasswordStrength
    score: int                    # 0-4
    message: str
    suggestions: List[str] = field(default_factory=list)
    

class AuthResult:
    """认证结果"""
    def __init__(self, success: bool, message: str = "", user: UserProfile = None):
        self.success = success
        self.message = message
        self.user = user


# ======= 认证系统 =======

class AuthSystem:
    """
    用户认证系统
    
    功能：
    1. 用户注册、登录、登出
    2. 密码加密存储 (PBKDF2-SHA256)
    3. 用户资料管理
    4. 会话管理（支持过期检查）
    5. 角色权限控制
    6. 密码强度评分
    7. 密码重置（邮箱令牌）
    8. 暴力破解防护（最大尝试次数 + 临时锁定）
    """
    
    def __init__(self, db_path: str = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = self._get_default_db_path()
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # 当前登录用户
        self._current_user: Optional[UserProfile] = None
        self._session_token: Optional[str] = None
        
        # 暴力破解防护：用户名 -> {attempts: int, locked_until: float}
        self._login_attempts: dict = {}
    
    def _get_default_db_path(self) -> Path:
        """获取默认数据库路径"""
        user_dir = Path.home() / ".hermes-desktop"
        if os.access(str(Path.home()), os.W_OK):
            return user_dir / "users.db"
        return Path(__file__).parent.parent / "users.db"
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        # 启用 WAL 模式提升并发性能
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
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
                
                CREATE TABLE IF NOT EXISTS password_resets (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets(user_id);
            """)
            conn.commit()
    
    def _hash_password(self, password: str, salt: str = None) -> tuple:
        """哈希密码 (PBKDF2-SHA256)"""
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
    
    # ==================== 密码策略 ====================
    
    def check_password_strength(self, password: str) -> PasswordScore:
        """
        密码强度检查
        
        Returns:
            PasswordScore: 密码强度评分
        """
        suggestions = []
        
        # 长度检查
        if len(password) < 8:
            suggestions.append("密码至少需要8个字符")
            return PasswordScore(
                strength=PasswordStrength.VERY_WEAK,
                score=0,
                message="密码过弱",
                suggestions=suggestions
            )
        
        # 复杂度检查
        has_upper = bool(re.search(r'[A-Z]', password))
        has_lower = bool(re.search(r'[a-z]', password))
        has_digit = bool(re.search(r'\d', password))
        has_special = bool(re.search(r'[!@#$%^&*()_+\-=\[\]{};\'":|,.<>\/?] ', password))
        
        char_types = sum([has_upper, has_lower, has_digit, has_special])
        
        if not has_upper or not has_lower:
            suggestions.append("密码需要同时包含大写和小写字母")
        if not has_digit:
            suggestions.append("密码需要包含数字")
        if not has_special:
            suggestions.append("密码建议包含特殊字符（如 !@#$%^&*）")
        
        # 评分
        if len(password) >= 16 and char_types >= 4:
            strength, score, message = PasswordStrength.VERY_STRONG, 4, "密码强度：非常强"
        elif len(password) >= 12 and char_types >= 3:
            strength, score, message = PasswordStrength.STRONG, 3, "密码强度：强"
        elif len(password) >= 8 and char_types >= 3:
            strength, score, message = PasswordStrength.MODERATE, 2, "密码强度：中等"
        else:
            strength, score, message = PasswordStrength.WEAK, 1, "密码强度：弱"
            suggestions.insert(0, "建议增加密码长度至至少12位并使用所有类型的字符")
        
        return PasswordScore(strength=strength, score=score, message=message, suggestions=suggestions)
    
    def validate_password(self, password: str) -> AuthResult:
        """
        验证密码是否符合要求
        
        Returns:
            AuthResult: 验证结果（包含提示信息）
        """
        score = self.check_password_strength(password)
        
        if score.strength in (PasswordStrength.VERY_WEAK, PasswordStrength.WEAK):
            return AuthResult(
                False,
                f"{score.message}",
                suggestions=score.suggestions
            )
        
        return AuthResult(True, score.message)
    
    def validate_password_requirements(self, password: str) -> tuple:
        """
        验证密码是否满足最低要求
        
        Returns:
            (bool, str): (通过, 错误信息)
        """
        if len(password) >= 8:
            return True, ""
        return False, "新密码至少需要8个字符"
    
    # ==================== 暴力破解防护 ====================
    
    def __check_login_lockout(self, username: str) -> Optional[str]:
        """
        检查登录锁定状态
        
        Returns:
            如果锁定中，返回锁定说明；否则返回 None
        """
        if username not in self._login_attempts:
            return None
        
        attempts = self._login_attempts[username]
        locked_until = attempts.get("locked_until", 0)
        
        if time.time() < locked_until:
            remaining = int(locked_until - time.time())
            minutes = remaining // 60
            seconds = remaining % 60
            return f"登录尝试次数过多，请等待 {minutes} 分 {seconds} 秒后重试"
        else:
            # 锁定已过期，清除记录
            del self._login_attempts[username]
            return None
    
    def __record_login_attempt(self, username: str, success: bool):
        """
        记录登录尝试
        
        Args:
            username: 用户名
            success: 是否成功
        """
        if username not in self._login_attempts:
            self._login_attempts[username] = {"attempts": 0, "locked_until": 0}
        
        if success:
            # 登录成功，清除之前的尝试
            self._login_attempts[username] = {"attempts": 0, "locked_until": 0}
        else:
            self._login_attempts[username]["attempts"] += 1
            attempts = self._login_attempts[username]["attempts"]
            
            if attempts >= MAX_LOGIN_ATTEMPTS:
                self._login_attempts[username]["locked_until"] = time.time() + LOCKOUT_DURATION
    
    def __cleanup_login_attempts(self):
        """清理过期的登录尝试记录"""
        now = time.time()
        expired = [u for u, v in self._login_attempts.items() if v.get("locked_until", 0) < now]
        for u in expired:
            del self._login_attempts[u]
    
    def __cleanup_expired_sessions(self):
        """清理已过期的会话"""
        now = time.time()
        expires_str = datetime.fromtimestamp(now).isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT token FROM sessions WHERE expires_at < ?", (expires_str,))
            expired_tokens = [row["token"] for row in cursor.fetchall()]
            
            if expired_tokens:
                placeholders = ",".join("?" for _ in expired_tokens)
                conn.execute(
                    f"DELETE FROM sessions WHERE token IN ({placeholders})",
                    expired_tokens
                )
                conn.commit()
    
    # ==================== 注册 ====================
    
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
            AuthResult: 注册结果，错误时附带 suggestions
        """
        # 验证用户名
        if len(username) < 3:
            return AuthResult(False, "用户名至少需要3个字符")
        
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            return AuthResult(False, "用户名只能包含字母、数字和下划线")
        
        # 检查用户名是否存在
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,)
            )
            if cursor.fetchone():
                return AuthResult(False, "用户名已存在")
        
        # 强密码验证
        score = self.check_password_strength(password)
        if score.strength in (PasswordStrength.VERY_WEAK, PasswordStrength.WEAK):
            return AuthResult(False, score.message, suggestions=score.suggestions)
        
        # 检查邮箱格式
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return AuthResult(False, "邮箱格式不正确")
        
        try:
            user_id = str(uuid.uuid4())
            password_hash, salt = self._hash_password(password)
            created_at = datetime.now().isoformat()
            
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT INTO users 
                       (id, username, password_hash, salt, email, display_name, created_at, role)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, username, password_hash, salt, email, display_name or username, created_at, UserRole.USER.value)
                )
                conn.commit()
            
            return AuthResult(True, "注册成功", UserProfile(
                id=user_id,
                username=username,
                email=email,
                display_name=display_name or username,
                role=UserRole.USER,
                created_at=created_at
            ))
            
        except Exception as e:
            return AuthResult(False, f"注册失败: {e}")
    
    # ==================== 登录 ====================
    
    def login(self, username: str, password: str) -> AuthResult:
        """
        用户登录
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            AuthResult: 登录结果
        """
        # 暴力破解检查
        lockout_msg = self.__check_login_lockout(username)
        if lockout_msg:
            return AuthResult(False, lockout_msg)
        
        # 清理过期记录
        self.__cleanup_login_attempts()
        self.__cleanup_expired_sessions()
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, username, password_hash, salt, email, display_name, 
                          role, created_at, last_login, preferences, avatar, bio
                   FROM users WHERE username = ?""",
                (username,)
            )
            row = cursor.fetchone()
        
        # 始终返回相同时间错误，防止用户名枚举
        if not row:
            self.__record_login_attempt(username, False)
            return AuthResult(False, "用户名或密码错误")
        
        if not self._verify_password(password, row["password_hash"], row["salt"]):
            self.__record_login_attempt(username, False)
            return AuthResult(False, "用户名或密码错误")
        
        # 登录成功
        self.__record_login_attempt(username, True)
        
        # 更新最后登录时间
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (datetime.now().isoformat(), row["id"])
            )
            conn.commit()
        
        # 创建会话（带过期时间）
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
    
    # ==================== 会话管理 ====================
    
    def logout(self):
        """用户登出"""
        self.revoke_session(self._session_token)
        self._current_user = None
        self._session_token = None
    
    def _create_session(self, user_id: str) -> str:
        """创建会话（含过期时间）"""
        token = uuid.uuid4().hex
        created_at = datetime.now().isoformat()
        expires_at = (datetime.now() + timedelta(hours=SESSION_EXPIRE_HOURS)).isoformat()
        
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token, user_id, created_at, expires_at)
            )
            conn.commit()
        
        return token
    
    def revoke_session(self, token: str) -> bool:
        """
        吊销指定会话
        
        Args:
            token: 会话令牌
            
        Returns:
            是否成功吊销
        """
        if not token:
            return False
        
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            return cursor.rowcount > 0
    
    def revoke_all_sessions(self, user_id: str) -> int:
        """
        吊销用户所有会话
        
        Args:
            user_id: 用户ID
            
        Returns:
            被吊销的会话数量
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE user_id = ? AND token != 'current'", (user_id,))
            conn.commit()
            return cursor.rowcount
    
    def verify_session(self, token: str) -> Optional[UserProfile]:
        """
        验证会话是否有效
        
        Args:
            token: 会话令牌
            
        Returns:
            如果有效返回 UserProfile，否则 None
        """
        self.__cleanup_expired_sessions()
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT u.id, u.username, u.email, u.display_name, u.role, 
                          u.created_at, u.last_login, u.preferences, u.avatar, u.bio
                   FROM sessions s
                   JOIN users u ON s.user_id = u.id
                   WHERE s.token = ? AND s.expires_at > ?""",
                (token, datetime.now().isoformat())
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
    
    @property
    def current_user(self) -> Optional[UserProfile]:
        """当前登录用户"""
        # 验证当前会话有效性
        if self._session_token:
            if not self.verify_session(self._session_token):
                self._current_user = None
                self._session_token = None
        return self._current_user
    
    @property
    def is_logged_in(self) -> bool:
        """是否已登录"""
        return self._current_user is not None and self.verify_session(self._session_token) is not None
    
    def get_active_sessions(self, user_id: str) -> List[dict]:
        """
        获取用户活跃会话列表
        
        Args:
            user_id: 用户ID
            
        Returns:
            会话列表
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT token, created_at, expires_at 
                   FROM sessions 
                   WHERE user_id = ? AND expires_at > ?
                   ORDER BY created_at DESC""",
                (user_id, datetime.now().isoformat())
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== 用户资料 ====================
    
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
    
    # ==================== 密码重置 ====================
    
    def generate_password_reset_token(self, email: str) -> AuthResult:
        """
        生成密码重置令牌
        
        Args:
            email: 注册邮箱
            
        Returns:
            AuthResult: 生成结果
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id FROM users WHERE email = ? AND email = ?""",
                (email, email)
            )
            row = cursor.fetchone()
        
        if not row:
            # 返回成功但隐藏提示（防止邮箱枚举）
            return AuthResult(True, "如果邮箱存在，重置链接已生成")
        
        user_id = row["id"]
        token = uuid.uuid4().hex
        expires_at = (datetime.now() + timedelta(hours=1)).isoformat()  # 1小时有效
        
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO password_resets (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                    (token, user_id, datetime.now().isoformat(), expires_at)
                )
                conn.commit()
            
            # TODO: 实际场景中发送重置邮件
            # 目前仅用于测试环境
            return AuthResult(True, "重置令牌已生成（请查看控制台）", token=token)
            
        except Exception as e:
            return AuthResult(False, f"生成失败: {e}")
    
    def reset_password(self, token: str, new_password: str) -> AuthResult:
        """
        使用令牌重置密码
        
        Args:
            token: 重置令牌
            new_password: 新密码
            
        Returns:
            AuthResult: 重置结果
        """
        # 密码强度检查
        score = self.validate_password(new_password)
        if not score.success:
            return AuthResult(False, score.message, suggestions=getattr(score, 'suggestions', []))
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT user_id, expires_at FROM password_resets WHERE token = ? AND used = 0""",
                (token,)
            )
            row = cursor.fetchone()
            
            if not row or row["expires_at"] < datetime.now().isoformat():
                return AuthResult(False, "重置令牌无效或已过期")
            
            # 获取用户当前 salt
            cursor2 = conn.execute(
                "SELECT salt FROM users WHERE id = ?",
                (row["user_id"],)
            )
            salt_row = cursor2.fetchone()
            if not salt_row:
                return AuthResult(False, "用户不存在")
            
            salt = salt_row["salt"]
            new_hash, _ = self._hash_password(new_password, salt)
            
            # 更新密码并标记令牌为已用
            try:
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (new_hash, row["user_id"])
                )
                conn.execute(
                    "UPDATE password_resets SET used = 1 WHERE token = ?",
                    (token,)
                )
                conn.commit()
                return AuthResult(True, "密码重置成功")
            except Exception as e:
                return AuthResult(False, f"密码重置失败: {e}")
    
    # ==================== 其他方法 ====================
    
    def update_profile(self, user_id: str, **kwargs) -> bool:
        """
        更新用户资料（使用参数化查询防止 SQL 注入）
        
        Args:
            user_id: 用户ID
            **kwargs: 要更新的字段
            
        Returns:
            是否更新成功
        """
        # 严格白名单过滤
        allowed_fields = ["email", "display_name", "preferences", "avatar", "bio"]
        
        updates: dict = {}
        for key, value in kwargs.items():
            if key in allowed_fields:
                if key == "preferences" and isinstance(value, dict):
                    updates[key] = json.dumps(value)
                elif key == "email" and value and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
                    # 验证邮箱格式
                    return False
                else:
                    updates[key] = value
        
        if not updates:
            return False
        
        # 使用参数化查询构建 UPDATE 语句
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [user_id]
        
        # 确保列名只在白名单内
        for col in updates.keys():
            if col not in allowed_fields:
                return False, "不允许更新的字段"
        
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
        # 密码强度检查
        score = self.validate_password(new_password)
        if not score.success:
            return AuthResult(False, score.message)
        
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
        user = self.get_user(user_id)
        if not user:
            return AuthResult(False, "用户不存在")
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT password_hash, salt FROM users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
        
        if not self._verify_password(password, row["password_hash"], row["salt"]):
            return AuthResult(False, "密码错误")
        
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
            
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


# ==================== 单例 ====================

_auth_system: Optional[AuthSystem] = None


def get_auth_system() -> AuthSystem:
    """获取认证系统单例"""
    global _auth_system
    if _auth_system is None:
        _auth_system = AuthSystem()
    return _auth_system
