"""
内容创作 AI (Content Creator)
============================

提供智能撰写辅助：
1. 语法检查（边缘节点）
2. 语气优化
3. 深度内容生成（海外集群）
4. 代码示例生成
5. 引用段落生成
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .workspace import IntelligentWorkspace


class WritingTone(Enum):
    """写作语气"""
    PROFESSIONAL = "professional"       # 专业商务
    FRIENDLY = "friendly"              # 友好亲切
    TECHNICAL = "technical"            # 技术严谨
    CASUAL = "casual"                  # 轻松随意
    FORMAL = "formal"                  # 正式规范


class ContentTemplate(Enum):
    """内容模板"""
    TECHNICAL_ARTICLE = "technical_article"     # 技术文章
    PROJECT_UPDATE = "project_update"           # 项目进度
    BUG_REPORT = "bug_report"                   # Bug 报告
    FEATURE_REQUEST = "feature_request"         # 功能需求
    KNOWLEDGE_SHARING = "knowledge_sharing"     # 知识分享
    MEETING_NOTES = "meeting_notes"            # 会议纪要
    WEEKLY_REPORT = "weekly_report"            # 周报


@dataclass
class WritingSuggestion:
    """写作建议"""
    type: str                              # suggestion/correction/completion
    original: str                          # 原始文本
    suggested: str                          # 建议文本
    reason: str                             # 原因说明
    confidence: float = 1.0                # 置信度


@dataclass
class CodeExample:
    """代码示例"""
    language: str
    code: str
    description: str
    source: str                             # 来源: github/paper/docs
    url: Optional[str] = None


@dataclass
class ContentEnhancement:
    """内容增强结果"""
    enhanced_content: str
    suggestions: list[WritingSuggestion] = field(default_factory=list)
    code_examples: list[CodeExample] = field(default_factory=list)
    references: list[str] = field(default_factory=list)  # 引用链接
    tone_score: float = 1.0                # 语气契合度


class ContentCreator:
    """
    内容创作 AI

    能力：
    - 语法检查与修正
    - 语气优化
    - 代码示例生成
    - 引用段落生成
    """

    def __init__(self, workspace: IntelligentWorkspace):
        self.workspace = workspace
        self.central_brain = workspace.central_brain

    async def enhance_writing(
        self,
        content: str,
        target_tone: WritingTone = WritingTone.PROFESSIONAL
    ) -> str:
        """
        增强写作

        Args:
            content: 原始内容
            target_tone: 目标语气

        Returns:
            增强后的内容
        """
        # 调用中心大脑进行 AI 增强
        if self.central_brain:
            prompt = f"""请优化以下文本的语气，使其符合【{target_tone.value}】风格：

原始文本：
{content}

要求：
1. 保持原意不变
2. 优化语法和表达
3. 调整语气风格
4. 返回优化后的文本
"""
            result = await self.central_brain.think(prompt)
            if result:
                return result.strip()

        # 无中心大脑时，返回原始内容
        return content

    async def check_grammar(self, content: str) -> list[WritingSuggestion]:
        """
        语法检查

        Returns:
            写作建议列表
        """
        suggestions = []

        # 基础语法检查
        checks = [
            # (正则模式, 错误类型, 建议)
            (r'([\u4e00-\u9fa5])\s+([\u4e00-\u9fa5])', "空格错误", "相邻汉字不应有空格"),
            (r'([，。；：、])\s', "标点后空格", "中文标点后不应有空格"),
            (r'\s([，。；：、])', "标点前空格", "中文标点前不应有空格"),
            (r'\.{3,}', "省略号", "应使用中文省略号……"),
            (r'\.\.\.', "省略号", "应使用中文省略号……"),
        ]

        # 这里简化实现，实际应该调用边缘节点的语法检查服务
        return suggestions

    async def optimize_tone(
        self,
        content: str,
        from_tone: str,
        to_tone: WritingTone
    ) -> str:
        """
        语气优化

        Args:
            content: 原始内容
            from_tone: 当前语气描述
            to_tone: 目标语气

        Returns:
            优化后的内容
        """
        tone_guide = {
            WritingTone.PROFESSIONAL: "专业、正式、商务、严谨",
            WritingTone.FRIENDLY: "亲切、友好、口语化",
            WritingTone.TECHNICAL: "技术性强、准确、专业术语",
            WritingTone.CASUAL: "轻松、随意、简略",
            WritingTone.FORMAL: "规范、正式、完整"
        }

        if self.central_brain:
            prompt = f"""将以下文本的语气从【{from_tone}】转换为【{tone_guide[to_tone]}】：

原始文本：
{content}

要求：
1. 保持技术准确性
2. 调整语气风格
3. 保持原意
"""
            result = await self.central_brain.think(prompt)
            if result:
                return result.strip()

        return content

    async def generate_summary(
        self,
        content: str,
        max_length: int = 200
    ) -> str:
        """
        生成摘要

        Args:
            content: 原始内容
            max_length: 最大长度

        Returns:
            摘要内容
        """
        if self.central_brain:
            prompt = f"""请为以下内容生成简洁的摘要（不超过 {max_length} 字）：

{content}

