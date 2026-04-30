"""
Qwen (通义千问) Agent 适配器
"""

import asyncio
from typing import List, Optional, Any, AsyncIterator
from . import BaseAgentAdapter, AgentConfig, AgentResponse


class QwenAdapter(BaseAgentAdapter):
    """Qwen API 适配器"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._client = None
        self._async_client = None
    
    def _get_client(self):
        """懒加载客户端"""
        if not self._client:
            try:
                from openai import OpenAI
                # Qwen 兼容 OpenAI API
                self._client = OpenAI(
                    api_key=self.config.api_key or "EMPTY",
                    base_url=self.config.base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    timeout=self.config.timeout
                )
            except ImportError:
                raise ImportError("请安装 openai 包: pip install openai")
        return self._client
    
    def _get_async_client(self):
        """懒加载异步客户端"""
        if not self._async_client:
            try:
                from openai import AsyncOpenAI
                self._async_client = AsyncOpenAI(
                    api_key=self.config.api_key or "EMPTY",
                    base_url=self.config.base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    timeout=self.config.timeout
                )
            except ImportError:
                raise ImportError("请安装 openai 包: pip install openai")
        return self._async_client
    
    def generate(self, prompt: str, **kwargs) -> AgentResponse:
        """同步生成响应"""
        client = self._get_client()
        
        response = client.chat.completions.create(
            model=self.config.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            **kwargs
        )
        
        return AgentResponse(
            content=response.choices[0].message.content,
            confidence=1.0,
            finish_reason=response.choices[0].finish_reason
        )
    
    async def async_generate(self, prompt: str, **kwargs) -> AgentResponse:
        """异步生成响应"""
        client = self._get_async_client()
        
        response = await client.chat.completions.create(
            model=self.config.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            **kwargs
        )
        
        return AgentResponse(
            content=response.choices[0].message.content,
            confidence=1.0,
            finish_reason=response.choices[0].finish_reason
        )
    
    def stream_generate(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """流式生成响应"""
        client = self._get_client()
        
        stream = client.chat.completions.create(
            model=self.config.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            stream=True,
            **kwargs
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表
        
        从配置中心动态获取，避免硬编码
        """
        try:
            from client.src.business.shared.config_center import ConfigCenter
            
            config_center = ConfigCenter()
            models = config_center.get("agents.qwen.models", [])
            
            if models and isinstance(models, list):
                return models
            
        except Exception as e:
            print(f"[QwenAdapter] 获取模型列表失败，使用默认列表: {e}")
        
        return [
            "qwen-max",
            "qwen-plus",
            "qwen-turbo",
            "qwen-2-7b-instruct",
            "qwen-2-14b-instruct",
            "qwen-2-72b-instruct"
        ]


# 注册适配器
from . import register_agent_adapter
register_agent_adapter("qwen", QwenAdapter)
register_agent_adapter("通义千问", QwenAdapter)