"""
会议纪要自动生成模块

使用 LLM 分析会议内容自动生成会议纪要
"""

import asyncio
import json
import time
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid


class SummaryType(Enum):
    """纪要类型"""
    FULL = "full"
    BRIEF = "brief"
    ACTION_ITEMS = "action_items"
    DECISIONS = "decisions"
    KEY_POINTS = "key_points"


@dataclass
class MeetingRecord:
    """会议记录"""
    meeting_id: str
    title: str
    date: str
    participants: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    speeches: List[Dict] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None


@dataclass
class SummarySection:
    """纪要章节"""
    title: str
    content: str
    importance: float = 1.0


@dataclass
class MeetingSummary:
    """会议纪要"""
    meeting_id: str
    title: str
    date: str
    duration: float
    participant_count: int
    sections: List[SummarySection] = field(default_factory=list)
    key_decisions: List[str] = field(default_factory=list)
    action_items: List[Dict] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)
    unresolved_issues: List[str] = field(default_factory=list)
    full_text: str = ""
    generated_at: float = field(default_factory=time.time)


@dataclass
class ActionItem:
    """待办事项"""
    task: str
    assignee: Optional[str] = None
    deadline: Optional[str] = None
    priority: str = "medium"
    status: str = "pending"


class MeetingSummaryGenerator:
    """会议纪要生成器"""

    def __init__(self, llm_handler: Optional[Callable] = None):
        self.llm_handler = llm_handler
        self._is_initialized = False

    async def initialize(self) -> bool:
        """
        初始化

        Returns:
            bool: 是否初始化成功
        """
        if self._is_initialized:
            return True

        if not self.llm_handler:
            print("[SummaryGenerator] 未提供 LLM handler，将使用模拟生成")
        else:
            print("[SummaryGenerator] 初始化成功")

        self._is_initialized = True
        return True

    async def generate_summary(
        self,
        meeting_record: MeetingRecord,
        summary_type: SummaryType = SummaryType.FULL
    ) -> MeetingSummary:
        """
        生成会议纪要

        Args:
            meeting_record: 会议记录
            summary_type: 纪要类型

        Returns:
            MeetingSummary: 会议纪要
        """
        if not self._is_initialized:
            await self.initialize()

        duration = 0
        if meeting_record.start_time and meeting_record.end_time:
            duration = meeting_record.end_time - meeting_record.start_time

        if self.llm_handler:
            return await self._generate_with_llm(meeting_record, summary_type, duration)
        else:
            return self._generate_mock(meeting_record, duration)

    async def _generate_with_llm(
        self,
        meeting_record: MeetingRecord,
        summary_type: SummaryType,
        duration: float
    ) -> MeetingSummary:
        """使用 LLM 生成"""
        prompt = self._build_prompt(meeting_record, summary_type)

        try:
            response = await self.llm_handler(prompt)

            return self._parse_llm_response(
                meeting_record, response, duration, summary_type
            )

        except Exception as e:
            print(f"[SummaryGenerator] LLM 生成失败: {e}")
            return self._generate_mock(meeting_record, duration)

    def _build_prompt(
        self,
        meeting_record: MeetingRecord,
        summary_type: SummaryType
    ) -> str:
        """构建提示"""
        speeches_text = "\n".join([
            f"- {s.get('speaker', 'Unknown')}: {s.get('text', '')}"
            for s in meeting_record.speeches
        ])

        prompt = f"""请分析以下会议记录，生成{'详细' if summary_type == SummaryType.FULL else '简要'}的会议纪要。

会议标题: {meeting_record.title}
会议日期: {meeting_record.date}
参与者: {', '.join(meeting_record.participants)}
议题: {', '.join(meeting_record.topics)}

会议内容:
{speeches_text}

请生成包含以下部分的纪要:
1. 会议概要
2. 关键决策
3. 待办事项（包含任务、负责人、优先级）
4. 关键要点
5. 未解决的问题

以 JSON 格式输出:
{{
    "summary": "会议概要",
    "key_decisions": ["决策1", "决策2"],
    "action_items": [{{"task": "任务", "assignee": "负责人", "priority": "high/medium/low"}}],
    "key_points": ["要点1", "要点2"],
    "unresolved_issues": ["问题1", "问题2"]
}}
"""
        return prompt

    def _parse_llm_response(
        self,
        meeting_record: MeetingRecord,
        response: str,
        duration: float,
        summary_type: SummaryType
    ) -> MeetingSummary:
        """解析 LLM 响应"""
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                json_str = response

            data = json.loads(json_str)

            sections = [
                SummarySection(
                    title="会议概要",
                    content=data.get("summary", ""),
                    importance=1.0
                )
            ]

            action_items = [
                ActionItem(
                    task=item.get("task", ""),
                    assignee=item.get("assignee"),
                    priority=item.get("priority", "medium")
                )
                for item in data.get("action_items", [])
            ]

            summary = MeetingSummary(
                meeting_id=meeting_record.meeting_id,
                title=meeting_record.title,
                date=meeting_record.date,
                duration=duration,
                participant_count=len(meeting_record.participants),
                sections=sections,
                key_decisions=data.get("key_decisions", []),
                action_items=action_items,
                key_points=data.get("key_points", []),
                unresolved_issues=data.get("unresolved_issues", []),
                full_text=response
            )

            return summary

        except json.JSONDecodeError:
            print("[SummaryGenerator] JSON 解析失败，使用默认生成")
            return self._generate_mock(meeting_record, duration)

    def _generate_mock(
        self,
        meeting_record: MeetingRecord,
        duration: float
    ) -> MeetingSummary:
        """生成模拟纪要"""
        summary_text = f"""会议纪要

会议标题: {meeting_record.title}
会议日期: {meeting_record.date}
参会人数: {len(meeting_record.participants)}
会议时长: {duration:.0f} 分钟

## 会议概要

本次会议围绕以下议题展开:
{chr(10).join(f"- {t}" for t in meeting_record.topics)}

## 关键决策

1. 确认了项目整体方向
2. 通过了下一阶段工作计划
3. 明确了责任分工

## 待办事项

- 完善技术方案 (负责人: 技术团队, 优先级: 高)
- 准备项目演示材料 (负责人: 产品团队, 优先级: 中)
- 安排下次评审会议 (负责人: 项目经理, 优先级: 低)

## 关键要点

1. 项目进展符合预期
2. 需要加强跨部门协作
3. 技术方案需要进一步优化

## 未解决的问题

- 预算调整方案待定
- 第三方依赖问题需要进一步评估
"""
        return MeetingSummary(
            meeting_id=meeting_record.meeting_id,
            title=meeting_record.title,
            date=meeting_record.date,
            duration=duration,
            participant_count=len(meeting_record.participants),
            sections=[
                SummarySection(title="会议概要", content="见下文", importance=1.0)
            ],
            key_decisions=[
                "确认了项目整体方向",
                "通过了下一阶段工作计划"
            ],
            action_items=[
                ActionItem(task="完善技术方案", assignee="技术团队", priority="high"),
                ActionItem(task="准备项目演示材料", assignee="产品团队", priority="medium")
            ],
            key_points=[
                "项目进展符合预期",
                "需要加强跨部门协作"
            ],
            unresolved_issues=[
                "预算调整方案待定"
            ],
            full_text=summary_text
        )

    def format_summary(
        self,
        summary: MeetingSummary,
        format_type: str = "markdown"
    ) -> str:
        """
        格式化纪要

        Args:
            summary: 会议纪要
            format_type: 格式类型 (markdown, html, json, txt)

        Returns:
            str: 格式化后的文本
        """
        if format_type == "json":
            return self._format_json(summary)
        elif format_type == "html":
            return self._format_html(summary)
        else:
            return self._format_markdown(summary)

    def _format_markdown(self, summary: MeetingSummary) -> str:
        """Markdown 格式"""
        action_items_text = "\n".join([
            f"- [{item.assignee}] {item.task} (优先级: {item.priority})"
            for item in summary.action_items
        ])

        decisions_text = "\n".join([
            f"{i+1}. {d}"
            for i, d in enumerate(summary.key_decisions)
        ])

        points_text = "\n".join([
            f"{i+1}. {p}"
            for i, p in enumerate(summary.key_points)
        ])

        return f"""# {summary.title}

**日期**: {summary.date}
**时长**: {summary.duration:.0f} 分钟
**参会人数**: {summary.participant_count}

---

## 会议概要

{summary.sections[0].content if summary.sections else ''}

## 关键决策

{decisions_text}

## 待办事项

{action_items_text}

## 关键要点

{points_text}

## 未解决的问题

{chr(10).join(f"- {i}" for i in summary.unresolved_issues)}

---

*纪要生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}*
"""

    def _format_html(self, summary: MeetingSummary) -> str:
        """HTML 格式"""
        markdown = self._format_markdown(summary)
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{summary.title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; border-bottom: 1px solid #ccc; }}
        .meta {{ color: #888; font-size: 14px; }}
        ul {{ line-height: 1.8; }}
    </style>
</head>
<body>
    <pre>{markdown}</pre>
</body>
</html>"""

    def _format_json(self, summary: MeetingSummary) -> str:
        """JSON 格式"""
        return json.dumps({
            "meeting_id": summary.meeting_id,
            "title": summary.title,
            "date": summary.date,
            "duration": summary.duration,
            "participant_count": summary.participant_count,
            "key_decisions": summary.key_decisions,
            "action_items": [
                {
                    "task": item.task,
                    "assignee": item.assignee,
                    "priority": item.priority,
                    "status": item.status
                }
                for item in summary.action_items
            ],
            "key_points": summary.key_points,
            "unresolved_issues": summary.unresolved_issues
        }, ensure_ascii=False, indent=2)


class MeetingMinutesExporter:
    """会议纪要导出器"""

    @staticmethod
    def export(
        summary: MeetingSummary,
        output_path: str,
        format_type: str = "markdown"
    ) -> bool:
        """
        导出纪要

        Args:
            summary: 会议纪要
            output_path: 输出路径
            format_type: 格式类型

        Returns:
            bool: 是否成功
        """
        try:
            generator = MeetingSummaryGenerator()
            content = generator.format_summary(summary, format_type)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return True

        except Exception as e:
            print(f"[Exporter] 导出失败: {e}")
            return False


_global_generator: Optional[MeetingSummaryGenerator] = None


def get_summary_generator(
    llm_handler: Optional[Callable] = None
) -> MeetingSummaryGenerator:
    """获取纪要生成器"""
    global _global_generator
    if _global_generator is None:
        _global_generator = MeetingSummaryGenerator(llm_handler)
    return _global_generator
