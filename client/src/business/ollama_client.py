"""
Ollama API 客户端（已迁移到 ModelRouter）
基于 OpenAI-Compatible 接口，支持流式 SSE
参考 hermes-agent 的模型调用架构

现已集成 ModelRouter，支持多后端（Ollama/Shimmy/OpenAI）
"""
import json
import time
from typing import Callable, Iterator, Optional
from dataclasses import dataclass, field

import requests

from business.config import OllamaConfig
from business.model_router import ModelRouter, BackendType, BackendConfig, get_model_router


# ── 数据模型 ────────────────────────────────────────────────

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
    def iter_sse(response: requests.Response) -> Iterator[dict]:
        """从 HTTP 响应迭代解析 SSE 事件"""
        for line in response.iter_lines():
            if isinstance(line, bytes):
                line = line.decode('utf-8')
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


# ── Ollama 客户端（已迁移到 ModelRouter）──────────────────────────────────

class OllamaClient:
    """
    Ollama API 客户端（OpenAI-Compatible）
    支持：
    - 标准 chat completions（/v1/chat/completions）
    - SSE 流式响应
    - 模型列表 / 模型信息 / 加载 / 卸载
    
    已迁移到 ModelRouter，支持多后端（Ollama/Shimmy/OpenAI）
    """

    def __init__(self, config: OllamaConfig, model_router: ModelRouter | None = None):
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self._num_ctx_cache: dict[str, int] = {}

        # 使用 ModelRouter
        self.model_router = model_router or get_model_router()
        
        # 确保 Ollama 后端已注册
        if "ollama" not in self.model_router.backends:
            ollama_config = BackendConfig(
                backend_type=BackendType.OLLAMA,
                base_url=self.base_url,
                priority=1,
                enabled=True
            )
            self.model_router.register_backend("ollama", ollama_config)
        
        # 获取 Ollama 后端实例
        self.ollama_backend = self.model_router.get_backend("ollama")
        
        logger.info(f"OllamaClient 初始化完成，使用 ModelRouter，后端: ollama")

    # ── 模型管理 ────────────────────────────────────────────────

    def list_models(self) -> list[OllamaModel]:
        """列出 Ollama 已注册的模型"""
        try:
            models_info = self.ollama_backend.list_models()
            # 转换为 OllamaModel
            models = []
            for m in models_info:
                models.append(OllamaModel(
                    name=m.name,
                    size=m.size or 0,
                    modified_at=m.modified_at or "",
                    details=m.details
                ))
            return models
        except Exception as e:
            logger.error(f"列出模型失败: {e}")
            return []

    def get_model_info(self, name: str) -> ModelInfo:
        """获取模型详细信息（自动缓存 num_ctx）"""
        if name in self._num_ctx_cache:
            return ModelInfo(name=name, num_ctx=self._num_ctx_cache[name])

        try:
            info_dict = self.ollama_backend.get_model_info(name)
            info = ModelInfo(
                name=name,
                num_ctx=info_dict.get("context_length", self.config.num_ctx),
                num_gpu=info_dict.get("num_gpu", self.config.num_gpu),
                num_params=info_dict.get("parameters", ""),
                extra=info_dict
            )
            self._num_ctx_cache[name] = info.num_ctx
            return info
        except Exception:
            return ModelInfo(name=name, num_ctx=self.config.num_ctx)

    def load_model(self, name: str, keep_alive: str | None = None) -> bool:
        """加载模型到内存"""
        return self.ollama_backend.load_model(name, keep_alive)

    def unload_model(self, name: str) -> bool:
        """卸载模型（keep_alive=0）"""
        return self.ollama_backend.unload_model(name)

    def is_loaded(self, name: str) -> bool:
        """检查模型是否在内存中"""
        return self.ollama_backend.is_loaded(name)

    def delete_model(self, name: str) -> bool:
        """从 Ollama 删除模型"""
        return self.ollama_backend.delete_model(name)

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

        # 构造 messages 列表
        msgs = [{"role": m.role, "content": m.content} for m in messages]
        
        # 构造参数
        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if tools:
            kwargs["tools"] = tools
        
        # 使用 ModelRouter 的 chat_stream
        try:
            for chunk_dict in self.model_router.chat_stream(model, msgs, **kwargs):
                chunk = self._parse_chunk(chunk_dict, reasoning_callback)
                yield chunk
                if chunk.done:
                    break
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
        """解析 SSE data（OpenAI 格式）"""
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
        return self.ollama_backend.ping()

    def version(self) -> str:
        """获取 Ollama 版本"""
        return self.ollama_backend.version()

    def health_check(self) -> bool:
        """健康检查（别名）"""
        return self.ollama_backend.health_check()


# ── 全局默认客户端 ────────────────────────────────────────────────

_default_client: OllamaClient | None = None

def get_ollama_client(config: OllamaConfig | None = None) -> OllamaClient:
    """获取默认 OllamaClient 实例（单例）"""
    global _default_client
    if _default_client is None:
        if config is None:
            from business.config import UnifiedConfig
            config = UnifiedConfig.get_instance().get_ollama_config()
        _default_client = OllamaClient(config)
    return _default_client


if __name__ == "__main__":
    # 测试代码
    import sys
    import os
    
    # 配置日志
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stdout, format='{message}', colorize=False)
    except ImportError:
        import logging
        logging.basicConfig(level=logging.INFO, format='%(message)s')
        logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("OllamaClient (ModelRouter) 测试")
    logger.info("=" * 60)
    
    # 创建配置
    from business.config import OllamaConfig
    config = OllamaConfig(
        base_url="http://localhost:11434",
        default_model="qwen2.5:1.5b"
    )
    
    # 创建客户端（会自动注册到 ModelRouter）
    client = OllamaClient(config)
    
    # 健康检查
    logger.info("\n[1] 健康检查:")
    if client.ping():
        logger.info("  Ollama 在线")
    else:
        logger.error("  Ollama 离线")
        sys.exit(1)
    
    # 列出模型
    logger.info("\n[2] 列出模型:")
    models = client.list_models()
    for m in models[:5]:
        logger.info(f"  - {m.name}")
    
    # 同步对话测试
    logger.info("\n[3] 同步对话测试:")
    messages = [ChatMessage(role="user", content="你好，请介绍一下自己")]
    try:
        content, reasoning, tool_calls = client.chat_sync(messages, model="qwen2.5:1.5b")
        logger.info(f"  回复: {content[:100]}...")
    except Exception as e:
        logger.error(f"  失败: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("测试完成")
    logger.info("=" * 60)
