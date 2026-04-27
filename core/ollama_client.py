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
            # 使用正常的超时时间
            client = httpx.Client(
                base_url=self.base_url,
                timeout=httpx.Timeout(10.0, connect=5.0),  # 增加超时时间
                headers={"Content-Type": "application/json"},
            )
            with client:
                r = client.get("/api/tags")
                r.raise_for_status()
                models = []
                for m in r.json().get("models", []):
                    # 过滤掉OllamaModel不支持的字段
                    filtered_data = {
                        k: v for k, v in m.items() 
                        if k in ["name", "size", "digest", "modified_at", "details"]
                    }
                    models.append(OllamaModel(**filtered_data))
                return models
        except Exception as e:
            # 打印错误信息
            print(f"[OllamaClient] list_models 错误: {e}")
            # 快速失败，避免长时间阻塞
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

    def get_loaded_models(self) -> list[str]:
        """
        获取当前 Ollama 中已加载的模型列表（通过 /api/ps）

        Returns:
            已加载模型名列表，如 ["qwen3.5:4b", "deepseek-r1:70b"]
        """
        try:
            with self._client() as c:
                r = c.get("/api/ps")
                if r.status_code == 200:
                    data = r.json()
                    models = data.get("models", [])
                    return [m.get("name", "") for m in models if m.get("name")]
        except Exception:
            pass
        return []

    def ensure_model_loaded(self, name: str, timeout: int = 60) -> bool:
        """
        确保模型已加载到内存（Ollama 空闲时模型会 auto-stop，需要时 auto-run）

        策略：
        1. 先查 /api/ps 确认模型是否已在内存中
        2. 如果不在，发送 /api/generate 请求触发 Ollama 自动加载

        Args:
            name: 模型名
            timeout: 等待模型加载的超时秒数（默认 60s）

        Returns:
            True=模型已加载或正在加载，False=失败
        """
        # 快速检查：是否已在内存
        if name in self.get_loaded_models():
            return True

        # 触发加载：发送轻量请求让 Ollama 自动启动模型
        # keep_alive=300s 保证至少活跃 5 分钟
        try:
            with self._client() as c:
                r = c.post("/api/generate", json={
                    "model": name,
                    "prompt": "",  # 空 prompt，仅触发加载
                    "keep_alive": 300,
                    "stream": False,
                }, timeout=timeout)
                # 200=加载成功，404=模型不存在，5xx=服务问题
                if r.status_code == 200:
                    print(f"[OllamaClient] 模型 {name} 已加载（keep_alive=300s）")
                    return True
                else:
                    print(f"[OllamaClient] 模型 {name} 加载失败: HTTP {r.status_code}")
                    return False
        except Exception as e:
            print(f"[OllamaClient] 模型 {name} 加载异常: {e}")
            return False

    def is_loaded(self, name: str) -> bool:
        """检查模型是否在内存中（通过 /api/ps）"""
        return name in self.get_loaded_models()

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

        Note:
            Ollama 空闲时会 auto-stop 模型。chat() 会在首次调用时
            自动 ensure_model_loaded()，所以即使模型已停止也能正常工作。
        """
        model = model or self.config.default_model
        if not model:
            yield StreamChunk(error="未指定模型")
            return

        # ── 确保模型已加载（Ollama auto-stop 恢复）─────────────────
        if not hasattr(self, "_model_loaded_cache"):
            self._model_loaded_cache: set[str] = set()

        if model not in self._model_loaded_cache:
            # 首次对话：确保模型已加载
            if not self.ensure_model_loaded(model):
                yield StreamChunk(error=f"模型 {model} 加载失败，请检查 Ollama 服务状态")
                return
            self._model_loaded_cache.add(model)

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
