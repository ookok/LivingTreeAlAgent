"""
Security - 端到端加密层
======================

基于Noise Protocol的加密实现：
- X25519密钥交换
- ChaCha20-Poly1305加密
- HKDF密钥派生

Author: LivingTreeAI Community
from __future__ import annotations
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Callable
from datetime import datetime
import asyncio
import logging
import os

logger = logging.getLogger(__name__)


@dataclass
class SecurityContext:
    """安全上下文"""
    peer_id: str
    session_key: bytes
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    messages_sent: int = 0
    messages_received: int = 0


class NoiseProtocol:
    """
    Noise Protocol 实现

    支持：
    - X25519密钥交换
    - ChaCha20-Poly1305对称加密
    - HKDF密钥派生
    """

    def __init__(self):
        self._private_key = None
        self._public_key = None
        self._sessions: Dict[str, SecurityContext] = {}

        # 初始化密钥
        self._init_keys()

    def _init_keys(self):
        """初始化密钥对"""
        try:
            from cryptography.hazmat.primitives.asymmetric import x25519

            self._private_key = x25519.X25519PrivateKey.generate()
            self._public_key = self._private_key.public_key()

            logger.info("Noise Protocol 密钥初始化完成")

        except ImportError:
            logger.warning("cryptography 库未安装，将使用简单加密（不推荐生产环境）")
            self._private_key = None
            self._public_key = None

    def get_public_key_bytes(self) -> bytes:
        """获取公钥字节"""
        if self._public_key is None:
            return b""
        return self._public_key.public_bytes_raw()

    def handshake(self, remote_public_key_bytes: bytes) -> bytes:
        """
        执行Noise IK握手

        Args:
            remote_public_key_bytes: 远程公钥

        Returns:
            会话密钥
        """
        if self._private_key is None or not remote_public_key_bytes:
            # 回退到简单密钥派生（不推荐）
            return os.urandom(32)

        try:
            from cryptography.hazmat.primitives.asymmetric import x25519
            from cryptography.hazmat.primitives.kdf.hkdf import HKDF
            from cryptography.hazmat.primitives import hashes

            # 密钥交换
            remote_pubkey = x25519.X25519PublicKey.from_public_bytes(remote_public_key_bytes)
            shared_secret = self._private_key.exchange(remote_pubkey)

            # HKDF派生会话密钥
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,  # ChaCha20-Poly1305 需要32字节密钥
                salt=None,
                info=b"lifetree-noise-session-key",
            )
            session_key = hkdf.derive(shared_secret)

            return session_key

        except Exception as e:
            logger.error(f"Noise握手失败: {e}")
            return os.urandom(32)

    def encrypt_message(self, session_key: bytes, plaintext: bytes) -> bytes:
        """
        加密消息

        Args:
            session_key: 会话密钥
            plaintext: 明文

        Returns:
            密文（包含nonce）
        """
        if not session_key or len(session_key) < 32:
            # 无加密，回退
            return plaintext

        try:
            from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

            aead = ChaCha20Poly1305(session_key)
            nonce = os.urandom(12)  # ChaCha20-Poly1305需要12字节nonce
            ciphertext = aead.encrypt(nonce, plaintext, None)

            return nonce + ciphertext

        except Exception as e:
            logger.error(f"消息加密失败: {e}")
            return plaintext

    def decrypt_message(self, session_key: bytes, ciphertext: bytes) -> bytes:
        """
        解密消息

        Args:
            session_key: 会话密钥
            ciphertext: 密文（包含nonce）

        Returns:
            明文
        """
        if not session_key or len(session_key) < 32:
            # 无加密，回退
            return ciphertext

        try:
            from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

            aead = ChaCha20Poly1305(session_key)

            if len(ciphertext) < 12:
                return ciphertext

            nonce = ciphertext[:12]
            data = ciphertext[12:]

            plaintext = aead.decrypt(nonce, data, None)
            return plaintext

        except Exception as e:
            logger.error(f"消息解密失败: {e}")
            return ciphertext

    def create_session(self, peer_id: str, session_key: bytes) -> SecurityContext:
        """创建安全会话"""
        ctx = SecurityContext(
            peer_id=peer_id,
            session_key=session_key,
        )
        self._sessions[peer_id] = ctx
        return ctx

    def get_session(self, peer_id: str) -> Optional[SecurityContext]:
        """获取安全会话"""
        return self._sessions.get(peer_id)

    def remove_session(self, peer_id: str):
        """移除安全会话"""
        if peer_id in self._sessions:
            del self._sessions[peer_id]

    def encrypt_for_peer(self, peer_id: str, plaintext: bytes) -> Optional[bytes]:
        """加密消息给指定节点"""
        session = self._sessions.get(peer_id)
        if session is None:
            logger.warning(f"不存在到 {peer_id} 的安全会话")
            return None

        ciphertext = self.encrypt_message(session.session_key, plaintext)
        session.messages_sent += 1
        session.last_activity = datetime.now()

        return ciphertext

    def decrypt_from_peer(self, peer_id: str, ciphertext: bytes) -> Optional[bytes]:
        """解密来自指定节点的消息"""
        session = self._sessions.get(peer_id)
        if session is None:
            logger.warning(f"不存在到 {peer_id} 的安全会话")
            return None

        plaintext = self.decrypt_message(session.session_key, ciphertext)
        session.messages_received += 1
        session.last_activity = datetime.now()

        return plaintext

    def get_all_sessions(self) -> Dict[str, SecurityContext]:
        """获取所有会话"""
        return self._sessions.copy()


class SecureChannel:
    """
    安全通道

    包装加密/解密操作，提供简单的接口
    """

    def __init__(self, security: NoiseProtocol, peer_id: str):
        self.security = security
        self.peer_id = peer_id

    async def send_encrypted(self, data: bytes) -> bytes:
        """发送加密消息"""
        encrypted = self.security.encrypt_for_peer(self.peer_id, data)
        if encrypted is None:
            # 没有会话密钥，使用明文
            return data
        return encrypted

    async def receive_decrypted(self, data: bytes) -> bytes:
        """接收解密消息"""
        decrypted = self.security.decrypt_from_peer(self.peer_id, data)
        if decrypted is None:
            # 没有会话密钥，假设是明文
            return data
        return decrypted


# 单例实例
_security: Optional[NoiseProtocol] = None


def get_security() -> NoiseProtocol:
    global _security
    if _security is None:
        _security = NoiseProtocol()
    return _security