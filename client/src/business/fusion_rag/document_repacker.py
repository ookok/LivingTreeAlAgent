"""
DocumentRepacker - 文档重新打包器

使用"反向"方法（相关性升序排列）对文档进行重新打包。

遵循自我进化原则：
- 从反馈中学习优化打包策略
- 动态调整打包顺序
"""

from typing import List, Dict, Any
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class DocumentChunk:
    """文档块"""
    content: str
    relevance_score: float
    position: int


@dataclass
class RepackResult:
    """重新打包结果"""
    repacked_text: str
    original_order: List[str]
    repacked_order: List[str]
    improvement_score: float = 0.0


class DocumentRepacker:
    """
    文档重新打包器
    
    使用"反向"方法对文档进行重新打包，提高检索准确性。
    
    核心思想：
    - 将最相关的文档放在最后
    - 这样在生成时，模型会更关注最新的（最相关的）信息
    """

    def __init__(self):
        self._logger = logger.bind(component="DocumentRepacker")
        self._learning_history = []

    async def repack(self, documents: List[Dict[str, Any]]) -> RepackResult:
        """
        重新打包文档
        
        Args:
            documents: 文档列表，每个文档包含 content 和 relevance_score
            
        Returns:
            RepackResult
        """
        self._logger.info(f"重新打包 {len(documents)} 个文档")

        if not documents:
            return RepackResult(
                repacked_text="",
                original_order=[],
                repacked_order=[]
            )

        # 创建文档块对象
        chunks = []
        original_order = []
        
        for i, doc in enumerate(documents):
            chunks.append(DocumentChunk(
                content=doc.get("content", ""),
                relevance_score=doc.get("relevance_score", 0.0),
                position=i
            ))
            original_order.append(doc.get("content", "")[:30] + "...")

        # 按相关性升序排列（最相关的放在最后）
        chunks.sort(key=lambda x: x.relevance_score)

        # 合并文档
        repacked_text = "\n\n---\n\n".join(chunk.content for chunk in chunks)

        repacked_order = [chunk.content[:30] + "..." for chunk in chunks]

        # 计算改进分数（基于相关性排序的变化）
        improvement_score = self._calculate_improvement(chunks)

        # 记录学习历史
        self._learning_history.append({
            "num_documents": len(documents),
            "improvement_score": improvement_score,
            "timestamp": len(self._learning_history)
        })

        return RepackResult(
            repacked_text=repacked_text,
            original_order=original_order,
            repacked_order=repacked_order,
            improvement_score=improvement_score
        )

    def _calculate_improvement(self, chunks: List[DocumentChunk]) -> float:
        """
        计算改进分数
        
        衡量重新打包对信息顺序的优化程度
        """
        # 检查是否按相关性升序排列
        is_ascending = all(
            chunks[i].relevance_score <= chunks[i+1].relevance_score
            for i in range(len(chunks) - 1)
        )
        
        if is_ascending:
            # 计算相关性分布的均匀度
            scores = [c.relevance_score for c in chunks]
            if len(scores) > 1:
                avg_score = sum(scores) / len(scores)
                variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
                # 方差越大，说明相关性差异越大，重新打包的效果可能越好
                return min(1.0, variance * 10)
            return 0.5
        return 0.0

    async def learn_from_feedback(self, improvement_score: float, feedback: str):
        """
        从反馈中学习
        
        Args:
            improvement_score: 改进分数
            feedback: 用户反馈（positive/neutral/negative）
        """
        self._learning_history.append({
            "improvement_score": improvement_score,
            "feedback": feedback,
            "timestamp": len(self._learning_history)
        })

    def get_stats(self) -> Dict[str, Any]:
        """获取打包器统计信息"""
        if not self._learning_history:
            return {
                "total_repacks": 0,
                "average_improvement": 0.0,
                "success_rate": 0.0
            }

        total_improvement = sum(h.get("improvement_score", 0) for h in self._learning_history)
        positive_feedbacks = sum(1 for h in self._learning_history if h.get("feedback") == "positive")

        return {
            "total_repacks": len(self._learning_history),
            "average_improvement": total_improvement / len(self._learning_history),
            "success_rate": positive_feedbacks / len(self._learning_history)
        }