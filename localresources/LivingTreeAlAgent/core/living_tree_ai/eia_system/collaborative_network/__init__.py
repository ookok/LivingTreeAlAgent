"""
P2P协同编制网络
将报告编制从"单机作业"变为"分布式协同"
"""

from .collaborative_network import (
    # 枚举
    NodeType,
    TaskStatus,
    OperationType,
    # 数据模型
    NetworkNode,
    ReportModule,
    CollaborativeTask,
    EditOperation,
    Contribution,
    ConsensusRecord,
    # 核心类
    TaskDispatcher,
    CollaborativeEditor,
    ContributionTracker,
    ContributionLedger,
    CollaborativeNetwork,
    # 工厂函数
    get_collaborative_network,
    create_collaborative_project_async,
)

__all__ = [
    "NodeType",
    "TaskStatus",
    "OperationType",
    "NetworkNode",
    "ReportModule",
    "CollaborativeTask",
    "EditOperation",
    "Contribution",
    "ConsensusRecord",
    "TaskDispatcher",
    "CollaborativeEditor",
    "ContributionTracker",
    "ContributionLedger",
    "CollaborativeNetwork",
    "get_collaborative_network",
    "create_collaborative_project_async",
]
