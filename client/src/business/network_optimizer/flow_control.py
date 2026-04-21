"""
Adaptive Flow Control and Congestion Avoidance

自适应流量控制与拥塞避免
- 滑动窗口
- 拥塞检测
- 自适应调整
- 公平性保障
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from .models import Connection, CongestionLevel, ConnectionQuality


@dataclass
class AdaptiveFlowController:
    """
    自适应流量控制器
    
    Features:
    - Sliding window control
    - Congestion window (cwnd)
    - Adaptive adjustment
    - Fairness guarantee
    """
    
    initial_window: int = 10
    max_window: int = 1000
    min_window: int = 1
    
    # 每个连接的状态
    _conn_windows: dict[str, dict] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    
    def _get_or_create_window(self, conn_id: str) -> dict:
        """获取或创建连接窗口状态"""
        if conn_id not in self._conn_windows:
            self._conn_windows[conn_id] = {
                "cwnd": self.initial_window,  # 拥塞窗口
                "ssthresh": 64,  # 慢启动阈值
                "in_flight": 0,  # 在飞包数
                "last_update": time.time(),
                "state": "slow_start",  # slow_start, congestion_avoidance
                "duplicate_acks": 0,
            }
        return self._conn_windows[conn_id]
    
    async def can_send(self, conn: Connection) -> bool:
        """
        检查是否可以发送数据
        
        Args:
            conn: 连接对象
            
        Returns:
            bool: 是否可以发送
        """
        async with self._lock:
            state = self._get_or_create_window(conn.conn_id)
            
            # 检查在飞包数是否小于窗口
            if state["in_flight"] >= state["cwnd"]:
                return False
            
            return True
    
    async def on_send(self, conn: Connection, bytes_sent: int):
        """
        发送数据后的回调
        
        Args:
            conn: 连接对象
            bytes_sent: 发送的字节数
        """
        async with self._lock:
            state = self._get_or_create_window(conn.conn_id)
            state["in_flight"] += 1
            state["last_update"] = time.time()
    
    async def on_ack(self, conn: Connection, ack_bytes: int):
        """
        收到ACK后的回调
        
        Args:
            conn: 连接对象
            ack_bytes: 确认的字节数
        """
        async with self._lock:
            state = self._get_or_create_window(conn.conn_id)
            state["in_flight"] = max(0, state["in_flight"] - 1)
            
            # 拥塞控制算法
            if state["state"] == "slow_start":
                # 慢启动：指数增长
                state["cwnd"] = min(
                    state["cwnd"] * 2,
                    state["ssthresh"]
                )
                if state["cwnd"] >= state["ssthresh"]:
                    state["state"] = "congestion_avoidance"
            else:
                # 拥塞避免：线性增长
                state["cwnd"] = min(
                    state["cwnd"] + 1,
                    self.max_window
                )
            
            state["last_update"] = time.time()
    
    async def on_loss(self, conn: Connection):
        """
        检测到丢包后的回调
        
        Args:
            conn: 连接对象
        """
        async with self._lock:
            state = self._get_or_create_window(conn.conn_id)
            
            # 快速重传/恢复
            state["ssthresh"] = max(state["cwnd"] // 2, self.min_window)
            state["cwnd"] = state["ssthresh"]
            state["state"] = "slow_start"
            state["in_flight"] = 0
            state["duplicate_acks"] = 0
    
    async def adjust_for_congestion(
        self,
        conn: Connection,
        congestion: 'CongestionInfo',
    ):
        """
        根据拥塞状态调整窗口
        
        Args:
            conn: 连接对象
            congestion: 拥塞信息
        """
        async with self._lock:
            state = self._get_or_create_window(conn.conn_id)
            
            if congestion.level == CongestionLevel.SEVERE:
                # 严重拥塞：大幅缩减
                state["cwnd"] = max(state["cwnd"] // 2, self.min_window)
                state["ssthresh"] = state["cwnd"]
            elif congestion.level == CongestionLevel.MODERATE:
                # 中度拥塞：适度缩减
                state["cwnd"] = max(state["cwnd"] // 2, self.min_window)
            elif congestion.level == CongestionLevel.MILD:
                # 轻度拥塞：暂停增长
                pass
            
            state["state"] = "slow_start"
    
    def get_window(self, conn_id: str) -> int:
        """获取连接窗口大小"""
        state = self._conn_windows.get(conn_id, {})
        return state.get("cwnd", self.initial_window)
    
    def get_state(self) -> dict:
        """获取流控状态"""
        total_window = sum(s["cwnd"] for s in self._conn_windows.values())
        return {
            "connections": len(self._conn_windows),
            "total_window": total_window,
            "avg_window": total_window / max(1, len(self._conn_windows)),
            "slow_start_count": sum(
                1 for s in self._conn_windows.values()
                if s["state"] == "slow_start"
            ),
        }


@dataclass
class CongestionInfo:
    """拥塞信息"""
    level: CongestionLevel
    rtt_ms: float = 0
    packet_loss_rate: float = 0
    bandwidth_mbps: float = 0
    queue_length: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class CongestionDetector:
    """
    拥塞检测器
    
    Features:
    - RTT detection
    - Packet loss detection
    - ECN support
    - Bandwidth estimation
    """
    
    # 历史数据
    _rtt_history: deque = field(default_factory=lambda: deque(maxlen=100))
    _loss_history: deque = field(default_factory=lambda: deque(maxlen=100))
    _bw_history: deque = field(default_factory=lambda: deque(maxlen=100))
    
    # 阈值
    RTT_MILD = 200  # ms
    RTT_MODERATE = 500  # ms
    RTT_SEVERE = 1000  # ms
    
    LOSS_MILD = 0.01  # 1%
    LOSS_MODERATE = 0.05  # 5%
    LOSS_SEVERE = 0.10  # 10%
    
    _last_detection: float = 0
    _detection_interval: float = 0.5  # 500ms
    
    async def detect(self, conn: Connection) -> CongestionInfo:
        """
        检测拥塞状态
        
        Args:
            conn: 连接对象
            
        Returns:
            CongestionInfo: 拥塞信息
        """
        now = time.time()
        if now - self._last_detection < self._detection_interval:
            return CongestionInfo(level=CongestionLevel.NONE)
        
        self._last_detection = now
        
        # 获取当前指标
        rtt = conn.info.avg_latency_ms
        loss = conn.info.packet_loss
        bw = await self._estimate_bandwidth(conn)
        
        # 记录历史
        self._rtt_history.append(rtt)
        self._loss_history.append(loss)
        self._bw_history.append(bw)
        
        # 判断拥塞等级
        level = self._calculate_level(rtt, loss, bw)
        
        return CongestionInfo(
            level=level,
            rtt_ms=rtt,
            packet_loss_rate=loss,
            bandwidth_mbps=bw,
        )
    
    def _calculate_level(
        self,
        rtt: float,
        loss: float,
        bw: float,
    ) -> CongestionLevel:
        """计算拥塞等级"""
        # 检查丢包
        if loss >= self.LOSS_SEVERE:
            return CongestionLevel.SEVERE
        elif loss >= self.LOSS_MODERATE:
            return CongestionLevel.MODERATE
        elif loss >= self.LOSS_MILD:
            return CongestionLevel.MILD
        
        # 检查RTT
        if rtt >= self.RTT_SEVERE:
            return CongestionLevel.SEVERE
        elif rtt >= self.RTT_MODERATE:
            return CongestionLevel.MODERATE
        elif rtt >= self.RTT_MILD:
            return CongestionLevel.MILD
        
        return CongestionLevel.NONE
    
    async def _estimate_bandwidth(self, conn: Connection) -> float:
        """估算带宽"""
        # 简单估算：基于吞吐量
        elapsed = time.time() - conn.info.created_at
        if elapsed <= 0:
            return 0
        
        bytes_total = conn.info.bytes_sent + conn.info.bytes_received
        bw_mbps = (bytes_total * 8) / (elapsed * 1_000_000)
        return bw_mbps
    
    async def detect_ecn(self, packet) -> bool:
        """
        检测ECN (Explicit Congestion Notification)
        
        Args:
            packet: 数据包
            
        Returns:
            bool: 是否检测到ECN
        """
        # 检查IP头部的ECN字段
        # ECN = 11 表示拥塞经历
        return getattr(packet, 'ecn', 0) == 3
    
    def get_rtt_trend(self) -> str:
        """获取RTT趋势"""
        if len(self._rtt_history) < 10:
            return "unknown"
        
        recent = list(self._rtt_history)[-10:]
        older = list(self._rtt_history)[-20:-10] if len(self._rtt_history) >= 20 else recent
        
        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older)
        
        if avg_recent > avg_older * 1.2:
            return "increasing"
        elif avg_recent < avg_older * 0.8:
            return "decreasing"
        else:
            return "stable"
    
    def get_state(self) -> dict:
        """获取检测器状态"""
        return {
            "rtt_avg": sum(self._rtt_history) / max(1, len(self._rtt_history)),
            "rtt_max": max(self._rtt_history) if self._rtt_history else 0,
            "rtt_trend": self.get_rtt_trend(),
            "loss_avg": sum(self._loss_history) / max(1, len(self._loss_history)),
            "bw_avg": sum(self._bw_history) / max(1, len(self._bw_history)),
            "sample_count": len(self._rtt_history),
        }
