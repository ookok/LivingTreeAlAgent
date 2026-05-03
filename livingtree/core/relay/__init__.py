"""
LivingTree Relay 中继链模块
============================

精简合并 client/src/business/ 中的 relay_chain (35文件) + relay_router (5文件) 
+ decentralized_mailbox (14文件) = 54 文件 为 3 个核心模块:

层次:
- models    — 统一的交易、共识、节点、消息数据模型
- ledger    — 交易账本 + 共识引擎 + 交易池
- transport — 节点注册中心 + 健康监控 + 消息传输

从 54 文件 / ~8500 行 → 3 文件 / ~1200 行 (精简 86%)

用法:
    from livingtree.core.relay import Ledger, ConsensusEngine, NodeRegistry, MessageTransport
    
    ledger = Ledger()
    consensus = ConsensusEngine()
    registry = NodeRegistry()
    transport = MessageTransport(registry)
"""

from .models import (
    OpType, TxStatus, NodeRole, ConsensusState,
    MessageChannel, MessageStatus,
    Tx, LedgerEntry,
    ConsensusVote, ConsensusResult,
    RelayNode, HealthReport,
    MailMessage,
    serialize_tx, deserialize_tx,
)
from .ledger import Mempool, Ledger, ConsensusEngine
from .transport import NodeRegistry, MessageTransport

__version__ = "1.0.0"
__author__ = "LivingTreeAI Team"

__all__ = [
    # 枚举
    "OpType", "TxStatus", "NodeRole", "ConsensusState",
    "MessageChannel", "MessageStatus",
    # 数据模型
    "Tx", "LedgerEntry",
    "ConsensusVote", "ConsensusResult",
    "RelayNode", "HealthReport",
    "MailMessage",
    "serialize_tx", "deserialize_tx",
    # 功能模块
    "Mempool", "Ledger", "ConsensusEngine",
    "NodeRegistry", "MessageTransport",
]
