"""
Event Sync - Gossip协议事件同步
================================

功能：
- 事件广播（带TTL限制）
- 订阅管理
- 签名验证
- 消息去重

Author: LivingTreeAI Community
"""

import asyncio
import hashlib
import time
import random
import json
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any, Set
from enum import Enum
from collections import defaultdict


class EventType(Enum):
    """事件类型"""
    # 缓存相关
    CACHE_INDEX_NEW = "cache_index_new"       # 新缓存索引
    CACHE_INDEX_UPDATE = "cache_index_update" # 缓存更新
    CACHE_INDEX_REMOVE = "cache_index_remove" # 缓存移除

    # 节点相关
    NODE_ONLINE = "node_online"               # 节点上线
    NODE_OFFLINE = "node_offline"             # 节点下线
    NODE_STATUS_CHANGE = "node_status_change" # 节点状态变化

    # 贡献相关
    CONTRIBUTION_NEW = "contribution_new"     # 新贡献证明
    CONTRIBUTION_VERIFY = "contribution_verify" # 贡献验证

    # 专长相关
    SPECIALTY_ANNOUNCE = "specialty_announce" # 专长声明
    SPECIALTY_REVOKE = "specialty_revoke"     # 专长撤销

    # 同步相关
    SYNC_REQUEST = "sync_request"             # 同步请求
    SYNC_RESPONSE = "sync_response"            # 同步响应

    # 通用
    HEARTBEAT = "heartbeat"                   # 心跳
    PING = "ping"                             # ping
    PONG = "pong"                             # pong


@dataclass
class SyncEvent:
    """同步事件"""
    id: str
    type: EventType
    data: dict
    sender: str
    timestamp: float
    ttl: int = 3
    signature: Optional[str] = None
    version: int = 1

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "data": self.data,
            "sender": self.sender,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
            "signature": self.signature,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SyncEvent":
        return cls(
            id=data["id"],
            type=EventType(data["type"]),
            data=data["data"],
            sender=data["sender"],
            timestamp=data["timestamp"],
            ttl=data.get("ttl", 3),
            signature=data.get("signature"),
            version=data.get("version", 1),
        )


class SubscriptionManager:
    """订阅管理器"""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._subscriptions: dict[EventType, Set[str]] = defaultdict(set)  # event_type -> node_ids
        self._node_subscriptions: dict[str, Set[EventType]] = defaultdict(set)  # node_id -> event_types

    def subscribe(self, node_id: str, event_types: list[EventType]):
        """节点订阅事件类型"""
        for et in event_types:
            self._subscriptions[et].add(node_id)
            self._node_subscriptions[node_id].add(et)

    def unsubscribe(self, node_id: str, event_types: Optional[list[EventType]] = None):
        """节点取消订阅"""
        if event_types is None:
            # 取消所有订阅
            for et in self._node_subscriptions.get(node_id, set()):
                self._subscriptions[et].discard(node_id)
            self._node_subscriptions.pop(node_id, None)
        else:
            for et in event_types:
                self._subscriptions[et].discard(node_id)
                self._node_subscriptions[node_id].discard(et)

    def get_subscribers(self, event_type: EventType) -> Set[str]:
        """获取事件类型的订阅者"""
        return self._subscriptions.get(event_type, set()).copy()

    def get_subscriptions(self, node_id: str) -> Set[EventType]:
        """获取节点的订阅"""
        return self._node_subscriptions.get(node_id, set()).copy()


