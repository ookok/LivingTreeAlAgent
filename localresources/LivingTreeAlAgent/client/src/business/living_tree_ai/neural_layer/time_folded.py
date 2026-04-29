"""
Time-Folded Messaging - 时间折叠通信
=====================================

消息可以指定在未来特定时间"展开"，或在时间流速不同的节点间同步

核心概念：
- 时间胶囊 (Time Capsule)
- 时间膨胀同步 (Time Dilation Sync)
- 延迟展开 (Delayed Unwrap)

Author: LivingTreeAI Community
"""

import asyncio
import time
import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any, Dict, List
from enum import Enum


class TimeCapsuleStatus(Enum):
    """时间胶囊状态"""
    SEALED = "sealed"       # 已密封
    WAITING = "waiting"     # 等待解锁
    DELIVERED = "delivered"  # 已送达
    EXPIRED = "expired"     # 已过期


@dataclass
class TimeCapsule:
    """
    时间胶囊

    消息被加密封装，在指定时间自动解锁
    """
    capsule_id: str
    recipient: str
    sender: str

    # 时间设置
    created_at: float
    unlock_time: float  # 解锁时间（Unix时间戳）
    expires_at: float   # 过期时间

    # 内容（密封后不可读）
    encrypted_content: Optional[bytes] = None
    content_hash: str = ""

    # 状态
    status: TimeCapsuleStatus = TimeCapsuleStatus.SEALED

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_ready(self) -> bool:
        """是否准备好解锁"""
        return (
            self.status == TimeCapsuleStatus.WAITING and
            time.time() >= self.unlock_time
        )

    def is_expired(self) -> bool:
        """是否已过期"""
        return time.time() > self.expires_at


@dataclass
class TimeDilationSync:
    """
    时间膨胀同步

    用于与"思考加速"或"思考减速"的节点同步
    """
    peer_id: str
    time_dilation_factor: float  # 1.0 = 正常，10.0 = 对端思考快10倍

    # 同步状态
    last_sync: float = 0
    sync_offset: float = 0
    sync_accuracy: float = 1.0


