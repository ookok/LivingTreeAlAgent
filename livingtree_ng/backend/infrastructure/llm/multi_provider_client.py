#!/usr/bin/env python3
"""
多提供商LLM客户端 - 支持DeepSeek、阿里云、腾讯云、MiniMax、GLM、Kimi等
"""

import json
import requests
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ChatMessage:
    role: str
    content: str

@dataclass
class LLMResponse:
    content: str
    model: str
    thinking: Optional[str] = None
    usage: Optional[Dict] = None

class MultiProviderLLMClient:
    """多提供商LLM客户端"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
    
    def _get_current_provider(self):
        """获取当前提供商配置"""
        return self.config_manager.config.get_current_provider()
    
    def _build_messages(self, history: List[ChatMessage]) -> List[Dict]:
        """构建消息格式"""
        return [{"role": m.role, "content": m.content} for m in history]
    
    def _call_openai_compatible(self, base_url: str, api_key: str, model: str, 
                                messages: List[Dict], thinking_mode: bool = False) -> str:
        """调用OpenAI兼容的API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else ""
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096
        }
        
        if thinking_mode:
            data["stream"] = False
        
        try:
            url = f"{base_url}/chat/completions"
            logger.debug(f"Calling LLM: {url}")
            logger.debug(f"Model: {model}, Messages: {len(messages)}")
            
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            
            if thinking_mode and "thinking" in result:
                thinking = result["thinking"]
                logger.info(f"Thinking: {thinking[:100]}...")
            
            content = result["choices"][0]["message"]["content"]
            return content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM API error: {e}")
            if response:
                try:
                    error_data = response.json()
                    logger.error(f"API Error Response: {error_data}")
                except:
                    logger.error(f"API Response: {response.text}")
            raise
    
    def chat_sync(self, history: List[ChatMessage], model: Optional[str] = None) -> str:
        """同步聊天"""
        provider = self._get_current_provider()
        if not provider:
            return "错误：未配置提供商"
        
        if not provider.api_key:
            return f"错误：{provider.display_name} 未配置API密钥"
        
        model_name = model or self.config_manager.config.current_model
        messages = self._build_messages(history)
        
        try:
            return self._call_openai_compatible(
                base_url=provider.base_url,
                api_key=provider.api_key,
                model=model_name,
                messages=messages,
                thinking_mode=provider.thinking_mode
            )
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"聊天失败: {str(e)}"
    
    def check_connection(self) -> Dict:
        """检查连接"""
        provider = self._get_current_provider()
        if not provider:
            return {"alive": False, "error": "未配置提供商"}
        
        if not provider.api_key:
            return {"alive": False, "error": "未配置API密钥"}
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {provider.api_key}" if provider.api_key else ""
            }
            
            # 尝试获取模型列表或简单的健康检查
            url = f"{provider.base_url}/models"
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return {"alive": True, "provider": provider.display_name}
            else:
                return {"alive": False, "status_code": response.status_code}
                
        except Exception as e:
            logger.error(f"Connection check error: {e}")
            return {"alive": False, "error": str(e)}
    
    def list_models(self) -> List[Dict]:
        """获取当前提供商的模型列表"""
        provider = self._get_current_provider()
        if not provider:
            return []
        
        return [{"name": m, "provider": provider.name, "provider_display": provider.display_name} 
                for m in provider.models]

# 创建全局实例
from ..config.llm_config import llm_config_manager
llm_client = MultiProviderLLMClient(llm_config_manager)
