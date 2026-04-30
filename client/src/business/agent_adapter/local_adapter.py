"""
本地模型 Agent 适配器

支持本地部署的开源模型：
- Qwen2.5-7B/14B/72B
- DeepSeek-V3-7B/33B
- Llama 3
- Mistral
"""

import asyncio
from typing import List, Optional, Any, AsyncIterator
from . import BaseAgentAdapter, AgentConfig, AgentResponse


class LocalModelAdapter(BaseAgentAdapter):
    """本地模型适配器"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._model = None
        self._tokenizer = None
    
    def _load_model(self):
        """懒加载模型"""
        if not self._model:
            try:
                from transformers import AutoTokenizer, AutoModelForCausalLM
                import torch
                
                model_name = self.config.model_name
                if not model_name:
                    model_name = "Qwen/Qwen2.5-7B-Instruct"
                
                self._tokenizer = AutoTokenizer.from_pretrained(model_name)
                
                # 根据显存大小选择量化方式
                self._model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    device_map="auto",
                    torch_dtype=torch.bfloat16,
                    load_in_4bit=True if self.config.max_tokens < 8192 else False,
                    trust_remote_code=True
                )
                
                print(f"[LocalModelAdapter] 模型加载完成: {model_name}")
            except ImportError:
                raise ImportError("请安装 transformers 和 accelerate 包")
        return self._model, self._tokenizer
    
    def generate(self, prompt: str, **kwargs) -> AgentResponse:
        """同步生成响应"""
        model, tokenizer = self._load_model()
        
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(messages, tokenize=False)
        
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        
        outputs = model.generate(
            **inputs,
            max_new_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            do_sample=True,
            **kwargs
        )
        
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # 提取响应内容（去掉 prompt 部分）
        if text in response:
            content = response[len(text):].strip()
        else:
            content = response.strip()
        
        return AgentResponse(
            content=content,
            confidence=0.95,
            finish_reason="completed"
        )
    
    async def async_generate(self, prompt: str, **kwargs) -> AgentResponse:
        """异步生成响应"""
        # 本地模型同步执行，包装为异步
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate, prompt, kwargs)
    
    def stream_generate(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """流式生成响应"""
        model, tokenizer = self._load_model()
        
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(messages, tokenize=False)
        
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        
        from transformers import TextStreamer
        
        streamer = TextStreamer(tokenizer, skip_prompt=True)
        
        model.generate(
            **inputs,
            max_new_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            do_sample=True,
            streamer=streamer,
            **kwargs
        )
    
    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表
        
        动态从 ModelManager 获取可用模型，避免硬编码
        """
        try:
            from client.src.business.model_manager import ModelManager
            from client.src.business.config import AppConfig, get_config
            
            config = get_config()
            manager = ModelManager(config)
            models = manager.get_available_models()
            
            model_names = []
            for model in models:
                if model.backend is not None:
                    model_names.append(model.name)
            
            if model_names:
                return model_names
            
        except Exception as e:
            print(f"[LocalModelAdapter] 获取模型列表失败，使用默认列表: {e}")
        
        return [
            "Qwen/Qwen2.5-7B-Instruct",
            "Qwen/Qwen2.5-14B-Instruct",
            "Qwen/Qwen2.5-72B-Instruct",
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-R1",
            "meta-llama/Meta-Llama-3-8B-Instruct",
            "mistralai/Mistral-7B-Instruct-v0.3"
        ]


# 注册适配器
from . import register_agent_adapter
register_agent_adapter("local", LocalModelAdapter)
register_agent_adapter("local_model", LocalModelAdapter)