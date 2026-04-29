"""
Neural Pulse Protocol - 神经脉冲协议
=====================================

模仿大脑神经元放电的通信协议

核心概念：
- 突触连接 (Synapse)
- 神经脉冲 (Neural Pulse)
- 动作电位 (Action Potential)
- 赫布学习 (Hebbian Learning)

Author: LivingTreeAI Community
"""

import asyncio
import time
import math
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, List, Dict, Set
from enum import Enum


class PulseType(Enum):
    """脉冲类型"""
    ALERT = "alert"           # 警报（高频，紧急）
    UPDATE = "update"          # 更新（正常）
    EMOTION = "emotion"       # 情感（携带情绪）
    REFLECT = "reflect"       # 反射（自动响应）
    SYNC = "sync"            # 同步
    INTENTION = "intention"   # 意图


@dataclass
class PulsePattern:
    """脉冲模式"""
    pulse_type: PulseType
    frequencies: List[float]  # 频率列表 (Hz)
    intensity: float = 1.0   # 强度 0-1
    duration_ms: float = 100  # 持续时间

    def to_dict(self) -> dict:
        return {
            "type": self.pulse_type.value,
            "frequencies": self.frequencies,
            "intensity": self.intensity,
            "duration_ms": self.duration_ms,
        }


@dataclass
class Synapse:
    """突触连接"""
    peer_id: str
    weight: float = 0.5  # 连接权重 0-1
    last_fired: float = 0
    fire_count: int = 0

    # 学习参数
    base_weight: float = 0.1
    max_weight: float = 1.0
    min_weight: float = 0.01


class HebbianLearning:
    """
    赫布学习器

    核心原理："一起激活的神经元，连接会增强"
    "Neurons that fire together, wire together"
    """

    def __init__(self):
        # 学习率
        self.learning_rate = 0.01
        self.decay_rate = 0.001

    def strengthen(self, synapse: Synapse):
        """增强连接"""
        synapse.weight = min(
            synapse.max_weight,
            synapse.weight + self.learning_rate * synapse.weight
        )
        synapse.fire_count += 1

    def weaken(self, synapse: Synapse):
        """减弱连接"""
        synapse.weight = max(
            synapse.min_weight,
            synapse.weight - self.decay_rate
        )

    def learn_co_fire(self, syn1: Synapse, syn2: Synapse):
        """学习同时激活的连接"""
        # 双向增强
        self.strengthen(syn1)
        self.strengthen(syn2)


