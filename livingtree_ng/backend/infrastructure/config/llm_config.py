#!/usr/bin/env python3
"""
LLM提供商配置模块 - 支持多种AI厂商
"""

import os
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from ..security.crypto import crypto_manager

@dataclass
class LLMProvider:
    """LLM提供商配置"""
    name: str
    display_name: str
    base_url: str
    api_key: str = ""
    models: List[str] = field(default_factory=list)
    provider_type: str = "openai"  # openai, anthropic, custom
    thinking_mode: bool = False
    enabled: bool = True

@dataclass
class LLMConfig:
    """LLM配置"""
    providers: List[LLMProvider] = field(default_factory=list)
    current_provider: str = "deepseek"
    current_model: str = "DeepSeek-V4-Flash"
    
    def get_provider(self, name: str) -> Optional[LLMProvider]:
        """获取指定提供商"""
        for p in self.providers:
            if p.name == name:
                return p
        return None
    
    def get_current_provider(self) -> Optional[LLMProvider]:
        """获取当前提供商"""
        return self.get_provider(self.current_provider)

class LLMConfigManager:
    """LLM配置管理器"""
    
    def __init__(self, config_dir: str = None):
        self.config_dir = config_dir or os.path.expanduser("~/.livingtree_ng")
        self.config_path = os.path.join(self.config_dir, "llm_config.json")
        self._ensure_dir()
        self.config = self._load_config()
    
    def _ensure_dir(self):
        """确保配置目录存在"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
    
    def _load_config(self) -> LLMConfig:
        """加载配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    providers = []
                    for p_data in data.get('providers', []):
                        providers.append(LLMProvider(
                            name=p_data['name'],
                            display_name=p_data['display_name'],
                            base_url=p_data['base_url'],
                            api_key=crypto_manager.decrypt(p_data['api_key']) if p_data.get('api_key') else "",
                            models=p_data.get('models', []),
                            provider_type=p_data.get('provider_type', 'openai'),
                            thinking_mode=p_data.get('thinking_mode', False),
                            enabled=p_data.get('enabled', True)
                        ))
                    return LLMConfig(
                        providers=providers,
                        current_provider=data.get('current_provider', 'deepseek'),
                        current_model=data.get('current_model', 'DeepSeek-V4-Flash')
                    )
            except Exception as e:
                print(f"Error loading config: {e}")
                return self._get_default_config()
        return self._get_default_config()
    
    def _get_default_config(self) -> LLMConfig:
        """获取默认配置"""
        return LLMConfig(
            providers=[
                LLMProvider(
                    name="deepseek",
                    display_name="DeepSeek",
                    base_url="https://api.deepseek.com/v1",
                    api_key="",
                    models=["DeepSeek-V4-Flash", "DeepSeek-V4-Pro"],
                    provider_type="openai",
                    thinking_mode=True
                ),
                LLMProvider(
                    name="aliyun",
                    display_name="阿里云",
                    base_url="https://dashscope.aliyuncs.com/api/text/chat",
                    api_key="",
                    models=["qwen-turbo", "qwen-plus", "qwen-max"],
                    provider_type="openai"
                ),
                LLMProvider(
                    name="tencent",
                    display_name="腾讯云",
                    base_url="https://api.chat.tencentiam.com/v1",
                    api_key="",
                    models=["llama-3.1-8b", "llama-3.1-70b"],
                    provider_type="openai"
                ),
                LLMProvider(
                    name="minimax",
                    display_name="MiniMax",
                    base_url="https://api.minimax.chat/v1/text/chatcompletion",
                    api_key="",
                    models=["abab5.5-chat", "abab6-chat"],
                    provider_type="openai"
                ),
                LLMProvider(
                    name="glm",
                    display_name="GLM",
                    base_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
                    api_key="",
                    models=["glm-4", "glm-4v", "glm-3-turbo"],
                    provider_type="openai"
                ),
                LLMProvider(
                    name="kimi",
                    display_name="Kimi",
                    base_url="https://api.moonshot.cn/v1",
                    api_key="",
                    models=["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
                    provider_type="openai"
                ),
                LLMProvider(
                    name="ollama",
                    display_name="Ollama",
                    base_url="http://localhost:11434/v1",
                    api_key="",
                    models=["qwen2.5:0.5b", "qwen2.5:1.5b", "qwen2.5:7b"],
                    provider_type="openai",
                    enabled=False
                ),
                LLMProvider(
                    name="openai",
                    display_name="OpenAI",
                    base_url="https://api.openai.com/v1",
                    api_key="",
                    models=["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
                    provider_type="openai"
                )
            ],
            current_provider="deepseek",
            current_model="DeepSeek-V4-Flash"
        )
    
    def save_config(self):
        """保存配置"""
        providers_data = []
        for p in self.config.providers:
            providers_data.append({
                "name": p.name,
                "display_name": p.display_name,
                "base_url": p.base_url,
                "api_key": crypto_manager.encrypt(p.api_key) if p.api_key else "",
                "models": p.models,
                "provider_type": p.provider_type,
                "thinking_mode": p.thinking_mode,
                "enabled": p.enabled
            })
        
        data = {
            "providers": providers_data,
            "current_provider": self.config.current_provider,
            "current_model": self.config.current_model
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def set_provider_api_key(self, provider_name: str, api_key: str):
        """设置提供商API密钥"""
        provider = self.config.get_provider(provider_name)
        if provider:
            provider.api_key = api_key
            self.save_config()
    
    def set_current_provider(self, provider_name: str):
        """设置当前提供商"""
        provider = self.config.get_provider(provider_name)
        if provider and provider.enabled:
            self.config.current_provider = provider_name
            if self.config.current_model not in provider.models:
                self.config.current_model = provider.models[0]
            self.save_config()
    
    def set_current_model(self, model_name: str):
        """设置当前模型"""
        self.config.current_model = model_name
        self.save_config()
    
    def list_providers(self) -> List[Dict]:
        """获取提供商列表（不包含API密钥）"""
        result = []
        for p in self.config.providers:
            result.append({
                "name": p.name,
                "display_name": p.display_name,
                "base_url": p.base_url,
                "models": p.models,
                "thinking_mode": p.thinking_mode,
                "enabled": p.enabled
            })
        return result

# 全局实例
llm_config_manager = LLMConfigManager()
