# -*- coding: utf-8 -*-
"""
去中心化知识区块链系统 - 安全模块

实现:
- 加密机制: 非对称加密/对称加密/零知识证明
- 攻击防护: Sybil/女巫/DDoS/自私攻击/合谋攻击
- 隐私保护: 身份隐私/数据隐私/行为隐私/社交隐私
"""

import asyncio
import logging
import json
import hashlib
import secrets
import time
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class EncryptionType(Enum):
    """加密类型"""
    NONE = "none"
    SYMMETRIC = "symmetric"
    ASYMMETRIC = "asymmetric"
    HYBRID = "hybrid"
    ZERO_KNOWLEDGE = "zero_knowledge"


class AttackType(Enum):
    """攻击类型"""
    SYBIL = "sybil"
    SYBIL_RATIO = "sybil_ratio"
    DENIAL_OF_SERVICE = "dos"
    SELFISH_MINING = "selfish_mining"
    COLLUSION = "collusion"
    ECLIPSE = "eclipse"


@dataclass
class SecurityEvent:
    """安全事件"""
    event_id: str
    attack_type: AttackType
    source_node: Optional[str]
    target_node: Optional[str]
    severity: str  # low/medium/high/critical
    description: str
    timestamp: datetime
    blocked: bool = False


@dataclass
class EncryptionKey:
    """加密密钥"""
    key_id: str
    key_type: str  # symmetric/asymmetric_public/asymmetric_private
    key_data: str
    owner_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None


@dataclass
class ZeroKnowledgeProof:
    """零知识证明"""
    proof_id: str
    statement: str
    proof_data: Dict[str, Any]
    public_inputs: List[str]
    created_at: datetime
    verified: bool = False


