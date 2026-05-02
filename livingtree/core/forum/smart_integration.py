"""
去中心化论坛 - 智能写作集成
将智能写作系统赋能论坛讨论

功能:
- 自动生成讨论论点/论据
- 回帖增强 (中立总结/反驳建议)
- 讨论质量评估
- 自动摘要
"""

import time
import json
import logging
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from .models import ForumPost, ForumReply, SmartDraft, ReplySummary, Author

logger = logging.getLogger(__name__)


class DiscussionQuality(Enum):
    """讨论质量等级"""
    HIGH = "high"      # 高质量: 有论点、有论据、结构清晰
    MEDIUM = "medium" # 中等质量: 有观点、但论据不足
    LOW = "low"       # 低质量: 情绪化、无实质内容


@dataclass
class ArgumentPoint:
    """论点"""
    point: str              # 论点内容
    evidence: List[str]     # 支持证据
    counter_points: List[str] = field(default_factory=list)  # 反面论点
    confidence: float = 0.8  # 置信度


@dataclass
class DiscussionAnalysis:
    """讨论分析结果"""
    topic: str                    # 主题
    main_arguments: List[ArgumentPoint]  # 主要论点
    sentiment_score: float        # 情感得分 (-1 到 1)
    quality: DiscussionQuality    # 质量等级
    summary: str                  # 摘要
    suggestions: List[str] = field(default_factory=list)  # 改进建议
    key_questions: List[str] = field(default_factory=list)  # 关键问题


