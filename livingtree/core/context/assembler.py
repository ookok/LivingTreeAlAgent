"""
LivingTree 上下文装配与压缩
===========================

ContextAssembler: 基于 Intent 装配完整的上下文
ContextCompressor: 智能压缩上下文窗口
ContextPrioritizer: 多源信息优先级排序
PromptTemplateEngine: 基于意图组装 Prompt 模板
TokenCounter: 精确 Token 估算
"""

import math
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..memory.store import MemoryItem, MemoryQuery, MemoryStore, MemoryType


class ContextPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    TRIVIAL = 4


@dataclass
class ContextChunk:
    content: str
    source: str
    priority: ContextPriority = ContextPriority.MEDIUM
    relevance: float = 0.0
    token_estimate: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.content)


@dataclass
class AssembledContext:
    intent_type: str = ""
    intent_complexity: float = 0.0
    memories: List[Dict[str, Any]] = field(default_factory=list)
    knowledge: List[Dict[str, Any]] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    history_summary: str = ""
    compressed_context: str = ""
    estimated_tokens: int = 0
    prompt: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class TokenCounter:
    """Token 估算 — 中英文混合 Token 计数."""

    CHINESE_CHAR_RATIO = 0.6
    ENGLISH_WORD_RATIO = 0.75

    @staticmethod
    def count(text: str) -> int:
        if not text:
            return 0
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        english = len(re.findall(r"[a-zA-Z]+", text))
        numbers = len(re.findall(r"\d+", text))
        other = len(text) - chinese - english - numbers

        tokens = (chinese * TokenCounter.CHINESE_CHAR_RATIO
                  + english * TokenCounter.ENGLISH_WORD_RATIO
                  + numbers * 1.0
                  + other * 0.3)
        return max(1, int(tokens))

    @staticmethod
    def count_messages(messages: List[Dict[str, str]]) -> int:
        total = 0
        for msg in messages:
            total += TokenCounter.count(msg.get("content", ""))
            total += 4
        return total


class ContextPrioritizer:
    """多源上下文优先级排序器."""

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens

    def prioritize(self, chunks: List[ContextChunk]) -> List[ContextChunk]:
        if not chunks:
            return []

        scored: List[Tuple[ContextChunk, float]] = []
        for c in chunks:
            score = c.relevance * 5.0 + (5.0 - c.priority.value) * 0.5
            if c.source == "current_task":
                score += 3.0
            elif c.source == "memory_short_term":
                score += 1.5
            elif c.source == "memory_long_term":
                score += 0.5
            scored.append((c, score))

        scored.sort(key=lambda x: -x[1])

        result: List[ContextChunk] = []
        total_tokens = 0
        for chunk, _ in scored:
            if total_tokens + chunk.token_estimate > self.max_tokens:
                continue
            result.append(chunk)
            total_tokens += chunk.token_estimate

        return result


PROMPT_TEMPLATES: Dict[str, str] = {
    "chat": """[系统]
你是一个有用且友好的 AI 助手。请用自然对话方式回复用户。

[上下文]
{context}

[用户]
{user_input}

[回复]""",

    "writing": """[系统]
你是一个专业的写作助手。请根据上下文和用户要求，撰写高质量内容。

[上下文]
{context}

[写作要求]
{user_input}

[开始写作]""",

    "code": """[系统]
你是一个高级编程助手。请根据上下文编写、调试或改进代码。确保代码正确、简洁、有注释。

[上下文]
{context}

[编程需求]
{user_input}

[代码]""",

    "analysis": """[系统]
你是一个数据分析专家。请基于提供的上下文，进行深入分析和推理。

[上下文]
{context}

[分析目标]
{user_input}

[分析结果]""",

    "search": """[系统]
你是一个信息检索专家。请根据上下文和查询，提供准确、全面的信息。

[背景知识]
{context}

[查询]
{user_input}

[检索结果]""",

    "automation": """[系统]
你是一个自动化专家。请根据需求设计自动化方案，考虑边界情况和错误处理。

[环境上下文]
{context}

[自动化需求]
{user_input}

[自动化方案]""",

    "default": """[系统]
你是一个通用 AI 助手。

[上下文]
{context}

[输入]
{user_input}

[输出]""",
}


class PromptTemplateEngine:
    """Prompt 模板引擎 — 基于意图选择最合适的模板."""

    def __init__(self):
        self._templates = dict(PROMPT_TEMPLATES)

    def render(self, intent_type: str, user_input: str,
               context: str = "", system_extra: str = "") -> str:
        template = self._templates.get(intent_type, self._templates["default"])
        rendered = template.format(
            context=context or "无额外上下文",
            user_input=user_input,
        )
        if system_extra:
            rendered = rendered.replace("[系统]", f"[系统]\n{system_extra}")
        return rendered

    def register_template(self, name: str, template: str):
        self._templates[name] = template

    def list_templates(self) -> List[str]:
        return list(self._templates.keys())


