"""
技能质量与匹配集成模块 - Skill Quality & Matching Integration
==========================================================

将 skill_quality_scorer.py 和 skill_matching_optimizer.py 集成到 SkillEvolutionAgent

核心功能：
1. 技能质量评估与追踪
2. 智能技能匹配
3. 技能推荐与预警
4. 反馈驱动的持续优化

Author: Hermes Desktop Team
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class SkillQualityAndMatchingIntegration:
    """
    技能质量与匹配集成器
    
    整合质量评分和匹配优化，为 Agent 提供智能技能推荐服务
    """

    def __init__(
        self,
        db = None,
        llm_client = None
    ):
        """初始化集成器"""
        self._scorer = None
        self._optimizer = None
        self._db = db
        self._llm = llm_client
        
        # 缓存
        self._skill_cache: Dict[str, Any] = {}
        self._last_refresh = 0.0
    
    @property
    def scorer(self):
        """获取评分器（懒加载）"""
        if self._scorer is None:
            from core.skill_evolution.skill_quality_scorer import SkillQualityScorer
            self._scorer = SkillQualityScorer()
        return self._scorer
    
    @property
    def optimizer(self):
        """获取匹配优化器（懒加载）"""
        if self._optimizer is None:
            from core.skill_evolution.skill_matching_optimizer import SkillMatchingOptimizer
            self._optimizer = SkillMatchingOptimizer(db=self._db, llm_client=self._llm)
        return self._optimizer
    
    def recommend_skill(
        self,
        query: str,
        task_type: str = "",
        required_tools: List[str] = None,
        user_id: str = "",
        context: Dict[str, Any] = None,
        task_complexity: float = 0.5
    ) -> Optional[Dict]:
        """
        智能推荐技能
        """
        from core.skill_evolution.skill_matching_optimizer import MatchRequest
        
        request = MatchRequest(
            query=query,
            task_type=task_type,
            required_tools=required_tools or [],
            user_id=user_id,
            context=context or {},
            task_complexity=task_complexity,
            threshold=30.0
        )
        
        match_result = self.optimizer.get_recommended_skill(request)
        
        if not match_result:
            return None
        
        skill = self._get_skill_by_id(match_result.skill_id)
        if not skill:
            return None
        
        quality_report = self.scorer.evaluate_skill(skill)
        
        return {
            "skill_id": skill.skill_id,
            "skill_name": skill.name,
            "description": skill.description,
            "match_score": match_result.score,
            "match_factors": match_result.factors,
            "predicted_success": match_result.predicted_success,
            "confidence": match_result.confidence,
            "reasons": match_result.reasons,
            "warnings": match_result.warnings,
            "quality_score": quality_report.weighted_score,
            "quality_trend": quality_report.trend,
            "success_rate": skill.success_rate,
            "use_count": skill.use_count,
            "evolution_status": skill.evolution_status.value,
            "recommended": match_result.recommended,
            "explanation": self.optimizer.get_match_explanation(match_result)
        }
    
    def find_similar_skills(
        self,
        query: str,
        top_k: int = 5,
        exclude_skill_id: str = None
    ) -> List[Dict]:
        """查找相似技能"""
        from core.skill_evolution.skill_matching_optimizer import MatchRequest
        
        request = MatchRequest(
            query=query,
            top_k=top_k * 2
        )
        
        results = self.optimizer.find_matches(request)
        
        if exclude_skill_id:
            results = [r for r in results if r.skill_id != exclude_skill_id]
        
        results = results[:top_k]
        
        skills_info = []
        for result in results:
            skill = self._get_skill_by_id(result.skill_id)
            if not skill:
                continue
            
            quality_report = self.scorer.evaluate_skill(skill)
            
            skills_info.append({
                "skill_id": skill.skill_id,
                "skill_name": skill.name,
                "match_score": result.score,
                "quality_score": quality_report.weighted_score,
                "predicted_success": result.predicted_success,
                "recommended": result.recommended,
                "success_rate": skill.success_rate,
                "use_count": skill.use_count,
                "evolution_status": skill.evolution_status.value
            })
        
        return skills_info
    
    def track_execution(
        self,
        skill_id: str,
        execution_record: Any,
        user_feedback: Dict = None
    ):
        """追踪技能执行"""
        if user_feedback:
            self.record_feedback(
                skill_id=skill_id,
                success=user_feedback.get("success", False),
                rating=user_feedback.get("rating"),
                user_id=user_feedback.get("user_id", "")
            )
    
    def record_feedback(
        self,
        skill_id: str,
        success: bool,
        rating: float = None,
        user_id: str = ""
    ):
        """记录用户反馈"""
        self.optimizer.record_feedback(skill_id, user_id, success, rating)
        logger.debug(f"已记录反馈: skill={skill_id}, success={success}")
    
    def get_quality_report(self, skill_id: str) -> Optional[Dict]:
        """获取技能质量报告"""
        skill = self._get_skill_by_id(skill_id)
        if not skill:
            return None
        
        report = self.scorer.evaluate_skill(skill)
        return report.to_dict()
    
    def get_skill_ranking(self) -> List[Dict]:
        """获取所有技能的质量排名"""
        skills = self._get_all_skills()
        if not skills:
            return []
        
        reports = self.scorer.batch_evaluate(skills)
        ranking = self.scorer.get_quality_ranking(reports)
        
        return [
            {
                "rank": r.rank,
                "skill_id": r.skill_id,
                "skill_name": r.skill_name,
                "quality_score": r.weighted_score,
                "percentile": r.percentile,
                "trend": r.trend,
                "success_rate": r.quality_score.details.get("success_rate", 0)
            }
            for r in ranking
        ]
    
    def _get_skill_by_id(self, skill_id: str):
        """获取技能（带缓存）"""
        if skill_id in self._skill_cache:
            return self._skill_cache[skill_id]
        
        if self._db:
            try:
                skill = self._db.get_skill(skill_id)
                if skill:
                    self._skill_cache[skill_id] = skill
                return skill
            except Exception as e:
                logger.warning(f"获取技能失败: {e}")
        
        return None
    
    def _get_all_skills(self) -> List:
        """获取所有技能"""
        if self._db:
            try:
                return self._db.get_all_skills()
            except Exception as e:
                logger.warning(f"获取技能列表失败: {e}")
        
        return []


# 全局实例
_integration: Optional[SkillQualityAndMatchingIntegration] = None


def get_integration() -> SkillQualityAndMatchingIntegration:
    """获取全局集成实例"""
    global _integration
    if _integration is None:
        _integration = SkillQualityAndMatchingIntegration()
    return _integration


def quick_recommend(query: str, task_type: str = "") -> Optional[Dict]:
    """快速推荐技能"""
    integration = get_integration()
    return integration.recommend_skill(query, task_type=task_type)


def get_skill_report(skill_id: str) -> Optional[Dict]:
    """快速获取技能质量报告"""
    integration = get_integration()
    return integration.get_quality_report(skill_id)


def quick_feedback(skill_id: str, success: bool, rating: float = None):
    """快速记录反馈"""
    integration = get_integration()
    integration.record_feedback(skill_id, success, rating)
