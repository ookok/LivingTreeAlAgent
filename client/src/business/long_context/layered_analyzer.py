# -*- coding: utf-8 -*-
"""
分层混合分析器 - Layered Hybrid Analyzer
=========================================

四层分析架构，为长文本提供从概览到细节的渐进式理解。

架构设计：
┌─────────────────────────────────────────────────────────────┐
│                    LayeredHybridAnalyzer                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 1: 超级摘要提取 (Super Summary)                      │
│  └── 用极简方式（<100字）获取全局结构和核心观点              │
│                                                             │
│  Layer 2: 分块深度分析 (Deep Chunk Analysis)                │
│  └── 对每个语义块独立分析，多轮对话探索                      │
│                                                             │
│  Layer 3: 关系网络构建 (Relation Network)                    │
│  └── 分析块间的联系：因果/对比/补充/引用                    │
│                                                             │
│  Layer 4: 综合分析 (Synthesis)                              │
│  └── 基于前三层结果生成最终分析报告                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘

设计原则：
1. 复用 Phase 1 组件 (SemanticChunker, ChunkAnalyzer, MultiTurnAnalyzer)
2. 支持增量计算和流式输出
3. 与 UnifiedContext 集成
4. 可配置的分析深度和超时控制

Author: Hermes Desktop Team
Date: 2026-04-24
from __future__ import annotations
"""


import re
import logging
import time
from typing import (
    List, Dict, Any, Optional, Callable, Iterator, 
    TypeVar, Generic, Union
)
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# 复用 Phase 1 组件
from .semantic_chunker import SemanticChunker, Chunk, ChunkType
from .chunk_analyzer import ChunkAnalyzer, ChunkAnalysis


# ============================================================================
# 数据结构定义
# ============================================================================

class AnalysisDepth(Enum):
    """分析深度枚举"""
    QUICK = "quick"        # 快速概览（仅 Layer 1）
    STANDARD = "standard"  # 标准分析（Layer 1-2）
    DEEP = "deep"          # 深度分析（Layer 1-3）
    COMPREHENSIVE = "comprehensive"  # 全面分析（Layer 1-4）


class RelationType(Enum):
    """关系类型枚举"""
    CAUSAL = "causal"           # 因果关系
    CONTRAST = "contrast"       # 对比关系
    SUPPLEMENT = "supplement"   # 补充关系
    REFERENCE = "reference"      # 引用关系
    SEQUENCE = "sequence"        # 顺序关系
    ELABORATION = "elaboration"  # 详述关系


@dataclass
class ChunkRelation:
    """分块关系"""
    from_chunk: int
    to_chunk: int
    relation_type: RelationType
    description: str
    strength: float = 0.5  # 关系强度 0-1
    
    @property
    def is_strong(self) -> bool:
        return self.strength >= 0.6


@dataclass
class Layer1Summary:
    """Layer 1: 超级摘要"""
    # 核心摘要（<100字）
    core_summary: str
    # 结构概述
    structure: str
    # 核心观点（最多5个）
    key_points: List[str] = field(default_factory=list)
    # 文档类型
    doc_type: str = ""
    # 预估质量
    confidence: float = 0.0
    
    @property
    def total_length(self) -> int:
        return len(self.core_summary)


@dataclass
class Layer2ChunkAnalysis:
    """Layer 2: 分块深度分析结果"""
    chunk_index: int
    chunk: Chunk
    # 独立分析结果
    analysis: ChunkAnalysis
    # 多轮探索结果
    exploration_results: List[Dict[str, Any]] = field(default_factory=list)
    # 追问列表（用于后续探索）
    follow_up_questions: List[str] = field(default_factory=list)
    # 洞察
    insights: List[str] = field(default_factory=list)
    # 与整体目标的关联
    relevance_to_task: float = 0.5
    
    @property
    def key_findings(self) -> List[str]:
        """关键发现"""
        findings = []
        findings.extend(self.analysis.key_points[:3])
        findings.extend([e.get("insight", "") for e in self.exploration_results if "insight" in e])
        return findings[:5]


@dataclass
class Layer3RelationNetwork:
    """Layer 3: 关系网络"""
    # 所有关系
    relations: List[ChunkRelation] = field(default_factory=list)
    # 关系统计
    relation_stats: Dict[str, int] = field(default_factory=dict)
    # 关键连接（核心节点）
    key_connections: List[Tuple[int, int]] = field(default_factory=list)
    # 聚类分析（相关的chunk组）
    clusters: List[List[int]] = field(default_factory=list)
    # 缺失的连接（可能存在但未识别的关系）
    potential_relations: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def total_relations(self) -> int:
        return len(self.relations)
    
    @property
    def strong_relations(self) -> List[ChunkRelation]:
        return [r for r in self.relations if r.is_strong]


