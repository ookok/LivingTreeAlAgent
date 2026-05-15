"""ProviderRegistry — Single source of truth for LLM provider registration.

Eliminates the triple-bootstrap problem where DualModelConsciousness,
TreeLLM.from_config(), and IntegrationHub each independently create providers
with different base URLs and default models.

All bootstrap paths call `register_all_providers(llm)` — the one and only
registration entry point.

Also handles tier fan-out: providers with multiple capability tiers
(flash/reasoning/pro/small) are registered as separate named providers
sharing the same API key, with tier-appropriate default models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from .core import TreeLLM


PROVIDER_BASE_URLS = {
    "deepseek": "https://api.deepseek.com/v1",
    "longcat": "https://api.longcat.chat/v1",
    "xiaomi": "https://api.xiaomimimo.com/v1",
    "aliyun": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "hunyuan": "https://api.hunyuan.cloud.tencent.com/v1",
    "baidu": "https://qianfan.baidubce.com/v2",
    "spark": "https://maas-api.cn-huabei-1.xf-yun.com/v2",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "mofang": "https://ai.gitee.com/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "modelscope": "https://api-inference.modelscope.cn/v1",
    "bailing": "https://api.baichuan.com/v1",
    "stepfun": "https://api.stepfun.com/v1",
    "internlm": "https://internlm-chat.intern-ai.org.cn/api/twlp/v1",
    "sensetime": "https://api.sensetime.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "dmxapi": "https://www.dmxapi.cn/v1",
}


def register_all_providers(llm: "TreeLLM") -> int:
    """Register all configured providers into the given TreeLLM instance.

    Reads API keys from config (which loads from encrypted vault).
    Handles both dedicated provider classes (DeepSeek, LongCat, etc.)
    and generic OpenAI-compatible providers.

    Also creates tier variants for multi-model platforms (siliconflow,
    mofang, nvidia) so all code paths see the same set of providers.

    Returns the number of providers registered.
    """
    try:
        from livingtree.config.settings import get_config
        config = get_config().model
    except Exception:
        return 0

    from .providers import (
        create_deepseek_provider, create_longcat_provider,
        create_nvidia_provider, create_modelscope_provider,
        create_bailing_provider, create_stepfun_provider,
        create_internlm_provider, create_sensetime_provider,
        create_openrouter_provider, OpenAILikeProvider,
    )

    count = 0

    # ═══ Tier-1: Dedicated provider classes ═══
    dedicated = [
        ("deepseek", lambda: create_deepseek_provider(config.deepseek_api_key)),
        ("longcat", lambda: create_longcat_provider(config.longcat_api_key)),
        ("nvidia", lambda: create_nvidia_provider(config.nvidia_api_key)),
        ("modelscope", lambda: create_modelscope_provider(config.modelscope_api_key)),
        ("bailing", lambda: create_bailing_provider(config.bailing_api_key)),
        ("stepfun", lambda: create_stepfun_provider(config.stepfun_api_key)),
        ("internlm", lambda: create_internlm_provider(config.internlm_api_key)),
        ("sensetime", lambda: create_sensetime_provider(config.sensetime_api_key)),
        ("openrouter", lambda: create_openrouter_provider(config.openrouter_api_key)),
    ]

    for name, factory in dedicated:
        key = getattr(config, f"{name}_api_key", "")
        if key:
            try:
                llm.add_provider(factory())
                count += 1
            except Exception as e:
                logger.debug(f"ProviderRegistry: {name} skipped ({e})")

    # ═══ Tier-2: Generic OpenAI-compatible providers ═══
    generic = [
        ("xiaomi", config.xiaomi_api_key, "https://api.xiaomimimo.com/v1", "mimo-v2-flash"),
        ("aliyun", config.aliyun_api_key, "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-turbo"),
        ("zhipu", config.zhipu_api_key, "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
        ("hunyuan", config.hunyuan_api_key, "https://api.hunyuan.cloud.tencent.com/v1", "hunyuan-lite"),
        ("baidu", config.baidu_api_key, "https://qianfan.baidubce.com/v2", "ernie-speed-128k"),
        ("spark", config.spark_api_key, "https://maas-api.cn-huabei-1.xf-yun.com/v2", "xdeepseekv3"),
        ("dmxapi", config.dmxapi_api_key, "https://www.dmxapi.cn/v1", "gpt-5-mini"),
    ]
    for name, key, url, model in generic:
        if key:
            try:
                llm.add_provider(OpenAILikeProvider(name=name, base_url=url, api_key=key, default_model=model))
                count += 1
            except Exception as e:
                logger.debug(f"ProviderRegistry: {name} skipped ({e})")

    # ═══ Tier-3: Multi-tier platforms (fan-out by capability) ═══
    _add_tier_variants(llm, config, count)

    logger.info(f"ProviderRegistry: registered {llm.provider_count} providers ({count} base + tier variants)")
    return count


def _add_tier_variants(llm: "TreeLLM", config, base_count: int) -> None:
    """Create flash/reasoning/pro/small tier variants for multi-model platforms.

    These platforms host multiple models behind a single API key. Each tier
    is registered as a separate named provider so the election system can
    select the right model for the task.
    """
    from .providers import OpenAILikeProvider

    # SiliconFlow: Qwen2.5 family across tiers
    if config.siliconflow_api_key:
        sf_key = config.siliconflow_api_key
        sf_url = config.siliconflow_base_url or "https://api.siliconflow.cn/v1"
        tiers = [
            ("siliconflow-flash", "Qwen/Qwen2.5-7B-Instruct"),
            ("siliconflow-reasoning", "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"),
            ("siliconflow-pro", "deepseek-ai/DeepSeek-V3"),
            ("siliconflow-small", "Qwen/Qwen2.5-1.5B-Instruct"),
        ]
        for name, model in tiers:
            llm.add_provider(OpenAILikeProvider(name=name, base_url=sf_url, api_key=sf_key, default_model=model))

    # MoFang: Qwen2.5 family
    if config.mofang_api_key:
        mf_key = config.mofang_api_key
        mf_url = config.mofang_base_url or "https://ai.gitee.com/v1"
        tiers = [
            ("mofang-flash", "Qwen/Qwen2.5-7B-Instruct"),
            ("mofang-reasoning", "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"),
            ("mofang-small", "Qwen/Qwen2.5-1.5B-Instruct"),
            ("mofang-pro", "deepseek-ai/DeepSeek-V3"),
        ]
        for name, model in tiers:
            llm.add_provider(OpenAILikeProvider(name=name, base_url=mf_url, api_key=mf_key, default_model=model))

    # NVIDIA NIM: diverse model family
    if config.nvidia_api_key:
        nv_key = config.nvidia_api_key
        nv_url = config.nvidia_base_url or "https://integrate.api.nvidia.com/v1"
        tiers = [
            ("nvidia-reasoning", "deepseek-ai/deepseek-r1"),
            ("nvidia-pro", "nvidia/llama-3.1-nemotron-ultra-253b-v1"),
            ("nvidia-flash", "meta/llama-3.3-70b-instruct"),
            ("nvidia-small", "microsoft/phi-3.5-mini-instruct"),
        ]
        for name, model in tiers:
            llm.add_provider(OpenAILikeProvider(name=name, base_url=nv_url, api_key=nv_key, default_model=model))
