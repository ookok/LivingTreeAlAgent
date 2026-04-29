# -*- coding: utf-8 -*-
"""
去中心化知识区块链系统 - 数据模型

定义所有核心数据结构
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import hashlib
import json


class NodeType(Enum):
    """节点类型"""
    FULL = "full"           # 全节点：存储完整区块链
    LIGHT = "light"          # 轻节点：存储部分数据
    MOBILE = "mobile"        # 移动节点：有限存储
    VALIDATOR = "validator"  # 验证节点：参与共识


class KnowledgeType(Enum):
    """知识类型"""
    CONCEPT = "concept"      # 概念知识
    METHOD = "method"        # 方法知识
    CASE = "case"           # 案例知识
    DATA = "data"            # 数据知识


class TransactionType(Enum):
    """交易类型"""
    KNOWLEDGE_CREATE = "knowledge_create"
    KNOWLEDGE_UPDATE = "knowledge_update"
    KNOWLEDGE_VERIFY = "knowledge_verify"
    KNOWLEDGE_LEARN = "knowledge_learn"
    KNOWLEDGE_SPREAD = "knowledge_spread"
    TOKEN_TRANSFER = "token_transfer"
    CONTRACT_DEPLOY = "contract_deploy"
    CONTRACT_EXECUTE = "contract_execute"
    DIALOGUE = "dialogue"
    GOVERNANCE = "governance"


class ContractType(Enum):
    """智能合约类型"""
    KNOWLEDGE_CREATE = "knowledge_create"
    KNOWLEDGE_VERIFY = "knowledge_verify"
    KNOWLEDGE_SPREAD = "knowledge_spread"
    KNOWLEDGE_LEARN = "knowledge_learn"
    COPYRIGHT = "copyright"
    AUTHORIZATION = "authorization"
    COLLABORATION = "collaboration"
    TEACHING = "teaching"
    GOVERNANCE = "governance"


class DialogueType(Enum):
    """对话类型"""
    KNOWLEDGE_QUERY = "knowledge_query"
    KNOWLEDGE_DEBATE = "knowledge_debate"
    KNOWLEDGE_COLLABORATE = "knowledge_collaborate"
    LEARNING_EXCHANGE = "learning_exchange"
    TEACHING = "teaching"


class ReputationDimension(Enum):
    """信誉维度"""
    KNOWLEDGE = "knowledge"      # 知识信誉
    VERIFICATION = "verification"  # 验证信誉
    SPREAD = "spread"            # 传播信誉
    LEARNING = "learning"        # 学习信誉
    TEACHING = "teaching"        # 教学信誉
    COLLABORATION = "collaboration"  # 协作信誉


# ==================== 知识单元 ====================

@dataclass
class VerificationInfo:
    """验证信息"""
    verification_count: int = 0
    pass_count: int = 0
    pass_rate: float = 0.0
    last_verification_time: Optional[datetime] = None
    verifier_ids: List[str] = field(default_factory=list)
    verification_comments: List[str] = field(default_factory=list)

    @property
    def is_verified(self) -> bool:
        return self.verification_count >= 3 and self.pass_rate >= 0.6

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_count": self.verification_count,
            "pass_count": self.pass_count,
            "pass_rate": self.pass_rate,
            "last_verification_time": self.last_verification_time.isoformat() if self.last_verification_time else None,
            "verifier_ids": self.verifier_ids,
            "verification_comments": self.verification_comments,
            "is_verified": self.is_verified
        }


@dataclass
class ValueInfo:
    """价值信息"""
    value_score: float = 0.0
    spread_count: int = 0
    learning_count: int = 0
    reference_count: int = 0
    citation_count: int = 0
    total_incentives: float = 0.0

    def calculate_value(self) -> float:
        """计算知识价值"""
        base = 10.0
        verification_bonus = self.pass_rate * 20 if hasattr(self, 'pass_rate') else 0
        spread_bonus = min(self.spread_count * 0.5, 20)
        learning_bonus = min(self.learning_count * 0.3, 15)
        reference_bonus = min(self.reference_count * 2, 30)
        citation_bonus = min(self.citation_count * 3, 25)
        
        self.value_score = base + verification_bonus + spread_bonus + learning_bonus + reference_bonus + citation_bonus
        return self.value_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value_score": self.value_score,
            "spread_count": self.spread_count,
            "learning_count": self.learning_count,
            "reference_count": self.reference_count,
            "citation_count": self.citation_count,
            "total_incentives": self.total_incentives
        }


@dataclass
class KnowledgeMetadata:
    """知识元数据"""
    knowledge_id: str = ""
    creator_id: str = ""
    creator_signature: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    version: int = 1
    knowledge_type: str = ""
    domain_tags: List[str] = field(default_factory=list)
    language: str = "zh-CN"
    license: str = "CC BY-SA 4.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "creator_id": self.creator_id,
            "creator_signature": self.creator_signature,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "version": self.version,
            "knowledge_type": self.knowledge_type,
            "domain_tags": self.domain_tags,
            "language": self.language,
            "license": self.license
        }


@dataclass
class KnowledgeContent:
    """知识内容"""
    title: str = ""
    summary: str = ""
    content: str = ""
    references: List[str] = field(default_factory=list)
    attachments: Dict[str, Any] = field(default_factory=dict)
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "references": self.references,
            "attachments": self.attachments,
            "keywords": self.keywords
        }

    def get_content_hash(self) -> str:
        """获取内容哈希"""
        content_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()


@dataclass
class KnowledgeUnit:
    """知识单元"""
    metadata: KnowledgeMetadata
    content: KnowledgeContent
    verification_info: VerificationInfo = field(default_factory=VerificationInfo)
    value_info: ValueInfo = field(default_factory=ValueInfo)
    learning_records: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if isinstance(self.metadata, dict):
            self.metadata = KnowledgeMetadata(**self.metadata)
        if isinstance(self.content, dict):
            self.content = KnowledgeContent(**self.content)
        if isinstance(self.verification_info, dict):
            self.verification_info = VerificationInfo(**self.verification_info)
        if isinstance(self.value_info, dict):
            self.value_info = ValueInfo(**self.value_info)

    @property
    def knowledge_id(self) -> str:
        return self.metadata.knowledge_id

    @property
    def creator_id(self) -> str:
        return self.metadata.creator_id

    @property
    def is_verified(self) -> bool:
        return self.verification_info.is_verified

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "content": self.content.to_dict(),
            "verification_info": self.verification_info.to_dict(),
            "value_info": self.value_info.to_dict(),
            "learning_records": self.learning_records
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeUnit':
        return cls(
            metadata=KnowledgeMetadata(**data.get("metadata", {})),
            content=KnowledgeContent(**data.get("content", {})),
            verification_info=VerificationInfo(**data.get("verification_info", {})),
            value_info=ValueInfo(**data.get("value_info", {})),
            learning_records=data.get("learning_records", [])
        )


# ==================== 区块结构 ====================

@dataclass
class BlockHeader:
    """区块头"""
    version: int = 1
    previous_block_hash: str = ""
    knowledge_merkle_root: str = ""
    state_merkle_root: str = ""
    timestamp: Optional[datetime] = None
    difficulty_target: int = 4
    nonce: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "previous_block_hash": self.previous_block_hash,
            "knowledge_merkle_root": self.knowledge_merkle_root,
            "state_merkle_root": self.state_merkle_root,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "difficulty_target": self.difficulty_target,
            "nonce": self.nonce
        }


@dataclass
class Block:
    """区块"""
    header: BlockHeader
    transactions: List['Transaction'] = field(default_factory=list)
    validator_signatures: List[str] = field(default_factory=list)
    consensus_proof: str = ""

    def __post_init__(self):
        if isinstance(self.header, dict):
            self.header = BlockHeader(**self.header)
        if self.transactions and isinstance(self.transactions[0], dict):
            self.transactions = [Transaction(**tx) if isinstance(tx, dict) else tx for tx in self.transactions]

    @property
    def block_hash(self) -> str:
        header_str = json.dumps(self.header.to_dict(), sort_keys=True)
        return hashlib.sha256(header_str.encode()).hexdigest()

    @property
    def block_number(self) -> int:
        return self.header.version

    def to_dict(self) -> Dict[str, Any]:
        return {
            "header": self.header.to_dict(),
            "transactions": [tx.to_dict() if isinstance(tx, Transaction) else tx for tx in self.transactions],
            "validator_signatures": self.validator_signatures,
            "consensus_proof": self.consensus_proof,
            "block_hash": self.block_hash
        }


# ==================== 交易结构 ====================

@dataclass
class Transaction:
    """交易"""
    tx_id: str = ""
    tx_type: str = ""
    sender_id: str = ""
    receiver_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    signature: str = ""
    fee: float = 0.0
    nonce: int = 0

    def __post_init__(self):
        if self.timestamp and isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)

    @property
    def tx_hash(self) -> str:
        tx_str = json.dumps({
            "tx_id": self.tx_id,
            "tx_type": self.tx_type,
            "sender_id": self.sender_id,
            "data": self.data
        }, sort_keys=True)
        return hashlib.sha256(tx_str.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "tx_type": self.tx_type,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "signature": self.signature,
            "fee": self.fee,
            "nonce": self.nonce,
            "tx_hash": self.tx_hash
        }


# ==================== 节点相关 ====================

@dataclass
class NodeProfile:
    """节点配置"""
    node_id: str
    node_type: NodeType
    nickname: str = ""
    avatar: str = ""
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    interests: List[str] = field(default_factory=list)
    expertise_domains: List[str] = field(default_factory=list)
    capabilities: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value if isinstance(self.node_type, NodeType) else self.node_type,
            "nickname": self.nickname,
            "avatar": self.avatar,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "interests": self.interests,
            "expertise_domains": self.expertise_domains,
            "capabilities": self.capabilities
        }


@dataclass
class ReputationScore:
    """信誉评分"""
    node_id: str
    total_score: float = 0.0
    
    # 各维度评分
    knowledge_score: float = 0.0
    verification_score: float = 0.0
    spread_score: float = 0.0
    learning_score: float = 0.0
    teaching_score: float = 0.0
    collaboration_score: float = 0.0
    
    # 统计数据
    knowledge_count: int = 0
    verification_count: int = 0
    spread_count: int = 0
    learning_count: int = 0
    
    # 等级
    level: int = 1
    title: str = "新手"
    
    updated_at: Optional[datetime] = None

    def calculate_total(self) -> float:
        """计算总评分"""
        self.total_score = (
            self.knowledge_score * 0.25 +
            self.verification_score * 0.20 +
            self.spread_score * 0.15 +
            self.learning_score * 0.15 +
            self.teaching_score * 0.15 +
            self.collaboration_score * 0.10
        )
        self._update_level()
        return self.total_score

    def _update_level(self):
        """更新等级"""
        if self.total_score >= 1000:
            self.level = 10
            self.title = "大师"
        elif self.total_score >= 500:
            self.level = 9
            self.title = "专家"
        elif self.total_score >= 200:
            self.level = 7
            self.title = "资深"
        elif self.total_score >= 100:
            self.level = 5
            self.title = "熟练"
        elif self.total_score >= 50:
            self.level = 3
            self.title = "进阶"
        else:
            self.level = 1
            self.title = "新手"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "total_score": self.total_score,
            "knowledge_score": self.knowledge_score,
            "verification_score": self.verification_score,
            "spread_score": self.spread_score,
            "learning_score": self.learning_score,
            "teaching_score": self.teaching_score,
            "collaboration_score": self.collaboration_score,
            "knowledge_count": self.knowledge_count,
            "verification_count": self.verification_count,
            "spread_count": self.spread_count,
            "learning_count": self.learning_count,
            "level": self.level,
            "title": self.title,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


@dataclass
class LearningRecord:
    """学习记录"""
    knowledge_id: str
    learner_id: str
    learned_at: Optional[datetime] = None
    learning_depth: float = 0.0
    notes: str = ""
    quiz_score: Optional[float] = None
    comprehension_rate: float = 0.0


# ==================== 对话系统 ====================

@dataclass
class DialogueMessage:
    """对话消息"""
    sender_id: str
    content: str
    message_type: str = "text"
    timestamp: Optional[datetime] = None
    message_id: str = ""
    reply_to: Optional[str] = None
    attachments: Dict[str, Any] = field(default_factory=dict)
    learning_highlights: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()
        if not self.message_id:
            content = f"{self.sender_id}{self.content}{self.timestamp}"
            self.message_id = hashlib.sha256(content.encode()).hexdigest()[:24]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sender_id": self.sender_id,
            "content": self.content,
            "message_type": self.message_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "message_id": self.message_id,
            "reply_to": self.reply_to,
            "attachments": self.attachments,
            "learning_highlights": self.learning_highlights
        }


@dataclass
class DialogueSession:
    """对话会话"""
    session_id: str
    initiator_id: str
    target_id: str
    dialogue_type: DialogueType
    created_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    messages: List[DialogueMessage] = field(default_factory=list)
    status: str = "active"
    learning_summary: str = ""

    def __post_init__(self):
        if isinstance(self.dialogue_type, str):
            self.dialogue_type = DialogueType(self.dialogue_type)
        if not self.created_at:
            self.created_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "initiator_id": self.initiator_id,
            "target_id": self.target_id,
            "dialogue_type": self.dialogue_type.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "messages": [m.to_dict() for m in self.messages],
            "status": self.status,
            "learning_summary": self.learning_summary
        }


# ==================== 智能合约 ====================

@dataclass
class ContractMetadata:
    """合约元数据"""
    contract_id: str = ""
    contract_type: str = ""
    creator_id: str = ""
    created_at: Optional[datetime] = None
    version: int = 1
    status: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "contract_type": self.contract_type,
            "creator_id": self.creator_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "version": self.version,
            "status": self.status
        }


@dataclass
class SmartContract:
    """智能合约"""
    metadata: ContractMetadata
    code: str = ""
    state: Dict[str, Any] = field(default_factory=dict)
    execution_history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if isinstance(self.metadata, dict):
            self.metadata = ContractMetadata(**self.metadata)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "code": self.code,
            "state": self.state,
            "execution_history": self.execution_history
        }


# ==================== 代币系统 ====================

@dataclass
class TokenBalance:
    """代币余额"""
    node_id: str
    balances: Dict[str, float] = field(default_factory=lambda: {
        "KNC": 0.0,    # 知识币
        "RPC": 0.0,    # 信誉币
        "CNC": 0.0,    # 贡献币
        "LNC": 0.0,    # 学习币
        "GNC": 0.0     # 治理币
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "balances": self.balances
        }


@dataclass
class TokenTransaction:
    """代币交易"""
    tx_id: str
    from_node: str
    to_node: str
    token_type: str
    amount: float
    reason: str
    timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "token_type": self.token_type,
            "amount": self.amount,
            "reason": reason,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


# ==================== 工具函数 ====================

def generate_knowledge_id(content_hash: str, creator_id: str, timestamp: datetime) -> str:
    """生成知识ID"""
    data = f"{content_hash}{creator_id}{timestamp.isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def generate_block_id(previous_hash: str, timestamp: datetime, nonce: int) -> str:
    """生成区块ID"""
    data = f"{previous_hash}{timestamp.isoformat()}{nonce}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def calculate_merkle_root(transactions: List[Transaction]) -> str:
    """计算Merkle根"""
    if not transactions:
        return hashlib.sha256(b"").hexdigest()
    
    hashes = [tx.tx_hash for tx in transactions]
    
    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])
        hashes = [hashlib.sha256((a + b).encode()).hexdigest() 
                  for a, b in zip(hashes[::2], hashes[1::2])]
    
    return hashes[0]
