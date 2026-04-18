# -*- coding: utf-8 -*-
"""
去中心化知识区块链系统 - 信誉系统

实现:
- 信誉计算: 基础信誉 + 知识信誉 + 行为信誉 + 社交信誉
- 信誉维度: 知识/验证/传播/学习/教学/协作
- 信誉影响: 激励权重/共识权重/检索权重/信任度/权限等级
"""

import asyncio
import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from .models import (
    NodeProfile, NodeType, ReputationScore, ReputationDimension
)

logger = logging.getLogger(__name__)


@dataclass
class ReputationConfig:
    """信誉配置"""
    # 基础信誉分
    initial_reputation: float = 50.0
    
    # 各维度权重
    knowledge_weight: float = 0.25
    verification_weight: float = 0.20
    spread_weight: float = 0.15
    learning_weight: float = 0.15
    teaching_weight: float = 0.15
    collaboration_weight: float = 0.10
    
    # 信誉变化参数
    positive_bonus: float = 5.0
    negative_penalty: float = -3.0
    decay_rate: float = 0.01  # 每日衰减
    decay_threshold: float = 100.0  # 超过此值开始衰减
    
    # 等级阈值
    level_thresholds: Dict[int, float] = field(default_factory=lambda: {
        1: 0,
        2: 20,
        3: 50,
        4: 100,
        5: 200,
        6: 350,
        7: 500,
        8: 750,
        9: 1000,
        10: 1500
    })
    
    # 等级称号
    level_titles: Dict[int, str] = field(default_factory=lambda: {
        1: "新手",
        2: "学徒",
        3: "进阶",
        4: "熟练",
        5: "专家",
        6: "资深",
        7: "大师",
        8: "宗师",
        9: "传奇",
        10: "神话"
    })


@dataclass
class ReputationEvent:
    """信誉事件"""
    event_id: str
    node_id: str
    dimension: str
    delta: float
    reason: str
    timestamp: datetime
    related_knowledge_id: Optional[str] = None
    related_node_id: Optional[str] = None