@dataclass
class Layer4Synthesis:
    """Layer 4: 综合分析"""
    # 最终报告
    report: str
    # 结构化总结
    structured_summary: Dict[str, Any] = field(default_factory=dict)
    # 结论
    conclusions: List[str] = field(default_factory=list)
    # 建议
    recommendations: List[str] = field(default_factory=list)
    # 知识图谱（简化版）
    knowledge_graph: Dict[str, Any] = field(default_factory=dict)
    # 置信度
    confidence: float = 0.0
    # 分析耗时（秒）
    processing_time: float = 0.0


@dataclass
class LayeredAnalysisResult:
    """分层分析完整结果"""
    # 各层结果
    layer1_summary: Optional[Layer1Summary] = None
    layer2_analyses: List[Layer2ChunkAnalysis] = field(default_factory=list)
    layer3_network: Optional[Layer3RelationNetwork] = None
    layer4_synthesis: Optional[Layer4Synthesis] = None
    
    # 分析配置
    depth: AnalysisDepth = AnalysisDepth.STANDARD
    total_chunks: int = 0
    
    # 性能指标
    start_time: float = 0.0
    end_time: float = 0.0
    
    # 错误信息
    errors: List[str] = field(default_factory=list)
    
    @property
    def processing_time(self) -> float:
        return self.end_time - self.start_time if self.end_time > 0 else 0.0
    
    @property
    def is_complete(self) -> bool:
        return self.layer4_synthesis is not None
    
    def get_layer(self, layer: int) -> Any:
        """获取指定层的结果"""
        layers = {
            1: self.layer1_summary,
            2: self.layer2_analyses,
            3: self.layer3_network,
            4: self.layer4_synthesis,
        }
        return layers.get(layer)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "depth": self.depth.value,
            "total_chunks": self.total_chunks,
            "processing_time": self.processing_time,
            "is_complete": self.is_complete,
            "errors": self.errors,
            "layer1_summary": self.layer1_summary.core_summary if self.layer1_summary else None,
            "layer2_count": len(self.layer2_analyses),
            "layer3_relations": self.layer3_network.total_relations if self.layer3_network else 0,
            "layer4_conclusions": len(self.layer4_synthesis.conclusions) if self.layer4_synthesis else 0,
        }


# ============================================================================
# 分层分析器核心实现
# ============================================================================

