# -*- coding: utf-8 -*-
"""
摘要动作处理器
==============

处理摘要意图：
- SUMMARIZATION: 文本/文档摘要

使用 GlobalModelRouter 调用摘要能力。
"""

from __future__ import annotations

import logging
from typing import Optional

from ..intent_types import IntentType
from .base import (
    BaseActionHandler,
    ActionContext,
    ActionResult,
    ActionResultStatus,
)

logger = logging.getLogger(__name__)


class SummarizationHandler(BaseActionHandler):
    """
    摘要处理器

    支持的意图：
    - SUMMARIZATION

    上下文参数：
    - text: 要摘要的文本（必需）
    - max_length: 最大摘要长度（默认：原长 30%）
    - focus: 摘要侧重点（general/technical/executive/bullet_points）
    - lang: 摘要语言（默认：同原文）
    """

    @property
    def name(self) -> str:
        return "SummarizationHandler"

    @property
    def supported_intents(self) -> list:
        return [IntentType.SUMMARIZATION]

    @property
    def priority(self) -> int:
        return 50

    async def handle(self, ctx: ActionContext) -> ActionResult:
        """
        执行摘要

        ctx.kwargs 可以包含：
        - text: 要摘要的文本
        - max_length: 最大长度（字符数或 'short'/'medium'/'long'）
        - focus: 侧重点
        - lang: 摘要语言
        """
        try:
            text = ctx.extra.get("text", "")
            if not text and ctx.intent.target:
                text = ctx.intent.target

            if not text:
                return ActionResult(
                    status=ActionResultStatus.NEED_CLARIFY,
                    clarification_prompt="请告诉我需要摘要什么内容？",
                )

            max_length = ctx.extra.get("max_length", "medium")
            focus = ctx.extra.get("focus", "general")
            lang = ctx.extra.get("lang", "auto")

            logger.info(f"执行摘要: text='{text[:50]}...', focus={focus}")

            result = await self._do_summarize(text, max_length, focus, lang)

            return ActionResult(
                status=ActionResultStatus.SUCCESS,
                output=result,
                output_type="text",
                suggestions=[
                    "可调整 focus 参数改变摘要风格",
                    "可指定 lang 参数输出其他语言的摘要",
                ],
            )

        except Exception as e:
            logger.error(f"摘要失败: {e}")
            return ActionResult(
                status=ActionResultStatus.FAILURE,
                error=f"摘要失败: {str(e)}",
            )

    async def _do_summarize(self, text: str, max_length: str,
                             focus: str, lang: str) -> str:
        """调用 GlobalModelRouter 执行摘要"""
        try:
            from client.src.business.global_model_router import (
                get_global_router, ModelCapability,
            )
        except ImportError:
            from .base import get_llm_client, LLMError
            client = get_llm_client()
            prompt = self._build_prompt(text, max_length, focus, lang)
            result = client.chat(prompt=prompt, temperature=0.3)
            return result["content"]

        router = get_global_router()

        focus_hint = {
            "general": "全面概括主要内容",
            "technical": "侧重技术细节、方法和结论",
            "executive": "侧重商业要点、决策建议和关键数据",
            "bullet_points": "用要点列表形式输出",
        }.get(focus, "全面概括主要内容")

        length_hint = {
            "short": "摘要长度控制在 100 字以内",
            "medium": "摘要长度为原文的 20-30%",
            "long": "摘要长度为原文的 40-50%",
        }.get(max_length, "摘要长度为原文的 20-30%")

        lang_hint = "" if lang == "auto" else f"用 {lang} 输出摘要。"

        prompt = f"""请对以下文本进行摘要。

要求：
- {focus_hint}
- {length_hint}
- {lang_hint}
- 直接输出摘要内容，不要添加"摘要："等前缀。

文本：
```
{text}
```

摘要："""

        system = "你是一个专业的文本摘要助手。准确提取要点，语言简洁。"

        result = await router.call_model(
            capability=ModelCapability.SUMMARIZATION,
            prompt=prompt,
            system_prompt=system,
            temperature=0.3,
        )

        content = result.get("content", "").strip()
        if not content:
            raise RuntimeError("摘要返回空内容")

        return content

    def _build_prompt(self, text: str, max_length: str,
                      focus: str, lang: str) -> str:
        """构建摘要提示词（fallback 用）"""
        focus_hint = {
            "general": "全面概括主要内容",
            "technical": "侧重技术细节、方法和结论",
            "executive": "侧重商业要点、决策建议和关键数据",
            "bullet_points": "用要点列表形式输出",
        }.get(focus, "全面概括主要内容")

        length_hint = {
            "short": "摘要长度控制在 100 字以内",
            "medium": "摘要长度为原文的 20-30%",
            "long": "摘要长度为原文的 40-50%",
        }.get(max_length, "摘要长度为原文的 20-30%")

        lang_hint = "" if lang == "auto" else f"用 {lang} 输出摘要。"

        return f"""请对以下文本进行摘要。

要求：
- {focus_hint}
- {length_hint}
- {lang_hint}
- 直接输出摘要内容，不要添加"摘要："等前缀。

文本：
```
{text}
```

摘要："""
