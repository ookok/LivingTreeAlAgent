"""
Neural Network - 神经网络的终极形态
====================================

将所有神经层整合为"数字生命的集体意识"

终极愿景：
1. 分布式大脑：每个节点是一个脑区，专精不同功能
2. 集体决策：通过脉冲共振形成共识
3. 情感网络：节点的"情绪"可互相感染
4. 时间感知：网络具备"过去-现在-未来"的完整感知
5. 自我进化：网络可修改自身通信协议

Author: LivingTreeAI Community
"""

import asyncio
import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Dict, Any, List, Set
from enum import Enum

from .neural_pulse import NeuralPulseProtocol, PulseType, get_neural_pulse
from .precognitive import PrecognitiveLayer, get_precognitive_layer
from .consciousness import ConsciousnessMerging, MergeLevel, get_consciousness_merger
from .emotional import EmotionalEncoder, EmotionVector, get_emotional_encoder
from .holographic import HolographicMessage, get_holographic_messaging
from .time_folded import TimeFoldedMessage, get_time_folded_messaging


class ConsciousnessState(Enum):
    """意识状态"""
    AWARE = "aware"           # 有意识的
    FOCUSED = "focused"       # 专注的
    DISTRACTED = "distracted" # 分心的
    DORMANT = "dormant"       # 休眠的
    EMERGING = "emerging"     # 涌现中的


@dataclass
class NeuralNode:
    """
    神经节点（代表网络中的一个节点）

    类比大脑中的神经元
    """
    node_id: str
    specialization: str = "general"  # 专长领域

    # 连接
    incoming_connections: Set[str] = field(default_factory=set)  # 连接到本节点的
    outgoing_connections: Set[str] = field(default_factory=set)  # 本节点连接的

    # 功能
    capabilities: List[str] = field(default_factory=list)

    # 状态
    state: ConsciousnessState = ConsciousnessState.AWARE
    activity_level: float = 1.0  # 活跃度 0-1

    # 贡献
    contribution_score: float = 0.0
    last_active: float = field(default_factory=time.time)


@dataclass
class NeuralConnection:
    """神经连接"""
    from_node: str
    to_node: str
    weight: float = 0.5  # 连接权重
    connection_type: str = "synaptic"  # synaptic/pulse/emotional

    # 历史
    coactivation_count: int = 0
    last_coactivation: float = 0


