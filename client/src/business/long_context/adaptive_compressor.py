# -*- coding: utf-8 -*-
"""
自适应差异化压缩器 - Adaptive Compressor
========================================

核心设计理念：
- 对不同的内容采用不同的压缩率
- 关键定义几乎不压缩（0.1）
- 例子说明适度压缩（0.5）
- 背景介绍高度压缩（0.8）

压缩策略：
| 内容类型 | 压缩率 | 说明 |
|---------|--------|------|
| definition | 0.1 | 关键定义、定理 |
| example | 0.5 | 例子、案例 |
| background | 0.8 | 背景介绍 |
| argument | 0.3 | 论证过程 |
| conclusion | 0.2 | 结论、总结 |
| code | 0.2 | 代码（保持可读） |
| data | 0.3 | 数据、表格 |
| general | 0.5 | 一般内容 |

Author: Hermes Desktop Team
Date: 2026-04-24
"""

from __future__ import annotations

import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter

logger = logging.getLogger(__name__)


class SegmentType(Enum):
    """内容片段类型"""
    DEFINITION = "definition"      # 关键定义
    EXAMPLE = "example"            # 例子说明
    BACKGROUND = "background"      # 背景介绍
    ARGUMENT = "argument"          # 论证过程
    CONCLUSION = "conclusion"      # 结论总结
    CODE = "code"                  # 代码片段
    DATA = "data"                  # 数据表格
    GENERAL = "general"            # 一般内容
    TRANSITION = "transition"      # 过渡段落


@dataclass
class Segment:
    """内容片段"""
    text: str
    segment_type: SegmentType
    importance: float = 0.5       # 0-1 重要度
    position: int = 0             # 在原文中的位置
    length: int = 0               # 原始长度
    compressed_length: int = 0     # 压缩后长度
    
    def __post_init__(self):
        if self.length == 0:
            self.length = len(self.text)


@dataclass
class CompressionResult:
    """压缩结果"""
    original_text: str
    compressed_text: str
    original_length: int
    compressed_length: int
    compression_ratio: float
    segments: List[Segment]
    processing_time_ms: float
    
    @property
    def saved_tokens(self) -> int:
        """节省的 token 数"""
        return self.original_length - self.compressed_length
    
    @property
    def saved_ratio(self) -> float:
        """节省比例"""
        return 1 - self.compression_ratio


