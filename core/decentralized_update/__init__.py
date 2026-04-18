# decentralized_update/__init__.py — P2P 去中心化更新系统

"""
Living Tree AI P2P Decentralized Update System
================================================

核心理念：构建一个自我演化、抗审查、高可用的分布式更新网络。
每个客户端既是使用者也是分发节点，利用区块链思想但不依赖区块链的轻量级解决方案。

三层网络架构：
┌─────────────────────────────────────────────────┐
│           发现层 (Discovery Layer)               │
│  DHT网络 + 智能种子节点 + 状态同步               │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│           验证层 (Validation Layer)               │
│  数字签名 + Merkle树 + 共识机制                  │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│           分发层 (Distribution Layer)             │
│  BitTorrent-like分片 + CDN优先策略               │
└─────────────────────────────────────────────────┘

核心模块：
1. models.py          - 协议定义与数据模型
2. discovery.py       - DHT 版本发现层
3. propagation.py      - 版本波纹扩散算法
4. delta_update.py    - 基因式增量更新
5. signature.py       - 社区共识签名验证
6. distribution.py     - BitTorrent 式分片分发
7. reputation.py       - 信誉系统
8. resilience.py       - 容错与自愈机制
9. manager.py         - 统一管理器

使用示例：
```python
from core.decentralized_update import get_update_manager, initialize_update_system

# 初始化
manager = await initialize_update_system()

# 检查更新
latest = await manager.check_for_updates()

# 下载更新
if latest:
    task = await manager.download_update(latest)

# 应用更新
await manager.apply_update(task.task_id)
```

Author: Hermes Desktop AI Assistant
"""

from pathlib import Path

# 数据目录
_DATA_DIR = Path.home() / ".hermes-desktop" / "decentralized_update"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

__version__ = "1.0.0"

# 子模块
from .models import (
    # 枚举
    NodeState, UpdateStage, MessageType, ReputationLevel,
    UpdateStrategy, SignatureType, VerificationStatus, ChunkState,
    # 数据类
    VersionInfo, NodeInfo, ChunkInfo, UpdateManifest,
    EndorsementSignature, UpdateTask, PropagationRecord,
    ProtocolMessage, AnnounceMessage, QueryMessage, ResponseMessage,
    HaveMessage, RequestChunkMessage, ChunkDataMessage, EndorsementMessage,
    # 工具
    MerkleTree, generate_task_id, generate_node_id,
    calculate_version_code, format_size, format_speed, format_duration,
)

from .discovery import (
    DHTNode, KBucket, DHTConfig,
    SeedNodeManager, get_dht_node, get_seed_manager,
)

from .propagation import (
    RipplePropagator, PropagationConfig, PropagationContext,
    PropagationState, VersionQuerier, get_propagator, get_querier,
)

from .delta_update import (
    DeltaManager, DeltaCalculator, VersionGeneGraph, VersionGene,
    VersionPathPlanner, DeltaConfig, get_delta_manager,
)

from .signature import (
    SignatureService, SignatureVerifier, SignatureConfig,
    SignatureChain, EndorsementCollector, VerificationStatus as SigVerificationStatus,
    get_signature_service,
)

from .distribution import (
    DistributionManager, ChunkManager, CDNOptimizer,
    DistributionConfig, ChunkDownload, get_distribution_manager, get_cdn_optimizer,
)

from .reputation import (
    ReputationManager, ReputationTracker, ReputationCalculator,
    ReputationConfig, ReputationRecord, ReputationEvent,
    get_reputation_manager,
)

from .resilience import (
    ResilienceManager, FailureDetector, ConnectionManager,
    CheckpointManager, NetworkSplitDetector, ConflictResolver,
    ResilienceConfig, FailureEvent, FailureType, Checkpoint,
    get_resilience_manager,
)

from .manager import (
    UpdateManager, UpdateConfig, UpdateSystemStatus, SystemState,
    get_update_manager, initialize_update_system, shutdown_update_system,
)

