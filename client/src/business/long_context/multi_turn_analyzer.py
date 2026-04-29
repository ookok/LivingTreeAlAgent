# -*- coding: utf-8 -*-
"""
多轮对话分析器 - Multi-Turn Analyzer
====================================

基于分块的多轮对话分析，支持深度探索和追问。

核心能力：
1. 针对每个分块的深度分析
2. 分块间关系追踪
3. 多轮追问与回答
4. 结果综合

Author: Hermes Desktop Team
Date: 2026-04-24
from __future__ import annotations
"""


import re
import logging
import time
from typing import List, Dict, Any, Optional, Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

from .semantic_chunker import Chunk, ChunkType
from .chunk_analyzer import ChunkAnalyzer, ChunkAnalysis, AnalysisResult


class TurnStatus(Enum):
    """轮次状态"""
    PENDING = "pending"     # 待处理
    IN_PROGRESS = "active" # 进行中
    COMPLETED = "done"     # 已完成
    FAILED = "failed"      # 失败


@dataclass
class Turn:
    """对话轮次"""
    turn_id: int
    chunk_id: int
    question: str
    answer: str = ""
    status: TurnStatus = TurnStatus.PENDING
    confidence: float = 0.0
    follow_ups: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    
    @property
    def is_complete(self) -> bool:
        return self.status == TurnStatus.COMPLETED


@dataclass
class ExplorationPath:
    """
    探索路径
    
    Attributes:
        path_id: 路径ID
        chunks: 探索的分块序列
        turns: 对话轮次
        insights: 洞察
        final_conclusion: 最终结论
    """
    path_id: str
    chunks: List[int] = field(default_factory=list)
    turns: List[Turn] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    final_conclusion: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float = 0
    
    @property
    def duration(self) -> float:
        if self.end_time > 0:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    @property
    def depth(self) -> int:
        return len(self.turns)


@dataclass
class TurnResult:
    """
    多轮分析结果
    
    Attributes:
        original_text: 原始文本
        chunks: 分块列表
        analysis: 分块分析
        exploration_paths: 探索路径
        synthesized_result: 综合结果
        total_turns: 总轮次
        duration: 总耗时
    """
    original_text: str
    chunks: List[Chunk] = field(default_factory=list)
    analysis: Optional[AnalysisResult] = None
    exploration_paths: List[ExplorationPath] = field(default_factory=list)
    synthesized_result: str = ""
    total_turns: int = 0
    duration_seconds: float = 0
    
    @property
    def all_insights(self) -> List[str]:
        """所有洞察"""
        insights = []
        for path in self.exploration_paths:
            insights.extend(path.insights)
        if self.analysis:
            insights.extend(self.analysis.insights)
        return list(set(insights))
    
    @property
    def all_questions(self) -> List[str]:
        """所有问题"""
        questions = []
        for path in self.exploration_paths:
            for turn in path.turns:
                questions.append(turn.question)
                questions.extend(turn.follow_ups)
        if self.analysis:
            questions.extend(self.analysis.recommended_questions)
        return list(set(questions))


