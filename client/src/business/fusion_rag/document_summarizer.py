"""
DocumentSummarizer - 文档摘要器

使用 Recomp 或类似方法进行文档摘要，降低 token 占用成本。

遵循自我进化原则：
- 从反馈中学习优化摘要质量
- 支持多种摘要策略
- 自动选择最佳摘要方式
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum


class SummaryStrategy(Enum):
    """摘要策略"""
    EXTRACTIVE = "extractive"      # 抽取式摘要
    ABSTRACTIVE = "abstractive"    # 抽象式摘要
    HYBRID = "hybrid"              # 混合式摘要
    RECOMP = "recomp"              # Recomp 方法


@dataclass
class SummaryResult:
    """摘要结果"""
    summary: str
    strategy: SummaryStrategy
    original_length: int
    summary_length: int
    compression_ratio: float


class DocumentSummarizer:
    """
    文档摘要器
    
    支持多种摘要策略，自动选择最佳方案。
    """

    def __init__(self):
        self._logger = logger.bind(component="DocumentSummarizer")
        self._learning_history = []

    async def summarize(
        self,
        text: str,
        strategy: SummaryStrategy = SummaryStrategy.HYBRID,
        max_length: int = 500,
        target_ratio: float = 0.3
    ) -> SummaryResult:
        """
        对文档进行摘要
        
        Args:
            text: 输入文本
            strategy: 摘要策略
            max_length: 最大摘要长度
            target_ratio: 目标压缩比
            
        Returns:
            SummaryResult
        """
        self._logger.info(f"摘要策略: {strategy.value}")

        original_length = len(text)
        summary = ""

        if strategy == SummaryStrategy.EXTRACTIVE:
            summary = await self._extractive_summary(text, max_length)
        
        elif strategy == SummaryStrategy.ABSTRACTIVE:
            summary = await self._abstractive_summary(text, max_length)
        
        elif strategy == SummaryStrategy.HYBRID:
            summary = await self._hybrid_summary(text, max_length)
        
        elif strategy == SummaryStrategy.RECOMP:
            summary = await self._recomp_summary(text, max_length, target_ratio)

        summary_length = len(summary)
        compression_ratio = summary_length / max(original_length, 1)

        # 记录学习历史
        self._learning_history.append({
            "strategy": strategy.value,
            "original_length": original_length,
            "summary_length": summary_length,
            "compression_ratio": compression_ratio
        })

        return SummaryResult(
            summary=summary,
            strategy=strategy,
            original_length=original_length,
            summary_length=summary_length,
            compression_ratio=compression_ratio
        )

    async def _extractive_summary(self, text: str, max_length: int) -> str:
        """抽取式摘要：提取关键句子"""
        # 简单实现：提取段落首句
        paragraphs = text.split('\n\n')
        sentences = []
        
        for para in paragraphs:
            # 提取段落的前几个句子
            period_pos = para.find('.')
            if period_pos != -1:
                sentences.append(para[:period_pos + 1])
        
        # 合并并截断到最大长度
        summary = ' '.join(sentences)
        return summary[:max_length]

    async def _abstractive_summary(self, text: str, max_length: int) -> str:
        """抽象式摘要：使用 LLM 生成新摘要"""
        try:
            from business.global_model_router import GlobalModelRouter, ModelCapability
            
            router = GlobalModelRouter()
            prompt = f"""
请对以下文本进行摘要，保持核心信息，控制在 {max_length} 字以内：

{text[:3000]}
"""
            response = router.call_model_sync(
                capability=ModelCapability.SUMMARIZATION,
                prompt=prompt,
                temperature=0.3
            )
            return response.strip()[:max_length]
        
        except Exception as e:
            self._logger.warning(f"抽象式摘要失败，降级到抽取式: {e}")
            return await self._extractive_summary(text, max_length)

    async def _hybrid_summary(self, text: str, max_length: int) -> str:
        """混合式摘要：抽取+抽象结合"""
        # 先抽取关键信息，再用抽象式方法优化
        extractive = await self._extractive_summary(text, int(max_length * 1.5))
        return await self._abstractive_summary(extractive, max_length)

    async def _recomp_summary(self, text: str, max_length: int, target_ratio: float) -> str:
        """
        Recomp 方法摘要
        
        Recomp (Recursive Compression) 是一种递归压缩方法：
        1. 将文档分成小块
        2. 对每块进行摘要
        3. 递归合并摘要直到达到目标长度
        """
        chunks = self._chunk_text(text, int(max_length / target_ratio))
        summaries = []
        
        for chunk in chunks:
            chunk_summary = await self._abstractive_summary(chunk, int(max_length / len(chunks)))
            summaries.append(chunk_summary)
        
        # 合并摘要
        combined = ' '.join(summaries)
        
        # 如果仍然太长，继续压缩
        if len(combined) > max_length:
            return await self._recomp_summary(combined, max_length, 1.0)
        
        return combined

    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """将文本分块"""
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
        return chunks

    async def learn_from_feedback(self, summary: str, rating: int):
        """
        从反馈中学习
        
        Args:
            summary: 生成的摘要
            rating: 用户评分（1-5）
        """
        self._learning_history.append({
            "summary_length": len(summary),
            "rating": rating,
            "timestamp": len(self._learning_history)
        })

    def suggest_strategy(self, text_length: int) -> SummaryStrategy:
        """
        根据文本长度建议摘要策略
        
        Args:
            text_length: 文本长度
            
        Returns:
            推荐的摘要策略
        """
        if text_length < 500:
            return SummaryStrategy.EXTRACTIVE
        elif text_length < 2000:
            return SummaryStrategy.HYBRID
        else:
            return SummaryStrategy.RECOMP

    def get_stats(self) -> Dict[str, Any]:
        """获取摘要器统计信息"""
        if not self._learning_history:
            return {
                "total_summaries": 0,
                "average_compression_ratio": 0,
                "preferred_strategy": "hybrid"
            }

        total_ratio = sum(h.get("compression_ratio", 0) for h in self._learning_history)
        strategy_counts = {}
        
        for record in self._learning_history:
            strategy = record.get("strategy", "hybrid")
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

        return {
            "total_summaries": len(self._learning_history),
            "average_compression_ratio": total_ratio / len(self._learning_history),
            "preferred_strategy": max(strategy_counts, key=strategy_counts.get)
        }