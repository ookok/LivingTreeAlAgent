"""
Recommendation Engine

推荐引擎，基于用户行为和内容相似性提供个性化推荐，集成DeepOnto实体嵌入。

作者: LivingTreeAI Team
日期: 2026-05-01
版本: 1.1.0
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from deeponto.embedding import OntologyEmbedding
    HAS_DEEPONTO = True
except ImportError:
    HAS_DEEPONTO = False


@dataclass
class Recommendation:
    """推荐结果"""
    page_id: str
    page_title: str
    summary: Optional[str]
    score: float
    reason: str
    tags: List[str] = field(default_factory=list)


class RecommendationEngine:
    """
    推荐引擎
    
    核心功能：
    - 基于浏览历史的页面推荐
    - 基于内容相似性的推荐
    - 发现潜在的知识连接
    - 个性化推荐
    """
    
    def __init__(self):
        """初始化推荐引擎"""
        self._wiki_core = None
        self._vector_store = None
        self._entity_kb = None
        
        self._user_history: Dict[str, List[str]] = {}  # user_id -> [page_ids]
        
        self._init_dependencies()
        logger.info("RecommendationEngine 初始化完成")
    
    def _init_dependencies(self):
        """初始化依赖模块"""
        try:
            from .wiki_core import WikiCore
            from ..fusion_rag.smart_vector_store import get_smart_vector_store
            from ..entity_management import get_entity_knowledge_base
            
            self._wiki_core = WikiCore()
            self._vector_store = get_smart_vector_store()
            self._entity_kb = get_entity_knowledge_base()
            
            logger.info("依赖模块加载成功")
        except ImportError as e:
            logger.warning(f"依赖模块加载失败: {e}")
    
    def track_view(self, user_id: str, page_id: str):
        """
        追踪用户浏览记录
        
        Args:
            user_id: 用户ID
            page_id: 页面ID
        """
        if user_id not in self._user_history:
            self._user_history[user_id] = []
        
        # 避免重复记录
        if page_id not in self._user_history[user_id]:
            self._user_history[user_id].append(page_id)
        
        # 限制历史记录数量
        if len(self._user_history[user_id]) > 50:
            self._user_history[user_id] = self._user_history[user_id][-50:]
        
        logger.debug(f"记录浏览: {user_id} -> {page_id}")
    
    def recommend_pages(self, user_id: str, limit: int = 10) -> List[Recommendation]:
        """
        推荐页面
        
        Args:
            user_id: 用户ID
            limit: 返回数量
            
        Returns:
            List 推荐结果列表
        """
        if not self._wiki_core:
            return []
        
        recommendations = []
        
        # 获取用户浏览历史
        history = self._user_history.get(user_id, [])
        
        if not history:
            # 如果没有历史记录，推荐热门页面
            return self._get_hot_pages(limit)
        
        # 基于历史记录推荐
        recommendations.extend(self._recommend_based_on_history(history, limit // 2))
        
        # 基于内容相似性推荐
        recommendations.extend(self._recommend_based_on_similarity(history[-1], limit // 2))
        
        # 去重并排序
        recommendations = self._deduplicate_and_sort(recommendations)
        
        return recommendations[:limit]
    
    def _get_hot_pages(self, limit: int) -> List[Recommendation]:
        """获取热门页面"""
        if not self._wiki_core:
            return []
        
        pages = self._wiki_core.get_all_pages()
        
        # 简单实现：返回最近更新的页面
        sorted_pages = sorted(pages, key=lambda p: p.updated_at, reverse=True)
        
        return [Recommendation(
            page_id=page.id,
            page_title=page.title,
            summary=page.summary,
            score=0.7,
            reason="热门页面",
            tags=page.tags,
        ) for page in sorted_pages[:limit]]
    
    def _recommend_based_on_history(self, history: List[str], limit: int) -> List[Recommendation]:
        """基于浏览历史推荐"""
        if not self._wiki_core:
            return []
        
        recommendations = []
        
        # 获取历史页面的标签
        all_tags = set()
        for page_id in history:
            page = self._wiki_core.get_page(page_id)
            if page:
                all_tags.update(page.tags)
        
        # 推荐具有相同标签的页面
        for tag in all_tags:
            tagged_pages = self._wiki_core.get_pages_by_tag(tag)
            for page in tagged_pages:
                if page.id not in history:
                    recommendations.append(Recommendation(
                        page_id=page.id,
                        page_title=page.title,
                        summary=page.summary,
                        score=0.6 + (len(page.tags) / 10),
                        reason=f"与您浏览的页面有相同标签「{tag}」",
                        tags=page.tags,
                    ))
        
        return recommendations[:limit]
    
    def _recommend_based_on_similarity(self, page_id: str, limit: int) -> List[Recommendation]:
        """基于内容相似性推荐"""
        if not self._wiki_core:
            return []
        
        page = self._wiki_core.get_page(page_id)
        if not page:
            return []
        
        recommendations = []
        
        # 获取页面内容中的实体
        entities = self._extract_entities(page.content)
        
        # 推荐包含相同实体的页面
        for entity in entities[:3]:
            entity_pages = self._wiki_core.search_pages(entity)
            for p in entity_pages:
                if p.id != page_id and p.id not in [r.page_id for r in recommendations]:
                    recommendations.append(Recommendation(
                        page_id=p.id,
                        page_title=p.title,
                        summary=p.summary,
                        score=0.5 + (entity_pages.index(p) / 10),
                        reason=f"包含相关实体「{entity}」",
                        tags=p.tags,
                    ))
        
        return recommendations[:limit]
    
    def _extract_entities(self, content: str) -> List[str]:
        """从内容中提取实体"""
        try:
            from ..entity_management import get_entity_recognizer
            
            recognizer = get_entity_recognizer()
            result = recognizer.recognize(content)
            
            entities = []
            for entity in result.entities:
                if entity.entity_type.value not in ["date", "number", "email", "phone", "url"]:
                    entities.append(entity.text)
            
            return entities
        except ImportError:
            return []
    
    def _deduplicate_and_sort(self, recommendations: List[Recommendation]) -> List[Recommendation]:
        """去重并排序"""
        seen = set()
        unique = []
        
        for rec in recommendations:
            if rec.page_id not in seen:
                seen.add(rec.page_id)
                unique.append(rec)
        
        # 按分数排序
        unique.sort(key=lambda r: r.score, reverse=True)
        
        return unique
    
    def suggest_missing_links(self, page_id: str) -> List[Dict[str, Any]]:
        """
        建议缺失的链接
        
        Args:
            page_id: 页面ID
            
        Returns:
            List 建议链接列表
        """
        if not self._wiki_core:
            return []
        
        page = self._wiki_core.get_page(page_id)
        if not page:
            return []
        
        suggestions = []
        
        # 提取页面中的实体
        entities = self._extract_entities(page.content)
        
        # 检查哪些实体没有对应的Wiki页面
        for entity in entities:
            existing_page = self._wiki_core.get_page_by_title(entity)
            if not existing_page:
                suggestions.append({
                    "entity": entity,
                    "suggested_title": entity,
                    "reason": f"「{entity}」没有对应的Wiki页面",
                    "confidence": 0.7,
                })
        
        return suggestions
    
    def get_personalized_digest(self, user_id: str) -> Dict[str, Any]:
        """
        获取个性化摘要
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict 个性化摘要数据
        """
        history = self._user_history.get(user_id, [])
        
        # 统计浏览过的标签
        tag_counts = {}
        for page_id in history:
            page = self._wiki_core.get_page(page_id)
            if page:
                for tag in page.tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # 推荐感兴趣的主题
        interests = sorted(tag_counts.keys(), key=lambda t: tag_counts[t], reverse=True)[:3]
        
        return {
            "user_id": user_id,
            "pages_viewed": len(history),
            "interests": interests,
            "recommendations": self.recommend_pages(user_id, 5),
        }


# 全局推荐引擎实例
_recommender_instance = None

def get_recommendation_engine() -> RecommendationEngine:
    """获取全局推荐引擎实例"""
    global _recommender_instance
    if _recommender_instance is None:
        _recommender_instance = RecommendationEngine()
    return _recommender_instance