class TimeFoldedMessage:
    """
    时间折叠消息

    功能：
    1. 时间胶囊消息
    2. 时间膨胀同步
    3. 未来消息预排
    """

    # 配置
    CAPSULE_CHECK_INTERVAL_MS = 1000  # 胶囊检查间隔
    MAX_ACTIVE_CAPSULES = 100
    DEFAULT_EXPIRY_SECONDS = 86400 * 7  # 7天

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
        storage_func: Optional[Callable[[str, Any], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 时间胶囊
        self.capsules: Dict[str, TimeCapsule] = {}
        self.sent_capsules: Dict[str, TimeCapsule] = {}

        # 时间膨胀同步
        self.dilation_syncs: Dict[str, TimeDilationSync] = {}

        # 网络函数
        self._send_func = send_func
        self._storage_func = storage_func

        # 任务
        self._check_task: Optional[asyncio.Task] = None
        self._running = False

        # 回调
        self._on_capsule_ready: Optional[Callable] = None
        self._on_capsule_received: Optional[Callable] = None

    # ========== 时间胶囊 ==========

    async def create_capsule(
        self,
        recipient: str,
        content: Any,
        delivery_time: Optional[float] = None,
        delay_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        创建时间胶囊

        Args:
            recipient: 收件人
            content: 内容
            delivery_time: 精确送达时间（Unix时间戳）
            delay_seconds: 延迟秒数（与delivery_time二选一）
            metadata: 元数据

        Returns:
            胶囊ID
        """
        capsule_id = f"capsule_{uuid.uuid4().hex[:16]}"

        # 确定送达时间
        now = time.time()
        if delivery_time:
            unlock_time = delivery_time
        elif delay_seconds:
            unlock_time = now + delay_seconds
        else:
            unlock_time = now + 60  # 默认1分钟后

        # 确定过期时间
        expires_at = unlock_time + self.DEFAULT_EXPIRY_SECONDS

        # 加密内容（简化实现）
        encrypted = self._encrypt_content(content)

        # 创建胶囊
        capsule = TimeCapsule(
            capsule_id=capsule_id,
            recipient=recipient,
            sender=self.node_id,
            created_at=now,
            unlock_time=unlock_time,
            expires_at=expires_at,
            encrypted_content=encrypted,
            content_hash=self._hash_content(content),
            status=TimeCapsuleStatus.SEALED,
            metadata=metadata or {},
        )

        self.capsules[capsule_id] = capsule
        self.sent_capsules[capsule_id] = capsule

        # 存储
        if self._storage_func:
            await self._storage_func(capsule_id, capsule)

        # 发送到网络
        await self._send_capsule_to_network(capsule)

        # 设置状态为等待
        capsule.status = TimeCapsuleStatus.WAITING

        return capsule_id

    def _encrypt_content(self, content: Any) -> bytes:
        """加密内容（简化实现）"""
        import json
        data = json.dumps(content, default=str).encode()
        # 简化：使用内容哈希作为"加密"
        return data

    def _decrypt_content(self, encrypted: bytes) -> Any:
        """解密内容"""
        import json
        return json.loads(encrypted.decode())

    def _hash_content(self, content: Any) -> str:
        """计算内容哈希"""
        import json
        data = json.dumps(content, sort_keys=True, default=str).encode()
        return hashlib.sha256(data).hexdigest()[:16]

    async def _send_capsule_to_network(self, capsule: TimeCapsule):
        """发送胶囊到网络"""
        if self._send_func:
            # 发送到分布式时间网络
            await self._send_func("time_network", {
                "type": "capsule_sealed",
                "capsule": {
                    "capsule_id": capsule.capsule_id,
                    "recipient": capsule.recipient,
                    "sender": capsule.sender,
                    "unlock_time": capsule.unlock_time,
                    "expires_at": capsule.expires_at,
                    "content_hash": capsule.content_hash,
                    "metadata": capsule.metadata,
                },
            })

    # ========== 胶囊接收 ==========

    async def receive_capsule(self, capsule_data: dict):
        """接收胶囊"""
        capsule_id = capsule_data.get("capsule_id")

        # 检查是否已存在
        if capsule_id in self.capsules:
            return

        capsule = TimeCapsule(
            capsule_id=capsule_id,
            recipient=capsule_data.get("recipient"),
            sender=capsule_data.get("sender"),
            created_at=capsule_data.get("created_at", time.time()),
            unlock_time=capsule_data.get("unlock_time"),
            expires_at=capsule_data.get("expires_at"),
            content_hash=capsule_data.get("content_hash", ""),
            status=TimeCapsuleStatus.WAITING,
            metadata=capsule_data.get("metadata", {}),
        )

        self.capsules[capsule_id] = capsule

    async def deliver_capsule_content(self, capsule_id: str, content: Any):
        """交付胶囊内容"""
        capsule = self.capsules.get(capsule_id)
        if not capsule:
            return

        # 更新状态
        capsule.status = TimeCapsuleStatus.DELIVERED

        # 回调
        if self._on_capsule_received:
            await self._on_capsule_received(capsule, content)

    # ========== 胶囊解锁检查 ==========

    async def start_capsule_checker(self):
        """启动胶囊检查任务"""
        self._running = True
        self._check_task = asyncio.create_task(self._capsule_check_loop())

    async def stop_capsule_checker(self):
        """停止胶囊检查"""
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            self._check_task = None

    async def _capsule_check_loop(self):
        """胶囊检查循环"""
        while self._running:
            try:
                await asyncio.sleep(self.CAPSULE_CHECK_INTERVAL_MS / 1000)

                now = time.time()

                # 检查每个胶囊
                for capsule_id, capsule in list(self.capsules.items()):
                    if capsule.status != TimeCapsuleStatus.WAITING:
                        continue

                    # 检查是否过期
                    if capsule.is_expired():
                        capsule.status = TimeCapsuleStatus.EXPIRED
                        continue

                    # 检查是否准备好解锁
                    if capsule.is_ready():
                        await self._unlock_capsule(capsule)

            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _unlock_capsule(self, capsule: TimeCapsule):
        """解锁胶囊"""
        # 获取内容
        if self._storage_func and not capsule.encrypted_content:
            data = await self._storage_func(capsule.capsule_id, None)
            if data:
                capsule.encrypted_content = data.get("encrypted_content")

        # 解密
        if capsule.encrypted_content:
            content = self._decrypt_content(capsule.encrypted_content)
        else:
            content = None

        # 更新状态
        capsule.status = TimeCapsuleStatus.DELIVERED

        # 回调
        if self._on_capsule_ready:
            await self._on_capsule_ready(capsule, content)

    # ========== 时间膨胀同步 ==========

    async def establish_dilation_sync(
        self,
        peer_id: str,
        dilation_factor: float,
    ) -> TimeDilationSync:
        """
        建立时间膨胀同步

        Args:
            peer_id: 对端节点
            dilation_factor: 时间膨胀因子
                - 1.0 = 正常时间
                - 10.0 = 对端思考快10倍（主观时间×10）
                - 0.1 = 对端思考慢10倍

        Returns:
            同步状态
        """
        sync = TimeDilationSync(
            peer_id=peer_id,
            time_dilation_factor=dilation_factor,
        )

        self.dilation_syncs[peer_id] = sync

        return sync

    def adjust_for_dilation(self, peer_id: str, local_time_ms: float) -> float:
        """
        调整时间以适应时间膨胀

        Args:
            peer_id: 对端节点
            local_time_ms: 本地时间（毫秒）

        Returns:
            调整后的时间
        """
        sync = self.dilation_syncs.get(peer_id)
        if not sync:
            return local_time_ms

        # 根据膨胀因子调整
        # 如果对端思考快(10x)，我们需要"减速"发送
        adjusted = local_time_ms * sync.time_dilation_factor
        return adjusted

    def compress_for_fast_peer(self, peer_id: str, content: Any) -> Any:
        """
        为"思考快"的节点压缩信息

        他们能在更短时间内处理更多信息
        """
        sync = self.dilation_syncs.get(peer_id)
        if not sync or sync.time_dilation_factor <= 1.0:
            return content

        # 简化：返回原始内容
        # 实际可以返回更详细的版本
        return content

    def expand_for_slow_peer(self, peer_id: str, content: Any) -> Any:
        """
        为"思考慢"的节点扩展信息

        需要更简洁的摘要
        """
        sync = self.dilation_syncs.get(peer_id)
        if not sync or sync.time_dilation_factor >= 1.0:
            return content

        # 简化：返回原始内容
        return content

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取统计"""
        waiting = sum(1 for c in self.capsules.values() if c.status == TimeCapsuleStatus.WAITING)
        delivered = sum(1 for c in self.capsules.values() if c.status == TimeCapsuleStatus.DELIVERED)

        return {
            "total_capsules": len(self.capsules),
            "waiting": waiting,
            "delivered": delivered,
            "active_dilation_syncs": len(self.dilation_syncs),
            "capsules": [
                {
                    "id": c.capsule_id,
                    "recipient": c.recipient,
                    "status": c.status.value,
                    "unlock_in": max(0, c.unlock_time - time.time()),
                }
                for c in list(self.capsules.values())[:5]
            ],
        }


# 全局单例
_time_folded_instance: Optional[TimeFoldedMessage] = None


def get_time_folded_messaging(node_id: str = "local") -> TimeFoldedMessage:
    """获取时间折叠消息单例"""
    global _time_folded_instance
    if _time_folded_instance is None:
        _time_folded_instance = TimeFoldedMessage(node_id)
    return _time_folded_instance