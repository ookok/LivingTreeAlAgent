"""
P2P 搜索代理系统 - 统一调度器

分布式搜索代理网络，允许受限节点通过外网节点路由搜索请求

核心功能：
- 搜索请求路由分发（直连/P2P/Relay）
- 外网节点能力发现与注册
- Agent-Reach 远程调用封装
- 智能路由策略

使用示例：
    # 启动搜索代理
    proxy = P2PSearchProxy(node_id="my-node")
    await proxy.start()

    # 执行搜索（自动选择最优路由）
    task = await proxy.search("python tutorial")
    print(task.results)

    # 强制使用P2P
    task = await proxy.search("最新AI新闻", use_p2p=True)
"""

from __future__ import annotations

from .models import (
    SearchEngineType,
    SearchResultStatus,
    SearchTask,
    SearchResult,
    PeerCapability,
    PeerSearchCapability,
    SearchRouteDecision,
    P2PSearchConfig,
)

from .capability_registry import CapabilityRegistry
from .search_proxy import P2PSearchProxy

__all__ = [
    # 模型
    "SearchEngineType",
    "SearchResultStatus",
    "SearchTask",
    "SearchResult",
    "PeerCapability",
    "PeerSearchCapability",
    "SearchRouteDecision",
    "P2PSearchConfig",

    # 核心类
    "CapabilityRegistry",
    "P2PSearchProxy",
]
