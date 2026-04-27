# -*- coding: utf-8 -*-
"""
语义分块器 - Semantic Chunker
==============================

LLM驱动的智能语义分块，不是简单的固定长度截断，
而是根据语义边界进行分块。

核心能力：
1. 语义边界检测（句子、段落、主题）
2. 动态分块大小（根据内容复杂度）
3. 块间关系追踪（继承、引用、因果）
4. 重叠窗口（避免边界信息丢失）

分块策略：
| 策略 | 适用场景 | 块大小 |
|------|---------|--------|
| SENTENCE | 短文本分析 | 1-5句 |
| PARAGRAPH | 标准文档 | 1-3段 |
| TOPIC | 长文档理解 | 主题一致 |
| SEMANTIC | 深度分析 | 语义完整 |
| HIERARCHICAL | 多级结构 | 多级嵌套 |

Author: Hermes Desktop Team
Date: 2026-04-24
"""

from __future__ import annotations

import re
import time
import logging
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class ChunkType(Enum):
    """分块类型"""
    SENTENCE = "sentence"           # 句子级
    PARAGRAPH = "paragraph"         # 段落级
    TOPIC = "topic"                 # 主题级
    SEMANTIC = "semantic"           # 语义完整
    SECTION = "section"             # 章节级
    DOCUMENT = "document"           # 文档级


@dataclass
class Chunk:
    """
    分块结果
    
    Attributes:
        content: 分块内容
        chunk_type: 分块类型
        index: 在原文中的位置
        start_pos: 起始位置
        end_pos: 结束位置
        summary: 分块摘要（可选）
        relations: 关联的分块索引
        importance: 重要度 0-1
        keywords: 关键词列表
        metadata: 元数据
    """
    content: str
    chunk_type: ChunkType
    index: int = 0
    start_pos: int = 0
    end_pos: int = 0
    summary: str = ""
    relations: List[int] = field(default_factory=list)
    importance: float = 0.5
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def length(self) -> int:
        """分块长度"""
        return len(self.content)
    
    @property
    def word_count(self) -> int:
        """词数（中文按字符计）"""
        return len(self.content)
    
    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"Chunk({self.chunk_type.value}, {self.index}, {len(self.content)}chars)"


