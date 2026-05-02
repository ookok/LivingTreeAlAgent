# -*- coding: utf-8 -*-
"""
OpenAI Compatible Driver - 通用 OpenAI 兼容驱动器（本地服务）

连接任何提供 /v1/chat/completions 端点的本地服务。
与 CloudDriver 的区别：此驱动标记为 LOCAL_SERVICE 模式，
且不支持云端重试策略。
"""

from __future__ import annotations

import json
import logging
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
    OpenAI 兼容驱动器（本地服务模式）

    纯粹使用 /v1/* 端点，不管理模型生命周期。
    """

    def __init__(
        self,
        name: str = "local-openai-compat",
        base_url: str = "http://localhost:11434",
        api_key: str = "",
        default_model: str = "",
        timeout: float = 120.0,
        connect_timeout: float = 10.0,
        **kwargs,
    ):
        super().__init__(name, DriverMode.LOCAL_SERVICE)
        self.base_url = base_url.rstrip("/")
        # 确保 base_url 以 /v1 结尾
        if not self.base_url.endswith("/v1"):
            self.base_url = self.base_url + "/v1"
        self.api_key = api_key
        self.default_model = default_model
        self.timeout = timeout
        self.connect_timeout = connect_timeout

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_client(self, timeout: float | None = None) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout or self.timeout, connect=self.connect_timeout),
            headers=self._build_headers(),
        )

    # ── 生命周期 ──────────────────────────────────────────────

    def initialize(self) -> bool:
        """探测服务可用性"""
        self._set_state(DriverState.LOADING)
        try:
            with self._build_client(timeout=5.0) as c:
                r = c.get("/models")
                if r.status_code == 200:
                    self._set_state(DriverState.READY)
                    logger.info(f"[{self.name}] connected: {self.base_url}")
                    return True
                r2 = c.get("/")
                if r2.status_code == 200:
                    self._set_state(DriverState.READY)
                    return True
        except Exception as e:
            logger.debug(f"[{self.name}] connection check: {e}")
        # 本地服务可能稍后启动，也标记为 READY
        self._set_state(DriverState.READY)
        return True

    def shutdown(self) -> None:
        self._set_state(DriverState.UNLOADED)
        logger.info(f"[{self.name}] shut down")

    def health_check(self) -> HealthReport:
        details = {"base_url": self.base_url}
        try:
            with self._build_client(timeout=3.0) as c:
                r = c.get("/models")
                details["status_code"] = r.status_code
                if r.status_code == 200:
                    self._error_count = 0
                    self._set_state(DriverState.READY)
        except Exception as e:
            details["error"] = str(e)
            self._set_state(DriverState.DEGRADED)
        return self._build_health(details)

    # ── 推理接口 ──────────────────────────────────────────────

    def chat(self, request: ChatRequest) -> ChatResponse:
        """同步对话"""
        if self._state not in (DriverState.READY, DriverState.DEGRADED):
            return ChatResponse(error=f"Driver not ready: {self._state.value}")

        model = request.model or self.default_model
        if not model:
            return ChatResponse(error="No model specified")

        t0 = time.time()
        try:
            payload = {
                "model": model,
                "messages": [{"role": m.role, "content": m.content} for m in request.messages],
                "stream": False,
                "temperature": request.temperature,
                "top_p": request.top_p,
                "max_tokens": request.max_tokens,
            }
            if request.stop:
                payload["stop"] = request.stop
            if request.tools:
                payload["tools"] = request.tools

            with self._build_client() as c:
                r = c.post("/chat/completions", json=payload)
                r.raise_for_status()
                data = r.json()

            elapsed = (time.time() - t0) * 1000
            self._record_success(elapsed)

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            usage_data = data.get("usage", {})
            return ChatResponse(
                content=message.get("content", ""),
                reasoning=message.get("reasoning_content", "") or message.get("reasoning", ""),
                tool_calls=message.get("tool_calls"),
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
            return ChatResponse(error=str(e))

    def chat_stream(self, request: ChatRequest) -> Iterator[StreamChunk]:
        """流式对话"""
        if self._state not in (DriverState.READY, DriverState.DEGRADED):
            yield StreamChunk(error=f"Driver not ready: {self._state.value}")
            return

        model = request.model or self.default_model
        if not model:
            yield StreamChunk(error="No model specified")
            return

        payload = {
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
                                done=finish in ("stop", "tool_calls"),
                                reasoning=reasoning_delta,
                                tool_calls=delta.get("tool_calls"),
                                usage=UsageInfo(**parsed["usage"]) if parsed.get("usage") else None,
                            )
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            self._record_error(str(e))
            yield StreamChunk(error=str(e), done=True)

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """文本补全"""
        if self._state not in (DriverState.READY, DriverState.DEGRADED):
            return CompletionResponse(error=f"Driver not ready: {self._state.value}")
        model = request.model or self.default_model
        payload = {
            "model": model, "prompt": request.prompt, "stream": False,
            "temperature": request.temperature, "top_p": request.top_p,
            "max_tokens": request.max_tokens,
        }
        if request.stop:
            payload["stop"] = request.stop
        try:
            with self._build_client() as c:
                r = c.post("/completions", json=payload)
                r.raise_for_status()
                data = r.json()
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
        if self._state not in (DriverState.READY, DriverState.DEGRADED):
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
                r.raise_for_status()
                return r.json().get("data", [])
        except Exception:
            return []

    def is_model_loaded(self, model: str) -> bool:
        models = self.list_models()
        return model in {m.get("id") for m in models}
