"""
事件驱动账本 - Event-Driven Ledger

将"积分记账"泛化为"事件日志"的核心理念：

传统积分系统：
  - op_type: IN/OUT/TRANSFER
  - amount: 积分数量
  - 关注点：余额计算

事件驱动账本：
  - op_type: TASK_DISPATCH / ASSET_TRANSFER / CROSS_TENANT_MSG / ...
  - amount: 可以是 1（表示发生）、可以是业务量（如任务权重）
  - 关注点：事件溯源、不可抵赖、防重放

核心扩展：
1. 任务调度防重放：用 biz_id 锁定任务ID，nonce 确保串行执行
2. 跨租户消息：tenant_id 隔离 + 不可抵赖的消息链
3. 游戏资产管理：资产即交易，流转全网可验证
4. 政务一码通：实名事件时间戳，不可篡改

防双花机制完全通用：
- nonce 机制：同一业务ID的交易必须串行
- prev_hash：事件链完整性
- 全网广播：所有中继独立验证
"""

from .event_transaction import (
    OpType,
    EventTx,
    EventTxBuilder,
    EventValidationResult,
)

from .event_ledger import (
    EventLedger,
    EventLedgerValidator,
)

from .task_scheduler import (
    TaskScheduler,
    TaskDefinition,
    TaskStatus,
)

from .cross_tenant import (
    CrossTenantChannel,
    TenantMessage,
    MessageReceipt,
)

from .game_asset import (
    GameAssetLedger,
    AssetDefinition,
    AssetOwnership,
)

from .distributed_im import (
    DistributedIM,
    GossipNode,
    GossipMessage,
    Conversation,
    ConversationType,
    MessageType,
    ReceiptType,
    UserProfile,
)

from .p2p_network import (
    DistributedNode,
    MulticastDiscover,
    Election,
    NodeRole,
    Protocol,
    MessageType as NetMessageType,
    RoutingTable,
    LoadBalancer,
    TaskDistributor,
)

from .p2p_network.zero_config import (
    start_node,
    create_node,
    run_web_dashboard,
)

# evolving_community - 渐进去中心化AI社区
from . import evolving_community

__all__ = [
    # event_transaction
    "OpType",
    "EventTx",
    "EventTxBuilder",
    "EventValidationResult",

    # event_ledger
    "EventLedger",
    "EventLedgerValidator",

    # task_scheduler
    "TaskScheduler",
    "TaskDefinition",
    "TaskStatus",

    # cross_tenant
    "CrossTenantChannel",
    "TenantMessage",
    "MessageReceipt",

    # game_asset
    "GameAssetLedger",
    "AssetDefinition",
    "AssetOwnership",

    # distributed_im
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
    "NetMessageType",
    "RoutingTable",
    "LoadBalancer",
    "TaskDistributor",
    "start_node",
    "create_node",
    "run_web_dashboard",
]