class NeuralPulseProtocol:
    """
    神经脉冲协议

    功能：
    1. 神经脉冲发送与接收
    2. 突触权重管理
    3. 动作电位触发
    4. 赫布学习

    预设脉冲模式：
    - 高频(100Hz+) = 紧急/危险
    - 中频(10-50Hz) = 普通信息
    - 低频(1-5Hz) = 后台/低优先级
    """

    # 配置
    RESTING_POTENTIAL = -70  # 静息电位 (mV)
    THRESHOLD_POTENTIAL = -55  # 阈值电位 (mV)
    ACTION_POTENTIAL_PEAK = 40  # 动作电位峰值 (mV)

    # 脉冲频率
    HIGH_FREQUENCY = 100  # Hz - 紧急
    MEDIUM_FREQUENCY = 20  # Hz - 普通
    LOW_FREQUENCY = 2     # Hz - 低优先级

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 突触连接
        self.synapses: Dict[str, Synapse] = {}

        # 膜电位
        self.membrane_potential = self.RESTING_POTENTIAL

        # 赫布学习器
        self.hebbian = HebbianLearning()

        # 动作电位触发器
        self._action_potential_handlers: List[Callable] = []

        # 网络函数
        self._send_func = send_func

        # 统计
        self.pulse_stats: Dict[str, int] = {
            "sent": 0,
            "received": 0,
            "action_potentials": 0,
        }

    # ========== 突触管理 ==========

    def create_synapse(self, peer_id: str, initial_weight: float = 0.5) -> Synapse:
        """创建突触连接"""
        if peer_id in self.synapses:
            return self.synapses[peer_id]

        synapse = Synapse(
            peer_id=peer_id,
            weight=initial_weight,
        )
        self.synapses[peer_id] = synapse
        return synapse

    def get_synapse(self, peer_id: str) -> Optional[Synapse]:
        """获取突触"""
        return self.synapses.get(peer_id)

    def remove_synapse(self, peer_id: str):
        """移除突触"""
        if peer_id in self.synapses:
            del self.synapses[peer_id]

    # ========== 脉冲发送 ==========

    async def fire_pulse(
        self,
        peer_id: str,
        pulse_type: PulseType,
        intensity: float = 1.0,
        custom_frequencies: Optional[List[float]] = None,
    ) -> bool:
        """
        发射神经脉冲

        Args:
            peer_id: 目标节点
            pulse_type: 脉冲类型
            intensity: 强度 0-1
            custom_frequencies: 自定义频率

        Returns:
            是否成功发送
        """
        synapse = self.get_synapse(peer_id)
        if not synapse:
            synapse = self.create_synapse(peer_id)

        # 确定频率
        if custom_frequencies:
            frequencies = custom_frequencies
        else:
            frequencies = self._get_frequencies_for_type(pulse_type)

        # 创建脉冲模式
        pattern = PulsePattern(
            pulse_type=pulse_type,
            frequencies=frequencies,
            intensity=intensity * synapse.weight,
        )

        # 发送脉冲
        if self._send_func:
            try:
                await self._send_func(peer_id, {
                    "type": "neural_pulse",
                    "from": self.node_id,
                    "pattern": pattern.to_dict(),
                    "timestamp": time.time(),
                })
            except Exception:
                return False

        # 更新突触状态
        synapse.last_fired = time.time()
        self.pulse_stats["sent"] += 1

        # 赫布学习：同时激活，连接增强
        self.hebbian.strengthen(synapse)

        return True

    async def fire_broadcast(
        self,
        pulse_type: PulseType,
        intensity: float = 1.0,
        include_types: Optional[List[str]] = None,
    ):
        """
        广播脉冲到所有连接的节点

        Args:
            pulse_type: 脉冲类型
            intensity: 强度
            include_types: 只发送到指定类型的节点
        """
        tasks = []
        for peer_id, synapse in self.synapses.items():
            if include_types and peer_id not in include_types:
                continue

            # 根据权重衰减强度
            adjusted_intensity = intensity * synapse.weight
            task = self.fire_pulse(peer_id, pulse_type, adjusted_intensity)
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _get_frequencies_for_type(self, pulse_type: PulseType) -> List[float]:
        """根据类型获取频率"""
        if pulse_type == PulseType.ALERT:
            # 高频 - 紧急
            return [100, 110, 120, 100]  # 100Hz+ 突发
        elif pulse_type == PulseType.EMOTION:
            # 情感变化
            return [8, 12, 8]  # Alpha 波
        elif pulse_type == PulseType.REFLECT:
            # 反射 - 快速
            return [50, 60]
        elif pulse_type == PulseType.SYNC:
            # 同步 - 规律
            return [10, 10, 10]
        elif pulse_type == PulseType.INTENTION:
            # 意图 - 微妙
            return [2, 3, 2]
        else:
            # 普通更新
            return [20, 25, 20]

    # ========== 脉冲接收 ==========

    async def receive_pulse(self, pulse_data: dict):
        """接收神经脉冲"""
        pattern_dict = pulse_data.get("pattern", {})
        sender = pulse_data.get("from")

        pattern = PulsePattern(
            pulse_type=PulseType(pattern_dict.get("type", "update")),
            frequencies=pattern_dict.get("frequencies", [20]),
            intensity=pattern_dict.get("intensity", 1.0),
            duration_ms=pattern_dict.get("duration_ms", 100),
        )

        # 更新突触权重（反向传播学习）
        synapse = self.get_synapse(sender)
        if synapse:
            # 接收脉冲也稍微增强连接
            self.hebbian.strengthen(synapse)

        # 改变膜电位
        self._update_membrane_potential(pattern)

        # 检查是否触发动作电位
        if self.membrane_potential >= self.THRESHOLD_POTENTIAL:
            await self._trigger_action_potential(pattern)

        self.pulse_stats["received"] += 1

    def _update_membrane_potential(self, pattern: PulsePattern):
        """更新膜电位"""
        # 计算频率贡献
        freq_contribution = sum(pattern.frequencies) / len(pattern.frequencies)

        # 频率越高，贡献越大
        freq_factor = freq_contribution / 100  # 归一化

        # 强度影响
        potential_delta = (
            freq_factor *
            pattern.intensity *
            10  # 缩放因子
        )

        self.membrane_potential += potential_delta

        # 膜电位自然衰减
        self.membrane_potential *= 0.95

        # 限制范围
        self.membrane_potential = max(
            self.RESTING_POTENTIAL,
            min(self.ACTION_POTENTIAL_PEAK, self.membrane_potential)
        )

    async def _trigger_action_potential(self, pattern: PulsePattern):
        """触发动作电位"""
        self.pulse_stats["action_potentials"] += 1

        # 重置膜电位
        self.membrane_potential = self.RESTING_POTENTIAL

        # 执行动作电位处理
        for handler in self._action_potential_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(pattern)
                else:
                    handler(pattern)
            except Exception:
                pass

    # ========== 反射弧 ==========

    async def setup_reflex(
        self,
        pulse_type: PulseType,
        response_func: Callable,
        intensity_threshold: float = 0.5,
    ):
        """
        设置反射弧（自动响应）

        Args:
            pulse_type: 触发的脉冲类型
            response_func: 响应函数
            intensity_threshold: 触发阈值
        """
        async def reflex_handler(pattern: PulsePattern):
            if pattern.pulse_type == pulse_type and pattern.intensity >= intensity_threshold:
                await response_func(pattern)

        self._action_potential_handlers.append(reflex_handler)

    async def fire_alert(self, message: str, level: str = "high"):
        """
        发送警报脉冲（全网广播）

        用法：当检测到攻击/异常时，快速通知所有节点
        """
        intensity = 1.0 if level == "high" else 0.5
        await self.fire_broadcast(PulseType.ALERT, intensity=intensity)

        # 同时发送详细信息
        if self._send_func:
            for peer_id in self.synapses:
                try:
                    await self._send_func(peer_id, {
                        "type": "alert_detail",
                        "message": message,
                        "level": level,
                        "timestamp": time.time(),
                    })
                except Exception:
                    pass

    # ========== 脉冲模式 ==========

    def create_pattern(
        self,
        pulse_type: PulseType,
        intensity: float = 1.0,
        custom_freqs: Optional[List[float]] = None,
    ) -> PulsePattern:
        """创建自定义脉冲模式"""
        return PulsePattern(
            pulse_type=pulse_type,
            frequencies=custom_freqs or self._get_frequencies_for_type(pulse_type),
            intensity=intensity,
        )

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "synapses": len(self.synapses),
            "membrane_potential": self.membrane_potential,
            "pulses_sent": self.pulse_stats["sent"],
            "pulses_received": self.pulse_stats["received"],
            "action_potentials": self.pulse_stats["action_potentials"],
            "synapse_weights": {
                peer: {
                    "weight": f"{s.weight:.2f}",
                    "fire_count": s.fire_count,
                }
                for peer, s in list(self.synapses.items())[:5]
            },
        }


# 全局单例
_neural_pulse_instance: Optional[NeuralPulseProtocol] = None


def get_neural_pulse(node_id: str = "local") -> NeuralPulseProtocol:
    """获取神经脉冲协议单例"""
    global _neural_pulse_instance
    if _neural_pulse_instance is None:
        _neural_pulse_instance = NeuralPulseProtocol(node_id)
    return _neural_pulse_instance