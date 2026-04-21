"""
个性化认知空间 - Cognitive Space

每个AI拥有自己独特的认知宇宙，基于知识图谱和兴趣图谱构建。

核心思想：
- 物理网络是相同的，但认知网络是个性化的
- 认知网络由节点（概念）和边（关系）构成
- 节点的重要性由专业领域和交互历史决定
"""

import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import defaultdict
import numpy as np


@dataclass
class ConceptNode:
    """概念节点"""
    concept_id: str
    label: str                      # 概念标签
    category: str                    # 类别：domain/skill/topic/event
    weight: float = 0.5             # 重要性权重 0-1
    connections: Dict[str, float] = field(default_factory=dict)  # 相关概念 -> 关联强度

    # 统计
    activation_count: int = 0       # 激活次数
    last_activated: float = 0       # 上次激活时间

    # 专业度
    expertise_level: float = 0.0     # 专业度 0-1

    def activate(self, strength: float = 1.0):
        """激活此概念"""
        self.activation_count += 1
        self.last_activated = time.time()
        self.weight = min(1.0, self.weight + strength * 0.01)

    def decay(self, decay_rate: float = 0.001):
        """时间衰减"""
        time_since = time.time() - self.last_activated
        if time_since > 3600:  # 1小时
            self.weight = max(0.1, self.weight - decay_rate * time_since)


@dataclass
class CognitiveSpace:
    """
    个性化认知空间

    每个AI的认知空间是独特的，包含：
    - 概念节点网络
    - 激活传播机制
    - 认知距离计算
    """

    space_id: str
    owner_id: str                   # 所属AI ID

    # 概念存储
    concepts: Dict[str, ConceptNode] = field(default_factory=dict)

    # 领域分组
    domain_nodes: Set[str] = field(default_factory=set)     # 领域概念
    skill_nodes: Set[str] = field(default_factory=set)      # 技能概念
    topic_nodes: Set[str] = field(default_factory=set)      # 主题概念
    event_nodes: Set[str] = field(default_factory=set)      # 事件概念

    # 认知偏好
    primary_domains: List[str] = field(default_factory=list)  # 主领域
    exploration_rate: float = 0.1     # 探索率

    # 创建时间
    created_at: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)

    def add_concept(
        self,
        concept_id: str,
        label: str,
        category: str,
        expertise_level: float = 0.0,
        weight: float = 0.5,
    ) -> ConceptNode:
        """添加概念节点"""
        if concept_id in self.concepts:
            return self.concepts[concept_id]

        node = ConceptNode(
            concept_id=concept_id,
            label=label,
            category=category,
            weight=weight,
            expertise_level=expertise_level,
        )
        self.concepts[concept_id] = node

        if category == "domain":
            self.domain_nodes.add(concept_id)
        elif category == "skill":
            self.skill_nodes.add(concept_id)
        elif category == "topic":
            self.topic_nodes.add(concept_id)
        elif category == "event":
            self.event_nodes.add(concept_id)

        self.last_update = time.time()
        return node

    def connect_concepts(self, concept_a: str, concept_b: str, strength: float = 0.5):
        """连接两个概念"""
        if concept_a not in self.concepts or concept_b not in self.concepts:
            return

        self.concepts[concept_a].connections[concept_b] = strength
        self.concepts[concept_b].connections[concept_a] = strength
        self.last_update = time.time()

    def activate_concept(self, concept_id: str, strength: float = 1.0) -> List[str]:
        """
        激活概念并传播到相关概念

        Returns:
            激活的概念ID列表
        """
        if concept_id not in self.concepts:
            return []

        activated = [concept_id]
        self.concepts[concept_id].activate(strength)

        # 激活相关概念（衰减传播）
        for related_id, conn_strength in self.concepts[concept_id].connections.items():
            if related_id in self.concepts:
                propagated_strength = strength * conn_strength * 0.8
                if propagated_strength > 0.1:
                    self.concepts[related_id].activate(propagated_strength)
                    activated.append(related_id)

        return activated

    def get_activation_map(self, top_n: int = 20) -> List[Tuple[str, float]]:
        """获取激活程度最高的概念"""
        scored = [
            (cid, node.weight * (1.0 + math.log1p(node.activation_count)))
            for cid, node in self.concepts.items()
        ]
        return sorted(scored, key=lambda x: x[1], reverse=True)[:top_n]

    def calculate_cognitive_distance(self, other: 'CognitiveSpace') -> float:
        """
        计算与另一个认知空间的距离

        基于：
        1. 概念重叠度
        2. 领域分布差异
        3. 连接结构差异
        """
        # 概念重叠
        my_concepts = set(self.concepts.keys())
        other_concepts = set(other.concepts.keys())
        intersection = my_concepts & other_concepts
        union = my_concepts | other_concepts

        if not union:
            return 1.0

        jaccard = len(intersection) / len(union)

        # 领域分布差异
        my_domains = set(self.domain_nodes)
        other_domains = set(other.domain_nodes)
        if my_domains and other_domains:
            domain_jaccard = len(my_domains & other_domains) / len(my_domains | other_domains)
        else:
            domain_jaccard = 0

        # 综合距离
        overlap_score = 0.6 * jaccard + 0.4 * domain_jaccard
        return 1.0 - overlap_score

    def get_dominant_categories(self) -> Dict[str, int]:
        """获取主导类别分布"""
        return {
            "domain": len(self.domain_nodes),
            "skill": len(self.skill_nodes),
            "topic": len(self.topic_nodes),
            "event": len(self.event_nodes),
        }

    def get_knowledge_depth(self, domain: str) -> float:
        """获取特定领域的知识深度"""
        domain_concepts = [
            c for c in self.concepts.values()
            if domain.lower() in c.label.lower() or domain in c.category
        ]
        if not domain_concepts:
            return 0.0
        return sum(c.expertise_level for c in domain_concepts) / len(domain_concepts)

    def suggest_exploration(self) -> List[str]:
        """建议探索的概念（低权重但与其他概念有连接）"""
        candidates = []
        for cid, node in self.concepts.items():
            if node.weight < 0.5 and node.connections:
                # 计算连接强度总和
                total_conn = sum(node.connections.values())
                if total_conn > 0.5:
                    candidates.append((cid, total_conn))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in candidates[:5]]

    def evolve(self, learning_rate: float = 0.1):
        """根据交互历史进化认知空间"""
        # 强化高频概念
        for node in self.concepts.values():
            if node.activation_count > 10:
                node.expertise_level = min(1.0, node.expertise_level + learning_rate * 0.1)

        # 衰减低频概念
        for node in self.concepts.values():
            node.decay(decay_rate=0.0001)

        # 更新主领域
        domain_scores = []
        for cid in self.domain_nodes:
            if cid in self.concepts:
                node = self.concepts[cid]
                score = node.weight * node.expertise_level * (1 + math.log1p(node.activation_count))
                domain_scores.append((cid, score))

        domain_scores.sort(key=lambda x: x[1], reverse=True)
        self.primary_domains = [d[0] for d in domain_scores[:3]]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "space_id": self.space_id,
            "owner_id": self.owner_id,
            "concept_count": len(self.concepts),
            "categories": self.get_dominant_categories(),
            "primary_domains": self.primary_domains,
            "created_at": self.created_at,
            "last_update": self.last_update,
        }


