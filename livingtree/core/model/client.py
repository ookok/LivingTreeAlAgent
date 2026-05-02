"""
LivingTree — Unified LLM Client
=================================

Unified client that auto-selects DeepSeek, Ollama, or OpenAI-compatible providers.
DeepSeek is the primary production provider.
"""

from typing import Optional, List, Dict, Any
from .router import (
    UnifiedModelRouter, UnifiedModelClient, ComputeTier,
    AIResponse, get_model_router, get_model_client,
)


def _make_req(model, messages, temperature, max_tokens):
    from livingtree.adapters.providers.ollama import ChatCompletionRequest
    return ChatCompletionRequest(
        model=model, messages=messages,
        temperature=temperature, max_tokens=max_tokens,
    )


class ProductionLLMClient:
    """
    Production-grade LLM Client — DeepSeek primary, Ollama fallback.

    Usage:
        client = ProductionLLMClient()
        resp = client.chat_sync("Hello, who are you?")
        print(resp.content)
    """

    def __init__(self):
        from livingtree.infrastructure.config import get_config
        self.config = get_config()

        self._deepseek = None
        self._ollama = None

        if self.config.deepseek.api_key:
            from livingtree.adapters.providers.deepseek import DeepSeekProvider as _DSP
            self._deepseek = _DSP(
                api_key=self.config.deepseek.api_key,
                base_url=self.config.deepseek.base_url,
                default_model=self.config.deepseek.default_model,
            )

        if self.config.ollama.base_url:
            from livingtree.adapters.providers.ollama import OllamaProvider
            self._ollama = OllamaProvider(base_url=self.config.ollama.base_url)

    @property
    def available(self) -> bool:
        return self._deepseek is not None

    @property
    def default_model(self) -> str:
        if self._deepseek:
            return self.config.deepseek.default_model
        return self.config.ollama.default_model or "qwen2.5:7b"

    def _resolve_model(self, model: str) -> tuple:
        """Resolve model to (actual_model, provider).
        Maps Ollama model names to DeepSeek when DeepSeek is available."""
        if self._deepseek and (not model or ":" in model or "qwen" in model.lower()):
            return self.config.deepseek.default_model, "deepseek"
        if self._deepseek:
            return model, "deepseek"
        return model or self.config.ollama.default_model or "qwen2.5:7b", "ollama"

    def chat_sync(self, prompt: str, model: str = "",
                  temperature: float = 0.7, max_tokens: int = 8192,
                  enable_thinking: bool = False,
                  history: Optional[List[Dict[str, str]]] = None) -> str:
        messages = list(history) if history else []
        messages.append({"role": "user", "content": prompt})
        resolved_model, provider = self._resolve_model(model)

        if provider == "deepseek" and self._deepseek:
            resp = self._deepseek.chat_sync(
                _make_req(resolved_model, messages, temperature, max_tokens),
                enable_thinking=enable_thinking)
            if resp.success:
                return resp.content

        if self._ollama:
            resp = self._ollama.chat_sync(
                _make_req(resolved_model, messages, temperature, max_tokens))
            if resp.success:
                return resp.content

        return f"[LLM unavailable] Prompt: {prompt[:100]}"

    async def chat_async(self, prompt: str, model: str = "",
                         temperature: float = 0.7, max_tokens: int = 8192,
                         enable_thinking: bool = False,
                         history: Optional[List[Dict[str, str]]] = None) -> str:
        messages = list(history) if history else []
        messages.append({"role": "user", "content": prompt})
        resolved_model, provider = self._resolve_model(model)

        if provider == "deepseek" and self._deepseek:
            resp = await self._deepseek.chat(
                _make_req(resolved_model, messages, temperature, max_tokens),
                enable_thinking=enable_thinking)
            if resp.success:
                return resp.content

        if self._ollama:
            resp = await self._ollama.chat(
                _make_req(resolved_model, messages, temperature, max_tokens))
            if resp.success:
                return resp.content

        return f"[LLM unavailable] Prompt: {prompt[:100]}"


def get_production_llm_client() -> ProductionLLMClient:
    """获取生产级 LLM 客户端单例"""
    global _production_llm_client
    if _production_llm_client is None:
        _production_llm_client = ProductionLLMClient()
    return _production_llm_client


_production_llm_client: Optional[ProductionLLMClient] = None


__all__ = ["ProductionLLMClient", "get_production_llm_client"]
