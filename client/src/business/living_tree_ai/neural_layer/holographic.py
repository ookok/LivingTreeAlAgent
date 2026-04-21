"""
Holographic Messaging - 全息通信
=================================

消息不是"发送-接收"，而是在网络中同时"存在"于所有相关节点

核心概念：
- 消息场 (Message Field)
- 观察者效应 (Observer Effect)
- 延迟实例化 (Lazy Instantiation)

Author: LivingTreeAI Community
"""

import asyncio
import time
import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Dict, Any, Set, List
from enum import Enum


class ObserverState(Enum):
    """观察者状态"""
    POTENTIAL = "potential"     # 潜在观察者
    OBSERVING = "observing"    # 正在观察
    COLLAPSED = "collapsed"    # 已实例化


@dataclass
class MessageField:
    """
    消息场

    消息发布到这个分布式场中，所有订阅的节点同时感知其存在
    """
    field_id: str
    field_type: str = "global"  # global/local/private
    content_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    # 观察者
    potential_observers: Set[str] = field(default_factory=set)
    active_observers: Set[str] = field(default_factory=set)

    # 状态
    exists: bool = True  # 是否存在于场中


@dataclass
class ObserverEffect:
    """观察者效应"""
    message_id: str
    observer_id: str
    collapsed: bool = False
    collapsed_at: Optional[float] = None
    content: Optional[Any] = None