# 智能零配置更新系统
from .smart_update_decider import (
    SmartUpdateDecider, ProgressiveUpdateNotifier,
    UpdateStrategy, UpdateChannel, NetworkType, DeviceType,
    NetworkEnvironment, UserPreferences, TimeContext, DecisionResult, UpdateState,
    get_smart_decider, get_progressive_notifier, quick_decide,
)

# 更新说明自动生成器
from .update_notifier import (
    UpdateNotifier, UpdateType, NotificationPriority,
    UpdateSource, ChangelogEntry, UpdateNotes, SyncResult,
    get_update_notifier, generate_and_sync_update,
)

# 博客论坛同步
from .blog_forum_sync import (
    BlogForumSync, SyncStatus,
    BlogPost, ForumTopic, SyncRecord,
    get_blog_forum_sync,
    generate_blog_content, generate_forum_content,
)

__all__ = [
    # 版本信息
    "__version__",

    # 枚举 - models
    "NodeState", "UpdateStage", "MessageType", "ReputationLevel",
    "UpdateStrategy", "SignatureType", "VerificationStatus", "ChunkState",

    # 数据类 - models
    "VersionInfo", "NodeInfo", "ChunkInfo", "UpdateManifest",
    "EndorsementSignature", "UpdateTask", "PropagationRecord",
    "ProtocolMessage", "AnnounceMessage", "QueryMessage", "ResponseMessage",
    "HaveMessage", "RequestChunkMessage", "ChunkDataMessage", "EndorsementMessage",

    # 工具 - models
    "MerkleTree", "generate_task_id", "generate_node_id",
    "calculate_version_code", "format_size", "format_speed", "format_duration",

    # discovery
    "DHTNode", "KBucket", "DHTConfig",
    "SeedNodeManager", "get_dht_node", "get_seed_manager",

    # propagation
    "RipplePropagator", "PropagationConfig", "PropagationContext",
    "PropagationState", "VersionQuerier", "get_propagator", "get_querier",

    # delta_update
    "DeltaManager", "DeltaCalculator", "VersionGeneGraph", "VersionGene",
    "VersionPathPlanner", "DeltaConfig", "get_delta_manager",

    # signature
    "SignatureService", "SignatureVerifier", "SignatureConfig",
    "SignatureChain", "EndorsementCollector", "get_signature_service",

    # distribution
    "DistributionManager", "ChunkManager", "CDNOptimizer",
    "DistributionConfig", "ChunkDownload", "get_distribution_manager", "get_cdn_optimizer",

    # reputation
    "ReputationManager", "ReputationTracker", "ReputationCalculator",
    "ReputationConfig", "ReputationRecord", "ReputationEvent",
    "get_reputation_manager",

    # resilience
    "ResilienceManager", "FailureDetector", "ConnectionManager",
    "CheckpointManager", "NetworkSplitDetector", "ConflictResolver",
    "ResilienceConfig", "FailureEvent", "FailureType", "Checkpoint",
    "get_resilience_manager",

    # manager
    "UpdateManager", "UpdateConfig", "UpdateSystemStatus", "SystemState",
    "get_update_manager", "initialize_update_system", "shutdown_update_system",

    # 智能零配置更新
    "SmartUpdateDecider", "ProgressiveUpdateNotifier",
    "UpdateStrategy", "UpdateChannel", "NetworkType", "DeviceType",
    "NetworkEnvironment", "UserPreferences", "TimeContext", "DecisionResult", "UpdateState",
    "get_smart_decider", "get_progressive_notifier", "quick_decide",

    # 更新说明生成器
    "UpdateNotifier", "UpdateType", "NotificationPriority",
    "UpdateSource", "ChangelogEntry", "UpdateNotes", "SyncResult",
    "get_update_notifier", "generate_and_sync_update",

    # 博客论坛同步
    "BlogForumSync", "SyncStatus",
    "BlogPost", "ForumTopic", "SyncRecord",
    "get_blog_forum_sync",
    "generate_blog_content", "generate_forum_content",
]
