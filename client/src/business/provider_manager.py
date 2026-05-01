"""
Provider Manager - 增强版 AI 服务商管理器

核心功能：
1. 统一管理主流 AI 服务商（DeepSeek、OpenAI、Anthropic、Google、Ollama、Azure、Together AI、Cohere）
2. 自动探测和配置服务商
3. 优先支持 Thinking 模式
4. 集成 Opik 可观测性
5. 智能路由和负载均衡

支持的服务商：
┌─────────────┬─────────────────────────────────────────────┬──────────────┐
│   Provider  │              Models                        │  Thinking    │
├─────────────┼─────────────────────────────────────────────┼──────────────┤
│  DeepSeek   │ DeepSeek-V4-Flash, DeepSeek-V4-Pro         │     ✅       │
│  OpenAI     │ GPT-4o, GPT-4, GPT-3.5-Turbo              │     ✅       │
│  Anthropic  │ Claude-3-Sonnet, Claude-3-Opus            │     ✅       │


│  Google     │ Gemini-1.5-Pro, Gemini-1.5-Flash          │     ✅       │
│  Ollama     │ Llama3, Qwen, Mistral, Phi-3              │     ❌       │
│  Azure      │ GPT-4o, GPT-4, GPT-3.5                    │     ✅       │
│  Together   │ Mixtral, Llama3, Qwen2                    │     ❌       │
│  Cohere     │ Command-R, Command-R-Plus                 │     ❌       │
└─────────────┴─────────────────────────────────────────────┴──────────────┘
"""

import json
import asyncio
import httpx
import time
import logging
from typing import Dict, Any, Optional, List, Callable, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """AI 服务商类型"""
    # 国际主流服务商
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    TOGETHER = "together"
    COHERE = "cohere"
    
    # 国内云服务商
    ALIBABA = "alibaba"           # 阿里云通义千问
    TENCENT = "tencent"           # 腾讯云混元
    BAIDU = "baidu"               # 百度文心一言
    
    # AI 聚合平台
    FASTCHAT = "fastchat"         # FastChat (vLLM)
    LITELLM = "litellm"           # LiteLLM
    OPENROUTER = "openrouter"     # OpenRouter
    ANYSCALE = "anyscale"         # Anyscale
    
    # 自定义平台（支持用户自定义配置）
    CUSTOM = "custom"             # 自定义平台（兼容 Ollama、本地部署等）


class ModelCapability(Enum):
    """模型能力"""
    CHAT = "chat"
    CONTENT_GENERATION = "content_generation"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    REASONING = "reasoning"
    PLANNING = "planning"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    FORMAT_UNDERSTANDING = "format_understanding"
    DOCUMENT_PLANNING = "document_planning"
    COMPLIANCE_CHECK = "compliance_check"
    OPTIMIZATION = "optimization"
    WEB_SEARCH = "web_search"


@dataclass
class ProviderModel:
    """服务商模型信息"""
    model_id: str
    name: str
    provider: ProviderType
    capabilities: List[ModelCapability]
    max_tokens: int = 8192
    context_length: int = 32768
    quality_score: float = 0.8
    speed_score: float = 0.8
    cost_score: float = 0.7
    privacy_score: float = 0.5
    supports_thinking: bool = False
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderConfig:
    """服务商配置"""
    provider_type: ProviderType
    api_key: str = ""
    base_url: str = ""
    enabled: bool = True
    priority: int = 50
    models: List[ProviderModel] = field(default_factory=list)


