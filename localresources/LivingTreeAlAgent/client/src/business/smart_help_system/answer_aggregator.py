"""
Answer Aggregator - 答案整合器

整合来自多个平台的回答，生成统一的答案反馈：
1. 答案去重与合并
2. 质量排序
3. 可信度评估
4. 生成整合报告
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import Counter

from .answer_monitor import Answer, MonitoredPost
from .platform_selector import Platform


@dataclass
class AnswerSource:
    """答案来源"""
    platform: Platform
    url: str
    author: str
    author_reputation: int
    upvotes: int
    is_accepted: bool
    relevance_score: float = 0.0


@dataclass
class AggregatedAnswer:
    """整合后的答案"""
    content: str                          # 整合后的内容
    sources: List[AnswerSource]           # 来源列表
    confidence: float                     # 置信度 0-1
    summary: str                          # 简短摘要
    key_points: List[str]                # 关键点
    code_snippets: List[str]             # 代码片段
    warnings: List[str]                  # 警告/注意事项
    alternative_approaches: List[str]   # 替代方案
    generated_at: datetime = field(default_factory=datetime.now)


class AnswerAggregator:
    """
    答案整合器

    将多个来源的回答整合成统一的高质量答案
    """

    def __init__(self):
        # 平台可信度权重
        self.platform_weights = {
            Platform.STACKOVERFLOW: 1.0,
            Platform.GITHUB: 0.9,
            Platform.CHATGPT: 0.8,
            Platform.ZHIHU: 0.7,
            Platform.CSDN: 0.6,
            Platform.REDDIT: 0.65,
            Platform.V2EX: 0.6,
            Platform.BLOGGER: 0.55,
        }

        # 代码片段模式
        self.code_patterns = [
            r'```[\s\S]*?```',  # Markdown代码块
            r'`[^`]+`',          # 行内代码
            r'<code>[\s\S]*?</code>',  # HTML代码
        ]

    def aggregate(
        self,
        posts: List[MonitoredPost],
        original_question: str
    ) -> AggregatedAnswer:
        """
        整合多个帖子的回答

        Args:
            posts: 监控的帖子列表
            original_question: 原始问题

        Returns:
            AggregatedAnswer: 整合后的答案
        """
        # 收集所有回答
        all_answers: List[AnswerSource] = []
        for post in posts:
            for answer in post.answers:
                source = AnswerSource(
                    platform=post.platform,
                    url=post.post_url,
                    author=answer.author,
                    author_reputation=answer.author_reputation,
                    upvotes=answer.upvotes,
                    is_accepted=answer.is_accepted,
                    relevance_score=self._calculate_relevance(
                        answer.content, original_question
                    )
                )
                all_answers.append(source)

        if not all_answers:
            return self._create_no_answer_response(original_question)

        # 排序：质量分 = 点赞*平台权重*相关性
        scored_answers = []
        for source in all_answers:
            score = self._calculate_quality_score(source)
            scored_answers.append((source, score))

        scored_answers.sort(key=lambda x: x[1], reverse=True)

        # 提取关键信息
        contents = [source.content for source, _ in scored_answers]
        code_snippets = self._extract_code_snippets(contents)
        key_points = self._extract_key_points(contents)
        warnings = self._extract_warnings(contents)
        alternatives = self._extract_alternatives(contents)

        # 生成整合内容
        aggregated_content = self._generate_aggregated_content(
            scored_answers[:5],  # 取前5个最佳回答
            key_points
        )

        # 计算置信度
        confidence = self._calculate_confidence(scored_answers)

        # 生成摘要
        summary = self._generate_summary(scored_answers, key_points)

        return AggregatedAnswer(
            content=aggregated_content,
            sources=all_answers[:10],  # 保留前10个来源
            confidence=confidence,
            summary=summary,
            key_points=key_points[:5],  # 最多5个关键点
            code_snippets=code_snippets[:3],  # 最多3个代码片段
            warnings=warnings,
            alternative_approaches=alternatives
        )

    def _calculate_relevance(self, answer_content: str, question: str) -> float:
        """计算回答与问题的相关性"""
        # 简单实现：统计问题关键词在回答中出现的次数
        question_words = set(re.findall(r'[\w]+', question.lower()))
        answer_words = set(re.findall(r'[\w]+', answer_content.lower()))

        # 去除常见词
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'under', 'again', 'further', 'then', 'once',
            'here', 'there', 'when', 'where', 'why', 'how', 'all',
            'each', 'few', 'more', 'most', 'other', 'some', 'such',
            'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
            'too', 'very', 'just', 'but', 'and', 'or', 'if', 'because',
            'as', 'until', 'while', 'of', '这', '那', '是', '在', '有',
        }
        question_words -= stopwords

        if not question_words:
            return 0.5

        matches = len(question_words & answer_words)
        return min(matches / len(question_words), 1.0)

    def _calculate_quality_score(self, source: AnswerSource) -> float:
        """计算回答质量分"""
        # 平台权重
        platform_weight = self.platform_weights.get(source.platform, 0.5)

        # 点赞归一化（假设最大1000）
        upvote_score = min(source.upvotes / 100, 1.0)

        # 声誉归一化（假设最大10000）
        reputation_score = min(source.author_reputation / 1000, 1.0)

        # 采纳加分
        accepted_bonus = 0.2 if source.is_accepted else 0

        # 相关性已有
        relevance = source.relevance_score

        # 综合评分
        score = (
            platform_weight * 0.3 +
            upvote_score * 0.25 +
            reputation_score * 0.15 +
            accepted_bonus * 0.1 +
            relevance * 0.2
        )

        return score

    def _extract_code_snippets(self, contents: List[str]) -> List[str]:
        """提取代码片段"""
        snippets = []
        seen = set()

        for content in contents:
            for pattern in self.code_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    # 清理代码
                    code = match.strip()
                    if len(code) > 20 and code not in seen:
                        snippets.append(code)
                        seen.add(code)

        return snippets

    def _extract_key_points(self, contents: List[str]) -> List[str]:
        """提取关键点"""
        # 统计最常见的句子模式
        sentences = []
        for content in contents:
            # 按句号、问号、换行分割
            parts = re.split(r'[。\n!?]', content)
            for part in parts:
                part = part.strip()
                if 10 < len(part) < 200:
                    sentences.append(part)

        # 找出重复最多的句子
        if not sentences:
            return []

        # 简单实现：选择包含"建议"、"可以"、"应该"等词的句子
        keywords = ['建议', '可以', '应该', 'try', 'use', 'use', 'install', 'import']
        keyword_sentences = []

        for sentence in sentences:
            sentence_lower = sentence.lower()
            for kw in keywords:
                if kw.lower() in sentence_lower:
                    keyword_sentences.append(sentence)
                    break

        # 去重并返回
        unique = list(dict.fromkeys(keyword_sentences))
        return unique[:5]

    def _extract_warnings(self, contents: List[str]) -> List[str]:
        """提取警告和注意事项"""
        warnings = []
        warning_keywords = [
            '注意', '警告', '小心', '不要', 'avoid', 'warning',
            'careful', 'don\'t', 'never', 'must not', '禁止',
            '谨慎', '风险', '问题', 'bug', 'issue', 'known'
        ]

        for content in contents:
            for kw in warning_keywords:
                if kw.lower() in content.lower():
                    # 提取包含该关键词的句子
                    sentences = re.split(r'[。\n!?]', content)
                    for sent in sentences:
                        if kw.lower() in sent.lower():
                            sent = sent.strip()
                            if 10 < len(sent) < 200:
                                warnings.append(sent)

        # 去重
        unique = list(dict.fromkeys(warnings))
        return unique[:3]

    def _extract_alternatives(self, contents: List[str]) -> List[str]:
        """提取替代方案"""
        alternatives = []
        alt_keywords = ['另一种', 'alternative', 'instead', '或者', '也可', '备选']

        for content in contents:
            for kw in alt_keywords:
                if kw.lower() in content.lower():
                    sentences = re.split(r'[。\n!?]', content)
                    for sent in sentences:
                        if kw.lower() in sent.lower():
                            sent = sent.strip()
                            if 10 < len(sent) < 200:
                                alternatives.append(sent)

        unique = list(dict.fromkeys(alternatives))
        return unique[:3]

    def _generate_aggregated_content(
        self,
        scored_answers: List[tuple],
        key_points: List[str]
    ) -> str:
        """生成整合后的内容"""
        lines = ["## 整合答案\n"]

        # 基于最佳回答生成主要内容
        if scored_answers:
            best_source, best_score = scored_answers[0]
            lines.append("### 最佳解决方案\n")
            lines.append(f"来源: {best_source.platform.value} - {best_source.author}\n")
            lines.append(f"评分: {best_score:.2f}\n")
            lines.append(f"\n{best_source.content}\n")

        # 添加关键点
        if key_points:
            lines.append("\n### 关键要点\n")
            for i, point in enumerate(key_points, 1):
                lines.append(f"{i}. {point}\n")

        # 添加警告
        warnings = self._extract_warnings(
            [src.content for src, _ in scored_answers]
        )
        if warnings:
            lines.append("\n### 注意事项\n")
            for warning in warnings:
                lines.append(f"- {warning}\n")

        return "\n".join(lines)

    def _generate_summary(
        self,
        scored_answers: List[tuple],
        key_points: List[str]
    ) -> str:
        """生成简短摘要"""
        total_sources = len(scored_answers)
        platforms = list(set(src.platform.value for src, _ in scored_answers))

        summary_parts = [
            f"收集了来自 {total_sources} 个回答，",
            f"涵盖 {', '.join(platforms)} 等平台。",
        ]

        if scored_answers:
            best = scored_answers[0][0]
            summary_parts.append(
                f"最相关回答来自 {best.platform.value}，"
                f"获得 {best.upvotes} 个点赞。"
            )

        if key_points:
            summary_parts.append(f"总结 {len(key_points)} 个关键要点。")

        return "".join(summary_parts)

    def _calculate_confidence(self, scored_answers: List[tuple]) -> float:
        """计算置信度"""
        if not scored_answers:
            return 0.0

        # 基于回答数量
        count_factor = min(len(scored_answers) / 5, 1.0)

        # 基于最高分
        best_score = scored_answers[0][1] if scored_answers else 0

        # 基于多平台
        platforms = set(src.platform for src, _ in scored_answers)
        platform_factor = min(len(platforms) / 3, 1.0)

        # 综合
        confidence = (
            count_factor * 0.3 +
            best_score * 0.5 +
            platform_factor * 0.2
        )

        return min(confidence, 1.0)

    def _create_no_answer_response(self, question: str) -> AggregatedAnswer:
        """创建无回答时的响应"""
        return AggregatedAnswer(
            content="目前尚未收集到回答。建议您：\n1. 检查帖子是否发布成功\n2. 换个平台尝试\n3. 稍后再试",
            sources=[],
            confidence=0.0,
            summary="暂无回答",
            key_points=[],
            code_snippets=[],
            warnings=["帖子可能未被正确发布或平台无响应"],
            alternative_approaches=[
                "手动检查帖子发布状态",
                "尝试使用其他平台发布问题",
                "考虑简化问题描述后重新发布"
            ]
        )

    def generate_user_friendly_report(
        self,
        aggregated: AggregatedAnswer,
        original_question: str
    ) -> str:
        """
        生成用户友好的报告

        Args:
            aggregated: 整合后的答案
            original_question: 原始问题

        Returns:
            格式化报告
        """
        lines = [
            "=" * 60,
            "🌐 智能求助结果报告",
            "=" * 60,
            "",
            f"📝 原始问题: {original_question}",
            "",
            "-" * 60,
            "📊 回答统计",
            "-" * 60,
            f"  - 来源数量: {len(aggregated.sources)}",
            f"  - 置信度: {aggregated.confidence:.0%}",
            f"  - 生成时间: {aggregated.generated_at.strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        if aggregated.sources:
            lines.extend([
                "-" * 60,
                "🏆 最佳回答",
                "-" * 60,
            ])
            best = aggregated.sources[0]
            lines.extend([
                f"  来自: {best.platform.value}",
                f"  作者: {best.author}",
                f"  点赞: {best.upvotes}",
                f"  链接: {best.url}",
                "",
            ])

        if aggregated.key_points:
            lines.extend([
                "-" * 60,
                "💡 关键要点",
                "-" * 60,
            ])
            for point in aggregated.key_points:
                lines.append(f"  • {point}")
            lines.append("")

        if aggregated.code_snippets:
            lines.extend([
                "-" * 60,
                "💻 推荐代码",
                "-" * 60,
            ])
            for i, code in enumerate(aggregated.code_snippets[:2], 1):
                # 截取前100字符
                preview = code[:100] + "..." if len(code) > 100 else code
                lines.append(f"  {i}. {preview}")
            lines.append("")

        if aggregated.warnings:
            lines.extend([
                "-" * 60,
                "⚠️ 注意事项",
                "-" * 60,
            ])
            for warning in aggregated.warnings:
                lines.append(f"  • {warning}")
            lines.append("")

        if aggregated.alternative_approaches:
            lines.extend([
                "-" * 60,
                "🔄 替代方案",
                "-" * 60,
            ])
            for alt in aggregated.alternative_approaches:
                lines.append(f"  • {alt}")
            lines.append("")

        lines.extend([
            "=" * 60,
            f"📎 详细回答请查看上方内容",
            "=" * 60,
        ])

        return "\n".join(lines)