class GossipSync:
    """
    Gossip协议事件同步

    特点：
    - 最终一致性
    - 去中心化
    - 容错性强
    - 消息去重
    - TTL限制传播次数
    """

    # Gossip参数
    DEFAULT_TTL = 3
    FANOUT_COUNT = 3  # 每次传播的节点数
    MESSAGE_CACHE_SIZE = 10000
    MESSAGE_CACHE_TTL = 3600  # 1小时

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
        sign_func: Optional[Callable[[dict], str]] = None,
        verify_func: Optional[Callable[[dict, str], bool]] = None,
    ):
        self.node_id = node_id

        # 已知节点
        self.peers: Set[str] = set()

        # 消息缓存（已处理消息）
        self.message_cache: dict[str, float] = {}  # event_id -> timestamp

        # 订阅管理
        self.subscriptions = SubscriptionManager(node_id)

        # 事件处理器
        self._handlers: dict[EventType, Callable] = {}

        # 网络函数
        self._send_func = send_func
        self._sign_func = sign_func or self._default_sign
        self._verify_func = verify_func or self._default_verify

        # 配置
        self.config = {
            "fanout_count": self.FANOUT_COUNT,
            "default_ttl": self.DEFAULT_TTL,
            "cache_size": self.MESSAGE_CACHE_SIZE,
        }

    # ========== 签名相关 ==========

    def _default_sign(self, data: dict) -> str:
        """默认签名（简化版）"""
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _default_verify(self, data: dict, signature: str) -> bool:
        """默认验证"""
        expected = self._default_sign(data)
        return signature == expected

    def sign_event(self, event: SyncEvent) -> str:
        """签名事件"""
        sign_data = {
            "id": event.id,
            "type": event.type.value,
            "data": event.data,
            "sender": event.sender,
            "timestamp": event.timestamp,
        }
        return self._sign_func(sign_data)

    def verify_signature(self, event: SyncEvent) -> bool:
        """验证签名"""
        if not event.signature:
            return False
        return self._verify_func(event.to_dict(), event.signature)

    # ========== 事件ID生成 ==========

    def generate_event_id(self) -> str:
        """生成唯一事件ID"""
        data = f"{self.node_id}:{time.time()}:{random.randint(0, 1000000)}"
        return hashlib.sha256(data.encode()).hexdigest()[:24]

    # ========== 广播事件 ==========

    async def broadcast_event(
        self,
        event_type: EventType,
        data: dict,
        ttl: Optional[int] = None,
    ) -> SyncEvent:
        """
        广播事件

        流程：
        1. 创建事件
        2. 签名
        3. 选择目标节点
        4. 发送
        5. 本地处理
        """
        if ttl is None:
            ttl = self.config["default_ttl"]

        event = SyncEvent(
            id=self.generate_event_id(),
            type=event_type,
            data=data,
            sender=self.node_id,
            timestamp=time.time(),
            ttl=ttl,
        )

        # 签名
        event.signature = self.sign_event(event)

        # 选择Gossip目标
        targets = self.select_gossip_targets(event)

        # 并行发送
        if self._send_func and targets:
            send_tasks = [
                self._send_func(peer, {"type": "event", "event": event.to_dict()})
                for peer in targets
            ]
            asyncio.create_task(asyncio.gather(*send_tasks, return_exceptions=True))

        # 本地处理
        await self.handle_event(event, is_local=True)

        return event

    def select_gossip_targets(self, event: SyncEvent) -> list[str]:
        """
        选择Gossip目标节点

        策略：
        1. 订阅了该事件类型的节点
        2. 随机选择部分节点（反熵）
        """
        targets = set()

        # 1. 订阅者
        subscribers = self.subscriptions.get_subscribers(event.type)
        targets.update(subscribers)

        # 2. 随机节点
        all_peers = list(self.peers - subscribers)
        random.shuffle(all_peers)
        random_count = min(self.config["fanout_count"], len(all_peers))
        targets.update(all_peers[:random_count])

        # 排除自己
        targets.discard(self.node_id)

        return list(targets)[:self.config["fanout_count"]]

    # ========== 处理事件 ==========

    async def handle_event(self, event: SyncEvent, is_local: bool = False):
        """处理事件"""
        # 记录到缓存
        self._cache_event(event.id)

        # 调用处理器
        if event.type in self._handlers:
            handler = self._handlers[event.type]
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)

    async def handle_incoming_event(self, event_data: dict):
        """处理收到的同步事件"""
        # 解析事件
        event = SyncEvent.from_dict(event_data)

        # 检查重复
        if self._is_duplicate(event.id):
            return

        # 验证签名
        if not self.verify_signature(event):
            return

        # 继续传播（TTL > 0 且 非本地生成）
        if event.ttl > 0:
            asyncio.create_task(self._forward_event(event))

        # 处理事件
        await self.handle_event(event, is_local=False)

    async def _forward_event(self, event: SyncEvent):
        """转发事件"""
        # 排除发送者和已处理节点
        exclude = {event.sender, self.node_id}
        processed_ids = set(self.message_cache.keys())

        forward_to = [
            peer for peer in self.peers
            if peer not in exclude
        ]

        # 随机选择
        random.shuffle(forward_to)
        forward_to = forward_to[:2]  # 只转发给2个节点

        # 创建转发事件
        forwarded = SyncEvent(
            id=event.id,
            type=event.type,
            data=event.data,
            sender=self.node_id,  # 标记自己是转发者
            timestamp=event.timestamp,
            ttl=event.ttl - 1,
            signature=event.signature,
        )

        for peer in forward_to:
            try:
                if self._send_func:
                    await self._send_func(peer, {"type": "event", "event": forwarded.to_dict()})
            except Exception:
                pass

    # ========== 消息缓存 ==========

    def _is_duplicate(self, event_id: str) -> bool:
        """检查是否重复"""
        if event_id in self.message_cache:
            return True
        return False

    def _cache_event(self, event_id: str):
        """缓存事件ID"""
        self.message_cache[event_id] = time.time()

        # 清理过期缓存
        if len(self.message_cache) > self.config["cache_size"]:
            self._cleanup_cache()

    def _cleanup_cache(self):
        """清理过期缓存"""
        now = time.time()
        expired = [
            eid for eid, ts in self.message_cache.items()
            if now - ts > self.MESSAGE_CACHE_TTL
        ]
        for eid in expired:
            del self.message_cache[eid]

        # 如果还是太大，随机删除一半
        if len(self.message_cache) > self.config["cache_size"]:
            to_remove = list(self.message_cache.keys())[:len(self.message_cache) // 2]
            for eid in to_remove:
                del self.message_cache[eid]

    # ========== 节点管理 ==========

    def add_peer(self, peer_id: str):
        """添加节点"""
        self.peers.add(peer_id)

    def remove_peer(self, peer_id: str):
        """移除节点"""
        self.peers.discard(peer_id)
        self.subscriptions.unsubscribe(peer_id)

    def get_peers(self) -> Set[str]:
        """获取所有节点"""
        return self.peers.copy()

    # ========== 处理器注册 ==========

    def register_handler(self, event_type: EventType, handler: Callable):
        """注册事件处理器"""
        self._handlers[event_type] = handler

    # ========== 便捷广播方法 ==========

    async def broadcast_node_online(self, node_info: dict):
        """广播节点上线"""
        return await self.broadcast_event(EventType.NODE_ONLINE, node_info)

    async def broadcast_node_offline(self, node_id: str):
        """广播节点下线"""
        return await self.broadcast_event(EventType.NODE_OFFLINE, {"node_id": node_id})

    async def broadcast_cache_index(self, cache_data: dict):
        """广播缓存索引"""
        return await self.broadcast_event(EventType.CACHE_INDEX_NEW, cache_data)

    async def broadcast_contribution(self, contribution_data: dict):
        """广播贡献证明"""
        return await self.broadcast_event(EventType.CONTRIBUTION_NEW, contribution_data)

    async def broadcast_specialty(self, specialty_data: dict):
        """广播专长声明"""
        return await self.broadcast_event(EventType.SPECIALTY_ANNOUNCE, specialty_data)

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "peers": len(self.peers),
            "cached_events": len(self.message_cache),
            "subscriptions": {
                et.value: len(nodes)
                for et, nodes in self.subscriptions._subscriptions.items()
            },
        }


# 全局单例
_gossip_instance: Optional[GossipSync] = None


def get_gossip_sync(node_id: str = "local") -> GossipSync:
    """获取Gossip同步单例"""
    global _gossip_instance
    if _gossip_instance is None:
        _gossip_instance = GossipSync(node_id)
    return _gossip_instance