要求：
1. 提取核心要点
2. 语言简洁
3. 不超过 {max_length} 字
"""
            result = await self.central_brain.think(prompt)
            if result:
                return result.strip()[:max_length]

        # 简化实现：取前 N 个字符
        return content[:max_length] + "..." if len(content) > max_length else content

    async def extract_keywords(self, content: str, top_n: int = 5) -> list[str]:
        """
        提取关键词

        Args:
            content: 内容
            top_n: 返回数量

        Returns:
            关键词列表
        """
        if self.central_brain:
            prompt = f"""从以下内容中提取 {top_n} 个最重要的关键词：

{content}

要求：
1. 返回格式：关键词1, 关键词2, ...
2. 只返回关键词，用逗号分隔
3. 选择最有代表性的词
"""
            result = await self.central_brain.think(prompt)
            if result:
                keywords = [k.strip() for k in result.split(",")]
                return keywords[:top_n]

        # 简化实现：提取长词
        words = content.split()
        keywords = [w for w in words if len(w) >= 4][:top_n]
        return keywords

    async def generate_code_examples(
        self,
        topic: str,
        language: str = "python",
        count: int = 3
    ) -> list[CodeExample]:
        """
        生成代码示例

        Args:
            topic: 主题
            language: 编程语言
            count: 示例数量

        Returns:
            代码示例列表
        """
        examples = []

        # 调用海外集群获取代码示例
        if self.central_brain:
            prompt = f"""为以下主题生成 {count} 个 {language} 代码示例：

主题：{topic}

要求：
1. 每个示例包含代码和简要说明
2. 代码应简洁实用
3. 标注代码来源（如 GitHub/官方文档）
"""
            result = await self.central_brain.think(prompt)
            if result:
                # 解析结果（简化实现）
                example = CodeExample(
                    language=language,
                    code=f"# {topic}\n# 示例代码",
                    description=f"{topic} 的 {language} 实现",
                    source="AI Generated"
                )
                examples.append(example)

        return examples

    async def generate_reply_suggestions(
        self,
        original_message: str,
        context: Optional[str] = None,
        count: int = 3
    ) -> list[str]:
        """
        生成回复建议

        Args:
            original_message: 原始消息
            context: 上下文
            count: 建议数量

        Returns:
            回复建议列表
        """
        tones = ["技术解答型", "友好感谢型", "简洁确认型"]
        suggestions = []

        for i, tone in enumerate(tones[:count]):
            if self.central_brain:
                prompt = f"""基于以下对话，生成一个【{tone}】风格的回复：

{context or "（无上下文）"}

原始消息：
{original_message}

要求：
1. 回复简洁
2. 符合指定语气
3. 只返回回复内容
"""
                result = await self.central_brain.think(prompt)
                if result:
                    suggestions.append(result.strip())

        return suggestions

    async def generate_content(
        self,
        title: str,
        template: ContentTemplate,
        context: Optional[str] = None,
        tone: WritingTone = WritingTone.PROFESSIONAL
    ) -> str:
        """
        根据模板生成内容

        Args:
            title: 标题
            template: 内容模板
            context: 上下文
            tone: 语气

        Returns:
            生成的内容
        """
        template_guides = {
            ContentTemplate.TECHNICAL_ARTICLE: "技术文章：包含摘要、背景、原理、实现、总结",
            ContentTemplate.PROJECT_UPDATE: "项目进度：包含完成情况、遇到的问题、下一步计划",
            ContentTemplate.BUG_REPORT: "Bug报告：包含问题描述、复现步骤、环境信息、堆栈信息",
            ContentTemplate.FEATURE_REQUEST: "功能需求：包含需求背景、功能描述、预期效果",
            ContentTemplate.KNOWLEDGE_SHARING: "知识分享：包含主题介绍、核心内容、实践案例",
            ContentTemplate.MEETING_NOTES: "会议纪要：包含会议主题、讨论要点、行动项",
            ContentTemplate.WEEKLY_REPORT: "周报：包含本周完成、下周计划、问题与思考"
        }

        if self.central_brain:
            prompt = f"""根据以下信息生成{template_guides[template]}：

标题：{title}
{tone.value}语气

{f"上下文信息：\n{context}" if context else ""}

要求：
1. 内容完整、结构清晰
2. 符合{tone.value}风格
3. 适当使用标题和列表
"""
            result = await self.central_brain.think(prompt)
            if result:
                return result.strip()

        return f"# {title}\n\n内容待生成..."

    async def suggest_related_content(
        self,
        content: str,
        limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        建议相关内容

        Args:
            content: 当前内容
            limit: 返回数量

        Returns:
            相关内容列表，每项包含 id、title、relevance_score
        """
        # 从数据库查找相关内容
        keywords = await self.extract_keywords(content)

        related = []
        for kw in keywords[:3]:
            contents = await self.workspace.list_contents(limit=limit)
            for c in contents:
                if kw in c.original_content or kw in c.summary:
                    related.append({
                        "id": c.metadata.content_id,
                        "title": c.metadata.title,
                        "relevance_score": 0.8
                    })

        return related[:limit]


def create_content_creator(workspace: IntelligentWorkspace) -> ContentCreator:
    """创建内容创建器"""
    return ContentCreator(workspace)