"""
Ollama API 客户端
基于 OpenAI-Compatible 接口，支持流式 SSE
参考 hermes-agent 的模型调用架构
"""

import json
import time
from typing import Callable, Iterator, Optional
from dataclasses import dataclass, field

import httpx

from core.config import OllamaConfig


# ── 数据模型 ────────────────────────────────────────────────────────

@dataclass
class OllamaModel:
    """Ollama 模型条目"""
    name: str
    size: int = 0
    digest: str = ""
    modified_at: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class ModelInfo:
    """从 /api/show 获取的模型详细信息"""
    name: str
    num_ctx: int = 8192
    num_gpu: int = 0
    num_params: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class StreamChunk:
    """流式响应块"""
    delta: str = ""
    done: bool = False
    reasoning: str = ""
    tool_calls: list[dict] | None = None
    error: str = ""
    usage: dict | None = None


# ── SSE 解析器（轻量，无外部依赖）───────────────────────────────────

class _SSEDecoder:
    """简单 SSE 解析器"""
    @staticmethod
    def iter_sse(response: httpx.Response) -> Iterator[dict]:
        """从 HTTP 响应迭代解析 SSE 事件"""
        for line in response.iter_lines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue


# ── Ollama 客户端 ───────────────────────────────────────────────────

class OllamaClient:
    """
    Ollama API 客户端（OpenAI-Compatible）
    支持：
    - 标准 chat completions（/v1/chat/completions）
    - SSE 流式响应
    - 模型列表 / 模型信息 / 加载 / 卸载
    """

    def __init__(self, config: OllamaConfig):
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self._num_ctx_cache: dict[str, int] = {}

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(120.0, connect=10.0),
            headers={"Content-Type": "application/json"},
        )

    # ── 模型管理 ────────────────────────────────────────────────

    def list_models(self) -> list[OllamaModel]:
        """列出 Ollama 已注册的模型"""
        try:
            with self._client() as c:
                r = c.get("/api/tags")
                r.raise_for_status()
                return [OllamaModel(**m) for m in r.json().get("models", [])]
        except Exception:
            return []

    def get_model_info(self, name: str) -> ModelInfo:
        """获取模型详细信息（自动缓存 num_ctx）"""
        if name in self._num_ctx_cache:
            return ModelInfo(name=name, num_ctx=self._num_ctx_cache[name])

        try:
            with self._client() as c:
                r = c.post("/api/show", json={"name": name})
                r.raise_for_status()
                d = r.json()
                info = ModelInfo(
                    name=name,
                    num_ctx=d.get("context_length", self.config.num_ctx),
                    num_gpu=d.get("num_gpu", self.config.num_gpu),
                    num_params=d.get("parameters", ""),
                    extra=d,
                )
                self._num_ctx_cache[name] = info.num_ctx
                return info
        except Exception:
            return ModelInfo(name=name, num_ctx=self.config.num_ctx)

    def load_model(self, name: str, keep_alive: str | None = None) -> bool:
        """加载模型到内存"""
        try:
            with self._client() as c:
                payload = {"model": name}
                if keep_alive is not None:
                    payload["keep_alive"] = keep_alive
                elif self.config.keep_alive:
                    payload["keep_alive"] = self.config.keep_alive
                r = c.post("/api/generate", json=payload)
                r.raise_for_status()
                return True
        except Exception:
            return False

    def unload_model(self, name: str) -> bool:
        """卸载模型（keep_alive=0）"""
        try:
            with self._client() as c:
                r = c.post("/api/generate", json={"model": name, "keep_alive": 0})
                r.raise_for_status()
                return True
        except Exception:
            return False

    def is_loaded(self, name: str) -> bool:
        """检查模型是否在内存中"""
        try:
            with self._client() as c:
                r = c.post("/api/show", json={"name": name})
                return r.status_code == 200
        except Exception:
            return False

    def delete_model(self, name: str) -> bool:
        """从 Ollama 删除模型"""
        try:
            with self._client() as c:
                r = c.delete("/api/delete", json={"name": name})
                r.raise_for_status()
                return True
        except Exception:
            return False

    # ── Chat API ─────────────────────────────────────────────────

    def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        num_ctx: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
    ) -> Iterator[StreamChunk]:
        """
        流式对话，返回迭代器

        Args:
            messages: 对话历史
            model: 模型名（None=默认）
            num_ctx: 上下文大小（None=自动从模型获取）
            tools: 工具定义列表
            reasoning_callback: 推理内容回调
        """
        model = model or self.config.default_model
        if not model:
            yield StreamChunk(error="未指定模型")
            return

        # 自动获取 num_ctx
        if num_ctx is None:
            info = self.get_model_info(model)
            num_ctx = info.num_ctx

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {"num_ctx": num_ctx},
        }
        if temperature is not None:
            payload["options"]["temperature"] = temperature
        if tools:
            payload["tools"] = tools

        try:
            with self._client() as c:
                with c.stream("POST", "/v1/chat/completions", json=payload) as r:
                    r.raise_for_status()
                    for data in _SSEDecoder.iter_sse(r):
                        chunk = self._parse_chunk(data, reasoning_callback)
                        yield chunk
                        if chunk.done:
                            break
        except httpx.HTTPStatusError as e:
            yield StreamChunk(error=f"HTTP {e.response.status_code}")
        except Exception as e:
            yield StreamChunk(error=str(e))

    def chat_sync(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> tuple[str, str, list[dict]]:
        """同步对话，返回 (content, reasoning, tool_calls)"""
        content, reasoning, tool_calls = "", "", []
        for chunk in self.chat(messages, model, temperature=temperature, tools=tools):
            if chunk.error:
                raise RuntimeError(chunk.error)
            content += chunk.delta
            reasoning += chunk.reasoning
            if chunk.tool_calls:
                tool_calls = chunk.tool_calls
        return content, reasoning, tool_calls

    @staticmethod
    def _parse_chunk(data: dict, reasoning_cb) -> StreamChunk:
        """解析 SSE data"""
        choices = data.get("choices", [])
        if not choices:
            return StreamChunk()

        delta = choices[0].get("delta", {})
        finish = choices[0].get("finish_reason", "")

        # 内容
        content_delta = delta.get("content", "")

        # 推理（thinks 字段）
        reasoning_delta = ""
        for key in ("reasoning", "thinking", "reasoning_content"):
            if key in delta:
                reasoning_delta = delta[key]
                if reasoning_cb:
                    reasoning_cb(reasoning_delta)
                break

        # 工具调用
        tool_calls = delta.get("tool_calls")

        done = finish in ("stop", "tool_calls")
        usage = data.get("usage")

        return StreamChunk(
            delta=content_delta,
            done=done,
            reasoning=reasoning_delta,
            tool_calls=tool_calls,
            usage=usage,
        )

    # ── 健康检查 ────────────────────────────────────────────────

    def ping(self) -> bool:
        """Ollama 服务是否在线"""
        try:
            with self._client() as c:
                return c.get("/").status_code == 200
        except Exception:
            return False

    def version(self) -> str:
        """获取 Ollama 版本"""
        try:
            with self._client() as c:
                r = c.get("/api/version")
                r.raise_for_status()
                return r.json().get("version", "unknown")
        except Exception:
            return "offline"
