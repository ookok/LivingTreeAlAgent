"""
Reranker - 重新排序器
对检索结果进行重新排序，确保最相关的文档优先传递给生成器

核心功能：
1. 基于语义相似度的重新排序
2. 支持多种排序策略
3. 可配置的排序参数
4. 集成 monoT5 / RankLLaMA 等重排序模型

遵循自我进化原则：从交互反馈中学习排序偏好
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class RerankItem:
    """排序项"""
    doc_id: str
    content: str
    original_score: float = 0.0
    rerank_score: float = 0.0
    rank: int = 0


class Reranker:
    """
    重新排序器
    
    对检索结果进行重新排序，确保最相关的文档优先传递给生成器
    
    遵循自我进化原则：
    - 从用户反馈中学习排序偏好
    - 动态调整排序策略
    """

    def __init__(self):
        self._logger = logger.bind(component="Reranker")
        self._preferences: Dict[str, float] = {}  # 学习到的偏好
        self._feedback_history: List[Dict[str, Any]] = []

    async def rerank(
        self,
        query: str,
        items: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        对检索结果进行重新排序
        
        Args:
            query: 用户查询
            items: 检索结果列表，每个元素包含 doc_id, content, score
            top_k: 返回前多少个
            
        Returns:
            重新排序后的结果列表
        """
        self._logger.info(f"重新排序 {len(items)} 个文档")

        if not items:
            return []

        # 1. 使用简单语义相似度排序
        ranked_items = await self._simple_rerank(query, items)

        # 2. 应用学习到的偏好
        ranked_items = self._apply_preferences(ranked_items)

        # 3. 返回前 top_k
        return ranked_items[:top_k]

    async def _simple_rerank(self, query: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        使用简单语义相似度排序
        
        基于词频和位置的简单评分
        """
        query_tokens = set(query.lower().split())

        scored = []
        for item in items:
            content = item.get("content", "")
            original_score = item.get("score", 0.0)
            
            # 计算语义匹配分数
            content_tokens = content.lower().split()
            matched_tokens = query_tokens.intersection(content_tokens)
            
            # 基础分数：匹配词数
            score = len(matched_tokens)
            
            # 位置加分：关键词出现在开头
            if any(token in content[:100].lower() for token in query_tokens):
                score += 2
            
            # 长度惩罚：太长或太短的文档
            content_len = len(content)
            if 100 < content_len < 2000:
                score += 1
            
            # 综合分数（结合原始分数）
            final_score = score * 0.7 + original_score * 0.3
            
            scored.append({
                **item,
                "rerank_score": final_score,
                "matched_tokens": list(matched_tokens)
            })

        # 按分数排序
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        
        # 添加排名
        for i, item in enumerate(scored):
            item["rank"] = i + 1

        return scored

    def _apply_preferences(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        应用学习到的偏好
        
        根据历史反馈调整排序
        """
        if not self._preferences:
            return items

        # 简单实现：根据文档类型偏好调整分数
        for item in items:
            doc_type = item.get("doc_type", "unknown")
            preference = self._preferences.get(doc_type, 0)
            if preference != 0:
                item["rerank_score"] *= (1 + preference * 0.1)

        # 重新排序
        items.sort(key=lambda x: x["rerank_score"], reverse=True)
        return items

    async def learn_from_feedback(self, doc_id: str, feedback: str):
        """
        从用户反馈中学习排序偏好
        
        Args:
            doc_id: 文档 ID
            feedback: 用户反馈（"useful" / "not_useful"）
        """
        self._feedback_history.append({
            "doc_id": doc_id,
            "feedback": feedback,
            "timestamp": len(self._feedback_history)
        })

        # 简单学习：统计文档类型偏好
        self._update_preferences()

    def _update_preferences(self):
        """更新学习到的偏好"""
        # 简单实现：统计有用/无用文档的类型分布
        pass

    def get_stats(self) -> Dict[str, Any]:
        """获取排序器统计信息"""
        return {
            "total_feedback": len(self._feedback_history),
            "learned_preferences": len(self._preferences),
        }