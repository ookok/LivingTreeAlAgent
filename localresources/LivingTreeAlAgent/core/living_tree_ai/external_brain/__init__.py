"""
ExternalBrain - 外脑调用与多通道回退系统
==========================================

核心理念："本地优先、用户知情、绝不越权"

四层回退架构：
- 通道0：本地直连（默认）
- 通道1：用户显式配置的代理
- 通道2：官方API通道
- 通道3：本地降级（离线韧性）

安全合规铁律：
1. 绝不内置代理/节点
2. 绝不自动修改系统网络设置
3. 用户授权原则：所有外部通道必须由用户显式配置
4. 数据隔离：外脑调用与业务数据物理隔离

Author: LivingTreeAI Community
"""

from .channel_manager import (
    ChannelType,
    ChannelStatus,
    ChannelResult,
    ChannelManager,
    get_channel_manager,
)
from .network_diagnosis import (
    ServiceStatus,
    DiagnosisReport,
    NetworkDiagnoser,
    get_network_diagnoser,
)
from .offline_queue import (
    OfflineTask,
    OfflineQueue,
    get_offline_queue,
)
from .external_brain_panel import (
    ExternalBrainPanel,
    NetworkStatusWidget,
    ChannelStatusWidget,
    ProxyConfigWidget,
    OfflineQueueWidget,
    create_external_brain_panel,
)

__all__ = [
    # 通道管理
    "ChannelType",
    "ChannelStatus",
    "ChannelResult",
    "ChannelManager",
    "get_channel_manager",
    # 网络诊断
    "ServiceStatus",
    "DiagnosisReport",
    "NetworkDiagnoser",
    "get_network_diagnoser",
    # 离线队列
    "OfflineTask",
    "OfflineQueue",
    "get_offline_queue",
    # UI面板
    "ExternalBrainPanel",
    "NetworkStatusWidget",
    "ChannelStatusWidget",
    "ProxyConfigWidget",
    "OfflineQueueWidget",
    "create_external_brain_panel",
]