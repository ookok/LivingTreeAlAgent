"""
AI 服务提供商配置管理
参考 hermes-agent 的 providers.py 设计

支持的提供商：
- OpenRouter: 聚合多个模型的网关
- Nous Portal: Nous 官方门户
- Anthropic: Claude 系列
- OpenAI: GPT 系列
- DeepSeek: DeepSeek 系列
- 阿里云 (DashScope/Qwen): 通义千问
- Z.AI (GLM): 智谱 GLM
- Kimi (Moonshot): 月之暗面
- MiniMax: MiniMax
- HuggingFace: HuggingFace
- 本地: Ollama / LM Studio / vLLM
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Provider Type ──────────────────────────────────────────────────────────

class AuthType(str, Enum):
    """认证类型"""
    API_KEY = "api_key"                    # 标准 API Key
    OAUTH_DEVICE_CODE = "oauth_device_code"  # Nous Portal 等
    OAUTH_EXTERNAL = "oauth_external"      # Qwen OAuth 等
    EXTERNAL_PROCESS = "external_process"  # GitHub Copilot ACP


class TransportType(str, Enum):
    """传输协议类型"""
    OPENAI_CHAT = "openai_chat"           # OpenAI Chat Completions
    ANTHROPIC_MESSAGES = "anthropic_messages"  # Anthropic Messages API
    CODEX_RESPONSES = "codex_responses"    # OpenAI Codex


# ── Provider Overlay ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProviderOverlay:
    """提供商特定元数据（Hermes 特定配置）"""
    transport: str = "openai_chat"
    is_aggregator: bool = False
    auth_type: str = "api_key"
    extra_env_vars: Tuple[str, ...] = ()
    base_url_override: str = ""
    base_url_env_var: str = ""
    doc: str = ""


# ── Provider Definitions ─────────────────────────────────────────────────────

HERMES_OVERLAYS: Dict[str, ProviderOverlay] = {
    # OpenRouter - 聚合多个模型
    "openrouter": ProviderOverlay(
        transport="openai_chat",
        is_aggregator=True,
        extra_env_vars=("OPENAI_API_KEY",),
        base_url_env_var="OPENROUTER_BASE_URL",
        doc="聚合多个 AI 提供商的网关服务",
    ),
    
    # Nous Portal - OAuth 登录
    "nous": ProviderOverlay(
        transport="openai_chat",
        auth_type="oauth_device_code",
        base_url_override="https://inference-api.nousresearch.com/v1",
        doc="Nous 官方门户，需要 OAuth 登录",
    ),
    
    # Anthropic - Claude 系列
    "anthropic": ProviderOverlay(
        transport="anthropic_messages",
        extra_env_vars=("ANTHROPIC_TOKEN", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"),
        doc="Anthropic Claude 系列模型",
    ),
    
    # OpenAI - GPT 系列
    "openai": ProviderOverlay(
        transport="openai_chat",
        extra_env_vars=("OPENAI_API_KEY",),
        doc="OpenAI GPT 系列模型",
    ),
    
    # OpenAI Codex
    "openai-codex": ProviderOverlay(
        transport="codex_responses",
        auth_type="oauth_external",
        base_url_override="https://chatgpt.com/backend-api/codex",
        doc="OpenAI Codex，需要 GitHub 授权",
    ),
    
    # Qwen OAuth
    "qwen-oauth": ProviderOverlay(
        transport="openai_chat",
        auth_type="oauth_external",
        base_url_override="https://portal.qwen.ai/v1",
        base_url_env_var="HERMES_QWEN_BASE_URL",
        doc="通义千问 OAuth 授权",
    ),
    
    # GitHub Copilot ACP
    "copilot-acp": ProviderOverlay(
        transport="codex_responses",
        auth_type="external_process",
        base_url_override="acp://copilot",
        base_url_env_var="COPILOT_ACP_BASE_URL",
        doc="GitHub Copilot ACP 协议",
    ),
    
    # GitHub Copilot
    "github-copilot": ProviderOverlay(
        transport="openai_chat",
        extra_env_vars=("COPILOT_GITHUB_TOKEN", "GH_TOKEN"),
        doc="GitHub Copilot",
    ),
    
    # Z.AI / GLM - 智谱
    "zai": ProviderOverlay(
        transport="openai_chat",
        extra_env_vars=("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"),
        base_url_env_var="GLM_BASE_URL",
        doc="智谱 GLM 系列模型",
    ),
    
    # Kimi / Moonshot
    "kimi-for-coding": ProviderOverlay(
        transport="openai_chat",
        base_url_env_var="KIMI_BASE_URL",
        doc="月之暗面 Kimi 系列",
    ),
    
    # MiniMax 国际版
    "minimax": ProviderOverlay(
        transport="openai_chat",
        base_url_env_var="MINIMAX_BASE_URL",
        doc="MiniMax 国际版（Anthropic-compatible）",
    ),
    
    # MiniMax 中国版
    "minimax-cn": ProviderOverlay(
        transport="openai_chat",
        base_url_env_var="MINIMAX_CN_BASE_URL",
        doc="MiniMax 中国版（国内直连）",
    ),
    
    # DeepSeek
    "deepseek": ProviderOverlay(
        transport="openai_chat",
        base_url_env_var="DEEPSEEK_BASE_URL",
        doc="DeepSeek 系列模型",
    ),
    
    # 阿里云 (DashScope/Qwen)
    "alibaba": ProviderOverlay(
        transport="openai_chat",
        base_url_env_var="DASHSCOPE_BASE_URL",
        doc="阿里云通义千问（DashScope）",
    ),
    
    # Vercel AI Gateway
    "vercel": ProviderOverlay(
        transport="openai_chat",
        is_aggregator=True,
        doc="Vercel AI Gateway 聚合",
    ),
    
    # OpenCode Zen
    "opencode": ProviderOverlay(
        transport="openai_chat",
        is_aggregator=True,
        base_url_env_var="OPENCODE_ZEN_BASE_URL",
        doc="OpenCode Zen 聚合",
    ),
    
    # OpenCode Go
    "opencode-go": ProviderOverlay(
        transport="openai_chat",
        is_aggregator=True,
        base_url_env_var="OPENCODE_GO_BASE_URL",
        doc="OpenCode Go 聚合",
    ),
    
    # KiloCode
    "kilo": ProviderOverlay(
        transport="openai_chat",
        is_aggregator=True,
        base_url_env_var="KILOCODE_BASE_URL",
        doc="KiloCode 聚合",
    ),
    
    # HuggingFace
    "huggingface": ProviderOverlay(
        transport="openai_chat",
        is_aggregator=True,
        base_url_env_var="HF_BASE_URL",
        doc="HuggingFace 推理端点",
    ),
}


# ── Provider Aliases ────────────────────────────────────────────────────────

ALIASES: Dict[str, str] = {
    # OpenAI
    "openai": "openrouter",     # 默认路由到 OpenRouter
    
    # Z.AI / GLM
    "glm": "zai",
    "z-ai": "zai",
    "z.ai": "zai",
    "zhipu": "zai",
    
    # Kimi / Moonshot
    "kimi": "kimi-for-coding",
    "kimi-coding": "kimi-for-coding",
    "moonshot": "kimi-for-coding",
    
    # MiniMax
    "minimax-china": "minimax-cn",
    "minimax_cn": "minimax-cn",
    
    # Anthropic / Claude
    "claude": "anthropic",
    "claude-code": "anthropic",
    
    # GitHub Copilot
    "copilot": "github-copilot",
    "github": "github-copilot",
    "github-copilot-acp": "copilot-acp",
    
    # Vercel
    "ai-gateway": "vercel",
    "aigateway": "vercel",
    "vercel-ai-gateway": "vercel",
    
    # OpenCode
    "opencode-zen": "opencode",
    "zen": "opencode",
    "go": "opencode-go",
    "opencode-go-sub": "opencode-go",
    
    # KiloCode
    "kilocode": "kilo",
    "kilo-code": "kilo",
    "kilo-gateway": "kilo",
    
    # DeepSeek
    "deep-seek": "deepseek",
    
    # 阿里云
    "dashscope": "alibaba",
    "aliyun": "alibaba",
    "qwen": "alibaba",
    "alibaba-cloud": "alibaba",
    
    # HuggingFace
    "hf": "huggingface",
    "hugging-face": "huggingface",
    "huggingface-hub": "huggingface",
    
    # 本地服务
    "lmstudio": "lmstudio",
    "lm-studio": "lmstudio",
    "lm_studio": "lmstudio",
    "ollama": "ollama-cloud",
    "vllm": "local",
    "llamacpp": "local",
    "llama.cpp": "local",
    "llama-cpp": "local",
}


# ── Display Labels ───────────────────────────────────────────────────────────

LABEL_OVERRIDES: Dict[str, str] = {
    "nous": "Nous Portal",
    "openai-codex": "OpenAI Codex",
    "copilot-acp": "GitHub Copilot ACP",
    "github-copilot": "GitHub Copilot",
    "anthropic": "Anthropic (Claude)",
    "zai": "Z.AI / 智谱 GLM",
    "kimi-for-coding": "Kimi / Moonshot",
    "minimax": "MiniMax (国际)",
    "minimax-cn": "MiniMax (中国)",
    "deepseek": "DeepSeek",
    "alibaba": "阿里云 (通义千问)",
    "vercel": "Vercel AI Gateway",
    "opencode": "OpenCode Zen",
    "opencode-go": "OpenCode Go",
    "kilo": "KiloCode",
    "huggingface": "HuggingFace",
    "local": "本地端点",
    "openrouter": "OpenRouter",
}


# ── Provider Definition ──────────────────────────────────────────────────────

@dataclass
class ProviderDef:
    """完整提供商定义"""
    id: str
    name: str
    transport: str
    api_key_env_vars: Tuple[str, ...]
    base_url: str = ""
    base_url_env_var: str = ""
    is_aggregator: bool = False
    auth_type: str = "api_key"
    doc: str = ""
    source: str = ""  # "hermes", "user-config"
    
    @property
    def is_user_defined(self) -> bool:
        return self.source == "user-config"


# ── Helper Functions ─────────────────────────────────────────────────────────

def normalize_provider(name: str) -> str:
    """规范化提供商名称"""
    key = name.strip().lower()
    return ALIASES.get(key, key)


def get_overlay(provider_id: str) -> Optional[ProviderOverlay]:
    """获取提供商 overlay"""
    canonical = normalize_provider(provider_id)
    return HERMES_OVERLAYS.get(canonical)


def get_label(provider_id: str) -> str:
    """获取可读的提供商名称"""
    canonical = normalize_provider(provider_id)
    
    if canonical in LABEL_OVERRIDES:
        return LABEL_OVERRIDES[canonical]
    
    overlay = get_overlay(canonical)
    if overlay and overlay.doc:
        return overlay.doc
    
    return canonical


def is_aggregator(provider: str) -> bool:
    """判断是否为聚合提供商"""
    overlay = get_overlay(provider)
    return overlay.is_aggregator if overlay else False


def get_provider(name: str) -> Optional[ProviderDef]:
    """获取提供商定义"""
    canonical = normalize_provider(name)
    overlay = HERMES_OVERLAYS.get(canonical)
    
    if overlay is not None:
        return ProviderDef(
            id=canonical,
            name=LABEL_OVERRIDES.get(canonical, canonical),
            transport=overlay.transport,
            api_key_env_vars=overlay.extra_env_vars,
            base_url=overlay.base_url_override,
            base_url_env_var=overlay.base_url_env_var,
            is_aggregator=overlay.is_aggregator,
            auth_type=overlay.auth_type,
            doc=overlay.doc,
            source="hermes",
        )
    
    return None


# ── API Key Management ───────────────────────────────────────────────────────

def get_api_key(provider_id: str) -> Optional[str]:
    """获取提供商的 API Key"""
    provider = get_provider(provider_id)
    if not provider:
        return None
    
    # 按优先级检查环境变量
    for env_var in provider.api_key_env_vars:
        key = os.environ.get(env_var)
        if key:
            return key
    
    return None


def has_api_key(provider_id: str) -> bool:
    """检查是否配置了 API Key"""
    return get_api_key(provider_id) is not None


def get_all_configured_providers() -> List[str]:
    """获取所有已配置 API Key 的提供商"""
    configured = []
    
    for provider_id in HERMES_OVERLAYS:
        if has_api_key(provider_id):
            configured.append(provider_id)
    
    return configured


# ── Transport Mapping ────────────────────────────────────────────────────────

TRANSPORT_TO_API_MODE: Dict[str, str] = {
    "openai_chat": "chat_completions",
    "anthropic_messages": "anthropic_messages",
    "codex_responses": "codex_responses",
}


def determine_api_mode(provider: str, base_url: str = "") -> str:
    """确定 API 模式"""
    provider_def = get_provider(provider)
    if provider_def:
        return TRANSPORT_TO_API_MODE.get(provider_def.transport, "chat_completions")
    
    # URL 启发式判断
    if base_url:
        url_lower = base_url.rstrip("/").lower()
        if url_lower.endswith("/anthropic") or "api.anthropic.com" in url_lower:
            return "anthropic_messages"
        if "api.openai.com" in url_lower:
            return "codex_responses"
    
    return "chat_completions"


# ── Provider Listing ────────────────────────────────────────────────────────

def list_providers(
    include_aggregators: bool = True,
    include_local: bool = True,
) -> List[ProviderDef]:
    """列出所有可用的提供商"""
    providers = []
    
    for provider_id, overlay in HERMES_OVERLAYS.items():
        if not include_aggregators and overlay.is_aggregator:
            continue
        
        if not include_local and provider_id in ("local", "ollama-cloud", "lmstudio"):
            continue
        
        provider_def = get_provider(provider_id)
        if provider_def:
            providers.append(provider_def)
    
    return providers


# ── Provider Categories ─────────────────────────────────────────────────────

PROVIDER_CATEGORIES = {
    "聚合服务": ["openrouter", "vercel", "opencode", "opencode-go", "kilo", "huggingface"],
    "官方模型": ["openai", "anthropic"],
    "国产模型": ["alibaba", "deepseek", "zai", "kimi-for-coding", "minimax", "minimax-cn", "nous"],
    "Copilot": ["github-copilot", "copilot-acp", "openai-codex", "qwen-oauth"],
    "本地部署": ["local", "ollama-cloud", "lmstudio"],
}


def get_providers_by_category(category: str) -> List[ProviderDef]:
    """按类别获取提供商"""
    provider_ids = PROVIDER_CATEGORIES.get(category, [])
    return [p for pid in provider_ids if (p := get_provider(pid)) is not None]


# ── 常用模型推荐 ─────────────────────────────────────────────────────────────

RECOMMENDED_MODELS = {
    "openrouter": [
        "anthropic/claude-3.5-sonnet",
        "anthropic/claude-3-haiku",
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "google/gemini-pro",
        "mistralai/mistral-large",
        "deepseek/deepseek-chat",
    ],
    "anthropic": [
        "claude-3-5-sonnet-20241022",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ],
    "alibaba": [
        "qwen-plus",
        "qwen-turbo",
        "qwen-max",
        "qwen2.5-72b-instruct",
    ],
    "deepseek": [
        "deepseek-chat",
        "deepseek-coder",
    ],
    "zai": [
        "glm-4",
        "glm-4-flash",
        "glm-4-plus",
    ],
    "kimi-for-coding": [
        "moonshot-v1-8k",
        "moonshot-v1-32k",
        "moonshot-v1-128k",
    ],
    "minimax": [
        "MiniMax-Text-01",
        "abab6.5s-chat",
    ],
    "minimax-cn": [
        "abab6.5s-chat",
    ],
    "nous": [
        "Hermes-3-Llama-3.1-8B",
        "Hermes-2-Mistral-7B-DPO",
    ],
}


def get_recommended_models(provider_id: str) -> List[str]:
    """获取推荐模型列表"""
    canonical = normalize_provider(provider_id)
    return RECOMMENDED_MODELS.get(canonical, [])
