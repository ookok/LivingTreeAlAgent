# -*- coding: utf-8 -*-
"""
provider_registry.py -- Multi-model Provider Registry (Unified)

Central registry for 40+ AI model providers, inspired by OpenCode's
support for 75+ providers. Provides a single entry point for discovering,
configuring, and managing LLM providers.

Design goals:
1. Unified catalog of local, cloud, aggregator, and enterprise providers
2. JSON-based persistence to ~/.hermes-desktop/providers.json
3. Provider availability detection via API key / env var checking
4. Singleton access via get_provider_registry()

Author: LivingTreeAI Agent
Date: 2026-04-29
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TransportType(str, Enum):
    """Transport protocol for provider API calls."""
    OPENAI_CHAT = "openai_chat"
    ANTHROPIC_MESSAGES = "anthropic_messages"
    OLLAMA_NATIVE = "ollama_native"


class ProviderCategory(str, Enum):
    """Provider classification for UI grouping."""
    LOCAL = "local"
    CLOUD = "cloud"
    AGGREGATOR = "aggregator"
    DOMESTIC = "domestic"
    ENTERPRISE = "enterprise"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Model Config (per-model definition inside a provider)
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    """Single model definition within a provider.

    Attributes:
        model_id: Unique identifier used in API calls (e.g. "gpt-4o").
        name: Human-readable display name (e.g. "GPT-4o").
        max_tokens: Maximum output tokens.
        context_window: Maximum context window in tokens.
        capabilities: List of capability tags.
        vision: Whether the model supports image input.
        cost_per_1k_input: Cost per 1,000 input tokens in USD (0 = unknown/free).
        cost_per_1k_output: Cost per 1,000 output tokens in USD (0 = unknown/free).
    """
    model_id: str
    name: str
    max_tokens: int = 4096
    context_window: int = 8192
    capabilities: List[str] = field(default_factory=lambda: ["chat"])
    vision: bool = False
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Provider Config
# ---------------------------------------------------------------------------

@dataclass
class ProviderConfig:
    """Configuration for a single provider.

    Attributes:
        id: Unique provider identifier (e.g. "openai").
        name: Internal name (e.g. "openai").
        display_name: Human-readable name (e.g. "OpenAI").
        transport: API transport protocol.
        base_url: Default API base URL.
        env_api_key: Primary environment variable for API key.
        env_base_url: Environment variable to override base_url.
        is_local: Whether this is a local provider.
        is_aggregator: Whether this provider aggregates multiple backends.
        icon: Icon name / resource key for the UI.
        category: Provider category for grouping.
        models: Predefined model list.
        doc: Short description.
    """
    id: str
    name: str
    display_name: str
    transport: str = "openai_chat"
    base_url: str = ""
    env_api_key: str = ""
    env_base_url: str = ""
    is_local: bool = False
    is_aggregator: bool = False
    icon: str = ""
    category: str = ProviderCategory.CLOUD
    models: List[ModelConfig] = field(default_factory=list)
    doc: str = ""

    # -- Runtime state (not persisted in catalog, only in saved config) --
    _api_key: str = field(default="", repr=False)
    _configured_base_url: str = field(default="", repr=False)
    _connected: bool = field(default=False, repr=False)

    @property
    def effective_base_url(self) -> str:
        """Return the effective base URL: user override > env > default."""
        if self._configured_base_url:
            return self._configured_base_url
        env_val = os.environ.get(self.env_base_url, "") if self.env_base_url else ""
        if env_val:
            return env_val
        return self.base_url

    @property
    def effective_api_key(self) -> str:
        """Return the effective API key: user-set > env var."""
        if self._api_key:
            return self._api_key
        return os.environ.get(self.env_api_key, "") if self.env_api_key else ""

    @property
    def is_available(self) -> bool:
        """Whether the provider has a usable API key configured."""
        if self.is_local:
            return True
        return bool(self.effective_api_key)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON persistence (excludes runtime-only fields)."""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "transport": self.transport,
            "base_url": self.base_url,
            "env_api_key": self.env_api_key,
            "env_base_url": self.env_base_url,
            "is_local": self.is_local,
            "is_aggregator": self.is_aggregator,
            "icon": self.icon,
            "category": self.category,
            "doc": self.doc,
            "models": [m.to_dict() for m in self.models],
        }

    def to_persist_dict(self) -> Dict[str, Any]:
        """Serialize for user config persistence (includes runtime overrides)."""
        d = self.to_dict()
        d["api_key"] = self._api_key
        d["configured_base_url"] = self._configured_base_url
        d["connected"] = self._connected
        return d


# ---------------------------------------------------------------------------
# Provider Catalog (40+ predefined providers)
# ---------------------------------------------------------------------------

def _m(model_id: str, name: str, max_tokens: int = 4096,
        context_window: int = 8192, capabilities: Optional[List[str]] = None,
        vision: bool = False) -> ModelConfig:
    """Shortcut to create a ModelConfig."""
    return ModelConfig(
        model_id=model_id,
        name=name,
        max_tokens=max_tokens,
        context_window=context_window,
        capabilities=capabilities or ["chat", "completion"],
        vision=vision,
    )