@dataclass
class LlmCallMetrics:
    """LLM 调用指标"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    success: bool = True
    error: Optional[str] = None
    model: str = ""
    provider: str = ""
    thinking_enabled: bool = False


@dataclass
class LlmResponse:
    """LLM 响应"""
    content: str
    model_used: str
    provider_used: str
    metrics: LlmCallMetrics
    thinking_content: Optional[str] = None


class ProviderManager:
    """
    增强版 AI 服务商管理器
    
    核心特性：
    1. 多服务商支持（8+主流服务商）
    2. Thinking 模式优先
    3. Opik 可观测性集成
    4. 智能负载均衡
    5. 自动故障转移
    """
    
    def __init__(self):
        self._providers: Dict[ProviderType, ProviderConfig] = {}
        self._models: Dict[str, ProviderModel] = {}
        self._metrics_cache = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "success_rate": 0.0,
            "provider_usage": defaultdict(int),
            "model_usage": defaultdict(int)
        }
        
        # Opik 追踪支持
        self._opik_available = False
        self._init_opik()
        
        # 健康状态
        self._health_status: Dict[str, bool] = {}
        
        # 初始化内置服务商配置
        self._init_default_providers()
    
    def _init_opik(self):
        """初始化 Opik 可观测性"""
        try:
            from opik import Opik
            from opik.tracing import trace
            self._opik_client = Opik(project_name="AI-Pipeline")
            self._opik_trace = trace
            self._opik_available = True
            logger.info("✅ Opik 可观测性已初始化")
        except ImportError:
            logger.warning("⚠️ Opik SDK 未安装，跳过可观测性初始化")
    
    def _init_default_providers(self):
        """初始化默认服务商配置"""
        # DeepSeek
        self._providers[ProviderType.DEEPSEEK] = ProviderConfig(
            provider_type=ProviderType.DEEPSEEK,
            base_url="https://api.deepseek.com",
            enabled=True,
            priority=10,
            models=[
                ProviderModel(
                    model_id="deepseek_flash",
                    name="DeepSeek-V4-Flash",
                    provider=ProviderType.DEEPSEEK,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION
                    ],
                    max_tokens=8192,
                    context_length=32768,
                    quality_score=0.85,
                    speed_score=0.95,
                    cost_score=0.85,
                    privacy_score=0.2,
                    supports_thinking=False,
                    config={"model": "deepseek-v4-flash"}
                ),
                ProviderModel(
                    model_id="deepseek_pro",
                    name="DeepSeek-V4-Pro",
                    provider=ProviderType.DEEPSEEK,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.CODE_REVIEW,
                        ModelCapability.REASONING,
                        ModelCapability.PLANNING,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION,
                        ModelCapability.FORMAT_UNDERSTANDING,
                        ModelCapability.DOCUMENT_PLANNING,
                        ModelCapability.COMPLIANCE_CHECK,
                        ModelCapability.OPTIMIZATION
                    ],
                    max_tokens=8192,
                    context_length=65536,
                    quality_score=0.95,
                    speed_score=0.85,
                    cost_score=0.7,
                    privacy_score=0.2,
                    supports_thinking=True,
                    config={"model": "deepseek-v4-pro"}
                )
            ]
        )
        
        # OpenAI
        self._providers[ProviderType.OPENAI] = ProviderConfig(
            provider_type=ProviderType.OPENAI,
            base_url="https://api.openai.com/v1",
            enabled=False,
            priority=20,
            models=[
                ProviderModel(
                    model_id="openai_gpt4o",
                    name="GPT-4o",
                    provider=ProviderType.OPENAI,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.CODE_REVIEW,
                        ModelCapability.REASONING,
                        ModelCapability.PLANNING,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION,
                        ModelCapability.FORMAT_UNDERSTANDING
                    ],
                    max_tokens=16384,
                    context_length=128000,
                    quality_score=0.98,
                    speed_score=0.8,
                    cost_score=0.4,
                    privacy_score=0.1,
                    supports_thinking=True,
                    config={"model": "gpt-4o"}
                ),
                ProviderModel(
                    model_id="openai_gpt4",
                    name="GPT-4",
                    provider=ProviderType.OPENAI,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.CODE_REVIEW,
                        ModelCapability.REASONING,
                        ModelCapability.PLANNING
                    ],
                    max_tokens=8192,
                    context_length=8192,
                    quality_score=0.95,
                    speed_score=0.6,
                    cost_score=0.3,
                    privacy_score=0.1,
                    supports_thinking=True,
                    config={"model": "gpt-4"}
                ),
                ProviderModel(
                    model_id="openai_gpt35",
                    name="GPT-3.5-Turbo",
                    provider=ProviderType.OPENAI,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION
                    ],
                    max_tokens=4096,
                    context_length=16384,
                    quality_score=0.8,
                    speed_score=0.95,
                    cost_score=0.75,
                    privacy_score=0.1,
                    supports_thinking=False,
                    config={"model": "gpt-3.5-turbo"}
                )
            ]
        )
        
        # Anthropic
        self._providers[ProviderType.ANTHROPIC] = ProviderConfig(
            provider_type=ProviderType.ANTHROPIC,
            base_url="https://api.anthropic.com/v1",
            enabled=False,
            priority=25,
            models=[
                ProviderModel(
                    model_id="anthropic_claude3_sonnet",
                    name="Claude-3-Sonnet",
                    provider=ProviderType.ANTHROPIC,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.CODE_REVIEW,
                        ModelCapability.REASONING,
                        ModelCapability.PLANNING,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION,
                        ModelCapability.FORMAT_UNDERSTANDING
                    ],
                    max_tokens=8192,
                    context_length=200000,
                    quality_score=0.95,
                    speed_score=0.75,
                    cost_score=0.5,
                    privacy_score=0.2,
                    supports_thinking=True,
                    config={"model": "claude-3-sonnet-20240229"}
                ),
                ProviderModel(
                    model_id="anthropic_claude3_opus",
                    name="Claude-3-Opus",
                    provider=ProviderType.ANTHROPIC,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.CODE_REVIEW,
                        ModelCapability.REASONING,
                        ModelCapability.PLANNING
                    ],
                    max_tokens=8192,
                    context_length=200000,
                    quality_score=0.98,
                    speed_score=0.6,
                    cost_score=0.3,
                    privacy_score=0.2,
                    supports_thinking=True,
                    config={"model": "claude-3-opus-20240229"}
                )
            ]
        )
        
        # Google
        self._providers[ProviderType.GOOGLE] = ProviderConfig(
            provider_type=ProviderType.GOOGLE,
            base_url="https://generativelanguage.googleapis.com/v1",
            enabled=False,
            priority=30,
            models=[
                ProviderModel(
                    model_id="google_gemini_pro",
                    name="Gemini-1.5-Pro",
                    provider=ProviderType.GOOGLE,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.REASONING,
                        ModelCapability.PLANNING,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION
                    ],
                    max_tokens=8192,
                    context_length=1000000,
                    quality_score=0.95,
                    speed_score=0.8,
                    cost_score=0.5,
                    privacy_score=0.2,
                    supports_thinking=True,
                    config={"model": "gemini-1.5-pro-latest"}
                ),
                ProviderModel(
                    model_id="google_gemini_flash",
                    name="Gemini-1.5-Flash",
                    provider=ProviderType.GOOGLE,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION
                    ],
                    max_tokens=8192,
                    context_length=1000000,
                    quality_score=0.85,
                    speed_score=0.95,
                    cost_score=0.8,
                    privacy_score=0.2,
                    supports_thinking=False,
                    config={"model": "gemini-1.5-flash-latest"}
                )
            ]
        )
        
        # Custom（自定义平台，兼容 Ollama、本地部署模型等）
        self._providers[ProviderType.CUSTOM] = ProviderConfig(
            provider_type=ProviderType.CUSTOM,
            base_url="http://localhost:11434/v1",  # 默认 Ollama 地址
            enabled=False,
            priority=40,
            models=[]  # 动态发现或用户自定义配置
        )
        
        # Azure OpenAI
        self._providers[ProviderType.AZURE] = ProviderConfig(
            provider_type=ProviderType.AZURE,
            base_url="",
            enabled=False,
            priority=35,
            models=[]  # 动态配置
        )
        
        # Together AI
        self._providers[ProviderType.TOGETHER] = ProviderConfig(
            provider_type=ProviderType.TOGETHER,
            base_url="https://api.together.xyz/v1",
            enabled=False,
            priority=50,
            models=[
                ProviderModel(
                    model_id="together_mixtral",
                    name="Mixtral-8x7B",
                    provider=ProviderType.TOGETHER,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION
                    ],
                    max_tokens=8192,
                    context_length=32768,
                    quality_score=0.85,
                    speed_score=0.9,
                    cost_score=0.85,
                    privacy_score=0.3,
                    supports_thinking=False,
                    config={"model": "mistralai/Mixtral-8x7B-Instruct-v0.1"}
                )
            ]
        )
        
        # Cohere
        self._providers[ProviderType.COHERE] = ProviderConfig(
            provider_type=ProviderType.COHERE,
            base_url="https://api.cohere.ai/v1",
            enabled=False,
            priority=55,
            models=[
                ProviderModel(
                    model_id="cohere_command_r",
                    name="Command-R",
                    provider=ProviderType.COHERE,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION
                    ],
                    max_tokens=4096,
                    context_length=128000,
                    quality_score=0.85,
                    speed_score=0.85,
                    cost_score=0.7,
                    privacy_score=0.3,
                    supports_thinking=False,
                    config={"model": "command-r"}
                ),
                ProviderModel(
                    model_id="cohere_command_r_plus",
                    name="Command-R-Plus",
                    provider=ProviderType.COHERE,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.REASONING,
                        ModelCapability.SUMMARIZATION
                    ],
                    max_tokens=8192,
                    context_length=200000,
                    quality_score=0.9,
                    speed_score=0.75,
                    cost_score=0.5,
                    privacy_score=0.3,
                    supports_thinking=False,
                    config={"model": "command-r-plus"}
                )
            ]
        )
        
        # ========== 国内云服务商 ==========
        
        # 阿里云通义千问
        self._providers[ProviderType.ALIBABA] = ProviderConfig(
            provider_type=ProviderType.ALIBABA,
            base_url="https://dashscope.aliyuncs.com/api/text/v1",
            enabled=False,
            priority=22,
            models=[
                ProviderModel(
                    model_id="alibaba_qwen_max",
                    name="Qwen-Max",
                    provider=ProviderType.ALIBABA,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.CODE_REVIEW,
                        ModelCapability.REASONING,
                        ModelCapability.PLANNING,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION,
                        ModelCapability.FORMAT_UNDERSTANDING
                    ],
                    max_tokens=8192,
                    context_length=128000,
                    quality_score=0.92,
                    speed_score=0.85,
                    cost_score=0.65,
                    privacy_score=0.4,
                    supports_thinking=True,
                    config={"model": "qwen-max"}
                ),
                ProviderModel(
                    model_id="alibaba_qwen_turbo",
                    name="Qwen-Turbo",
                    provider=ProviderType.ALIBABA,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION
                    ],
                    max_tokens=4096,
                    context_length=32768,
                    quality_score=0.82,
                    speed_score=0.95,
                    cost_score=0.8,
                    privacy_score=0.4,
                    supports_thinking=False,
                    config={"model": "qwen-turbo"}
                ),
                ProviderModel(
                    model_id="alibaba_qwen_code",
                    name="Qwen-Coder",
                    provider=ProviderType.ALIBABA,
                    capabilities=[
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.CODE_REVIEW,
                        ModelCapability.CHAT
                    ],
                    max_tokens=8192,
                    context_length=65536,
                    quality_score=0.9,
                    speed_score=0.85,
                    cost_score=0.7,
                    privacy_score=0.4,
                    supports_thinking=False,
                    config={"model": "qwen-coder"}
                )
            ]
        )
        
        # 腾讯云混元
        self._providers[ProviderType.TENCENT] = ProviderConfig(
            provider_type=ProviderType.TENCENT,
            base_url="https://api.tencentai.tencent.com/v1/",
            enabled=False,
            priority=23,
            models=[
                ProviderModel(
                    model_id="tencent_hunyuan_pro",
                    name="HunYuan-Pro",
                    provider=ProviderType.TENCENT,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.REASONING,
                        ModelCapability.PLANNING,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION
                    ],
                    max_tokens=8192,
                    context_length=8192,
                    quality_score=0.9,
                    speed_score=0.85,
                    cost_score=0.65,
                    privacy_score=0.4,
                    supports_thinking=True,
                    config={"model": "hunyuan-pro"}
                ),
                ProviderModel(
                    model_id="tencent_hunyuan_std",
                    name="HunYuan-Standard",
                    provider=ProviderType.TENCENT,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION
                    ],
                    max_tokens=4096,
                    context_length=4096,
                    quality_score=0.82,
                    speed_score=0.9,
                    cost_score=0.75,
                    privacy_score=0.4,
                    supports_thinking=False,
                    config={"model": "hunyuan-standard"}
                )
            ]
        )
        
        # 百度文心一言
        self._providers[ProviderType.BAIDU] = ProviderConfig(
            provider_type=ProviderType.BAIDU,
            base_url="https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
            enabled=False,
            priority=24,
            models=[
                ProviderModel(
                    model_id="baidu_ernie_40",
                    name="ERNIE-4.0",
                    provider=ProviderType.BAIDU,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.REASONING,
                        ModelCapability.PLANNING,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION,
                        ModelCapability.FORMAT_UNDERSTANDING
                    ],
                    max_tokens=8192,
                    context_length=8192,
                    quality_score=0.9,
                    speed_score=0.8,
                    cost_score=0.65,
                    privacy_score=0.4,
                    supports_thinking=True,
                    config={"model": "ernie-4.0"}
                ),
                ProviderModel(
                    model_id="baidu_ernie_35",
                    name="ERNIE-3.5",
                    provider=ProviderType.BAIDU,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.SUMMARIZATION,
                        ModelCapability.TRANSLATION
                    ],
                    max_tokens=4096,
                    context_length=4096,
                    quality_score=0.85,
                    speed_score=0.85,
                    cost_score=0.7,
                    privacy_score=0.4,
                    supports_thinking=False,
                    config={"model": "ernie-3.5"}
                )
            ]
        )
        
        # ========== AI 聚合平台 ==========
        
        # LiteLLM（统一接口聚合）
        self._providers[ProviderType.LITELLM] = ProviderConfig(
            provider_type=ProviderType.LITELLM,
            base_url="http://localhost:4000/v1",
            enabled=False,
            priority=60,
            models=[]  # LiteLLM 代理的模型由后端配置
        )
        
        # OpenRouter（聚合多种模型）
        self._providers[ProviderType.OPENROUTER] = ProviderConfig(
            provider_type=ProviderType.OPENROUTER,
            base_url="https://openrouter.ai/api/v1",
            enabled=False,
            priority=65,
            models=[
                ProviderModel(
                    model_id="openrouter_gpt4o",
                    name="GPT-4o (OpenRouter)",
                    provider=ProviderType.OPENROUTER,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.REASONING,
                        ModelCapability.PLANNING
                    ],
                    max_tokens=8192,
                    context_length=128000,
                    quality_score=0.98,
                    speed_score=0.75,
                    cost_score=0.45,
                    privacy_score=0.2,
                    supports_thinking=True,
                    config={"model": "openai/gpt-4o"}
                ),
                ProviderModel(
                    model_id="openrouter_claude3",
                    name="Claude-3-Sonnet (OpenRouter)",
                    provider=ProviderType.OPENROUTER,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION,
                        ModelCapability.REASONING
                    ],
                    max_tokens=8192,
                    context_length=200000,
                    quality_score=0.95,
                    speed_score=0.7,
                    cost_score=0.45,
                    privacy_score=0.2,
                    supports_thinking=True,
                    config={"model": "anthropic/claude-3-sonnet"}
                )
            ]
        )
        
        # FastChat / vLLM（本地部署代理）
        self._providers[ProviderType.FASTCHAT] = ProviderConfig(
            provider_type=ProviderType.FASTCHAT,
            base_url="http://localhost:8000/v1",
            enabled=False,
            priority=58,
            models=[]  # FastChat 代理的模型由后端配置
        )
        
        # Anyscale（云原生 LLM 平台）
        self._providers[ProviderType.ANYSCALE] = ProviderConfig(
            provider_type=ProviderType.ANYSCALE,
            base_url="https://api.endpoints.anyscale.com/v1",
            enabled=False,
            priority=57,
            models=[
                ProviderModel(
                    model_id="anyscale_mistral",
                    name="Mistral-8x7B (AnyScale)",
                    provider=ProviderType.ANYSCALE,
                    capabilities=[
                        ModelCapability.CHAT,
                        ModelCapability.CONTENT_GENERATION,
                        ModelCapability.CODE_GENERATION
                    ],
                    max_tokens=8192,
                    context_length=32768,
                    quality_score=0.85,
                    speed_score=0.9,
                    cost_score=0.75,
                    privacy_score=0.3,
                    supports_thinking=False,
                    config={"model": "mistralai/Mixtral-8x7B-Instruct-v0.1"}
                )
            ]
        )
        
        # 构建模型索引
        self._build_model_index()
    
    def _build_model_index(self):
        """构建模型索引"""
        self._models.clear()
        for provider_config in self._providers.values():
            for model in provider_config.models:
                self._models[model.model_id] = model
    
    def load_config_from_encrypted(self):
        """从加密配置加载服务商配置"""
        try:
            from business.encrypted_config import load_model_config
            
            for provider_type in ProviderType:
                cfg = load_model_config(provider_type.value)
                if cfg:
                    self._update_provider_from_config(provider_type, cfg)
            
            # 动态发现 Custom 平台的模型（支持 Ollama 等本地部署）
            self._discover_custom_models()
            
            self._build_model_index()
            logger.info("✅ 服务商配置已从加密配置加载")
        except Exception as e:
            logger.error(f"加载服务商配置失败: {e}")
    
    def _discover_custom_models(self):
        """动态发现自定义平台的模型（支持 Ollama、本地部署等）"""
        custom_provider = self._providers.get(ProviderType.CUSTOM)
        if not custom_provider or not custom_provider.enabled:
            return
        
        # 如果已有模型配置，不自动发现
        if custom_provider.models:
            return
        
        # 尝试从 API 获取模型列表（Ollama 风格）
        try:
            import httpx
            import asyncio
            
            async def discover():
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        # 尝试 Ollama API
                        url = f"{custom_provider.base_url}/api/tags"
                        response = await client.get(url)
                        if response.status_code == 200:
                            data = response.json()
                            for model_info in data.get("models", []):
                                model_name = model_info.get("name", "")
                                model_id = f"custom_{model_name.replace(':', '_').replace('/', '_')}"
                                
                                # 确定模型能力（基于名称猜测）
                                capabilities = [ModelCapability.CHAT, ModelCapability.CONTENT_GENERATION]
                                if "code" in model_name.lower() or "coder" in model_name.lower():
                                    capabilities.append(ModelCapability.CODE_GENERATION)
                                if "llama3" in model_name.lower() or "qwen" in model_name.lower():
                                    capabilities.append(ModelCapability.REASONING)
                                
                                custom_provider.models.append(ProviderModel(
                                    model_id=model_id,
                                    name=f"{model_name} (Custom)",
                                    provider=ProviderType.CUSTOM,
                                    capabilities=capabilities,
                                    max_tokens=4096,
                                    context_length=8192,
                                    quality_score=0.75,
                                    speed_score=0.95,
                                    cost_score=1.0,
                                    privacy_score=1.0,
                                    supports_thinking=False,
                                    config={"model": model_name, "base_url": custom_provider.base_url}
                                ))
                            logger.info(f"✅ 发现 {len(custom_provider.models)} 个自定义模型")
                except Exception as e:
                    logger.debug(f"自定义平台模型发现失败: {e}")
            
            # 非阻塞执行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(asyncio.wait_for(discover(), timeout=5))
            loop.close()
        except ImportError:
            logger.debug("httpx 未安装，跳过自定义模型发现")
    
    def add_custom_provider(self, name: str, base_url: str, api_key: str = "", 
                           priority: int = 50) -> ProviderType:
        """
        添加自定义服务商
        
        Args:
            name: 服务商名称（用于生成枚举值）
            base_url: API 基础 URL
            api_key: API 密钥（可选）
            priority: 优先级
        
        Returns:
            创建的 ProviderType 或 None
        """
        # 创建自定义配置
        custom_id = f"custom_{name.lower().replace(' ', '_')}"
        
        # 检查是否已存在
        if custom_id in [p.value for p in ProviderType]:
            logger.warning(f"自定义服务商已存在: {custom_id}")
            return None
        
        # 添加配置
        self._providers[ProviderType.CUSTOM] = ProviderConfig(
            provider_type=ProviderType.CUSTOM,
            base_url=base_url,
            api_key=api_key,
            enabled=True,
            priority=priority,
            models=[]
        )
        
        logger.info(f"✅ 已添加自定义服务商: {name} @ {base_url}")
        return ProviderType.CUSTOM
    
    def add_custom_model(self, provider_type: ProviderType, model_id: str, name: str,
                        capabilities: List[str], config: Dict[str, Any],
                        supports_thinking: bool = False, quality_score: float = 0.8):
        """
        添加自定义模型
        
        Args:
            provider_type: 服务商类型
            model_id: 模型ID
            name: 模型名称
            capabilities: 模型能力列表
            config: 模型配置
            supports_thinking: 是否支持思考模式
            quality_score: 质量评分
        """
        provider = self._providers.get(provider_type)
        if not provider:
            logger.error(f"服务商不存在: {provider_type}")
            return
        
        caps = [
            getattr(ModelCapability, c.upper(), ModelCapability.CHAT)
            for c in capabilities
        ]
        
        provider.models.append(ProviderModel(
            model_id=model_id,
            name=name,
            provider=provider_type,
            capabilities=caps,
            max_tokens=config.get("max_tokens", 4096),
            context_length=config.get("context_length", 8192),
            quality_score=quality_score,
            speed_score=config.get("speed_score", 0.8),
            cost_score=config.get("cost_score", 0.7),
            privacy_score=config.get("privacy_score", 0.5),
            supports_thinking=supports_thinking,
            config=config
        ))
        
        # 更新索引
        self._build_model_index()
        logger.info(f"✅ 已添加自定义模型: {name}")
    
    def _update_provider_from_config(self, provider_type: ProviderType, config: Dict):
        """更新服务商配置"""
        if provider_type not in self._providers:
            self._providers[provider_type] = ProviderConfig(provider_type=provider_type)
        
        provider = self._providers[provider_type]
        
        if "api_key" in config:
            provider.api_key = config["api_key"]
        
        if "base_url" in config:
            provider.base_url = config["base_url"]
        
        if "enabled" in config:
            provider.enabled = config["enabled"]
        
        if "priority" in config:
            provider.priority = config["priority"]
        
        # 更新模型配置
        if "models" in config:
            for key, model_config in config["models"].items():
                model_id = model_config.get("model_id", f"{provider_type.value}_{key}")
                existing_model = next((m for m in provider.models if m.model_id == model_id), None)
                
                if existing_model:
                    # 更新现有模型
                    if "enabled" in model_config:
                        # 通过 enabled 控制模型可用性
                        pass
                else:
                    # 添加新模型
                    caps = [
                        getattr(ModelCapability, c.upper(), ModelCapability.CHAT)
                        for c in model_config.get("capabilities", [])
                    ]
                    provider.models.append(ProviderModel(
                        model_id=model_id,
                        name=model_config.get("model_name", key),
                        provider=provider_type,
                        capabilities=caps,
                        max_tokens=model_config.get("max_tokens", 8192),
                        context_length=model_config.get("context_length", 32768),
                        quality_score=model_config.get("quality_score", 0.8),
                        speed_score=model_config.get("speed_score", 0.8),
                        cost_score=model_config.get("cost_score", 0.7),
                        privacy_score=model_config.get("privacy_score", 0.5),
                        supports_thinking=model_config.get("supports_thinking", False),
                        config={
                            "model": model_config.get("model_name", key),
                            "base_url": provider.base_url,
                            "api_key": provider.api_key
                        }
                    ))
    
    def get_models_for_capability(self, capability: ModelCapability, 
                                 prefer_thinking: bool = True) -> List[ProviderModel]:
        """获取支持指定能力的模型列表"""
        models = [
            m for m in self._models.values()
            if capability in m.capabilities and 
               self._providers[m.provider].enabled and
               self._providers[m.provider].api_key
        ]
        
        # 优先排序
        if prefer_thinking:
            models.sort(key=lambda x: (
                -x.supports_thinking,      # Thinking 模式优先
                -x.quality_score,          # 质量次之
                x.cost_score               # 成本最后
            ))
        else:
            models.sort(key=lambda x: (
                -x.quality_score,
                x.cost_score
            ))
        
        return models
    
    async def call_model(self, capability: ModelCapability, prompt: str,
                        system_prompt: str = "", prefer_thinking: bool = True,
                        max_tokens: int = 1024, **kwargs) -> LlmResponse:
        """
        调用模型
        
        Args:
            capability: 需要的能力
            prompt: 用户提示
            system_prompt: 系统提示
            prefer_thinking: 是否优先使用 Thinking 模式
            max_tokens: 最大 token 数
        
        Returns:
            LlmResponse 对象
        """
        start_time = time.time()
        
        # Opik 追踪
        opik_span = None
        if self._opik_available:
            try:
                opik_span = self._opik_trace.start_span(
                    name=f"llm_call_{capability.value}",
                    trace_type="llm",
                    metadata={
                        "capability": capability.value,
                        "prefer_thinking": prefer_thinking
                    }
                )
            except Exception as e:
                logger.debug(f"Opik 追踪初始化失败: {e}")
        
        try:
            # 获取可用模型
            models = self.get_models_for_capability(capability, prefer_thinking)
            
            if not models:
                raise ValueError(f"无可用模型支持能力: {capability.value}")
            
            # 选择最佳模型
            model = models[0]
            provider_config = self._providers[model.provider]
            
            # 构建请求
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # 根据服务商类型调用
            if model.provider in [ProviderType.DEEPSEEK, ProviderType.OPENAI, ProviderType.AZURE]:
                result = await self._call_openai_style(
                    model=model,
                    provider_config=provider_config,
                    messages=messages,
                    max_tokens=max_tokens,
                    thinking=model.supports_thinking and prefer_thinking,
                    **kwargs
                )
            elif model.provider == ProviderType.ANTHROPIC:
                result = await self._call_anthropic(
                    model=model,
                    provider_config=provider_config,
                    messages=messages,
                    max_tokens=max_tokens,
                    thinking=model.supports_thinking and prefer_thinking,
                    **kwargs
                )
            elif model.provider == ProviderType.GOOGLE:
                result = await self._call_google(
                    model=model,
                    provider_config=provider_config,
                    messages=messages,
                    max_tokens=max_tokens,
                    thinking=model.supports_thinking and prefer_thinking,
                    **kwargs
                )
            elif model.provider == ProviderType.COHERE:
                result = await self._call_cohere(
                    model=model,
                    provider_config=provider_config,
                    messages=messages,
                    max_tokens=max_tokens,
                    **kwargs
                )
            else:
                raise ValueError(f"不支持的服务商类型: {model.provider}")
            
            # 计算耗时和成本
            latency_ms = (time.time() - start_time) * 1000
            cost_usd = self._calculate_cost(result["usage"], model)
            
            # 更新指标
            self._update_metrics(result["usage"], model, latency_ms, cost_usd, True)
            
            # 更新 Opik 追踪
            if opik_span:
                try:
                    opik_span.set_output(result["response"])
                    opik_span.set_attributes({
                        "model": model.name,
                        "provider": model.provider.value,
                        "tokens_used": result["usage"].get("total_tokens", 0),
                        "latency_ms": latency_ms,
                        "cost_usd": cost_usd
                    })
                except Exception as e:
                    logger.debug(f"Opik 追踪更新失败: {e}")
            
            return LlmResponse(
                content=result["response"],
                model_used=model.name,
                provider_used=model.provider.value,
                metrics=LlmCallMetrics(
                    prompt_tokens=result["usage"].get("prompt_tokens", 0),
                    completion_tokens=result["usage"].get("completion_tokens", 0),
                    total_tokens=result["usage"].get("total_tokens", 0),
                    latency_ms=latency_ms,
                    cost_usd=cost_usd,
                    success=True,
                    model=model.name,
                    provider=model.provider.value,
                    thinking_enabled=model.supports_thinking and prefer_thinking
                ),
                thinking_content=result.get("thinking_content")
            )
        
        except Exception as e:
            # 更新指标
            self._update_metrics({}, model, 0, 0, False, str(e))
            
            if opik_span:
                try:
                    opik_span.set_error(str(e))
                except Exception as ex:
                    logger.debug(f"Opik 错误记录失败: {ex}")
            
            return LlmResponse(
                content="",
                model_used="",
                provider_used="",
                metrics=LlmCallMetrics(
                    success=False,
                    error=str(e)
                )
            )
    
    async def _call_openai_style(self, model: ProviderModel, provider_config: ProviderConfig,
                                messages: List[Dict], max_tokens: int, thinking: bool = False,
                                **kwargs) -> Dict:
        """调用 OpenAI 风格的 API"""
        import httpx
        
        url = f"{provider_config.base_url}/chat/completions"
        api_key = provider_config.api_key
        
        data = {
            "model": model.config["model"],
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", 0.7)
        }
        
        # Thinking 模式（DeepSeek V4 Pro 支持）
        if thinking and model.supports_thinking:
            data["thinking"] = {
                "type": "enabled",
                "thought": True,
                "thought_num": 5,
                "thought_max_token": 512
            }
        
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=data
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("choices"):
                message = result["choices"][0]["message"]
                response_text = message["content"]
                thinking_content = message.get("reasoning_content", "")
                
                return {
                    "response": response_text,
                    "thinking_content": thinking_content,
                    "usage": result.get("usage", {})
                }
        
        return {"response": "", "thinking_content": "", "usage": {}}
    
    async def _call_anthropic(self, model: ProviderModel, provider_config: ProviderConfig,
                             messages: List[Dict], max_tokens: int, thinking: bool = False,
                             **kwargs) -> Dict:
        """调用 Anthropic API"""
        import httpx
        
        url = f"{provider_config.base_url}/messages"
        api_key = provider_config.api_key
        
        # 转换消息格式
        anthropic_messages = []
        system_prompt = ""
        
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        data = {
            "model": model.config["model"],
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", 0.7)
        }
        
        if system_prompt:
            data["system"] = system_prompt
        
        # Claude 3 的思考模式通过 system prompt 实现
        if thinking and model.supports_thinking:
            system_prompt_prefix = "请使用思考模式详细解释你的推理过程。\n\n"
            data["system"] = system_prompt_prefix + (data.get("system", ""))
        
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                url,
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json"
                },
                json=data
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("content"):
                response_text = result["content"][0]["text"]
                return {
                    "response": response_text,
                    "thinking_content": "",
                    "usage": result.get("usage", {})
                }
        
        return {"response": "", "thinking_content": "", "usage": {}}
    
    async def _call_google(self, model: ProviderModel, provider_config: ProviderConfig,
                          messages: List[Dict], max_tokens: int, thinking: bool = False,
                          **kwargs) -> Dict:
        """调用 Google Gemini API"""
        import httpx
        
        model_name = model.config["model"]
        url = f"{provider_config.base_url}/models/{model_name}:generateContent"
        
        # 转换消息格式
        contents = []
        for msg in messages:
            contents.append({
                "role": msg["role"],
                "parts": [{"text": msg["content"]}]
            })
        
        data = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": kwargs.get("temperature", 0.7)
            }
        }
        
        # Gemini 的思考模式
        if thinking and model.supports_thinking:
            data["generationConfig"]["responseMimeType"] = "application/json"
            # 通过系统提示启用思考模式
        
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                url,
                headers={
                    "Content-Type": "application/json"
                },
                params={"key": provider_config.api_key},
                json=data
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("candidates"):
                content = result["candidates"][0].get("content", {})
                parts = content.get("parts", [])
                response_text = "".join(p.get("text", "") for p in parts)
                
                return {
                    "response": response_text,
                    "thinking_content": "",
                    "usage": {}
                }
        
        return {"response": "", "thinking_content": "", "usage": {}}
    
    async def _call_cohere(self, model: ProviderModel, provider_config: ProviderConfig,
                          messages: List[Dict], max_tokens: int, **kwargs) -> Dict:
        """调用 Cohere API"""
        import httpx
        
        url = f"{provider_config.base_url}/chat"
        api_key = provider_config.api_key
        
        # 转换消息格式
        chat_history = []
        user_message = ""
        
        for msg in messages[:-1]:
            chat_history.append({
                "role": msg["role"],
                "message": msg["content"]
            })
        
        if messages:
            user_message = messages[-1]["content"]
        
        data = {
            "model": model.config["model"],
            "message": user_message,
            "chat_history": chat_history,
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", 0.7)
        }
        
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=data
            )
            
            response.raise_for_status()
            result = response.json()
            
            return {
                "response": result.get("text", ""),
                "thinking_content": "",
                "usage": result.get("meta", {}).get("usage", {})
            }
    
    def _calculate_cost(self, usage: Dict, model: ProviderModel) -> float:
        """计算调用成本"""
        cost_per_1k_tokens = {
            "deepseek-v4-flash": 0.0002,
            "deepseek-v4-pro": 0.0005,
            "gpt-4o": 0.005,
            "gpt-4": 0.01,
            "gpt-3.5-turbo": 0.0015,
            "claude-3-sonnet": 0.003,
            "claude-3-opus": 0.015,
            "gemini-1.5-pro": 0.0025,
            "gemini-1.5-flash": 0.00075,
            "command-r": 0.001,
            "command-r-plus": 0.003
        }
        
        rate = cost_per_1k_tokens.get(model.config.get("model"), 0.0003)
        return (usage.get("total_tokens", 0) / 1000) * rate
    
    def _update_metrics(self, usage: Dict, model: ProviderModel, 
                       latency_ms: float, cost_usd: float, success: bool, 
                       error: str = None):
        """更新指标缓存"""
        self._metrics_cache["total_calls"] += 1
        self._metrics_cache["total_tokens"] += usage.get("total_tokens", 0)
        self._metrics_cache["total_cost_usd"] += cost_usd
        
        # 成功率计算
        if success:
            self._metrics_cache["success_rate"] = (
                (self._metrics_cache["success_rate"] * (self._metrics_cache["total_calls"] - 1) + 1) 
                / self._metrics_cache["total_calls"]
            )
        else:
            self._metrics_cache["success_rate"] = (
                self._metrics_cache["success_rate"] * (self._metrics_cache["total_calls"] - 1) 
                / self._metrics_cache["total_calls"]
            )
        
        # 服务商和模型使用统计
        self._metrics_cache["provider_usage"][model.provider.value] += 1
        self._metrics_cache["model_usage"][model.model_id] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取聚合指标"""
        return {
            "total_calls": self._metrics_cache["total_calls"],
            "total_tokens": self._metrics_cache["total_tokens"],
            "total_cost_usd": round(self._metrics_cache["total_cost_usd"], 4),
            "success_rate": round(self._metrics_cache["success_rate"] * 100, 2),
            "provider_usage": dict(self._metrics_cache["provider_usage"]),
            "model_usage": dict(self._metrics_cache["model_usage"])
        }
    
    def generate_report(self) -> str:
        """生成可观测性报告"""
        metrics = self.get_metrics()
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║                    Provider Manager 报告                    ║
╠══════════════════════════════════════════════════════════════╣
║  总调用次数:      {metrics['total_calls']:>10} 次             ║
║  总 Token 数:    {metrics['total_tokens']:>10}               ║
║  总成本(USD):    ${metrics['total_cost_usd']:>10.4f}        ║
║  成功率:         {metrics['success_rate']:>10.2f}%           ║
╠══════════════════════════════════════════════════════════════╣
║  服务商使用分布:                                            ║
"""
        
        for provider, count in metrics['provider_usage'].items():
            percentage = (count / metrics['total_calls']) * 100 if metrics['total_calls'] > 0 else 0
            report += f"║    {provider:15}  {count:5} 次  ({percentage:5.1f}%)\n"
        
        report += f"""
