"""
ChunkOptimizer - 数据分块优化器

支持多种分块策略：
1. 固定大小分块（256-512 token）
2. small2big 策略（先小后大）
3. 滑动窗口策略
4. 基于语义的智能分块

遵循自我进化原则：
- 从使用中学习最优分块大小
- 动态调整分块策略
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum


class ChunkStrategy(Enum):
    """分块策略"""
    FIXED = "fixed"
    SMALL2BIG = "small2big"
    SLIDING_WINDOW = "sliding_window"
    SEMANTIC = "semantic"


@dataclass
class ChunkResult:
    """分块结果"""
    chunks: List[str]
    strategy: ChunkStrategy
    chunk_size: int
    overlap_size: int


class ChunkOptimizer:
    """
    数据分块优化器
    
    支持多种分块策略，自动选择最优方案。
    """

    def __init__(self):
        self._logger = logger.bind(component="ChunkOptimizer")
        self._default_chunk_sizes = [256, 384, 512]
        self._overlap_ratio = 0.2  # 20% 重叠
        self._learning_history = []

    async def chunk(
        self,
        text: str,
        strategy: ChunkStrategy = ChunkStrategy.FIXED,
        chunk_size: int = 512,
        overlap_size: Optional[int] = None
    ) -> ChunkResult:
        """
        对文本进行分块
        
        Args:
            text: 输入文本
            strategy: 分块策略
            chunk_size: 块大小（token数）
            overlap_size: 重叠大小（可选，默认使用重叠比例）
            
        Returns:
            ChunkResult
        """
        self._logger.info(f"分块策略: {strategy.value}, 块大小: {chunk_size}")

        if overlap_size is None:
            overlap_size = int(chunk_size * self._overlap_ratio)

        chunks = []
        
        if strategy == ChunkStrategy.FIXED:
            chunks = self._chunk_fixed(text, chunk_size, overlap_size)
        
        elif strategy == ChunkStrategy.SMALL2BIG:
            chunks = self._chunk_small2big(text)
        
        elif strategy == ChunkStrategy.SLIDING_WINDOW:
            chunks = self._chunk_sliding_window(text, chunk_size, overlap_size)
        
        elif strategy == ChunkStrategy.SEMANTIC:
            chunks = self._chunk_semantic(text, chunk_size)

        # 记录学习历史
        self._learning_history.append({
            "strategy": strategy.value,
            "chunk_size": chunk_size,
            "num_chunks": len(chunks),
            "text_length": len(text)
        })

        return ChunkResult(
            chunks=chunks,
            strategy=strategy,
            chunk_size=chunk_size,
            overlap_size=overlap_size
        )

    def _chunk_fixed(self, text: str, chunk_size: int, overlap_size: int) -> List[str]:
        """固定大小分块"""
        chunks = []
        text_length = len(text)
        start = 0

        while start < text_length:
            end = min(start + chunk_size, text_length)
            chunk = text[start:end]
            
            # 尽量在句子边界处分割
            if end < text_length:
                # 向前查找句子结束
                sentence_end = chunk.rfind('.')
                if sentence_end != -1 and sentence_end > chunk_size // 2:
                    end = start + sentence_end + 1
                    chunk = text[start:end]
            
            chunks.append(chunk)
            start = end - overlap_size

            if start >= text_length:
                break

        return chunks

    def _chunk_small2big(self, text: str) -> List[str]:
        """small2big 策略：先小后大"""
        chunks = []
        
        # 首先尝试小分块
        small_chunks = self._chunk_fixed(text, 256, int(256 * 0.2))
        
        # 如果块数太多，尝试较大的分块
        if len(small_chunks) > 10:
            medium_chunks = self._chunk_fixed(text, 384, int(384 * 0.2))
            chunks = medium_chunks
        else:
            chunks = small_chunks
        
        return chunks

    def _chunk_sliding_window(self, text: str, chunk_size: int, overlap_size: int) -> List[str]:
        """滑动窗口策略"""
        chunks = []
        text_length = len(text)
        step = chunk_size - overlap_size
        
        if step <= 0:
            step = 1

        for i in range(0, text_length, step):
            end = min(i + chunk_size, text_length)
            chunk = text[i:end]
            
            # 确保最后一个块至少有最小长度
            if i + step >= text_length and end - i < chunk_size // 2:
                # 将最后一小块合并到前一个块
                if chunks:
                    chunks[-1] = chunks[-1] + chunk
                    continue
            
            chunks.append(chunk)

        return chunks

    def _chunk_semantic(self, text: str, target_size: int) -> List[str]:
        """基于语义的智能分块"""
        chunks = []
        
        # 简单实现：按段落分割
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) <= target_size:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    def suggest_strategy(self, text_length: int, expected_query_type: str = "general") -> ChunkStrategy:
        """
        根据文本长度和查询类型建议分块策略
        
        Args:
            text_length: 文本长度
            expected_query_type: 查询类型（general/fact/qa/summary）
            
        Returns:
            推荐的分块策略
        """
        if text_length < 500:
            return ChunkStrategy.FIXED
        elif text_length < 2000:
            return ChunkStrategy.SLIDING_WINDOW
        else:
            if expected_query_type in ["qa", "fact"]:
                return ChunkStrategy.SMALL2BIG
            else:
                return ChunkStrategy.SEMANTIC

    def get_stats(self) -> Dict[str, Any]:
        """获取分块器统计信息"""
        return {
            "total_chunking_operations": len(self._learning_history),
            "preferred_chunk_size": self._learn_preferred_size(),
            "strategy_distribution": self._get_strategy_distribution()
        }

    def _learn_preferred_size(self) -> int:
        """从历史中学习最优块大小"""
        if not self._learning_history:
            return 512
        
        # 简单学习：返回最常用的块大小
        size_counts = {}
        for record in self._learning_history:
            size = record["chunk_size"]
            size_counts[size] = size_counts.get(size, 0) + 1
        
        return max(size_counts, key=size_counts.get)

    def _get_strategy_distribution(self) -> Dict[str, int]:
        """获取策略分布"""
        distribution = {}
        for record in self._learning_history:
            strategy = record["strategy"]
            distribution[strategy] = distribution.get(strategy, 0) + 1
        return distribution