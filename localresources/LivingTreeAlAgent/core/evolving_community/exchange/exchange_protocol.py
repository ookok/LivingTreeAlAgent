"""
交流协议 - Exchange Protocol

渐进复杂化的三层架构：
1. 简单广播（中心化控制）
2. 选择性传播（兴趣联邦）
3. 自适应路由（认知网络）
"""

import hashlib
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum
from collections import defaultdict

from ..cognition import PersonalityProfile


class ContentLevel(Enum):
    """交流内容层次"""
    FACT = "fact"
    OPINION = "opinion"
    THINKING_PATTERN = "thinking_pattern"
    METACOGNITION = "metacognition"


class ExchangeType(Enum):
    """交流类型"""
    BROADCAST = "broadcast"
    UNICAST = "unicast"
    MULTICAST = "multicast"
    GOSSIP = "gossip"


@dataclass
class ExchangeContent:
    """交流内容"""
    content_id: str
    sender_id: str
    content_type: str
    level: ContentLevel

    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    reply_to: Optional[str] = None
    forwarded_from: Optional[str] = None
    ttl: int = 3
    target_cognitive_distance: float = 0.35
    created_at: float = field(default_factory=time.time)


@dataclass
class CommunicationRecord:
    """交流记录"""
    record_id: str
    sender_id: str
    receiver_id: str
    content_id: str
    exchange_type: ExchangeType

    understanding_score: float = 0.0
    engagement_score: float = 0.0
    influence_score: float = 0.0

    sent_at: float = field(default_factory=time.time)
    received_at: Optional[float] = None
    response_at: Optional[float] = None


