"""
LivingTree P2P NAT 穿透与加密模块
==================================

合并 p2p_broadcast (弱XOR加密)、p2p_knowledge (ECDH+AES-256-GCM) 
的加密方案，统一采用 ECDH + AES-256-GCM 强加密。

NAT 穿透策略: DIRECT → STUN → TURN → RELAY

Author: LivingTreeAI Team
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import socket
import struct
from typing import Optional, Tuple

from loguru import logger
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .models import NetworkAddress, NATType, ConnectionConfig, PeerInfo

# ============================================================================
# 加密层：ECDH + AES-256-GCM
# ============================================================================

class CryptoSession:
    """
    安全会话 —— 基于 ECDH 密钥交换 + AES-256-GCM 加密

    流程:
    1. 双方交换 X25519 公钥
    2. 各自计算共享密钥 (ECDH)
    3. 通过 HKDF 派生 AES-256-GCM 密钥
    4. 后续消息使用 AES-256-GCM 加密 + HMAC 签名
    """

    def __init__(self):
        self._private_key = x25519.X25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()
        self._shared_key: Optional[bytes] = None
        self._aesgcm: Optional[AESGCM] = None

    @property
    def public_bytes(self) -> bytes:
        """获取公钥字节（用于交换）"""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def complete_handshake(self, peer_public_bytes: bytes) -> None:
        """
        完成密钥交换

        Args:
            peer_public_bytes: 对端公钥（32字节 X25519）
        """
        peer_public = x25519.X25519PublicKey.from_public_bytes(peer_public_bytes)
        shared = self._private_key.exchange(peer_public)

        # HKDF 派生 AES-256 密钥
        derived = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"livingtree-p2p-v1",
        ).derive(shared)

        self._shared_key = derived
        self._aesgcm = AESGCM(derived)
        logger.debug("CryptoSession: 握手完成")

    def encrypt(self, plaintext: bytes) -> bytes:
        """
        加密消息

        Returns:
            nonce (12字节) + ciphertext + tag (16字节)
        """
        if self._aesgcm is None:
            raise RuntimeError("密钥交换未完成")
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def decrypt(self, encrypted: bytes) -> bytes:
        """
        解密消息

        Args:
            encrypted: nonce (前12字节) + ciphertext_and_tag
        """
        if self._aesgcm is None:
            raise RuntimeError("密钥交换未完成")
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        return self._aesgcm.decrypt(nonce, ciphertext, None)

    def sign(self, data: bytes) -> bytes:
        """HMAC-SHA256 签名"""
        if self._shared_key is None:
            raise RuntimeError("密钥交换未完成")
        return hmac.new(self._shared_key, data, hashlib.sha256).digest()

    def verify(self, data: bytes, signature: bytes) -> bool:
        """验证 HMAC 签名"""
        if self._shared_key is None:
            raise RuntimeError("密钥交换未完成")
        expected = self.sign(data)
        return hmac.compare_digest(expected, signature)


# ============================================================================
# NAT 类型检测
# ============================================================================

class NATDetector:
    """
    NAT 类型检测器

    使用 STUN 协议检测 NAT 类型：
    1. 发送 Binding Request 到 STUN 服务器
    2. 比较本地地址和公网地址
    3. 尝试从不同 IP/Port 发送请求以区分 NAT 类型
    """

    STUN_PORT = 3478
    MAGIC_COOKIE = 0x2112A442

    @staticmethod
    async def detect(
        stun_server: NetworkAddress,
        local_port: int = 0,
        timeout: float = 5.0,
    ) -> Tuple[NATType, Optional[NetworkAddress]]:
        """
        检测 NAT 类型并获取公网地址

        Returns:
            (NATType, 公网地址 或 None)
        """
        try:
            public_addr = await NATDetector._stun_request(stun_server, local_port, timeout)
            if public_addr is None:
                return NATType.UNKNOWN, None

            # 获取本地地址
            local_addr = NATDetector._get_local_address(stun_server.host)

            # 判断 NAT 类型
            if local_addr and public_addr.host == local_addr[0]:
                nat_type = NATType.OPEN
            else:
                # 简化判断：有公网地址但不同 = 有 NAT
                nat_type = NATType.UNKNOWN  # 需要进一步测试区分

            logger.debug(
                f"NAT 检测: type={nat_type.value}, "
                f"public={public_addr}, local={local_addr}"
            )
            return nat_type, public_addr

        except Exception as e:
            logger.warning(f"NAT 检测失败: {e}")
            return NATType.UNKNOWN, None

    @staticmethod
    async def _stun_request(
        server: NetworkAddress,
        local_port: int = 0,
        timeout: float = 5.0,
    ) -> Optional[NetworkAddress]:
        """发送 STUN Binding Request"""
        loop = asyncio.get_event_loop()

        # STUN Binding Request (RFC 5389)
        msg_type = struct.pack("!H", 0x0001)            # Binding Request
        msg_length = struct.pack("!H", 0)               # No attributes
        magic = struct.pack("!I", NATDetector.MAGIC_COOKIE)
        transaction_id = os.urandom(12)
        request = msg_type + msg_length + magic + transaction_id

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)

        try:
            if local_port:
                sock.bind(("0.0.0.0", local_port))
            sock.sendto(request, server.to_tuple())

            response, addr = await loop.run_in_executor(None, sock.recvfrom, 2048)

            # 解析 XOR-MAPPED-ADDRESS
            if len(response) >= 20:
                # 跳过 header，查找 XOR-MAPPED-ADDRESS (0x0020)
                pos = 20
                while pos + 4 <= len(response):
                    attr_type = struct.unpack("!H", response[pos : pos + 2])[0]
                    attr_len = struct.unpack("!H", response[pos + 2 : pos + 4])[0]
                    if attr_type == 0x0020 and attr_len >= 8:  # XOR-MAPPED-ADDRESS
                        family = struct.unpack("!H", response[pos + 5 : pos + 7])[0]
                        if family == 0x01:  # IPv4
                            xor_port = struct.unpack("!H", response[pos + 6 : pos + 8])[0]
                            xor_ip = struct.unpack("!I", response[pos + 8 : pos + 12])[0]
                            port = xor_port ^ (NATDetector.MAGIC_COOKIE >> 16)
                            ip_int = xor_ip ^ NATDetector.MAGIC_COOKIE
                            ip = ".".join(str((ip_int >> (8 * i)) & 0xFF) for i in range(3, -1, -1))
                            return NetworkAddress(host=ip, port=port)
                    pos += 4 + attr_len
            return None
        finally:
            sock.close()

    @staticmethod
    def _get_local_address(remote_host: str) -> Optional[Tuple[str, int]]:
        """获取本地网络地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((remote_host, 1))
            addr = s.getsockname()
            s.close()
            return addr
        except Exception:
            return None


