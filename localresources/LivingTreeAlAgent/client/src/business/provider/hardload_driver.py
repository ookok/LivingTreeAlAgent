"""
hardload_driver.py — 硬加载驱动

直接在进程内加载本地模型文件，支持：
  - GGUF (llama-cpp-python)
  - Ollama 本地模型 (通过 Ollama 本地进程)
  - vLLM (本地推理引擎)
  - Unsloth (高效微调推理)

此驱动无网络中间层，延迟最低，但资源消耗最大。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .base import (
    ChatRequest, ChatResponse, ChatMessage,
    CompletionRequest, CompletionResponse,
    EmbeddingRequest, EmbeddingResponse,
    StreamChunk, ModelDriver, DriverMode, DriverState,
    UsageInfo,
)

logger = logging.getLogger(__name__)


class HardLoadDriver(ModelDriver):
    """
    硬加载驱动

    通过 llama-cpp-python、vLLM、Unsloth 等在进程内直接加载模型。
    支持按需加载/卸载模型，模型预热。
    """

    # 后端类型
    BACKEND_LLAMA_CPP = "llama_cpp"
    BACKEND_OLLAMA = "ollama"
    BACKEND_VLLM = "vllm"
    BACKEND_UNSLOTH = "unsloth"

    def __init__(
        self,
        name: str = "hardload",
        backend: str = "llama_cpp",
        model_path: str = "",
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "",
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,
        n_threads: int = 4,
        use_mlock: bool = True,
        use_mmap: bool = True,
        verbose: bool = False,
    ):
        super().__init__(name, DriverMode.HARD_LOAD)
        self.backend = backend
        self.model_path = model_path
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.ollama_model = ollama_model
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.n_threads = n_threads
        self.use_mlock = use_mlock
        self.use_mmap = use_mmap
        self.verbose = verbose

        # 运行时状态
        self._engine = None           # 实际推理引擎实例
        self._current_model: str = ""
        self._lock = __import__("threading").Lock()

        # 可用性标记
        self._llama_cpp_available: Optional[bool] = None

    # ── 后端可用性检测 ────────────────────────────────────────

    def _check_llama_cpp(self) -> bool:
        """延迟检测 llama-cpp-python 是否可用"""
        if self._llama_cpp_available is not None:
            return self._llama_cpp_available
        try:
            from llama_cpp import Llama
            self._llama_cpp_available = True
        except ImportError:
            self._llama_cpp_available = False
        return self._llama_cpp_available

    # ── 生命周期 ─────────────────────────────────────────────

    def initialize(self) -> bool:
        """初始化硬加载驱动"""
        self._set_state(DriverState.LOADING)

        try:
            if self.backend == self.BACKEND_LLAMA_CPP:
                return self._init_llama_cpp()
            elif self.backend == self.BACKEND_OLLAMA:
                return self._init_ollama()
            elif self.backend == self.BACKEND_VLLM:
                return self._init_vllm()
            elif self.backend == self.BACKEND_UNSLOTH:
                return self._init_unsloth()
            else:
                self._set_state(DriverState.ERROR)
                self._record_error(f"Unknown backend: {self.backend}")
                return False
        except Exception as e:
            logger.error(f"[HardLoad] init failed: {e}")
            self._set_state(DriverState.ERROR)
            self._record_error(str(e))
            return False

    def _init_llama_cpp(self) -> bool:
        """初始化 llama-cpp-python"""
        if not self._check_llama_cpp():
            logger.warning("[HardLoad] llama-cpp-python not installed")
            self._set_state(DriverState.DEGRADED)
            self._record_error("llama-cpp-python not installed")
            return False

        model_path = Path(self.model_path)
        if not model_path.exists():
            logger.error(f"[HardLoad] model file not found: {model_path}")
            self._set_state(DriverState.ERROR)
            self._record_error(f"Model file not found: {model_path}")
            return False

        from llama_cpp import Llama

        logger.info(f"[HardLoad] loading GGUF: {model_path}")
        t0 = time.time()

        self._engine = Llama(
            model_path=str(model_path),
            n_ctx=self.n_ctx,
            n_gpu_layers=self.n_gpu_layers,
            n_threads=self.n_threads,
            use_mlock=self.use_mlock,
            use_mmap=self.use_mmap,
            verbose=self.verbose,
        )

        self._current_model = model_path.stem
        elapsed = time.time() - t0
        logger.info(f"[HardLoad] model loaded in {elapsed:.1f}s")
        self._set_state(DriverState.READY)
        return True

    def _init_ollama(self) -> bool:
        """通过 Ollama API 预加载模型"""
        try:
            import httpx
            model = self.ollama_model
            if not model:
                self._set_state(DriverState.ERROR)
                self._record_error("No ollama_model specified")
                return False

            # 预加载模型到内存
            logger.info(f"[HardLoad/Ollama] preloading: {model}")
            with httpx.Client(
                base_url=self.ollama_base_url,
                timeout=httpx.Timeout(120.0, connect=10.0),
            ) as c:
                r = c.post("/api/generate", json={"model": model, "keep_alive": "10m"})
                r.raise_for_status()

            self._current_model = model
            self._engine = "ollama"  # 标记为使用 Ollama
            self._set_state(DriverState.READY)
            return True
        except Exception as e:
            logger.error(f"[HardLoad/Ollama] preloading failed: {e}")
            self._set_state(DriverState.ERROR)
            self._record_error(str(e))
            return False

    def _init_vllm(self) -> bool:
        """初始化 vLLM 引擎（如果可用）"""
        try:
            from vllm import LLM, SamplingParams
            self._engine = LLM(model=self.model_path, trust_remote_code=True)
            self._sampling_params = SamplingParams()
            self._current_model = self.model_path
            self._set_state(DriverState.READY)
            return True
        except ImportError:
            logger.warning("[HardLoad] vllm not installed")
            self._set_state(DriverState.DEGRADED)
            self._record_error("vllm not installed")
            return False
        except Exception as e:
            self._set_state(DriverState.ERROR)
            self._record_error(str(e))
            return False

    def _init_unsloth(self) -> bool:
        """初始化 Unsloth 推理"""
        try:
            from unsloth import FastLanguageModel
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=self.model_path,
                max_seq_length=self.n_ctx,
                dtype=None,  # auto
                load_in_4bit=True,
            )
            FastLanguageModel.for_inference(model)
            self._engine = model
            self._tokenizer = tokenizer
            self._current_model = self.model_path
            self._set_state(DriverState.READY)
            return True
        except ImportError:
            logger.warning("[HardLoad] unsloth not installed")
            self._set_state(DriverState.DEGRADED)
            self._record_error("unsloth not installed")
            return False
        except Exception as e:
            self._set_state(DriverState.ERROR)
            self._record_error(str(e))
            return False

    def shutdown(self) -> None:
        """关闭驱动"""
        with self._lock:
            if self._engine and self._engine != "ollama":
                try:
                    del self._engine
                except Exception:
                    pass
            self._engine = None
            self._current_model = ""
            self._set_state(DriverState.UNLOADED)
            logger.info("[HardLoad] driver shut down")

    def health_check(self):
        from .base import HealthReport
        details = {
            "backend": self.backend,
            "model": self._current_model,
            "model_path": self.model_path,
        }
        if self.backend == self.BACKEND_LLAMA_CPP and self._engine:
            details["llama_cpp_loaded"] = True
        elif self.backend == self.BACKEND_OLLAMA:
            try:
                import httpx
                with httpx.Client(
                    base_url=self.ollama_base_url,
                    timeout=httpx.Timeout(3.0, connect=2.0),
                ) as c:
                    ok = c.get("/").status_code == 200
                details["ollama_reachable"] = ok
                if ok:
                    self._error_count = 0
            except Exception:
                details["ollama_reachable"] = False
        return self._build_health(details)

    # ── 核心推理 ─────────────────────────────────────────────

    def chat(self, request: ChatRequest) -> ChatResponse:
        """同步对话"""
        if self._state != DriverState.READY:
            return ChatResponse(error=f"Driver not ready: {self._state.value}")

        t0 = time.time()
        try:
            with self._lock:
                if self.backend == self.BACKEND_LLAMA_CPP:
                    result = self._chat_llama_cpp(request)
                elif self.backend == self.BACKEND_OLLAMA:
                    result = self._chat_ollama(request, stream=False)
                elif self.backend == self.BACKEND_VLLM:
                    result = self._chat_vllm(request)
                elif self.backend == self.BACKEND_UNSLOTH:
                    result = self._chat_unsloth(request)
                else:
                    return ChatResponse(error=f"Unsupported backend: {self.backend}")

            latency = (time.time() - t0) * 1000
            self._record_success(latency)
            result.model = result.model or self._current_model
            return result
        except Exception as e:
            self._record_error(str(e))
            return ChatResponse(error=str(e))

    def chat_stream(self, request: ChatRequest) -> Iterator[StreamChunk]:
        """流式对话"""
        if self._state != DriverState.READY:
            yield StreamChunk(error=f"Driver not ready: {self._state.value}")
            return

        try:
            if self.backend == self.BACKEND_LLAMA_CPP:
                for chunk in self._stream_llama_cpp(request):
                    yield chunk
            elif self.backend == self.BACKEND_OLLAMA:
                for chunk in self._chat_ollama(request, stream=True):
                    yield chunk
            elif self.backend == self.BACKEND_VLLM:
                yield StreamChunk(error="vLLM streaming not yet supported in hardload mode")
            elif self.backend == self.BACKEND_UNSLOTH:
                yield StreamChunk(error="Unsloth streaming not yet supported in hardload mode")
            else:
                yield StreamChunk(error=f"Unsupported backend: {self.backend}")
        except Exception as e:
            self._record_error(str(e))
            yield StreamChunk(error=str(e))

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """文本补全"""
        if self._state != DriverState.READY:
            return CompletionResponse(error=f"Driver not ready: {self._state.value}")

        # 转换为 chat 格式
        chat_req = ChatRequest(
            messages=[ChatMessage(role="user", content=request.prompt)],
            model=request.model,
            temperature=request.temperature,
            top_p=request.top_p,
            max_tokens=request.max_tokens,
            stop=request.stop,
            stream=False,
        )
        chat_resp = self.chat(chat_req)
        return CompletionResponse(
            text=chat_resp.content,
            usage=chat_resp.usage,
            model=chat_resp.model,
            finish_reason=chat_resp.finish_reason,
            error=chat_resp.error,
        )

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """文本嵌入"""
        if self.backend == self.BACKEND_OLLAMA:
            return self._embed_ollama(request)
        if self.backend == self.BACKEND_LLAMA_CPP and self._engine:
            try:
                result = self._engine.embed(texts=request.texts)
                return EmbeddingResponse(
                    embeddings=result["embeddings"] if isinstance(result, dict) else result,
                    model=self._current_model,
                )
            except Exception as e:
                self._record_error(str(e))
                return EmbeddingResponse(error=str(e))
        return EmbeddingResponse(error=f"Embedding not supported by backend: {self.backend}")

    # ── 模型管理 ─────────────────────────────────────────────

    def list_models(self) -> List[Dict[str, Any]]:
        if self.backend == self.BACKEND_OLLAMA:
            return self._list_ollama_models()
        if self.backend == self.BACKEND_LLAMA_CPP:
            return [{"name": self._current_model, "path": self.model_path, "backend": "llama_cpp"}]
        return []

    def is_model_loaded(self, model: str) -> bool:
        if not model:
            return self._state == DriverState.READY
        return model == self._current_model and self._state == DriverState.READY

    def load_model(self, model_path: str = "", model_name: str = "") -> bool:
        """运行时切换模型"""
        if model_path:
            self.model_path = model_path
        if model_name:
            self.ollama_model = model_name
        self.shutdown()
        return self.initialize()

    # ── llama-cpp 实现 ───────────────────────────────────────

    def _build_prompt(self, messages: List[ChatMessage]) -> str:
        """构建 llama.cpp 格式提示词"""
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

    def _chat_llama_cpp(self, request: ChatRequest) -> ChatResponse:
        """llama-cpp 同步对话"""
        prompt = self._build_prompt(request.messages)
        result = self._engine(
            prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            stop=request.stop,
            echo=False,
            stream=False,
        )
        text = result["choices"][0]["text"] if result.get("choices") else ""
        usage = result.get("usage", {})
        return ChatResponse(
            content=text,
            model=self._current_model,
            usage=UsageInfo(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
        )

    def _stream_llama_cpp(self, request: ChatRequest) -> Iterator[StreamChunk]:
        """llama-cpp 流式对话"""
        prompt = self._build_prompt(request.messages)
        stream = self._engine(
            prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            stop=request.stop,
            echo=False,
            stream=True,
        )
        for output in stream:
            delta = ""
            if "choices" in output:
                delta = output["choices"][0].get("delta", {}).get("content", "")
            if delta:
                yield StreamChunk(delta=delta)
        yield StreamChunk(done=True)

    # ── Ollama 实现（硬加载模式使用 Ollama 本地）────────────

    def _chat_ollama(self, request: ChatRequest, stream: bool = True):
        """通过 Ollama API 对话"""
        import httpx
        import json

        model = request.model or self.ollama_model
        if not model:
            if stream:
                yield StreamChunk(error="No model specified")
            else:
                return ChatResponse(error="No model specified")
            return

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": stream,
        }
        if request.temperature != 0.7:
            payload["options"] = payload.get("options", {})
            payload["options"]["temperature"] = request.temperature
        if request.tools:
            payload["tools"] = request.tools

        try:
            with httpx.Client(
                base_url=self.ollama_base_url,
                timeout=httpx.Timeout(120.0, connect=10.0),
            ) as c:
                with c.stream("POST", "/v1/chat/completions", json=payload) as r:
                    r.raise_for_status()
                    if stream:
                        for line in r.iter_lines():
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue
                            data = line[6:]
                            if data == "[DONE]":
                                yield StreamChunk(done=True)
                                return
                            try:
                                parsed = json.loads(data)
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
                                )
                            except json.JSONDecodeError:
                                continue
                    else:
                        # 同步模式：收集所有块
                        content, reasoning, tool_calls_list = "", "", None
                        for line in r.iter_lines():
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                parsed = json.loads(data)
                                choices = parsed.get("choices", [])
                                if not choices:
                                    continue
                                delta = choices[0].get("delta", {})
                                content += delta.get("content", "")
                                for key in ("reasoning", "thinking", "reasoning_content"):
                                    if key in delta:
                                        reasoning += delta[key]
                                if delta.get("tool_calls"):
                                    tool_calls_list = delta["tool_calls"]
                            except json.JSONDecodeError:
                                continue
                        return ChatResponse(
                            content=content,
                            reasoning=reasoning,
                            tool_calls=tool_calls_list,
                            model=model,
                        )
        except Exception as e:
            if stream:
                yield StreamChunk(error=str(e))
            else:
                return ChatResponse(error=str(e))

    def _embed_ollama(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """通过 Ollama API 获取嵌入"""
        import httpx
        try:
            with httpx.Client(
                base_url=self.ollama_base_url,
                timeout=httpx.Timeout(60.0),
            ) as c:
                embeddings = []
                for text in request.texts:
                    r = c.post("/api/embed", json={"model": self.ollama_model, "input": text})
                    r.raise_for_status()
                    data = r.json()
                    embeddings.append(data.get("embeddings", [[]])[0])
                return EmbeddingResponse(embeddings=embeddings, model=self._current_model)
        except Exception as e:
            self._record_error(str(e))
            return EmbeddingResponse(error=str(e))

    def _list_ollama_models(self) -> List[Dict[str, Any]]:
        """列出 Ollama 模型"""
        import httpx
        try:
            with httpx.Client(
                base_url=self.ollama_base_url,
                timeout=httpx.Timeout(3.0, connect=2.0),
            ) as c:
                r = c.get("/api/tags")
                r.raise_for_status()
                return r.json().get("models", [])
        except Exception:
            return []

    # ── vLLM 实现 ────────────────────────────────────────────

    def _chat_vllm(self, request: ChatRequest) -> ChatResponse:
        """vLLM 同步对话"""
        from vllm import SamplingParams

        prompt = self._build_prompt(request.messages)
        params = SamplingParams(
            temperature=request.temperature,
            top_p=request.top_p,
            max_tokens=request.max_tokens,
            stop=request.stop if request.stop else None,
        )
        outputs = self._engine.generate([prompt], params)
        text = outputs[0].outputs[0].text
        return ChatResponse(content=text, model=self._current_model)

    # ── Unsloth 实现 ─────────────────────────────────────────

    def _chat_unsloth(self, request: ChatRequest) -> ChatResponse:
        """Unsloth 同步对话"""
        prompt = self._build_prompt(request.messages)
        inputs = self._tokenizer(prompt, return_tensors="pt")
        outputs = self._engine.generate(**inputs, max_new_tokens=request.max_tokens)
        text = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
        return ChatResponse(content=text, model=self._current_model)