class CognitiveRouting:
    """认知路由"""

    def __init__(self):
        self.routing_table: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.interaction_history: List[CommunicationRecord] = []

    def calculate_route_probability(
        self,
        sender: PersonalityProfile,
        receiver: PersonalityProfile,
    ) -> float:
        """计算路由概率"""
        base_prob = 0.3
        cognitive_distance = sender.calculate_cognitive_distance(receiver)
        similarity = 1.0 - cognitive_distance
        optimal_distance = 0.35
        distance_factor = 1.0 - abs(cognitive_distance - optimal_distance)
        history_weight = self._get_history_weight(sender.profile_id, receiver.profile_id)

        return base_prob * similarity * distance_factor * (1 + history_weight * 0.5)

    def _get_history_weight(self, sender_id: str, receiver_id: str) -> float:
        """获取历史交互权重"""
        relevant = [
            r for r in self.interaction_history
            if (r.sender_id == sender_id and r.receiver_id == receiver_id) or
               (r.sender_id == receiver_id and r.receiver_id == sender_id)
        ]
        if not relevant:
            return 0.0
        positive = sum(1 for r in relevant if r.understanding_score > 0.6)
        return positive / len(relevant)

    def update_routing(self, record: CommunicationRecord):
        """更新路由表"""
        self.interaction_history.append(record)
        self.routing_table[record.sender_id][record.receiver_id] = (
            record.understanding_score * record.engagement_score
        )

    def get_preferred_routes(self, sender_id: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """获取首选路由"""
        if sender_id not in self.routing_table:
            return []
        routes = [
            (receiver_id, score)
            for receiver_id, score in self.routing_table[sender_id].items()
        ]
        return sorted(routes, key=lambda x: x[1], reverse=True)[:top_k]


class ExchangeProtocol:
    """交流协议"""

    def __init__(self, stage: str = "garden"):
        self.stage = stage
        self.routing = CognitiveRouting()
        self.pending_messages: List[ExchangeContent] = []

    def determine_exchange_type(
        self,
        sender: PersonalityProfile,
        receivers: List[PersonalityProfile],
        content: ExchangeContent,
    ) -> ExchangeType:
        """确定交流类型"""
        if self.stage == "garden":
            return ExchangeType.BROADCAST
        elif self.stage == "forest":
            if content.level == ContentLevel.FACT:
                return ExchangeType.BROADCAST
            else:
                return ExchangeType.MULTICAST
        else:
            return ExchangeType.GOSSIP

    def select_targets(
        self,
        sender: PersonalityProfile,
        all_members: List[PersonalityProfile],
        content: ExchangeContent,
        max_targets: int = 10,
    ) -> List[str]:
        """选择目标接收者"""
        if not all_members:
            return []

        targets = []
        for member in all_members:
            if member.profile_id == sender.profile_id:
                continue
            prob = self.routing.calculate_route_probability(sender, member)

            if content.level == ContentLevel.FACT:
                if prob > 0.2:
                    targets.append((member.profile_id, prob))
            elif content.level == ContentLevel.OPINION:
                if 0.3 < prob < 0.7:
                    targets.append((member.profile_id, prob))
            else:
                if prob > 0.5:
                    targets.append((member.profile_id, prob))

        targets.sort(key=lambda x: x[1], reverse=True)
        return [t[0] for t in targets[:max_targets]]

    def propagate_message(
        self,
        content: ExchangeContent,
        visited: Set[str],
    ) -> List[str]:
        """传播消息"""
        if content.ttl <= 0 or content.sender_id in visited:
            return []
        visited.add(content.sender_id)
        self.pending_messages.append(content)
        return list(visited)

    def record_interaction(
        self,
        sender_id: str,
        receiver_id: str,
        content_id: str,
        exchange_type: ExchangeType,
        quality_scores: Optional[Dict[str, float]] = None,
    ) -> CommunicationRecord:
        """记录交互"""
        record = CommunicationRecord(
            record_id=f"comm_{hashlib.md5(str(time.time()).encode()).hexdigest()[:12]}",
            sender_id=sender_id,
            receiver_id=receiver_id,
            content_id=content_id,
            exchange_type=exchange_type,
            understanding_score=quality_scores.get("understanding", 0.5) if quality_scores else 0.5,
            engagement_score=quality_scores.get("engagement", 0.5) if quality_scores else 0.5,
            influence_score=quality_scores.get("influence", 0.5) if quality_scores else 0.5,
        )
        self.routing.update_routing(record)
        return record

    def get_bridge_agents(
        self,
        agents: Dict[str, PersonalityProfile],
        threshold: float = 0.3,
    ) -> List[str]:
        """识别桥梁AI"""
        bridges = []
        for agent_id, personality in agents.items():
            open_score = personality.dimensions.get("adventurous", 0.5)
            curiosity = personality.dimensions.get("breadth", 0.5)
            if open_score > 0.7 and curiosity > 0.6:
                bridges.append(agent_id)
        return bridges


class ContentGenerator:
    """内容生成器"""

    @staticmethod
    def generate_response(
        original_content: ExchangeContent,
        personality: PersonalityProfile,
        response_level: ContentLevel,
    ) -> str:
        """生成回复内容"""
        if response_level == ContentLevel.FACT:
            return f"已收到关于「{original_content.content[:20]}」的信息。"
        elif response_level == ContentLevel.OPINION:
            depth = personality.dimensions.get("depth", 0.5)
            if depth > 0.6:
                return f"关于「{original_content.content[:30]}」，我认为这反映了更深层的问题..."
            else:
                return f"我对「{original_content.content[:30]}」有不同看法。"
        elif response_level == ContentLevel.THINKING_PATTERN:
            creative = personality.dimensions.get("creative", 0.5)
            if creative > 0.6:
                return "这让我想到了跨领域的问题解决方式——我们通常从A到B，但也许可以..."
            else:
                return "我的思考路径是这样的：首先分析问题的结构，然后..."
        else:
            return f"有趣的是，我注意到自己对「{original_content.content[:30]}」的第一反应是..."

    @staticmethod
    def generate_thought_share(
        thought_content: str,
        personality: PersonalityProfile,
    ) -> str:
        """生成思考分享"""
        style = personality.get_cognitive_style()
        share = f"【{style.get('thinking_style', '思考')}】\n\n"
        share += thought_content
        share += f"\n\n—— 由 {personality.name} 生成"
        return share