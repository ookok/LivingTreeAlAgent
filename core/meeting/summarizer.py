"""
Meeting Summarizer - 会议摘要生成器

支持多种 AI 提供商生成会议摘要：
1. Ollama (本地推荐)
2. Groq (实时推理)
3. OpenRouter (多模型聚合)
4. OpenAI / Claude (云端 API)

特性：
- 多模板支持
- 关键点提取
- 行动项识别
- 会议纪要导出
"""

import os
import json
import httpx
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod

from .transcriber import TranscriptionResult, TranscriptionSegment


class SummaryTemplate(Enum):
    """摘要模板"""
    STANDARD = "standard"           # 标准模板
    DETAILED = "detailed"          # 详细模板
    MINUTES = "minutes"            # 会议纪要
    ACTION_ITEMS = "action_items"   # 行动项模板
    BULLET_POINTS = "bullet_points" # 要点模板


@dataclass
class SummarySection:
    """摘要段落"""
    title: str                    # 标题
    content: str                  # 内容
    keywords: List[str] = field(default_factory=list)  # 关键词


@dataclass
class ActionItem:
    """行动项"""
    task: str                    # 任务描述
    assignee: Optional[str] = None  # 负责人
    deadline: Optional[str] = None  # 截止时间
    priority: str = "medium"     # 优先级: high/medium/low


@dataclass
class SummaryResult:
    """摘要结果"""
    meeting_id: str
    title: str                   # 会议标题
    summary: str                  # 完整摘要
    sections: List[SummarySection]  # 分段摘要
    action_items: List[ActionItem]  # 行动项
    key_points: List[str]        # 关键要点
    participants: List[str]       # 参与者
    duration: str                 # 会议时长
    timestamp: datetime = field(default_factory=datetime.now)
    provider: str = ""           # AI 提供商
    model: str = ""             # 使用的模型
    tokens_used: int = 0         # 消耗的 token 数
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """导出为 Markdown 格式"""
        lines = [
            f"# {self.title}",
            "",
            f"**时间**: {self.timestamp.strftime('%Y-%m-%d %H:%M')}",
            f"**时长**: {self.duration}",
            f"**参与者**: {', '.join(self.participants)}" if self.participants else "",
            "",
            "---",
            "",
        ]

        if self.sections:
            lines.append("## 摘要")
            for section in self.sections:
                lines.append(f"### {section.title}")
                lines.append(section.content)
                lines.append("")

        if self.key_points:
            lines.append("## 关键要点")
            for point in self.key_points:
                lines.append(f"- {point}")
            lines.append("")

        if self.action_items:
            lines.append("## 行动项")
            for i, item in enumerate(self.action_items, 1):
                assignee = f"@{item.assignee}" if item.assignee else ""
                deadline = f"[{item.deadline}]" if item.deadline else ""
                lines.append(f"{i}. {item.task} {assignee} {deadline}")
            lines.append("")

        lines.extend([
            "---",
            f"*由 {self.provider} ({self.model}) 生成*",
        ])

        return "\n".join(lines)

    def to_json(self) -> str:
        """导出为 JSON 格式"""
        return json.dumps({
            "meeting_id": self.meeting_id,
            "title": self.title,
            "summary": self.summary,
            "sections": [
                {"title": s.title, "content": s.content, "keywords": s.keywords}
                for s in self.sections
            ],
            "action_items": [
                {
                    "task": a.task,
                    "assignee": a.assignee,
                    "deadline": a.deadline,
                    "priority": a.priority,
                }
                for a in self.action_items
            ],
            "key_points": self.key_points,
            "participants": self.participants,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat(),
            "provider": self.provider,
            "model": self.model,
            "tokens_used": self.tokens_used,
        }, ensure_ascii=False, indent=2)


class AIProvider(ABC):
    """AI 提供商基类"""

    @abstractmethod
    def generate_summary(
        self,
        transcription: TranscriptionResult,
        template: SummaryTemplate,
        **kwargs
    ) -> SummaryResult:
        """生成摘要"""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """测试连接"""
        pass


class OllamaProvider(AIProvider):
    """
    Ollama 本地提供商

    推荐用于隐私敏感场景
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        timeout: int = 120
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate_summary(
        self,
        transcription: TranscriptionResult,
        template: SummaryTemplate,
        **kwargs
    ) -> SummaryResult:
        """生成摘要"""
        prompt = self._build_prompt(transcription, template)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                    }
                )
                response.raise_for_status()
                result = response.json()

                return self._parse_response(transcription, result, "ollama", self.model)

        except httpx.ConnectError:
            raise RuntimeError(f"无法连接到 Ollama ({self.base_url})，请确保 Ollama 服务已启动")
        except httpx.TimeoutException:
            raise RuntimeError("Ollama 响应超时，请尝试更小的模型或检查服务状态")

    def test_connection(self) -> bool:
        """测试连接"""
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    def _build_prompt(self, transcription: TranscriptionResult, template: SummaryTemplate) -> str:
        """构建提示词"""
        template_prompts = {
            SummaryTemplate.STANDARD: self._standard_template(),
            SummaryTemplate.DETAILED: self._detailed_template(),
            SummaryTemplate.MINUTES: self._minutes_template(),
            SummaryTemplate.ACTION_ITEMS: self._action_items_template(),
            SummaryTemplate.BULLET_POINTS: self._bullet_template(),
        }

        base_prompt = template_prompts.get(template, self._standard_template())

        # 添加转录文本
        text = f"会议转录内容:\n{transcription.full_text}"

        return f"{base_prompt}\n\n{text}"

    def _standard_template(self) -> str:
        return """你是一个专业的会议助理。请根据以下会议转录内容，生成一份简洁的会议摘要。

