"""
优化后的 Ollama 客户端
=====================

集成 ContextPreprocessor，在消息到达 LLM 之前进行优化：
- 智能压缩上下文（节省 60-90% token）
- 去重和冗余内容过滤
- 关键信息提取
- 上下文窗口优化

参考项目：https://github.com/rtk-ai/rtk

Author: Hermes Desktop Team
Date: 2026-04-22
"""

import logging
from typing import Callable, Iterator, Optional, List, Dict, Any

from client.src.business.ollama_client import OllamaClient, ChatMessage, StreamChunk
from client.src.business.config import OllamaConfig
from client.src.business.context_preprocessor import ContextPreprocessor, ProcessingStats

logger = logging.getLogger(__name__)


class OptimizedOllamaClient:
    """
    优化后的 Ollama 客户端

    包装原始 OllamaClient，在发送请求前自动优化上下文
    """

    def __init__(
        self,
        config: OllamaConfig,
        enable_preprocessing: bool = True,
        preprocessor_config: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化优化客户端

        Args:
            config: Ollama 配置
            enable_preprocessing: 是否启用上下文预处理
            preprocessor_config: 预处理器配置字典
        """
        # 原始客户端
        self.raw_client = OllamaClient(config)

        # 预处理开关
        self.enable_preprocessing = enable_preprocessing

        # 上下文预处理器
        if enable_preprocessing:
            if preprocessor_config:
                self.preprocessor = ContextPreprocessor.create_from_config(preprocessor_config)
            else:
                self.preprocessor = ContextPreprocessor()
        else:
            self.preprocessor = None

        # 统计
        self.total_requests = 0
        self.total_tokens_saved = 0

    # ─── 代理原始客户端方法 ──────────────────────────────────

    def list_models(self):
        """列出模型"""
        return self.raw_client.list_models()

    def get_model_info(self, name: str):
        """获取模型信息"""
        return self.raw_client.get_model_info(name)

    def load_model(self, name: str, keep_alive: str | None = None) -> bool:
        """加载模型"""
        return self.raw_client.load_model(name, keep_alive)

    def unload_model(self, name: str) -> bool:
        """卸载模型"""
        return self.raw_client.unload_model(name)

    def is_loaded(self, name: str) -> bool:
        """检查模型是否加载"""
        return self.raw_client.is_loaded(name)

    def delete_model(self, name: str) -> bool:
        """删除模型"""
        return self.raw_client.delete_model(name)

    def ping(self) -> bool:
        """检查服务是否在线"""
        return self.raw_client.ping()

    def version(self) -> str:
        """获取版本"""
        return self.raw_client.version()

    # ─── 优化的聊天方法 ──────────────────────────────────

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
        优化的流式对话

        在发送到 LLM 之前自动优化上下文
        """
        self.total_requests += 1

        # 优化上下文
        optimized_messages = messages
        if self.enable_preprocessing and self.preprocessor:
            try:
                # 转换为 dict 格式
                messages_dict = [{"role": m.role, "content": m.content} for m in messages]

                # 处理上下文
                optimized_messages_dict = self.preprocessor.process_messages(messages_dict)

                # 转换回 ChatMessage
                optimized_messages = [
                    ChatMessage(role=m["role"], content=m["content"])
                    for m in optimized_messages_dict
                ]

                # 记录统计
                stats = self.preprocessor.get_stats()
                if stats.compression_ratio > 0:
                    self.total_tokens_saved += int(stats.original_tokens - stats.compressed_tokens)
                    logger.info(
                        f"[ContextPreprocessor] 优化上下文: "
                        f"{stats.original_tokens} → {stats.compressed_tokens} tokens "
                        f"(节省 {stats.compression_ratio:.1f}%, "
                        f"耗时 {stats.processing_time_ms:.0f}ms)"
                    )

            except Exception as e:
                logger.warning(f"[ContextPreprocessor] 优化失败，使用原始上下文: {e}")
                # 失败时回退到原始消息
                optimized_messages = messages

        # 调用原始客户端
        yield from self.raw_client.chat(
            messages=optimized_messages,
            model=model,
            num_ctx=num_ctx,
            temperature=temperature,
            tools=tools,
            reasoning_callback=reasoning_callback,
        )

    def chat_sync(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> tuple[str, str, list[dict]]:
        """优化的同步对话"""
        content, reasoning, tool_calls = "", "", []
        for chunk in self.chat(
            messages, model, temperature=temperature, tools=tools
        ):
            if chunk.error:
                raise RuntimeError(chunk.error)
            content += chunk.delta
            reasoning += chunk.reasoning
            if chunk.tool_calls:
                tool_calls = chunk.tool_calls
        return content, reasoning, tool_calls

    # ─── 统计和管理 ──────────────────────────────────

    def get_preprocessing_stats(self) -> ProcessingStats:
        """获取预处理统计"""
        if self.preprocessor:
            return self.preprocessor.get_stats()
        return ProcessingStats()

    def get_total_stats(self) -> Dict[str, Any]:
        """获取总体统计"""
        return {
            "total_requests": self.total_requests,
            "total_tokens_saved": self.total_tokens_saved,
            "preprocessing_enabled": self.enable_preprocessing,
            "preprocessor_stats": self.get_preprocessing_stats().__dict__,
        }

    def reset_stats(self):
        """重置统计"""
        self.total_requests = 0
        self.total_tokens_saved = 0
        if self.preprocessor:
            self.preprocessor.reset_stats()

    def set_preprocessing_enabled(self, enabled: bool):
        """设置预处理开关"""
        self.enable_preprocessing = enabled
        if enabled and not self.preprocessor:
            self.preprocessor = ContextPreprocessor()

    def configure_preprocessor(self, config: Dict[str, Any]):
        """配置预处理器"""
        self.preprocessor = ContextPreprocessor.create_from_config(config)
        self.enable_preprocessing = True
