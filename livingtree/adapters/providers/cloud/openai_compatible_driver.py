# -*- coding: utf-8 -*-
"""
Cloud OpenAI Compatible Driver - 云服务 OpenAI 兼容驱动器

与 local_service 版本的区别：
  - 标记 mode=CLOUD_SERVICE
  - 支持更严格的超时和重试策略
  - 支持 API Key 环境变量自动发现
  - 提供 CloudDriver 门面已包含预设提供商配置

此子模块供 gateway/config_manager 动态创建使用。
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Iterator, List

import httpx

from ..base import (
    ChatRequest, ChatResponse, ChatMessage,
    CompletionRequest, CompletionResponse,
    EmbeddingRequest, EmbeddingResponse,
    StreamChunk, ModelDriver, DriverMode, DriverState,
    UsageInfo, HealthReport,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleDriver(ModelDriver):
    """
    云服务 OpenAI 兼容驱动器

    用于调用任何 OpenAI 兼容的云端 API。
    """

    def __init__(
        self,
        name: str = "cloud-openai-compat",
        base_url: str = "",
        api_key: str = "",
        api_key_env: str = "",
        default_model: str = "",
        timeout: float = 120.0,
        connect_timeout: float = 10.0,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        extra_params: Dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(name, DriverMode.CLOUD_SERVICE)
        self.base_url = base_url.rstrip("/")
        if self.base_url and not self.base_url.endswith("/v1"):
            self.base_url = self.base_url + "/v1"
        self._api_key = api_key
        self.api_key_env = api_key_env
        self.default_model = default_model
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.extra_params = extra_params or {}

    def _get_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        if self.api_key_env:
            key = os.environ.get(self.api_key_env, "")
            if key:
                self._api_key = key
        return self._api_key

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = self._get_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _build_client(self, timeout: float | None = None) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout or self.timeout, connect=self.connect_timeout),
            headers=self._build_headers(),
        )

    # ── 生命周期 ──────────────────────────────────────────────

    def initialize(self) -> bool:
        """验证 API Key 可用性"""
        self._set_state(DriverState.LOADING)
        if not self._get_api_key():
            logger.warning(f"[{self.name}] API Key not configured (env: {self.api_key_env})")
            self._set_state(DriverState.DEGRADED)
            self._record_error("API Key not configured")
            return False
        # 云服务标记为 READY 即可
        self._set_state(DriverState.READY)
        return True

    def shutdown(self) -> None:
        self._set_state(DriverState.UNLOADED)

    def health_check(self) -> HealthReport:
        details = {
            "base_url": self.base_url,
            "has_api_key": bool(self._get_api_key()),
            "default_model": self.default_model,
        }
        try:
            with self._build_client(timeout=5.0) as c:
                r = c.get("/models")
                details["status_code"] = r.status_code
                if r.status_code == 200:
                    self._error_count = 0
        except Exception as e:
            details["error"] = str(e)
        return self._build_health(details)

    # ── 推理接口 ──────────────────────────────────────────────

    def chat(self, request: ChatRequest) -> ChatResponse:
        """同步对话（收集流式）"""
        if self._state != DriverState.READY:
            return ChatResponse(error=f"Driver not ready: {self._state.value}")
        model = request.model or self.default_model
        if not model:
            return ChatResponse(error="No model specified")
        if not self._get_api_key():
            return ChatResponse(error="API Key not configured")

        t0 = time.time()
        content, reasoning, tool_calls = "", "", None
        usage_info = None
        try:
            for chunk in self.chat_stream(request):
                if chunk.error:
                    return ChatResponse(error=chunk.error, model=model)
                content += chunk.delta
                reasoning += chunk.reasoning
                if chunk.tool_calls:
                    tool_calls = chunk.tool_calls
                if chunk.usage:
                    usage_info = chunk.usage
            elapsed = (time.time() - t0) * 1000
            self._record_success(elapsed)
            return ChatResponse(
                content=content, reasoning=reasoning,
                tool_calls=tool_calls, usage=usage_info or UsageInfo(),
                model=model, finish_reason="stop",
            )
        except Exception as e:
            self._record_error(str(e))
            return ChatResponse(error=str(e), model=model)

    def chat_stream(self, request: ChatRequest) -> Iterator[StreamChunk]:
        """流式对话（带重试）"""
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
                                reasoning_delta = ""
                                for key in ("reasoning", "thinking", "reasoning_content"):
                                    if key in delta:
                                        reasoning_delta = delta[key]
                                        break
                                yield StreamChunk(
                                    delta=delta.get("content", ""),
                                    done=finish in ("stop", "tool_calls", "end_turn"),
                                    reasoning=reasoning_delta,
                                    tool_calls=delta.get("tool_calls"),
                                    usage=UsageInfo(**parsed["usage"]) if parsed.get("usage") else None,
                                )
                                if finish in ("stop", "tool_calls", "end_turn"):
                                    return
                            except json.JSONDecodeError:
                                continue
                return
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}"
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
        payload = {
            "model": model, "prompt": request.prompt, "stream": False,
            "temperature": request.temperature, "top_p": request.top_p,
            "max_tokens": request.max_tokens,
        }
        if request.stop:
            payload["stop"] = request.stop
        t0 = time.time()
        try:
            with self._build_client() as c:
                r = c.post("/completions", json=payload)
                r.raise_for_status()
                data = r.json()
            elapsed = (time.time() - t0) * 1000
            self._record_success(elapsed)
            choice = data.get("choices", [{}])[0]
            usage_data = data.get("usage", {})
            return CompletionResponse(
                text=choice.get("text", ""),
                model=data.get("model", model),
                finish_reason=choice.get("finish_reason", ""),
                usage=UsageInfo(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                ),
            )
        except Exception as e:
            self._record_error(str(e))
            return CompletionResponse(error=str(e))

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """文本嵌入"""
        if self._state != DriverState.READY:
            return EmbeddingResponse(error="Driver not ready")
        model = request.model or self.default_model
        payload = {"model": model, "input": request.texts, "encoding_format": request.encoding_format}
        try:
            with self._build_client(timeout=60.0) as c:
                r = c.post("/embeddings", json=payload)
                r.raise_for_status()
                data = r.json()
            embeddings = [item["embedding"] for item in data.get("data", [])]
            usage_data = data.get("usage", {})
            return EmbeddingResponse(
                embeddings=embeddings, model=data.get("model", model),
                usage=UsageInfo(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                ),
            )
        except Exception as e:
            self._record_error(str(e))
            return EmbeddingResponse(error=str(e))

    # ── 模型管理 ──────────────────────────────────────────────

    def list_models(self) -> List[Dict[str, Any]]:
        try:
            with self._build_client(timeout=5.0) as c:
                r = c.get("/models")
                if r.status_code == 200:
                    return r.json().get("data", [])
        except Exception:
            pass
        return []

    def is_model_loaded(self, model: str) -> bool:
        if not model:
            return bool(self.default_model)
        models = self.list_models()
        return model in {m.get("id") for m in models}