# ============================================================================
# NAT 穿透连接器
# ============================================================================

class NATTraversalEngine:
    """
    NAT 穿透引擎 —— 策略模式：DIRECT → STUN → TURN → RELAY
    """

    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.config = config or ConnectionConfig()
        self.detector = NATDetector()

    async def establish_connection(
        self,
        local_info: PeerInfo,
        remote_info: PeerInfo,
    ) -> Tuple[bool, str]:
        """
        建立与远程节点的连接

        策略链（按优先级）：
        1. DIRECT  — 双方均有公网 IP / 同局域网
        2. STUN    — UDP 打洞
        3. TURN    — TURN 中继
        4. RELAY   — 应用层中继

        Returns:
            (是否成功, 连接类型)
        """
        # 1. 尝试直连
        if remote_info.local_addr and self._can_direct_connect(local_info, remote_info):
            return True, ConnectionType.DIRECT.value

        # 2. 检测自己的 NAT 类型
        nat_type, public_addr = await self.detector.detect(
            self.config.stun_servers[0],
            timeout=self.config.connect_timeout,
        )
        local_info.nat_type = nat_type
        local_info.public_addr = public_addr

        # 3. 尝试 STUN 打洞
        if nat_type not in (NATType.SYMMETRIC, NATType.UNKNOWN):
            if remote_info.public_addr:
                result = await self._try_stun_hole_punch(local_info, remote_info)
                if result:
                    return True, ConnectionType.STUN_HOLE.value

        # 4. 尝试 TURN 中继
        if self.config.turn_servers:
            result = await self._try_turn_relay(local_info, remote_info)
            if result:
                return True, ConnectionType.TURN_RELAY.value

        # 5. 降级到应用层中继
        if self.config.relay_hosts:
            logger.info(f"降级到中继连接: peer={remote_info.identity.short_id}")
            return True, ConnectionType.RELAY.value

        return False, ConnectionType.OFFLINE.value

    @staticmethod
    def _can_direct_connect(local: PeerInfo, remote: PeerInfo) -> bool:
        """判断是否可直连"""
        # 同网段（简单判断）
        if local.local_addr and remote.local_addr:
            local_ip = local.local_addr.host.split(".")
            remote_ip = remote.local_addr.host.split(".")
            if len(local_ip) == 4 and len(remote_ip) == 4:
                if local_ip[:3] == remote_ip[:3]:  # 同 C 段
                    return True
        # 公网 IP
        if remote.nat_type == NATType.OPEN:
            return True
        return False

    async def _try_stun_hole_punch(
        self, local: PeerInfo, remote: PeerInfo
    ) -> bool:
        """尝试 STUN 打洞"""
        try:
            logger.debug(f"尝试 STUN 打洞: local={local.identity.short_id}, remote={remote.identity.short_id}")
            # 简化实现：假设已有对方的公网地址
            if remote.public_addr:
                # 向对方公网地址发送心跳包（触发 NAT 映射）
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(self.config.connect_timeout)
                sock.sendto(b"PING", remote.public_addr.to_tuple())
                sock.close()
                return True
        except Exception as e:
            logger.debug(f"STUN 打洞失败: {e}")
        return False

    async def _try_turn_relay(
        self, local: PeerInfo, remote: PeerInfo
    ) -> bool:
        """尝试 TURN 中继"""
        # TURN 协议较复杂，这里提供占位实现
        logger.debug(f"TURN 中继暂未实现，降级到应用层中继")
        return False


__all__ = [
    "CryptoSession",
    "NATDetector",
    "NATTraversalEngine",
]