要求：
1. 生成会议标题
2. 总结会议主要讨论内容
3. 提取3-5个关键要点
4. 识别行动项（如果有）
5. 列出参与者（如果提及）

请用中文回复，格式如下：
TITLE: <会议标题>
SUMMARY: <会议摘要>
KEY_POINTS: <关键要点，每行一个>
ACTION_ITEMS: <行动项，格式：任务 | 负责人 | 截止时间>
PARTICIPANTS: <参与者>

请直接输出，不要有多余的解释。"""

    def _detailed_template(self) -> str:
        return """你是一个专业的会议助理。请根据以下会议转录内容，生成一份详细的会议报告。

要求：
1. 生成会议标题
2. 按主题分段总结
3. 每个主题提取关键讨论点
4. 识别所有行动项，包括负责人和截止时间
5. 列出所有参与者
6. 提取关键词

请用中文回复，格式如下：
TITLE: <会议标题>
SECTIONS: <分段总结，格式：主题|内容|关键词>
KEY_POINTS: <关键要点>
ACTION_ITEMS: <行动项>
PARTICIPANTS: <参与者>
KEYWORDS: <关键词>

请直接输出，不要有多余的解释。"""

    def _minutes_template(self) -> str:
        return """你是一个专业的会议助理。请根据以下会议转录内容，生成标准会议纪要。

格式要求：
1. 会议基本信息（时间、参与者）
2. 议程与讨论
3. 决议事项
4. 行动项清单

请用中文回复，格式如下：
TITLE: <会议标题>
DATE: <会议日期>
PARTICIPANTS: <参与者>
AGENDA: <议程>
DISCUSSION: <讨论内容>
DECISIONS: <决议事项>
ACTION_ITEMS: <行动项>

请直接输出，不要有多余的解释。"""

    def _action_items_template(self) -> str:
        return """你是一个专业的会议助理。请从以下会议转录中提取所有行动项。

要求：
1. 列出每个行动项
2. 标注负责人（如果提到）
3. 标注截止时间（如果提到）
4. 评估优先级（高/中/低）

请用中文回复，格式如下：
ACTION_ITEMS:
序号|任务描述|负责人|截止时间|优先级
1|<任务1>|<负责人1>|<时间1>|<优先级1>
2|<任务2>|<负责人2>|<时间2>|<优先级2>

请直接输出，不要有多余的解释。"""

    def _bullet_template(self) -> str:
        return """你是一个专业的会议助理。请根据以下会议转录内容，用简洁的要点形式总结。

要求：
1. 用 bullet points 格式
2. 每个要点简洁明了
3. 突出重要决策和结论
4. 行动项单独列出

请用中文回复，直接输出要点列表。"""

    def _parse_response(
        self,
        transcription: TranscriptionResult,
        response: Dict,
        provider: str,
        model: str
    ) -> SummaryResult:
        """解析 AI 响应"""
        text = response.get("response", "")

        # 简单解析（实际应该用更健壮的解析）
        lines = text.split("\n")

        title = "会议摘要"
        summary = text
        key_points = []
        action_items = []
        participants = []

        for line in lines:
            line = line.strip()
            if line.startswith("TITLE:"):
                title = line.replace("TITLE:", "").strip()
            elif line.startswith("SUMMARY:"):
                summary = line.replace("SUMMARY:", "").strip()
            elif line.startswith("KEY_POINTS:"):
                # 后续行都是要点
                pass
            elif line.startswith("ACTION_ITEMS:"):
                # 后续行都是行动项
                pass
            elif line.startswith("PARTICIPANTS:"):
                participants_str = line.replace("PARTICIPANTS:", "").strip()
                if participants_str:
                    participants = [p.strip() for p in participants_str.split(",")]

        # 简单地将全文作为摘要
        sections = [SummarySection(title="会议摘要", content=summary)]

        return SummaryResult(
            meeting_id=transcription.meeting_id,
            title=title,
            summary=summary,
            sections=sections,
            action_items=action_items,
            key_points=key_points,
            participants=participants,
            duration=f"{int(transcription.duration // 60)}分钟",
            provider=provider,
            model=model,
            tokens_used=response.get("eval_count", 0),
        )


class GroqProvider(AIProvider):
    """
    Groq 云端提供商

    实时推理，低延迟
    """

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.1-70b-versatile",
        timeout: int = 60
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate_summary(
        self,
        transcription: TranscriptionResult,
        template: SummaryTemplate,
        **kwargs
    ) -> SummaryResult:
        """生成摘要"""
        prompt = self._build_prompt(transcription, template)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "你是一个专业的会议助理。"},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,
                    }
                )
                response.raise_for_status()
                result = response.json()

                return self._parse_response(
                    transcription,
                    result["choices"][0]["message"]["content"],
                    "groq",
                    self.model
                )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise RuntimeError("Groq API 密钥无效")
            raise RuntimeError(f"Groq API 错误: {e}")

    def test_connection(self) -> bool:
        """测试连接"""
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return response.status_code == 200
        except Exception:
            return False

    def _build_prompt(self, transcription: TranscriptionResult, template: SummaryTemplate) -> str:
        """构建提示词"""
        # 简化实现
        return f"""请根据以下会议转录内容生成摘要：

