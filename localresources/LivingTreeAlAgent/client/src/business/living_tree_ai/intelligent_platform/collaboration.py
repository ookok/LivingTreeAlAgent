"""
协作引擎 (Collaboration Engine)
==============================

论坛与邮件的预测性协作：
1. 智能回复建议
2. 知识沉淀
3. 邮件转工单
4. @ 提及增强
"""

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .workspace import IntelligentWorkspace


class ReplyTone(Enum):
    """回复语气"""
    TECHNICAL = "technical"           # 技术解答型
    FRIENDLY = "friendly"            # 友好感谢型
    CONCISE = "concise"               # 简洁确认型
    EMPATHETIC = "empathetic"         # 共情理解型


@dataclass
class KnowledgeEntry:
    """知识条目"""
    entry_id: str
    question: str
    answer: str
    source_content_id: str            # 来源内容 ID
    source_type: str                  # forum_post/mail/document
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0          # 置信度
    verified: bool = False            # 是否已验证
    created_at: datetime = field(default_factory=datetime.now)
    view_count: int = 0
    helpful_count: int = 0


@dataclass
class ReplySuggestion:
    """回复建议"""
    tone: ReplyTone
    content: str
    confidence: float = 1.0
    relevant_context: Optional[str] = None


@dataclass
class IssueTicket:
    """工单"""
    ticket_id: str
    title: str
    description: str
    ticket_type: str                  # bug/feature/question
    priority: int                     # 1-5, 5 最高
    status: str = "open"              # open/in_progress/resolved/closed
    related_content_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class CollaborationEngine:
    """
    协作引擎

    能力：
    - 智能回复建议
    - 知识沉淀
    - 邮件转工单
    - @ 提及增强
    """

    def __init__(self, workspace: IntelligentWorkspace):
        self.workspace = workspace
        self.central_brain = workspace.central_brain

        # 知识库
        self.knowledge_base: list[KnowledgeEntry] = []

    def generate_entry_id(self, content: str) -> str:
        """生成知识条目 ID"""
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    async def suggest_replies(
        self,
        original_message: str,
        context: Optional[str] = None,
        tones: Optional[list[ReplyTone]] = None
    ) -> list[ReplySuggestion]:
        """
        生成回复建议

        Args:
            original_message: 原始消息
            context: 上下文（对话历史）
            tones: 希望的回复语气列表

        Returns:
            回复建议列表
        """
        tones = tones or [ReplyTone.TECHNICAL, ReplyTone.FRIENDLY, ReplyTone.CONCISE]
        suggestions = []

        for tone in tones[:3]:
            if self.central_brain:
                prompt = f"""基于以下对话上下文，生成一个【{tone.value}】风格的回复建议：

上下文：
{context or "（无上下文）"}

需要回复的消息：
{original_message}

回复要求：
1. 简洁有力（不超过 100 字）
2. 符合{tone.value}风格
3. 如有相关知识可引用，请一并给出

返回格式：
语气：{tone.value}
回复：<回复内容>
相关知识：<如果有的话>
"""
                result = await self.central_brain.think(prompt)
                if result:
                    # 解析结果
                    lines = result.strip().split("\n")
                    content = ""
                    relevant = None
                    for line in lines:
                        if line.startswith("回复："):
                            content = line[3:].strip()
                        elif line.startswith("相关知识："):
                            relevant = line[5:].strip()

                    if content:
                        suggestions.append(ReplySuggestion(
                            tone=tone,
                            content=content,
                            confidence=0.85,
                            relevant_context=relevant
                        ))

        return suggestions

    async def auto_tag_content(self, content: str) -> list[str]:
        """
        自动打标签

        根据内容自动识别类型并打标：
        - Bug: 包含错误、异常、崩溃等关键词
        - Feature: 包含建议、功能、改进等关键词
        - Question: 包含如何、怎么、是什么等关键词

        Args:
            content: 内容

        Returns:
            标签列表
        """
        tags = []

        # 基础关键词匹配
        bug_keywords = ["bug", "错误", "异常", "崩溃", "失败", "error", "crash"]
        feature_keywords = ["建议", "功能", "改进", "feature", "request", "优化"]
        question_keywords = ["如何", "怎么", "是什么", "为什么", "who", "how", "what", "why"]
        tutorial_keywords = ["教程", "入门", "指南", "tutorial", "guide", "学习"]

        content_lower = content.lower()

        if any(kw in content_lower for kw in bug_keywords):
            tags.append("bug")
        if any(kw in content_lower for kw in feature_keywords):
            tags.append("feature")
        if any(kw in content_lower for kw in question_keywords):
            tags.append("question")
        if any(kw in content_lower for kw in tutorial_keywords):
            tags.append("tutorial")

        # AI 增强标签
        if self.central_brain:
            prompt = f"""分析以下内容，提取 3-5 个标签：

{content[:500]}

要求：
1. 标签应简洁（2-4 字）
2. 反映内容核心主题
3. 用逗号分隔

返回示例：技术, Python, 性能优化
"""
            result = await self.central_brain.think(prompt)
            if result:
                ai_tags = [t.strip() for t in result.split(",")]
                tags.extend(ai_tags[:3])

        # 去重
        return list(set(tags))[:5]

    async def convert_to_ticket(
        self,
        content: str,
        title: str,
        source_type: str = "mail"
    ) -> IssueTicket:
        """
        邮件/帖子转工单

        当内容包含 Bug、需求等关键词时，自动创建工单

        Args:
            content: 内容
            title: 标题
            source_type: 来源类型

        Returns:
            工单对象
        """
        ticket_id = self.generate_entry_id(title + content)

        # 确定工单类型
        content_lower = content.lower()
        if any(kw in content_lower for kw in ["bug", "错误", "异常", "崩溃"]):
            ticket_type = "bug"
            priority = 4
        elif any(kw in content_lower for kw in ["建议", "功能", "改进"]):
            ticket_type = "feature"
            priority = 3
        else:
            ticket_type = "question"
            priority = 2

        # AI 增强描述
        description = content
        if self.central_brain:
            prompt = f"""将以下内容整理为工单描述：

标题：{title}
内容：
{content}

要求：
1. 保持技术细节
2. 结构化表达（问题描述、复现步骤、预期结果）
3. 不超过 300 字
"""
            result = await self.central_brain.think(prompt)
            if result:
                description = result.strip()

        return IssueTicket(
            ticket_id=ticket_id,
            title=title,
            description=description,
            ticket_type=ticket_type,
            priority=priority,
            related_content_id=None
        )

    async def enhance_mention(
        self,
        text: str,
        current_project: Optional[str] = None
    ) -> str:
        """
        @ 提及增强

        自动补全 @ 同事时其最近活跃的项目上下文

        Args:
            text: 输入文本（含 @ 符号）
            current_project: 当前项目

        Returns:
            增强后的文本
        """
        if "@" not in text:
            return text

        if not self.central_brain:
            return text

        # 提取 @ 后面的用户名
        import re
        mentions = re.findall(r'@(\w+)', text)

        for username in mentions:
            # 获取用户最近上下文（简化实现）
            prompt = f"""为 @{username} 生成一个简短的上下文提示：

当前项目：{current_project or "未知"}

请给出：
1. 用户最近讨论的主题（1 句话）
2. 用户当前关注的项目

返回格式：
最近主题：<主题>
关注项目：<项目名>
"""
            result = await self.central_brain.think(prompt)
            if result:
                # 在 @ 后面添加上下文
                context_note = f"\n💡 {result.strip()}"
                text = text.replace(f"@{username}", f"@{username}{context_note}")

        return text

    async def precipitate_knowledge(
        self,
        question: str,
        answer: str,
        source_content_id: str,
        source_type: str,
        tags: Optional[list[str]] = None
    ) -> KnowledgeEntry:
        """
        知识沉淀

        将优质问答存入知识库

        Args:
            question: 问题
            answer: 回答
            source_content_id: 来源内容 ID
            source_type: 来源类型
            tags: 标签

        Returns:
            知识条目
        """
        entry = KnowledgeEntry(
            entry_id=self.generate_entry_id(question + answer),
            question=question,
            answer=answer,
            source_content_id=source_content_id,
            source_type=source_type,
            tags=tags or []
        )

        # 添加到知识库
        self.knowledge_base.append(entry)

        # 如果有海外集群，同步到海外索引
        if self.central_brain:
            # 通知中心节点进行知识图谱更新
            pass

        return entry

    async def search_knowledge(
        self,
        query: str,
        limit: int = 5
    ) -> list[KnowledgeEntry]:
        """
        搜索知识库

        Args:
            query: 查询
            limit: 返回数量

        Returns:
            匹配的知识条目
        """
        results = []

        # 简单关键词匹配
        query_keywords = query.lower().split()
        for entry in self.knowledge_base:
            score = 0
            entry_text = (entry.question + " " + entry.answer).lower()

            for kw in query_keywords:
                if kw in entry_text:
                    score += 1

            if score > 0:
                entry.confidence = score / len(query_keywords)
                results.append(entry)

        # AI 语义排序
        if self.central_brain and results:
            prompt = f"""对以下知识库搜索结果进行相关性排序：

查询：{query}

结果：
{chr(10).join([f"{i+1}. Q: {r.question}\n   A: {r.answer[:100]}..." for i, r in enumerate(results)])}

返回格式：
按相关性排序后的序号，用逗号分隔。例如：3,1,2
"""
            result = await self.central_brain.think(prompt)
            if result:
                # 解析排序结果
                try:
                    order = [int(x.strip()) - 1 for x in result.split(",")]
                    results = [results[i] for i in order if i < len(results)]
                except ValueError:
                    pass

        return results[:limit]

    async def suggest_related_questions(
        self,
        current_question: str,
        limit: int = 3
    ) -> list[str]:
        """
        推荐相关问题

        当用户提问时，推荐相关的高质量问题

        Args:
            current_question: 当前问题
            limit: 返回数量

        Returns:
            相关问题列表
        """
        if not self.knowledge_base:
            return []

        # 基于关键词相似度
        current_keywords = set(current_question.lower().split())

        questions = []
        for entry in self.knowledge_base:
            entry_keywords = set(entry.question.lower().split())
            overlap = len(current_keywords & entry_keywords)
            if overlap > 0:
                questions.append((entry.question, overlap))

        # 排序并返回
        questions.sort(key=lambda x: x[1], reverse=True)
        return [q[0] for q in questions[:limit]]

    async def summarize_thread(
        self,
        posts: list[dict[str, Any]]
    ) -> str:
        """
        总结帖子线程

        对一个讨论串进行 AI 总结

        Args:
            posts: 帖子列表，每项包含 author, content, timestamp

        Returns:
            总结内容
        """
        if not posts:
            return ""

        # 构建对话上下文
        context = "\n\n".join([
            f"【{p.get('author', '匿名')}】{p.get('content', '')}"
            for p in posts[-10:]  # 最近 10 条
        ])

        if not self.central_brain:
            return f"讨论串共 {len(posts)} 条回复"

        prompt = f"""总结以下讨论串的核心要点：

{context}

要求：
1. 提取主要观点
2. 归纳分歧点（如果有）
3. 给出最终结论或解决方案
4. 简洁明了，不超过 200 字
"""
        result = await self.central_brain.think(prompt)
        return result.strip() if result else f"讨论串共 {len(posts)} 条回复"

    async def get_active_contributors(
        self,
        time_range_days: int = 7
    ) -> list[dict[str, Any]]:
        """
        获取活跃贡献者

        统计最近活跃的用户

        Args:
            time_range_days: 统计时间范围（天）

        Returns:
            贡献者列表
        """
        # 简化实现
        # 实际应该查询数据库
        return [
            {"node_id": "user1@device1", "name": "Alice", "posts": 15, "helpful": 12},
            {"node_id": "user2@device2", "name": "Bob", "posts": 8, "helpful": 7},
            {"node_id": "user3@device3", "name": "Charlie", "posts": 5, "helpful": 4}
        ]


def create_collaboration_engine(workspace: IntelligentWorkspace) -> CollaborationEngine:
    """创建协作引擎"""
    return CollaborationEngine(workspace)