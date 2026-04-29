"""
消息加密与解密模块

实现端到端加密、签名验签、密钥派生
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import os
import secrets
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class MailCrypto:
    """
    邮箱加密器
    
    功能:
    - ECDH密钥交换
    - AES-256-GCM加密
    - 消息签名与验签
    - 密钥派生
    """
    
    # 加密参数
    KEY_SIZE = 32           # 256位密钥
    IV_SIZE = 12            # 96位IV (GCM推荐)
    SALT_SIZE = 16          # 128位盐
    NONCE_SIZE = 8         # 64位随机数
    
    # 签名曲线
    SIGNATURE_CURVE = ec.SECP256R1()
    
    def __init__(self):
        self.private_key: Optional[ec.EllipticCurvePrivateKey] = None
        self.public_key: Optional[ec.EllipticCurvePublicKey] = None
        self.key_id: Optional[str] = None
        
        # 共享密钥缓存
        self._shared_keys: dict[str, bytes] = {}
    
    def generate_keypair(self) -> tuple[str, str]:
        """
        生成密钥对
        
        Returns:
            tuple: (key_id, public_key_base64)
        """
        self.private_key = ec.generate_private_key(self.SIGNATURE_CURVE, default_backend())
        self.public_key = self.private_key.public_key()
        
        # 计算密钥ID
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self.key_id = hashlib.sha256(pub_bytes).hexdigest()[:16]
        
        # 导出公钥
        public_key_b64 = base64.b64encode(pub_bytes).decode()
        
        logger.info(f"Generated keypair: {self.key_id}")
        return self.key_id, public_key_b64
    
    def import_private_key(self, key_data: bytes) -> bool:
        """
        导入私钥
        
        Args:
            key_data: DER格式私钥
            
        Returns:
            bool: 是否成功
        """
        try:
            self.private_key = serialization.load_der_private_key(
                key_data, password=None, backend=default_backend()
            )
            self.public_key = self.private_key.public_key()
            
            pub_bytes = self.public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            self.key_id = hashlib.sha256(pub_bytes).hexdigest()[:16]
            
            logger.info(f"Imported private key: {self.key_id}")
            return True
        except Exception as e:
            logger.error(f"Import private key failed: {e}")
            return False
    
    def export_public_key(self) -> str:
        """导出公钥 (Base64)"""
        if not self.public_key:
            self.generate_keypair()
        
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(pub_bytes).decode()
    
    def derive_shared_key(self, peer_public_key_b64: str) -> Optional[bytes]:
        """
        使用ECDH派生共享密钥
        
        Args:
            peer_public_key_b64: 对方公钥 (Base64)
            
        Returns:
            bytes: 共享密钥
        """
        try:
            peer_pub_bytes = base64.b64decode(peer_public_key_b64)
            peer_pub = serialization.load_der_public_key(peer_pub_bytes, default_backend())
            
            # ECDH交换
            shared = self.private_key.exchange(ec.ECDH(), peer_pub)
            
            # 派生会话密钥
            session_key = hashlib.pbkdf2_hmac(
                'sha256',
                shared,
                self.key_id.encode() if self.key_id else b'',
                100000,
                dklen=self.KEY_SIZE
            )
            
            peer_key_id = hashlib.sha256(peer_pub_bytes).hexdigest()[:16]
            self._shared_keys[peer_key_id] = session_key
            
            return session_key
            
        except Exception as e:
            logger.error(f"Derive shared key failed: {e}")
            return None
    
    def get_shared_key(self, peer_key_id: str) -> Optional[bytes]:
        """获取共享密钥"""
        return self._shared_keys.get(peer_key_id)
    
    # ========== 消息加密 ==========
    
    def encrypt_message(self, plaintext: str, shared_key: Optional[bytes] = None) -> tuple[bytes, bytes, bytes]:
        """
        加密消息
        
        Args:
            plaintext: 明文
            shared_key: 共享密钥 (可选, 如果不提供则生成临时密钥)
            
        Returns:
            tuple: (加密数据, IV, 盐)
        """
        # 生成或使用共享密钥
        if shared_key is None:
            shared_key = secrets.token_bytes(self.KEY_SIZE)
        
        # 生成盐
        salt = secrets.token_bytes(self.SALT_SIZE)
        
        # 派生加密密钥
        encryption_key = hashlib.pbkdf2_hmac(
            'sha256',
            shared_key,
            salt,
            100000,
            dklen=self.KEY_SIZE
        )
        
        # 生成IV
        iv = secrets.token_bytes(self.IV_SIZE)
        
        # AES-GCM加密
        aesgcm = AESGCM(encryption_key)
        plaintext_bytes = plaintext.encode('utf-8')
        ciphertext = aesgcm.encrypt(iv, plaintext_bytes, None)
        
        return ciphertext, iv, salt
    
    def decrypt_message(self, ciphertext: bytes, iv: bytes, salt: bytes, 
                       shared_key: Optional[bytes] = None) -> Optional[str]:
        """
        解密消息
        
        Args:
            ciphertext: 加密数据
            iv: IV
            salt: 盐
            shared_key: 共享密钥
            
        Returns:
            str: 明文 或 None
        """
        try:
            # 派生加密密钥
            if shared_key is None:
                return None
            
            encryption_key = hashlib.pbkdf2_hmac(
                'sha256',
                shared_key,
                salt,
                100000,
                dklen=self.KEY_SIZE
            )
            
            # AES-GCM解密
            aesgcm = AESGCM(encryption_key)
            plaintext_bytes = aesgcm.decrypt(iv, ciphertext, None)
            
            return plaintext_bytes.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Decrypt message failed: {e}")
            return None
    
    # ========== 分块加密 (大文件) ==========
    
    def encrypt_chunk(self, data: bytes, key: Optional[bytes] = None) -> tuple[bytes, bytes, bytes]:
        """
        加密数据块
        
        Args:
            data: 原始数据
            key: 密钥
            
        Returns:
            tuple: (ciphertext, nonce, key_id)
        """
        if key is None:
            key = secrets.token_bytes(self.KEY_SIZE)
        
        nonce = secrets.token_bytes(self.NONCE_SIZE)
        key_id = hashlib.sha256(key).hexdigest()[:8]
        
        # 使用AES-CTR (更适合流式加密)
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        
        cipher = Cipher(algorithms.AES(key), modes.CTR(nonce), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        return ciphertext, nonce, key_id.encode()
    
    def decrypt_chunk(self, ciphertext: bytes, nonce: bytes, key_id: bytes,
                     get_key_func=None) -> Optional[bytes]:
        """
        解密数据块
        
        Args:
            ciphertext: 加密数据
            nonce: Nonce
            key_id: 密钥ID
            get_key_func: 获取密钥的回调函数
            
        Returns:
            bytes: 明文
        """
        try:
            if get_key_func:
                key = get_key_func(key_id.decode())
            else:
                key = self._shared_keys.get(key_id.decode())
            
            if not key:
                logger.error(f"Key not found: {key_id}")
                return None
            
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            
            cipher = Cipher(algorithms.AES(key), modes.CTR(nonce), backend=default_backend())
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            return plaintext
            
        except Exception as e:
            logger.error(f"Decrypt chunk failed: {e}")
            return None
    
    # ========== 数字签名 ==========
    
    def sign_message(self, message: str) -> Optional[str]:
        """
        签名消息
        
        Args:
            message: 消息
            
        Returns:
            str: 签名的Base64 或 None
        """
        if not self.private_key:
            logger.error("No private key for signing")
            return None
        
        try:
            message_bytes = message.encode('utf-8')
            signature = self.private_key.sign(
                message_bytes,
                ec.ECDSA(hashes.SHA256())
            )
            return base64.b64encode(signature).decode()
            
        except Exception as e:
            logger.error(f"Sign message failed: {e}")
            return None
    
    def verify_signature(self, message: str, signature_b64: str, public_key_b64: str) -> bool:
        """
        验签
        
        Args:
            message: 消息
            signature_b64: 签名 (Base64)
            public_key_b64: 公钥 (Base64)
            
        Returns:
            bool: 是否验证通过
        """
        try:
            message_bytes = message.encode('utf-8')
            signature = base64.b64decode(signature_b64)
            pub_bytes = base64.b64decode(public_key_b64)
            
            public_key = serialization.load_der_public_key(pub_bytes, default_backend())
            public_key.verify(signature, message_bytes, ec.ECDSA(hashes.SHA256()))
            
            return True
            
        except Exception as e:
            logger.debug(f"Verify signature failed: {e}")
            return False
    
    # ========== 哈希与校验 ==========
    
    @staticmethod
    def hash_data(data: bytes) -> str:
        """计算SHA256哈希"""
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def verify_checksum(data: bytes, expected_checksum: str) -> bool:
        """验证校验和"""
        return MailCrypto.hash_data(data) == expected_checksum
    
    @staticmethod
    def generate_message_id() -> str:
        """生成唯一消息ID"""
        random_bytes = secrets.token_bytes(16)
        return hashlib.sha256(random_bytes).hexdigest()[:16]
    
    @staticmethod
    def compute_message_hash(message: str, timestamp: float, sender: str) -> str:
        """计算消息哈希 (用于存证)"""
        data = f"{message}:{timestamp}:{sender}".encode()
        return hashlib.sha256(data).hexdigest()