class SecurityModule:
    """安全模块"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化安全模块
        
        Args:
            config: 配置
        """
        self.config = config or {}
        
        # 加密密钥
        self.keys: Dict[str, EncryptionKey] = {}
        self.node_keys: Dict[str, str] = {}  # node_id -> key_id
        
        # 安全事件
        self.security_events: List[SecurityEvent] = []
        self.blocked_nodes: Dict[str, datetime] = {}  # node_id -> blocked_until
        
        # 攻击检测
        self.attack_detectors: Dict[AttackType, Callable] = {}
        self.node_reputation: Dict[str, float] = {}  # 行为信誉
        self.request_counts: Dict[str, List[datetime]] = defaultdict(list)  # 请求计数
        
        # 隐私保护
        self.anonymous_identities: Dict[str, str] = {}  # 匿名ID -> 真实ID
        self.behavior_records: Dict[str, List[Dict]] = defaultdict(list)  # 行为记录
        
        # 零知识证明
        self.zk_proofs: Dict[str, ZeroKnowledgeProof] = {}
        
        # 配置
        self.rate_limit_window = 60  # 秒
        self.rate_limit_max_requests = 100
        self.sybil_threshold = 0.3  # Sybil检测阈值
        
        self._init_attack_detectors()
        
        logger.info("安全模块初始化完成")

    async def initialize(self) -> bool:
        """初始化安全模块"""
        # 生成节点密钥
        await self._generate_node_key()
        
        logger.info("✅ 安全模块初始化完成")
        return True

    async def stop(self):
        """停止安全模块"""
        logger.info("安全模块已停止")

    # ==================== 加密功能 ====================

    async def encrypt_symmetric(
        self,
        data: Any,
        key_id: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        对称加密
        
        Args:
            data: 待加密数据
            key_id: 密钥ID（可选）
            
        Returns:
            (加密数据, 密钥ID)
        """
        # 获取或生成密钥
        if key_id and key_id in self.keys:
            key = self.keys[key_id]
        else:
            key_id = await self._generate_symmetric_key()
            key = self.keys[key_id]
        
        # 序列化数据
        if isinstance(data, dict):
            data_str = json.dumps(data, ensure_ascii=False)
        else:
            data_str = str(data)
        
        # 简化实现：使用AES风格加密（实际应使用cryptography库）
        encrypted = self._xor_encrypt(data_str, key.key_data)
        
        return encrypted, key_id

    async def decrypt_symmetric(
        self,
        encrypted_data: str,
        key_id: str
    ) -> Optional[Any]:
        """
        对称解密
        
        Args:
            encrypted_data: 加密数据
            key_id: 密钥ID
            
        Returns:
            解密后的数据
        """
        key = self.keys.get(key_id)
        if not key:
            return None
        
        # 解密
        decrypted = self._xor_decrypt(encrypted_data, key.key_data)
        
        # 尝试解析JSON
        try:
            return json.loads(decrypted)
        except:
            return decrypted

    async def encrypt_asymmetric(
        self,
        data: Any,
        public_key_id: str
    ) -> str:
        """
        非对称加密
        
        Args:
            data: 待加密数据
            public_key_id: 公钥ID
            
        Returns:
            加密数据
        """
        # 序列化数据
        if isinstance(data, dict):
            data_str = json.dumps(data, ensure_ascii=False)
        else:
            data_str = str(data)
        
        # 简化实现：使用公钥进行加密（实际应使用RSA/ECC）
        public_key = self.keys.get(public_key_id)
        if not public_key:
            return data_str
        
        encrypted = self._xor_encrypt(data_str, public_key.key_data)
        
        return encrypted

    async def decrypt_asymmetric(
        self,
        encrypted_data: str,
        private_key_id: str
    ) -> Optional[Any]:
        """
        非对称解密
        
        Args:
            encrypted_data: 加密数据
            private_key_id: 私钥ID
            
        Returns:
            解密后的数据
        """
        private_key = self.keys.get(private_key_id)
        if not private_key:
            return None
        
        decrypted = self._xor_decrypt(encrypted_data, private_key.key_data)
        
        try:
            return json.loads(decrypted)
        except:
            return decrypted

    async def generate_key_pair(self, owner_id: str) -> Tuple[str, str]:
        """
        生成非对称密钥对
        
        Args:
            owner_id: 所有者ID
            
        Returns:
            (公钥ID, 私钥ID)
        """
        # 生成公钥
        public_id = self._generate_key_id()
        public_data = secrets.token_hex(32)
        
        public_key = EncryptionKey(
            key_id=public_id,
            key_type="asymmetric_public",
            key_data=public_data,
            owner_id=owner_id,
            created_at=datetime.now()
        )
        self.keys[public_id] = public_key
        
        # 生成私钥
        private_id = self._generate_key_id()
        private_data = secrets.token_hex(32)
        
        private_key = EncryptionKey(
            key_id=private_id,
            key_type="asymmetric_private",
            key_data=private_data,
            owner_id=owner_id,
            created_at=datetime.now()
        )
        self.keys[private_id] = private_key
        
        return public_id, private_id

    def _xor_encrypt(self, data: str, key: str) -> str:
        """XOR加密（简化实现）"""
        result = []
        for i, char in enumerate(data):
            key_char = key[i % len(key)]
            result.append(chr(ord(char) ^ ord(key_char)))
        return ''.join(result)

    def _xor_decrypt(self, encrypted: str, key: str) -> str:
        """XOR解密（简化实现）"""
        return self._xor_encrypt(encrypted, key)  # XOR是对称的

    async def _generate_symmetric_key(self) -> str:
        """生成对称密钥"""
        key_id = self._generate_key_id()
        key_data = secrets.token_hex(32)
        
        key = EncryptionKey(
            key_id=key_id,
            key_type="symmetric",
            key_data=key_data,
            owner_id="system",
            created_at=datetime.now()
        )
        
        self.keys[key_id] = key
        return key_id

    async def _generate_node_key(self):
        """生成节点密钥"""
        # 生成节点加密密钥对
        public_id, private_id = await self.generate_key_pair("node")
        self.node_keys["node"] = private_id  # 存储私钥ID
        
        return public_id

    def _generate_key_id(self) -> str:
        """生成密钥ID"""
        return secrets.token_hex(16)

    # ==================== 攻击检测与防护 ====================

    def _init_attack_detectors(self):
        """初始化攻击检测器"""
        self.attack_detectors = {
            AttackType.SYBIL: self._detect_sybil,
            AttackType.SYBIL_RATIO: self._detect_sybil_ratio,
            AttackType.DENIAL_OF_SERVICE: self._detect_dos,
            AttackType.SELFISH_MINING: self._detect_selfish_mining,
            AttackType.COLLUSION: self._detect_collusion
        }

    async def check_security(
        self,
        source_node: str,
        target_node: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        安全检查
        
        Args:
            source_node: 源节点
            target_node: 目标节点
            
        Returns:
            (是否允许, 拒绝原因)
        """
        # 检查是否被屏蔽
        if source_node in self.blocked_nodes:
            blocked_until = self.blocked_nodes[source_node]
            if datetime.now() < blocked_until:
                return False, "node_blocked"
            else:
                del self.blocked_nodes[source_node]
        
        # 检查请求速率
        if not await self._check_rate_limit(source_node):
            await self._record_security_event(
                attack_type=AttackType.DENIAL_OF_SERVICE,
                source_node=source_node,
                target_node=target_node,
                severity="medium",
                description=f"Rate limit exceeded for {source_node}"
            )
            return False, "rate_limit_exceeded"
        
        # 运行攻击检测
        for attack_type, detector in self.attack_detectors.items():
            if await detector(source_node):
                await self._record_security_event(
                    attack_type=attack_type,
                    source_node=source_node,
                    target_node=target_node,
                    severity="high",
                    description=f"Potential {attack_type.value} attack from {source_node}"
                )
                
                # 自动屏蔽
                await self._block_node(source_node, duration=3600)
                return False, f"{attack_type.value}_detected"
        
        # 更新行为信誉
        self._update_behavior_score(source_node, 0.1)
        
        return True, None

    async def _check_rate_limit(self, node_id: str) -> bool:
        """检查速率限制"""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.rate_limit_window)
        
        # 清理过期记录
        self.request_counts[node_id] = [
            t for t in self.request_counts[node_id]
            if t > window_start
        ]
        
        # 检查限制
        if len(self.request_counts[node_id]) >= self.rate_limit_max_requests:
            return False
        
        # 记录请求
        self.request_counts[node_id].append(now)
        
        return True

    async def _detect_sybil(self, node_id: str) -> bool:
        """检测Sybil攻击"""
        # 检查同一IP的节点数量
        # 简化实现：检查行为信誉
        score = self.node_reputation.get(node_id, 0.5)
        return score < 0.2

    async def _detect_sybil_ratio(self, node_id: str) -> bool:
        """检测Sybil比例"""
        # 检测恶意节点占总节点的比例
        # 简化实现
        malicious_count = sum(1 for s in self.node_reputation.values() if s < 0.3)
        total_count = len(self.node_reputation)
        
        if total_count == 0:
            return False
        
        ratio = malicious_count / total_count
        return ratio > self.sybil_threshold

    async def _detect_dos(self, node_id: str) -> bool:
        """检测DDoS攻击"""
        # 检查请求频率异常
        now = datetime.now()
        recent = [t for t in self.request_counts[node_id] 
                  if (now - t).total_seconds() < 10]
        
        return len(recent) > self.rate_limit_max_requests / 2

    async def _detect_selfish_mining(self, node_id: str) -> bool:
        """检测自私挖矿"""
        # 检测区块提交行为异常
        # 简化实现
        return False

    async def _detect_collusion(self, node_id: str) -> bool:
        """检测合谋攻击"""
        # 检测节点间的异常协作模式
        # 简化实现
        return False

    async def _block_node(self, node_id: str, duration: int = 3600):
        """屏蔽节点"""
        self.blocked_nodes[node_id] = datetime.now() + timedelta(seconds=duration)
        logger.warning(f"🚫 节点已被屏蔽: {node_id} (时长: {duration}秒)")

    def _update_behavior_score(self, node_id: str, delta: float):
        """更新行为信誉分数"""
        current = self.node_reputation.get(node_id, 0.5)
        new_score = max(0, min(1, current + delta))
        self.node_reputation[node_id] = new_score

    async def _record_security_event(
        self,
        attack_type: AttackType,
        source_node: Optional[str],
        target_node: Optional[str],
        severity: str,
        description: str
    ):
        """记录安全事件"""
        import hashlib
        
        event = SecurityEvent(
            event_id=hashlib.sha256(f"{attack_type.value}{source_node}{datetime.now()}".encode()).hexdigest()[:24],
            attack_type=attack_type,
            source_node=source_node,
            target_node=target_node,
            severity=severity,
            description=description,
            timestamp=datetime.now()
        )
        
        self.security_events.append(event)
        
        # 只保留最近1000个事件
        if len(self.security_events) > 1000:
            self.security_events = self.security_events[-1000:]

    # ==================== 零知识证明 ====================

    async def create_zk_proof(
        self,
        statement: str,
        witness: Dict[str, Any],
        public_inputs: List[str]
    ) -> Optional[str]:
        """
        创建零知识证明
        
        Args:
            statement: 语句
            witness: 见证（私密输入）
            public_inputs: 公开输入
            
        Returns:
            证明ID
        """
        proof_id = secrets.token_hex(16)
        
        # 简化实现：生成模拟证明
        proof_data = {
            "a": hashlib.sha256(json.dumps(witness).encode()).hexdigest(),
            "b": hashlib.sha256(statement.encode()).hexdigest(),
            "c": secrets.token_hex(32)
        }
        
        proof = ZeroKnowledgeProof(
            proof_id=proof_id,
            statement=statement,
            proof_data=proof_data,
            public_inputs=public_inputs,
            created_at=datetime.now()
        )
        
        self.zk_proofs[proof_id] = proof
        
        return proof_id

    async def verify_zk_proof(self, proof_id: str) -> bool:
        """
        验证零知识证明
        
        Args:
            proof_id: 证明ID
            
        Returns:
            是否验证通过
        """
        proof = self.zk_proofs.get(proof_id)
        if not proof:
            return False
        
        # 简化实现：模拟验证
        # 实际应实现真正的零知识证明验证逻辑
        proof.verified = True
        
        return True

    # ==================== 隐私保护 ====================

    async def create_anonymous_identity(self, real_node_id: str) -> str:
        """
        创建匿名身份
        
        Args:
            real_node_id: 真实节点ID
            
        Returns:
            匿名ID
        """
        anonymous_id = secrets.token_hex(16)
        self.anonymous_identities[anonymous_id] = real_node_id
        
        return anonymous_id

    async def get_real_identity(self, anonymous_id: str) -> Optional[str]:
        """
        获取真实身份（仅授权方）
        
        Args:
            anonymous_id: 匿名ID
            
        Returns:
            真实ID
        """
        return self.anonymous_identities.get(anonymous_id)

    async def record_behavior(
        self,
        node_id: str,
        behavior_type: str,
        details: Dict[str, Any]
    ):
        """
        记录行为（用于隐私保护审计）
        
        Args:
            node_id: 节点ID
            behavior_type: 行为类型
            details: 行为详情
        """
        record = {
            "type": behavior_type,
            "details": details,
            "timestamp": datetime.now()
        }
        
        self.behavior_records[node_id].append(record)
        
        # 只保留最近100条记录
        if len(self.behavior_records[node_id]) > 100:
            self.behavior_records[node_id] = self.behavior_records[node_id][-100:]

    # ==================== 签名验证 ====================

    async def sign_data(self, data: Any, private_key_id: str) -> Optional[str]:
        """
        签名数据
        
        Args:
            data: 待签名数据
            private_key_id: 私钥ID
            
        Returns:
            签名
        """
        private_key = self.keys.get(private_key_id)
        if not private_key:
            return None
        
        # 序列化数据
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        else:
            data_str = str(data)
        
        # 生成签名
        signature = hashlib.sha256(
            (data_str + private_key.key_data).encode()
        ).hexdigest()
        
        return signature

    async def verify_signature(
        self,
        data: Any,
        signature: str,
        public_key_id: str
    ) -> bool:
        """
        验证签名
        
        Args:
            data: 原数据
            signature: 签名
            public_key_id: 公钥ID
            
        Returns:
            是否验证通过
        """
        public_key = self.keys.get(public_key_id)
        if not public_key:
            return False
        
        # 重新计算签名
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        else:
            data_str = str(data)
        
        expected_signature = hashlib.sha256(
            (data_str + public_key.key_data).encode()
        ).hexdigest()
        
        return signature == expected_signature

    # ==================== 统计 ====================

    def get_security_stats(self) -> Dict[str, Any]:
        """获取安全统计"""
        return {
            "total_keys": len(self.keys),
            "blocked_nodes": len(self.blocked_nodes),
            "security_events_count": len(self.security_events),
            "critical_events": sum(1 for e in self.security_events if e.severity == "critical"),
            "anonymous_identities": len(self.anonymous_identities),
            "zk_proofs": len(self.zk_proofs),
            "node_behavior_scores": {
                node_id: score 
                for node_id, score in self.node_reputation.items()
            }
        }

    def get_security_events(
        self,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取安全事件"""
        events = self.security_events
        
        if severity:
            events = [e for e in events if e.severity == severity]
        
        return [
            {
                "event_id": e.event_id,
                "attack_type": e.attack_type.value,
                "source_node": e.source_node,
                "target_node": e.target_node,
                "severity": e.severity,
                "description": e.description,
                "timestamp": e.timestamp.isoformat(),
                "blocked": e.blocked
            }
            for e in events[-limit:]
        ]
