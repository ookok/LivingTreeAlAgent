"""
BaseProvider - LLM 提供商抽象层

借鉴 pi-mono 的极简设计哲学，统一抽象层屏蔽底层差异。

设计原则：
1. 统一接口：所有提供商实现相同的调用接口
2. OpenAI兼容：输出格式与 OpenAI API 保持一致
3. 配置驱动：通过环境变量统一管理
4. 增量更新：支持增量上下文管理

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum


class ModelCapability(Enum):
    """模型能力枚举"""
    CHAT = "chat"
    COMPLETION = "completion"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    REASONING = "reasoning"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    DOCUMENT_PLANNING = "document_planning"
    CONTENT_GENERATION = "content_generation"
    FORMAT_UNDERSTANDING = "format_understanding"
    COMPLIANCE_CHECK = "compliance_check"
    OPTIMIZATION = "optimization"
    WEB_SEARCH = "web_search"
    PLANNING = "planning"


class ProviderType(Enum):
    """提供商类型枚举"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    AWS = "aws"
    MISTRAL = "mistral"
    COHERE = "cohere"
    GROQ = "groq"
    LLAMA_CPP = "llama_cpp"
    HUGGINGFACE = "huggingface"
    REPLICATE = "replicate"
    TOGETHER = "together"
    LEVEL1 = "level1"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    BAIDU = "baidu"
    ALIBABA = "alibaba"
    TENCENT = "tencent"
    OTHER = "other"


@dataclass
class ModelInfo:
    """模型信息"""
    model_id: str
    name: str
    provider: str
    capabilities: List[ModelCapability]
    max_tokens: int = 4096
    context_window: int = 8192
    tier: int = 1
    cost_per_token: float = 0.0
    supported_formats: List[str] = field(default_factory=lambda: ["text", "json"])


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str  # system, user, assistant
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class UsageInfo:
    """使用信息"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


@dataclass
class ProviderResponse:
    """提供商响应"""
    success: bool
    content: str
    usage: UsageInfo = field(default_factory=UsageInfo)
    model: str = ""
    error: Optional[str] = None
    finish_reason: Optional[str] = None


class BaseProvider(ABC):
    """
    LLM 提供商抽象基类
    
    所有 LLM 提供商必须实现此类的抽象方法，确保统一的调用接口。
    
    设计模式：策略模式 + 模板方法模式
    """
    
    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """提供商类型"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """提供商名称"""
        pass
    
    @property
    @abstractmethod
    def supported_models(self) -> List[ModelInfo]:
        """支持的模型列表"""
        pass
    
    @property
    def is_available(self) -> bool:
        """检查提供商是否可用"""
        try:
            return self._check_availability()
        except Exception:
            return False
    
    @abstractmethod
    def _check_availability(self) -> bool:
        """检查可用性（子类实现）"""
        pass
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> ProviderResponse:
        """
        聊天补全接口（OpenAI兼容）
        
        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大输出 token 数
            **kwargs: 其他参数
        
        Returns:
            ProviderResponse 响应对象
        """
        pass
    
    @abstractmethod
    async def text_completion(
        self,
        prompt: str,
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> ProviderResponse:
        """
        文本补全接口
        
        Args:
            prompt: 提示文本
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大输出 token 数
            **kwargs: 其他参数
        
        Returns:
            ProviderResponse 响应对象
        """
        pass
    
    def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """获取模型信息"""
        for model in self.supported_models:
            if model.model_id == model_id:
                return model
        return None
    
    def get_models_by_capability(self, capability: ModelCapability) -> List[ModelInfo]:
        """根据能力获取支持的模型"""
        return [m for m in self.supported_models if capability in m.capabilities]
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int, model_id: str) -> float:
        """估算调用成本"""
        model_info = self.get_model_info(model_id)
        if model_info:
            return (prompt_tokens + completion_tokens) * model_info.cost_per_token
        return 0.0
    
    def format_messages(self, messages: List[Dict[str, str]]) -> List[ChatMessage]:
        """格式化消息为 ChatMessage 对象"""
        return [ChatMessage(role=m["role"], content=m["content"]) for m in messages]
    
    def to_openai_format(self, response: ProviderResponse) -> Dict[str, Any]:
        """转换为 OpenAI 兼容格式"""
        return {
            "id": "chatcmpl-" + str(hash(response.content)),
            "object": "chat.completion",
            "created": 0,
            "model": response.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response.content
                },
                "finish_reason": response.finish_reason or "stop"
            }],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }