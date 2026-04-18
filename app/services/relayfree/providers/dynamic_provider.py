"""
RelayFreeLLM 万能 Provider
通过配置驱动，支持所有标准 OpenAI 兼容厂商
"""

import os
import re
import httpx
import json
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from .base import BaseProvider, BaseProviderConfig

logger = logging.getLogger(__name__)


class GenericProvider(BaseProvider):
    """万能 Provider - 靠配置干活，支持所有标准 OpenAI 兼容厂商"""

    def __init__(self, provider_id: str, config: Dict[str, Any]):
        base_config = BaseProviderConfig(
            provider_id=provider_id,
            base_url=self._resolve_env_vars(config.get("base_url", "")),
            auth=config.get("auth", "bearer"),
            key_env_var=config.get("key_env_var"),
            secret_env_var=config.get("secret_env_var"),
            secret2_env_var=config.get("secret2_env_var"),
            header_field=config.get("header_field", "Authorization"),
            priority=config.get("priority", 500),
            timeout=config.get("timeout", 60),
            max_retries=config.get("max_retries", 3),
            capabilities=config.get("capabilities", ["chat", "completion"]),
            model_mapping=config.get("model_mapping", {}),
            extra_body=config.get("extra_body", {}),
            enabled=config.get("enabled", True),
            description=config.get("description", "")
        )
        super().__init__(base_config)
        self._config = config
        self._client: Optional[httpx.AsyncClient] = None

    def _resolve_env_vars(self, url: str) -> str:
        """解析 ${VAR:-default} 格式环境变量"""
        pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'
        def replacer(m):
            return os.getenv(m.group(1), m.group(2) or "")
        return re.sub(pattern, replacer, url)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
            )
        return self._client

    async def create_completion(
        self, model: str, messages: List[Dict[str, Any]], **kwargs
    ) -> Dict[str, Any]:
        real_model = self.map_model(model)
        headers = self._build_headers()
        payload = {"model": real_model, "messages": messages, **self.config.extra_body}
        
        for key in ["temperature", "max_tokens", "top_p", "top_k", "stream", "stop", "response_format"]:
            if key in kwargs:
                payload[key] = kwargs[key]

        url = f"{self.config.base_url}/chat/completions"

        async def _do():
            client = await self._get_client()
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

        return await self.with_retry(_do())

    async def create_completion_stream(
        self, model: str, messages: List[Dict[str, Any]], **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        real_model = self.map_model(model)
        headers = self._build_headers()
        headers["Accept"] = "text/event-stream"
        
        payload = {"model": real_model, "messages": messages, "stream": True, **self.config.extra_body}
        for key in ["temperature", "max_tokens", "top_p", "stream", "stop"]:
            if key in kwargs:
                payload[key] = kwargs[key]

        url = f"{self.config.base_url}/chat/completions"
        client = await self._get_client()

        try:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            yield {"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]}
                            break
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"[{self.provider_id}] 流式请求失败: {e}")
            self.mark_unhealthy(str(e))
            raise

    async def list_models(self) -> List[Dict[str, Any]]:
        headers = self._build_headers()
        url = f"{self.config.base_url}/models"

        async def _do():
            client = await self._get_client()
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data:
                    return data["data"]
                elif "models" in data:
                    return data["models"]
            return []

        try:
            return await self.with_retry(_do())
        except Exception:
            return [{"id": m, "object": "model", "owned_by": self.provider_id} 
                    for m in self.config.model_mapping.values()]

    async def health_check(self) -> bool:
        try:
            headers = self._build_headers()
            url = f"{self.config.base_url}/models"
            client = await self._get_client()
            resp = await client.get(url, headers=headers, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class ProviderFactory:
    """Provider 工厂类，根据配置动态创建"""
    _handlers = {}
    _special_registered = False

    @classmethod
    def register_handler(cls, name: str, provider_class):
        cls._handlers[name] = provider_class

    @classmethod
    def _ensure_special_handlers(cls):
        """延迟注册特殊处理器"""
        if not cls._special_registered:
            try:
                from ..special_handlers.baidu_qianfan import BaiduQianfanProvider
                from ..special_handlers.spark_websocket import SparkWebSocketProvider
                cls.register_handler("baidu_qianfan", BaiduQianfanProvider)
                cls.register_handler("spark_websocket", SparkWebSocketProvider)
            except ImportError as e:
                import logging
                logging.getLogger(__name__).warning(f"特殊处理器导入失败: {e}")
            cls._special_registered = True

    @classmethod
    def create(cls, provider_id: str, config: Dict[str, Any]) -> BaseProvider:
        cls._ensure_special_handlers()
        handler = config.get("handler")
        if handler and handler in cls._handlers:
            return cls._handlers[handler](provider_id, config)
        return GenericProvider(provider_id, config)

    @classmethod
    def create_all(cls, providers_config: Dict[str, Any]) -> Dict[str, BaseProvider]:
        providers = {}
        for pid, pcfg in providers_config.get("providers", {}).items():
            if not pcfg.get("enabled", True):
                continue
            try:
                providers[pid] = cls.create(pid, pcfg)
                logger.info(f"[RelayFree] 加载 Provider: {pid}")
            except Exception as e:
                logger.error(f"[RelayFree] Provider {pid} 创建失败: {e}")
        return providers


# 注册特殊处理器 (延迟导入避免循环依赖)
def _register_special_handlers():
    from ..special_handlers.baidu_qianfan import BaiduQianfanProvider
    from ..special_handlers.spark_websocket import SparkWebSocketProvider
    ProviderFactory.register_handler("baidu_qianfan", BaiduQianfanProvider)
    ProviderFactory.register_handler("spark_websocket", SparkWebSocketProvider)

# 注册将在首次 create 时触发