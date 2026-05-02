# -*- coding: utf-8 -*-
"""
llama-cpp-python 硬加载驱动器

直接加载 GGUF 模型文件进行推理，无需 Ollama 等中间服务。
支持 GPU 加速 (n_gpu_layers)、流式/同步推理。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List

from ..base import (
    ChatMessage, ChatRequest, ChatResponse,
    CompletionRequest, CompletionResponse,
    EmbeddingRequest, EmbeddingResponse,
    StreamChunk, ModelDriver, DriverMode, DriverState,
    UsageInfo, HealthReport,
)

logger = logging.getLogger(__name__)

# 延迟检测 llama-cpp-python
_LLAMA_CPP_AVAILABLE = False
_Llama = None


def _check_llama_cpp() -> bool:
    global _LLAMA_CPP_AVAILABLE, _Llama
    if _LLAMA_CPP_AVAILABLE:
        return True
    try:
        from llama_cpp import Llama
        _Llama = Llama
        _LLAMA_CPP_AVAILABLE = True
        return True
    except ImportError:
        logger.warning("llama-cpp-python not installed")
        return False


class LlamaCppHardDriver(ModelDriver):
    """
    llama-cpp-python 硬加载驱动器

    直接加载 GGUF 文件，不依赖外部服务。
    """

    def __init__(
        self,
        name: str = "llama-cpp-hard",
        model_path: str = "",
        model: str = "",
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,
        n_threads: int = 4,
        use_mlock: bool = True,
        use_mmap: bool = True,
        verbose: bool = False,
        **kwargs,
    ):
        super().__init__(name, DriverMode.HARD_LOAD)
        self._model_id = model or (Path(model_path).stem if model_path else "")
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.n_threads = n_threads
        self.use_mlock = use_mlock
        self.use_mmap = use_mmap
        self.verbose = verbose
        self._llama = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def _build_prompt(self, messages: List[ChatMessage]) -> str:
        """构建 ChatML 格式提示词"""
        parts = []
        for msg in messages:
            if msg.role == "system":
                parts.append(f"<|im_start|>system\n{msg.content}<|im_end|>\n")
            elif msg.role == "user":
                parts.append(f"<|im_start|>user\n{msg.content}<|im_end|>\n")
            elif msg.role == "assistant":
                parts.append(f"<|im_start|>assistant\n{msg.content}<|im_end|>\n")
        parts.append("<|im_start|>assistant\n")
        return "".join(parts)

    # ── 生命周期 ──────────────────────────────────────────────

    def initialize(self) -> bool:
        """加载 GGUF 模型"""
        self._set_state(DriverState.LOADING)

        if not _check_llama_cpp():
            self._set_state(DriverState.DEGRADED)
            self._record_error("llama-cpp-python not installed")
            return False

        model_path = Path(self.model_path)
        if not model_path.exists():
            self._set_state(DriverState.ERROR)
            self._record_error(f"Model file not found: {model_path}")
            return False

        try:
            t0 = time.time()
            self._llama = _Llama(
                model_path=str(model_path),
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                n_threads=self.n_threads,
                use_mlock=self.use_mlock,
                use_mmap=self.use_mmap,
                verbose=self.verbose,
            )
            elapsed = time.time() - t0
            self._set_state(DriverState.READY)
            logger.info(f"[{self.name}] 模型加载完成: {model_path.name} ({elapsed:.1f}s)")
            return True
        except Exception as e:
            self._set_state(DriverState.ERROR)
            self._record_error(str(e))
            logger.error(f"[{self.name}] 加载失败: {e}")
            return False

    def shutdown(self) -> None:
        """卸载模型"""
        if self._llama:
            try:
                del self._llama
            except Exception:
                pass
            self._llama = None
        self._set_state(DriverState.UNLOADED)
        logger.info(f"[{self.name}] 模型已卸载")

    def health_check(self) -> HealthReport:
        """检查模型是否已加载"""
        return self._build_health({
            "backend": "llama_cpp",
            "model": self._model_id,
            "model_path": self.model_path,
            "loaded": self._llama is not None,
        })

    # ── 推理接口 ──────────────────────────────────────────────

    def chat(self, request: ChatRequest) -> ChatResponse:
        """同步对话"""
        if self._state != DriverState.READY or not self._llama:
            return ChatResponse(error=f"Driver not ready: {self._state.value}")

        prompt = self._build_prompt(request.messages)
        t0 = time.time()
        try:
            result = self._llama(
                prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                stop=request.stop or [],
                stream=False,
            )
            elapsed = (time.time() - t0) * 1000
            self._record_success(elapsed)

            content = ""
            if result.get("choices"):
                content = result["choices"][0].get("text", "")
            usage_data = result.get("usage", {})
            return ChatResponse(
                content=content,
                model=self._model_id,
                usage=UsageInfo(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                ),
            )
        except Exception as e:
            self._record_error(str(e))
            return ChatResponse(error=str(e), model=self._model_id)

    def chat_stream(self, request: ChatRequest) -> Iterator[StreamChunk]:
        """流式对话"""
        if self._state != DriverState.READY or not self._llama:
            yield StreamChunk(error=f"Driver not ready: {self._state.value}")
            return

        prompt = self._build_prompt(request.messages)
        try:
            stream = self._llama(
                prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                stop=request.stop or [],
                stream=True,
            )
            for output in stream:
                delta = ""
                if "choices" in output:
                    choices = output["choices"]
                    if choices:
                        delta = choices[0].get("delta", {}).get("content", "")
                        if not delta:
                            delta = choices[0].get("text", "")
                if delta:
                    yield StreamChunk(delta=delta)
            yield StreamChunk(done=True)
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
        """文本嵌入"""
        if self._state != DriverState.READY or not self._llama:
            return EmbeddingResponse(error="Driver not ready")
        try:
            result = self._llama.embed(texts=request.texts)
            embeddings = result["embeddings"] if isinstance(result, dict) else result
            return EmbeddingResponse(embeddings=embeddings, model=self._model_id)
        except Exception as e:
            self._record_error(str(e))
            return EmbeddingResponse(error=str(e))

    # ── 模型管理 ──────────────────────────────────────────────

    def list_models(self) -> List[Dict[str, Any]]:
        """返回当前加载的模型"""
        if self._state == DriverState.READY:
            return [{"name": self._model_id, "path": self.model_path, "backend": "llama_cpp"}]
        return []

    def is_model_loaded(self, model: str) -> bool:
        if not model:
            return self._state == DriverState.READY and self._llama is not None
        return model == self._model_id and self._llama is not None
