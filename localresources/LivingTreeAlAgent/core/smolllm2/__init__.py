# -*- coding: utf-8 -*-
"""
SmolLM2-135M L0 快反大脑
======================

定位：轻量意图路由与快速响应
- 意图分类：cache / local / search / heavy / human
- 轻量任务：格式清洗、JSON 提取、简单对话
- 响应时间：<1s

Author: Hermes Desktop Team
"""

from .models import (
    RouteDecision,
    RouteType,
    IntentType,
    SmolLM2Config,
)
from .downloader import HuggingFaceDownloader, find_smallest_gguf
from .ollama_runner import OllamaRunner, OllamaRunnerManager
from .router import L0Router


__all__ = [
    # 模型
    "RouteDecision",
    "RouteType",
    "IntentType",
    "SmolLM2Config",
    # 下载器
    "HuggingFaceDownloader",
    "find_smallest_gguf",
    # Runner
    "OllamaRunner",
    "OllamaRunnerManager",
    # 路由
    "L0Router",
    "get_l0_router",
]


# 全局路由实例
_l0_router = None


def get_l0_router() -> L0Router:
    """获取全局 L0 路由实例"""
    global _l0_router
    if _l0_router is None:
        _l0_router = L0Router()
    return _l0_router


async def quick_route(prompt: str) -> RouteDecision:
    """
    快捷路由函数

    用法：
    >>> decision = await quick_route("帮我查下这个产品的库存")
    >>> print(decision.route)  # -> RouteType.LOCAL
    """
    router = get_l0_router()
    return await router.route(prompt)
