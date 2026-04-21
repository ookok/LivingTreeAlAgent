"""
远程 API 客户端
支持 OpenAI 兼容 API (OpenRouter, DeepSeek, Claude, Groq 等)
"""
import json
import time
from typing import Optional, Dict, List, Iterator, Union, Any

import requests

from .unified_model_client import (
    UnifiedModelClient,
    GenerationConfig,
    Message,
)


class RemoteApiClient(UnifiedModelClient):
    """
    远程 API 适配器
    支持 OpenAI 兼容 API
    """

    # API 类型检测关键字
    API_TYPES = {
        "openai": ["openai.com"],
        "deepseek": ["deepseek"],
        "anthropic": ["anthropic"],
        "openrouter": ["openrouter"],
        "groq": ["groq"],
        "ollama": ["ollama"],
    }

    def __init__(
        self,
        api_url: str,
        api_key: Optional[str] = None,
        model_name: str = "gpt-4",
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key or ""
        self.model_name = model_name
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
        self._api_type = self._detect_api_type()

        # 设置请求头
        self._headers = {"Content-Type": "application/json"}
        if self.api_key and self._api_type != "anthropic":
            self._headers["Authorization"] = f"Bearer {self.api_key}"

    def _detect_api_type(self) -> str:
        url_lower = self.api_url.lower()
        for api_type, keywords in self.API_TYPES.items():
            if any(k in url_lower for k in keywords):
                return api_type
        return "openai_compatible"

    def _build_url(self, endpoint: str) -> str:
        if endpoint.startswith("http"):
            return endpoint
        return f"{self.api_url}/{endpoint.lstrip('/')}"

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        stream: bool = False,
    ) -> Union[Dict, Iterator[str]]:
        url = self._build_url(endpoint)
        headers = self._headers.copy()

        if self._api_type == "anthropic":
            headers["x-api-key"] = self.api_key
            headers["anthropic-version"] = "2023-06-01"
            headers.pop("Authorization", None)

        for attempt in range(self.max_retries):
            try:
                if stream:
                    response = self._session.request(
                        method, url, json=data, headers=headers,
                        timeout=self.timeout, stream=True
                    )
                    response.raise_for_status()
                    return self._stream_response(response)
                else:
                    response = self._session.request(
                        method, url, json=data, headers=headers,
                        timeout=self.timeout
                    )
                    response.raise_for_status()
                    return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(1 * (attempt + 1))

    def _stream_response(self, response: requests.Response) -> Iterator[str]:
        for line in response.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    if "choices" in data:
                        delta = data["choices"][0].get("delta", {})
                        if content := delta.get("content", ""):
                            yield content
                    elif "type" in data:
                        if data["type"] == "content_block_delta":
                            if content := data.get("delta", {}).get("text", ""):
                                yield content
                        elif data["type"] == "message_stop":
                            break
                except json.JSONDecodeError:
                    continue

    def generate(self, prompt: str, config: Optional[GenerationConfig] = None) -> str:
        config = config or GenerationConfig()
        if self._api_type == "anthropic":
            data = {
                "model": self.model_name,
                "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
                "max_tokens_to_sample": config.max_tokens,
                "temperature": config.temperature,
            }
            result = self._request("POST", "v1/complete", data)
            return result.get("completion", "")
        else:
            data = {
                "model": self.model_name,
                "prompt": prompt,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "stream": False,
            }
            result = self._request("POST", "v1/completions", data)
            return result["choices"][0]["text"]

    def generate_stream(self, prompt: str, config: Optional[GenerationConfig] = None) -> Iterator[str]:
        config = config or GenerationConfig()
        if self._api_type == "anthropic":
            data = {
                "model": self.model_name,
                "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
                "max_tokens_to_sample": config.max_tokens,
                "temperature": config.temperature,
                "stream": True,
            }
            return self._request("POST", "v1/complete", data, stream=True)
        else:
            data = {
                "model": self.model_name,
                "prompt": prompt,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "stream": True,
            }
            return self._request("POST", "v1/completions", data, stream=True)

    def chat(self, messages: List[Message], config: Optional[GenerationConfig] = None) -> str:
        config = config or GenerationConfig()
        if self._api_type == "anthropic":
            system_msg, anthropic_messages = "", []
            for msg in messages:
                if msg.role == "system":
                    system_msg += msg.content + "\n"
                else:
                    anthropic_messages.append({"role": msg.role, "content": msg.content})
            data = {
                "model": self.model_name,
                "messages": anthropic_messages,
                "system": system_msg.strip() or None,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
            }
            result = self._request("POST", "v1/messages", data)
            return result["content"][0]["text"]
        else:
            converted = [{"role": m.role, "content": m.content} for m in messages]
            data = {
                "model": self.model_name,
                "messages": converted,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "stream": False,
            }
            result = self._request("POST", "v1/chat/completions", data)
            return result["choices"][0]["message"]["content"]

    def chat_stream(self, messages: List[Message], config: Optional[GenerationConfig] = None) -> Iterator[str]:
        config = config or GenerationConfig()
        if self._api_type == "anthropic":
            system_msg, anthropic_messages = "", []
            for msg in messages:
                if msg.role == "system":
                    system_msg += msg.content + "\n"
                else:
                    anthropic_messages.append({"role": msg.role, "content": msg.content})
            data = {
                "model": self.model_name,
                "messages": anthropic_messages,
                "system": system_msg.strip() or None,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "stream": True,
            }
            return self._request("POST", "v1/messages", data, stream=True)
        else:
            converted = [{"role": m.role, "content": m.content} for m in messages]
            data = {
                "model": self.model_name,
                "messages": converted,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "stream": True,
            }
            return self._request("POST", "v1/chat/completions", data, stream=True)

    def is_ready(self) -> bool:
        try:
            if self._api_type == "anthropic":
                self._request("POST", "v1/messages", {
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                })
            else:
                self._request("POST", "v1/chat/completions", {
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                })
            return True
        except Exception:
            return False

    def unload(self):
        """远程 API 不需要卸载"""
        pass


# ============= 提供商预设配置 =============

PROVIDER_PRESETS = {
    "openai": {
        "api_url": "https://api.openai.com/v1",
        "model": "gpt-4-turbo",
    },
    "deepseek": {
        "api_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "deepseek-coder": {
        "api_url": "https://api.deepseek.com/v1",
        "model": "deepseek-coder",
    },
    "openrouter": {
        "api_url": "https://openrouter.ai/api/v1",
        "model": "anthropic/claude-3-opus",
    },
    "groq": {
        "api_url": "https://api.groq.com/openai/v1",
        "model": "llama-3-70b-versatile",
    },
    "ollama": {
        "api_url": "http://localhost:11434/v1",
        "model": "llama3",
    },
    "lmstudio": {
        "api_url": "http://localhost:1234/v1",
        "model": "local-model",
    },
}


def create_client_from_preset(
    preset: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> RemoteApiClient:
    """
    从预设创建客户端

    Args:
        preset: 提供商预设 ("openai", "deepseek", "openrouter", 等)
        api_key: API 密钥
        model: 可选，覆盖默认模型

    Returns:
        RemoteApiClient 实例
    """
    if preset not in PROVIDER_PRESETS:
        raise ValueError(f"Unknown preset: {preset}. Available: {list(PROVIDER_PRESETS.keys())}")

    config = PROVIDER_PRESETS[preset]
    return RemoteApiClient(
        api_url=config["api_url"],
        api_key=api_key or "",
        model_name=model or config["model"],
    )
