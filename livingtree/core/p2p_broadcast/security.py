"""
安全加密模块

实现端到端加密、身份验证、安全通信等功能
from __future__ import annotations
"""


import hashlib
import hmac
import json
import logging
import os
import secrets
import struct
import time
from typing import Dict, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class CryptoManager:
    """加密管理器"""
    
    def __init__(self):
        self._keys: Dict[str, bytes] = {}
        self._nonce_counter: Dict[str, int] = {}
    
    def generate_key_pair(self) -> Tuple[bytes, bytes]:
        """生成密钥对"""
        private_key = secrets.token_bytes(32)
        public_key = hashlib.sha256(private_key).digest()
        return public_key, private_key
    
    def derive_key(self, password: str, salt: bytes = None) -> Tuple[bytes, bytes]:
        """从密码派生密钥"""
        if salt is None:
            salt = secrets.token_bytes(16)
        
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            iterations=100000,
            dklen=32
        )
        return key, salt
    
    def encrypt(self, data: bytes, key: bytes) -> bytes:
        """加密数据"""
        nonce = secrets.token_bytes(8)
        key_extended = (key * ((len(data) // len(key)) + 1))[:len(data)]
        encrypted = bytes(a ^ b for a, b in zip(data, key_extended))
        result = nonce + encrypted
        hmac_value = hmac.new(key, result, hashlib.sha256).digest()[:16]
        return result + hmac_value
    
    def decrypt(self, encrypted_data: bytes, key: bytes) -> Optional[bytes]:
        """解密数据"""
        try:
            if len(encrypted_data) < 24:
                return None
            
            nonce = encrypted_data[:8]
            hmac_value = encrypted_data[-16:]
            data = encrypted_data[8:-16]
            
            expected_hmac = hmac.new(key, nonce + data, hashlib.sha256).digest()[:16]
            if not hmac.compare_digest(hmac_value, expected_hmac):
                return None
            
            key_extended = (key * ((len(data) // len(key)) + 1))[:len(data)]
            decrypted = bytes(a ^ b for a, b in zip(data, key_extended))
            return decrypted
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None
    
    def sign(self, data: bytes, key: bytes) -> bytes:
        """对数据签名"""
        return hmac.new(key, data, hashlib.sha256).digest()
    
    def verify(self, data: bytes, signature: bytes, key: bytes) -> bool:
        """验证签名"""
        expected = self.sign(data, key)
        return hmac.compare_digest(signature, expected)
    
    def hash_password(self, password: str) -> Tuple[str, str]:
        """哈希密码"""
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations=100000
        ).hex()
        return hashed, salt
    
    def verify_password(self, password: str, hashed: str, salt: str) -> bool:
        """验证密码"""
        expected = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations=100000
        ).hex()
        return hmac.compare_digest(expected, hashed)
    
    def compute_hash(self, data: bytes) -> str:
        """计算SHA256哈希"""
        return hashlib.sha256(data).hexdigest()
    
    def compute_file_hash(self, file_path: str) -> str:
        """计算文件哈希"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()


class IdentityManager:
    """身份管理器"""
    
    def __init__(self, crypto: CryptoManager = None):
        self.crypto = crypto or CryptoManager()
        self._identities: Dict[str, Dict] = {}
        self._trusted: Dict[str, str] = {}
        self._current_identity: Optional[Dict] = None
        self._tokens: Dict[str, str] = {}
    
    def create_identity(self, user_id: str, user_name: str, device_id: str = None) -> Dict:
        """创建身份"""
        device_id = device_id or secrets.token_hex(8)
        public_key, private_key = self.crypto.generate_key_pair()
        
        identity = {
            "user_id": user_id,
            "user_name": user_name,
            "device_id": device_id,
            "public_key": public_key.hex(),
            "created_at": time.time(),
            "last_active": time.time(),
        }
        
        self._identities[device_id] = identity
        self._current_identity = identity
        self._tokens[device_id] = secrets.token_hex(32)
        
        return identity
    
    def get_identity(self, device_id: str = None) -> Optional[Dict]:
        """获取身份"""
        if device_id:
            return self._identities.get(device_id)
        return self._current_identity
    
    def authenticate(self, device_id: str, token: str) -> bool:
        """验证设备令牌"""
        stored_token = self._tokens.get(device_id)
        if stored_token and hmac.compare_digest(token, stored_token):
            identity = self._identities.get(device_id)
            if identity:
                identity["last_active"] = time.time()
            return True
        return False
    
    def trust_device(self, device_id: str, trust_level: str = "trusted"):
        """信任设备"""
        self._trusted[device_id] = trust_level
    
    def is_trusted(self, device_id: str) -> bool:
        """检查设备是否被信任"""
        return self._trusted.get(device_id) in ("trusted", "verified")
    
    def get_trust_level(self, device_id: str) -> str:
        """获取设备信任级别"""
        return self._trusted.get(device_id, "unknown")


class SecureChannel:
    """安全通道"""
    
    def __init__(self, crypto: CryptoManager = None):
        self.crypto = crypto or CryptoManager()
        self._session_keys: Dict[str, bytes] = {}
        self._channels: Dict[str, Dict] = {}
    
    def initiate_handshake(self, peer_id: str, private_key: bytes) -> Dict:
        """发起握手"""
        public_key = hashlib.sha256(private_key).digest()
        handshake = {
            "public_key": public_key.hex(),
            "timestamp": time.time(),
            "nonce": secrets.token_hex(16),
        }
        
        self._channels[peer_id] = {
            "local_public": public_key,
            "local_private": private_key,
            "handshake": handshake,
        }
        
        return handshake
    
    def complete_handshake(self, peer_id: str, peer_handshake: Dict, private_key: bytes) -> bool:
        """完成握手"""
        try:
            peer_public = bytes.fromhex(peer_handshake["public_key"])
            combined = private_key + peer_public
            session_key = hashlib.sha256(combined).digest()
            self._session_keys[peer_id] = session_key
            self._channels[peer_id]["session_key"] = session_key
            self._channels[peer_id]["peer_public"] = peer_public
            return True
        except Exception as e:
            logger.error(f"Handshake failed: {e}")
            return False
    
    def encrypt_message(self, peer_id: str, message: bytes) -> Optional[bytes]:
        """加密消息"""
        session_key = self._session_keys.get(peer_id)
        if not session_key:
            return None
        return self.crypto.encrypt(message, session_key)
    
    def decrypt_message(self, peer_id: str, encrypted: bytes) -> Optional[bytes]:
        """解密消息"""
        session_key = self._session_keys.get(peer_id)
        if not session_key:
            return None
        return self.crypto.decrypt(encrypted, session_key)
    
    def close_channel(self, peer_id: str):
        """关闭通道"""
        if peer_id in self._session_keys:
            del self._session_keys[peer_id]
        if peer_id in self._channels:
            del self._channels[peer_id]


class AccessControl:
    """访问控制"""
    
    def __init__(self):
        self._policies: Dict[str, Dict] = {}
        self._roles: Dict[str, set] = {}
        self._roles["admin"] = {"read", "write", "delete", "manage"}
        self._roles["user"] = {"read", "write"}
        self._roles["guest"] = {"read"}
        self.user_roles: Dict[str, str] = {}
    
    def check_permission(self, role: str, resource: str, action: str) -> bool:
        """检查权限"""
        if resource in self._policies:
            if role in self._policies[resource]:
                return action in self._policies[resource][role]
        
        if role in self._roles:
            return action in self._roles[role]
        
        return False
    
    def assign_role(self, user_id: str, role: str):
        """分配角色"""
        self.user_roles[user_id] = role
    
    def get_role(self, user_id: str) -> str:
        """获取用户角色"""
        return self.user_roles.get(user_id, "guest")


__all__ = [
    "CryptoManager",
    "IdentityManager",
    "SecureChannel",
    "AccessControl",
]