class SemanticChunker:
    """
    语义分块器
    
    提供多种分块策略，从简单的句子分块到复杂的主题分块。
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        overlap: int = 100,
        min_chunk_size: int = 100,
        max_chunk_size: int = 2000,
        llm_client: Optional[Any] = None,
    ):
        """
        初始化分块器
        
        Args:
            chunk_size: 默认块大小（字符数）
            overlap: 重叠窗口大小
            min_chunk_size: 最小块大小
            max_chunk_size: 最大块大小
            llm_client: LLM客户端（用于智能分块）
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.llm_client = llm_client
        
        # 编译正则表达式
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则表达式"""
        # 句子边界
        self.sentence_end = re.compile(r'[。！？；\n]+')
        
        # 段落边界
        self.paragraph_end = re.compile(r'\n\n+')
        
        # 标题模式
        self.heading_pattern = re.compile(
            r'^(#{1,6}\s+|第[一二三四五六七八九十百千]+[章节段部分])\s*'
        )
        
        # 列表项
        self.list_pattern = re.compile(r'^\d+[.、]\s+|^[·•●○]\s+')
        
        # 代码块
        self.code_block = re.compile(r'```[\s\S]*?```')
        
        # 中文停用词（用于关键词提取）
        self.stop_words = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
            '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
            '你', '会', '着', '没有', '看', '好', '自己', '这', '那',
            '可以', '这个', '什么', '怎么', '为什么', '如何',
        }
    
    def chunk(
        self,
        text: str,
        strategy: str = "auto",
        task: Optional[str] = None,
    ) -> List[Chunk]:
        """
        分块主入口
        
        Args:
            text: 原始文本
            strategy: 分块策略
                - "auto": 自动选择策略
                - "sentence": 句子级
                - "paragraph": 段落级
                - "topic": 主题级
                - "semantic": 语义完整
                - "fixed": 固定大小
            task: 任务描述（用于智能选择）
        
        Returns:
            List[Chunk]: 分块列表
        """
        if not text or not text.strip():
            return []
        
        # 自动选择策略
        if strategy == "auto":
            strategy = self._select_strategy(text, task)
        
        # 执行分块
        if strategy == "sentence":
            chunks = self._chunk_by_sentence(text)
        elif strategy == "paragraph":
            chunks = self._chunk_by_paragraph(text)
        elif strategy == "topic":
            chunks = self._chunk_by_topic(text)
        elif strategy == "semantic":
            chunks = self._chunk_by_semantic(text)
        elif strategy == "hierarchical":
            chunks = self._chunk_hierarchical(text)
        else:
            chunks = self._chunk_by_size(text)
        
        # 提取关键词
        for chunk in chunks:
            chunk.keywords = self._extract_keywords(chunk.content)
        
        # 提取摘要
        for chunk in chunks:
            if not chunk.summary:
                chunk.summary = self._summarize_chunk(chunk.content)
        
        # 建立关系
        self._build_relations(chunks)
        
        return chunks
    
    def _select_strategy(self, text: str, task: Optional[str]) -> str:
        """自动选择分块策略"""
        length = len(text)
        
        # 根据任务选择
        if task:
            task_lower = task.lower()
            if any(kw in task_lower for kw in ['总结', '摘要', '概括']):
                return "paragraph"
            if any(kw in task_lower for kw in ['分析', '理解', '深入']):
                return "semantic"
            if any(kw in task_lower for kw in ['翻译', '润色']):
                return "sentence"
        
        # 根据长度选择
        if length < 500:
            return "sentence"
        elif length < 3000:
            return "paragraph"
        elif length < 10000:
            return "semantic"
        else:
            return "topic"
    
    def _chunk_by_sentence(self, text: str) -> List[Chunk]:
        """按句子分块"""
        chunks = []
        sentences = self.sentence_end.split(text)
        
        current_chunk = []
        current_size = 0
        index = 0
        position = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_len = len(sentence)
            
            # 如果单句超过限制，拆分
            if sentence_len > self.max_chunk_size:
                if current_chunk:
                    chunks.append(self._create_chunk(
                        ''.join(current_chunk),
                        ChunkType.SENTENCE,
                        index,
                        position
                    ))
                    index += 1
                    position += sum(len(s) for s in current_chunk)
                    current_chunk = []
                
                # 递归处理长句
                sub_chunks = self._split_long_text(sentence, self.max_chunk_size)
                for sub in sub_chunks:
                    chunks.append(self._create_chunk(
                        sub, ChunkType.SENTENCE, index, position
                    ))
                    index += 1
                    position += len(sub)
                
                current_size = 0
                continue
            
            # 检查是否需要创建新块
            if current_size + sentence_len > self.chunk_size and current_chunk:
                chunks.append(self._create_chunk(
                    ''.join(current_chunk),
                    ChunkType.SENTENCE,
                    index,
                    position
                ))
                index += 1
                position += sum(len(s) for s in current_chunk)
                current_chunk = []
                current_size = 0
            
            current_chunk.append(sentence + '。')
            current_size += sentence_len
        
        # 处理剩余内容
        if current_chunk:
            chunks.append(self._create_chunk(
                ''.join(current_chunk),
                ChunkType.SENTENCE,
                index,
                position
            ))
        
        return chunks
    
    def _chunk_by_paragraph(self, text: str) -> List[Chunk]:
        """按段落分块"""
        chunks = []
        paragraphs = self.paragraph_end.split(text)
        
        current_chunk = []
        current_size = 0
        index = 0
        position = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_len = len(para)
            
            # 检查段落类型
            if self.heading_pattern.match(para):
                # 标题：创建新块
                if current_chunk:
                    chunks.append(self._create_chunk(
                        '\n\n'.join(current_chunk),
                        ChunkType.PARAGRAPH,
                        index,
                        position
                    ))
                    index += 1
                    position += sum(len(s) + 2 for s in current_chunk)
                    current_chunk = []
                    current_size = 0
                
                # 标题单独成块
                chunks.append(self._create_chunk(
                    para, ChunkType.PARAGRAPH, index, position
                ))
                index += 1
                position += para_len
                continue
            
            # 如果单段超过限制，拆分
            if para_len > self.max_chunk_size:
                if current_chunk:
                    chunks.append(self._create_chunk(
                        '\n\n'.join(current_chunk),
                        ChunkType.PARAGRAPH,
                        index,
                        position
                    ))
                    index += 1
                    position += sum(len(s) + 2 for s in current_chunk)
                    current_chunk = []
                    current_size = 0
                
                sub_chunks = self._split_long_text(para, self.max_chunk_size)
                for sub in sub_chunks:
                    chunks.append(self._create_chunk(
                        sub, ChunkType.PARAGRAPH, index, position
                    ))
                    index += 1
                    position += len(sub)
                continue
            
            # 检查是否需要创建新块
            if current_size + para_len > self.chunk_size and current_chunk:
                chunks.append(self._create_chunk(
                    '\n\n'.join(current_chunk),
                    ChunkType.PARAGRAPH,
                    index,
                    position
                ))
                index += 1
                position += sum(len(s) + 2 for s in current_chunk)
                current_chunk = []
                current_size = 0
            
            current_chunk.append(para)
            current_size += para_len
        
        # 处理剩余内容
        if current_chunk:
            chunks.append(self._create_chunk(
                '\n\n'.join(current_chunk),
                ChunkType.PARAGRAPH,
                index,
                position
            ))
        
        return chunks
    
    def _chunk_by_topic(self, text: str) -> List[Chunk]:
        """按主题分块"""
        # 先按段落分块
        para_chunks = self._chunk_by_paragraph(text)
        
        # 合并相似主题的段落
        chunks = []
        current_topic = []
        current_type = ChunkType.PARAGRAPH
        index = 0
        position = 0
        
        for chunk in para_chunks:
            # 检测主题变化
            topic_changed = self._detect_topic_change(current_topic, [chunk])
            
            if topic_changed and current_topic:
                # 创建主题块
                chunks.append(self._create_chunk(
                    '\n\n'.join(c.content for c in current_topic),
                    ChunkType.TOPIC,
                    index,
                    position
                ))
                index += 1
                position += sum(len(c.content) + 2 for c in current_topic)
                current_topic = []
            
            current_topic.append(chunk)
        
        # 处理剩余内容
        if current_topic:
            chunks.append(self._create_chunk(
                '\n\n'.join(c.content for c in current_topic),
                ChunkType.TOPIC,
                index,
                position
            ))
        
        return chunks if chunks else para_chunks
    
    def _chunk_by_semantic(self, text: str) -> List[Chunk]:
        """按语义完整性分块"""
        # 使用 LLM 进行智能分块（如果有 LLM）
        if self.llm_client:
            return self._chunk_by_llm(text)
        
        # 回退到段落分块
        return self._chunk_by_paragraph(text)
    
    def _chunk_by_llm(self, text: str) -> List[Chunk]:
        """使用 LLM 进行语义分块"""
        # 构建提示
        prompt = f"""请将以下文本按语义完整性分成若干块，每块代表一个完整的语义单元。

