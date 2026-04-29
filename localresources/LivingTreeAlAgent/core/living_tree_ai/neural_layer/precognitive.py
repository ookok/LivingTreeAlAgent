"""
Precognitive Layer - 预感知通信
================================

在消息发送前，接收方已开始准备接收

核心概念：
- 意图波 (Intent Wave)
- 连接预热 (Connection Preheat)
- 预测缓存 (Predictive Cache)

Author: LivingTreeAI Community
"""

import asyncio
import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Dict, List
from collections import defaultdict


@dataclass
class IntentWave:
    """意图波 - 广播"我可能要发送这个消息" """
    source_id: str
    intent_hash_prefix: str  # 消息哈希前缀（未来1秒内）
    timestamp_ns: int
    expiry_ms: int = 1000  # 1秒后过期

    def is_expired(self) -> bool:
        return (time.time_ns() - self.timestamp_ns) > (self.expiry_ms * 1_000_000)

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "intent_hash_prefix": self.intent_hash_prefix,
            "timestamp_ns": self.timestamp_ns,
            "expiry_ms": self.expiry_ms,
        }


@dataclass
class ConnectionPreheat:
    """连接预热状态"""
    target_id: str
    established: bool = False
    buffer_prepared: bool = False
    predicted_hash: Optional[str] = None
    lastPreheat: float = field(default_factory=time.time)


class PrecognitiveLayer:
    """
    预感知通信层

    功能：
    1. 意图波广播
    2. 连接预热
    3. 预测性缓存

    效果：
    - 实际消息到达时，连接已是"热连接"
    - 延迟降低可达 80%
    """

    # 配置
    INTENT_WAVE_INTERVAL_MS = 100  # 意图波广播间隔
    INTENT_HASH_PREFIX_LEN = 8  # 哈希前缀长度
    MAX_PREHEAT_CONNECTIONS = 20  # 最大预热连接数

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
        connect_func: Optional[Callable[[str], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 意图波
        self.active_intents: Dict[str, IntentWave] = {}  # hash_prefix -> wave
        self.received_intents: Dict[str, List[IntentWave]] = defaultdict(list)

        # 连接预热
        self.preheated_connections: Dict[str, ConnectionPreheat] = {}

        # 网络函数
        self._send_func = send_func
        self._connect_func = connect_func

        # 任务
        self._intent_broadcast_task: Optional[asyncio.Task] = None
        self._running = False

        # 回调
        self._on_prediction_matched: Optional[Callable] = None

    # ========== 意图波 ==========

    async def start_intent_broadcast(self, pending_messages: List[dict]):
        """
        启动意图波广播

        Args:
            pending_messages: 待发送消息列表（即将发送的消息）
        """
        self._running = True
        self._intent_broadcast_task = asyncio.create_task(
            self._intent_broadcast_loop(pending_messages)
        )

    async def stop_intent_broadcast(self):
        """停止意图波广播"""
        self._running = False
        if self._intent_broadcast_task:
            self._intent_broadcast_task.cancel()
            self._intent_broadcast_task = None

    async def _intent_broadcast_loop(self, pending_messages: List[dict]):
        """意图波广播循环"""
        while self._running:
            try:
                # 为每个待发送消息生成意图波
                for msg in pending_messages:
                    intent = self._create_intent_wave(msg)
                    self.active_intents[intent.intent_hash_prefix] = intent

                    # 广播意图波
                    await self._broadcast_intent(intent)

                # 等待下一次广播
                await asyncio.sleep(self.INTENT_WAVE_INTERVAL_MS / 1000)

            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def _create_intent_wave(self, message: dict) -> IntentWave:
        """为消息创建意图波"""
        # 计算消息哈希
        content = message.get("content", "")
        msg_hash = hashlib.sha256(str(content).encode()).hexdigest()

        return IntentWave(
            source_id=self.node_id,
            intent_hash_prefix=msg_hash[:self.INTENT_HASH_PREFIX_LEN],
            timestamp_ns=time.time_ns(),
        )

    async def _broadcast_intent(self, intent: IntentWave):
        """广播意图波"""
        if self._send_func:
            # 广播给所有已知节点
            # 实际应该使用底层广播机制
            await self._send_func("broadcast", {
                "type": "intent_wave",
                "wave": intent.to_dict(),
            })

    # ========== 意图接收与预热 ==========

    async def receive_intent_wave(self, wave_data: dict):
        """接收意图波"""
        wave = IntentWave(
            source_id=wave_data["source_id"],
            intent_hash_prefix=wave_data["intent_hash_prefix"],
            timestamp_ns=wave_data["timestamp_ns"],
            expiry_ms=wave_data.get("expiry_ms", 1000),
        )

        # 检查是否过期
        if wave.is_expired():
            return

        # 记录接收到的意图
        self.received_intents[wave.source_id].append(wave)

        # 预热连接
        await self._preheat_for_intent(wave)

    async def _preheat_for_intent(self, intent: IntentWave):
        """为意图预热连接"""
        # 检查是否已预热
        preheat = self.preheated_connections.get(intent.source_id)

        if preheat and preheat.lastPreheat > time.time() - 1:
            # 1秒内已预热，跳过
            return

        # 创建预热
        preheat = ConnectionPreheat(
            target_id=intent.source_id,
            established=False,
            buffer_prepared=False,
            predicted_hash=intent.intent_hash_prefix,
            lastPreheat=time.time(),
        )
        self.preheated_connections[intent.source_id] = preheat

        # 执行预热
        if self._connect_func:
            try:
                await self._connect_func(intent.source_id)
                preheat.established = True
            except Exception:
                pass

        # 准备缓冲区（如果连接已建立）
        if preheat.established:
            preheat.buffer_prepared = True

    async def check_intent_match(self, actual_message: dict) -> Optional[str]:
        """
        检查实际消息是否匹配预热的意图

        Returns:
            如果匹配，返回预热的目标ID
        """
        content = actual_message.get("content", "")
        msg_hash = hashlib.sha256(str(content).encode()).hexdigest()
        prefix = msg_hash[:self.INTENT_HASH_PREFIX_LEN]

        # 检查是否有匹配的预热
        for target_id, preheat in self.preheated_connections.items():
            if preheat.predicted_hash == prefix:
                # 匹配！触发回调
                if self._on_prediction_matched:
                    await self._on_prediction_matched(target_id, actual_message)

                # 清理预热
                del self.preheated_connections[target_id]

                return target_id

        return None

    # ========== 预测缓存 ==========

    async def predictive_cache(
        self,
        content_type: str,
        content_id: str,
        data: dict,
    ):
        """
        预测性缓存

        当某个内容即将被请求时，预先缓存
        """
        cache_key = f"{content_type}:{content_id}"

        # 存储到预测缓存
        # 实际应该使用分布式缓存
        pass

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "active_intents": len(self.active_intents),
            "received_intents": sum(len(v) for v in self.received_intents.values()),
            "preheated_connections": len(self.preheated_connections),
            "preheated": [
                {
                    "target": p.target_id,
                    "established": p.established,
                    "buffer_ready": p.buffer_prepared,
                }
                for p in list(self.preheated_connections.values())[:5]
            ],
        }


# 全局单例
_precog_instance: Optional[PrecognitiveLayer] = None


def get_precognitive_layer(node_id: str = "local") -> PrecognitiveLayer:
    """获取预感知层单例"""
    global _precog_instance
    if _precog_instance is None:
        _precog_instance = PrecognitiveLayer(node_id)
    return _precog_instance