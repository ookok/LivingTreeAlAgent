"""TreeLLM — Lightweight multi-provider LLM routing.

Usage:
    from livingtree.treellm import TreeLLM, create_deepseek_provider, create_longcat_provider

    llm = TreeLLM()
    llm.add_provider(create_deepsek_provider("sk-xxx"))
    llm.add_provider(create_longcat_provider("ak-xxx"))

    result = await llm.chat([{"role": "user", "content": "Hello"}])
    async for token in llm.stream([...]):
        print(token, end="")
"""

from .core import TreeLLM, RouterStats
from .providers import (
    Provider, ProviderResult,
    DeepSeekProvider, LongCatProvider, OpenAILikeProvider,
    create_deepseek_provider, create_longcat_provider,
)
from .classifier import TinyClassifier

__all__ = [
    "TreeLLM", "RouterStats",
    "Provider", "ProviderResult",
    "DeepSeekProvider", "LongCatProvider", "OpenAILikeProvider",
    "create_deepseek_provider", "create_longcat_provider",
    "TinyClassifier",
]
