# -*- coding: utf-8 -*-
"""
L0-L4 集成层
============

将 SmolLM2 L0 快反大脑与 L4 RelayFreeLLM 网关串联：

用户输入 → L0 Router (SmolLM2) → 路由决策
                                          ↓
    ┌─────────────────────────────────────┼─────────────────────────────────────┐
    ↓                                     ↓                                     ↓
 CACHE 返回                         LOCAL 快速执行                       需要大模型
 (直接返回)                         (格式化/JSON等)                      ↓
                                                                    L4 RelayFreeLLM
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from enum import Enum

from .models import RouteDecision, RouteType, IntentType, SmolLM2Config
from .router import L0Router
from .ollama_runner import get_runner_manager


class L0L4Config:
    """L0-L4 集成配置"""
    enable_l0: bool = True           # 是否启用 L0 路由
    enable_cache: bool = True        # 是否启用缓存
    enable_fast_local: bool = True   # 是否启用本地快速执行
    fast_intents: List[IntentType] = None  # 本地快速执行的意图

    def __init__(self):
        self.fast_intents = [
            IntentType.GREETING,
            IntentType.SIMPLE_QUESTION,
            IntentType.FORMAT_CLEAN,
            IntentType.JSON_EXTRACT,
            IntentType.QUICK_REPLY,
            IntentType.CODE_SIMPLE,
        ]


class L0L4IntegratedExecutor:
    """
    L0-L4 集成执行器

    在 L4 RelayFreeLLM 基础上增加 L0 前置路由层：
    1. L0 SmolLM2 快速意图分类
    2. 本地快速任务直接执行
    3. 缓存命中直接返回
    4. 复杂任务走 L4 RelayFreeLLM
    """

    def __init__(
        self,
        l0_config: Optional[L0L4Config] = None,
        l4_executor: Optional[Any] = None
    ):
        self.l0_config = l0_config or L0L4Config()
        self._l4_executor = l4_executor
        self._l0_router: Optional[L0Router] = None

        # 本地快速处理器
        self._fast_handlers: Dict[IntentType, Callable] = {}

        # 注册默认快速处理器
        self._register_default_handlers()

    def _register_default_handlers(self):
        """注册默认快速处理器"""

        async def handle_greeting(route: RouteDecision) -> Dict[str, Any]:
            """问候处理"""
            greetings = {
                "zh": ["你好！有什么我可以帮你的吗？", "您好！有什么问题可以问我。"],
                "en": ["Hello! How can I help you?", "Hi there!"],
            }
            return {
                "role": "assistant",
                "content": greetings["zh"][0],  # 默认中文
                "l0_decision": route.to_dict()
            }

        async def handle_simple_q(route: RouteDecision) -> Dict[str, Any]:
            """简单问答处理"""
            return {
                "role": "assistant",
                "content": "这个问题我帮你查一下...",
                "l0_decision": route.to_dict()
            }

        async def handle_format_clean(route: RouteDecision) -> Dict[str, Any]:
            """格式清洗处理"""
            return {
                "role": "assistant",
                "content": "好的，我来帮你整理格式。",
                "l0_decision": route.to_dict()
            }

        async def handle_json_extract(route: RouteDecision) -> Dict[str, Any]:
            """JSON 提取处理"""
            return {
                "role": "assistant",
                "content": "请提供需要提取的内容，我来帮你转为 JSON。",
                "l0_decision": route.to_dict()
            }

        self.register_handler(IntentType.GREETING, handle_greeting)
        self.register_handler(IntentType.SIMPLE_QUESTION, handle_simple_q)
        self.register_handler(IntentType.FORMAT_CLEAN, handle_format_clean)
        self.register_handler(IntentType.JSON_EXTRACT, handle_json_extract)

    def register_handler(self, intent: IntentType, handler: Callable):
        """注册快速处理器"""
        self._fast_handlers[intent] = handler

    async def _get_l0_router(self) -> L0Router:
        """获取 L0 路由实例"""
        if self._l0_router is None:
            self._l0_router = L0Router(
                enable_cache=self.l0_config.enable_cache
            )
        return self._l0_router

    async def _get_l4_executor(self) -> Any:
        """获取 L4 执行器"""
        if self._l4_executor is None:
            # 懒加载 L4 执行器
            try:
                from client.src.business.fusion_rag.l4_executor import L4RelayExecutor
                self._l4_executor = L4RelayExecutor()
            except ImportError:
                raise RuntimeError("L4 执行器不可用，请检查 fusion_rag 模块")
        return self._l4_executor

    async def execute(
        self,
        prompt: str,
        messages: Optional[List[Dict[str, Any]]] = None,
        enable_l0: bool = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        统一执行入口

        Args:
            prompt: 用户输入（用于 L0 路由）
            messages: 完整对话消息（用于 L4 执行）
            enable_l0: 是否启用 L0 路由（默认用配置）
            **kwargs: 传给 L4 的参数

        Returns:
            执行结果
        """
        enable_l0 = enable_l0 if enable_l0 is not None else self.l0_config.enable_l0

        # 如果禁用了 L0，直接走 L4
        if not enable_l0:
            executor = await self._get_l4_executor()
            return await executor.execute(messages or [{"role": "user", "content": prompt}], **kwargs)

        # L0 路由决策
        router = await self._get_l0_router()
        decision = await router.route(prompt)

        # 路由分发
        if decision.route == RouteType.CACHE:
            # 缓存命中，直接返回
            cached_response = router._cache.get(router._hash_prompt(prompt))
            if cached_response:
                return {
                    "role": "assistant",
                    "content": cached_response.response,
                    "l0_decision": decision.to_dict(),
                    "cache_hit": True
                }

        elif decision.route == RouteType.LOCAL:
            # 本地快速执行
            if self.l0_config.enable_fast_local:
                handler = self._fast_handlers.get(decision.intent)
                if handler:
                    result = await handler(decision)
                    # 缓存结果
                    router.cache_response(prompt, result["content"])
                    return result

        elif decision.route in (RouteType.HEAVY, RouteType.SEARCH):
            # 需要大模型，走 L4
            executor = await self._get_l4_executor()
            result = await executor.execute(
                messages or [{"role": "user", "content": prompt}],
                **kwargs
            )
            result["l0_decision"] = decision.to_dict()

            # 缓存结果
            router.cache_response(prompt, result.get("content", ""), source="cloud")

            return result

        elif decision.route == RouteType.HUMAN:
            # 转人工
            return {
                "role": "assistant",
                "content": "这个问题我帮你转接到人工客服，请稍候...",
                "l0_decision": decision.to_dict(),
                "escalate_to_human": True
            }

        # 兜底：走 L4
        executor = await self._get_l4_executor()
        result = await executor.execute(
            messages or [{"role": "user", "content": prompt}],
            **kwargs
        )
        result["l0_decision"] = decision.to_dict()
        return result

    async def route_only(self, prompt: str) -> RouteDecision:
        """
        仅做路由决策，不执行

        用于预览路由结果
        """
        router = await self._get_l0_router()
        return await router.route(prompt)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self._l0_router:
            return self._l0_router.get_stats()
        return {}


# ==================== 快捷函数 ====================

_l0l4_executor: Optional[L0L4IntegratedExecutor] = None


async def get_l0l4_executor() -> L0L4IntegratedExecutor:
    """获取全局 L0-L4 集成执行器"""
    global _l0l4_executor
    if _l0l4_executor is None:
        _l0l4_executor = L0L4IntegratedExecutor()
    return _l0l4_executor


async def smart_execute(
    prompt: str,
    messages: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    智能执行函数

    自动进行 L0 路由 + L4 执行

    用法：
    >>> result = await smart_execute("你好")
    >>> print(result["content"])
    你好！有什么我可以帮你的吗？
    """
    executor = await get_l0l4_executor()
    return await executor.execute(prompt, messages, **kwargs)


async def preview_route(prompt: str) -> RouteDecision:
    """
    预览路由决策

    用法：
    >>> decision = await preview_route("帮我查下这个产品的库存")
    >>> print(decision.route.value)  # -> "search"
    """
    executor = await get_l0l4_executor()
    return await executor.route_only(prompt)
