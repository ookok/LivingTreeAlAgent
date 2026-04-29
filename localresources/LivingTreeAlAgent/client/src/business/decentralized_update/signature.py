# signature.py — 社区共识签名验证

"""
社区共识签名验证
================

核心理念：更新包验证不依赖中心服务器，而是通过社区共识实现。

验证机制：
1. 开发者用私钥签名初始版本
2. 高信誉节点验证后添加"背书签名"
3. 新节点需要收集 N 个可信签名才能更新
4. 签名链可追溯，防止恶意更新

信誉系统设计：
- 基础分：在线时长、网络稳定性
- 贡献分：成功分发次数、带宽贡献
- 违规分：传播错误版本、恶意行为
- 衰减机制：信誉随时间自然衰减
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum

from .models import (
    NodeInfo, VersionInfo, EndorsementSignature,
    SignatureType, ReputationLevel, generate_node_id
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SignatureConfig:
    """签名验证配置"""
    min_endorsements: int = 3              # 最少背书数量
    developer_key_id: str = ""            # 开发者公钥 ID
    endorsement_expiry: int = 86400 * 7   # 背书有效期 (7天)
    trust_threshold: float = 0.6          # 信任阈值
    signature_window: int = 86400 * 14   # 签名窗口 (14天)
    decay_rate: float = 0.01              # 每日衰减率


# ═══════════════════════════════════════════════════════════════════════════════
# 签名状态
# ═══════════════════════════════════════════════════════════════════════════════


class VerificationStatus(Enum):
    """验证状态"""
    UNVERIFIED = "unverified"           # 未验证
    VERIFYING = "verifying"             # 验证中
    VERIFIED = "verified"               # 已验证
    EXPIRED = "expired"                # 已过期
    INVALID = "invalid"                  # 无效
    REJECTED = "rejected"              # 拒绝


@dataclass
class SignatureChain:
    """签名链"""
    version: str                              # 版本号
    developer_signature: Optional[EndorsementSignature] = None  # 开发者签名
    endorsements: List[EndorsementSignature] = field(default_factory=list)  # 背书列表
    merkle_root: str = ""                     # Merkle 树根
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verified_at: float = 0                     # 验证时间
    created_at: float = 0

    def __post_init__(self):
        if self.created_at == 0:
            self.created_at = time.time()

    @property
    def is_valid(self) -> bool:
        """签名链是否有效"""
        if self.verification_status != VerificationStatus.VERIFIED:
            return False
        if self.developer_signature is None:
            return False
        if time.time() - self.created_at > SignatureConfig().signature_window:
            return False
        return True

    @property
    def trust_score(self) -> float:
        """计算信任分数"""
        if not self.developer_signature:
            return 0

        # 开发者签名权重
        score = 0.4

        # 背书签名权重
        if self.endorsements:
            endorsement_score = min(0.5, len(self.endorsements) * 0.1)

            # 考虑背书者信誉
            weighted_endorsements = 0
            total_weight = 0
            for end in self.endorsements:
                # 简化处理：假设每个背书者信誉分为 50-100
                weight = 50 / 100
                weighted_endorsements += weight
                total_weight += weight

            if total_weight > 0:
                endorsement_score *= (weighted_endorsements / total_weight)

            score += endorsement_score

        return min(1.0, score)


# ═══════════════════════════════════════════════════════════════════════════════
# 签名验证器
# ═══════════════════════════════════════════════════════════════════════════════


class SignatureVerifier:
    """
    签名验证器

    验证开发者签名和社区背书
    """

    def __init__(self, config: SignatureConfig = None):
        self.config = config or SignatureConfig()
        self.chains: Dict[str, SignatureChain] = {}  # version -> chain
        self._developer_keys: Dict[str, str] = {}  # key_id -> public_key
        self._lock = asyncio.Lock()

    def register_developer_key(self, key_id: str, public_key: str):
        """注册开发者公钥"""
        self._developer_keys[key_id] = public_key
        logger.info(f"Registered developer key: {key_id}")

    async def verify_developer_signature(
        self,
        version_info: VersionInfo,
        signature: str
    ) -> bool:
        """
        验证开发者签名

        Args:
            version_info: 版本信息
            signature: 签名数据

        Returns:
            True 如果签名有效
        """
        if not self.config.developer_key_id:
            logger.warning("No developer key configured")
            return False

        public_key = self._developer_keys.get(self.config.developer_key_id)
        if not public_key:
            logger.error(f"Developer key not found: {self.config.developer_key_id}")
            return False

        # 计算版本信息的哈希
        content_hash = self._hash_version_info(version_info)

        # 验证签名
        try:
            # 简化实现：使用 HMAC 代替 ECDSA
            expected_sig = hmac.new(
                public_key.encode(),
                content_hash.encode(),
                hashlib.sha256
            ).hexdigest()

            is_valid = hmac.compare_digest(signature, expected_sig)

            logger.info(f"Developer signature verified: {is_valid}")
            return is_valid

        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    async def add_endorsement(
        self,
        version: str,
        endorser: NodeInfo,
        signature: str
    ) -> bool:
        """
        添加背书签名

        Args:
            version: 版本号
            endorser: 背书节点
            signature: 背书签名

        Returns:
            True 如果添加成功
        """
        # 检查背书者信誉
        if endorser.reputation_level.value < ReputationLevel.TRUSTED.value:
            logger.warning(f"Endorser {endorser.node_id[:8]} not trusted enough")
            return False

        async with self._lock:
            if version not in self.chains:
                self.chains[version] = SignatureChain(version=version)

            chain = self.chains[version]

            # 检查是否已存在该节点的背书
            for end in chain.endorsements:
                if end.signer_id == endorser.node_id:
                    logger.debug(f"Endorsement already exists from {endorser.node_id[:8]}")
                    return False

            # 创建背书签名
            endorsement = EndorsementSignature(
                signer_id=endorser.node_id,
                signature_type=SignatureType.ENDORSEMENT,
                version=version,
                signature=signature,
                timestamp=time.time()
            )

            chain.endorsements.append(endorsement)

            logger.info(
                f"Endorsement added for {version} by {endorser.node_id[:8]}, "
                f"total endorsements: {len(chain.endorsements)}"
            )

            return True

    async def verify_chain(self, version: str) -> VerificationStatus:
        """
        验证签名链

        Args:
            version: 版本号

        Returns:
            验证状态
        """
        async with self._lock:
            if version not in self.chains:
                return VerificationStatus.UNVERIFIED

            chain = self.chains[version]

            # 检查过期
            if time.time() - chain.created_at > self.config.signature_window:
                chain.verification_status = VerificationStatus.EXPIRED
                return VerificationStatus.EXPIRED

            # 检查开发者签名
            if chain.developer_signature is None:
                chain.verification_status = VerificationStatus.UNVERIFIED
                return VerificationStatus.UNVERIFIED

            # 检查背书数量
            if len(chain.endorsements) < self.config.min_endorsements:
                chain.verification_status = VerificationStatus.VERIFYING
                return VerificationStatus.VERIFYING

            # 所有检查通过
            chain.verification_status = VerificationStatus.VERIFIED
            chain.verified_at = time.time()

            logger.info(f"Signature chain verified for {version}")
            return VerificationStatus.VERIFIED

    async def get_chain_status(self, version: str) -> Dict[str, Any]:
        """获取签名链状态"""
        if version not in self.chains:
            return {
                'version': version,
                'status': VerificationStatus.UNVERIFIED.value,
                'has_developer_sig': False,
                'endorsements': 0,
                'trust_score': 0
            }

        chain = self.chains[version]
        return {
            'version': version,
            'status': chain.verification_status.value,
            'has_developer_sig': chain.developer_signature is not None,
            'endorsements': len(chain.endorsements),
            'min_endorsements': self.config.min_endorsements,
            'trust_score': chain.trust_score,
            'is_valid': chain.is_valid,
            'created_at': chain.created_at,
            'verified_at': chain.verified_at
        }

    def _hash_version_info(self, version_info: VersionInfo) -> str:
        """计算版本信息的哈希"""
        content = f"{version_info.version}:{version_info.checksum}:{version_info.version_code}"
        return hashlib.sha256(content.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# 背书收集器
# ═══════════════════════════════════════════════════════════════════════════════


class EndorsementCollector:
    """
    背书收集器

    收集社区节点的背书签名
    """

    def __init__(self, verifier: SignatureVerifier, config: SignatureConfig = None):
        self.verifier = verifier
        self.config = config or SignatureConfig()
        self.pending_endorsements: Dict[str, asyncio.Event] = {}
        self.collected_endorsements: Dict[str, List[EndorsementSignature]] = {}

    async def request_endorsement(
        self,
        version: str,
        endorser: NodeInfo
    ) -> bool:
        """
        请求背书

        Args:
            version: 版本号
            endorser: 背书节点

        Returns:
            True 如果获得背书
        """
        # 创建待处理事件
        if version not in self.pending_endorsements:
            self.pending_endorsements[version] = asyncio.Event()

        # 模拟背书验证过程
        try:
            # 实际实现中会：
            # 1. 下载完整包
            # 2. 验证功能正常
            # 3. 生成背书签名

            # 简化处理：直接添加背书
            signature = hashlib.sha256(
                f"{version}:{endorser.node_id}".encode()
            ).hexdigest()

            success = await self.verifier.add_endorsement(version, endorser, signature)

            if success:
                # 通知等待的协程
                if version in self.pending_endorsements:
                    self.pending_endorsements[version].set()

            return success

        except Exception as e:
            logger.error(f"Endorsement request failed: {e}")
            return False

    async def wait_for_endorsements(
        self,
        version: str,
        required_count: int = None,
        timeout: float = 300
    ) -> List[EndorsementSignature]:
        """
        等待获得足够的背书

        Args:
            version: 版本号
            required_count: 需要的背书数量
            timeout: 超时时间

        Returns:
            获得的背书列表
        """
        required_count = required_count or self.config.min_endorsements

        start_time = time.time()

        while time.time() - start_time < timeout:
            status = await self.verifier.get_chain_status(version)

            if status['endorsements'] >= required_count:
                chain = self.verifier.chains.get(version)
                if chain:
                    return chain.endorsements

            # 等待一段时间后重试
            await asyncio.sleep(5)

        logger.warning(f"Timeout waiting for endorsements: {version}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# 签名服务
# ═══════════════════════════════════════════════════════════════════════════════


class SignatureService:
    """
    签名服务

    提供签名和验证的统一接口
    """

    def __init__(self, config: SignatureConfig = None):
        self.config = config or SignatureConfig()
        self.verifier = SignatureVerifier(config)
        self.collector = EndorsementCollector(self.verifier, config)
        self._private_key: Optional[str] = None  # 开发者私钥

    def set_developer_key(self, private_key: str, public_key: str, key_id: str):
        """设置开发者密钥"""
        self._private_key = private_key
        self.verifier.config.developer_key_id = key_id
        self.verifier.register_developer_key(key_id, public_key)
        logger.info(f"Developer keys configured: {key_id}")

    async def sign_version(
        self,
        version_info: VersionInfo
    ) -> Optional[str]:
        """
        签名版本

        Args:
            version_info: 版本信息

        Returns:
            签名数据
        """
        if not self._private_key:
            logger.error("No private key configured for signing")
            return None

        try:
            # 计算内容哈希
            content = f"{version_info.version}:{version_info.checksum}:{version_info.version_code}"
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            # 生成签名
            signature = hmac.new(
                self._private_key.encode(),
                content_hash.encode(),
                hashlib.sha256
            ).hexdigest()

            # 创建签名链
            sig_chain = SignatureChain(
                version=version_info.version,
                developer_signature=EndorsementSignature(
                    signer_id="developer",
                    signature_type=SignatureType.DEVELOPER,
                    version=version_info.version,
                    signature=signature,
                    timestamp=time.time()
                )
            )
            self.verifier.chains[version_info.version] = sig_chain

            logger.info(f"Version {version_info.version} signed by developer")
            return signature

        except Exception as e:
            logger.error(f"Failed to sign version: {e}")
            return None

    async def verify_version(
        self,
        version_info: VersionInfo
    ) -> Tuple[bool, float]:
        """
        验证版本

        Args:
            version_info: 版本信息

        Returns:
            (is_valid, trust_score)
        """
        chain = self.verifier.chains.get(version_info.version)
        if not chain:
            return False, 0

        status = await self.verifier.verify_chain(version_info.version)

        if status == VerificationStatus.VERIFIED:
            return True, chain.trust_score

        return False, chain.trust_score if chain else 0

    async def endorse_version(
        self,
        version: str,
        endorser: NodeInfo
    ) -> bool:
        """背书版本"""
        return await self.collector.request_endorsement(version, endorser)

    async def get_verification_status(self, version: str) -> Dict[str, Any]:
        """获取验证状态"""
        return await self.verifier.get_chain_status(version)


# ═══════════════════════════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════════════════════════


_signature_service: Optional[SignatureService] = None


def get_signature_service() -> SignatureService:
    """获取全局签名服务"""
    global _signature_service
    if _signature_service is None:
        _signature_service = SignatureService()
    return _signature_service
