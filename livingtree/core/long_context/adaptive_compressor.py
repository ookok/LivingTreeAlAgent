"""
自适应压缩器 (Adaptive Compressor)

动态压缩长上下文以适配 LLM 输入限制：
- 重要性评分 → 按重要性排序删除低分内容
- 摘要压缩 → 将长段落替换为摘要
- 分层压缩 → 逐步降低信息密度
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CompressionResult:
    original_length: int
    compressed_length: int
    compression_ratio: float
    method: str


class AdaptiveCompressor:

    def __init__(self, target_length: int = 2000):
        self.target_length = target_length

    def compress(self, text: str) -> str:
        if len(text) <= self.target_length:
            return text

        paragraphs = text.split('\n\n')
        scored = [(i, len(p), self._score_paragraph(p), p)
                  for i, p in enumerate(paragraphs) if p.strip()]

        return self._select_top_paragraphs(scored, self.target_length)

    def compress_aggressive(self, text: str) -> str:
        if len(text) <= self.target_length:
            return text

        lines = text.splitlines()
        result = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(('#', '//', '/*')):
                continue
            if len(stripped) < 10 and not stripped.endswith(('.', ':', ';')):
                continue
            result.append(stripped)

        if len('\n'.join(result)) > self.target_length:
            result = result[:int(self.target_length / 20)]

        return '\n'.join(result)

    def _score_paragraph(self, text: str) -> float:
        score = 1.0

        if any(k in text.lower() for k in
               ['结论', '总结', '核心', '关键', '重要']):
            score += 2.0
        if '?' in text:
            score += 1.0
        score += min(2.0, len(text) / 1000 * 2.0)

        return score

    def _select_top_paragraphs(self, scored: List, target: int) -> str:
        scored.sort(key=lambda x: -x[2])

        result = []
        total = 0
        for _, length, score, text in scored:
            if total + length > target and result:
                break
            result.append(text)
            total += length

        return '\n\n'.join(result)

    def get_compression_stats(self, original: str,
                              compressed: str,
                              method: str = "selective") -> CompressionResult:
        return CompressionResult(
            original_length=len(original),
            compressed_length=len(compressed),
            compression_ratio=(len(compressed) / max(len(original), 1)),
            method=method)


__all__ = ["CompressionResult", "AdaptiveCompressor"]
