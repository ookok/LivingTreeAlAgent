"""
身份管理系统
Decentralized Identity Management
"""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class UserIdentity:
    """用户身份信息"""
    user_id: str
    username: str
    email: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_login: datetime = field(default_factory=datetime.now)
    
    # 设备管理
    devices: List[str] = field(default_factory=list)
    current_device_id: Optional[str] = None
    
    # 安全设置
    login_count: int = 0
    failed_login_count: int = 0
    is_locked: bool = False
    locked_until: Optional[datetime] = None
    
    # 加密密钥
    encryption_key_hash: Optional[str] = None
    session_token: Optional[str] = None
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceInfo:
    """设备信息"""
    device_id: str
    device_name: str
    device_type: str  # desktop, mobile, tablet
    last_active: datetime
    is_trusted: bool = False
    login_time: datetime = field(default_factory=datetime.now)


class IdentityManager:
    """
    去中心化身份管理系统
    
    功能：
    - 本地身份验证
    - 离线登录支持
    - 多设备管理
    - 身份凭证备份
    """
    
    # 最大登录失败次数
    MAX_FAILED_ATTEMPTS = 5
    # 锁定时间（分钟）
    LOCKOUT_DURATION = 30
    # 会话过期时间（小时）
    SESSION_EXPIRY_HOURS = 24
    
    def __init__(self, config: Optional[Any] = None):
        self.config = config
        self._storage_path = Path.home() / ".hermes-desktop" / "identity"
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存
        self._identities: Dict[str, UserIdentity] = {}
        self._sessions: Dict[str, str] = {}  # session_token -> user_id
        
        # 锁
        self._lock = asyncio.Lock()
        
        # 加载已有身份
        self._load_identities()
        
        logger.info(f"身份管理器初始化完成，已加载 {len(self._identities)} 个身份")
    
    def _get_user_path(self, user_id: str) -> Path:
        """获取用户数据路径"""
        return self._storage_path / f"{user_id}.json"
    
    def _get_password_hash(self, password: str, salt: Optional[str] = None) -> tuple:
        """生成密码哈希和盐"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        # PBKDF2-SHA256
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # 迭代次数
        )
        
        return key.hex(), salt
    
    def _verify_password(self, password: str, stored_hash: str, 
                         salt: str) -> bool:
        """验证密码"""
        computed_hash, _ = self._get_password_hash(password, salt)
        return hmac.compare_digest(computed_hash, stored_hash)
    
    def _load_identities(self) -> None:
        """加载所有身份"""
        for file_path in self._storage_path.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                identity = UserIdentity(
                    user_id=data['user_id'],
                    username=data['username'],
                    email=data.get('email'),
                    created_at=datetime.fromisoformat(data['created_at']),
                    last_login=datetime.fromisoformat(data['last_login']),
                    devices=data.get('devices', []),
                    current_device_id=data.get('current_device_id'),
                    login_count=data.get('login_count', 0),
                    failed_login_count=data.get('failed_login_count', 0),
                    is_locked=data.get('is_locked', False),
                    metadata=data.get('metadata', {})
                )
                
                # 解析locked_until
                if data.get('locked_until'):
                    identity.locked_until = datetime.fromisoformat(data['locked_until'])
                
                self._identities[identity.user_id] = identity
                
            except Exception as e:
                logger.error(f"加载身份失败 {file_path}: {e}")
    
    def _save_identity(self, identity: UserIdentity) -> None:
        """保存身份到磁盘"""
        file_path = self._get_user_path(identity.user_id)
        
        data = {
            'user_id': identity.user_id,
            'username': identity.username,
            'email': identity.email,
            'created_at': identity.created_at.isoformat(),
            'last_login': identity.last_login.isoformat(),
            'devices': identity.devices,
            'current_device_id': identity.current_device_id,
            'login_count': identity.login_count,
            'failed_login_count': identity.failed_login_count,
            'is_locked': identity.is_locked,
            'locked_until': identity.locked_until.isoformat() if identity.locked_until else None,
            'metadata': identity.metadata
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    async def register(self, username: str, password: str,
                      email: Optional[str] = None) -> Optional[UserIdentity]:
        """
        注册新用户
        
        Args:
            username: 用户名
            password: 密码
            email: 邮箱（可选）
        
        Returns:
            UserIdentity: 新建的用户身份，或None（如果失败）
        """
        async with self._lock:
            # 检查用户名是否已存在
            for identity in self._identities.values():
                if identity.username == username:
                    logger.warning(f"用户名已存在: {username}")
                    return None
            
            # 生成用户ID
            user_id = secrets.token_urlsafe(16)
            
            # 生成密码哈希
            password_hash, salt = self._get_password_hash(password)
            
            # 创建身份
            identity = UserIdentity(
                user_id=user_id,
                username=username,
                email=email,
                encryption_key_hash=password_hash  # 存储用于离线验证
            )
            
            # 保存
            self._identities[user_id] = identity
            self._save_identity(identity)
            
            logger.info(f"用户注册成功: {username} ({user_id})")
            return identity
    
    async def login(self, username: str, password: str,
                   device_id: Optional[str] = None) -> Optional[UserIdentity]:
        """
        用户登录
        
        Args:
            username: 用户名
            password: 密码
            device_id: 设备ID（可选）
        
        Returns:
            UserIdentity: 登录的用户身份，或None（如果失败）
        """
        async with self._lock:
            # 查找用户
            identity = None
            for id in self._identities.values():
                if id.username == username:
                    identity = id
                    break
            
            if not identity:
                logger.warning(f"用户不存在: {username}")
                return None
            
            # 检查账户锁定
            if identity.is_locked and identity.locked_until:
                if datetime.now() < identity.locked_until:
                    remaining = (identity.locked_until - datetime.now()).seconds // 60
                    logger.warning(f"账户已锁定，剩余 {remaining} 分钟")
                    return None
                else:
                    # 解除锁定
                    identity.is_locked = False
                    identity.locked_until = None
                    identity.failed_login_count = 0
            
            # 验证密码
            if not identity.encryption_key_hash:
                logger.error(f"用户 {username} 缺少密码哈希")
                return None
            
            # 尝试验证（使用存储的盐）
            salt = self._get_salt_from_hash(identity.encryption_key_hash)
            if not self._verify_password(password, identity.encryption_key_hash, salt or ""):
                # 登录失败
                identity.failed_login_count += 1
                
                if identity.failed_login_count >= self.MAX_FAILED_ATTEMPTS:
                    identity.is_locked = True
                    identity.locked_until = datetime.now() + timedelta(minutes=self.LOCKOUT_DURATION)
                    logger.warning(f"账户已锁定: {username}")
                
                self._save_identity(identity)
                return None
            
            # 登录成功
            identity.login_count += 1
            identity.last_login = datetime.now()
            identity.failed_login_count = 0
            
            # 生成会话令牌
            session_token = secrets.token_urlsafe(32)
            identity.session_token = session_token
            self._sessions[session_token] = identity.user_id
            
            # 管理设备
            if device_id and device_id not in identity.devices:
                identity.devices.append(device_id)
            
            identity.current_device_id = device_id
            
            # 保存
            self._save_identity(identity)
            
            logger.info(f"用户登录成功: {username}")
            return identity
    
    def _get_salt_from_hash(self, hash_str: str) -> Optional[str]:
        """从哈希中提取盐（简化版，实际应分开存储）"""
        # 这里简化处理，实际应该分开存储salt
        # 暂时返回None，使用固定盐
        return None
    
    async def logout(self, user_id: str) -> bool:
        """
        用户登出
        
        Args:
            user_id: 用户ID
        
        Returns:
            bool: 是否成功
        """
        async with self._lock:
            identity = self._identities.get(user_id)
            if not identity:
                return False
            
            # 清除会话
            if identity.session_token:
                self._sessions.pop(identity.session_token, None)
                identity.session_token = None
            
            self._save_identity(identity)
            logger.info(f"用户登出: {identity.username}")
            return True
    
    def validate_session(self, session_token: str) -> Optional[UserIdentity]:
        """
        验证会话令牌
        
        Args:
            session_token: 会话令牌
        
        Returns:
            UserIdentity: 如果有效返回用户身份
        """
        user_id = self._sessions.get(session_token)
        if not user_id:
            return None
        
        identity = self._identities.get(user_id)
        if not identity:
            return None
        
        # 检查会话是否过期
        if identity.last_login + timedelta(hours=self.SESSION_EXPIRY_HOURS) < datetime.now():
            self._sessions.pop(session_token, None)
            return None
        
        return identity
    
    def load_identity(self, user_id: str) -> Optional[UserIdentity]:
        """
        加载身份（用于自动登录）
        
        Args:
            user_id: 用户ID
        
        Returns:
            UserIdentity: 用户身份
        """
        return self._identities.get(user_id)
    
    def get_identity_by_username(self, username: str) -> Optional[UserIdentity]:
        """根据用户名获取身份"""
        for identity in self._identities.values():
            if identity.username == username:
                return identity
        return None
    
    async def change_password(self, user_id: str, old_password: str,
                              new_password: str) -> bool:
        """
        修改密码
        
        Args:
            user_id: 用户ID
            old_password: 旧密码
            new_password: 新密码
        
        Returns:
            bool: 是否成功
        """
        async with self._lock:
            identity = self._identities.get(user_id)
            if not identity:
                return False
            
            # 验证旧密码
            salt = self._get_salt_from_hash(identity.encryption_key_hash or "")
            if not self._verify_password(old_password, 
                                         identity.encryption_key_hash or "", 
                                         salt or ""):
                return False
            
            # 生成新密码哈希
            new_hash, new_salt = self._get_password_hash(new_password)
            identity.encryption_key_hash = new_hash
            
            # 清除所有会话
            if identity.session_token:
                self._sessions.pop(identity.session_token, None)
                identity.session_token = None
            
            self._save_identity(identity)
            logger.info(f"密码修改成功: {identity.username}")
            return True
    
    def get_all_identities(self) -> List[UserIdentity]:
        """获取所有本地身份"""
        return list(self._identities.values())
    
    async def delete_identity(self, user_id: str, password: str) -> bool:
        """
        删除身份
        
        Args:
            user_id: 用户ID
            password: 密码确认
        
        Returns:
            bool: 是否成功
        """
        async with self._lock:
            identity = self._identities.get(user_id)
            if not identity:
                return False
            
            # 验证密码
            salt = self._get_salt_from_hash(identity.encryption_key_hash or "")
            if not self._verify_password(password,
                                         identity.encryption_key_hash or "",
                                         salt or ""):
                return False
            
            # 删除文件
            file_path = self._get_user_path(user_id)
            if file_path.exists():
                file_path.unlink()
            
            # 从内存移除
            self._identities.pop(user_id, None)
            
            logger.info(f"身份已删除: {identity.username}")
            return True
