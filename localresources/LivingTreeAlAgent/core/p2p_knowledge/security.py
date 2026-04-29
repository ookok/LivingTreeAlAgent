"""
安全加密模块

实现端到端加密、身份验证和访问控制
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import secrets
import time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from typing import Optional

logger = logging.getLogger(__name__)


class CryptoManager:
    """加密管理器"""
    
    def __init__(self):
        self.private_key: Optional[ec.EllipticCurvePrivateKey] = None
        self.public_key: Optional[ec.EllipticCurvePublicKey] = None
        self.key_id: Optional[str] = None
        
        # 共享密钥缓存
        self.shared_keys: dict[str, bytes] = {}
    
    def generate_keypair(self) -> str:
        """生成密钥对"""
        self.private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        self.public_key = self.private_key.public_key()
        
        # 生成密钥ID
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self.key_id = hashlib.sha256(pub_bytes).hexdigest()[:16]
        
        logger.info(f"Generated new keypair: {self.key_id}")
        return self.key_id
    
    def export_public_key(self) -> str:
        """导出公钥"""
        if not self.public_key:
            self.generate_keypair()
        
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(pub_bytes).decode()
    
    def import_public_key(self, key_data: str) -> bool:
        """导入公钥"""
        try:
            pub_bytes = base64.b64decode(key_data)
            self.public_key = serialization.load_der_public_key(pub_bytes, default_backend())
            return True
        except Exception as e:
            logger.error(f"Import public key failed: {e}")
            return False
    
    def derive_shared_key(self, peer_key_id: str, peer_public_key: bytes) -> bytes:
        """使用ECDH派生共享密钥"""
        try:
            peer_pub = serialization.load_der_public_key(peer_public_key, default_backend())
            
            shared = self.private_key.exchange(ec.ECDH(), peer_pub)
            
            # 派生会话密钥
            session_key = hashlib.pbkdf2_hmac(
                'sha256',
                shared,
                peer_key_id.encode(),
                100000,
                dklen=32
            )
            
            self.shared_keys[peer_key_id] = session_key
            return session_key
            
        except Exception as e:
            logger.error(f"Derive shared key failed: {e}")
            return b''
    
    def get_shared_key(self, peer_key_id: str) -> Optional[bytes]:
        """获取共享密钥"""
        return self.shared_keys.get(peer_key_id)
    
    def encrypt_data(self, data: bytes, key: Optional[bytes] = None) -> tuple[bytes, bytes]:
        """
        AES-256-GCM加密
        返回: (nonce, ciphertext_with_tag)
        """
        if not key:
            key = secrets.token_bytes(32)  # 256位密钥
        
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)  # 96位nonce
        ciphertext = aesgcm.encrypt(nonce, data, None)
        
        return nonce, ciphertext
    
    def decrypt_data(self, nonce: bytes, ciphertext: bytes, key: bytes) -> Optional[bytes]:
        """AES-256-GCM解密"""
        try:
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as e:
            logger.error(f"Decrypt failed: {e}")
            return None


class IdentityManager:
    """身份管理器"""
    
    def __init__(self, crypto: CryptoManager):
        self.crypto = crypto
        self.node_id: Optional[str] = None
        self.user_id: Optional[str] = None
        self.certificate: Optional[str] = None
        self.trusted_peers: set[str] = set()
    
    def create_identity(self, node_id: str, user_id: str) -> str:
        """创建本地身份"""
        self.node_id = node_id
        self.user_id = user_id
        
        # 生成密钥对
        key_id = self.crypto.generate_keypair()
        
        # 生成证书（简化版，实际应使用PKI）
        self.certificate = self._create_self_certificate()
        
        logger.info(f"Created identity: node={node_id}, user={user_id}, key={key_id}")
        return key_id
    
    def _create_self_certificate(self) -> str:
        """创建自签名证书"""
        cert_data = f"{self.node_id}:{self.user_id}:{self.crypto.key_id}:{time.time()}"
        cert_hash = hashlib.sha256(cert_data.encode()).hexdigest()
        return f"CERT:{self.crypto.export_public_key()}:{cert_hash}"
    
    def verify_peer(self, peer_id: str, peer_certificate: str) -> bool:
        """验证对等方身份"""
        # 简化验证：检查证书哈希
        if not peer_certificate.startswith("CERT:"):
            return False
        
        parts = peer_certificate.split(':')
        if len(parts) < 3:
            return False
        
        self.trusted_peers.add(peer_id)
        return True
    
    def is_trusted(self, peer_id: str) -> bool:
        """检查是否信任对等方"""
        return peer_id in self.trusted_peers


class MessageAuthenticator:
    """消息认证器"""
    
    def __init__(self, secret_key: bytes):
        self.secret_key = secret_key
    
    def create_mac(self, message: bytes) -> bytes:
        """创建消息认证码"""
        return hmac.new(self.secret_key, message, hashlib.sha256).digest()
    
    def verify_mac(self, message: bytes, mac: bytes) -> bool:
        """验证消息认证码"""
        expected = self.create_mac(message)
        return hmac.compare_digest(expected, mac)
    
    def sign_message(self, message: bytes) -> tuple[bytes, bytes]:
        """签名消息 (nonce, signature)"""
        nonce = secrets.token_bytes(16)
        signed = nonce + self.create_mac(message + nonce)
        return nonce, signed
    
    def verify_signature(self, message: bytes, nonce: bytes, signature: bytes) -> bool:
        """验证签名"""
        expected = self.create_mac(message + nonce)
        return hmac.compare_digest(expected, signature[16:])


class AccessControl:
    """访问控制器"""
    
    def __init__(self):
        self.permissions: dict[str, set[str]] = {}  # user_id -> permissions
        self.share_permissions: dict[str, dict] = {}  # share_code -> permissions
        self.default_permissions = {"read"}
    
    def grant_permission(self, user_id: str, permission: str):
        """授予权限"""
        if user_id not in self.permissions:
            self.permissions[user_id] = set()
        self.permissions[user_id].add(permission)
    
    def revoke_permission(self, user_id: str, permission: str):
        """撤销权限"""
        if user_id in self.permissions:
            self.permissions[user_id].discard(permission)
    
    def has_permission(self, user_id: str, permission: str) -> bool:
        """检查权限"""
        perms = self.permissions.get(user_id, self.default_permissions)
        return permission in perms
    
    def set_share_permissions(
        self,
        share_code: str,
        can_read: bool = True,
        can_write: bool = False,
        can_share: bool = False,
        expires_at: Optional[float] = None
    ):
        """设置分享权限"""
        self.share_permissions[share_code] = {
            "can_read": can_read,
            "can_write": can_write,
            "can_share": can_share,
            "expires_at": expires_at
        }
    
    def check_share_permission(
        self,
        share_code: str,
        permission: str
    ) -> bool:
        """检查分享权限"""
        perms = self.share_permissions.get(share_code)
        if not perms:
            return False
        
        if perms.get("expires_at") and time.time() > perms["expires_at"]:
            return False
        
        perm_map = {
            "read": "can_read",
            "write": "can_write",
            "share": "can_share"
        }
        
        return perms.get(perm_map.get(permission, ""), False)


class SecureChannel:
    """安全通道"""
    
    def __init__(
        self,
        crypto: CryptoManager,
        peer_id: str,
        peer_key: bytes,
        is_initiator: bool = False
    ):
        self.crypto = crypto
        self.peer_id = peer_id
        self.peer_key = peer_key
        self.is_initiator = is_initiator
        
        # 派生会话密钥
        session_key = hashlib.pbkdf2_hmac(
            'sha256',
            self.peer_key,
            f"{'init' if is_initiator else 'resp'}:{peer_id}".encode(),
            100000,
            dklen=32
        )
        
        self.cipher = CryptoManager()
        self.auth = MessageAuthenticator(session_key)
        self.session_key = session_key
        
        # 序列号
        self.local_seq = 0
        self.remote_seq = 0
    
    def encrypt_message(self, plaintext: bytes) -> bytes:
        """加密并签名消息"""
        # 增加序列号
        self.local_seq += 1
        
        # 添加序列号到消息
        message = self.local_seq.to_bytes(8, 'big') + plaintext
        
        # 签名
        nonce, signature = self.auth.sign_message(message)
        
        # 加密
        cipher_nonce, ciphertext = self.cipher.encrypt_data(message, self.session_key)
        
        # 返回: nonce + cipher_nonce + ciphertext
        return nonce + cipher_nonce + ciphertext
    
    def decrypt_message(self, data: bytes) -> Optional[bytes]:
        """解密并验证消息"""
        if len(data) < 12 + 16:  # 最小长度检查
            return None
        
        # 提取各部分
        nonce = data[:16]
        cipher_nonce = data[16:28]
        ciphertext = data[28:]
        
        # 解密
        plaintext = self.cipher.decrypt_data(cipher_nonce, ciphertext, self.session_key)
        if not plaintext:
            return None
        
        # 提取序列号
        seq_bytes = plaintext[:8]
        message = plaintext[8:]
        
        # 恢复nonce和签名用于验证
        recovered_nonce = nonce
        recovered_sig = nonce + self.auth.create_mac(seq_bytes + message)
        
        # 验证签名
        if not self.auth.verify_signature(message, seq_bytes, recovered_sig):
            logger.warning("Signature verification failed")
            return None
        
        # 检查序列号
        remote_seq = int.from_bytes(seq_bytes, 'big')
        if remote_seq <= self.remote_seq:
            logger.warning("Replay attack detected")
            return None
        
        self.remote_seq = remote_seq
        return message


class WatermarkGenerator:
    """水印生成器"""
    
    @staticmethod
    def generate_watermark(
        user_id: str,
        document_id: str,
        timestamp: float
    ) -> str:
        """生成文档水印"""
        data = f"{user_id}:{document_id}:{timestamp}:secret"
        watermark = hashlib.sha256(data.encode()).hexdigest()[:32]
        return f"HERMES-{watermark}"
    
    @staticmethod
    def embed_watermark(text: str, watermark: str) -> str:
        """嵌入水印到文本"""
        # 简单实现：在文本末尾添加不可见水印标记
        return f"{text}\n<!-- {watermark} -->"
    
    @staticmethod
    def extract_watermark(text: str) -> Optional[str]:
        """提取水印"""
        if "<!-- " in text and " -->" in text:
            start = text.rfind("<!-- ") + 5
            end = text.rfind(" -->")
            if start < end:
                return text[start:end]
        return None


# ============= 便捷函数 =============

def create_secure_channel(
    local_key_id: str,
    peer_key_id: str,
    peer_public_key: bytes,
    is_initiator: bool = False
) -> SecureChannel:
    """创建安全通道"""
    crypto = CryptoManager()
    crypto.key_id = local_key_id
    crypto.generate_keypair()
    crypto.derive_shared_key(peer_key_id, peer_public_key)
    
    return SecureChannel(crypto, peer_key_id, peer_public_key, is_initiator)


def encrypt_file_content(data: bytes, password: Optional[str] = None) -> tuple[bytes, bytes, bytes]:
    """加密文件内容，返回(nonce, salt, ciphertext)"""
    if password:
        salt = secrets.token_bytes(16)
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=32)
    else:
        key = secrets.token_bytes(32)
        salt = b''
    
    crypto = CryptoManager()
    nonce, ciphertext = crypto.encrypt_data(data, key)
    
    return nonce, salt, ciphertext


def decrypt_file_content(nonce: bytes, salt: bytes, ciphertext: bytes, password: str) -> Optional[bytes]:
    """解密文件内容"""
    try:
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=32)
        crypto = CryptoManager()
        return crypto.decrypt_data(nonce, ciphertext, key)
    except Exception as e:
        logger.error(f"Decrypt file failed: {e}")
        return None
