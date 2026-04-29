"""
LivingTreeAI Sync Network - 三层同步体系
==========================================

三层同步架构：
┌─────────────────────────────────────────────────────────────┐
│                    三层同步体系                              │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐│
│  │  事件同步(实时)  │→ │  增量同步(定期)  │→ │ 全量同步(兜底││
│  │  Gossip Protocol │  │ Merkle+版本向量  │  │ 分片+校验   ││
│  └─────────────────┘  └─────────────────┘  └─────────────┘│
├─────────────────────────────────────────────────────────────┤
│                    共享基础设施                              │
│  (通信协议栈 / 加密签名 / 冲突解决)                          │
└─────────────────────────────────────────────────────────────┘

同步类型：
- event_sync.py    : 事件同步（Gossip协议）
- incremental_sync.py : 增量同步（Merkle树 + 版本向量）
- full_sync.py     : 全量同步（分片 + 校验）
- consistency.py   : 一致性保证
- sync_manager.py  : 同步管理器

Author: LivingTreeAI Community
License: Apache 2.0
"""

__version__ = "1.0.0"

from .event_sync import (
    GossipSync,
    SyncEvent,
    EventType,
    SubscriptionManager,
    get_gossip_sync,
)

from .incremental_sync import (
    IncrementalSync,
    VersionVector,
    MerkleTree,
    DataDigest,
    get_incremental_sync,
)

from .full_sync import (
    FullSync,
    Snapshot,
    Shard,
    ShardStatus,
    get_full_sync,
)

from .consistency import (
    ConsistencyModel,
    ConflictResolver,
    WriteOperation,
    ConsistencyLevel,
    get_consistency_model,
)

from .sync_manager import (
    SyncManager,
    SyncConfig,
    SyncPartner,
    SyncStats,
    get_sync_manager,
)

__all__ = [
    # 版本
    "__version__",
    # 事件同步
    "GossipSync",
    "SyncEvent",
    "EventType",
    "SubscriptionManager",
    "get_gossip_sync",
    # 增量同步
    "IncrementalSync",
    "VersionVector",
    "MerkleTree",
    "DataDigest",
    "get_incremental_sync",
    # 全量同步
    "FullSync",
    "Snapshot",
    "Shard",
    "ShardStatus",
    "get_full_sync",
    # 一致性
    "ConsistencyModel",
    "ConflictResolver",
    "WriteOperation",
    "ConsistencyLevel",
    "get_consistency_model",
    # 管理器
    "SyncManager",
    "SyncConfig",
    "SyncPartner",
    "SyncStats",
    "get_sync_manager",
]