class HolographicMessage:
    """
    全息消息

    原理：
    1. 消息发布到"消息场"，获得"量子态"
    2. 观察者订阅场，感知消息存在
    3. 观察者"观察"消息时，消息"坍缩"为具体实例
    """

    # 配置
    FIELD_BROADCAST_INTERVAL_MS = 100  # 场广播间隔
    COLLAPSE_TIMEOUT_SECONDS = 60  # 坍缩超时

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
        storage_func: Optional[Callable[[str, Any], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 消息场
        self.active_fields: Dict[str, MessageField] = {}

        # 观察者状态
        self.observer_states: Dict[str, ObserverEffect] = {}

        # 网络函数
        self._send_func = send_func
        self._storage_func = storage_func

        # 回调
        self._on_message_projected: Optional[Callable] = None
        self._on_message_observed: Optional[Callable] = None
        self._on_message_collapsed: Optional[Callable] = None

    # ========== 消息发布 ==========

    async def project_message(
        self,
        content: Any,
        field_type: str = "global",
        observer_candidates: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        将消息投影到消息场

        Args:
            content: 消息内容
            field_type: 场类型 (global/local/private)
            observer_candidates: 潜在的观察者列表
            metadata: 元数据

        Returns:
            消息ID
        """
        message_id = str(uuid.uuid4())[:16]

        # 计算内容哈希
        content_hash = self._hash_content(content)

        # 创建消息场
        field = MessageField(
            field_id=message_id,
            field_type=field_type,
            content_hash=content_hash,
            metadata=metadata or {},
        )

        # 设置潜在观察者
        if observer_candidates:
            field.potential_observers.update(observer_candidates)

        self.active_fields[message_id] = field

        # 存储到分布式存储
        if self._storage_func:
            await self._storage_func(message_id, {
                "content": content,
                "content_hash": content_hash,
                "metadata": metadata,
            })

        # 广播存在通知
        await self._broadcast_existence(field)

        # 回调
        if self._on_message_projected:
            await self._on_message_projected(message_id, field)

        return message_id

    async def _broadcast_existence(self, field: MessageField):
        """广播消息存在"""
        if self._send_func:
            # 广播给潜在观察者
            for observer in field.potential_observers:
                try:
                    await self._send_func(observer, {
                        "type": "holographic_announce",
                        "message_id": field.field_id,
                        "content_hash": field.content_hash,
                        "metadata": field.metadata,
                        "field_type": field.field_type,
                    })
                except Exception:
                    pass

    # ========== 消息观察 ==========

    async def observe_message(
        self,
        message_id: str,
        observer_id: Optional[str] = None,
    ) -> ObserverEffect:
        """
        观察消息（触发实例化/坍缩）

        Args:
            message_id: 消息ID
            observer_id: 观察者ID（默认为本节点）

        Returns:
            观察者效应
        """
        observer = observer_id or self.node_id

        field = self.active_fields.get(message_id)
        if not field:
            # 消息不在本地场中，请求传输
            return await self._request_remote_collapse(message_id, observer)

        # 创建观察者状态
        effect = ObserverEffect(
            message_id=message_id,
            observer_id=observer,
            collapsed=False,
        )
        self.observer_states[f"{message_id}:{observer}"] = effect

        # 添加到活跃观察者
        field.active_observers.add(observer)

        # 回调
        if self._on_message_observed:
            await self._on_message_observed(effect)

        # 触发坍缩（获取内容）
        return await self._collapse_message(message_id, observer)

    async def _collapse_message(
        self,
        message_id: str,
        observer_id: str,
    ) -> ObserverEffect:
        """
        消息坍缩（实例化）

        只有观察时才传输实际内容
        """
        effect = self.observer_states.get(f"{message_id}:{observer_id}")
        if not effect:
            return effect

        # 获取内容
        if self._storage_func:
            try:
                data = await self._storage_func(message_id, None)
                if data:
                    effect.content = data.get("content")
                    effect.collapsed = True
                    effect.collapsed_at = time.time()
            except Exception:
                pass

        # 更新观察者状态
        effect.collapsed = True
        effect.collapsed_at = time.time()

        # 回调
        if self._on_message_collapsed:
            await self._on_message_collapsed(effect)

        return effect

    async def _request_remote_collapse(
        self,
        message_id: str,
        observer_id: str,
    ) -> ObserverEffect:
        """请求远程坍缩"""
        effect = ObserverEffect(
            message_id=message_id,
            observer_id=observer_id,
        )

        # 发送请求到持有消息的节点
        if self._send_func:
            try:
                response = await self._send_func("any", {
                    "type": "holographic_request",
                    "message_id": message_id,
                    "observer": observer_id,
                })

                if response:
                    effect.content = response.get("content")
                    effect.collapsed = True
                    effect.collapsed_at = time.time()
            except Exception:
                pass

        return effect

    # ========== 消息接收 ==========

    async def receive_announcement(self, announcement: dict):
        """接收消息存在公告"""
        message_id = announcement.get("message_id")
        content_hash = announcement.get("content_hash")
        metadata = announcement.get("metadata", {})
        field_type = announcement.get("field_type", "global")

        # 检查是否已存在
        if message_id in self.active_fields:
            return

        # 创建场条目（只有元数据，没有内容）
        field = MessageField(
            field_id=message_id,
            field_type=field_type,
            content_hash=content_hash,
            metadata=metadata,
        )

        self.active_fields[message_id] = field

        # 回调
        if self._on_message_projected:
            await self._on_message_projected(message_id, field)

    async def receive_content(self, message_id: str, content: Any):
        """接收消息内容"""
        # 更新存储
        if self._storage_func:
            await self._storage_func(message_id, {"content": content})

    # ========== 消息场查询 ==========

    def get_field(self, message_id: str) -> Optional[MessageField]:
        """获取消息场"""
        return self.active_fields.get(message_id)

    def list_fields(self, field_type: Optional[str] = None) -> List[MessageField]:
        """列出消息场"""
        if field_type:
            return [f for f in self.active_fields.values() if f.field_type == field_type]
        return list(self.active_fields.values())

    def get_observer_count(self, message_id: str) -> int:
        """获取观察者数量"""
        field = self.active_fields.get(message_id)
        if field:
            return len(field.active_observers)
        return 0

    # ========== 辅助 ==========

    def _hash_content(self, content: Any) -> str:
        """计算内容哈希"""
        import json
        data = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "active_fields": len(self.active_fields),
            "total_observers": sum(
                len(f.active_observers)
                for f in self.active_fields.values()
            ),
            "collapsed_messages": sum(
                1 for e in self.observer_states.values()
                if e.collapsed
            ),
            "fields": [
                {
                    "id": f.field_id,
                    "type": f.field_type,
                    "observers": len(f.active_observers),
                }
                for f in list(self.active_fields.values())[:5]
            ],
        }


# 全局单例
_holographic_instance: Optional[HolographicMessage] = None


def get_holographic_messaging(node_id: str = "local") -> HolographicMessage:
    """获取全息通信单例"""
    global _holographic_instance
    if _holographic_instance is None:
        _holographic_instance = HolographicMessage(node_id)
    return _holographic_instance