"""
local_service_driver.py — 本地服务驱动

连接本地运行的 OpenAI 兼容 API 服务，支持：
  - Ollama (http://localhost:11434)
  - LM Studio (http://localhost:1234)
  - vLLM Server (http://localhost:8000)
  - LMDeploy (http://localhost:23333)
  - 任何 OpenAI 兼容的本地服务

特点：
  - 模型管理由本地服务负责
  - 此驱动只负责 API 调用
  - 自动探测服务可用性
  - 支持流式 SSE
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Iterator, List, Optional

import httpx

from .base import (
    ChatRequest, ChatResponse, ChatMessage,
    CompletionRequest, CompletionResponse,
    EmbeddingRequest, EmbeddingResponse,
    StreamChunk, ModelDriver, DriverMode, DriverState,
    UsageInfo,
)

logger = logging.getLogger(__name__)


class LocalServiceDriver(ModelDriver):
    """
    本地服务驱动

    连接本地运行的 OpenAI 兼容 API 服务。
    """

    def __init__(
        self,
        name: str = "local_service",
        base_url: str = "http://localhost:11434",
        api_key: str = "",
        default_model: str = "",
        timeout: float = 120.0,
        connect_timeout: float = 10.0,
        keep_alive: str = "5m",
    ):
        super().__init__(name, DriverMode.LOCAL_SERVICE)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.keep_alive = keep_alive

        # 缓存
        self._models_cache: List[Dict[str, Any]] = []
        self._models_cache_time: float = 0.0
        self._cache_ttl: float = 60.0  # 模型列表缓存 60 秒

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

    # ── 生命周期 ─────────────────────────────────────────────

    def initialize(self) -> bool:
        """初始化：探测本地服务可用性"""
        self._set_state(DriverState.LOADING)
        try:
            with self._build_client(timeout=5.0) as c:
                r = c.get("/")
                if r.status_code == 200:
                    self._set_state(DriverState.READY)
                    logger.info(f"[LocalService] connected to {self.base_url}")
                    return True
                # 有些服务根路径返回其他内容，尝试 ping 端点
                r2 = c.get("/v1/models")
                if r2.status_code == 200:
                    self._set_state(DriverState.READY)
                    logger.info(f"[LocalService] connected to {self.base_url}")
                    return True
        except Exception as e:
            logger.error(f"[LocalService] connection failed: {e}")
        self._set_state(DriverState.ERROR)
        self._record_error(f"Cannot connect to {self.base_url}")
        return False

    def shutdown(self) -> None:
        self._set_state(DriverState.UNLOADED)
        logger.info("[LocalService] driver shut down")

    def health_check(self):
        from .base import HealthReport
        details = {"base_url": self.base_url}
        try:
            with self._build_client(timeout=3.0) as c:
                r = c.get("/")
                details["status_code"] = r.status_code
                healthy = r.status_code == 200
                if healthy:
                    self._error_count = 0
                    self._set_state(DriverState.READY)
                else:
                    self._set_state(DriverState.DEGRADED)
        except Exception as e:
            details["error"] = str(e)
            healthy = False
            self._set_state(DriverState.ERROR)
            self._record_error(str(e))

        return self._build_health(details)

    # ── 核心推理 ─────────────────────────────────────────────

    def chat(self, request: ChatRequest) -> ChatResponse:
        """同步对话"""
        if self._state != DriverState.READY:
            return ChatResponse(error=f"Driver not ready: {self._state.value}")

        t0 = time.time()
        model = request.model or self.default_model
        if not model:
            return ChatResponse(error="No model specified")

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

        try:
            with self._build_client() as c:
                r = c.post("/v1/chat/completions", json=payload)
                r.raise_for_status()
                data = r.json()

            latency = (time.time() - t0) * 1000
            self._record_success(latency)

            choices = data.get("choices", [])
            if not choices:
                return ChatResponse(error="No choices in response")

            choice = choices[0]
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
            latency = (time.time() - t0) * 1000
            self._record_error(str(e))
            return ChatResponse(error=str(e))

    def chat_stream(self, request: ChatRequest) -> Iterator[StreamChunk]:
        """流式对话"""
        if self._state != DriverState.READY:
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
                with c.stream("POST", "/v1/chat/completions", json=payload) as r:
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
                            done = finish in ("stop", "tool_calls")
                            yield StreamChunk(
                                delta=content_delta,
                                done=done,
                                reasoning=reasoning_delta,
                                tool_calls=tool_calls,
                                usage=UsageInfo(**parsed["usage"]) if parsed.get("usage") else None,
                            )
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            self._record_error(str(e))
            yield StreamChunk(error=str(e))

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

        try:
            with self._build_client() as c:
                r = c.post("/v1/completions", json=payload)
                r.raise_for_status()
                data = r.json()

            choices = data.get("choices", [])
            if not choices:
                return CompletionResponse(error="No choices in response")

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
            return CompletionResponse(error=str(e))

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
            with self._build_client(timeout=60.0) as c:
                r = c.post("/v1/embeddings", json=payload)
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
        """列出可用模型（带缓存）"""
        now = time.time()
        if self._models_cache and (now - self._models_cache_time) < self._cache_ttl:
            return self._models_cache

        try:
            with self._build_client(timeout=5.0) as c:
                r = c.get("/v1/models")
                r.raise_for_status()
                data = r.json()
                self._models_cache = data.get("data", [])
                self._models_cache_time = now
                return self._models_cache
        except Exception:
            return []

    def is_model_loaded(self, model: str) -> bool:
        """检查模型是否在本地服务中可用"""
        models = self.list_models()
        model_ids = {m.get("id") for m in models}
        return model in model_ids

    # ── Ollama 特有功能 ─────────────────────────────────────

    def ollama_preload(self, model: str, keep_alive: str | None = None) -> bool:
        """预加载 Ollama 模型（仅适用于 Ollama 服务）"""
        try:
            with self._build_client() as c:
                payload = {"model": model}
                if keep_alive or self.keep_alive:
                    payload["keep_alive"] = keep_alive or self.keep_alive
                r = c.post("/api/generate", json=payload)
                r.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"[LocalService] ollama preload failed: {e}")
            return False

    def ollama_unload(self, model: str) -> bool:
        """卸载 Ollama 模型"""
        try:
            with self._build_client() as c:
                r = c.post("/api/generate", json={"model": model, "keep_alive": 0})
                r.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"[LocalService] ollama unload failed: {e}")
            return False

    # ── 服务探测 ─────────────────────────────────────────────

    @staticmethod
    def detect_services(timeout: float = 2.0) -> List[Dict[str, str]]:
        """
        探测本地运行的 OpenAI 兼容服务

        Returns:
            [{"name": "...", "url": "...", "status": "ok/error"}, ...]
        """
        known_services = [
            ("Ollama", "http://localhost:11434"),
            ("LM Studio", "http://localhost:1234"),
            ("vLLM", "http://localhost:8000"),
            ("LMDeploy", "http://localhost:23333"),
            ("text-generation-webui", "http://localhost:5000"),
            ("TabbyAPI", "http://localhost:5001"),
        ]
        results = []
        for name, url in known_services:
            try:
                with httpx.Client(
                    base_url=url,
                    timeout=httpx.Timeout(timeout, connect=timeout),
                ) as c:
                    r = c.get("/")
                    if r.status_code == 200:
                        results.append({"name": name, "url": url, "status": "ok"})
                        continue
                # 尝试 /v1/models
                with httpx.Client(
                    base_url=url,
                    timeout=httpx.Timeout(timeout, connect=timeout),
                ) as c:
                    r = c.get("/v1/models")
                    if r.status_code == 200:
                        results.append({"name": name, "url": url, "status": "ok"})
                        continue
                results.append({"name": name, "url": url, "status": "no_response"})
            except Exception:
                results.append({"name": name, "url": url, "status": "unreachable"})
        return results
