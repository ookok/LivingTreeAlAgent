"""Web2API — turn AI web interfaces into OpenAI-compatible APIs.

12 providers registered:
  DeepSeek, Claude, Gemini, Kimi,
  通义千问, 智谱清言, 豆包, 讯飞星火, 百川, 元宝, MiniMax, 阶跃星辰
"""

from .base_provider import WebProvider, WebAccount, AccountPool, ProviderResult, AccountStatus
from .deepseek_provider import DeepSeekWebProvider
from .extended_providers import ClaudeWebProvider, GeminiWebProvider, KimiWebProvider
from .chinese_providers import (
    QwenWebProvider, GLMWebProvider, DoubaoWebProvider,
    SparkWebProvider, BaichuanWebProvider, YuanbaoWebProvider,
    MiniMaxWebProvider, StepChatWebProvider,
)
from .server import Web2APIServer, ProviderRegistry, get_web2api_server

__all__ = [
    "WebProvider", "WebAccount", "AccountPool", "ProviderResult", "AccountStatus",
    "DeepSeekWebProvider", "ClaudeWebProvider", "GeminiWebProvider", "KimiWebProvider",
    "QwenWebProvider", "GLMWebProvider", "DoubaoWebProvider",
    "SparkWebProvider", "BaichuanWebProvider", "YuanbaoWebProvider",
    "MiniMaxWebProvider", "StepChatWebProvider",
    "Web2APIServer", "ProviderRegistry", "get_web2api_server",
]
