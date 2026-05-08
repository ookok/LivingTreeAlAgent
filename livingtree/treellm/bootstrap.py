"""TreeLLM Bootstrap — Initialize model registry with all configured providers.

Extracted from integration/hub.py to keep initialization logic modular.
Called once during system boot. All imports are lazy-safe.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from loguru import logger


async def setup_model_registry(config: Any, lazy: bool = False) -> Any | None:
    """Register all configured LLM providers with the model registry.

    Returns the ModelRegistry instance, or None if lazy boot.
    """
    if lazy:
        logger.info("Model registry deferred (lazy boot)")
        return None

    try:
        from .model_registry import get_model_registry
        registry = get_model_registry()

        # ── Qwen provider (千问 API — OpenAI compatible) ──
        qwen_key = getattr(config.model, 'aliyun_api_key', '')
        registry.register_provider(
            "qwen",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            qwen_key or "free-tier",
        )

        # ── All configured providers ──
        provider_keys = {
            "deepseek":    ("https://api.deepseek.com/v1", config.model.deepseek_api_key),
            "longcat":     ("https://api.longcat.chat/openai/v1", config.model.longcat_api_key),
            "xiaomi":      ("https://api.xiaomimimo.com/v1", config.model.xiaomi_api_key),
            "aliyun":      ("https://dashscope.aliyuncs.com/compatible-mode/v1", config.model.aliyun_api_key),
            "zhipu":       ("https://open.bigmodel.cn/api/paas/v4", config.model.zhipu_api_key),
            "siliconflow": ("https://api.siliconflow.cn/v1", config.model.siliconflow_api_key),
            "mofang":      ("https://ai.gitee.com/v1", config.model.mofang_api_key),
            "nvidia":      ("https://integrate.api.nvidia.com/v1", config.model.nvidia_api_key),
            "spark":       ("https://maas-api.cn-huabei-1.xf-yun.com/v2", config.model.spark_api_key),
            "modelscope":  ("https://api-inference.modelscope.cn/v1", config.model.modelscope_api_key),
            "bailing":     ("https://api.baichuan-ai.com/v1", config.model.bailing_api_key),
            "stepfun":     ("https://api.stepfun.com/v1", config.model.stepfun_api_key),
            "internlm":    ("https://api.intern-ai.org.cn/v1", config.model.internlm_api_key),
            "web2api":     ("http://localhost:5001/v1", "web2api-local"),
            "doubao":     ("https://ark.cn-beijing.volces.com/api/v3", config.model.doubao_api_key if hasattr(config.model, 'doubao_api_key') else os.environ.get("DOUBAO_API_KEY", "")),
        }

        registered = 0
        for name, (base_url, api_key) in provider_keys.items():
            if api_key:
                registry.register_provider(name, base_url, api_key)
                registered += 1

        # Load cached models and start periodic refresh
        registry.load_cache()
        asyncio.create_task(_refresh_models_async(registry))
        await registry.start_periodic_refresh(86400)

        logger.info(f"Model registry: {registered}/{len(provider_keys)} providers registered")
        return registry

    except Exception as e:
        logger.debug(f"Model registry bootstrap: {e}")
        return None


async def _refresh_models_async(registry: Any) -> None:
    """Background refresh all provider model lists."""
    try:
        await asyncio.sleep(5)  # Let UI boot first
        await registry.refresh_all()
    except Exception as e:
        logger.debug(f"Model refresh: {e}")
