"""
LivingTreeAI Streaming Network - 实时流媒体传输系统
==================================================

架构：
┌─────────────────────────────────────────────────────────────┐
│                  实时流媒体分层架构                          │
├─────────────────────────────────────────────────────────────┤
│  应用层: 语音/视频通话、直播、弹幕/聊天、状态同步              │
├─────────────────────────────────────────────────────────────┤
│  控制层: WebRTC SFU、拓扑管理、会话控制                        │
├─────────────────────────────────────────────────────────────┤
│  传输层: QUIC/WebRTC DataChannel、自适应码率                  │
├─────────────────────────────────────────────────────────────┤
│  基础设施: 节点发现、带宽探测、质量监控                        │
└─────────────────────────────────────────────────────────────┘

模块：
- webrtc_sfu.py       : WebRTC SFU 实现
- streaming_topology.py : 树状+网状混合拓扑
- sync_protocol.py     : 媒体同步协议
- stream_state.py      : 流状态同步（聊天/弹幕/点赞）
- conflict_resolution.py: 冲突解决（OCC + 最终一致性）
- quality_monitor.py   : 质量监控与自适应

Author: LivingTreeAI Community
License: Apache 2.0
"""

__version__ = "1.0.0"

from .webrtc_sfu import (
    WebRTCSFU,
    StreamSession,
    MediaTrack,
    ConnectionState,
    get_webrtc_sfu,
)

from .streaming_topology import (
    StreamingTopology,
    TopologyType,
    TreeNode,
    MeshNode,
    get_streaming_topology,
)

from .sync_protocol import (
    MediaSyncProtocol,
    SyncSource,
    ClockSync,
    get_media_sync,
)

from .stream_state import (
    StreamState,
    StreamStateType,
    ChatMessage,
    DanmakuMessage,
    LikeEvent,
    StreamStateSync,
    get_stream_state_sync,
)

from .conflict_resolution import (
    OptimisticConflictResolver,
    ConflictType,
    EventualConsistency,
    CRDTRegister,
    CRDTCounter,
    get_conflict_resolver,
)

from .quality_monitor import (
    StreamQualityMonitor,
    QualityMetrics,
    AdaptationAction,
    get_quality_monitor,
)

__all__ = [
    # 版本
    "__version__",
    # WebRTC SFU
    "WebRTCSFU",
    "StreamSession",
    "MediaTrack",
    "ConnectionState",
    "get_webrtc_sfu",
    # 拓扑
    "StreamingTopology",
    "TopologyType",
    "TreeNode",
    "MeshNode",
    "get_streaming_topology",
    # 同步
    "MediaSyncProtocol",
    "SyncSource",
    "ClockSync",
    "get_media_sync",
    # 状态
    "StreamState",
    "StreamStateType",
    "ChatMessage",
    "DanmakuMessage",
    "LikeEvent",
    "StreamStateSync",
    "get_stream_state_sync",
    # 冲突
    "OptimisticConflictResolver",
    "ConflictType",
    "EventualConsistency",
    "CRDTRegister",
    "CRDTCounter",
    "get_conflict_resolver",
    # 质量
    "StreamQualityMonitor",
    "QualityMetrics",
    "AdaptationAction",
    "get_quality_monitor",
]