class MultiTurnAnalyzer:
    """
    多轮对话分析器
    
    支持对长文本进行分块分析，每块进行多轮深度探索。
    """
    
    def __init__(
        self,
        chunker: Optional[Any] = None,
        analyzer: Optional[ChunkAnalyzer] = None,
        llm_client: Optional[Any] = None,
        max_turns_per_chunk: int = 3,
        enable_synthesis: bool = True,
    ):
        """
        初始化分析器
        
        Args:
            chunker: 分块器
            analyzer: 分块分析器
            llm_client: LLM客户端
            max_turns_per_chunk: 每块最大轮次
            enable_synthesis: 是否启用综合
        """
        self.chunker = chunker
        self.analyzer = analyzer or ChunkAnalyzer()
        self.llm_client = llm_client
        self.max_turns_per_chunk = max_turns_per_chunk
        self.enable_synthesis = enable_synthesis
        
        # 初始化默认分块器
        if self.chunker is None:
            from .semantic_chunker import SemanticChunker
            self.chunker = SemanticChunker(
                chunk_size=1000,
                overlap=100,
            )
    
    def analyze(
        self,
        text: str,
        task: Optional[str] = None,
        strategy: str = "auto",
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> TurnResult:
        """
        多轮分析主入口
        
        Args:
            text: 原始文本
            task: 任务描述
            strategy: 分块策略
            progress_callback: 进度回调 (message, progress)
        
        Returns:
            TurnResult: 分析结果
        """
        start_time = time.time()
        
        result = TurnResult(original_text=text)
        
        # 步骤1: 分块
        if progress_callback:
            progress_callback("正在分块...", 0.1)
        
        chunks = self.chunker.chunk(text, strategy=strategy, task=task)
        result.chunks = chunks
        
        if not chunks:
            result.synthesized_result = "文本过短，无需分析。"
            return result
        
        # 步骤2: 分块分析
        if progress_callback:
            progress_callback(f"分析 {len(chunks)} 个分块...", 0.3)
        
        result.analysis = self.analyzer.analyze_chunks(chunks)
        
        # 步骤3: 多轮探索
        if progress_callback:
            progress_callback("深度探索中...", 0.6)
        
        exploration_paths = self._explore_chunks(
            chunks,
            result.analysis,
            task,
            progress_callback
        )
        result.exploration_paths = exploration_paths
        
        # 统计
        result.total_turns = sum(len(p.turns) for p in exploration_paths)
        
        # 步骤4: 综合结果
        if progress_callback:
            progress_callback("综合结果...", 0.9)
        
        if self.enable_synthesis:
            result.synthesized_result = self._synthesize(
                result.analysis,
                exploration_paths,
                task
            )
        
        result.duration_seconds = time.time() - start_time
        
        if progress_callback:
            progress_callback("完成", 1.0)
        
        return result
    
    def analyze_stream(
        self,
        text: str,
        task: Optional[str] = None,
        strategy: str = "auto",
    ) -> Iterator[Dict[str, Any]]:
        """
        流式分析
        
        Yields:
            Dict: 进度事件
        """
        start_time = time.time()
        
        # 分块
        yield {
            "event": "chunk_start",
            "message": "开始分块",
        }
        
        chunks = self.chunker.chunk(text, strategy=strategy, task=task)
        
        yield {
            "event": "chunk_done",
            "chunks": len(chunks),
            "message": f"分块完成，共 {len(chunks)} 个分块",
        }
        
        # 分析
        yield {"event": "analyze_start"}
        
        analysis = self.analyzer.analyze_chunks(chunks)
        
        yield {
            "event": "analyze_done",
            "entities": len(analysis.global_entities),
            "relations": len(analysis.global_relations),
        }
        
        # 多轮探索
        for i, chunk in enumerate(chunks):
            yield {
                "event": "explore_start",
                "chunk_id": i,
                "chunk_preview": chunk.content[:50],
            }
            
            # 模拟多轮
            for turn_id in range(self.max_turns_per_chunk):
                question = self._generate_question(chunk, analysis.chunk_analyses[i])
                
                yield {
                    "event": "turn",
                    "chunk_id": i,
                    "turn_id": turn_id,
                    "question": question,
                }
                
                # 模拟回答
                answer = self._generate_answer(chunk, question)
                
                yield {
                    "event": "answer",
                    "chunk_id": i,
                    "turn_id": turn_id,
                    "answer": answer,
                }
            
            yield {
                "event": "explore_done",
                "chunk_id": i,
            }
        
        # 综合
        yield {"event": "synthesize_start"}
        
        synthesized = self._synthesize(analysis, [], task)
        
        yield {
            "event": "synthesize_done",
            "result": synthesized,
            "duration": time.time() - start_time,
        }
    
    def _explore_chunks(
        self,
        chunks: List[Chunk],
        analysis: AnalysisResult,
        task: Optional[str],
        progress_callback: Optional[Callable],
    ) -> List[ExplorationPath]:
        """探索分块"""
        paths = []
        
        # 对每个关键分块创建探索路径
        key_chunks = self._select_key_chunks(chunks, analysis)
        
        for path_id, chunk in enumerate(key_chunks):
            path = ExplorationPath(path_id=f"path_{path_id}")
            path.chunks.append(chunk.index)
            
            chunk_analysis = analysis.chunk_analyses[chunk.index]
            
            # 多轮探索
            for turn_id in range(self.max_turns_per_chunk):
                if progress_callback:
                    progress_callback(
                        f"探索块 {chunk.index} 轮次 {turn_id + 1}...",
                        0.6 + 0.3 * (path_id / len(key_chunks))
                    )
                
                turn = self._explore_turn(
                    chunk,
                    chunk_analysis,
                    task,
                    turn_id
                )
                
                path.turns.append(turn)
                
                # 提取洞察
                if turn.answer:
                    insights = self._extract_insights(turn.answer)
                    path.insights.extend(insights)
            
            # 生成路径结论
            path.final_conclusion = self._synthesize_path(path)
            path.end_time = time.time()
            
            paths.append(path)
        
        return paths
    
    def _explore_turn(
        self,
        chunk: Chunk,
        chunk_analysis: ChunkAnalysis,
        task: Optional[str],
        turn_id: int,
    ) -> Turn:
        """探索单个轮次"""
        turn = Turn(
            turn_id=turn_id,
            chunk_id=chunk.index,
            question="",  # 后面设置
        )
        
        # 生成问题
        if turn_id == 0:
            # 第一轮：基于内容类型的问题
            turn.question = self._generate_initial_question(chunk, chunk_analysis, task)
        else:
            # 后续轮次：基于前一轮答案
            turn.question = self._generate_follow_up_question(chunk, chunk_analysis)
        
        # 生成答案
        turn.answer = self._generate_answer(chunk, turn.question)
        
        # 生成追问
        turn.follow_ups = self._generate_follow_ups(chunk, turn.answer)
        
        # 评估置信度
        turn.confidence = self._evaluate_confidence(turn.answer)
        
        # 提取洞察
        turn.insights = self._extract_insights(turn.answer)
        
        turn.status = TurnStatus.COMPLETED
        
        return turn
    
    def _generate_initial_question(
        self,
        chunk: Chunk,
        analysis: ChunkAnalysis,
        task: Optional[str]
    ) -> str:
        """生成初始问题"""
        # 基于任务
        if task:
            if '总结' in task or '摘要' in task:
                return f"请总结这段内容的主要观点。"
            if '分析' in task:
                return f"请深入分析这段内容的关键要素。"
        
        # 基于内容类型
        from .adaptive_compressor import SegmentType
        
        if analysis.content_type == SegmentType.DEFINITION:
            return f"这段内容中'{chunk.keywords[0] if chunk.keywords else '概念'}'的定义是什么？有什么需要注意的？"
        
        elif analysis.content_type == SegmentType.EXAMPLE:
            return f"这个例子说明了什么原理或概念？"
        
        elif analysis.content_type == SegmentType.CODE:
            return f"这段代码的功能是什么？输入输出是什么？"
        
        elif analysis.content_type == SegmentType.DATA:
            return f"这些数据的关键指标是什么？有什么趋势或规律？"
        
        elif analysis.content_type == SegmentType.CONCLUSION:
            return f"这个结论的依据是什么？适用范围是什么？"
        
        else:
            return f"这段内容的主要信息是什么？哪些是关键点？"
    
    def _generate_follow_up_question(
        self,
        chunk: Chunk,
        analysis: ChunkAnalysis
    ) -> str:
        """生成追问"""
        # 基于实体
        if analysis.entities:
            entity = analysis.entities[0]
            if entity.entity_type.value in ['person', 'org', 'tech']:
                return f"关于'{entity.text}'，还有什么需要了解的？"
        
        # 基于关键词
        if chunk.keywords:
            return f"'{chunk.keywords[0]}'在实际应用中有哪些场景？"
        
        # 基于关系
        if analysis.relations:
            rel = analysis.relations[0]
            return f"'{rel.source}'和'{rel.target}'之间的关系是什么？"
        
        # 默认追问
        return f"这段内容还有什么值得深入了解的地方吗？"
    
    def _generate_answer(
        self,
        chunk: Chunk,
        question: str
    ) -> str:
        """生成回答"""
        # 如果有 LLM 客户端
        if self.llm_client:
            try:
                prompt = f"""基于以下内容回答问题。

问题：{question}

内容：
{chunk.content[:2000]}

请简洁、准确地回答。"""
                
                response = self.llm_client.chat(prompt)
                return response
            except Exception as e:
                logger.warning(f"LLM 生成回答失败: {e}")
        
        # 回退：基于内容的简单回答
        return self._generate_fallback_answer(chunk, question)
    
    def _generate_fallback_answer(
        self,
        chunk: Chunk,
        question: str
    ) -> str:
        """生成回退回答"""
        # 简单提取相关内容
        sentences = re.split(r'[。！？]', chunk.content)
        
        if '主要' in question or '关键' in question or '总结' in question:
            return sentences[0] + '。' if sentences else chunk.content[:200]
        
        if '定义' in question or '是什么' in question:
            for sent in sentences:
                if any(kw in sent for kw in ['是', '指', '代表']):
                    return sent + '。'
        
        if '例子' in question or '说明' in question:
            for sent in sentences:
                if '例如' in sent or '比如' in sent:
                    return sent + '。'
        
        return sentences[0] + '。' if sentences else chunk.content[:200]
    
    def _generate_follow_ups(
        self,
        chunk: Chunk,
        answer: str
    ) -> List[str]:
        """生成追问列表"""
        follow_ups = []
        
        # 基于回答内容
        if '但是' in answer or '然而' in answer:
            follow_ups.append("这个转折说明了什么？")
        
        if '因此' in answer or '所以' in answer:
            follow_ups.append("这个结论的前提条件是什么？")
        
        if '例如' in answer:
            follow_ups.append("还有其他类似的例子吗？")
        
        if '需要' in answer or '应该' in answer:
            follow_ups.append("具体应该怎么做？")
        
        if len(follow_ups) < 2:
            follow_ups.append("这个观点在实际中如何应用？")
            follow_ups.append("有什么局限性需要注意？")
        
        return follow_ups[:3]
    
    def _select_key_chunks(
        self,
        chunks: List[Chunk],
        analysis: AnalysisResult
    ) -> List[Chunk]:
        """选择关键分块"""
        # 选择重要度高、复杂度高的分块
        scored = []
        
        for i, chunk in enumerate(chunks):
            chunk_analysis = analysis.chunk_analyses[i]
            
            # 综合得分
            score = (
                chunk_analysis.quality * 0.4 +
                chunk_analysis.complexity * 0.3 +
                chunk.importance * 0.3
            )
            
            # 实体数量加成
            score += len(chunk_analysis.entities) * 0.05
            
            scored.append((chunk, score))
        
        # 排序并选择
        scored.sort(key=lambda x: -x[1])
        
        # 选择前 N 个
        max_chunks = min(5, len(chunks))
        return [chunk for chunk, _ in scored[:max_chunks]]
    
    def _evaluate_confidence(self, answer: str) -> float:
        """评估置信度"""
        score = 0.5
        
        # 长度适中
        if 50 < len(answer) < 500:
            score += 0.2
        
        # 有具体信息
        if any(c.isdigit() for c in answer):
            score += 0.1
        
        # 有定义或解释
        if any(kw in answer for kw in ['是', '指', '因为', '所以']):
            score += 0.1
        
        # 无明显不确定词
        uncertain_words = ['可能', '也许', '大概', '似乎', '不确定']
        if not any(w in answer for w in uncertain_words):
            score += 0.1
        
        return min(score, 1.0)
    
    def _extract_insights(self, text: str) -> List[str]:
        """提取洞察"""
        insights = []
        
        # 提取关键断言
        sentences = re.split(r'[。！？]', text)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 20:
                continue
            
            # 检查关键模式
            if any(kw in sent for kw in ['重要', '关键', '核心']):
                insights.append(sent)
            elif any(kw in sent for kw in ['然而', '但是', '不过']):
                insights.append(f"转折点: {sent[:50]}...")
            elif any(kw in sent for kw in ['因此', '所以', '结论']):
                insights.append(f"结论: {sent[:50]}...")
        
        return insights[:3]
    
    def _synthesize_path(self, path: ExplorationPath) -> str:
        """综合单条路径"""
        if not path.turns:
            return ""
        
        # 收集所有洞察
        insights = []
        for turn in path.turns:
            insights.extend(turn.insights)
        
        if not insights:
            return "探索完成，未发现明显洞察。"
        
        # 去重
        unique_insights = list(dict.fromkeys(insights))
        
        return " / ".join(unique_insights[:3])
    
    def _synthesize(
        self,
        analysis: AnalysisResult,
        paths: List[ExplorationPath],
        task: Optional[str]
    ) -> str:
        """综合所有结果"""
        parts = []
        
        # 整体摘要
        if analysis.overall_summary:
            parts.append(f"整体摘要：{analysis.overall_summary}")
        
        # 核心主题
        if analysis.key_themes:
            parts.append(f"核心主题：{', '.join(analysis.key_themes[:5])}")
        
        # 关键洞察
        all_insights = []
        for path in paths:
            all_insights.extend(path.insights)
        if analysis.insights:
            all_insights.extend(analysis.insights)
        
        if all_insights:
            unique = list(dict.fromkeys(all_insights))
            parts.append(f"关键洞察：{'; '.join(unique[:3])}")
        
        # 实体统计
        if analysis.global_entities:
            entity_types = {}
            for e in analysis.global_entities:
                t = e.entity_type.value
                entity_types[t] = entity_types.get(t, 0) + 1
            parts.append(f"识别实体：{len(analysis.global_entities)} 个（{entity_types}）")
        
        return "\n".join(parts) if parts else "分析完成"
