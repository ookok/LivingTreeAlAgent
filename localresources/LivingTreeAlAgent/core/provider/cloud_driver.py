# -*- coding: utf-8 -*-
"""
cloud_driver.py — 云服务驱动门面

调用云端 API 服务，支持：
  - OpenAI (GPT-4o, GPT-4, GPT-3.5)
  - Anthropic (Claude 3.5/4 系列)
  - Google (Gemini)
  - DeepSeek
  - 阿里云百炼 (Qwen)
  - 任何 OpenAI 兼容的云端 API

通过 ProviderConfig 配置 API Key、base_url、默认参数。
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Iterator, List, Optional
from dataclasses import dataclass, field

from .base import (
    ChatRequest, ChatResponse, ChatMessage,
    CompletionRequest, CompletionResponse,
    EmbeddingRequest, EmbeddingResponse,
    StreamChunk, ModelDriver, DriverMode, DriverState,
    UsageInfo,
)

logger = logging.getLogger(__name__)


# ── 云服务提供商预设 ────────────────────────────────────────────

CLOUD_PROVIDERS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "env_key": "ANTHROPIC_API_KEY",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_key": "GOOGLE_API_KEY",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    },
    "aliyun": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "env_key": "DASHSCOPE_API_KEY",
        "models": ["qwen-plus", "qwen-turbo", "qwen-max"],
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "env_key": "ZHIPU_API_KEY",
        "models": ["glm-4-plus", "glm-4-flash", "glm-4"],
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "env_key": "MOONSHOT_API_KEY",
        "models": ["moonshot-v1-128k", "moonshot-v1-32k", "moonshot-v1-8k"],
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "env_key": "SILICONFLOW_API_KEY",
        "models": ["deepseek-ai/DeepSeek-V3"],
    },
}


class CloudDriver(ModelDriver):
    """
    云服务驱动

    通过 OpenAI 兼容 API 调用云端模型服务。
    """

    def __init__(
        self,
        name: str = "cloud",
        provider: str = "openai",
        base_url: str = "",
        api_key: str = "",
        api_key_env: str = "",
        default_model: str = "",
        timeout: float = 120.0,
        connect_timeout: float = 10.0,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        extra_params: Dict[str, Any] | None = None,
    ):
        super().__init__(name, DriverMode.CLOUD_SERVICE)

        # 提供商预设
        self.provider = provider
        preset = CLOUD_PROVIDERS.get(provider, {})

        self.base_url = (base_url or preset.get("base_url", "")).rstrip("/")
        # 确保 base_url 以 /v1 结尾
        if self.base_url and not self.base_url.endswith("/v1"):
            self.base_url = self.base_url + "/v1"

        self.api_key_env = api_key_env or preset.get("env_key", "")
        self._api_key = api_key
        self.default_model = default_model
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.extra_params = extra_params or {}

    def _get_api_key(self) -> str:
        """获取 API Key（优先显式传入，其次环境变量）"""
        if self._api_key:
            return self._api_key
        if self.api_key_env:
            key = os.environ.get(self.api_key_env, "")
            if key:
                self._api_key = key  # 缓存
        return self._api_key

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = self._get_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _build_client(self, timeout: float | None = None):
        import httpx
        return httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout or self.timeout, connect=self.connect_timeout),
            headers=self._build_headers(),
        )

    # ── 生命周期 ─────────────────────────────────────────────

    def initialize(self) -> bool:
        """初始化：验证 API Key 可用性"""
        self._set_state(DriverState.LOADING)
        api_key = self._get_api_key()
        if not api_key:
            logger.warning(f"[Cloud/{self.provider}] API Key not configured (env: {self.api_key_env})")
            self._set_state(DriverState.DEGRADED)
            self._record_error("API Key not configured")
            return False

        try:
            import httpx
            with httpx.Client(
                base_url=self.base_url,
                timeout=httpx.Timeout(5.0, connect=3.0),
                headers=self._build_headers(),
            ) as c:
                r = c.get("/models")
                if r.status_code == 200:
                    self._set_state(DriverState.READY)
                    logger.info(f"[Cloud/{self.provider}] initialized: {self.base_url}")
                    return True
                # 某些 API 不支持 /models，降级为 READY
                logger.info(f"[Cloud/{self.provider}] /models returned {r.status_code}, marking READY anyway")
                self._set_state(DriverState.READY)
                return True
        except Exception as e:
            logger.warning(f"[Cloud/{self.provider}] init check failed: {e}")
            # 云服务可能在运行时才需要连接，标记为 READY
            self._set_state(DriverState.READY)
            return True

    def shutdown(self) -> None:
        self._set_state(DriverState.UNLOADED)
        logger.info(f"[Cloud/{self.provider}] driver shut down")

    def health_check(self):
        from .base import HealthReport
        api_key = self._get_api_key()
        details = {
            "provider": self.provider,
            "base_url": self.base_url,
            "has_api_key": bool(api_key),
            "default_model": self.default_model,
        }
        try:
            import httpx
            with httpx.Client(
                base_url=self.base_url,
                timeout=httpx.Timeout(5.0, connect=3.0),
                headers=self._build_headers(),
            ) as c:
                r = c.get("/models")
                details["status_code"] = r.status_code
                if r.status_code == 200:
                    self._error_count = 0
                    self._set_state(DriverState.READY)
        except Exception as e:
            details["error"] = str(e)

        return self._build_health(details)

    # ── 核心推理 ─────────────────────────────────────────────

    def chat(self, request: ChatRequest) -> ChatResponse:
        """同步对话（收集流式响应）"""
        if self._state != DriverState.READY:
            return ChatResponse(error=f"Driver not ready: {self._state.value}")

        content, reasoning, tool_calls = "", "", None
        usage_info = None
        model = request.model or self.default_model
        if not model:
            return ChatResponse(error="No model specified")
        if not self._get_api_key():
            return ChatResponse(error=f"API Key not configured for {self.provider}")

        start = time.time()
        try:
            for chunk in self.chat_stream(request):
                if chunk.error:
                    return ChatResponse(
                        error=chunk.error,
                        model=model,
                    )
                content += chunk.delta
                reasoning += chunk.reasoning
                if chunk.tool_calls:
                    tool_calls = chunk.tool_calls
                if chunk.usage:
                    usage_info = chunk.usage
        except Exception as e:
            self._record_error(str(e))
            return ChatResponse(error=str(e), model=model)

        elapsed = (time.time() - start) * 1000
        self._record_success(elapsed)
        return ChatResponse(
            content=content,
            reasoning=reasoning,
            tool_calls=tool_calls,
            usage=usage_info or UsageInfo(),
            model=model,
            finish_reason="stop",
        )

    def chat_stream(self, request: ChatRequest) -> Iterator[StreamChunk]:
        """流式对话"""
        import httpx

        if self._state != DriverState.READY:
            yield StreamChunk(error=f"Driver not ready: {self._state.value}")
            return

        model = request.model or self.default_model
        if not model:
            yield StreamChunk(error="No model specified")
            return

        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": True,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
        }
        if request.stop:
            payload["stop"] = request.stop
        if request.tools:
            payload["tools"] = request.tools

        # 合并提供商特定默认参数
        for k, v in self.extra_params.items():
            if k not in payload:
                payload[k] = v

        last_error = ""
        for attempt in range(self.max_retries + 1):
            try:
                with self._build_client() as c:
                    with c.stream("POST", "/chat/completions", json=payload) as r:
                        r.raise_for_status()
                        for line in r.iter_lines():
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                yield StreamChunk(done=True)
                                return
                            try:
                                parsed = json.loads(data_str)
                                choices = parsed.get("choices", [])
                                if not choices:
                                    continue
                                delta = choices[0].get("delta", {})
                                finish = choices[0].get("finish_reason", "")

                                content_delta = delta.get("content", "")
                                reasoning_delta = ""
                                for key in ("reasoning", "thinking", "reasoning_content"):
                                    if key in delta:
                                        reasoning_delta = delta[key]
                                        break

                                tool_calls = delta.get("tool_calls")
                                done = finish in ("stop", "tool_calls", "end_turn")
                                usage = parsed.get("usage")

                                yield StreamChunk(
                                    delta=content_delta,
                                    done=done,
                                    reasoning=reasoning_delta,
                                    tool_calls=tool_calls,
                                    usage=UsageInfo(**usage) if usage else None,
                                )
                                if done:
                                    return
                            except json.JSONDecodeError:
                                continue
                return  # 成功完成
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}"
                try:
                    error_body = e.response.json()
                    last_error += f": {error_body.get('error', {}).get('message', '')}"
                except Exception:
                    pass
                if attempt < self.max_retries and e.response.status_code >= 500:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                break
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                break

        self._record_error(last_error)
        yield StreamChunk(error=last_error, done=True)

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """文本补全"""
        if self._state != DriverState.READY:
            return CompletionResponse(error=f"Driver not ready: {self._state.value}")

        model = request.model or self.default_model
        if not model:
            return CompletionResponse(error="No model specified")

        payload = {
            "model": model,
            "prompt": request.prompt,
            "stream": False,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
        }
        if request.stop:
            payload["stop"] = request.stop

        start = time.time()
        try:
            import httpx
            with self._build_client() as c:
                r = c.post("/completions", json=payload)
                r.raise_for_status()
                data = r.json()

            elapsed = (time.time() - start) * 1000
            self._record_success(elapsed)

            choices = data.get("choices", [])
            if not choices:
                return CompletionResponse(error="No choices in response", model=model)

            usage_data = data.get("usage", {})
            return CompletionResponse(
                text=choices[0].get("text", ""),
                model=data.get("model", model),
                finish_reason=choices[0].get("finish_reason", ""),
                usage=UsageInfo(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                ),
            )
        except Exception as e:
            self._record_error(str(e))
            return CompletionResponse(error=str(e), model=model)

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """文本嵌入"""
        if self._state != DriverState.READY:
            return EmbeddingResponse(error=f"Driver not ready: {self._state.value}")

        model = request.model or self.default_model
        payload = {
            "model": model,
            "input": request.texts,
            "encoding_format": request.encoding_format,
        }

        try:
            import httpx
            with self._build_client(timeout=60.0) as c:
                r = c.post("/embeddings", json=payload)
                r.raise_for_status()
                data = r.json()

            embeddings = [item["embedding"] for item in data.get("data", [])]
            usage_data = data.get("usage", {})
            return EmbeddingResponse(
                embeddings=embeddings,
                model=data.get("model", model),
                usage=UsageInfo(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                ),
            )
        except Exception as e:
            self._record_error(str(e))
            return EmbeddingResponse(error=str(e))

    # ── 模型管理 ─────────────────────────────────────────────

    def list_models(self) -> List[Dict[str, Any]]:
        """列出可用模型"""
        try:
            import httpx
            with self._build_client(timeout=5.0) as c:
                r = c.get("/models")
                if r.status_code == 200:
                    data = r.json()
                    return data.get("data", [])
        except Exception:
            pass
        # 返回预设模型列表
        preset = CLOUD_PROVIDERS.get(self.provider, {})
        return [{"id": m, "provider": self.provider} for m in preset.get("models", [])]

    def is_model_loaded(self, model: str) -> bool:
        """云服务始终认为模型可用（按需调用）"""
        if not model:
            return bool(self.default_model)
        models = self.list_models()
        model_ids = {m.get("id") for m in models}
        return model in model_ids

    # ── 便捷工厂 ─────────────────────────────────────────────

    @classmethod
    def from_provider(cls, provider: str, api_key: str = "", default_model: str = "", **kwargs) -> "CloudDriver":
        """
        通过提供商名称快速创建驱动

        Args:
            provider: 提供商名称 (openai/anthropic/deepseek/google/aliyun/zhipu/moonshot/siliconflow)
            api_key: API Key (为空则从环境变量读取)
            default_model: 默认模型
            **kwargs: 其他参数传递给 __init__
        """
        preset = CLOUD_PROVIDERS.get(provider, {})
        return cls(
            provider=provider,
            base_url=kwargs.pop("base_url", ""),
            api_key=api_key,
            api_key_env=kwargs.pop("api_key_env", preset.get("env_key", "")),
            default_model=default_model or (preset.get("models", [""])[0] if preset else ""),
            **kwargs,
        )