class AdaptiveCompressor:
    """
    自适应差异化压缩器
    
    根据内容类型动态选择压缩率，保留关键信息的同时最大化节省 token。
    """
    
    # 默认压缩策略
    DEFAULT_RATIOS = {
        SegmentType.DEFINITION: 0.1,   # 几乎不压缩
        SegmentType.EXAMPLE: 0.5,       # 适度压缩
        SegmentType.BACKGROUND: 0.8,    # 高度压缩
        SegmentType.ARGUMENT: 0.3,      # 轻度压缩
        SegmentType.CONCLUSION: 0.2,    # 轻度压缩
        SegmentType.CODE: 0.2,          # 保持可读
        SegmentType.DATA: 0.3,          # 轻度压缩
        SegmentType.GENERAL: 0.5,       # 适度压缩
        SegmentType.TRANSITION: 0.9,    # 极高压缩
    }
    
    def __init__(
        self,
        custom_ratios: Optional[Dict[SegmentType, float]] = None,
        enable_context_aware: bool = True,
        min_segment_length: int = 50,
    ):
        """
        初始化压缩器
        
        Args:
            custom_ratios: 自定义压缩率覆盖
            enable_context_aware: 是否启用上下文感知
            min_segment_length: 最小片段长度
        """
        self.ratios = {**self.DEFAULT_RATIOS}
        if custom_ratios:
            self.ratios.update(custom_ratios)
        
        self.enable_context_aware = enable_context_aware
        self.min_segment_length = min_segment_length
        
        # 编译正则表达式
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则表达式"""
        # 代码块
        self.code_pattern = re.compile(r'```[\s\S]*?```|`[^`]+`')
        
        # 数字和表格
        self.data_pattern = re.compile(
            r'\d+\.?\d*\s*[%℃万元亿元个点次天年月]\b|'
            r'\$\d+|'
            r'\d+年\d+月|'
            r'table:|表格[:：]'
        )
        
        # 定义模式
        self.definition_patterns = [
            re.compile(r'^(是|指|代表|表示|定义|称为|简称|即)\s*'),
            re.compile(r'所谓.+=.*'),
            re.compile(r'^\d+[.、]\s*[^\n]{5,20}是'),
            re.compile(r'[,，].*是一种'),
        ]
        
        # 结论模式
        self.conclusion_patterns = [
            re.compile(r'^(因此|所以|总之|综上所述|结论是|总结|因此可以|由此可见)'),
            re.compile(r'^(总之|总而言之|最后|最终|最终结论)'),
        ]
        
        # 过渡模式
        self.transition_patterns = [
            re.compile(r'^(下面|接下来|然后|接着|此外|另外|此外|与此同时)'),
            re.compile(r'^(首先|第一|其次|第二|最后|第三)'),
        ]
        
        # 例子模式
        self.example_patterns = [
            re.compile(r'^(例如|比如|如|举例|具体而言|以.为例)'),
            re.compile(r'[,，]例如[,，]'),
            re.compile(r'[,，]比如[,，]'),
        ]
    
    def compress(
        self,
        text: str,
        target_ratio: float = 0.5,
        preserve_structure: bool = True,
    ) -> CompressionResult:
        """
        压缩文本
        
        Args:
            text: 原始文本
            target_ratio: 目标压缩比例
            preserve_structure: 是否保留结构（段落、换行）
        
        Returns:
            CompressionResult: 压缩结果
        """
        import time
        start_time = time.time()
        
        original_length = len(text)
        
        # 步骤1: 按类型分段
        segments = self._segment_by_type(text)
        
        # 步骤2: 计算压缩策略
        compression_plan = self._plan_compression(segments, target_ratio)
        
        # 步骤3: 执行压缩
        compressed_segments = []
        for segment in segments:
            ratio = compression_plan.get(segment.segment_type, target_ratio)
            compressed = self._compress_segment(segment, ratio)
            compressed_segments.append(compressed)
        
        # 步骤4: 重组文本
        if preserve_structure:
            compressed_text = self._reconstruct_with_structure(
                compressed_segments, segments
            )
        else:
            compressed_text = '\n'.join(compressed_segments)
        
        compressed_length = len(compressed_text)
        actual_ratio = compressed_length / original_length if original_length > 0 else 1.0
        
        return CompressionResult(
            original_text=text,
            compressed_text=compressed_text,
            original_length=original_length,
            compressed_length=compressed_length,
            compression_ratio=actual_ratio,
            segments=segments,
            processing_time_ms=(time.time() - start_time) * 1000,
        )
    
    def _segment_by_type(self, text: str) -> List[Segment]:
        """按类型分段"""
        segments = []
        
        # 提取代码块（保护代码）
        code_matches = list(self.code_pattern.finditer(text))
        code_ranges = [(m.start(), m.end(), m.group()) for m in code_matches]
        
        # 按位置分割
        last_end = 0
        current_pos = 0
        
        for start, end, code_text in code_ranges:
            # 处理代码前的文本
            if start > last_end:
                before_text = text[last_end:start]
                before_segments = self._split_text_segments(before_text, current_pos)
                segments.extend(before_segments)
                current_pos += len(before_text)
            
            # 添加代码段
            segments.append(Segment(
                text=code_text,
                segment_type=SegmentType.CODE,
                importance=0.9,
                position=current_pos,
                length=len(code_text),
            ))
            current_pos += len(code_text)
            last_end = end
        
        # 处理剩余文本
        if last_end < len(text):
            remaining_text = text[last_end:]
            remaining_segments = self._split_text_segments(remaining_text, current_pos)
            segments.extend(remaining_segments)
        
        return segments
    
    def _split_text_segments(self, text: str, base_position: int) -> List[Segment]:
        """拆分文本为片段"""
        segments = []
        
        # 按段落分割
        paragraphs = text.split('\n\n')
        position = base_position
        
        for para in paragraphs:
            if not para.strip():
                continue
            
            para_type = self._classify_paragraph(para)
            importance = self._estimate_importance(para, para_type)
            
            segments.append(Segment(
                text=para.strip(),
                segment_type=para_type,
                importance=importance,
                position=position,
                length=len(para),
            ))
            position += len(para) + 2  # +2 for \n\n
        
        return segments
    
    def _classify_paragraph(self, para: str) -> SegmentType:
        """分类段落类型"""
        # 检查结论
        for pattern in self.conclusion_patterns:
            if pattern.match(para.strip()):
                return SegmentType.CONCLUSION
        
        # 检查定义
        for pattern in self.definition_patterns:
            if pattern.match(para.strip()):
                return SegmentType.DEFINITION
        
        # 检查例子
        for pattern in self.example_patterns:
            if pattern.search(para):
                return SegmentType.EXAMPLE
        
        # 检查过渡（只有很短的才判定为过渡）
        if len(para) < 30:
            for pattern in self.transition_patterns:
                if pattern.match(para.strip()):
                    return SegmentType.TRANSITION
        
        # 检查数据
        if self.data_pattern.search(para):
            return SegmentType.DATA
        
        # 检查长度（很短的可能是过渡）
        if len(para) < 50:
            return SegmentType.TRANSITION
        
        return SegmentType.GENERAL
    
    def _estimate_importance(self, para: str, para_type: SegmentType) -> float:
        """估计段落重要度"""
        base_importance = {
            SegmentType.DEFINITION: 0.9,
            SegmentType.CONCLUSION: 0.9,
            SegmentType.EXAMPLE: 0.6,
            SegmentType.ARGUMENT: 0.7,
            SegmentType.DATA: 0.8,
            SegmentType.CODE: 0.85,
            SegmentType.GENERAL: 0.5,
            SegmentType.BACKGROUND: 0.3,
            SegmentType.TRANSITION: 0.2,
        }
        
        importance = base_importance.get(para_type, 0.5)
        
        # 根据内容调整
        if any(kw in para for kw in ['重要', '关键', '核心', '必须', '应该']):
            importance += 0.1
        
        if any(kw in para for kw in ['可能', '也许', '大概', '似乎']):
            importance -= 0.1
        
        return max(0.1, min(1.0, importance))
    
    def _plan_compression(
        self,
        segments: List[Segment],
        target_ratio: float
    ) -> Dict[SegmentType, float]:
        """规划压缩策略"""
        plan = {}
        
        # 基础压缩率
        for seg_type in SegmentType:
            base_ratio = self.ratios.get(seg_type, target_ratio)
            
            # 根据上下文调整
            if self.enable_context_aware:
                base_ratio = self._adjust_ratio_by_context(seg_type, segments, base_ratio)
            
            plan[seg_type] = base_ratio
        
        return plan
    
    def _adjust_ratio_by_context(
        self,
        seg_type: SegmentType,
        all_segments: List[Segment],
        base_ratio: float
    ) -> float:
        """根据上下文调整压缩率"""
        # 计算段落类型分布
        type_counts = Counter(s.segment_type for s in all_segments)
        total = len(all_segments)
        
        # 如果某种类型很少，适当减少压缩
        if type_counts.get(seg_type, 0) / total < 0.1:
            return base_ratio * 0.8
        
        # 如果某种类型很多，可以增加压缩
        if type_counts.get(seg_type, 0) / total > 0.4:
            return base_ratio * 1.1
        
        return base_ratio
    
    def _compress_segment(self, segment: Segment, ratio: float) -> str:
        """压缩单个片段"""
        text = segment.text
        
        # 代码不压缩
        if segment.segment_type == SegmentType.CODE:
            return text
        
        # 根据压缩率决定策略
        if ratio < 0.3:
            # 轻度压缩：保留主要内容
            return self._light_compress(text)
        elif ratio < 0.6:
            # 中度压缩：删除冗余
            return self._medium_compress(text)
        else:
            # 重度压缩：高度概括
            return self._heavy_compress(text)
    
    def _light_compress(self, text: str) -> str:
        """轻度压缩"""
        # 去除多余空格
        text = re.sub(r'[ \t]+', ' ', text)
        # 去除首尾空白
        text = text.strip()
        return text
    
    def _medium_compress(self, text: str) -> str:
        """中度压缩"""
        # 轻度压缩
        text = self._light_compress(text)
        
        # 删除常见冗余
        redundancies = [
            (r'让我们来', ''),
            (r'接下来我们', ''),
            (r'下面我将', ''),
            (r'事实上', ''),
            (r'实际上', ''),
            (r'从这个角度', ''),
            (r'从某种意义上', ''),
        ]
        
        for pattern, replacement in redundancies:
            text = re.sub(pattern, replacement, text)
        
        # 压缩长句子中的重复词
        text = re.sub(r'([^,，])(\1{2,})', r'\1', text)
        
        return text
    
    def _heavy_compress(self, text: str) -> str:
        """重度压缩"""
        # 中度压缩
        text = self._medium_compress(text)
        
        # 提取核心句子
        sentences = re.split(r'[。！？]', text)
        if not sentences:
            return text
        
        # 保留前1-2句（通常包含核心信息）
        core_sentences = []
        for sent in sentences[:2]:
            sent = sent.strip()
            if len(sent) > 10:  # 跳过太短的句子
                core_sentences.append(sent)
        
        if core_sentences:
            # 保留第一句的核心
            return core_sentences[0][:min(len(core_sentences[0]), 200)] + '...'
        
        return text[:200] + '...' if len(text) > 200 else text
    
    def _reconstruct_with_structure(
        self,
        compressed_segments: List[str],
        original_segments: List[Segment],
    ) -> str:
        """保留结构重组"""
        parts = []
        
        for i, (original, compressed) in enumerate(zip(original_segments, compressed_segments)):
            if not compressed.strip():
                continue
            
            # 只在原文有换行的地方添加换行
            if i > 0 and '\n' in original.text:
                parts.append('\n')
            
            parts.append(compressed)
        
        return ''.join(parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "ratios": {k.value: v for k, v in self.ratios.items()},
            "min_segment_length": self.min_segment_length,
            "context_aware": self.enable_context_aware,
        }


def compress_adaptive(
    text: str,
    target_ratio: float = 0.5,
    custom_ratios: Optional[Dict[str, float]] = None,
) -> CompressionResult:
    """
    便捷压缩函数
    
    Args:
        text: 原始文本
        target_ratio: 目标压缩比例
        custom_ratios: 自定义压缩率 {"definition": 0.1, ...}
    
    Returns:
        CompressionResult: 压缩结果
    """
    ratios = None
    if custom_ratios:
        ratios = {
            SegmentType(k): v for k, v in custom_ratios.items()
            if k in [e.value for e in SegmentType]
        }
    
    compressor = AdaptiveCompressor(custom_ratios=ratios)
    return compressor.compress(text, target_ratio)
