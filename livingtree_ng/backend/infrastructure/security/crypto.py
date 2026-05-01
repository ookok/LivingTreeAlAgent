#!/usr/bin/env python3
"""
加密工具模块 - 用于加密保存敏感配置如API密钥
"""

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

class CryptoManager:
    """加密管理器"""
    
    def __init__(self, config_dir: str = None):
        self.config_dir = config_dir or os.path.expanduser("~/.livingtree_ng")
        self.key_path = os.path.join(self.config_dir, "secret.key")
        self._ensure_dir()
        self._ensure_key()
    
    def _ensure_dir(self):
        """确保配置目录存在"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
    
    def _ensure_key(self):
        """确保密钥文件存在"""
        if not os.path.exists(self.key_path):
            key = Fernet.generate_key()
            with open(self.key_path, 'wb') as f:
                f.write(key)
    
    def _get_key(self) -> bytes:
        """获取加密密钥"""
        with open(self.key_path, 'rb') as f:
            return f.read()
    
    def encrypt(self, plain_text: str) -> str:
        """加密字符串"""
        fernet = Fernet(self._get_key())
        return fernet.encrypt(plain_text.encode()).decode()
    
    def decrypt(self, encrypted_text: str) -> str:
        """解密字符串"""
        fernet = Fernet(self._get_key())
        return fernet.decrypt(encrypted_text.encode()).decode()

# 单例实例
crypto_manager = CryptoManager()
