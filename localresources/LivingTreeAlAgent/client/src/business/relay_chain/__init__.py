"""
中继链 - Relay Chain

无币无挖矿的分布式积分记账系统 + 事件驱动扩展

核心组件：
- transaction: 交易数据结构
- ledger: 链式账本
- mempool: 交易池
- consensus: 共识机制
- node_manager: 节点管理
- sync_protocol: 同步协议
- db: 数据库模型

事件扩展 (event_ext)：
- event_transaction: 扩展交易类型（任务/租户/资产/政务）
- event_ledger: 泛化事件账本
- task_scheduler: 任务调度防重放（替代 Redis 锁）
- cross_tenant: 跨租户消息通道
- game_asset: 游戏资产管理

架构设计：
1. P2P中继网络，无主从之分
2. 链式账本，余额由历史计算
3. 交易池暂存未确认交易
4. 多数派共识确认机制
5. 注册中心管理节点发现

防双花核心：
- nonce 机制：同一用户交易必须按顺序入账
- prev_hash：交易链完整性
- 余额校验：支出不能超过余额
- 全网广播：所有节点独立验证

扩展场景：
- 任务调度防重放（替代 Redis 分布式锁）
- 跨租户消息通道（SaaS 多租户）
- 游戏资产流转（非区块链版 Web3）
- 政务一码通互信底座

参考设计：
- https://gitee.com/simazehao/company-stamp (仅参考结构)
"""

from .transaction import (
    Tx,
    OpType,
    TxValidationResult,
    TxConfirm,
    TxBuilder
)

from .ledger import (
    Ledger,
    AccountState,
    LedgerValidator
)

from .mempool import (
    Mempool,
    PendingTx,
    MempoolSynchronizer
)

from .consensus import (
    ConsensusEngine,
    ConsensusState,
    ConsensusVote,
    TxConsensus
)

from .node_manager import (
    RelayNode,
    NodeType,
    NodeState,
    Registry,
    NodeManager
)

from .sync_protocol import (
    SyncProtocol,
    SyncState,
    SyncMessageType,
    SyncMessage,
    SyncProgress,
    StateComparator
)

from .payment_callback import (
    PaymentCallback,
    PaymentCallbackHandler,
    PaymentCallbackResult,
    PaymentChannel,
    PaymentSignatureVerifier,
    IdempotencyChecker,
    create_payment_callback_handler
)

from .pending_tx import (
    PendingTxManager,
    PendingTx,
    TxStatus
)

from .reconciliation import (
    ReconciliationService,
    ReconciliationResult,
    ReconciliationScheduler
)

from .monitor import (
    MonitoringService,
    Alert,
    AlertLevel,
    NodeMetrics,
    MetricsCollector
)

from .audit import (
    AuditService,
    AuditTrail,
    BalanceProof,
    AuditLogger
)

# 事件扩展模块
from .event_ext import (
    OpType,
    EventTx,
    EventTxBuilder,
    EventValidationResult,
    EventLedger,
    EventLedgerValidator,
    TaskScheduler,
    TaskDefinition,
    TaskStatus,
    CrossTenantChannel,
    TenantMessage,
    MessageReceipt,
    GameAssetLedger,
    AssetDefinition,
    AssetOwnership,
    # 分布式 IM
    DistributedIM,
    GossipNode,
    GossipMessage,
    Conversation,
    ConversationType,
    MessageType,
    ReceiptType,
    UserProfile,
    # P2P 自组织网络
    DistributedNode,
    MulticastDiscover,
    Election,
    NodeRole,
    Protocol,
    RoutingTable,
    LoadBalancer,
    TaskDistributor,
    start_node,
    create_node,
    run_web_dashboard,
)

__all__ = [
    # transaction
    "Tx",
    "OpType",
    "TxValidationResult",
    "TxConfirm",
    "TxBuilder",

    # ledger
    "Ledger",
    "AccountState",
    "LedgerValidator",

    # mempool
    "Mempool",
    "PendingTx",
    "MempoolSynchronizer",

    # consensus
    "ConsensusEngine",
    "ConsensusState",
    "ConsensusVote",
    "TxConsensus",

    # node_manager
    "RelayNode",
    "NodeType",
    "NodeState",
    "Registry",
    "NodeManager",

    # sync_protocol
    "SyncProtocol",
    "SyncState",
    "SyncMessageType",
    "SyncMessage",
    "SyncProgress",
    "StateComparator",

    # payment_callback
    "PaymentCallback",
    "PaymentCallbackHandler",
    "PaymentCallbackResult",
    "PaymentChannel",
    "PaymentSignatureVerifier",
    "IdempotencyChecker",
    "create_payment_callback_handler",

    # pending_tx
    "PendingTxManager",
    "PendingTx",
    "TxStatus",

    # reconciliation
    "ReconciliationService",
    "ReconciliationResult",
    "ReconciliationScheduler",

    # monitor
    "MonitoringService",
    "Alert",
    "AlertLevel",
    "NodeMetrics",
    "MetricsCollector",

    # audit
    "AuditService",
    "AuditTrail",
    "BalanceProof",
    "AuditLogger",

    # event_ext - 事件驱动扩展
    "OpType",
    "EventTx",
    "EventTxBuilder",
    "EventValidationResult",
    "EventLedger",
    "EventLedgerValidator",
    "TaskScheduler",
    "TaskDefinition",
    "TaskStatus",
    "CrossTenantChannel",
    "TenantMessage",
    "MessageReceipt",
    "GameAssetLedger",
    "AssetDefinition",
    "AssetOwnership",

    # distributed_im - 分布式 IM
    "DistributedIM",
    "GossipNode",
    "GossipMessage",
    "Conversation",
    "ConversationType",
    "MessageType",
    "ReceiptType",
    "UserProfile",

    # p2p_network - 零配置自组织网络
    "DistributedNode",
    "MulticastDiscover",
    "Election",
    "NodeRole",
    "Protocol",
    "RoutingTable",
    "LoadBalancer",
    "TaskDistributor",
    "start_node",
    "create_node",
    "run_web_dashboard",
]