"""
加密工具模块
Cryptography Utilities for Activation License System

提供：
- AES-256-GCM 对称加密（用于实名信息加密）
- SHA-256 哈希（用于激活码校验）
- HMAC 消息认证（用于防篡改）
- 密钥派生（PBKDF2）
"""

import hashlib
import hmac
import os
import json
import base64
import secrets
from typing import Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


try:
    from Cryptodome.Cipher import AES
    from Cryptodome.Util import Padding
    from Cryptodome.Protocol.KDF import PBKDF2
    CRYPTO_AVAILABLE = True
except ImportError:
    try:
        from Crypto.Cipher import AES
        from Crypto.Util import Padding
        from Crypto.Protocol.KDF import PBKDF2
        CRYPTO_AVAILABLE = True
    except ImportError:
        CRYPTO_AVAILABLE = False


@dataclass
class EncryptedData:
    """加密数据结构"""
    ciphertext: bytes      # 密文
    nonce: bytes           # 随机向量
    tag: bytes             # 认证标签 (GCM模式)
    salt: bytes            # 盐值
    
    def to_json(self) -> str:
        """序列化为JSON"""
        return json.dumps({
            'ciphertext': base64.b64encode(self.ciphertext).decode('ascii'),
            'nonce': base64.b64encode(self.nonce).decode('ascii'),
            'tag': base64.b64encode(self.tag).decode('ascii'),
            'salt': base64.b64encode(self.salt).decode('ascii'),
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'EncryptedData':
        """从JSON反序列化"""
        data = json.loads(json_str)
        return cls(
            ciphertext=base64.b64decode(data['ciphertext']),
            nonce=base64.b64decode(data['nonce']),
            tag=base64.b64decode(data['tag']),
            salt=base64.b64decode(data['salt']),
        )


class CryptoUtils:
    """
    加密工具类
    
    设计理念：
    - 实名信息使用 AES-256-GCM 加密，确保机密性 + 完整性
    - 激活码校验使用 HMAC-SHA256，防止伪造
    - 密钥派生使用 PBKDF2，抵御暴力破解
    """
    
    # 密钥长度 (256位)
    KEY_SIZE = 32
    # 盐值长度 (128位)
    SALT_SIZE = 16
    # Nonce长度 (GCM标准96位)
    NONCE_SIZE = 12
    
    def __init__(self, master_key: Optional[str] = None):
        """
        初始化加密工具
        
        Args:
            master_key: 主密钥（如果为None，从环境变量或机器特征派生）
        """
        if master_key:
            self._master_key = master_key.encode('utf-8')
        else:
            self._master_key = self._derive_machine_key()
    
    def _derive_machine_key(self) -> bytes:
        """从机器特征派生密钥"""
        # 组合多种机器特征
        import platform
        machine_id = (
            platform.node() +
            platform.machine() +
            platform.processor()
        )
        # 使用固定盐值派生
        salt = b'HermesLicenseSystem_v1'
        return PBKDF2(
            machine_id.encode('utf-8'),
            salt,
            dkLen=self.KEY_SIZE,
            count=100000
        )
    
    def encrypt_real_name(self, real_name: str, id_number: str = "") -> EncryptedData:
        """
        加密实名信息
        
        Args:
            real_name: 真实姓名
            id_number: 身份证号（可选）
        
        Returns:
            EncryptedData: 加密后的数据
        """
        if not CRYPTO_AVAILABLE:
            # 降级方案：仅Base64编码（安全性降低）
            data = f"{real_name}|{id_number}".encode('utf-8')
            return EncryptedData(
                ciphertext=base64.b64encode(data),
                nonce=b'no_crypto',
                tag=b'no_crypto',
                salt=b'no_crypto'
            )
        
        # 准备明文数据
        plaintext = f"{real_name}|{id_number}".encode('utf-8')
        
        # 生成随机盐值和Nonce
        salt = secrets.token_bytes(self.SALT_SIZE)
        nonce = secrets.token_bytes(self.NONCE_SIZE)
        
        # 派生加密密钥
        key = PBKDF2(
            self._master_key,
            salt,
            dkLen=self.KEY_SIZE,
            count=100000
        )
        
        # 加密 (AES-256-GCM)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        
        return EncryptedData(
            ciphertext=ciphertext,
            nonce=nonce,
            tag=tag,
            salt=salt
        )
    
    def decrypt_real_name(self, encrypted: EncryptedData) -> Tuple[str, str]:
        """
        解密实名信息
        
        Args:
            encrypted: 加密的数据
        
        Returns:
            Tuple[str, str]: (真实姓名, 身份证号)
        """
        if not CRYPTO_AVAILABLE:
            # 降级方案
            data = base64.b64decode(encrypted.ciphertext).decode('utf-8')
            parts = data.split('|', 1)
            return parts[0], parts[1] if len(parts) > 1 else ""
        
        # 派生解密密钥
        key = PBKDF2(
            self._master_key,
            encrypted.salt,
            dkLen=self.KEY_SIZE,
            count=100000
        )
        
        # 解密
        cipher = AES.new(key, AES.MODE_GCM, nonce=encrypted.nonce)
        try:
            plaintext = cipher.decrypt_and_verify(encrypted.ciphertext, encrypted.tag)
            data = plaintext.decode('utf-8')
            parts = data.split('|', 1)
            return parts[0], parts[1] if len(parts) > 1 else ""
        except ValueError:
            raise ValueError("解密失败：数据已被篡改或密钥不匹配")
    
    @staticmethod
    def compute_license_checksum(license_key: str) -> str:
        """
        计算激活码校验位
        
        格式: ENT-PRO-XXXX-XXXX-XXXX-YYYYMMDD
        
        算法: 取前15位进行SHA256哈希，取前6位作为校验位
        """
        hash_input = license_key.upper().replace('-', '')
        hash_result = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
        return hash_result[:6].upper()
    
    @staticmethod
    def verify_license_checksum(license_key: str) -> bool:
        """
        验证激活码校验位
        
        Args:
            license_key: 激活码
        
        Returns:
            bool: 校验是否通过
        """
        parts = license_key.split('-')
        if len(parts) != 6:
            return False
        
        # 重组前5部分
        core_parts = parts[:5]
        provided_checksum = parts[5]
        
        # 计算期望的校验位
        expected_checksum = CryptoUtils.compute_license_checksum('-'.join(core_parts))
        
        return provided_checksum == expected_checksum
    
    @staticmethod
    def generate_hmac(data: str, key: str = None) -> str:
        """
        生成HMAC用于防篡改
        
        Args:
            data: 待签名数据
            key: 密钥（如果为None，使用默认密钥）
        
        Returns:
            str: HMAC-SHA256 十六进制字符串
        """
        if key is None:
            key = "HermesLicenseHMAC_v1_default_key_change_in_production"
        
        mac = hmac.new(
            key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        )
        return mac.hexdigest()
    
    @staticmethod
    def verify_hmac(data: str, mac: str, key: str = None) -> bool:
        """验证HMAC"""
        expected_mac = CryptoUtils.generate_hmac(data, key)
        return hmac.compare_digest(expected_mac, mac)
    
    @staticmethod
    def hash_password(password: str, salt: bytes = None) -> Tuple[str, bytes]:
        """
        哈希密码（用于激活码本地存储）
        
        Returns:
            Tuple[str, bytes]: (哈希值, 盐值)
        """
        if salt is None:
            salt = secrets.token_bytes(32)
        
        hash_value = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return hash_value.hex(), salt
    
    @staticmethod
    def verify_password(password: str, hash_value: str, salt: bytes) -> bool:
        """验证密码哈希"""
        expected_hash, _ = CryptoUtils.hash_password(password, salt)
        return hmac.compare_digest(expected_hash, hash_value)


# 全局单例
_crypto_utils: Optional[CryptoUtils] = None


def get_crypto_utils() -> CryptoUtils:
    """获取加密工具单例"""
    global _crypto_utils
    if _crypto_utils is None:
        _crypto_utils = CryptoUtils()
    return _crypto_utils