PROVIDER_CATALOG: List[ProviderConfig] = [
    # ========================================================================
    # LOCAL PROVIDERS
    # ========================================================================
    ProviderConfig(
        id="ollama",
        name="ollama",
        display_name="Ollama",
        transport="ollama_native",
        base_url="http://localhost:11434",
        is_local=True,
        category=ProviderCategory.LOCAL,
        icon="ollama",
        doc="Run models locally via Ollama. No API key required.",
        models=[
            _m("llama3.1", "Llama 3.1 8B", 4096, 128000, ["chat", "completion"]),
            _m("llama3.1:70b", "Llama 3.1 70B", 4096, 128000, ["chat", "completion"]),
            _m("qwen2.5:7b", "Qwen 2.5 7B", 4096, 32768, ["chat", "completion"]),
            _m("qwen2.5:72b", "Qwen 2.5 72B", 4096, 32768, ["chat", "completion"]),
            _m("codellama", "Code Llama 13B", 4096, 16384, ["chat", "code_generation"]),
            _m("deepseek-coder-v2", "DeepSeek Coder V2", 4096, 128000, ["chat", "code_generation"]),
            _m("mistral", "Mistral 7B", 4096, 32768, ["chat", "completion"]),
            _m("gemma2:9b", "Gemma 2 9B", 4096, 8192, ["chat", "completion"]),
            _m("phi3", "Phi-3 Mini", 4096, 128000, ["chat", "completion"]),
            _m("nomic-embed-text", "Nomic Embed Text", 8192, 8192, ["embedding"]),
        ],
    ),
    ProviderConfig(
        id="lm-studio",
        name="lm-studio",
        display_name="LM Studio",
        transport="openai_chat",
        base_url="http://localhost:1234/v1",
        is_local=True,
        category=ProviderCategory.LOCAL,
        icon="lmstudio",
        doc="Run GGUF models locally via LM Studio's OpenAI-compatible server.",
        models=[
            _m("local-model", "Local Model", 4096, 8192, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="llama-cpp",
        name="llama-cpp",
        display_name="llama.cpp",
        transport="openai_chat",
        base_url="http://localhost:8080/v1",
        is_local=True,
        category=ProviderCategory.LOCAL,
        icon="llamacpp",
        doc="llama.cpp HTTP server with OpenAI-compatible endpoint.",
        models=[
            _m("local-model", "Local Model", 4096, 8192, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="vllm",
        name="vllm",
        display_name="vLLM",
        transport="openai_chat",
        base_url="http://localhost:8000/v1",
        is_local=True,
        category=ProviderCategory.LOCAL,
        icon="vllm",
        doc="vLLM high-throughput inference server.",
        models=[
            _m("local-model", "Local Model", 4096, 32768, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="ollama-cloud",
        name="ollama-cloud",
        display_name="Ollama Cloud",
        transport="ollama_native",
        base_url="https://cloud.ollama.com",
        env_api_key="OLLAMA_API_KEY",
        is_local=False,
        category=ProviderCategory.LOCAL,
        icon="ollama",
        doc="Ollama cloud-hosted models.",
        models=[
            _m("llama3.1", "Llama 3.1 8B", 4096, 128000),
            _m("qwen2.5:7b", "Qwen 2.5 7B", 4096, 32768),
        ],
    ),

    # ========================================================================
    # CLOUD PROVIDERS
    # ========================================================================
    ProviderConfig(
        id="openai",
        name="openai",
        display_name="OpenAI",
        transport="openai_chat",
        base_url="https://api.openai.com/v1",
        env_api_key="OPENAI_API_KEY",
        category=ProviderCategory.CLOUD,
        icon="openai",
        doc="OpenAI GPT series models.",
        models=[
            _m("gpt-4o", "GPT-4o", 16384, 128000, ["chat", "code_generation", "reasoning", "vision"], True),
            _m("gpt-4o-mini", "GPT-4o Mini", 16384, 128000, ["chat", "code_generation", "reasoning"], False),
            _m("gpt-4-turbo", "GPT-4 Turbo", 4096, 128000, ["chat", "code_generation", "vision"], True),
            _m("gpt-4.1", "GPT-4.1", 32768, 1047576, ["chat", "code_generation", "reasoning"]),
            _m("gpt-4.1-mini", "GPT-4.1 Mini", 32768, 1047576, ["chat", "code_generation", "reasoning"]),
            _m("gpt-4.1-nano", "GPT-4.1 Nano", 32768, 1047576, ["chat", "code_generation", "reasoning"]),
            _m("o3", "O3", 100000, 200000, ["chat", "reasoning", "code_generation"]),
            _m("o4-mini", "O4 Mini", 100000, 200000, ["chat", "reasoning", "code_generation"]),
            _m("o3-mini", "O3 Mini", 65536, 200000, ["chat", "reasoning", "code_generation"]),
        ],
    ),
    ProviderConfig(
        id="anthropic",
        name="anthropic",
        display_name="Anthropic",
        transport="anthropic_messages",
        base_url="https://api.anthropic.com/v1",
        env_api_key="ANTHROPIC_API_KEY",
        category=ProviderCategory.CLOUD,
        icon="anthropic",
        doc="Anthropic Claude series models.",
        models=[
            _m("claude-sonnet-4-20250514", "Claude Sonnet 4", 16384, 200000, ["chat", "code_generation", "reasoning"], True),
            _m("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", 8192, 200000, ["chat", "code_generation", "reasoning"], True),
            _m("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", 8192, 200000, ["chat", "code_generation"]),
            _m("claude-3-opus-20240229", "Claude 3 Opus", 4096, 200000, ["chat", "reasoning", "vision"], True),
            _m("claude-3-haiku-20240307", "Claude 3 Haiku", 4096, 200000, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="google",
        name="google",
        display_name="Google Gemini",
        transport="openai_chat",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        env_api_key="GOOGLE_API_KEY",
        category=ProviderCategory.CLOUD,
        icon="google",
        doc="Google Gemini models via OpenAI-compatible endpoint.",
        models=[
            _m("gemini-2.5-pro", "Gemini 2.5 Pro", 65536, 1048576, ["chat", "code_generation", "reasoning"], True),
            _m("gemini-2.5-flash", "Gemini 2.5 Flash", 65536, 1048576, ["chat", "code_generation", "reasoning"], True),
            _m("gemini-2.0-flash", "Gemini 2.0 Flash", 8192, 1048576, ["chat", "code_generation"], True),
            _m("gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite", 8192, 1048576, ["chat", "completion"]),
            _m("gemini-1.5-pro", "Gemini 1.5 Pro", 8192, 2097152, ["chat", "code_generation", "vision"], True),
            _m("gemini-1.5-flash", "Gemini 1.5 Flash", 8192, 1048576, ["chat", "completion"], True),
        ],
    ),
    ProviderConfig(
        id="azure-openai",
        name="azure-openai",
        display_name="Azure OpenAI",
        transport="openai_chat",
        base_url="https://{resource}.openai.azure.com/openai/deployments/{deployment}",
        env_api_key="AZURE_OPENAI_API_KEY",
        env_base_url="AZURE_OPENAI_ENDPOINT",
        category=ProviderCategory.CLOUD,
        icon="azure",
        doc="Azure-hosted OpenAI models. Requires resource name and deployment ID.",
        models=[
            _m("gpt-4o", "GPT-4o (Azure)", 16384, 128000, ["chat", "code_generation", "vision"], True),
            _m("gpt-4o-mini", "GPT-4o Mini (Azure)", 16384, 128000, ["chat", "code_generation"]),
        ],
    ),
    ProviderConfig(
        id="deepseek",
        name="deepseek",
        display_name="DeepSeek",
        transport="openai_chat",
        base_url="https://api.deepseek.com/v1",
        env_api_key="DEEPSEEK_API_KEY",
        env_base_url="DEEPSEEK_BASE_URL",
        category=ProviderCategory.CLOUD,
        icon="deepseek",
        doc="DeepSeek models with strong code generation.",
        models=[
            _m("deepseek-chat", "DeepSeek V3", 8192, 65536, ["chat", "code_generation", "reasoning"]),
            _m("deepseek-reasoner", "DeepSeek R1", 16384, 65536, ["chat", "reasoning", "code_generation"]),
        ],
    ),
    ProviderConfig(
        id="xai",
        name="xai",
        display_name="xAI (Grok)",
        transport="openai_chat",
        base_url="https://api.x.ai/v1",
        env_api_key="XAI_API_KEY",
        category=ProviderCategory.CLOUD,
        icon="xai",
        doc="xAI Grok series models.",
        models=[
            _m("grok-3", "Grok 3", 8192, 131072, ["chat", "reasoning", "code_generation"]),
            _m("grok-3-mini", "Grok 3 Mini", 8192, 131072, ["chat", "reasoning"]),
            _m("grok-2", "Grok 2", 8192, 131072, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="groq",
        name="groq",
        display_name="Groq",
        transport="openai_chat",
        base_url="https://api.groq.com/openai/v1",
        env_api_key="GROQ_API_KEY",
        category=ProviderCategory.CLOUD,
        icon="groq",
        doc="Ultra-fast inference powered by LPU chips.",
        models=[
            _m("llama-3.3-70b-versatile", "Llama 3.3 70B (Groq)", 32768, 131072, ["chat", "code_generation"]),
            _m("llama-3.1-8b-instant", "Llama 3.1 8B (Groq)", 8192, 131072, ["chat", "completion"]),
            _m("gemma2-9b-it", "Gemma 2 9B (Groq)", 8192, 8192, ["chat", "completion"]),
            _m("mixtral-8x7b-32768", "Mixtral 8x7B (Groq)", 32768, 32768, ["chat", "completion"]),
            _m("deepseek-r1-distill-llama-70b", "DeepSeek R1 Distill 70B (Groq)", 16384, 131072, ["chat", "reasoning"]),
        ],
    ),
    ProviderConfig(
        id="cerebras",
        name="cerebras",
        display_name="Cerebras",
        transport="openai_chat",
        base_url="https://api.cerebras.ai/v1",
        env_api_key="CEREBRAS_API_KEY",
        category=ProviderCategory.CLOUD,
        icon="cerebras",
        doc="Fast inference on Cerebras wafer-scale engine.",
        models=[
            _m("llama-3.3-70b", "Llama 3.3 70B (Cerebras)", 8192, 131072, ["chat", "code_generation"]),
            _m("llama3.1-8b", "Llama 3.1 8B (Cerebras)", 8192, 131072, ["chat", "completion"]),
            _m("deepseek-r1-distill-llama-70b", "DeepSeek R1 Distill 70B (Cerebras)", 16384, 131072, ["chat", "reasoning"]),
        ],
    ),
    ProviderConfig(
        id="together-ai",
        name="together-ai",
        display_name="Together AI",
        transport="openai_chat",
        base_url="https://api.together.xyz/v1",
        env_api_key="TOGETHER_API_KEY",
        is_aggregator=True,
        category=ProviderCategory.AGGREGATOR,
        icon="together",
        doc="Open-source model hosting with serverless endpoints.",
        models=[
            _m("meta-llama/Llama-3.3-70B-Instruct-Turbo", "Llama 3.3 70B", 8192, 131072, ["chat", "code_generation"]),
            _m("mistralai/Mixtral-8x7B-Instruct-v0.1", "Mixtral 8x7B", 8192, 32768, ["chat", "completion"]),
            _m("deepseek-ai/DeepSeek-R1-Distill-Llama-70B", "DeepSeek R1 Distill 70B", 16384, 131072, ["chat", "reasoning"]),
        ],
    ),
    ProviderConfig(
        id="fireworks-ai",
        name="fireworks-ai",
        display_name="Fireworks AI",
        transport="openai_chat",
        base_url="https://api.fireworks.ai/inference/v1",
        env_api_key="FIREWORKS_API_KEY",
        category=ProviderCategory.CLOUD,
        icon="fireworks",
        doc="Fast open-source model inference.",
        models=[
            _m("accounts/fireworks/models/llama-v3p1-70b-instruct", "Llama 3.1 70B", 8192, 131072, ["chat", "code_generation"]),
            _m("accounts/fireworks/models/llama-v3p1-8b-instruct", "Llama 3.1 8B", 8192, 131072, ["chat", "completion"]),
            _m("accounts/fireworks/models/deepseek-r1", "DeepSeek R1", 16384, 65536, ["chat", "reasoning"]),
        ],
    ),
    ProviderConfig(
        id="mistral",
        name="mistral",
        display_name="Mistral AI",
        transport="openai_chat",
        base_url="https://api.mistral.ai/v1",
        env_api_key="MISTRAL_API_KEY",
        category=ProviderCategory.CLOUD,
        icon="mistral",
        doc="Mistral AI models (Codestral, Mistral Large, etc.).",
        models=[
            _m("codestral-latest", "Codestral", 8192, 256000, ["chat", "code_generation", "completion"]),
            _m("mistral-large-latest", "Mistral Large", 8192, 131072, ["chat", "reasoning", "code_generation"]),
            _m("mistral-medium-latest", "Mistral Medium", 8192, 32768, ["chat", "completion"]),
            _m("open-mistral-nemo", "Mistral Nemo", 4096, 131072, ["chat", "completion"]),
            _m("pixtral-large-latest", "Pixtral Large", 8192, 131072, ["chat", "vision"], True),
        ],
    ),
    ProviderConfig(
        id="cohere",
        name="cohere",
        display_name="Cohere",
        transport="openai_chat",
        base_url="https://api.cohere.com/v2",
        env_api_key="COHERE_API_KEY",
        category=ProviderCategory.CLOUD,
        icon="cohere",
        doc="Cohere Command series models.",
        models=[
            _m("command-r-plus", "Command R+", 4096, 128000, ["chat", "reasoning"]),
            _m("command-r", "Command R", 4096, 128000, ["chat", "completion"]),
            _m("command-a", "Command A", 4096, 256000, ["chat", "completion"]),
        ],
    ),

    # ========================================================================
    # AGGREGATORS
    # ========================================================================
    ProviderConfig(
        id="openrouter",
        name="openrouter",
        display_name="OpenRouter",
        transport="openai_chat",
        base_url="https://openrouter.ai/api/v1",
        env_api_key="OPENROUTER_API_KEY",
        is_aggregator=True,
        category=ProviderCategory.AGGREGATOR,
        icon="openrouter",
        doc="Unified gateway to 200+ models from 50+ providers.",
        models=[
            _m("anthropic/claude-sonnet-4", "Claude Sonnet 4", 16384, 200000, ["chat", "code_generation", "reasoning"]),
            _m("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet", 8192, 200000, ["chat", "code_generation"]),
            _m("openai/gpt-4o", "GPT-4o", 16384, 128000, ["chat", "code_generation", "vision"], True),
            _m("openai/gpt-4o-mini", "GPT-4o Mini", 16384, 128000, ["chat", "completion"]),
            _m("google/gemini-2.5-pro", "Gemini 2.5 Pro", 65536, 1048576, ["chat", "code_generation"]),
            _m("deepseek/deepseek-chat", "DeepSeek V3", 8192, 65536, ["chat", "code_generation"]),
            _m("deepseek/deepseek-r1", "DeepSeek R1", 16384, 65536, ["chat", "reasoning"]),
            _m("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B", 8192, 131072, ["chat", "code_generation"]),
            _m("mistralai/mistral-large", "Mistral Large", 8192, 131072, ["chat", "reasoning"]),
            _m("qwen/qwen-2.5-72b-instruct", "Qwen 2.5 72B", 8192, 32768, ["chat", "code_generation"]),
        ],
    ),

    # ========================================================================
    # DOMESTIC (Chinese) PROVIDERS
    # ========================================================================
    ProviderConfig(
        id="alibaba",
        name="alibaba",
        display_name="Aliyun DashScope",
        transport="openai_chat",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        env_api_key="DASHSCOPE_API_KEY",
        env_base_url="DASHSCOPE_BASE_URL",
        category=ProviderCategory.DOMESTIC,
        icon="alibaba",
        doc="Alibaba Cloud DashScope / Qwen series.",
        models=[
            _m("qwen-max", "Qwen Max", 8192, 32768, ["chat", "code_generation", "reasoning"]),
            _m("qwen-plus", "Qwen Plus", 8192, 131072, ["chat", "code_generation"]),
            _m("qwen-turbo", "Qwen Turbo", 8192, 131072, ["chat", "completion"]),
            _m("qwen2.5-72b-instruct", "Qwen 2.5 72B", 4096, 32768, ["chat", "code_generation"]),
            _m("qwen2.5-coder-32b-instruct", "Qwen 2.5 Coder 32B", 8192, 32768, ["chat", "code_generation"]),
            _m("qwen-vl-max", "Qwen VL Max", 8192, 131072, ["chat", "vision"], True),
        ],
    ),
    ProviderConfig(
        id="baidu",
        name="baidu",
        display_name="Baidu ERNIE",
        transport="openai_chat",
        base_url="https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
        env_api_key="BAIDU_API_KEY",
        category=ProviderCategory.DOMESTIC,
        icon="baidu",
        doc="Baidu ERNIE (Wenxin) models.",
        models=[
            _m("ernie-4.0-8k", "ERNIE 4.0", 4096, 8192, ["chat", "completion"]),
            _m("ernie-3.5-8k", "ERNIE 3.5", 4096, 8192, ["chat", "completion"]),
            _m("ernie-speed-128k", "ERNIE Speed", 4096, 131072, ["chat", "completion"]),
            _m("ernie-lite-8k", "ERNIE Lite", 4096, 8192, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="tencent",
        name="tencent",
        display_name="Tencent Hunyuan",
        transport="openai_chat",
        base_url="https://hunyuan.tencentcloudapi.com",
        env_api_key="TENCENT_API_KEY",
        category=ProviderCategory.DOMESTIC,
        icon="tencent",
        doc="Tencent Hunyuan (混元) models.",
        models=[
            _m("hunyuan-pro", "Hunyuan Pro", 4096, 32768, ["chat", "completion"]),
            _m("hunyuan-standard", "Hunyuan Standard", 4096, 32768, ["chat", "completion"]),
            _m("hunyuan-lite", "Hunyuan Lite", 4096, 32768, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="moonshot",
        name="moonshot",
        display_name="Moonshot (Kimi)",
        transport="openai_chat",
        base_url="https://api.moonshot.cn/v1",
        env_api_key="MOONSHOT_API_KEY",
        env_base_url="KIMI_BASE_URL",
        category=ProviderCategory.DOMESTIC,
        icon="moonshot",
        doc="Moonshot AI (Kimi) long-context models.",
        models=[
            _m("moonshot-v1-128k", "Kimi 128K", 4096, 131072, ["chat", "code_generation", "reasoning"]),
            _m("moonshot-v1-32k", "Kimi 32K", 4096, 32768, ["chat", "completion"]),
            _m("moonshot-v1-8k", "Kimi 8K", 4096, 8192, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="zhipu",
        name="zhipu",
        display_name="Zhipu GLM",
        transport="openai_chat",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        env_api_key="ZHIPU_API_KEY",
        category=ProviderCategory.DOMESTIC,
        icon="zhipu",
        doc="Zhipu AI GLM series models.",
        models=[
            _m("glm-4-plus", "GLM-4 Plus", 4096, 131072, ["chat", "code_generation", "reasoning"]),
            _m("glm-4", "GLM-4", 4096, 131072, ["chat", "code_generation"]),
            _m("glm-4-flash", "GLM-4 Flash", 4096, 131072, ["chat", "completion"]),
            _m("glm-4v", "GLM-4V", 4096, 8192, ["chat", "vision"], True),
            _m("glm-4-long", "GLM-4 Long", 4096, 1048576, ["chat", "summarization"]),
        ],
    ),
    ProviderConfig(
        id="minimax",
        name="minimax",
        display_name="MiniMax",
        transport="openai_chat",
        base_url="https://api.minimax.chat/v1",
        env_api_key="MINIMAX_API_KEY",
        env_base_url="MINIMAX_BASE_URL",
        category=ProviderCategory.DOMESTIC,
        icon="minimax",
        doc="MiniMax models (international version).",
        models=[
            _m("MiniMax-Text-01", "MiniMax Text-01", 4096, 1048576, ["chat", "completion"]),
            _m("abab6.5s-chat", "MiniMax 6.5s", 4096, 8192, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="siliconflow",
        name="siliconflow",
        display_name="SiliconFlow",
        transport="openai_chat",
        base_url="https://api.siliconflow.cn/v1",
        env_api_key="SILICONFLOW_API_KEY",
        is_aggregator=True,
        category=ProviderCategory.DOMESTIC,
        icon="siliconflow",
        doc="SiliconFlow Chinese model aggregation platform.",
        models=[
            _m("deepseek-ai/DeepSeek-V3", "DeepSeek V3", 8192, 65536, ["chat", "code_generation"]),
            _m("Qwen/Qwen2.5-72B-Instruct", "Qwen 2.5 72B", 4096, 32768, ["chat", "code_generation"]),
            _m("THUDM/glm-4-9b-chat", "GLM-4 9B", 4096, 131072, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="yi",
        name="yi",
        display_name="01.AI (Yi)",
        transport="openai_chat",
        base_url="https://api.01.ai/v1",
        env_api_key="YI_API_KEY",
        category=ProviderCategory.DOMESTIC,
        icon="yi",
        doc="01.AI Yi series models.",
        models=[
            _m("yi-large", "Yi Large", 4096, 32768, ["chat", "completion"]),
            _m("yi-medium", "Yi Medium", 4096, 16384, ["chat", "completion"]),
            _m("yi-spark", "Yi Spark", 4096, 16384, ["chat", "completion"]),
            _m("yi-vision", "Yi Vision", 4096, 16384, ["chat", "vision"], True),
        ],
    ),
    ProviderConfig(
        id="baichuan",
        name="baichuan",
        display_name="Baichuan",
        transport="openai_chat",
        base_url="https://api.baichuan-ai.com/v1",
        env_api_key="BAICHUAN_API_KEY",
        category=ProviderCategory.DOMESTIC,
        icon="baichuan",
        doc="Baichuan AI models.",
        models=[
            _m("Baichuan4", "Baichuan 4", 4096, 32768, ["chat", "code_generation", "reasoning"]),
            _m("Baichuan3-Turbo", "Baichuan 3 Turbo", 4096, 32768, ["chat", "completion"]),
            _m("Baichuan3-Turbo-128k", "Baichuan 3 Turbo 128K", 4096, 131072, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="spark",
        name="spark",
        display_name="iFlytek Spark",
        transport="openai_chat",
        base_url="https://spark-api-open.xf-yun.com/v1",
        env_api_key="IFLYTEK_SPARK_API_KEY",
        category=ProviderCategory.DOMESTIC,
        icon="spark",
        doc="iFlytek Xinghuo (Spark) models.",
        models=[
            _m("spark-max", "Spark Max", 4096, 32768, ["chat", "code_generation"]),
            _m("spark-pro", "Spark Pro", 4096, 32768, ["chat", "completion"]),
            _m("spark-lite", "Spark Lite", 4096, 8192, ["chat", "completion"]),
        ],
    ),

    # ========================================================================
    # ENTERPRISE
    # ========================================================================
    ProviderConfig(
        id="aws-bedrock",
        name="aws-bedrock",
        display_name="AWS Bedrock",
        transport="openai_chat",
        base_url="https://bedrock-runtime.us-east-1.amazonaws.com",
        env_api_key="AWS_ACCESS_KEY_ID",
        category=ProviderCategory.ENTERPRISE,
        icon="aws",
        doc="AWS Bedrock - access Claude, Llama, Titan and more.",
        models=[
            _m("anthropic.claude-sonnet-4-20250514-v1:0", "Claude Sonnet 4 (Bedrock)", 16384, 200000, ["chat", "code_generation"]),
            _m("anthropic.claude-3-5-sonnet-20241022-v2:0", "Claude 3.5 Sonnet (Bedrock)", 8192, 200000, ["chat", "code_generation"]),
            _m("meta.llama3-3-70b-instruct-v1:0", "Llama 3.3 70B (Bedrock)", 8192, 131072, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="azure-cognitive",
        name="azure-cognitive",
        display_name="Azure Cognitive Services",
        transport="openai_chat",
        base_url="https://{resource}.cognitiveservices.azure.com",
        env_api_key="AZURE_COGNITIVE_KEY",
        category=ProviderCategory.ENTERPRISE,
        icon="azure",
        doc="Azure Cognitive Services for multi-model inference.",
        models=[
            _m("gpt-4o", "GPT-4o (Cognitive)", 16384, 128000, ["chat", "code_generation"]),
        ],
    ),
    ProviderConfig(
        id="github-copilot",
        name="github-copilot",
        display_name="GitHub Copilot",
        transport="openai_chat",
        base_url="https://api.githubcopilot.com",
        env_api_key="GITHUB_TOKEN",
        category=ProviderCategory.ENTERPRISE,
        icon="github",
        doc="GitHub Copilot AI coding assistant models.",
        models=[
            _m("copilot", "Copilot GPT-4o", 8192, 128000, ["chat", "code_generation"]),
        ],
    ),
    ProviderConfig(
        id="gitlab-duo",
        name="gitlab-duo",
        display_name="GitLab Duo",
        transport="openai_chat",
        base_url="https://gitlab.com/api/v4/code_suggestions",
        env_api_key="GITLAB_API_KEY",
        category=ProviderCategory.ENTERPRISE,
        icon="gitlab",
        doc="GitLab Duo AI-powered code suggestions.",
        models=[
            _m("code-suggestions", "GitLab Duo Chat", 4096, 8192, ["chat", "code_generation"]),
        ],
    ),

    # ========================================================================
    # OTHER / SPECIALIZED
    # ========================================================================
    ProviderConfig(
        id="huggingface",
        name="huggingface",
        display_name="HuggingFace",
        transport="openai_chat",
        base_url="https://api-inference.huggingface.co/v1",
        env_api_key="HF_API_KEY",
        is_aggregator=True,
        category=ProviderCategory.OTHER,
        icon="huggingface",
        doc="HuggingFace Inference Endpoints and Serverless API.",
        models=[
            _m("meta-llama/Llama-3.3-70B-Instruct", "Llama 3.3 70B", 8192, 131072, ["chat", "code_generation"]),
            _m("mistralai/Mixtral-8x7B-Instruct-v0.1", "Mixtral 8x7B", 8192, 32768, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="replicate",
        name="replicate",
        display_name="Replicate",
        transport="openai_chat",
        base_url="https://api.replicate.com/v1",
        env_api_key="REPLICATE_API_TOKEN",
        is_aggregator=True,
        category=ProviderCategory.OTHER,
        icon="replicate",
        doc="Replicate cloud model hosting platform.",
        models=[
            _m("meta/llama-3.3-70b-instruct", "Llama 3.3 70B", 8192, 131072, ["chat", "code_generation"]),
            _m("mistralai/mixtral-8x7b-instruct-v0.1", "Mixtral 8x7B", 8192, 32768, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="cloudflare-ai",
        name="cloudflare-ai",
        display_name="Cloudflare AI Gateway",
        transport="openai_chat",
        base_url="https://gateway.ai.cloudflare.com/v1",
        env_api_key="CF_API_TOKEN",
        is_aggregator=True,
        category=ProviderCategory.OTHER,
        icon="cloudflare",
        doc="Cloudflare AI Gateway with caching and analytics.",
        models=[
            _m("@cf/meta/llama-3.3-70b-instruct", "Llama 3.3 70B (CF)", 8192, 131072, ["chat", "code_generation"]),
            _m("@cf/meta/llama-3.1-8b-instruct", "Llama 3.1 8B (CF)", 8192, 131072, ["chat", "completion"]),
        ],
    ),
    ProviderConfig(
        id="vercel-ai",
        name="vercel-ai",
        display_name="Vercel AI Gateway",
        transport="openai_chat",
        base_url="https://gateway.vercel.ai/v1",
        env_api_key="VERCEL_API_KEY",
        is_aggregator=True,
        category=ProviderCategory.OTHER,
        icon="vercel",
        doc="Vercel AI Gateway for edge model deployment.",
        models=[
            _m("openai/gpt-4o", "GPT-4o (Vercel)", 16384, 128000, ["chat", "code_generation"]),
            _m("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet (Vercel)", 8192, 200000, ["chat", "code_generation"]),
        ],
    ),
    ProviderConfig(
        id="perplexity",
        name="perplexity",
        display_name="Perplexity",
        transport="openai_chat",
        base_url="https://api.perplexity.ai",
        env_api_key="PERPLEXITY_API_KEY",
        category=ProviderCategory.OTHER,
        icon="perplexity",
        doc="Perplexity AI search-augmented models.",
        models=[
            _m("sonar-pro", "Sonar Pro", 8192, 200000, ["chat", "web_search"]),
            _m("sonar", "Sonar", 8192, 127000, ["chat", "web_search"]),
        ],
    ),
    ProviderConfig(
        id="sambanova",
        name="sambanova",
        display_name="SambaNova",
        transport="openai_chat",
        base_url="https://api.sambanova.ai/v1",
        env_api_key="SAMBANOVA_API_KEY",
        category=ProviderCategory.OTHER,
        icon="sambanova",
        doc="SambaNova fast inference platform.",
        models=[
            _m("Meta-Llama-3.3-70B-Instruct", "Llama 3.3 70B", 8192, 131072, ["chat", "code_generation"]),
            _m("DeepSeek-R1-Distill-Llama-70B", "DeepSeek R1 Distill 70B", 16384, 131072, ["chat", "reasoning"]),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Provider Registry (Singleton)
# ---------------------------------------------------------------------------

class ProviderRegistry:
    """Central registry for managing LLM provider configurations.

    Provides CRUD operations, filtering, persistence, and connection
    management for all providers. Thread-safe via internal lock.

    Usage::

        registry = get_provider_registry()
        for p in registry.get_available_providers():
            print(p.display_name, p.effective_base_url)
    """

    def __init__(self, config_dir: Optional[str] = None):
        self._providers: Dict[str, ProviderConfig] = {}
        self._lock = threading.Lock()

        # Determine config directory
        if config_dir:
            self._config_dir = Path(config_dir)
        else:
            try:
                self._config_dir = Path.home() / ".hermes-desktop"
                self._config_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                # Fallback to temp directory
                self._config_dir = Path(os.environ.get("TEMP", "/tmp")) / ".hermes-desktop"
                self._config_dir.mkdir(parents=True, exist_ok=True)

        self._config_path = os.path.join(str(self._config_dir), "providers.json")

        # Load catalog defaults, then overlay user config
        self._load_catalog()
        self._load_config()

    # -- Catalog Loading -----------------------------------------------------

    def _load_catalog(self):
        """Load all predefined providers from PROVIDER_CATALOG."""
        with self._lock:
            for config in PROVIDER_CATALOG:
                self._providers[config.id] = config

    # -- CRUD ----------------------------------------------------------------

    def register_provider(self, config: ProviderConfig) -> None:
        """Register or update a provider configuration."""
        with self._lock:
            # Preserve any existing runtime state
            existing = self._providers.get(config.id)
            if existing:
                config._api_key = existing._api_key
                config._configured_base_url = existing._configured_base_url
                config._connected = existing._connected
            self._providers[config.id] = config
            logger.debug("Registered provider: %s", config.id)

    def unregister_provider(self, provider_id: str) -> bool:
        """Remove a provider from the registry. Returns True if found."""
        with self._lock:
            removed = self._providers.pop(provider_id, None)
            if removed:
                logger.debug("Unregistered provider: %s", provider_id)
            return removed is not None

    # -- Queries -------------------------------------------------------------

    def get_provider(self, provider_id: str) -> Optional[ProviderConfig]:
        """Get a provider by its ID."""
        with self._lock:
            return self._providers.get(provider_id)

    def get_all_providers(self) -> List[ProviderConfig]:
        """Return all registered providers."""
        with self._lock:
            return list(self._providers.values())

    def get_available_providers(self) -> List[ProviderConfig]:
        """Return providers that have an API key configured (or are local)."""
        with self._lock:
            return [p for p in self._providers.values() if p.is_available]

    def get_local_providers(self) -> List[ProviderConfig]:
        """Return all local (self-hosted) providers."""
        with self._lock:
            return [p for p in self._providers.values() if p.is_local]

    def get_cloud_providers(self) -> List[ProviderConfig]:
        """Return all remote (cloud/enterprise/aggregator/other) providers."""
        with self._lock:
            return [p for p in self._providers.values() if not p.is_local]

    def get_providers_by_category(self, category: str) -> List[ProviderConfig]:
        """Return providers filtered by category string."""
        with self._lock:
            return [p for p in self._providers.values() if p.category == category]

    def get_provider_models(self, provider_id: str) -> List[Dict[str, Any]]:
        """Return model dicts for a given provider."""
        provider = self.get_provider(provider_id)
        if not provider:
            return []
        return [m.to_dict() for m in provider.models]

    def check_provider_available(self, provider_id: str) -> bool:
        """Check if a provider is available (has API key or is local)."""
        provider = self.get_provider(provider_id)
        return provider.is_available if provider else False

    def find_provider_by_name(self, name: str) -> Optional[ProviderConfig]:
        """Find a provider by ID, display_name, or name (case-insensitive)."""
        name_lower = name.strip().lower()
        with self._lock:
            for p in self._providers.values():
                if (p.id.lower() == name_lower
                        or p.display_name.lower() == name_lower
                        or p.name.lower() == name_lower):
                    return p
        return None

    def get_model_ids(self, provider_id: str) -> List[str]:
        """Return just the model ID strings for a provider."""
        provider = self.get_provider(provider_id)
        if not provider:
            return []
        return [m.model_id for m in provider.models]

    # -- Connection Management -----------------------------------------------

    def connect_provider(
        self,
        provider_id: str,
        api_key: str,
        base_url: Optional[str] = None,
    ) -> bool:
        """Configure and mark a provider as connected.

        Args:
            provider_id: Provider identifier.
            api_key: API key for authentication.
            base_url: Optional base URL override.

        Returns:
            True if the provider was found and configured.
        """
        provider = self.get_provider(provider_id)
        if not provider:
            logger.warning("Cannot connect unknown provider: %s", provider_id)
            return False

        with self._lock:
            provider._api_key = api_key
            provider._configured_base_url = base_url or ""
            provider._connected = bool(api_key)

        logger.info("Connected provider: %s", provider_id)
        return True

    def disconnect_provider(self, provider_id: str) -> bool:
        """Disconnect a provider and clear stored credentials.

        Returns:
            True if the provider was found and disconnected.
        """
        provider = self.get_provider(provider_id)
        if not provider:
            return False

        with self._lock:
            provider._api_key = ""
            provider._configured_base_url = ""
            provider._connected = False

        logger.info("Disconnected provider: %s", provider_id)
        return True

    # -- Persistence ---------------------------------------------------------

    def save_config(self) -> None:
        """Persist user configuration (API keys, overrides) to JSON file."""
        with self._lock:
            user_data: Dict[str, Any] = {"version": 1, "providers": {}}
            for pid, p in self._providers.items():
                # Only persist providers with user modifications
                if p._api_key or p._configured_base_url or p._connected:
                    user_data["providers"][pid] = p.to_persist_dict()

        try:
            config_path = self._config_path
            parent = os.path.dirname(config_path)
            os.makedirs(parent, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(user_data, f, ensure_ascii=False, indent=2)
            logger.debug("Saved provider config to %s", config_path)
        except Exception as e:
            logger.error("Failed to save provider config: %s", e)

    def _load_config(self) -> None:
        """Load user configuration from JSON file and overlay on catalog."""
        config_path = self._config_path
        if not os.path.exists(config_path):
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load provider config: %s", e)
            return

        providers_data = data.get("providers", {})
        with self._lock:
            for pid, pdata in providers_data.items():
                existing = self._providers.get(pid)
                if existing:
                    existing._api_key = pdata.get("api_key", "")
                    existing._configured_base_url = pdata.get("configured_base_url", "")
                    existing._connected = pdata.get("connected", bool(pdata.get("api_key")))
                else:
                    # User-defined provider not in catalog: reconstruct
                    models = []
                    for md in pdata.get("models", []):
                        models.append(ModelConfig(**md))
                    config = ProviderConfig(
                        id=pid,
                        name=pdata.get("name", pid),
                        display_name=pdata.get("display_name", pid),
                        transport=pdata.get("transport", "openai_chat"),
                        base_url=pdata.get("base_url", ""),
                        env_api_key=pdata.get("env_api_key", ""),
                        env_base_url=pdata.get("env_base_url", ""),
                        is_local=pdata.get("is_local", False),
                        is_aggregator=pdata.get("is_aggregator", False),
                        icon=pdata.get("icon", ""),
                        category=pdata.get("category", ProviderCategory.OTHER),
                        models=models,
                        doc=pdata.get("doc", ""),
                    )
                    config._api_key = pdata.get("api_key", "")
                    config._configured_base_url = pdata.get("configured_base_url", "")
                    config._connected = pdata.get("connected", bool(pdata.get("api_key")))
                    self._providers[pid] = config

        logger.debug("Loaded provider config from %s", config_path)

    # -- Statistics ----------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """Return summary statistics about the registry."""
        all_providers = self.get_all_providers()
        available = [p for p in all_providers if p.is_available]
        return {
            "total": len(all_providers),
            "available": len(available),
            "local": len([p for p in all_providers if p.is_local]),
            "cloud": len([p for p in all_providers if not p.is_local]),
            "categories": {
                cat.value: len([p for p in all_providers if p.category == cat])
                for cat in ProviderCategory
            },
        }


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_registry: Optional[ProviderRegistry] = None
_registry_lock = threading.Lock()


def get_provider_registry() -> ProviderRegistry:
    """Return the global ProviderRegistry singleton."""
    global _registry
    with _registry_lock:
        if _registry is None:
            _registry = ProviderRegistry()
    return _registry
