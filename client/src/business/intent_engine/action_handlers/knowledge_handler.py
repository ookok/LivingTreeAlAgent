# -*- coding: utf-8 -*-
"""
知识动作处理器 - KnowledgeQueryHandler, ConceptExplainerHandler
================================================================

处理知识问答相关意图的执行：
- 知识查询 (KNOWLEDGE_QUERY)
- 概念解释 (CONCEPT_EXPLANATION)
- 最佳实践 (BEST_PRACTICE) — 同时也注册在 CodeReviewHandler

v2.0: 使用共享 LLMClient（自动回退 requests→urllib），带重试和错误分类
from __future__ import annotations
"""


import time
import logging
from typing import Any, Dict, List, Optional

from ..intent_types import IntentType
from .base import (
    BaseActionHandler,
    ActionContext,
    ActionResult,
    ActionResultStatus,
    get_llm_client,
)
from .code_handler import call_llm

logger = logging.getLogger(__name__)


class KnowledgeQueryHandler(BaseActionHandler):
    """
    知识查询处理器

    覆盖意图：
    - KNOWLEDGE_QUERY
    - BEST_PRACTICE（部分）

    执行流程：
    1. 构建知识查询提示
    2. 调用 LLM（优先使用小模型，降低延迟）
    3. 格式化输出
    """

    @property
    def name(self) -> str:
        return "knowledge_query"

    @property
    def supported_intents(self) -> List[IntentType]:
        return [
            IntentType.KNOWLEDGE_QUERY,
            IntentType.BEST_PRACTICE,
        ]

    @property
    def priority(self) -> int:
        return 50

    def handle(self, ctx: ActionContext) -> ActionResult:
        """执行知识查询"""
        start = time.time()
        intent = ctx.intent

        prompt = f"""## 知识查询

问题: {intent.raw_input}
技术栈: {', '.join(intent.tech_stack) if intent.tech_stack else ''}

请准确回答此问题。如果涉及技术概念，请：
1. 先给出简洁的定义
2. 然后详细说明
3. 最后给出实际示例

使用中文回答，结构清晰。"""

        # 知识查询优先使用轻量模型
        knowledge_ctx = ActionContext(
            intent=intent,
            ollama_url=ctx.ollama_url,
            model_name="qwen3.5:4b",  # 轻量模型
            temperature=0.2,            # 低温度，更确定性
            timeout=60.0,               # 知识查询超时短
        )

        try:
            output = call_llm(knowledge_ctx, prompt, system="你是一个准确的技术知识助手。请用中文回答。")
        except RuntimeError as e:
            return self._make_error(f"知识查询失败: {e}")

        execution_time = time.time() - start

        result = self._make_result(
            output=output,
            output_type="text",
            suggestions=["需要更深入了解某个方面吗？"],
        )
        result.steps = [
            {"name": "知识检索", "detail": intent.target or intent.raw_input[:50], "duration": execution_time},
        ]
        result.execution_time = execution_time

        return result


class ConceptExplainerHandler(BaseActionHandler):
    """
    概念解释处理器

    覆盖意图：
    - CONCEPT_EXPLANATION

    与 KnowledgeQueryHandler 的区别：
    - KnowledgeQuery: 事实性查询（"Python GIL 是什么？"）
    - ConceptExplainer: 深度概念解释（"解释一下异步编程的原理"）
    """

    @property
    def name(self) -> str:
        return "concept_explainer"

    @property
    def supported_intents(self) -> List[IntentType]:
        return [
            IntentType.CONCEPT_EXPLANATION,
        ]

    @property
    def priority(self) -> int:
        return 60

    def handle(self, ctx: ActionContext) -> ActionResult:
        """执行概念解释"""
        start = time.time()
        intent = ctx.intent

        prompt = f"""## 概念解释

用户想了解: {intent.raw_input}
技术栈上下文: {', '.join(intent.tech_stack) if intent.tech_stack else ''}

请用深入浅出的方式解释这个概念：

### 一句话定义
（用最简洁的话概括）

### 详细解释
（分层次讲解核心原理）

### 实际示例
（用代码或场景说明）

### 常见误区
（人们容易犯的错误）

### 相关概念
（推荐进一步学习的内容）

使用中文回答，适合有一定技术背景的开发者阅读。"""

        try:
            output = call_llm(ctx, prompt, system="你是一个技术概念解释专家。请深入浅出地解释概念。")
        except RuntimeError as e:
            return self._make_error(f"概念解释失败: {e}")

        execution_time = time.time() - start

        result = self._make_result(
            output=output,
            output_type="text",
            suggestions=self._get_related_suggestions(intent),
        )
        result.steps = [
            {"name": "概念解释", "detail": intent.target or intent.raw_input[:50], "duration": execution_time},
        ]
        result.execution_time = execution_time

        return result

    def _get_related_suggestions(self, intent) -> List[str]:
        """获取相关概念建议"""
        base = intent.target or intent.raw_input
        return [
            f"想了解更多关于 {base} 的内容吗？",
            "需要实际的代码示例吗？",
        ]
