"""
Media Sync Protocol - 媒体同步协议
==================================

功能：
- 逻辑时钟同步
- 媒体时钟同步
- 多源时钟校准
- 定期同步

Author: LivingTreeAI Community
"""

import asyncio
import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, List, Dict
from enum import Enum


class SyncSource(Enum):
    """同步源类型"""
    MASTER = "master"      # 主播（权威源）
    RELAY = "relay"       # 中继节点
    PEER = "peer"         # 对等节点


@dataclass
class ClockSync:
    """时钟同步状态"""
    source: str
    source_type: SyncSource
    offset_ms: float = 0  # 偏移量
    round_trip_ms: float = 0  # 往返延迟
    last_sync: float = 0
    accuracy: float = 0  # 精度估计


class MediaSyncProtocol:
    """
    媒体同步协议

    功能：
    1. 主时钟获取
    2. 时钟偏移计算
    3. 平滑同步
    4. 多源校准
    """

    # 配置
    SYNC_INTERVAL_MS = 5000  # 同步间隔
    SMOOTHING_FACTOR = 0.1  # 平滑因子
    MAX_SOURCES = 5  # 最大同步源数

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 媒体时钟
        self.media_clock_ms = 0  # 毫秒
        self.wall_clock_offset = 0  # 墙钟偏移

        # 同步状态
        self.master_clock_source: Optional[str] = None
        self.peer_clocks: Dict[str, ClockSync] = {}
        self.sync_sources: List[str] = []

        # 网络函数
        self._send_func = send_func

        # 任务
        self._sync_task: Optional[asyncio.Task] = None

    # ========== 同步控制 ==========

    async def start_sync(self):
        """启动同步"""
        if self._sync_task:
            return

        self._sync_task = asyncio.create_task(self._sync_loop())

    async def stop_sync(self):
        """停止同步"""
        if self._sync_task:
            self._sync_task.cancel()
            self._sync_task = None

    async def _sync_loop(self):
        """同步循环"""
        while True:
            try:
                await asyncio.sleep(self.SYNC_INTERVAL_MS / 1000)
                await self.periodic_sync()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def periodic_sync(self):
        """定期同步"""
        for source in self.sync_sources[:self.MAX_SOURCES]:
            try:
                await self._sync_with_source(source)
            except Exception:
                pass

    async def _sync_with_source(self, source: str) -> bool:
        """与指定源同步"""
        if not self._send_func:
            return False

        t0 = time.time()

        # 发送时间请求
        try:
            response = await self._send_func(source, {
                "type": "time_sync_request",
                "client_ts": int(t0 * 1000),
                "node_id": self.node_id,
            })
        except Exception:
            return False

        t4 = time.time()

        if not response:
            return False

        # 计算偏移
        t1 = response.get("server_ts_1", 0)  # 请求到达服务器
        t2 = response.get("server_ts_2", 0)  # 响应发送时间
        t3 = response.get("client_ts", 0)     # 客户端接收时间

        if t1 == 0 or t2 == 0 or t3 == 0:
            return False

        # NTP 风格计算
        round_trip = (t4 - t0) * 1000
        server_processing = (t2 - t1)
        offset = ((t1 - t0) + (t2 - t3)) / 2 * 1000

        # 更新同步状态
        clock_sync = ClockSync(
            source=source,
            source_type=SyncSource.PEER,
            offset_ms=offset,
            round_trip_ms=round_trip,
            last_sync=time.time(),
            accuracy=round_trip / 2,
        )
        self.peer_clocks[source] = clock_sync

        # 平滑调整
        self._smooth_adjust(offset)

        return True

    def _smooth_adjust(self, offset_ms: float):
        """平滑调整时钟"""
        # 使用滑动平均
        if self.wall_clock_offset == 0:
            self.wall_clock_offset = offset_ms
        else:
            self.wall_clock_offset = (
                self.wall_clock_offset * (1 - self.SMOOTHING_FACTOR) +
                offset_ms * self.SMOOTHING_FACTOR
            )

    # ========== 时间获取 ==========

    def get_synchronized_time_ms(self) -> float:
        """获取同步后的时间（毫秒）"""
        return time.time() * 1000 + self.wall_clock_offset

    def get_media_time_ms(self) -> float:
        """获取媒体时间"""
        return self.media_clock_ms + self.get_synchronized_time_ms()

    def update_media_clock(self, clock_ms: float):
        """更新媒体时钟"""
        self.media_clock_ms = clock_ms

    def advance_media_clock(self, delta_ms: float):
        """推进媒体时钟"""
        self.media_clock_ms += delta_ms

    # ========== 主时钟 ==========

    async def set_master_clock(self, master_id: str):
        """设置主时钟源"""
        self.master_clock_source = master_id

    async def get_master_clock(self) -> Optional[float]:
        """获取主时钟时间"""
        if not self.master_clock_source:
            return self.get_synchronized_time_ms()

        if not self._send_func:
            return None

        try:
            response = await self._send_func(self.master_clock_source, {
                "type": "get_master_clock",
                "node_id": self.node_id,
            })
            if response:
                return response.get("clock_ms")
        except Exception:
            pass

        return None

    # ========== 序列号 ==========

    def get_next_sequence(self) -> int:
        """获取下一个序列号"""
        return int(self.get_synchronized_time_ms())

    # ========== 同步源管理 ==========

    def add_sync_source(self, source: str):
        """添加同步源"""
        if source not in self.sync_sources:
            self.sync_sources.append(source)

    def remove_sync_source(self, source: str):
        """移除同步源"""
        if source in self.sync_sources:
            self.sync_sources.remove(source)

    def get_sync_stats(self) -> dict:
        """获取同步统计"""
        return {
            "offset_ms": self.wall_clock_offset,
            "media_clock_ms": self.media_clock_ms,
            "master_source": self.master_clock_source,
            "peer_sources": len(self.peer_clocks),
            "sync_sources": self.sync_sources,
        }


# 全局单例
_sync_instance: Optional[MediaSyncProtocol] = None


def get_media_sync(node_id: str = "local") -> MediaSyncProtocol:
    """获取媒体同步协议单例"""
    global _sync_instance
    if _sync_instance is None:
        _sync_instance = MediaSyncProtocol(node_id)
    return _sync_instance