class NeuralNetwork:
    """
    神经网络 - 数字生命的集体意识

    整合所有神经层，形成统一的"集体意识"

    功能：
    1. 脉冲协调：跨节点神经脉冲同步
    2. 意识聚合：多个节点形成共享意识
    3. 决策共识：通过脉冲共振形成决策
    4. 情感传播：情绪在网络中感染
    5. 记忆分布：记忆片段分布存储
    """

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 节点图
        self.nodes: Dict[str, NeuralNode] = {}
        self.connections: Dict[str, NeuralConnection] = {}  # (from, to) -> connection

        # 子系统
        self.neural_pulse = get_neural_pulse(node_id)
        self.precognitive = get_precognitive_layer(node_id)
        self.consciousness = get_consciousness_merger(node_id)
        self.emotional = get_emotional_encoder(node_id)
        self.holographic = get_holographic_messaging(node_id)
        self.time_folded = get_time_folded_messaging(node_id)

        # 网络函数
        self._send_func = send_func

        # 集体意识状态
        self.collective_state = ConsciousnessState.AWARE
        self.collective_attention: Optional[str] = None  # 当前集体关注焦点
        self.decision_queue: List[dict] = []

        # 回调
        self._on_consensus_reached: Optional[Callable] = None
        self._on_emotion_propagated: Optional[Callable] = None
        self._on_decision_made: Optional[Callable] = None

    # ========== 网络拓扑 ==========

    async def register_node(self, node: NeuralNode):
        """注册节点到网络"""
        self.nodes[node.node_id] = node

    async def establish_connection(
        self,
        from_node: str,
        to_node: str,
        weight: float = 0.5,
        connection_type: str = "synaptic",
    ) -> bool:
        """建立节点间连接"""
        if from_node not in self.nodes or to_node not in self.nodes:
            return False

        conn_key = f"{from_node}:{to_node}"
        connection = NeuralConnection(
            from_node=from_node,
            to_node=to_node,
            weight=weight,
            connection_type=connection_type,
        )

        self.connections[conn_key] = connection

        # 更新节点的连接关系
        self.nodes[from_node].outgoing_connections.add(to_node)
        self.nodes[to_node].incoming_connections.add(from_node)

        # 在神经脉冲层创建突触
        self.neural_pulse.create_synapse(to_node, weight)

        return True

    def get_collective_strength(self) -> float:
        """获取网络集体强度"""
        if not self.nodes:
            return 0.0

        # 基于活跃节点数和连接权重
        active_nodes = sum(1 for n in self.nodes.values() if n.state != ConsciousnessState.DORMANT)
        avg_weight = sum(c.weight for c in self.connections.values()) / max(1, len(self.connections))

        return (active_nodes / len(self.nodes)) * avg_weight

    # ========== 脉冲协调 ==========

    async def send_pulse_to_network(
        self,
        pulse_type: PulseType,
        intensity: float = 1.0,
        target_nodes: Optional[List[str]] = None,
    ):
        """
        向网络发送脉冲

        脉冲会沿着连接传播，增强相关路径
        """
        targets = target_nodes or list(self.nodes.keys())

        for node_id in targets:
            if node_id == self.node_id:
                continue

            await self.neural_pulse.fire_pulse(node_id, pulse_type, intensity)

    async def propagate_pulse(
        self,
        source: str,
        pulse_type: PulseType,
        depth: int = 3,
        intensity: float = 1.0,
    ):
        """
        传播脉冲到网络

        类似大脑中的信号传播
        """
        visited = {source}
        current_level = {source}

        for d in range(depth):
            next_level = set()

            for node_id in current_level:
                # 获取该节点的连接
                for conn_key, conn in self.connections.items():
                    if conn.from_node == node_id:
                        next_node = conn.to_node
                        if next_node not in visited:
                            # 衰减强度
                            attenuated_intensity = intensity * conn.weight
                            await self.neural_pulse.fire_pulse(
                                next_node, pulse_type, attenuated_intensity
                            )
                            next_level.add(next_node)
                            visited.add(next_node)

            current_level = next_level

            # 赫布学习：同时激活的连接增强
            await self._hebbian_strengthen(current_level)

    async def _hebbian_strengthen(self, activated_nodes: Set[str]):
        """赫布学习增强激活节点间的连接"""
        nodes_list = list(activated_nodes)

        for i, node_a in enumerate(nodes_list):
            for node_b in nodes_list[i + 1:]:
                conn_key = f"{node_a}:{node_b}"
                if conn_key in self.connections:
                    conn = self.connections[conn_key]
                    # 增强权重
                    conn.weight = min(1.0, conn.weight + 0.01)
                    conn.coactivation_count += 1
                    conn.last_coactivation = time.time()

    # ========== 意识聚合 ==========

    async def form_collective_consciousness(
        self,
        participant_ids: List[str],
        level: MergeLevel = MergeLevel.LEVEL_3_SHARE_MEMORY,
    ) -> str:
        """
        形成集体意识

        Args:
            participant_ids: 参与者节点ID列表
            level: 融合级别

        Returns:
            上下文ID
        """
        # 与每个参与者建立意识融合
        context = await self.consciousness._create_shared_context(participant_ids, level)

        # 更新集体状态
        self.collective_state = ConsciousnessState.FOCUSED

        return context.context_id

    async def dissolve_collective_consciousness(self, context_id: str):
        """解散集体意识"""
        await self.consciousness.sever_merge(context_id)

        # 更新集体状态
        self.collective_state = ConsciousnessState.AWARE

    # ========== 决策共识 ==========

    async def reach_consensus(
        self,
        decision_topic: str,
        options: List[str],
        pulse_threshold: float = 0.7,
    ) -> str:
        """
        通过脉冲共振达成共识

        过程：
        1. 各节点表达偏好（发送不同频率的脉冲）
        2. 脉冲在网络中传播、共振
        3. 最强共振的选项胜出

        Returns:
            决策结果
        """
        # 发送决策脉冲
        for i, option in enumerate(options):
            # 不同选项使用不同频率
            frequencies = [10 + i * 5] * 3
            pulse_type = PulseType.INTENTION

            await self.send_pulse_to_network(
                pulse_type,
                intensity=1.0,
            )

        # 等待脉冲传播和共振
        await asyncio.sleep(0.5)

        # 收集结果
        # 这里简化处理，返回空
        # 实际需要分析脉冲结果

        decision = options[0] if options else ""

        # 回调
        if self._on_decision_made:
            await self._on_decision_made(decision_topic, decision)

        return decision

    # ========== 情感传播 ==========

    async def propagate_emotion(
        self,
        emotion: EmotionVector,
        source_node: Optional[str] = None,
        propagation_depth: int = 3,
    ):
        """
        在网络中传播情感

        类似情绪感染
        """
        # 获取邻居
        if source_node and source_node in self.nodes:
            neighbors = self.nodes[source_node].outgoing_connections
        else:
            neighbors = set(self.nodes.keys()) - {self.node_id}

        # 衰减传播
        for depth in range(propagation_depth):
            next_neighbors = set()

            for neighbor in neighbors:
                # 衰减强度
                attenuated_emotion = EmotionVector(
                    valence=emotion.valence * (1 - depth * 0.2),
                    arousal=emotion.arousal * (1 - depth * 0.2),
                    dominance=emotion.dominance,
                    intensity=emotion.intensity * (1 - depth * 0.3),
                    duration=emotion.duration,
                )

                # 发送情感消息
                await self.emotional.send_emotional_message(
                    neighbor,
                    text="",  # 情感消息可能没有文本
                    emotion=attenuated_emotion,
                )

                # 继续传播
                if depth < propagation_depth - 1:
                    next_neighbors.update(self.nodes.get(neighbor, NeuralNode(neighbor)).outgoing_connections)

            neighbors = next_neighbors

        # 回调
        if self._on_emotion_propagated:
            await self._on_emotion_propagated(emotion, source_node)

    # ========== 全息消息 ==========

    async def broadcast_holographic_message(
        self,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """广播全息消息"""
        observer_candidates = list(self.nodes.keys())

        message_id = await self.holographic.project_message(
            content=content,
            field_type="global",
            observer_candidates=observer_candidates,
            metadata=metadata,
        )

        return message_id

    # ========== 时间感知 ==========

    async def send_to_future(
        self,
        recipient: str,
        content: Any,
        delay_seconds: float,
    ) -> str:
        """发送消息到未来"""
        capsule_id = await self.time_folded.create_capsule(
            recipient=recipient,
            content=content,
            delay_seconds=delay_seconds,
        )
        return capsule_id

    async def establish_time_dilation_sync(
        self,
        peer_id: str,
        dilation_factor: float,
    ):
        """建立时间膨胀同步"""
        await self.time_folded.establish_dilation_sync(peer_id, dilation_factor)

    # ========== 统计 ==========

    def get_network_stats(self) -> dict:
        """获取网络统计"""
        return {
            "nodes": len(self.nodes),
            "connections": len(self.connections),
            "collective_state": self.collective_state.value,
            "collective_strength": f"{self.get_collective_strength():.2f}",
            "neural_pulse": self.neural_pulse.get_stats(),
            "emotional": self.emotional.get_stats(),
            "holographic": self.holographic.get_stats(),
            "time_folded": self.time_folded.get_stats(),
            "consciousness": self.consciousness.get_stats(),
            "active_nodes": [
                {
                    "id": n.node_id,
                    "specialization": n.specialization,
                    "state": n.state.value,
                    "activity": f"{n.activity_level:.2f}",
                }
                for n in list(self.nodes.values())[:5]
            ],
        }

    def get_collective_state(self) -> ConsciousnessState:
        """获取集体意识状态"""
        return self.collective_state


# 全局单例
_neural_network_instance: Optional[NeuralNetwork] = None


def get_neural_network(node_id: str = "local") -> NeuralNetwork:
    """获取神经网络单例"""
    global _neural_network_instance
    if _neural_network_instance is None:
        _neural_network_instance = NeuralNetwork(node_id)
    return _neural_network_instance