要求：
1. 每个块应该包含完整的意思，不要在句子中间截断
2. 块的大小建议在 {self.chunk_size} 字符左右
3. 识别主题边界，在主题转换处断开
4. 保留代码块、列表等特殊结构

请以 JSON 格式返回分块结果：
{{
    "chunks": [
        {{"content": "第一块内容", "reason": "分块理由"}},
        {{"content": "第二块内容", "reason": "分块理由"}}
    ]
}}

文本内容：
{text[:5000]}"""  # 限制长度
        
        try:
            response = self.llm_client.chat(prompt)
            import json
            result = json.loads(response)
            
            chunks = []
            position = 0
            for i, item in enumerate(result.get("chunks", [])):
                content = item.get("content", "")
                start = text.find(content[:50]) if content else position
                
                chunks.append(Chunk(
                    content=content,
                    chunk_type=ChunkType.SEMANTIC,
                    index=i,
                    start_pos=start,
                    end_pos=start + len(content),
                    summary=item.get("reason", ""),
                ))
                position = start + len(content)
            
            return chunks
        except Exception as e:
            logger.warning(f"LLM 分块失败: {e}，回退到段落分块")
            return self._chunk_by_paragraph(text)
    
    def _chunk_hierarchical(self, text: str) -> List[Chunk]:
        """层级分块"""
        chunks = []
        
        # 第一级：段落
        para_chunks = self._chunk_by_paragraph(text)
        
        # 第二级：按大小合并
        current = []
        current_size = 0
        index = 0
        position = 0
        
        for chunk in para_chunks:
            if current_size + chunk.length > self.chunk_size and current:
                chunks.append(self._create_chunk(
                    '\n\n'.join(c.content for c in current),
                    ChunkType.SECTION,
                    index,
                    position
                ))
                index += 1
                position += sum(len(c.content) + 2 for c in current)
                current = []
                current_size = 0
            
            current.append(chunk)
            current_size += chunk.length
        
        if current:
            chunks.append(self._create_chunk(
                '\n\n'.join(c.content for c in current),
                ChunkType.SECTION,
                index,
                position
            ))
        
        return chunks
    
    def _chunk_by_size(self, text: str) -> List[Chunk]:
        """固定大小分块（带重叠）"""
        chunks = []
        position = 0
        index = 0
        
        while position < len(text):
            end_pos = min(position + self.chunk_size, len(text))
            
            # 尝试在句子边界截断
            if end_pos < len(text):
                boundary = self._find_boundary(text, position, end_pos)
                end_pos = boundary if boundary > position else end_pos
            
            chunk_text = text[position:end_pos]
            
            chunks.append(Chunk(
                content=chunk_text,
                chunk_type=ChunkType.SEMANTIC,
                index=index,
                start_pos=position,
                end_pos=end_pos,
            ))
            
            index += 1
            position = end_pos - self.overlap  # 减去重叠
            
            if position >= end_pos:
                position = end_pos
        
        return chunks
    
    def _find_boundary(self, text: str, start: int, end: int) -> int:
        """在范围内找到最近的句子边界"""
        # 向前查找
        for i in range(end - 1, start + 10, -1):
            if i < len(text) and text[i] in '。！？；\n':
                return i + 1
        
        # 向后查找
        for i in range(end, min(end + 50, len(text))):
            if text[i] in '。！？；\n':
                return i + 1
        
        return end
    
    def _split_long_text(self, text: str, max_size: int) -> List[str]:
        """拆分长文本"""
        parts = []
        position = 0
        
        while position < len(text):
            end = min(position + max_size, len(text))
            
            # 找句子边界
            boundary = self._find_boundary(text, position, end)
            
            parts.append(text[position:boundary])
            position = boundary
        
        return parts
    
    def _detect_topic_change(
        self,
        current: List[Chunk],
        new: List[Chunk]
    ) -> bool:
        """检测主题变化"""
        if not current or not new:
            return False
        
        # 提取关键词
        current_keywords = set()
        for chunk in current:
            current_keywords.update(chunk.keywords)
        
        new_keywords = set()
        for chunk in new:
            new_keywords.update(self._extract_keywords(chunk.content))
        
        # 计算重叠度
        if not new_keywords:
            return False
        
        overlap = len(current_keywords & new_keywords)
        ratio = overlap / len(new_keywords)
        
        # 重叠度低于阈值认为主题变化
        return ratio < 0.3
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单实现：提取连续的非停用词序列
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
        
        # 过滤停用词
        keywords = [
            w for w in words
            if w not in self.stop_words and len(w) >= 2
        ]
        
        # 统计频率
        freq = defaultdict(int)
        for w in keywords:
            freq[w] += 1
        
        # 取频率最高的 5 个
        top = sorted(freq.items(), key=lambda x: -x[1])[:5]
        return [w for w, _ in top]
    
    def _summarize_chunk(self, content: str) -> str:
        """生成块摘要"""
        # 简单实现：取前50字
        if len(content) <= 50:
            return content
        
        # 找第一个句号
        first_period = content.find('。')
        if first_period > 0 and first_period < 100:
            return content[:first_period + 1]
        
        return content[:50] + '...'
    
    def _create_chunk(
        self,
        content: str,
        chunk_type: ChunkType,
        index: int,
        position: int,
    ) -> Chunk:
        """创建 Chunk 对象"""
        return Chunk(
            content=content,
            chunk_type=chunk_type,
            index=index,
            start_pos=position,
            end_pos=position + len(content),
        )
    
    def _build_relations(self, chunks: List[Chunk]):
        """建立块间关系"""
        for i, chunk in enumerate(chunks):
            relations = []
            
            # 前一个块
            if i > 0:
                relations.append(i - 1)
            
            # 后一个块
            if i < len(chunks) - 1:
                relations.append(i + 1)
            
            # 查找相似主题的块
            for j, other in enumerate(chunks):
                if i != j and j not in relations:
                    overlap = set(chunk.keywords) & set(other.keywords)
                    if len(overlap) >= 2:
                        relations.append(j)
            
            chunk.relations = relations[:5]  # 最多5个关联
    
    def get_stats(self, chunks: List[Chunk]) -> Dict[str, Any]:
        """获取分块统计"""
        if not chunks:
            return {}
        
        return {
            "total_chunks": len(chunks),
            "total_length": sum(c.length for c in chunks),
            "avg_chunk_size": sum(c.length for c in chunks) / len(chunks),
            "chunk_types": {
                ct.value: len([c for c in chunks if c.chunk_type == ct])
                for ct in ChunkType
            },
            "overlap": self.overlap,
            "chunk_size": self.chunk_size,
        }


def chunk_semantic(
    text: str,
    strategy: str = "auto",
    chunk_size: int = 1000,
    overlap: int = 100,
) -> List[Chunk]:
    """
    便捷分块函数
    
    Args:
        text: 原始文本
        strategy: 分块策略
        chunk_size: 块大小
        overlap: 重叠大小
    
    Returns:
        List[Chunk]: 分块列表
    """
    chunker = SemanticChunker(
        chunk_size=chunk_size,
        overlap=overlap,
    )
    return chunker.chunk(text, strategy)
