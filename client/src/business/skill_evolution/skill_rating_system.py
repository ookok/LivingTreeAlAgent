"""
SkillRatingSystem - 技能评分系统

参考 Multica 的技能评分设计，实现技能评分与反馈机制。

功能：
1. 技能评分（1-5星）
2. 反馈收集
3. 技能推荐
4. 技能改进提醒
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum


class RatingType(Enum):
    """评分类型"""
    USABILITY = "usability"      # 易用性
    EFFECTIVENESS = "effectiveness"  # 有效性
    ACCURACY = "accuracy"        # 准确性
    PERFORMANCE = "performance"  # 性能
    OVERALL = "overall"          # 综合评分


@dataclass
class SkillRating:
    """技能评分"""
    rating_id: str
    skill_id: str
    user_id: str
    rating: int  # 1-5
    rating_type: RatingType = RatingType.OVERALL
    feedback: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SkillFeedback:
    """技能反馈"""
    feedback_id: str
    skill_id: str
    user_id: str
    content: str
    type: str = "general"  # bug, feature_request, suggestion, praise
    status: str = "pending"  # pending, resolved, rejected
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None


class SkillRatingSystem:
    """
    技能评分系统
    
    核心功能：
    1. 技能评分（1-5星）
    2. 反馈收集
    3. 技能推荐
    4. 技能改进提醒
    """
    
    def __init__(self):
        self._logger = logger.bind(component="SkillRatingSystem")
        self._ratings: Dict[str, SkillRating] = {}
        self._feedbacks: Dict[str, SkillFeedback] = {}
    
    async def rate_skill(self, skill_id: str, user_id: str, rating: int, 
                        rating_type: RatingType = RatingType.OVERALL, 
                        feedback: str = "") -> SkillRating:
        """
        评分技能
        
        Args:
            skill_id: 技能 ID
            user_id: 用户 ID
            rating: 评分（1-5）
            rating_type: 评分类型
            feedback: 反馈意见
            
        Returns:
            SkillRating
        """
        # 限制评分范围
        rating = max(1, min(5, rating))
        
        rating_id = f"rating_{len(self._ratings) + 1}"
        skill_rating = SkillRating(
            rating_id=rating_id,
            skill_id=skill_id,
            user_id=user_id,
            rating=rating,
            rating_type=rating_type,
            feedback=feedback
        )
        
        self._ratings[rating_id] = skill_rating
        self._logger.info(f"技能评分: {skill_id}, 用户: {user_id}, 评分: {rating}")
        
        # 如果评分高，推荐给其他用户
        if rating >= 4:
            await self._recommend_skill(skill_id)
        
        # 如果评分低，标记为需要改进
        if rating <= 2:
            await self._mark_as_needs_improvement(skill_id, feedback)
        
        return skill_rating
    
    async def add_feedback(self, skill_id: str, user_id: str, content: str, 
                          feedback_type: str = "general") -> SkillFeedback:
        """
        添加反馈
        
        Args:
            skill_id: 技能 ID
            user_id: 用户 ID
            content: 反馈内容
            feedback_type: 反馈类型（bug, feature_request, suggestion, praise）
            
        Returns:
            SkillFeedback
        """
        feedback_id = f"feedback_{len(self._feedbacks) + 1}"
        feedback = SkillFeedback(
            feedback_id=feedback_id,
            skill_id=skill_id,
            user_id=user_id,
            content=content,
            type=feedback_type
        )
        
        self._feedbacks[feedback_id] = feedback
        self._logger.info(f"技能反馈: {skill_id}, 用户: {user_id}")
        
        # 如果是 bug 反馈，立即通知开发者
        if feedback_type == "bug":
            await self._notify_developer(skill_id, content)
        
        return feedback
    
    async def resolve_feedback(self, feedback_id: str, resolved_by: str):
        """
        解决反馈
        
        Args:
            feedback_id: 反馈 ID
            resolved_by: 解决者 ID
        """
        feedback = self._feedbacks.get(feedback_id)
        if feedback:
            feedback.status = "resolved"
            feedback.resolved_at = datetime.now()
            self._logger.info(f"反馈已解决: {feedback_id}")
    
    async def get_skill_ratings(self, skill_id: str) -> List[SkillRating]:
        """获取技能的所有评分"""
        return [r for r in self._ratings.values() if r.skill_id == skill_id]
    
    async def get_skill_feedback(self, skill_id: str) -> List[SkillFeedback]:
        """获取技能的所有反馈"""
        return [f for f in self._feedbacks.values() if f.skill_id == skill_id]
    
    async def get_skill_average_rating(self, skill_id: str) -> float:
        """获取技能的平均评分"""
        ratings = await self.get_skill_ratings(skill_id)
        if not ratings:
            return 0.0
        return sum(r.rating for r in ratings) / len(ratings)
    
    async def get_top_skills(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取评分最高的技能"""
        skill_ratings = {}
        
        for rating in self._ratings.values():
            if rating.skill_id not in skill_ratings:
                skill_ratings[rating.skill_id] = []
            skill_ratings[rating.skill_id].append(rating.rating)
        
        # 计算平均评分
        skill_avg = []
        for skill_id, ratings in skill_ratings.items():
            avg_rating = sum(ratings) / len(ratings)
            skill_avg.append({"skill_id": skill_id, "average_rating": avg_rating, "vote_count": len(ratings)})
        
        # 按评分排序
        skill_avg.sort(key=lambda x: x["average_rating"], reverse=True)
        
        return skill_avg[:limit]
    
    async def get_skills_needing_improvement(self) -> List[Dict[str, Any]]:
        """获取需要改进的技能"""
        skill_avg = []
        
        for skill_id in set(r.skill_id for r in self._ratings.values()):
            avg_rating = await self.get_skill_average_rating(skill_id)
            if avg_rating < 3.0:
                skill_avg.append({"skill_id": skill_id, "average_rating": avg_rating})
        
        return skill_avg
    
    async def _recommend_skill(self, skill_id: str):
        """推荐技能给其他用户"""
        self._logger.info(f"推荐技能: {skill_id}")
        # 实际实现：可以发送通知、添加到推荐列表等
    
    async def _mark_as_needs_improvement(self, skill_id: str, feedback: str):
        """标记技能需要改进"""
        self._logger.warning(f"技能需要改进: {skill_id}, 原因: {feedback}")
    
    async def _notify_developer(self, skill_id: str, content: str):
        """通知开发者关于 bug 反馈"""
        self._logger.error(f"Bug 反馈: {skill_id}, 内容: {content}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        rating_type_counts = {}
        feedback_type_counts = {}
        feedback_status_counts = {}
        
        for rating in self._ratings.values():
            rating_type_counts[rating.rating_type.value] = rating_type_counts.get(rating.rating_type.value, 0) + 1
        
        for feedback in self._feedbacks.values():
            feedback_type_counts[feedback.type] = feedback_type_counts.get(feedback.type, 0) + 1
            feedback_status_counts[feedback.status] = feedback_status_counts.get(feedback.status, 0) + 1
        
        return {
            "total_ratings": len(self._ratings),
            "total_feedbacks": len(self._feedbacks),
            "rating_type_counts": rating_type_counts,
            "feedback_type_counts": feedback_type_counts,
            "feedback_status_counts": feedback_status_counts
        }