"""
LivingTree 加密配置模块
========================

用 AES-GCM 加密敏感配置项（API Key 等）。
密钥通过环境变量 LIVINGTREE_SECRET_KEY 或本地密钥文件管理。
"""

import os
import json
import base64
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_AVAILABLE = True
    USE_FERNET = False
except ImportError:
    try:
        from cryptography.fernet import Fernet as _Fernet
        CRYPTO_AVAILABLE = True
        USE_FERNET = True
    except ImportError:
        CRYPTO_AVAILABLE = False
        USE_FERNET = False


def _get_secret_key() -> bytes:
    """获取 256-bit 加密密钥。优先级：环境变量 > 本地密钥文件 > 派生密钥"""
    env_key = os.environ.get("LIVINGTREE_SECRET_KEY")
    if env_key:
        return base64.b64decode(env_key)

    key_file = Path(__file__).parent.parent.parent / "data" / ".ltkey"
    if key_file.exists():
        return base64.b64decode(key_file.read_bytes().strip())

    # 派生密钥 (机器指纹)
    machine_id = hashlib.sha256(os.environ.get("COMPUTERNAME", "livingtree").encode()).digest()
    return machine_id


_ENCRYPTION_KEY: Optional[bytes] = None


def _get_key() -> bytes:
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is None:
        _ENCRYPTION_KEY = _get_secret_key()
    return _ENCRYPTION_KEY


def encrypt_value(plaintext: str) -> str:
    """AES-GCM 加密字符串，返回 base64 编码的密文（含 nonce）"""
    if not CRYPTO_AVAILABLE:
        return base64.b64encode(plaintext.encode()).decode()
    if USE_FERNET:
        f = _Fernet(base64.urlsafe_b64encode(_get_key()[:32]))
        return f.encrypt(plaintext.encode()).decode()
    key = _get_key()[:32]
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt_value(ciphertext: str) -> str:
    """AES-GCM 解密字符串"""
    if not CRYPTO_AVAILABLE:
        try:
            return base64.b64decode(ciphertext).decode()
        except Exception:
            return ciphertext
    if USE_FERNET:
        f = _Fernet(base64.urlsafe_b64encode(_get_key()[:32]))
        return f.decrypt(ciphertext.encode()).decode()
    try:
        data = base64.b64decode(ciphertext)
        key = _get_key()[:32]
        aesgcm = AESGCM(key)
        nonce, ct = data[:12], data[12:]
        return aesgcm.decrypt(nonce, ct, None).decode()
    except Exception:
        return ciphertext


def encrypt_file(input_path: str, output_path: str = None):
    """加密 JSON 文件中的敏感字段"""
    if output_path is None:
        output_path = input_path
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    def _encrypt_dict(d):
        for key, value in d.items():
            if isinstance(value, dict):
                _encrypt_dict(value)
            elif isinstance(value, str) and key in ("api_key", "api_secret", "access_token", "secret_key"):
                d[key] = encrypt_value(value)

    _encrypt_dict(data)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def decrypt_file(input_path: str) -> Dict[str, Any]:
    """解密 JSON 文件中的敏感字段并返回数据"""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    def _decrypt_dict(d):
        for key, value in d.items():
            if isinstance(value, dict):
                _decrypt_dict(value)
            elif isinstance(value, str) and key in ("api_key", "api_secret", "access_token", "secret_key"):
                d[key] = decrypt_value(value)

    _decrypt_dict(data)
    return data


__all__ = [
    "encrypt_value", "decrypt_value",
    "encrypt_file", "decrypt_file",
]