╠══════════════════════════════════════════════════════════════╣
║  支持的服务商: {', '.join(p.value for p in self._providers.keys())}  ║
║  支持的模型数: {len(self._models)}                            ║
║  Thinking模式: DeepSeek-V4-Pro, GPT-4o, Claude-3, Gemini-1.5 ║
╚══════════════════════════════════════════════════════════════╝
"""
        
        return report


# 全局单例
_global_provider_manager: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    """获取全局 ProviderManager 单例"""
    global _global_provider_manager
    if _global_provider_manager is None:
        _global_provider_manager = ProviderManager()
        _global_provider_manager.load_config_from_encrypted()
    return _global_provider_manager


# 测试函数
async def test_provider_manager():
    """测试 ProviderManager"""
    print("🧪 测试 ProviderManager")
    print("="*60)
    
    manager = get_provider_manager()
    
    # 测试获取模型
    models = manager.get_models_for_capability(ModelCapability.REASONING, prefer_thinking=True)
    print(f"✅ 支持推理的模型数: {len(models)}")
    for m in models[:3]:
        print(f"   - {m.name} (Thinking: {m.supports_thinking})")
    
    # 测试指标报告
    print("\n📊 指标报告:")
    print(manager.generate_report())
    
    return True


if __name__ == "__main__":
    asyncio.run(test_provider_manager())