class LayeredHybridAnalyzer:
    """
    分层混合分析器
    
    四层分析架构：
    1. 超级摘要：用极简方式获取全局概念
    2. 分块深度分析：每个分块独立探索
    3. 关系网络：构建块间关系
    4. 综合分析：生成最终报告
    
    使用示例：
    ```python
    analyzer = LayeredHybridAnalyzer()
    result = analyzer.analyze(text, task="总结要点")
    print(result.layer4_synthesis.report)
    ```
    """
    
    def __init__(
        self,
        # 分块配置
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        # 分析深度
        default_depth: AnalysisDepth = AnalysisDepth.STANDARD,
        # Layer 2 配置
        max_turns_per_chunk: int = 3,
        # Layer 3 配置
        min_relation_strength: float = 0.3,
        # 性能配置
        max_workers: int = 4,
        timeout_per_layer: int = 300,
        # LLM 配置
        llm_config: Optional[Dict[str, Any]] = None,
        # 回调函数
        progress_callback: Optional[Callable[[str, float], None]] = None,
        # ChunkAnalyzer 实例
        chunk_analyzer: Optional[ChunkAnalyzer] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.default_depth = default_depth
        self.max_turns_per_chunk = max_turns_per_chunk
        self.min_relation_strength = min_relation_strength
        self.max_workers = max_workers
        self.timeout_per_layer = timeout_per_layer
        self.llm_config = llm_config or {}
        self.progress_callback = progress_callback
        self._chunk_analyzer = chunk_analyzer
        
        # 初始化子组件
        self._init_components()
        
        # 统计信息
        self.stats = {
            "total_analyzes": 0,
            "total_chunks_processed": 0,
            "total_time": 0.0,
        }
    
    def _init_components(self):
        """初始化子组件"""
        # 语义分块器
        self.chunker = SemanticChunker(
            chunk_size=self.chunk_size,
            overlap=self.chunk_overlap,
        )
        
        # 分块分析器
        self.chunk_analyzer = self._chunk_analyzer or ChunkAnalyzer()
    
    def analyze(
        self,
        text: str,
        task: str = "总结要点",
        depth: Optional[AnalysisDepth] = None,
        chunk_strategy: str = "auto",
    ) -> LayeredAnalysisResult:
        """
        执行分层分析
        
        Args:
            text: 待分析文本
            task: 分析任务描述
            depth: 分析深度
            chunk_strategy: 分块策略
            
        Returns:
            LayeredAnalysisResult: 分层分析结果
        """
        depth = depth or self.default_depth
        result = LayeredAnalysisResult(
            depth=depth,
            start_time=time.time(),
        )
        
        try:
            self._report_progress("开始分层分析...", 0.0)
            
            # Layer 1: 超级摘要
            result.layer1_summary = self._layer1_super_summary(text, task)
            result.total_chunks = 0
            self._report_progress("Layer 1 完成", 0.2)
            
            # Layer 2: 分块深度分析
            if depth.value in ["standard", "deep", "comprehensive"]:
                chunks = self.chunker.chunk(text, strategy=chunk_strategy)
                result.total_chunks = len(chunks)
                result.layer2_analyses = self._layer2_deep_analysis(
                    chunks, task, result.layer1_summary
                )
                self._report_progress("Layer 2 完成", 0.5)
            
            # Layer 3: 关系网络
            if depth.value in ["deep", "comprehensive"]:
                result.layer3_network = self._layer3_relation_network(
                    result.layer2_analyses
                )
                self._report_progress("Layer 3 完成", 0.75)
            
            # Layer 4: 综合分析
            if depth.value == "comprehensive":
                result.layer4_synthesis = self._layer4_synthesis(
                    text, task, result
                )
                self._report_progress("Layer 4 完成", 0.95)
            
            result.end_time = time.time()
            
            # 更新统计
            self._update_stats(result)
            
            self._report_progress("分析完成", 1.0)
            
        except Exception as e:
            logger.error(f"分层分析失败: {e}")
            result.errors.append(str(e))
            result.end_time = time.time()
        
        return result
    
    def analyze_streaming(
        self,
        text: str,
        task: str = "总结要点",
        depth: Optional[AnalysisDepth] = None,
    ) -> Iterator[Tuple[str, Any, float]]:
        """
        流式分析，实时返回各层结果
        
        Yields:
            Tuple[str, Any, float]: (层名称, 层结果, 进度)
        """
        depth = depth or self.default_depth
        
        # Layer 1
        yield "layer1", None, 0.0
        layer1 = self._layer1_super_summary(text, task)
        yield "layer1", layer1, 0.2
        
        # Layer 2
        if depth.value in ["standard", "deep", "comprehensive"]:
            yield "layer2", None, 0.3
            chunks = self.chunker.chunk(text)
            layer2_results = []
            for i, chunk in enumerate(chunks):
                chunk_result = self._analyze_single_chunk(chunk, task, layer1)
                layer2_results.append(chunk_result)
                progress = 0.3 + (i / len(chunks)) * 0.2
                yield "layer2_progress", chunk_result, progress
            yield "layer2", layer2_results, 0.5
        
        # Layer 3
        if depth.value in ["deep", "comprehensive"]:
            yield "layer3", None, 0.6
            layer3 = self._layer3_relation_network(layer2_results)
            yield "layer3", layer3, 0.75
        
        # Layer 4
        if depth.value == "comprehensive":
            yield "layer4", None, 0.8
            layer4 = self._layer4_synthesis(text, task, None)
            yield "layer4", layer4, 1.0
    
    # =========================================================================
    # Layer 1: 超级摘要
    # =========================================================================
    
    def _layer1_super_summary(self, text: str, task: str) -> Layer1Summary:
        """
        Layer 1: 生成超级摘要
        
        用极简方式（<100字）获取全局结构和核心观点。
        关键：压缩率要足够高，但保留核心结构。
        """
        # 计算文本基本信息
        total_length = len(text)
        lines = text.split('\n')
        paragraphs = [p for p in text.split('\n\n') if p.strip()]
        
        # 估算句子数量
        sentence_count = len(re.findall(r'[。！？.!?]+', text))
        
        # 提取高频词作为关键词
        keywords = self._extract_keywords_quick(text)
        
        # 生成结构概述
        structure = self._analyze_structure(text)
        
        # 识别文档类型
        doc_type = self._identify_doc_type(text)
        
        # 生成核心摘要
        core_summary = self._generate_core_summary(text, task, structure)
        
        # 提取关键观点
        key_points = self._extract_key_points(text, structure)
        
        return Layer1Summary(
            core_summary=core_summary,
            structure=structure,
            key_points=key_points[:5],  # 最多5个
            doc_type=doc_type,
            confidence=0.8,
        )
    
    def _extract_keywords_quick(self, text: str, top_n: int = 10) -> List[str]:
        """快速提取关键词（无需LLM）"""
        # 停用词
        stop_words = {
            '的', '了', '是', '在', '我', '有', '和', '就', '不', '人',
            '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
            '你', '会', '着', '没有', '看', '好', '自己', '这', '那',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        }
        
        # 简单分词（按空格和标点）
        words = re.findall(r'[\w\u4e00-\u9fff]{2,}', text.lower())
        
        # 过滤停用词和短词
        words = [w for w in words if w not in stop_words and len(w) > 1]
        
        # 统计词频
        word_freq = defaultdict(int)
        for word in words:
            word_freq[word] += 1
        
        # 返回高频词
        return [w for w, _ in sorted(word_freq.items(), key=lambda x: -x[1])[:top_n]]
    
    def _analyze_structure(self, text: str) -> str:
        """分析文档结构"""
        lines = text.split('\n')
        
        # 统计各类标题
        h1_count = len(re.findall(r'^#\s', text, re.MULTILINE))
        h2_count = len(re.findall(r'^##\s', text, re.MULTILINE))
        h3_count = len(re.findall(r'^###\s', text, re.MULTILINE))
        
        # 数字列表
        numbered_items = len(re.findall(r'^\d+[.、)]', text, re.MULTILINE))
        
        # 估算段落数
        paragraph_count = len([p for p in text.split('\n\n') if p.strip()])
        
        structure_parts = []
        
        if h1_count > 0:
            structure_parts.append(f"{h1_count}个一级章节")
        if h2_count > 0:
            structure_parts.append(f"{h2_count}个二级章节")
        if numbered_items > 0:
            structure_parts.append(f"{numbered_items}个编号项")
        if paragraph_count > 0:
            structure_parts.append(f"{paragraph_count}个段落")
        
        if structure_parts:
            return "，".join(structure_parts)
        return f"{paragraph_count}个段落"
    
    def _identify_doc_type(self, text: str) -> str:
        """识别文档类型"""
        # 技术文档特征
        tech_keywords = ['函数', '方法', '类', '接口', 'API', '代码', '实现', '模块']
        if sum(1 for k in tech_keywords if k in text) >= 3:
            return "技术文档"
        
        # 报告特征
        report_keywords = ['分析', '报告', '数据', '统计', '结果', '结论']
        if sum(1 for k in report_keywords if k in text) >= 3:
            return "分析报告"
        
        # 教程特征
        tutorial_keywords = ['教程', '步骤', '首先', '然后', '最后', '如何', '怎么']
        if sum(1 for k in tutorial_keywords if k in text) >= 3:
            return "教程指南"
        
        # 论文特征
        paper_keywords = ['研究', '方法论', '实验', '结论', '摘要', '引用']
        if sum(1 for k in paper_keywords if k in text) >= 3:
            return "研究论文"
        
        return "通用文档"
    
    def _generate_core_summary(
        self, 
        text: str, 
        task: str,
        structure: str
    ) -> str:
        """生成核心摘要（<100字）"""
        # 提取首段和尾段
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        if not paragraphs:
            return "无法生成摘要"
        
        # 首段通常包含核心内容
        first_para = paragraphs[0]
        last_para = paragraphs[-1] if len(paragraphs) > 1 else ""
        
        # 提取关键句
        sentences = re.split(r'[。！？.!?]', first_para)
        key_sentences = [s.strip() for s in sentences if len(s) > 10][:3]
        
        # 组合摘要
        summary_parts = []
        
        # 结构信息
        summary_parts.append(f"[{structure}]")
        
        # 核心内容
        if key_sentences:
            # 选取最长的句子
            main_sentence = max(key_sentences, key=len)
            # 截断到合理长度
            if len(main_sentence) > 60:
                main_sentence = main_sentence[:57] + "..."
            summary_parts.append(main_sentence)
        
        return " ".join(summary_parts)
    
    def _extract_key_points(self, text: str, structure: str) -> List[str]:
        """提取关键观点"""
        points = []
        
        # 提取标题作为观点
        titles = re.findall(r'^(#{1,3})\s+(.+)$', text, re.MULTILINE)
        for hash_level, title in titles[:5]:
            if title.strip():
                points.append(title.strip())
        
        # 如果标题不够，提取每段首句
        if len(points) < 3:
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            for para in paragraphs:
                # 取首句
                first_sentence = re.split(r'[。！？.!?]', para)[0].strip()
                if first_sentence and len(first_sentence) > 5:
                    points.append(first_sentence)
                if len(points) >= 5:
                    break
        
        return points[:5]
    
    # =========================================================================
    # Layer 2: 分块深度分析
    # =========================================================================
    
    def _layer2_deep_analysis(
        self,
        chunks: List[Chunk],
        task: str,
        layer1_summary: Layer1Summary,
    ) -> List[Layer2ChunkAnalysis]:
        """
        Layer 2: 对每个分块进行深度分析
        
        使用并行处理加速，同时复用 MultiTurnAnalyzer。
        """
        results = []
        
        # 根据 chunk 数量决定是否并行
        if len(chunks) <= 3:
            # 小数量：串行处理，保持顺序
            for chunk in chunks:
                result = self._analyze_single_chunk(chunk, task, layer1_summary)
                results.append(result)
                self._report_progress(
                    f"分析分块 {len(results)}/{len(chunks)}", 
                    0.2 + 0.3 * (len(results) / len(chunks))
                )
        else:
            # 大数量：并行处理
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(
                        self._analyze_single_chunk, 
                        chunk, task, layer1_summary
                    ): i 
                    for i, chunk in enumerate(chunks)
                }
                
                # 按顺序收集结果
                results = [None] * len(chunks)
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        results[idx] = future.result(timeout=60)
                    except Exception as e:
                        logger.error(f"分块 {idx} 分析失败: {e}")
                        from .chunk_analyzer import ChunkAnalysis
                        from .adaptive_compressor import SegmentType
                        results[idx] = Layer2ChunkAnalysis(
                            chunk_index=idx,
                            chunk=chunks[idx],
                            analysis=ChunkAnalysis(
                                chunk_id=idx,
                                content_type=SegmentType.GENERAL,
                                key_points=[f"分析失败: {str(e)}"],
                            ),
                        )
                    
                    self._report_progress(
                        f"分析分块 {idx + 1}/{len(chunks)}",
                        0.2 + 0.3 * ((idx + 1) / len(chunks))
                    )
        
        return results
    
    def _analyze_single_chunk(
        self,
        chunk: Chunk,
        task: str,
        layer1_summary: Layer1Summary,
    ) -> Layer2ChunkAnalysis:
        """分析单个分块"""
        # 基础分析
        analysis = self.chunk_analyzer.analyze_chunk(chunk)
        
        # 多轮探索（使用现有的 MultiTurnAnalyzer）
        exploration_results = []
        try:
            # 生成针对此分块的探索问题
            exploration_questions = self._generate_exploration_questions(
                chunk, task, layer1_summary
            )
            
            for question in exploration_questions[:self.max_turns_per_chunk]:
                # 执行探索
                exploration = self._explore_chunk(chunk, question)
                if exploration:
                    exploration_results.append(exploration)
        except Exception as e:
            logger.warning(f"探索失败: {e}")
        
        # 计算与任务的关联度
        relevance = self._calculate_relevance(chunk, task, layer1_summary)
        
        return Layer2ChunkAnalysis(
            chunk_index=chunk.index,
            chunk=chunk,
            analysis=analysis,
            exploration_results=exploration_results,
            follow_up_questions=self._generate_follow_up_questions(chunk, analysis),
            insights=self._extract_insights(analysis, exploration_results),
            relevance_to_task=relevance,
        )
    
    def _generate_exploration_questions(
        self,
        chunk: Chunk,
        task: str,
        layer1_summary: Layer1Summary,
    ) -> List[str]:
        """生成探索问题"""
        questions = []
        
        # 基于 chunk 类型生成问题
        if chunk.chunk_type == ChunkType.TOPIC:
            questions.append(f"这段关于\"{chunk.summary or '主题'}\"的内容如何支撑整体分析？")
        
        # 基于关键词生成问题
        if chunk.keywords:
            for kw in chunk.keywords[:2]:
                questions.append(f"\"{kw}\"在本分块中的具体含义是什么？")
        
        # 基于任务生成问题
        if "总结" in task:
            questions.append("这段的核心观点是什么？")
        elif "分析" in task:
            questions.append("这段支持或反驳了什么观点？")
        elif "对比" in task:
            questions.append("这段与其他部分有什么异同？")
        
        # 默认问题
        if not questions:
            questions = [
                "这段的主要内容是什么？",
                "有什么值得特别关注的细节？",
            ]
        
        return questions[:self.max_turns_per_chunk]
    
    def _explore_chunk(
        self,
        chunk: Chunk,
        question: str,
    ) -> Optional[Dict[str, Any]]:
        """探索单个分块"""
        try:
            # 简单基于规则的探索（未来可替换为 LLM）
            # 提取相关句子
            sentences = chunk.content.split('。')
            relevant_sentences = [
                s.strip() for s in sentences 
                if len(s.strip()) > 10
            ]
            
            if relevant_sentences:
                return {
                    "question": question,
                    "answer": relevant_sentences[0],
                    "insight": f"发现关键信息: {relevant_sentences[0][:50]}...",
                    "source_chunk": chunk.index,
                }
        except Exception as e:
            logger.warning(f"探索失败: {e}")
        
        return None
    
    def _calculate_relevance(
        self,
        chunk: Chunk,
        task: str,
        layer1_summary: Layer1Summary,
    ) -> float:
        """计算分块与任务的关联度"""
        relevance = 0.5
        
        # 基于重要性
        relevance += (chunk.importance - 0.5) * 0.3
        
        # 基于关键词匹配
        task_keywords = set(task.lower().split())
        chunk_keywords = set(kw.lower() for kw in chunk.keywords)
        if task_keywords & chunk_keywords:
            relevance += 0.2
        
        # 基于层1摘要的关键词
        layer1_keywords = set(layer1_summary.key_points)
        if task_keywords & layer1_keywords:
            relevance += 0.1
        
        return max(0.0, min(1.0, relevance))
    
    def _generate_follow_up_questions(
        self,
        chunk: Chunk,
        analysis: AnalysisResult,
    ) -> List[str]:
        """生成追问问题"""
        questions = []
        
        # 基于实体生成问题
        for entity in analysis.entities[:2]:
            questions.append(f"\"{entity.text}\"与整体分析有什么关系？")
        
        # 基于关键点生成问题
        for point in analysis.key_points[:2]:
            if len(point) > 10:
                questions.append(f"\"{point[:30]}...\"的具体含义是什么？")
        
        return questions[:3]
    
    def _extract_insights(
        self,
        analysis: AnalysisResult,
        exploration_results: List[Dict[str, Any]],
    ) -> List[str]:
        """提取洞察"""
        insights = []
        
        # 从分析结果提取
        insights.extend(analysis.key_points[:3])
        
        # 从探索结果提取
        for result in exploration_results:
            if "insight" in result:
                insights.append(result["insight"])
        
        return insights[:5]
    
    # =========================================================================
    # Layer 3: 关系网络
    # =========================================================================
    
    def _layer3_relation_network(
        self,
        layer2_results: List[Layer2ChunkAnalysis],
    ) -> Layer3RelationNetwork:
        """
        Layer 3: 构建分块间的关系网络
        
        识别关系类型：
        - 因果关系
        - 对比关系
        - 补充关系
        - 引用关系
        """
        relations = []
        clusters = []
        
        if len(layer2_results) < 2:
            return Layer3RelationNetwork(
                relations=[],
                relation_stats={},
                key_connections=[],
                clusters=list(range(len(layer2_results))),
            )
        
        # 构建关系
        for i in range(len(layer2_results)):
            for j in range(i + 1, len(layer2_results)):
                relation = self._detect_relation(
                    layer2_results[i],
                    layer2_results[j],
                )
                if relation:
                    relations.append(relation)
        
        # 统计关系类型
        relation_stats = defaultdict(int)
        for rel in relations:
            relation_stats[rel.relation_type.value] += 1
        
        # 识别关键连接
        key_connections = [
            (r.from_chunk, r.to_chunk) 
            for r in relations if r.is_strong
        ]
        
        # 聚类分析（基于关系强度）
        clusters = self._cluster_chunks(relations, len(layer2_results))
        
        # 识别潜在关系
        potential_relations = self._find_potential_relations(
            layer2_results, relations
        )
        
        return Layer3RelationNetwork(
            relations=relations,
            relation_stats=dict(relation_stats),
            key_connections=key_connections,
            clusters=clusters,
            potential_relations=potential_relations,
        )
    
    def _detect_relation(
        self,
        chunk_a: Layer2ChunkAnalysis,
        chunk_b: Layer2ChunkAnalysis,
    ) -> Optional[ChunkRelation]:
        """检测两个分块间的关系"""
        content_a = chunk_a.chunk.content.lower()
        content_b = chunk_b.chunk.content.lower()
        
        # 检查因果关系关键词
        causal_keywords_a = ['因此', '所以', '导致', '造成', 'result', 'therefore', 'thus']
        causal_keywords_b = ['因为', '由于', '为了', '由于', 'because', 'since']
        
        has_cause = any(k in content_a for k in causal_keywords_a + causal_keywords_b)
        
        # 检查对比关系关键词
        contrast_keywords = ['但是', '然而', '相比', '不同', 'however', 'but', 'unlike', 'whereas']
        has_contrast = any(k in content_a or k in content_b for k in contrast_keywords)
        
        # 检查补充关系关键词
        supplement_keywords = ['此外', '另外', '并且', '还有', 'furthermore', 'additionally']
        has_supplement = any(k in content_a or k in content_b for k in supplement_keywords)
        
        # 检查引用关系（关键词重复）
        common_keywords = set(chunk_a.chunk.keywords) & set(chunk_b.chunk.keywords)
        has_reference = len(common_keywords) >= 2
        
        # 计算关系强度
        strength = 0.0
        relation_type = None
        
        if has_cause:
            strength = 0.7
            relation_type = RelationType.CAUSAL
        elif has_contrast:
            strength = 0.6
            relation_type = RelationType.CONTRAST
        elif has_supplement:
            strength = 0.5
            relation_type = RelationType.SUPPLEMENT
        elif has_reference:
            strength = 0.4 + len(common_keywords) * 0.1
            relation_type = RelationType.REFERENCE
        
        # 顺序关系（默认）
        if relation_type is None and abs(chunk_a.chunk_index - chunk_b.chunk_index) == 1:
            strength = 0.3
            relation_type = RelationType.SEQUENCE
        
        if relation_type and strength >= self.min_relation_strength:
            return ChunkRelation(
                from_chunk=chunk_a.chunk_index,
                to_chunk=chunk_b.chunk_index,
                relation_type=relation_type,
                description=f"{relation_type.value}关系",
                strength=min(strength, 1.0),
            )
        
        return None
    
    def _cluster_chunks(
        self,
        relations: List[ChunkRelation],
        total_chunks: int,
    ) -> List[List[int]]:
        """聚类分析：将相关的分块分组"""
        if not relations:
            return [[i] for i in range(total_chunks)]
        
        # 构建邻接表
        adjacency = defaultdict(set)
        for rel in relations:
            if rel.is_strong:
                adjacency[rel.from_chunk].add(rel.to_chunk)
                adjacency[rel.to_chunk].add(rel.from_chunk)
        
        # BFS 聚类
        visited = set()
        clusters = []
        
        for start in range(total_chunks):
            if start in visited:
                continue
            
            cluster = []
            queue = [start]
            
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                
                visited.add(node)
                cluster.append(node)
                
                for neighbor in adjacency[node]:
                    if neighbor not in visited:
                        queue.append(neighbor)
            
            if cluster:
                clusters.append(sorted(cluster))
        
        return clusters
    
    def _find_potential_relations(
        self,
        layer2_results: List[Layer2ChunkAnalysis],
        existing_relations: List[ChunkRelation],
    ) -> List[Dict[str, Any]]:
        """发现潜在关系"""
        potential = []
        
        # 检查同一簇但未直接连接的分块
        existing_pairs = {(r.from_chunk, r.to_chunk) for r in existing_relations}
        existing_pairs.update((r.to_chunk, r.from_chunk) for r in existing_relations)
        
        # 构建邻接表
        adjacency = defaultdict(set)
        for rel in existing_relations:
            if rel.is_strong:
                adjacency[rel.from_chunk].add(rel.to_chunk)
                adjacency[rel.to_chunk].add(rel.from_chunk)
        
        for i, chunk_a in enumerate(layer2_results):
            for j, chunk_b in enumerate(layer2_results):
                if i >= j:
                    continue
                
                if (i, j) not in existing_pairs:
                    # 检查是否有间接关系
                    neighbors_i = adjacency.get(i, set())
                    neighbors_j = adjacency.get(j, set())
                    common_neighbors = neighbors_i & neighbors_j
                    if common_neighbors:
                        potential.append({
                            "chunk_a": i,
                            "chunk_b": j,
                            "reason": f"都与{len(common_neighbors)}个分块相关",
                            "confidence": 0.3,
                        })
        
        return potential[:5]  # 最多返回5个
    
    # =========================================================================
    # Layer 4: 综合分析
    # =========================================================================
    
    def _layer4_synthesis(
        self,
        text: str,
        task: str,
        result: Optional[LayeredAnalysisResult],
    ) -> Layer4Synthesis:
        """
        Layer 4: 综合分析
        
        基于前三层结果生成最终分析报告。
        """
        start_time = time.time()
        
        # 收集所有层的关键信息
        structured_summary = {
            "task": task,
            "document_type": result.layer1_summary.doc_type if result and result.layer1_summary else "",
            "structure": result.layer1_summary.structure if result and result.layer1_summary else "",
            "total_chunks": result.total_chunks if result else 0,
        }
        
        # 生成结论
        conclusions = []
        if result and result.layer2_analyses:
            # 从各分块提取结论
            for chunk_analysis in result.layer2_analyses:
                # 选取关键发现
                for finding in chunk_analysis.key_findings[:2]:
                    if finding and len(finding) > 10:
                        conclusions.append(finding)
        
        # 去重
        seen = set()
        unique_conclusions = []
        for c in conclusions:
            # 简单去重
            normalized = c[:50].lower()
            if normalized not in seen:
                seen.add(normalized)
                unique_conclusions.append(c)
        
        # 生成建议
        recommendations = self._generate_recommendations(
            result, unique_conclusions
        )
        
        # 构建简化知识图谱
        knowledge_graph = self._build_knowledge_graph(result)
        
        # 生成最终报告
        report = self._generate_final_report(
            task, 
            result, 
            unique_conclusions,
            recommendations,
        )
        
        processing_time = time.time() - start_time
        
        return Layer4Synthesis(
            report=report,
            structured_summary=structured_summary,
            conclusions=unique_conclusions[:10],  # 最多10个结论
            recommendations=recommendations,
            knowledge_graph=knowledge_graph,
            confidence=0.85 if result else 0.5,
            processing_time=processing_time,
        )
    
    def _generate_recommendations(
        self,
        result: Optional[LayeredAnalysisResult],
        conclusions: List[str],
    ) -> List[str]:
        """生成建议"""
        recommendations = []
        
        # 基于文档类型生成建议
        if result and result.layer1_summary:
            doc_type = result.layer1_summary.doc_type
            
            if doc_type == "技术文档":
                recommendations.append("建议深入理解核心概念后进行实践验证")
            elif doc_type == "分析报告":
                recommendations.append("建议核实数据来源和时效性")
            elif doc_type == "教程指南":
                recommendations.append("建议按步骤实践并记录遇到的问题")
            elif doc_type == "研究论文":
                recommendations.append("建议查阅最新相关研究进行对比")
        
        # 基于结论数量生成建议
        if len(conclusions) > 5:
            recommendations.append("内容较为复杂，建议分多次深入阅读")
        elif len(conclusions) > 3:
            recommendations.append("内容核心观点清晰，可作为快速参考")
        
        if not recommendations:
            recommendations.append("建议根据具体需求选择相关部分深入阅读")
        
        return recommendations
    
    def _build_knowledge_graph(
        self,
        result: Optional[LayeredAnalysisResult],
    ) -> Dict[str, Any]:
        """构建简化知识图谱"""
        graph = {
            "nodes": [],
            "edges": [],
        }
        
        if not result or not result.layer2_analyses:
            return graph
        
        # 添加节点（实体）
        entity_ids = {}
        for chunk_analysis in result.layer2_analyses:
            for entity in chunk_analysis.analysis.entities[:3]:
                entity_text = getattr(entity, 'text', str(entity))
                if entity_text not in entity_ids:
                    node_id = len(graph["nodes"])
                    entity_ids[entity_text] = node_id
                    graph["nodes"].append({
                        "id": node_id,
                        "label": entity_text,
                        "type": entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type),
                    })
        
        # 添加边（关系）
        if result.layer3_network:
            for rel in result.layer3_network.relations[:10]:  # 最多10条边
                graph["edges"].append({
                    "from": rel.from_chunk,
                    "to": rel.to_chunk,
                    "label": rel.relation_type.value,
                    "strength": rel.strength,
                })
        
        return graph
    
    def _generate_final_report(
        self,
        task: str,
        result: Optional[LayeredAnalysisResult],
        conclusions: List[str],
        recommendations: List[str],
    ) -> str:
        """生成最终分析报告"""
        lines = []
        
        # 标题
        lines.append("=" * 60)
        lines.append(f"分析报告: {task}")
        lines.append("=" * 60)
        lines.append("")
        
        # 概述
        if result and result.layer1_summary:
            lines.append("【概述】")
            lines.append(f"文档类型: {result.layer1_summary.doc_type}")
            lines.append(f"结构: {result.layer1_summary.structure}")
            lines.append(f"核心摘要: {result.layer1_summary.core_summary}")
            lines.append("")
        
        # 核心发现
        if conclusions:
            lines.append("【核心发现】")
            for i, conclusion in enumerate(conclusions[:5], 1):
                lines.append(f"{i}. {conclusion}")
            lines.append("")
        
        # 分块分析摘要
        if result and result.layer2_analyses:
            lines.append(f"【分块分析】共分析 {len(result.layer2_analyses)} 个分块")
            
            # 按重要性排序
            sorted_chunks = sorted(
                result.layer2_analyses,
                key=lambda x: x.relevance_to_task,
                reverse=True,
            )
            
            for chunk in sorted_chunks[:3]:  # 显示前3个最相关的
                lines.append(f"\n  分块 {chunk.chunk_index + 1} (相关度: {chunk.relevance_to_task:.0%})")
                for insight in chunk.insights[:2]:
                    lines.append(f"    • {insight[:60]}{'...' if len(insight) > 60 else ''}")
            lines.append("")
        
        # 关系网络摘要
        if result and result.layer3_network:
            lines.append("【关系网络】")
            stats = result.layer3_network.relation_stats
            for rel_type, count in stats.items():
                lines.append(f"  • {rel_type}: {count}个")
            
            if result.layer3_network.clusters:
                lines.append(f"  • 发现 {len(result.layer3_network.clusters)} 个聚类")
            lines.append("")
        
        # 建议
        if recommendations:
            lines.append("【建议】")
            for i, rec in enumerate(recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")
        
        # 结尾
        lines.append("=" * 60)
        if result:
            lines.append(f"分析完成，耗时 {result.processing_time:.2f} 秒")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    # =========================================================================
    # 辅助方法
    # =========================================================================
    
    def _report_progress(self, message: str, progress: float):
        """报告进度"""
        if self.progress_callback:
            self.progress_callback(message, progress)
    
    def _update_stats(self, result: LayeredAnalysisResult):
        """更新统计信息"""
        self.stats["total_analyzes"] += 1
        self.stats["total_chunks_processed"] += result.total_chunks
        self.stats["total_time"] += result.processing_time
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        if stats["total_analyzes"] > 0:
            stats["avg_chunks_per_analysis"] = (
                stats["total_chunks_processed"] / stats["total_analyzes"]
            )
            stats["avg_time_per_analysis"] = (
                stats["total_time"] / stats["total_analyzes"]
            )
        return stats
    
    def reset_stats(self):
        """重置统计"""
        self.stats = {
            "total_analyzes": 0,
            "total_chunks_processed": 0,
            "total_time": 0.0,
        }


# ============================================================================
# 便捷函数
# ============================================================================

def analyze_layered(
    text: str,
    task: str = "总结要点",
    depth: str = "standard",
) -> LayeredAnalysisResult:
    """
    便捷函数：执行分层分析
    
    Args:
        text: 待分析文本
        task: 分析任务
        depth: 分析深度 (quick/standard/deep/comprehensive)
        
    Returns:
        LayeredAnalysisResult
    """
    depth_map = {
        "quick": AnalysisDepth.QUICK,
        "standard": AnalysisDepth.STANDARD,
        "deep": AnalysisDepth.DEEP,
        "comprehensive": AnalysisDepth.COMPREHENSIVE,
    }
    
    analyzer = LayeredHybridAnalyzer(
        default_depth=depth_map.get(depth, AnalysisDepth.STANDARD)
    )
    
    return analyzer.analyze(text, task)


# 导出
__all__ = [
    # 类
    "LayeredHybridAnalyzer",
    # 枚举
    "AnalysisDepth",
    "RelationType",
    # 数据类
    "ChunkRelation",
    "Layer1Summary",
    "Layer2ChunkAnalysis",
    "Layer3RelationNetwork",
    "Layer4Synthesis",
    "LayeredAnalysisResult",
    # 函数
    "analyze_layered",
]
