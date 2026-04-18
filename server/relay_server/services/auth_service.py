"""
Authentication Service - 认证服务
================================

提供 JWT 认证、API Key 验证、密码哈希等功能
"""

import os
import re
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from functools import wraps

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

try:
    from passlib.context import CryptContext
    PASSLIB_AVAILABLE = True
except ImportError:
    PASSLIB_AVAILABLE = False


# ============ 密码哈希 ============

if PASSLIB_AVAILABLE:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
else:
    # 简单的 SHA256 哈希（仅用于开发环境）
    def simple_hash(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    pwd_context = type('obj', (object,), {'verify': lambda s, h: simple_hash(s) == h, 'hash': lambda p: simple_hash(p)})()


# ============ JWT 配置 ============

JWT_SECRET = os.environ.get("HERMES_JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 小时
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30


class AuthService:
    """认证服务"""
    
    def __init__(self):
        self.jwt_available = JWT_AVAILABLE
        self.passlib_available = PASSLIB_AVAILABLE
    
    # ============ 密码操作 ============
    
    def hash_password(self, password: str) -> str:
        """哈希密码"""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(plain_password, hashed_password)
    
    # ============ JWT Token ============
    
    def create_access_token(
        self, 
        user_id: str, 
        username: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """创建访问令牌"""
        if not self.jwt_available:
            raise RuntimeError("PyJWT is not installed")
        
        if expires_delta is None:
            expires_delta = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        
        expire = datetime.utcnow() + expires_delta
        
        payload = {
            "sub": user_id,
            "username": username,
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4()),
        }
        
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    def create_refresh_token(
        self, 
        user_id: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """创建刷新令牌"""
        if not self.jwt_available:
            raise RuntimeError("PyJWT is not installed")
        
        if expires_delta is None:
            expires_delta = timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        
        expire = datetime.utcnow() + expires_delta
        
        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4()),
        }
        
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证令牌"""
        if not self.jwt_available:
            raise RuntimeError("PyJWT is not installed")
        
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None  # Token 过期
        except jwt.InvalidTokenError:
            return None  # 无效 Token
    
    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """解码令牌（不验证）"""
        if not self.jwt_available:
            raise RuntimeError("PyJWT is not installed")
        
        try:
            return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_signature": False})
        except Exception:
            return None
    
    # ============ API Key ============
    
    def generate_api_key(self, prefix: str = "hbd") -> Tuple[str, str]:
        """
        生成 API Key
        
        Returns:
            (raw_key, hashed_key)
        """
        key_id = secrets.token_hex(16)
        random_part = secrets.token_hex(24)
        raw_key = f"{prefix}_{key_id}_{random_part}"
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
        
        return raw_key, hashed_key
    
    def verify_api_key(self, raw_key: str, hashed_key: str) -> bool:
        """验证 API Key"""
        return hashlib.sha256(raw_key.encode()).hexdigest() == hashed_key
    
    def hash_api_key(self, raw_key: str) -> str:
        """哈希 API Key"""
        return hashlib.sha256(raw_key.encode()).hexdigest()
    
    # ============ 用户 ID 生成 ============
    
    def generate_user_id(self) -> str:
        """生成唯一用户 ID"""
        return f"usr_{uuid.uuid4().hex[:16]}"
    
    def generate_session_id(self) -> str:
        """生成唯一会话 ID"""
        return f"sess_{uuid.uuid4().hex[:16]}"
    
    def generate_message_id(self) -> str:
        """生成唯一消息 ID"""
        return f"msg_{uuid.uuid4().hex[:16]}"
    
    # ============ 验证工具 ============
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """验证邮箱格式"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """验证用户名格式（3-32位字母数字下划线）"""
        pattern = r'^[a-zA-Z0-9_]{3,32}$'
        return bool(re.match(pattern, username))
    
    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        """
        验证密码强度
        
        Returns:
            (is_valid, error_message)
        """
        if len(password) < 8:
            return False, "密码长度至少 8 位"
        if len(password) > 128:
            return False, "密码长度不能超过 128 位"
        if not re.search(r'[A-Za-z]', password):
            return False, "密码必须包含字母"
        if not re.search(r'[0-9]', password):
            return False, "密码必须包含数字"
        return True, ""


# 全局实例
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """获取认证服务单例"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


# ============ 装饰器 ============

def require_auth(func):
    """要求认证的装饰器"""
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        # 从请求头获取 Token
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header[7:]  # 去掉 "Bearer "
        
        auth_service = get_auth_service()
        payload = auth_service.verify_token(token)
        
        if payload is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # 将用户信息添加到请求中
        request.state.user_id = payload.get("sub")
        request.state.username = payload.get("username")
        
        return await func(request, *args, **kwargs)
    
    return wrapper


def require_scope(*scopes):
    """要求特定权限的装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            # TODO: 实现权限检查
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
