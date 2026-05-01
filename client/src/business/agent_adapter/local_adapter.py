"""
远程模型 Agent 适配器

支持通过远程 URL 调用模型，兼容 OpenAI 格式：
- FlowyAIPC Herdsman 引擎 (推荐)
- 其他 OpenAI 兼容 API

注意：本模块已不再支持本地模型下载和加载（GGUF 格式），
所有模型调用均通过远程 URL 进行。
"""

import asyncio
import aiohttp
import json
from typing import List, Optional, Any, AsyncIterator
from . import BaseAgentAdapter, AgentConfig, AgentResponse


class RemoteModelAdapter(BaseAgentAdapter):
    """远程模型适配器（兼容 OpenAI 格式）"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._base_url = config.base_url or "http://localhost:8080/v1"
        self._api_key = config.api_key or ""
        self._model_name = config.model_name or "default"
        self._timeout = config.timeout or 60
    
    async def async_generate(self, prompt: str, **kwargs) -> AgentResponse:
        """异步生成响应"""
        headers = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        
        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens or 4096),
            "temperature": kwargs.get("temperature", self.config.temperature or 0.7),
            "stream": False,
        }
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self._timeout)) as session:
                async with session.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return AgentResponse(
                            content=content,
                            confidence=0.95,
                            finish_reason="completed"
                        )
                    else:
                        error_text = await resp.text()
                        return AgentResponse(
                            content=f"API调用失败: {resp.status}\n{error_text}",
                            confidence=0.0,
                            finish_reason="error"
                        )
        except Exception as e:
            return AgentResponse(
                content=f"连接失败: {str(e)}",
                confidence=0.0,
                finish_reason="error"
            )
    
    def generate(self, prompt: str, **kwargs) -> AgentResponse:
        """同步生成响应"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.async_generate(prompt, **kwargs))
    
    async def stream_generate(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """流式生成响应"""
        headers = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        
        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens or 4096),
            "temperature": kwargs.get("temperature", self.config.temperature or 0.7),
            "stream": True,
        }
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self._timeout)) as session:
                async with session.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as resp:
                    if resp.status == 200:
                        async for line in resp.content:
                            if line:
                                try:
                                    data = line.decode("utf-8").strip()
                                    if data.startswith("data: "):
                                        data = data[6:]
                                    if data == "[DONE]":
                                        break
                                    if data:
                                        json_data = json.loads(data)
                                        content = json_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                        if content:
                                            yield content
                                except json.JSONDecodeError:
                                    continue
                    else:
                        error_text = await resp.text()
                        yield f"API调用失败: {resp.status}\n{error_text}"
        except Exception as e:
            yield f"连接失败: {str(e)}"
    
    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表"""
        return [
            "FlowyAIPC Herdsman",
            "OpenAI Compatible API",
            "Custom Remote Model",
        ]


# 注册适配器
from . import register_agent_adapter
register_agent_adapter("remote", RemoteModelAdapter)
register_agent_adapter("remote_url", RemoteModelAdapter)
register_agent_adapter("openai_compatible", RemoteModelAdapter)