"""
L4 Relay 执行器
四级缓存金字塔的最终执行层
集成 RelayFreeLLM 网关，支持动态降级和零配置裸跑
"""

import os
import sys
import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncIterator, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """L4 执行模式"""
    DIRECT = "direct"           # 直接执行（绕过 RelayFreeLLM）
    RELAY_GATEWAY = "relay"     # 通过 RelayFreeLLM 网关
    AUTO = "auto"               # 自动选择


class L4RelayExecutor:
    """
    L4 Relay 执行器

    职责:
    1. 封装对 RelayFreeLLM 网关的调用
    2. 处理模型路由和降级逻辑
    3. L4 结果回填缓存
    4. 零配置裸跑支持（本地 Ollama 默认）
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        gateway_url: str = "http://localhost:8000/v1",
        relayfree_path: Optional[str] = None,
        enable_write_back: bool = True,
        fallback_to_direct: bool = True
    ):
        if self._initialized:
            return

        self.gateway_url = gateway_url
        self.enable_write_back = enable_write_back
        self.fallback_to_direct = fallback_to_direct

        # RelayFreeLLM 网关客户端
        self._relay_client: Optional[Any] = None
        self._relay_available = False

        # 直接 Ollama 客户端（零配置兜底）
        self._direct_client: Optional[Any] = None
        self._direct_available = False

        # 回填缓存回调
        self._write_back_callback: Optional[Callable] = None

        # 统计
        self._stats = {
            "total_requests": 0,
            "relay_requests": 0,
            "direct_requests": 0,
            "write_back_count": 0,
            "failures": 0,
            "last_provider": None
        }

        # 初始化
        self._initialized = True
        self._init_sync()
        logger.info(f"[L4Executor] L4 Relay 执行器初始化完成")
        logger.info(f"[L4Executor]   - Gateway: {gateway_url}")
        logger.info(f"[L4Executor]   - Direct Ollama: {'启用' if fallback_to_direct else '禁用'}")

    def _init_sync(self):
        """同步初始化（检查连接）"""
        # 检查 RelayFreeLLM 网关
        if self._check_gateway():
            self._relay_available = True
            logger.info("[L4Executor] RelayFreeLLM 网关可用")

        # 检查直接 Ollama（零配置裸跑）
        if self.fallback_to_direct:
            if self._check_direct_ollama():
                self._direct_available = True
                logger.info("[L4Executor] 直接 Ollama 可用（零配置兜底）")

    def _check_gateway(self) -> bool:
        """检查 RelayFreeLLM 网关是否可用"""
        try:
            import httpx
            resp = httpx.get(f"{self.gateway_url.rstrip('/v1')}/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def _check_direct_ollama(self) -> bool:
        """检查直接 Ollama 是否可用"""
        try:
            import httpx
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            resp = httpx.get(f"{ollama_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    async def _ensure_relay_client(self):
        """确保 RelayFreeLLM 客户端已初始化"""
        if self._relay_client is None:
            try:
                from openai import AsyncOpenAI
                # 尝试从 RelayFreeLLM 获取无 Key 访问
                self._relay_client = AsyncOpenAI(
                    base_url=self.gateway_url,
                    api_key="relay-free",  # 自定义 Key 标识
                    http_client=httpx.AsyncClient(timeout=120)
                )
            except ImportError:
                logger.warning("[L4Executor] openai 包未安装，使用 httpx 直接调用")
                self._relay_client = "httpx_fallback"
            except Exception as e:
                logger.error(f"[L4Executor] Relay 客户端初始化失败: {e}")
                self._relay_client = None

    async def _ensure_direct_client(self):
        """确保直接 Ollama 客户端已初始化"""
        if self._direct_client is None:
            try:
                from openai import AsyncOpenAI
                ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                self._direct_client = AsyncOpenAI(
                    base_url=f"{ollama_url}/v1",
                    api_key="ollama",  # Ollama 不需要真实 Key
                    http_client=httpx.AsyncClient(timeout=120)
                )
            except ImportError:
                self._direct_client = "httpx_fallback"
            except Exception as e:
                logger.error(f"[L4Executor] Direct 客户端初始化失败: {e}")
                self._direct_client = None

    async def execute(
        self,
        messages: List[Dict[str, Any]],
        model: str = "auto",
        model_hint: Optional[str] = None,
        stream: bool = False,
        intent: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        统一执行入口

        Args:
            messages: 对话消息
            model: 模型标识（auto 自动路由）
            model_hint: 模型提示（如 "code", "chinese", "fast"）
            stream: 是否流式
            intent: 意图类型（用于路由）
            **kwargs: 其他参数

        Returns:
            标准 ChatCompletion 响应
        """
        self._stats["total_requests"] += 1

        # 1. 尝试 RelayFreeLLM 网关
        if self._relay_available:
            try:
                result = await self._execute_via_relay(
                    messages, model, model_hint, stream, intent, **kwargs
                )
                self._stats["relay_requests"] += 1
                self._stats["last_provider"] = "relay"
                await self._handle_write_back(messages, result)
                return result
            except Exception as e:
                logger.warning(f"[L4Executor] Relay 执行失败: {e}，尝试降级")

        # 2. 降级到直接 Ollama（零配置裸跑）
        if self._direct_available and self.fallback_to_direct:
            try:
                result = await self._execute_via_direct(
                    messages, model, stream, **kwargs
                )
                self._stats["direct_requests"] += 1
                self._stats["last_provider"] = "direct"
                await self._handle_write_back(messages, result)
                return result
            except Exception as e:
                logger.error(f"[L4Executor] Direct 执行也失败: {e}")
                self._stats["failures"] += 1

        # 3. 完全失败
        raise L4ExecutionError(
            f"L4 执行失败: Relay={self._relay_available}, Direct={self._direct_available}"
        )

    async def _execute_via_relay(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        model_hint: Optional[str],
        stream: bool,
        intent: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """通过 RelayFreeLLM 网关执行"""
        await self._ensure_relay_client()

        # 构建请求模型
        request_model = model
        if model == "auto" and model_hint:
            request_model = self._hint_to_model(model_hint)

        # 添加额外参数
        request_kwargs = {
            "model": request_model,
            "messages": messages,
            "stream": stream,
            **kwargs
        }

        # 添加意图路由提示（通过 extra_headers）
        if intent:
            request_kwargs["extra_headers"] = {"X-Intent": intent}

        if stream:
            return await self._relay_client.chat.completions.create(**request_kwargs)
        else:
            result = await self._relay_client.chat.completions.create(**request_kwargs)
            # 转换为 dict
            if hasattr(result, 'model_dump'):
                return result.model_dump()
            return dict(result)

    async def _execute_via_direct(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """直接通过 Ollama 执行（零配置裸跑）"""
        await self._ensure_direct_client()

        # 解析实际模型
        actual_model = self._resolve_local_model(model)

        request_kwargs = {
            "model": actual_model,
            "messages": messages,
            "stream": stream,
            **kwargs
        }

        if stream:
            return await self._direct_client.chat.completions.create(**request_kwargs)
        else:
            result = await self._direct_client.chat.completions.create(**request_kwargs)
            if hasattr(result, 'model_dump'):
                return result.model_dump()
            return dict(result)

    def _hint_to_model(self, hint: str) -> str:
        """将意图提示转换为模型名"""
        # 意图 -> 优先模型映射
        intent_model_map = {
            "code": "deepseek-coder",
            "reasoning": "deepseek",
            "chinese": "zhipu",
            "fast": "qwen2.5",
            "cheap": "moonshot",
            "privacy": "ollama",
        }
        return intent_model_map.get(hint, "gpt-3.5")

    def _resolve_local_model(self, model: str) -> str:
        """解析本地模型（零配置裸跑时）"""
        if model == "auto":
            # 默认使用 qwen2.5-coder（如果可用）
            return os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5-coder:latest")
        # 模型别名映射
        alias_map = {
            "gpt-4": "qwen2.5-coder:latest",
            "gpt-3.5": "qwen2.5:latest",
            "claude": "llama3:latest",
        }
        return alias_map.get(model, model)

    async def _handle_write_back(self, messages: List[Dict[str, Any]], result: Dict[str, Any]):
        """处理 L4 结果回填缓存"""
        if not self.enable_write_back:
            return

        if self._write_back_callback:
            try:
                # 生成缓存 Key
                cache_key = self._generate_cache_key(messages)
                await self._write_back_callback(cache_key, result)
                self._stats["write_back_count"] += 1
                logger.debug(f"[L4Executor] 回填缓存: {cache_key[:32]}...")
            except Exception as e:
                logger.warning(f"[L4Executor] 回填缓存失败: {e}")

    def set_write_back_callback(self, callback: Callable):
        """设置回填缓存回调"""
        self._write_back_callback = callback

    def _generate_cache_key(self, messages: List[Dict[str, Any]]) -> str:
        """生成缓存 Key"""
        # 简单策略：使用消息内容的 MD5
        content = "".join(m.get("content", "") for m in messages)
        return hashlib.md5(content.encode()).hexdigest()

    def get_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        return {
            **self._stats,
            "relay_available": self._relay_available,
            "direct_available": self._direct_available,
            "success_rate": (
                (self._stats["total_requests"] - self._stats["failures"])
                / max(self._stats["total_requests"], 1)
            )
        }

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "relay_gateway": self._relay_available,
            "direct_ollama": self._direct_available,
            "stats": self.get_stats()
        }

    async def shutdown(self):
        """关闭执行器"""
        logger.info("[L4Executor] 关闭 L4 执行器...")
        # 清理资源
        self._relay_client = None
        self._direct_client = None


class L4ExecutionError(Exception):
    """L4 执行异常"""
    pass


# ==================== 快捷函数 ====================

_executor_instance: Optional[L4RelayExecutor] = None


def get_l4_executor(
    gateway_url: str = "http://localhost:8000/v1",
    enable_write_back: bool = True,
    fallback_to_direct: bool = True
) -> L4RelayExecutor:
    """获取 L4 执行器单例"""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = L4RelayExecutor(
            gateway_url=gateway_url,
            enable_write_back=enable_write_back,
            fallback_to_direct=fallback_to_direct
        )
    return _executor_instance


async def execute_via_l4(
    messages: List[Dict[str, Any]],
    model: str = "auto",
    **kwargs
) -> Dict[str, Any]:
    """快捷执行函数"""
    executor = get_l4_executor()
    return await executor.execute(messages, model, **kwargs)


# ==================== httpx 依赖声明 ====================
import httpx