class SmartWritingIntegration:
    """
    智能写作集成

    集成现有的智能创作与专业审核增强系统 (core/creative_review_system/)
    为论坛讨论提供 AI 增强功能
    """

    def __init__(self):
        # AI 生成回调 (将由 ForumHub 设置)
        self._generate_callback: Optional[Callable] = None

        # 本地 LLM 回调 (用于简单分析)
        self._local_llm_callback: Optional[Callable] = None

        # 缓存
        self._analysis_cache: Dict[str, DiscussionAnalysis] = {}
        self._summary_cache: Dict[str, ReplySummary] = {}

    def set_generate_callback(self, callback: Callable):
        """设置生成回调 (系统大脑生成)"""
        self._generate_callback = callback

    def set_local_llm_callback(self, callback: Callable):
        """设置本地 LLM 回调"""
        self._local_llm_callback = callback

    async def generate_draft(self, topic: str, perspective: str = "balanced") -> SmartDraft:
        """
        为给定主题生成智能草稿

        Args:
            topic: 讨论主题
            perspective: 视角 (balanced/pro/against/neutral)
        """
        # 检查缓存
        cache_key = f"draft_{topic}_{perspective}"
        if cache_key in self._analysis_cache:
            cached = self._analysis_cache[cache_key]
            return SmartDraft(
                topic=topic,
                outline=[a.point for a in cached.main_arguments],
                arguments_for=[a.point for a in cached.main_arguments if a.confidence > 0.6],
                arguments_against=cached.main_arguments[-2:] if len(cached.main_arguments) > 2 else [],
                suggested_references=cached.key_questions
            )

        # 使用 AI 生成
        if self._generate_callback:
            try:
                prompt = self._build_draft_prompt(topic, perspective)
                result = await self._generate_callback(prompt)

                # 解析结果
                draft = self._parse_draft_result(topic, result)
                return draft
            except Exception as e:
                logger.error(f"Draft generation error: {e}")

        # 回退到本地分析
        return self._local_generate_draft(topic, perspective)

    def _build_draft_prompt(self, topic: str, perspective: str) -> str:
        """构建草稿生成提示"""
        return f"""请为以下讨论主题生成高质量的论点框架:

主题: {topic}
视角: {perspective}

请生成:
1. 大纲要点 (3-5个)
2. 支持论点 (2-3个, 带论据)
3. 反对论点 (1-2个, 带论据)
4. 建议参考资料 (2-3个关键词)

请用 JSON 格式返回:
{{
    "outline": ["要点1", "要点2", ...],
    "arguments_for": [{{"point": "论点", "evidence": ["证据1", "证据2"]}}],
    "arguments_against": [{{"point": "论点", "evidence": ["证据1"]}}],
    "references": ["参考1", "参考2"]
}}
"""

    def _parse_draft_result(self, topic: str, result: str) -> SmartDraft:
        """解析草稿生成结果"""
        try:
            # 尝试 JSON 解析
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]

            data = json.loads(result.strip())

            return SmartDraft(
                topic=topic,
                outline=data.get("outline", []),
                arguments_for=[a.get("point", "") for a in data.get("arguments_for", [])],
                arguments_against=[a.get("point", "") for a in data.get("arguments_against", [])],
                suggested_references=data.get("references", []),
                generated_at=time.time()
            )
        except Exception as e:
            logger.error(f"Parse draft error: {e}")
            return self._local_generate_draft(topic, "balanced")

    def _local_generate_draft(self, topic: str, perspective: str) -> SmartDraft:
        """本地生成草稿 (简单回退)"""
        return SmartDraft(
            topic=topic,
            outline=[
                f"主题: {topic}",
                "论点1: 正面角度分析",
                "论点2: 反面角度分析",
                "论点3: 中立综合视角"
            ],
            arguments_for=[
                f"支持 {topic} 的理由1",
                f"支持 {topic} 的理由2"
            ],
            arguments_against=[
                f"反对 {topic} 的理由1"
            ],
            suggested_references=["相关背景资料1", "相关背景资料2"],
            generated_at=time.time()
        )

    async def analyze_discussion(self, post: ForumPost, replies: List[ForumReply]) -> DiscussionAnalysis:
        """
        分析讨论质量

        Args:
            post: 主帖
            replies: 回复列表
        """
        cache_key = f"analysis_{post.post_id}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        # 合并所有文本
        all_text = post.content.text + "\n\n"
        for reply in replies:
            all_text += f"{reply.author.display_name}: {reply.content.text}\n\n"

        # 使用 AI 分析
        if self._generate_callback:
            try:
                prompt = self._build_analysis_prompt(post.title, all_text, len(replies))
                result = await self._generate_callback(prompt)
                analysis = self._parse_analysis_result(post.title, result)

                # 缓存
                self._analysis_cache[cache_key] = analysis
                return analysis
            except Exception as e:
                logger.error(f"Discussion analysis error: {e}")

        # 回退到本地分析
        analysis = self._local_analyze_discussion(post, replies)
        self._analysis_cache[cache_key] = analysis
        return analysis

    def _build_analysis_prompt(self, title: str, content: str, reply_count: int) -> str:
        """构建分析提示"""
        return f"""请分析以下讨论的质量和结构:

标题: {title}
回复数: {reply_count}

内容:
{content[:3000]}

请从以下维度分析:
1. 主要论点 (提取关键论点)
2. 情感倾向 (-1 到 1, 负数表示负面)
3. 讨论质量 (high/medium/low)
4. 摘要 (50字内)
5. 改进建议 (1-3条)
6. 关键问题 (1-3个待讨论的问题)

请用 JSON 格式返回:
{{
    "main_arguments": [{{"point": "论点", "evidence": ["证据"], "confidence": 0.8}}],
    "sentiment_score": 0.2,
    "quality": "medium",
    "summary": "摘要",
    "suggestions": ["建议1", "建议2"],
    "key_questions": ["问题1"]
}}
"""

    def _parse_analysis_result(self, topic: str, result: str) -> DiscussionAnalysis:
        """解析分析结果"""
        try:
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]

            data = json.loads(result.strip())

            arguments = []
            for arg in data.get("main_arguments", []):
                arguments.append(ArgumentPoint(
                    point=arg.get("point", ""),
                    evidence=arg.get("evidence", []),
                    confidence=arg.get("confidence", 0.5)
                ))

            return DiscussionAnalysis(
                topic=topic,
                main_arguments=arguments,
                sentiment_score=data.get("sentiment_score", 0.0),
                quality=DiscussionQuality(data.get("quality", "medium")),
                summary=data.get("summary", ""),
                suggestions=data.get("suggestions", []),
                key_questions=data.get("key_questions", [])
            )
        except Exception as e:
            logger.error(f"Parse analysis error: {e}")
            return DiscussionAnalysis(
                topic=topic,
                main_arguments=[],
                sentiment_score=0.0,
                quality=DiscussionQuality.MEDIUM,
                summary="分析失败"
            )

    def _local_analyze_discussion(self, post: ForumPost, replies: List[ForumReply]) -> DiscussionAnalysis:
        """本地分析讨论 (简单回退)"""
        # 简单统计
        total_chars = len(post.content.text)
        for reply in replies:
            total_chars += len(reply.content.text)

        avg_reply_length = total_chars / (len(replies) + 1) if replies else 0

        # 简单质量判断
        if avg_reply_length > 200 and len(replies) >= 3:
            quality = DiscussionQuality.HIGH
        elif avg_reply_length > 100:
            quality = DiscussionQuality.MEDIUM
        else:
            quality = DiscussionQuality.LOW

        return DiscussionAnalysis(
            topic=post.title,
            main_arguments=[
                ArgumentPoint(
                    point="主要观点",
                    evidence=["帖子内容分析"],
                    confidence=0.6
                )
            ],
            sentiment_score=0.1,
            quality=quality,
            summary=f"共 {len(replies)} 条回复, 平均长度 {avg_reply_length:.0f} 字",
            suggestions=["建议增加论据支持", "建议更深入分析"],
            key_questions=["还有其他角度吗?"]
        )

    async def generate_reply_summary(self, reply: ForumReply) -> ReplySummary:
        """
        为回复生成 AI 摘要/分析

        用于:
        - 长回复自动摘要
        - 情感分析
        - 反驳建议
        """
        cache_key = f"summary_{reply.reply_id}"
        if cache_key in self._summary_cache:
            return self._summary_cache[cache_key]

        if self._generate_callback:
            try:
                prompt = self._build_summary_prompt(reply)
                result = await self._generate_callback(prompt)
                summary = self._parse_summary_result(reply.reply_id, result)

                self._summary_cache[cache_key] = summary
                return summary
            except Exception as e:
                logger.error(f"Reply summary error: {e}")

        # 本地回退
        summary = ReplySummary(
            reply_id=reply.reply_id,
            summary=reply.content.text[:100] + "..." if len(reply.content.text) > 100 else reply.content.text,
            sentiment="neutral",
            key_points=[reply.content.text[:50]],
            generated_at=time.time()
        )
        self._summary_cache[cache_key] = summary
        return summary

    def _build_summary_prompt(self, reply: ForumReply) -> str:
        """构建摘要提示"""
        return f"""请分析以下回复:

作者: {reply.author.display_name}
内容: {reply.content.text}

请生成:
1. 摘要 (30字内)
2. 情感 (positive/neutral/negative)
3. 关键论点 (1-2个)
4. 建议反驳角度 (1-2个, 如果是负面/有争议的内容)

请用 JSON 格式返回:
{{
    "summary": "摘要",
    "sentiment": "neutral",
    "key_points": ["要点1"],
    "suggested_counter": ["反驳角度1"]
}}
"""

    def _parse_summary_result(self, reply_id: str, result: str) -> ReplySummary:
        """解析摘要结果"""
        try:
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]

            data = json.loads(result.strip())

            return ReplySummary(
                reply_id=reply_id,
                summary=data.get("summary", ""),
                sentiment=data.get("sentiment", "neutral"),
                key_points=data.get("key_points", []),
                suggested_counter=data.get("suggested_counter", []),
                generated_at=time.time()
            )
        except Exception as e:
            logger.error(f"Parse summary error: {e}")
            return ReplySummary(
                reply_id=reply_id,
                summary="摘要生成失败",
                sentiment="neutral",
                key_points=[],
                generated_at=time.time()
            )

    async def enhance_reply(self, draft_text: str, context: str = "") -> str:
        """
        增强回复质量

        输入用户的草稿, 输出润色后的版本
        """
        if self._generate_callback:
            try:
                prompt = f"""请润色以下回复, 使其更理性、有逻辑、有建设性:

原文:
{draft_text}

上下文:
{context}

要求:
1. 保持原意
2. 增加论据支持
3. 语气更中立专业
4. 避免情绪化表达

请直接返回润色后的文本, 不要解释。
"""
                result = await self._generate_callback(prompt)
                return result.strip()
            except Exception as e:
                logger.error(f"Reply enhancement error: {e}")

        return draft_text

    def clear_cache(self):
        """清除缓存"""
        self._analysis_cache.clear()
        self._summary_cache.clear()