class ContextAssembler:
    """上下文装配器 — 从多个来源组装完整上下文."""

    def __init__(self, memory_store: Optional[MemoryStore] = None):
        self.memory_store = memory_store or MemoryStore()
        self.token_counter = TokenCounter()
        self.prioritizer = ContextPrioritizer()
        self.template_engine = PromptTemplateEngine()

    def assemble(self, intent_type: str, raw_text: str,
                 complexity: float = 0.0,
                 history: Optional[List[Dict[str, str]]] = None) -> AssembledContext:
        ctx = AssembledContext(
            intent_type=intent_type,
            intent_complexity=complexity,
        )
        chunks: List[ContextChunk] = []

        # 1. 当前任务描述
        current_tokens = self.token_counter.count(raw_text)
        chunks.append(ContextChunk(
            content=raw_text, source="current_task",
            priority=ContextPriority.CRITICAL,
            relevance=1.0, token_estimate=current_tokens,
        ))

        # 2. 记忆检索 — 短期
        if raw_text:
            mem_query = MemoryQuery(
                text=raw_text, keywords=raw_text.split()[:10],
                memory_types=[MemoryType.SHORT_TERM, MemoryType.VECTOR],
                limit=5, strategy="recent",
            )
            mem_result = self.memory_store.search(mem_query)
            for item in mem_result.items:
                tokens = self.token_counter.count(item.content)
                chunks.append(ContextChunk(
                    content=item.content, source="memory_short_term",
                    priority=ContextPriority.HIGH,
                    relevance=item.relevance, token_estimate=tokens,
                    metadata={"memory_id": item.id, "importance": item.importance},
                ))
            ctx.memories = [
                {"id": i.id, "content": i.content, "relevance": i.relevance}
                for i in mem_result.items
            ]

        # 3. 记忆检索 — 长期知识
        if complexity >= 0.5:
            deep_query = MemoryQuery(
                text=raw_text, keywords=raw_text.split()[:10],
                memory_types=[MemoryType.LONG_TERM, MemoryType.GRAPH],
                limit=3, strategy="knowledge",
            )
            deep_result = self.memory_store.search(deep_query)
            for item in deep_result.items:
                tokens = self.token_counter.count(item.content)
                chunks.append(ContextChunk(
                    content=item.content, source="memory_long_term",
                    priority=ContextPriority.MEDIUM,
                    relevance=item.relevance, token_estimate=tokens,
                ))
            ctx.knowledge = [
                {"id": i.id, "content": i.content, "relevance": i.relevance}
                for i in deep_result.items
            ]

        # 4. 对话历史
        if history:
            history_text = self._summarize_history(history)
            ctx.history_summary = history_text
            chunks.append(ContextChunk(
                content=history_text, source="conversation_history",
                priority=ContextPriority.HIGH,
                relevance=0.7, token_estimate=self.token_counter.count(history_text),
            ))

        # 5. 优先级排序
        prioritized = self.prioritizer.prioritize(chunks)
        compressed = "\n\n".join(c.content for c in prioritized)
        ctx.compressed_context = compressed

        # 6. 生成 Prompt
        prompt = self.template_engine.render(
            intent_type=intent_type,
            user_input=raw_text,
            context=compressed,
        )
        ctx.prompt = prompt

        # 7. Token 估算
        ctx.estimated_tokens = self.token_counter.count(prompt)

        ctx.metadata = {
            "chunk_count": len(chunks),
            "prioritized_count": len(prioritized),
            "sources": list(set(c.source for c in chunks)),
            "strategy": "priority_based",
        }

        return ctx

    def assemble_compact(self, intent_type: str, raw_text: str,
                         max_tokens: int = 2048) -> str:
        """快速紧凑装配 — 仅返回组装后的 Prompt 字符串."""
        self.prioritizer.max_tokens = max_tokens
        ctx = self.assemble(intent_type, raw_text)
        return ctx.prompt

    def _summarize_history(self, history: List[Dict[str, str]],
                           max_entries: int = 8) -> str:
        recent = history[-max_entries:]
        parts = []
        for msg in recent:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if len(content) > 300:
                content = content[:300] + "..."
            parts.append(f"[{role}]: {content}")
        return "\n".join(parts)


class ContextCompressor:
    """上下文压缩器 — 智能截断 + 摘要."""

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self.token_counter = TokenCounter()

    def compress(self, messages: List[Dict[str, str]],
                 max_tokens: Optional[int] = None) -> List[Dict[str, str]]:
        max_tokens = max_tokens or self.max_tokens
        if not messages:
            return []

        estimated = self.token_counter.count_messages(messages)
        if estimated <= max_tokens:
            return messages

        result = []
        running = 0

        for msg in reversed(messages):
            content = msg.get("content", "")
            tokens = self.token_counter.count(content) + 4

            if running + tokens > max_tokens and result:
                break

            result.insert(0, msg)
            running += tokens

        top_off = messages[:max(0, len(messages) - len(result))]
        if top_off:
            summary = self._make_summary(top_off)
            summary_tokens = self.token_counter.count(summary) + 4
            if running + summary_tokens <= max_tokens:
                result.insert(0, {"role": "system", "content": summary})

        while running > max_tokens and len(result) > 1:
            oldest = result.pop(0)
            content = oldest.get("content", "")
            truncated = content[:200] + "..."
            result.insert(0, {**oldest, "content": truncated})
            running = self.token_counter.count_messages(result)

        return result

    def summarize(self, messages: List[Dict[str, str]]) -> str:
        parts = []
        for msg in messages[-10:]:
            content = msg.get("content", "")[:200]
            role = msg.get("role", "unknown")
            parts.append(f"[{role}]: {content}")
        return "\n".join(parts)

    def _make_summary(self, messages: List[Dict[str, str]]) -> str:
        roles = {}
        total_chars = 0
        for msg in messages:
            r = msg.get("role", "unknown")
            roles[r] = roles.get(r, 0) + 1
            total_chars += len(msg.get("content", ""))

        summary_parts = [f"早前对话摘要 ({len(messages)} 条消息):"]
        for role, count in roles.items():
            summary_parts.append(f"  {role}: {count} 条")
        summary_parts.append(f"  总计 {total_chars} 字符")
        return "\n".join(summary_parts)


__all__ = [
    "ContextAssembler",
    "ContextCompressor",
    "ContextPrioritizer",
    "PromptTemplateEngine",
    "TokenCounter",
    "AssembledContext",
    "ContextChunk",
    "ContextPriority",
]
