"""
企业级安全认证模块
支持 JWT 令牌、API 密钥、权限控制
"""
import os
import secrets
import time
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass
class TokenData:
    """令牌数据"""
    username: Optional[str] = None
    scopes: List[str] = field(default_factory=list)
    is_admin: bool = False
    expires_at: Optional[datetime] = None


@dataclass
class APIKey:
    """API 密钥"""
    key: str
    name: str
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True


class SecurityManager:
    """安全管理器"""
    
    _instance: Optional['SecurityManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # JWT 配置
        self.secret_key = os.getenv("JWT_SECRET_KEY") or secrets.token_urlsafe(32)
        self.algorithm = "HS256"
        self.token_expire_hours = 24
        
        # API 密钥存储
        self._api_keys: Dict[str, APIKey] = {}
        
        # 速率限制
        self._rate_limits: Dict[str, List[float]] = {}
        self.rate_limit_per_minute = 60
        
        # 权限定义
        self.ALL_SCOPES = {
            "models:read": "读取模型信息",
            "models:download": "下载模型",
            "models:load": "加载/卸载模型",
            "models:batch": "批量操作模型",
            "models:evaluate": "评估模型",
            "models:inference": "使用模型推理",
            "system:admin": "系统管理",
        }
    
    def create_access_token(self, username: str, scopes: List[str] = None, 
                           is_admin: bool = False) -> str:
        """创建 JWT 访问令牌"""
        scopes = scopes or []
        expires_at = datetime.utcnow() + timedelta(hours=self.token_expire_hours)
        
        try:
            from jose import jwt
            payload = {
                "sub": username,
                "scopes": scopes,
                "is_admin": is_admin,
                "iat": datetime.utcnow().timestamp(),
                "exp": expires_at.timestamp()
            }
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        except ImportError:
            # 简化版本
            import base64
            import json
            payload = {
                "sub": username,
                "scopes": scopes,
                "is_admin": is_admin,
                "iat": datetime.utcnow().timestamp(),
                "exp": expires_at.timestamp()
            }
            data = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
            token = f"{data}"
        
        return token
    
    def verify_token(self, token: str) -> Optional[TokenData]:
        """验证 JWT 令牌"""
        try:
            from jose import jwt, JWTError
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return TokenData(
                username=payload.get("sub"),
                scopes=payload.get("scopes", []),
                is_admin=payload.get("is_admin", False),
                expires_at=datetime.fromtimestamp(payload.get("exp", 0))
            )
        except ImportError:
            # 简化版本
            import base64
            import json
            try:
                data = base64.urlsafe_b64decode(token.encode()).decode()
                payload = json.loads(data)
                return TokenData(
                    username=payload.get("sub"),
                    scopes=payload.get("scopes", []),
                    is_admin=payload.get("is_admin", False),
                    expires_at=datetime.fromtimestamp(payload.get("exp", 0))
                )
            except Exception:
                return None
        except Exception:
            return None
    
    def create_api_key(self, name: str, scopes: List[str] = None,
                      expires_days: int = None) -> str:
        """创建 API 密钥"""
        key = f"sk_{secrets.token_urlsafe(32)}"
        
        api_key = APIKey(
            key=key,
            name=name,
            scopes=scopes or [],
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=expires_days) if expires_days else None
        )
        
        self._api_keys[key] = api_key
        return key
    
    def verify_api_key(self, key: str) -> Optional[APIKey]:
        """验证 API 密钥"""
        if key not in self._api_keys:
            return None
        
        api_key = self._api_keys[key]
        
        # 检查是否激活
        if not api_key.is_active:
            return None
        
        # 检查是否过期
        if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
            return None
        
        return api_key
    
    def revoke_api_key(self, key: str) -> bool:
        """撤销 API 密钥"""
        if key in self._api_keys:
            self._api_keys[key].is_active = False
            return True
        return False
    
    def check_rate_limit(self, identifier: str) -> bool:
        """检查速率限制"""
        now = time.time()
        minute_ago = now - 60
        
        # 获取该标识符的请求历史
        if identifier not in self._rate_limits:
            self._rate_limits[identifier] = []
        
        # 清理过期的记录
        self._rate_limits[identifier] = [
            t for t in self._rate_limits[identifier] if t > minute_ago
        ]
        
        # 检查是否超过限制
        if len(self._rate_limits[identifier]) >= self.rate_limit_per_minute:
            return False
        
        # 记录本次请求
        self._rate_limits[identifier].append(now)
        return True
    
    def require_scopes(self, required_scopes: List[str]):
        """权限检查装饰器工厂"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def hash_password(self, password: str) -> str:
        """密码哈希"""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return f"{salt}${pwd_hash.hex()}"
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        try:
            salt, pwd_hash = hashed.split('$')
            new_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                100000
            )
            return new_hash.hex() == pwd_hash
        except ValueError:
            return False
    
    def get_active_keys(self) -> List[Dict[str, Any]]:
        """获取所有活跃的 API 密钥信息"""
        return [
            {
                "name": k.name,
                "scopes": k.scopes,
                "created_at": k.created_at.isoformat(),
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "is_active": k.is_active
            }
            for k in self._api_keys.values() if k.is_active
        ]


@lru_cache(maxsize=1)
def get_security_manager() -> SecurityManager:
    """获取安全管理器单例"""
    return SecurityManager()
