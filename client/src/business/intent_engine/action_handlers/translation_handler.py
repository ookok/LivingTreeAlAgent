# -*- coding: utf-8 -*-
"""
翻译动作处理器
=================

处理翻译意图：
- TRANSLATION: 文本翻译

使用 GlobalModelRouter 调用翻译能力。
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

# 支持的目标语言映射
LANGUAGE_MAP = {
    "中文": "Chinese",
    "简体中文": "Simplified Chinese",
    "繁体中文": "Traditional Chinese",
    "英文": "English",
    "英语": "English",
    "日语": "Japanese",
    "日语": "Japanese",
    "韩语": "Korean",
    "法语": "French",
    "德语": "German",
    "西班牙语": "Spanish",
    "俄语": "Russian",
}


class TranslationHandler(BaseActionHandler):
    """
    翻译处理器

    支持的意图：
    - TRANSLATION

    上下文参数：
    - text: 要翻译的文本（必需）
    - target_lang: 目标语言（默认：中文）
    - source_lang: 源语言（可选，自动检测）
    - formality: 正式程度（formal/informal/auto）
    """

    @property
    def name(self) -> str:
        return "TranslationHandler"

    @property
    def supported_intents(self) -> list:
        return [IntentType.TRANSLATION]

    @property
    def priority(self) -> int:
        return 50  # 较高优先级

    def handle(self, ctx: ActionContext) -> ActionResult:
        """
        执行翻译

        Args:
            ctx: 动作执行上下文
                  ctx.kwargs 可以包含：
                  - text: 要翻译的文本
                  - target_lang: 目标语言（中文/英文/...）
                  - source_lang: 源语言（可选）
                  - formality: 正式程度

        Returns:
            ActionResult: 执行结果
        """
        import asyncio

        try:
            # 从上下文或 kwargs 获取参数
            text = ctx.extra.get("text", "")
            if not text and ctx.intent.target:
                text = ctx.intent.target

            if not text:
                return ActionResult(
                    status=ActionResultStatus.NEED_CLARIFY,
                    clarification_prompt="请告诉我需要翻译什么内容？",
                )

            target_lang = ctx.extra.get("target_lang", "中文")
            source_lang = ctx.extra.get("source_lang", "auto")
            formality = ctx.extra.get("formality", "auto")

            logger.info(f"执行翻译: text='{text[:50]}...', target={target_lang}")

            # 调用 GlobalModelRouter
            result = asyncio.run(self._do_translate(text, target_lang, source_lang, formality))

            return ActionResult(
                status=ActionResultStatus.SUCCESS,
                output=result,
                output_type="text",
                suggestions=[
                    f"已将文本翻译为{target_lang}",
                    "如需调整正式程度，请指定 formality 参数",
                ],
            )

        except Exception as e:
            logger.error(f"翻译失败: {e}")
            return ActionResult(
                status=ActionResultStatus.FAILED,
                error=f"翻译失败: {str(e)}",
            )

    async def _do_translate(self, text: str, target_lang: str,
                            source_lang: str, formality: str) -> str:
        """调用 GlobalModelRouter 执行翻译"""
        try:
            from client.src.business.global_model_router import (
                get_global_router, ModelCapability,
            )
        except ImportError:
            # fallback: 使用 LLMClient
            from .base import get_llm_client, LLMError
            client = get_llm_client()
            prompt = self._build_prompt(text, target_lang, source_lang, formality)
            result = client.chat(prompt=prompt, temperature=0.3)
            return result["content"]

        router = get_global_router()

        # 构建翻译提示词
        target_lang_en = LANGUAGE_MAP.get(target_lang, target_lang)
        source_hint = f"从 {source_lang} " if source_lang != "auto" else ""
        formality_hint = ""
        if formality == "formal":
            formality_hint = "使用正式、礼貌的语气。"
        elif formality == "informal":
            formality_hint = "使用随意、口语化的语气。"

        prompt = f"""请将以下文本{source_hint}翻译为 {target_lang_en}。
{formality_hint}

只返回翻译结果，不要添加任何解释或额外内容。

文本：
```
{text}
```

翻译结果："""

        system = f"你是一个专业翻译助手，精通多种语言。请准确翻译，保持原意。{formality_hint}"

        result = await router.call_model(
            capability=ModelCapability.TRANSLATION,
            prompt=prompt,
            system_prompt=system,
            temperature=0.3,
        )

        content = result.get("content", "").strip()
        if not content:
            raise RuntimeError("翻译返回空内容")

        return content

    def _build_prompt(self, text: str, target_lang: str,
                      source_lang: str, formality: str) -> str:
        """构建翻译提示词（fallback 用）"""
        target_lang_en = LANGUAGE_MAP.get(target_lang, target_lang)
        source_hint = f"从 {source_lang} " if source_lang != "auto" else ""
        formality_hint = ""
        if formality == "formal":
            formality_hint = "使用正式、礼貌的语气。"
        elif formality == "informal":
            formality_hint = "使用随意、口语化的语气。"

        return f"""请将以下文本{source_hint}翻译为 {target_lang_en}。
{formality_hint}

只返回翻译结果，不要添加任何解释或额外内容。

文本：
```
{text}
```

翻译结果："""
