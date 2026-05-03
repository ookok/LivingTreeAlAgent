"""
LivingTree P2P 网络统一模块
============================

合并 client/src/business/ 中的 p2p_broadcast、p2p_connector、p2p_knowledge
三个独立模块为一个统一的分层架构。

层次结构:
- models    — 统一数据模型（消除三套重复定义）
- nat       — NAT 穿透 + ECDH/AES-256-GCM 加密
- discovery — 节点发现 + 消息路由

用法:
    from livingtree.core.network.p2p import (
        PeerIdentity, PeerInfo, PeerDiscovery, MessageDispatcher
    )

    identity = PeerIdentity.generate("MyNode")
    discovery = PeerDiscovery(identity)
    await discovery.start()
    peers = await discovery.discover()
"""

from .models import (
    PeerStatus, ConnectionType, MessageType, NATType, TrustLevel, DiscoveryMethod,
    NetworkAddress, PeerIdentity, PeerInfo, P2PMessage,
    ConnectionConfig, RoutingEntry,
    serialize_message, deserialize_message,
)
from .nat import CryptoSession, NATDetector, NATTraversalEngine
from .discovery import PeerDiscovery, MessageDispatcher, DiscoveryResult

__version__ = "1.0.0"
__author__ = "LivingTreeAI Team"

__all__ = [
    # 枚举
    "PeerStatus", "ConnectionType", "MessageType", "NATType", "TrustLevel", "DiscoveryMethod",
    # 数据模型
    "NetworkAddress", "PeerIdentity", "PeerInfo", "P2PMessage",
    "ConnectionConfig", "RoutingEntry",
    "serialize_message", "deserialize_message",
    # 加密
    "CryptoSession",
    # NAT
    "NATDetector", "NATTraversalEngine",
    # 发现与消息
    "PeerDiscovery", "MessageDispatcher", "DiscoveryResult",
]
