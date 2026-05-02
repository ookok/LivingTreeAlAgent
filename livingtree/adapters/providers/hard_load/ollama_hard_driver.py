# -*- coding: utf-8 -*-
"""
Ollama 硬加载驱动器

通过 Ollama API 直接加载和管理本地 GGUF 模型。
使用 /v1/chat/completions (OpenAI 兼容) + /api/* (原生管理)。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Iterator, List, Optional

from ..base import (
    ChatMessage, ChatRequest, ChatResponse,
    CompletionRequest, CompletionResponse,
    EmbeddingRequest, EmbeddingResponse,
    StreamChunk, ModelDriver, DriverMode, DriverState,
    UsageInfo, HealthReport,
)

logger = logging.getLogger(__name__)


class OllamaHardDriver(ModelDriver):
    """
    Ollama 硬加载驱动器

    通过 Ollama 本地 API 加载/管理模型。
    区别于 LocalServiceDriver，此驱动使用 /api/* 端点管理模型生命周期。
    """

    def __init__(
        self,
        name: str = "ollama-hard",
        model: str = "",
        base_url: str = "http://localhost:11434",
        keep_alive: str = "5m",
        **kwargs,
    ):
        super().__init__(name, DriverMode.HARD_LOAD)
        self._model_id = model
        self.base_url = base_url.rstrip("/")
        self._keep_alive = keep_alive
        self._extra = kwargs

    @property
    def model_id(self) -> str:
        return self._model_id

    def _client(self, timeout: float = None) -> "httpx.Client":
        import httpx
        return httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout or 120.0, connect=10.0),
            headers={"Content-Type": "application/json"},
        )

    # ── 生命周期 ──────────────────────────────────────────────

    def initialize(self) -> bool:
        """预加载模型到 Ollama 内存"""
        self._set_state(DriverState.LOADING)
        if not self._model_id:
            self._set_state(DriverState.ERROR)
            self._record_error("No model specified")
            return False
        try:
            with self._client() as c:
                r = c.post("/api/generate", json={
                    "model": self._model_id,
                    "keep_alive": self._keep_alive,
                })
                r.raise_for_status()
            self._set_state(DriverState.READY)
            logger.info(f"[{self.name}] 模型已加载: {self._model_id}")
            return True
        except Exception as e:
            self._set_state(DriverState.ERROR)
            self._record_error(str(e))
            logger.error(f"[{self.name}] 加载失败: {e}")
            return False

    def shutdown(self) -> None:
        """卸载模型"""
        if self._model_id and self._state == DriverState.READY:
            try:
                with self._client(timeout=5.0) as c:
                    c.post("/api/generate", json={
                        "model": self._model_id,
                        "keep_alive": 0,
                    })
            except Exception:
                pass
        self._set_state(DriverState.UNLOADED)
        logger.info(f"[{self.name}] 模型已卸载")

    def health_check(self) -> HealthReport:
        """检查 Ollama 服务 + 模型可用性"""
        details = {"base_url": self.base_url, "model": self._model_id}
        try:
            with self._client(timeout=3.0) as c:
                r = c.get("/")
                if r.status_code != 200:
                    details["ollama_reachable"] = False
                    return self._build_health(details)
                if self._model_id:
                    r2 = c.post("/api/show", json={"name": self._model_id})
                    details["model_available"] = r2.status_code == 200
                details["ollama_reachable"] = True
                self._error_count = 0
        except Exception as e:
            details["error"] = str(e)
            details["ollama_reachable"] = False
            self._record_error(str(e))
        return self._build_health(details)

    # ── 推理接口 ──────────────────────────────────────────────

    def chat(self, request: ChatRequest) -> ChatResponse:
        """同步对话"""
        if self._state != DriverState.READY:
            return ChatResponse(error=f"Driver not ready: {self._state.value}")
        model = request.model or self._model_id
        if not model:
            return ChatResponse(error="No model specified")

        t0 = time.time()
        try:
            content, reasoning, tool_calls = "", "", None
            for chunk in self.chat_stream(request):
                if chunk.error:
                    return ChatResponse(error=chunk.error, model=model)
                content += chunk.delta
                reasoning += chunk.reasoning
                if chunk.tool_calls:
                    tool_calls = chunk.tool_calls

            elapsed = (time.time() - t0) * 1000
            self._record_success(elapsed)
            return ChatResponse(
                content=content, reasoning=reasoning,
                tool_calls=tool_calls, model=model,
            )
        except Exception as e:
            self._record_error(str(e))
            return ChatResponse(error=str(e), model=model)

    def chat_stream(self, request: ChatRequest) -> Iterator[StreamChunk]:
        """流式对话"""
        import httpx

        model = request.model or self._model_id
        if not model:
            yield StreamChunk(error="No model specified")
            return

        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if request.temperature != 0.7:
            payload["options"] = payload.get("options", {})
            payload["options"]["temperature"] = request.temperature
        if request.tools:
            payload["tools"] = request.tools

        try:
            with self._client() as c:
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
                            )
                        except json.JSONDecodeError:
                            continue
        except httpx.HTTPStatusError as e:
            yield StreamChunk(error=f"HTTP {e.response.status_code}", done=True)
        except Exception as e:
            self._record_error(str(e))
            yield StreamChunk(error=str(e), done=True)

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """文本补全"""
        chat_req = ChatRequest(
            messages=[ChatMessage(role="user", content=request.prompt)],
            model=request.model or self._model_id,
            temperature=request.temperature,
            top_p=request.top_p,
            max_tokens=request.max_tokens,
            stop=request.stop,
        )
        resp = self.chat(chat_req)
        return CompletionResponse(
            text=resp.content, usage=resp.usage,
            model=resp.model, finish_reason=resp.finish_reason,
            error=resp.error,
        )

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """通过 Ollama /api/embed 获取嵌入"""
        model = request.model or self._model_id
        try:
            with self._client(timeout=60.0) as c:
                embeddings = []
                for text in request.texts:
                    r = c.post("/api/embed", json={"model": model, "input": text})
                    r.raise_for_status()
                    data = r.json()
                    embeddings.append(data.get("embeddings", [[]])[0])
                return EmbeddingResponse(embeddings=embeddings, model=model)
        except Exception as e:
            self._record_error(str(e))
            return EmbeddingResponse(error=str(e))

    # ── 模型管理 ──────────────────────────────────────────────

    def list_models(self) -> List[Dict[str, Any]]:
        """列出 Ollama 已注册模型"""
        try:
            with self._client(timeout=3.0) as c:
                r = c.get("/api/tags")
                r.raise_for_status()
                return r.json().get("models", [])
        except Exception:
            return []

    def is_model_loaded(self, model: str) -> bool:
        """检查模型是否在 Ollama 中可用"""
        try:
            with self._client(timeout=3.0) as c:
                r = c.post("/api/show", json={"name": model or self._model_id})
                return r.status_code == 200
        except Exception:
            return False
