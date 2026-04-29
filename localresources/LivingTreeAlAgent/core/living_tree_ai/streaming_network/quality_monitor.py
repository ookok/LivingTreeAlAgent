"""
Quality Monitor - 质量监控与自适应
===================================

功能：
- 实时质量指标收集
- 自适应码率调整
- 拓扑自适应
- 告警与恢复

Author: LivingTreeAI Community
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, List, Dict
from enum import Enum


class AdaptationAction(Enum):
    """自适应动作"""
    INCREASE_BITRATE = "increase_bitrate"
    DECREASE_BITRATE = "decrease_bitrate"
    CHANGE_PARENT = "change_parent"
    SWITCH_TO_MESH = "switch_to_mesh"
    REQUEST_KEYFRAME = "request_keyframe"
    ENABLE_FEC = "enable_fec"
    DISABLE_FEC = "disable_fec"


@dataclass
class QualityMetrics:
    """质量指标"""
    timestamp: float = field(default_factory=time.time)

    # 码率
    bitrate_kbps: int = 0
    target_bitrate_kbps: int = 0

    # 帧率
    fps: float = 0
    target_fps: int = 30

    # 网络
    packet_loss: float = 0  # 丢包率 0-1
    latency_ms: float = 0
    jitter_ms: float = 0

    # 缓冲
    buffer_ms: float = 0
    stall_count: int = 0

    # 综合
    quality_score: float = 1.0  # 0-1


class StreamQualityMonitor:
    """
    流质量监控与自适应

    功能：
    1. 实时指标收集
    2. 质量评估
    3. 自适应调整
    4. 异常告警
    """

    # 配置
    MONITOR_INTERVAL_MS = 1000
    BITRATE_INCREASE_THRESHOLD = 0.01  # 丢包率 < 1%
    BITRATE_DECREASE_THRESHOLD = 0.1  # 丢包率 > 10%
    LATENCY_THRESHOLD_MS = 300
    QUALITY_LOW_THRESHOLD = 0.5
    QUALITY_HIGH_THRESHOLD = 0.8

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 指标历史
        self.metrics_history: List[QualityMetrics] = []
        self.max_history = 60  # 保留60秒历史

        # 当前指标
        self.current_metrics = QualityMetrics()

        # 配置
        self.min_bitrate = 500
        self.max_bitrate = 8000
        self.default_bitrate = 2000

        # 网络函数
        self._send_func = send_func

        # 回调
        self._on_adaptation: Optional[Callable] = None
        self._on_quality_degraded: Optional[Callable] = None
        self._on_quality_recovered: Optional[Callable] = None

        # 任务
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

        # 上一次动作（避免频繁调整）
        self._last_action_time = 0
        self._last_action: Optional[AdaptationAction] = None
        self._action_cooldown = 5.0  # 5秒冷却

    # ========== 监控控制 ==========

    async def start(self):
        """启动监控"""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """停止监控"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None

    async def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                await asyncio.sleep(self.MONITOR_INTERVAL_MS / 1000)

                # 收集指标
                await self._collect_metrics()

                # 评估质量
                await self._evaluate_quality()

                # 自适应调整
                await self._adaptive_adjustment()

            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _collect_metrics(self):
        """收集质量指标"""
        # 简化实现：需要连接到实际媒体引擎获取指标
        # 这里使用模拟数据

        metrics = QualityMetrics(
            timestamp=time.time(),
            bitrate_kbps=self.current_metrics.bitrate_kbps or self.default_bitrate,
            target_bitrate_kbps=self.default_bitrate,
            fps=30,
            target_fps=30,
            packet_loss=0.01,
            latency_ms=50,
            jitter_ms=10,
            buffer_ms=1000,
            stall_count=0,
        )

        self.current_metrics = metrics

        # 添加到历史
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > self.max_history:
            self.metrics_history.pop(0)

    async def _evaluate_quality(self):
        """评估质量"""
        m = self.current_metrics

        # 计算综合质量分数
        score = 1.0

        # 丢包影响（最关键）
        score *= (1 - m.packet_loss * 5)  # 10%丢包 → 0.5分

        # 延迟影响
        if m.latency_ms > self.LATENCY_THRESHOLD_MS:
            score *= 0.7

        # 帧率影响
        if m.fps < m.target_fps * 0.8:
            score *= 0.8

        # 缓冲影响
        if m.buffer_ms < 1000:
            score *= 0.9
        if m.stall_count > 0:
            score *= (1 - min(m.stall_count * 0.1, 0.5))

        self.current_metrics.quality_score = max(0, min(1, score))

    async def _adaptive_adjustment(self):
        """自适应调整"""
        # 检查冷却
        if time.time() - self._last_action_time < self._action_cooldown:
            return

        m = self.current_metrics
        actions_needed: List[AdaptationAction] = []

        # 1. 丢包自适应码率
        if m.packet_loss > self.BITRATE_DECREASE_THRESHOLD:
            # 高丢包，降低码率
            new_bitrate = int(m.bitrate_kbps * 0.8)
            new_bitrate = max(self.min_bitrate, new_bitrate)
            actions_needed.append(AdaptationAction.DECREASE_BITRATE)

        elif m.packet_loss < self.BITRATE_INCREASE_THRESHOLD and m.bitrate_kbps < self.max_bitrate:
            # 低丢包，尝试提高码率
            new_bitrate = int(m.bitrate_kbps * 1.2)
            new_bitrate = min(self.max_bitrate, new_bitrate)
            actions_needed.append(AdaptationAction.INCREASE_BITRATE)

        # 2. 高延迟切换拓扑
        if m.latency_ms > self.LATENCY_THRESHOLD_MS:
            actions_needed.append(AdaptationAction.CHANGE_PARENT)

        # 3. 质量过低告警
        if m.quality_score < self.QUALITY_LOW_THRESHOLD:
            if self._on_quality_degraded:
                await self._on_quality_degraded(m)

        elif m.quality_score > self.QUALITY_HIGH_THRESHOLD:
            if self._on_quality_recovered:
                await self._on_quality_recovered(m)

        # 执行动作
        if actions_needed:
            action = actions_needed[0]  # 优先执行第一个
            await self._execute_action(action)

    async def _execute_action(self, action: AdaptationAction):
        """执行自适应动作"""
        self._last_action = action
        self._last_action_time = time.time()

        if action == AdaptationAction.DECREASE_BITRATE:
            m = self.current_metrics
            new_bitrate = int(m.bitrate_kbps * 0.8)
            self.current_metrics.bitrate_kbps = max(self.min_bitrate, new_bitrate)

        elif action == AdaptationAction.INCREASE_BITRATE:
            m = self.current_metrics
            new_bitrate = int(m.bitrate_kbps * 1.2)
            self.current_metrics.bitrate_kbps = min(self.max_bitrate, new_bitrate)

        elif action == AdaptationAction.REQUEST_KEYFRAME:
            await self._request_keyframe()

        elif action == AdaptationAction.ENABLE_FEC:
            # 启用前向纠错
            pass

        # 回调
        if self._on_adaptation:
            await self._on_adaptation(action, self.current_metrics)

    async def _request_keyframe(self):
        """请求关键帧"""
        if self._send_func:
            await self._send_func("parent", {
                "type": "request_keyframe",
                "node_id": self.node_id,
            })

    # ========== 外部指标更新 ==========

    def update_metrics(self, metrics: QualityMetrics):
        """外部更新指标"""
        self.current_metrics = metrics

        self.metrics_history.append(metrics)
        if len(self.metrics_history) > self.max_history:
            self.metrics_history.pop(0)

    def update_bitrate(self, bitrate_kbps: int):
        """更新码率"""
        self.current_metrics.bitrate_kbps = bitrate_kbps

    def update_latency(self, latency_ms: float):
        """更新延迟"""
        self.current_metrics.latency_ms = latency_ms

    def update_packet_loss(self, packet_loss: float):
        """更新丢包率"""
        self.current_metrics.packet_loss = packet_loss

    # ========== 质量查询 ==========

    def get_current_quality(self) -> QualityMetrics:
        """获取当前质量"""
        return self.current_metrics

    def get_average_quality(self, duration_seconds: int = 10) -> float:
        """获取平均质量"""
        cutoff = time.time() - duration_seconds
        recent = [m.quality_score for m in self.metrics_history if m.timestamp > cutoff]
        if not recent:
            return 1.0
        return sum(recent) / len(recent)

    def get_bitrate_recommendation(self) -> int:
        """获取推荐码率"""
        m = self.current_metrics

        if m.packet_loss > 0.1:
            return max(self.min_bitrate, int(m.bitrate_kbps * 0.7))
        elif m.packet_loss > 0.05:
            return max(self.min_bitrate, int(m.bitrate_kbps * 0.85))
        elif m.packet_loss < 0.01 and m.latency_ms < 100:
            return min(self.max_bitrate, int(m.bitrate_kbps * 1.2))

        return m.bitrate_kbps

    # ========== 回调设置 ==========

    def set_adaptation_callback(self, callback: Callable):
        self._on_adaptation = callback

    def set_quality_degraded_callback(self, callback: Callable):
        self._on_quality_degraded = callback

    def set_quality_recovered_callback(self, callback: Callable):
        self._on_quality_recovered = callback

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取统计"""
        avg_quality = self.get_average_quality(30)

        return {
            "current": {
                "bitrate_kbps": self.current_metrics.bitrate_kbps,
                "fps": self.current_metrics.fps,
                "packet_loss": f"{self.current_metrics.packet_loss * 100:.1f}%",
                "latency_ms": self.current_metrics.latency_ms,
                "quality_score": f"{self.current_metrics.quality_score * 100:.1f}%",
            },
            "average": {
                "quality_30s": f"{avg_quality * 100:.1f}%",
            },
            "last_action": self._last_action.value if self._last_action else None,
            "history_length": len(self.metrics_history),
        }


# 全局单例
_quality_instance: Optional[StreamQualityMonitor] = None


def get_quality_monitor(node_id: str = "local") -> StreamQualityMonitor:
    """获取质量监控单例"""
    global _quality_instance
    if _quality_instance is None:
        _quality_instance = StreamQualityMonitor(node_id)
    return _quality_instance