class ReputationSystem:
    """信誉系统"""

    def __init__(
        self,
        storage: 'DistributedStorage',
        economy: 'TokenEconomy'
    ):
        """
        初始化信誉系统
        
        Args:
            storage: 分布式存储
            economy: 经济系统
        """
        self.storage = storage
        self.economy = economy
        
        self.config = ReputationConfig()
        
        # 节点信誉数据
        self.reputations: Dict[str, ReputationScore] = {}
        self.profiles: Dict[str, NodeProfile] = {}
        
        # 信誉事件历史
        self.events: Dict[str, List[ReputationEvent]] = {}  # node_id -> events
        
        # 排行榜
        self.leaderboard: List[tuple] = []  # (score, node_id)
        
        logger.info("信誉系统初始化完成")

    async def initialize(self, node_id: str) -> bool:
        """初始化信誉系统"""
        try:
            # 加载已有数据
            await self._load_data()
            
            # 为当前节点创建初始信誉
            if node_id not in self.reputations:
                await self.create_node_profile(
                    node_id=node_id,
                    node_type=NodeType.LIGHT
                )
            
            logger.info("✅ 信誉系统初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"信誉系统初始化失败: {e}")
            return False

    async def stop(self):
        """停止信誉系统"""
        await self._save_data()
        logger.info("信誉系统已停止")

    # ==================== 节点配置 ====================

    async def create_node_profile(
        self,
        node_id: str,
        node_type: NodeType,
        nickname: str = "",
        interests: Optional[List[str]] = None
    ) -> NodeProfile:
        """
        创建节点配置
        
        Args:
            node_id: 节点ID
            node_type: 节点类型
            nickname: 昵称
            interests: 兴趣标签
            
        Returns:
            节点配置
        """
        profile = NodeProfile(
            node_id=node_id,
            node_type=node_type,
            nickname=nickname or f"节点_{node_id[:8]}",
            created_at=datetime.now(),
            last_active=datetime.now(),
            interests=interests or []
        )
        
        self.profiles[node_id] = profile
        
        # 创建初始信誉
        reputation = ReputationScore(
            node_id=node_id,
            total_score=self.config.initial_reputation,
            knowledge_score=self.config.initial_reputation,
            verification_score=self.config.initial_reputation,
            spread_score=self.config.initial_reputation,
            learning_score=self.config.initial_reputation,
            teaching_score=self.config.initial_reputation,
            collaboration_score=self.config.initial_reputation,
            level=1,
            title=self.config.level_titles[1],
            updated_at=datetime.now()
        )
        
        self.reputations[node_id] = reputation
        self.events[node_id] = []
        
        logger.info(f"✅ 节点配置创建: {node_id}")
        
        return profile

    async def get_node_profile(self, node_id: str) -> Optional[NodeProfile]:
        """获取节点配置"""
        return self.profiles.get(node_id)

    async def update_node_profile(
        self,
        node_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """更新节点配置"""
        profile = self.profiles.get(node_id)
        if not profile:
            return False
        
        if "nickname" in updates:
            profile.nickname = updates["nickname"]
        if "interests" in updates:
            profile.interests = updates["interests"]
        if "expertise_domains" in updates:
            profile.expertise_domains = updates["expertise_domains"]
        
        profile.last_active = datetime.now()
        
        return True

    # ==================== 信誉查询 ====================

    async def get_node_reputation(self, node_id: str) -> Optional[ReputationScore]:
        """获取节点信誉"""
        return self.reputations.get(node_id)

    async def get_reputation_rank(self, node_id: str) -> Optional[int]:
        """获取信誉排名"""
        if not self.leaderboard:
            await self._rebuild_leaderboard()
        
        for rank, (score, nid) in enumerate(self.leaderboard, 1):
            if nid == node_id:
                return rank
        
        return None

    async def get_top_reputations(self, limit: int = 10) -> List[ReputationScore]:
        """获取最高信誉列表"""
        if not self.leaderboard:
            await self._rebuild_leaderboard()
        
        results = []
        for _, node_id in self.leaderboard[:limit]:
            rep = self.reputations.get(node_id)
            if rep:
                results.append(rep)
        
        return results

    def get_average_reputation(self) -> float:
        """获取平均信誉"""
        if not self.reputations:
            return 0.0
        
        total = sum(r.total_score for r in self.reputations.values())
        return total / len(self.reputations)

    # ==================== 信誉更新 ====================

    async def record_knowledge_creation(
        self,
        node_id: str,
        knowledge_id: str,
        quality_score: float
    ) -> bool:
        """
        记录知识创建
        
        Args:
            node_id: 节点ID
            knowledge_id: 知识ID
            quality_score: 质量评分
            
        Returns:
            是否成功
        """
        reputation = self.reputations.get(node_id)
        if not reputation:
            return False
        
        # 基础奖励
        delta = self.config.positive_bonus * (0.5 + quality_score * 0.5)
        
        # 更新信誉
        reputation.knowledge_score += delta
        reputation.knowledge_count += 1
        reputation.total_score = reputation.calculate_total()
        
        # 记录事件
        await self._record_event(
            node_id=node_id,
            dimension="knowledge",
            delta=delta,
            reason=f"knowledge_creation:{knowledge_id}",
            related_knowledge_id=knowledge_id
        )
        
        await self._update_node_level(reputation)
        
        return True

    async def record_verification(
        self,
        node_id: str,
        knowledge_id: str,
        is_valid: bool
    ) -> bool:
        """
        记录验证行为
        
        Args:
            node_id: 节点ID
            knowledge_id: 知识ID
            is_valid: 验证是否正确
            
        Returns:
            是否成功
        """
        reputation = self.reputations.get(node_id)
        if not reputation:
            return False
        
        # 根据验证结果调整
        if is_valid:
            delta = self.config.positive_bonus
        else:
            delta = self.config.negative_penalty
        
        # 更新信誉
        reputation.verification_score += delta
        reputation.verification_count += 1
        reputation.total_score = reputation.calculate_total()
        
        # 记录事件
        await self._record_event(
            node_id=node_id,
            dimension="verification",
            delta=delta,
            reason=f"knowledge_verification:{knowledge_id}",
            related_knowledge_id=knowledge_id
        )
        
        await self._update_node_level(reputation)
        
        return True

    async def record_spread(
        self,
        node_id: str,
        knowledge_id: str
    ) -> bool:
        """
        记录传播行为
        
        Args:
            node_id: 节点ID
            knowledge_id: 知识ID
            
        Returns:
            是否成功
        """
        reputation = self.reputations.get(node_id)
        if not reputation:
            return False
        
        delta = self.config.positive_bonus * 0.3
        
        reputation.spread_score += delta
        reputation.spread_count += 1
        reputation.total_score = reputation.calculate_total()
        
        await self._record_event(
            node_id=node_id,
            dimension="spread",
            delta=delta,
            reason=f"knowledge_spread:{knowledge_id}",
            related_knowledge_id=knowledge_id
        )
        
        await self._update_node_level(reputation)
        
        return True

    async def record_learning(
        self,
        node_id: str,
        knowledge_id: str
    ) -> bool:
        """
        记录学习行为
        
        Args:
            node_id: 节点ID
            knowledge_id: 知识ID
            
        Returns:
            是否成功
        """
        reputation = self.reputations.get(node_id)
        if not reputation:
            return False
        
        delta = self.config.positive_bonus * 0.2
        
        reputation.learning_score += delta
        reputation.learning_count += 1
        reputation.total_score = reputation.calculate_total()
        
        await self._record_event(
            node_id=node_id,
            dimension="learning",
            delta=delta,
            reason=f"knowledge_learn:{knowledge_id}",
            related_knowledge_id=knowledge_id
        )
        
        await self._update_node_level(reputation)
        
        return True

    async def record_teaching(
        self,
        teacher_id: str,
        student_id: str,
        effectiveness_score: float
    ) -> bool:
        """
        记录教学行为
        
        Args:
            teacher_id: 教学者ID
            student_id: 学员ID
            effectiveness_score: 效果评分
            
        Returns:
            是否成功
        """
        reputation = self.reputations.get(teacher_id)
        if not reputation:
            return False
        
        delta = self.config.positive_bonus * effectiveness_score
        
        reputation.teaching_score += delta
        reputation.total_score = reputation.calculate_total()
        
        await self._record_event(
            node_id=teacher_id,
            dimension="teaching",
            delta=delta,
            reason=f"teaching:{student_id}",
            related_node_id=student_id
        )
        
        await self._update_node_level(reputation)
        
        return True

    async def record_collaboration(
        self,
        node_id: str,
        collaborators: List[str],
        contribution_score: float
    ) -> bool:
        """
        记录协作行为
        
        Args:
            node_id: 节点ID
            collaborators: 协作者列表
            contribution_score: 贡献评分
            
        Returns:
            是否成功
        """
        reputation = self.reputations.get(node_id)
        if not reputation:
            return False
        
        delta = self.config.positive_bonus * contribution_score
        
        reputation.collaboration_score += delta
        reputation.total_score = reputation.calculate_total()
        
        await self._record_event(
            node_id=node_id,
            dimension="collaboration",
            delta=delta,
            reason=f"collaboration",
            related_node_id=",".join(collaborators)
        )
        
        await self._update_node_level(reputation)
        
        return True

    # ==================== 信誉衰减 ====================

    async def apply_decay(self):
        """应用信誉衰减"""
        now = datetime.now()
        
        for reputation in self.reputations.values():
            if reputation.total_score > self.config.decay_threshold:
                # 每日衰减
                days = (now - (reputation.updated_at or now)).days
                decay = self.config.decay_rate * days * reputation.total_score
                
                reputation.knowledge_score = max(0, reputation.knowledge_score - decay * 0.3)
                reputation.verification_score = max(0, reputation.verification_score - decay * 0.2)
                reputation.spread_score = max(0, reputation.spread_score - decay * 0.15)
                reputation.learning_score = max(0, reputation.learning_score - decay * 0.15)
                reputation.teaching_score = max(0, reputation.teaching_score - decay * 0.1)
                reputation.collaboration_score = max(0, reputation.collaboration_score - decay * 0.1)
                
                reputation.total_score = reputation.calculate_total()
                reputation.updated_at = now
        
        await self._save_data()
        logger.info("信誉衰减已应用")

    # ==================== 内部方法 ====================

    async def _record_event(
        self,
        node_id: str,
        dimension: str,
        delta: float,
        reason: str,
        related_knowledge_id: Optional[str] = None,
        related_node_id: Optional[str] = None
    ):
        """记录信誉事件"""
        import hashlib
        
        event = ReputationEvent(
            event_id=hashlib.sha256(f"{node_id}{reason}{datetime.now()}".encode()).hexdigest()[:24],
            node_id=node_id,
            dimension=dimension,
            delta=delta,
            reason=reason,
            timestamp=datetime.now(),
            related_knowledge_id=related_knowledge_id,
            related_node_id=related_node_id
        )
        
        if node_id not in self.events:
            self.events[node_id] = []
        
        self.events[node_id].append(event)
        
        # 只保留最近100个事件
        if len(self.events[node_id]) > 100:
            self.events[node_id] = self.events[node_id][-100:]

    async def _update_node_level(self, reputation: ReputationScore):
        """更新节点等级"""
        total = reputation.total_score
        
        # 找到对应等级
        new_level = 1
        for level, threshold in sorted(self.config.level_thresholds.items(), reverse=True):
            if total >= threshold:
                new_level = level
                break
        
        # 更新等级和称号
        if new_level > reputation.level:
            reputation.level = new_level
            reputation.title = self.config.level_titles.get(new_level, "新手")
            logger.info(f"🎉 节点 {reputation.node_id} 升级到 Lv.{new_level} {reputation.title}")

    async def _rebuild_leaderboard(self):
        """重建排行榜"""
        self.leaderboard = [
            (r.total_score, node_id)
            for node_id, r in self.reputations.items()
        ]
        self.leaderboard.sort(key=lambda x: x[0], reverse=True)

    async def sync(self) -> bool:
        """同步信誉数据"""
        await self._save_data()
        return True

    # ==================== 数据管理 ====================

    async def _save_data(self):
        """保存数据"""
        try:
            data = {
                "reputations": {
                    node_id: rep.to_dict()
                    for node_id, rep in self.reputations.items()
                },
                "profiles": {
                    node_id: profile.to_dict()
                    for node_id, profile in self.profiles.items()
                }
            }
            
            await self.storage.put("reputation_data", data)
            
        except Exception as e:
            logger.error(f"保存信誉数据失败: {e}")

    async def _load_data(self):
        """加载数据"""
        try:
            data = await self.storage.get("reputation_data")
            if data:
                for node_id, rep_data in data.get("reputations", {}).items():
                    self.reputations[node_id] = ReputationScore(**rep_data)
                
                for node_id, profile_data in data.get("profiles", {}).items():
                    if isinstance(profile_data.get("node_type"), str):
                        profile_data["node_type"] = NodeType(profile_data["node_type"])
                    self.profiles[node_id] = NodeProfile(**profile_data)
                
                await self._rebuild_leaderboard()
                
        except Exception as e:
            logger.error(f"加载信誉数据失败: {e}")