{transcription.full_text[:3000]}

请用以下格式回复：
TITLE: <会议标题>
SUMMARY: <200字以内的摘要>
KEY_POINTS: <关键要点>
ACTION_ITEMS: <行动项（如果有）>"""

    def _parse_response(
        self,
        transcription: TranscriptionResult,
        text: str,
        provider: str,
        model: str
    ) -> SummaryResult:
        """解析响应"""
        return SummaryResult(
            meeting_id=transcription.meeting_id,
            title="会议摘要",
            summary=text,
            sections=[SummarySection(title="摘要", content=text)],
            action_items=[],
            key_points=[],
            participants=[],
            duration=f"{int(transcription.duration // 60)}分钟",
            provider=provider,
            model=model,
        )


class OpenRouterProvider(AIProvider):
    """
    OpenRouter 多模型聚合提供商
    """

    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-3.5-sonnet",
        timeout: int = 60
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate_summary(
        self,
        transcription: TranscriptionResult,
        template: SummaryTemplate,
        **kwargs
    ) -> SummaryResult:
        """生成摘要"""
        prompt = self._build_prompt(transcription, template)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://hermes-desktop",
                        "X-Title": "Hermes Desktop Meeting Assistant",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "你是一个专业的会议助理。"},
                            {"role": "user", "content": prompt},
                        ],
                    }
                )
                response.raise_for_status()
                result = response.json()

                return self._parse_response(
                    transcription,
                    result["choices"][0]["message"]["content"],
                    "openrouter",
                    self.model
                )

        except Exception as e:
            raise RuntimeError(f"OpenRouter API 错误: {e}")

    def test_connection(self) -> bool:
        """测试连接"""
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return response.status_code == 200
        except Exception:
            return False

    def _build_prompt(self, transcription: TranscriptionResult, template: SummaryTemplate) -> str:
        return f"""请根据以下会议转录内容生成摘要：

{transcription.full_text[:3000]}

请用以下格式回复：
TITLE: <会议标题>
SUMMARY: <200字以内的摘要>
KEY_POINTS: <关键要点>
ACTION_ITEMS: <行动项（如果有）>"""

    def _parse_response(
        self,
        transcription: TranscriptionResult,
        text: str,
        provider: str,
        model: str
    ) -> SummaryResult:
        """解析响应"""
        return SummaryResult(
            meeting_id=transcription.meeting_id,
            title="会议摘要",
            summary=text,
            sections=[SummarySection(title="摘要", content=text)],
            action_items=[],
            key_points=[],
            participants=[],
            duration=f"{int(transcription.duration // 60)}分钟",
            provider=provider,
            model=model,
        )


class MeetingSummarizer:
    """
    会议摘要生成器

    统一接口，支持多种 AI 提供商
    """

    PROVIDERS = {
        "ollama": OllamaProvider,
        "groq": GroqProvider,
        "openrouter": OpenRouterProvider,
    }

    def __init__(self, provider: str = "ollama", **kwargs):
        """
        初始化摘要生成器

        Args:
            provider: 提供商名称 (ollama/groq/openrouter)
            **kwargs: 提供商特定参数
        """
        provider_class = self.PROVIDERS.get(provider)
        if not provider_class:
            raise ValueError(f"不支持的提供商: {provider}")

        self.provider_name = provider
        self.provider = provider_class(**kwargs)

    def summarize(
        self,
        transcription: TranscriptionResult,
        template: SummaryTemplate = SummaryTemplate.STANDARD
    ) -> SummaryResult:
        """
        生成摘要

        Args:
            transcription: 转录结果
            template: 摘要模板

        Returns:
            SummaryResult: 摘要结果
        """
        return self.provider.generate_summary(transcription, template)

    def test_connection(self) -> bool:
        """测试连接"""
        return self.provider.test_connection()

    @classmethod
    def create_ollama(cls, model: str = "llama3.2") -> "MeetingSummarizer":
        """创建 Ollama 提供商"""
        return cls(provider="ollama", model=model)

    @classmethod
    def create_groq(cls, api_key: str, model: str = "llama-3.1-70b-versatile") -> "MeetingSummarizer":
        """创建 Groq 提供商"""
        return cls(provider="groq", api_key=api_key, model=model)

    @classmethod
    def create_openrouter(cls, api_key: str, model: str = "anthropic/claude-3.5-sonnet") -> "MeetingSummarizer":
        """创建 OpenRouter 提供商"""
        return cls(provider="openrouter", api_key=api_key, model=model)