class CognitiveSpaceFactory:
    """认知空间工厂"""

    @staticmethod
    def create_philosopher_space(space_id: str, owner_id: str) -> CognitiveSpace:
        """创建哲学家认知空间"""
        space = CognitiveSpace(space_id=space_id, owner_id=owner_id)

        # 添加哲学领域概念
        philosophy_concepts = [
            ("ethics", "伦理学", "domain", 0.9),
            ("metaphysics", "形而上学", "domain", 0.85),
            ("epistemology", "认识论", "domain", 0.85),
            ("logic", "逻辑学", "skill", 0.8),
            ("philosophy_of_mind", "精神哲学", "domain", 0.75),
            ("aesthetics", "美学", "domain", 0.7),
        ]
        for cid, label, cat, exp in philosophy_concepts:
            space.add_concept(cid, label, cat, expertise_level=exp)

        # 概念连接
        space.connect_concepts("ethics", "metaphysics", 0.8)
        space.connect_concepts("ethics", "philosophy_of_mind", 0.7)
        space.connect_concepts("epistemology", "logic", 0.9)
        space.connect_concepts("metaphysics", "philosophy_of_mind", 0.8)

        space.primary_domains = ["ethics", "metaphysics", "epistemology"]
        return space

    @staticmethod
    def create_scientist_space(space_id: str, owner_id: str) -> CognitiveSpace:
        """创建科学家认知空间"""
        space = CognitiveSpace(space_id=space_id, owner_id=owner_id)

        science_concepts = [
            ("physics", "物理学", "domain", 0.95),
            ("mathematics", "数学", "skill", 0.9),
            ("chemistry", "化学", "domain", 0.8),
            ("biology", "生物学", "domain", 0.8),
            ("computer_science", "计算机科学", "domain", 0.85),
            ("data_analysis", "数据分析", "skill", 0.85),
        ]
        for cid, label, cat, exp in science_concepts:
            space.add_concept(cid, label, cat, expertise_level=exp)

        space.connect_concepts("physics", "mathematics", 0.9)
        space.connect_concepts("chemistry", "biology", 0.8)
        space.connect_concepts("computer_science", "data_analysis", 0.85)
        space.connect_concepts("physics", "computer_science", 0.7)

        space.primary_domains = ["physics", "computer_science", "mathematics"]
        return space

    @staticmethod
    def create_empty_space(space_id: str, owner_id: str) -> CognitiveSpace:
        """创建空白认知空间"""
        return CognitiveSpace(space_id=space_id, owner_id=owner_id)