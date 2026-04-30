"""
Agent Adapter 层 (Agent Adapter Layer)

提供统一的 Agent 接入接口，支持多种模型/agent：
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude 3)
- Google (Gemini)
- Qwen (通义千问)
- DeepSeek (深度求索)
- 自定义 Agent

核心设计：BYOA (Bring Your Own Agent)
"""

from typing import Dict, List, Optional, Any, Callable, AsyncIterator
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class AgentResponse:
    """Agent 响应结果"""
    content: str
    reasoning: Optional[List[str]] = None
    confidence: float = 1.0
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: str = "completed"


@dataclass
class AgentConfig:
    """Agent 配置"""
    agent_type: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: str = "default"
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 60


class BaseAgentAdapter(ABC):
    """
    Agent 适配器基类
    
    所有 Agent 适配器必须实现此类
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> AgentResponse:
        """同步生成响应"""
        pass
    
    @abstractmethod
    async def async_generate(self, prompt: str, **kwargs) -> AgentResponse:
        """异步生成响应"""
        pass
    
    @abstractmethod
    def stream_generate(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """流式生成响应"""
        pass
    
    @abstractmethod
    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表"""
        pass


class AgentAdapterFactory:
    """
    Agent Adapter 工厂类
    
    负责创建和管理各种 Agent 适配器
    """
    
    def __init__(self):
        self._adapters: Dict[str, Callable[[AgentConfig], BaseAgentAdapter]] = {}
    
    def register_adapter(self, agent_type: str, creator: Callable[[AgentConfig], BaseAgentAdapter]):
        """
        注册 Agent 适配器
        
        Args:
            agent_type: Agent 类型标识
            creator: 创建函数
        """
        self._adapters[agent_type] = creator
        print(f"[AgentAdapterFactory] 注册 Agent 适配器: {agent_type}")
    
    def create_adapter(self, config: AgentConfig) -> BaseAgentAdapter:
        """
        创建 Agent 适配器
        
        Args:
            config: Agent 配置
            
        Returns:
            Agent 适配器实例
        """
        creator = self._adapters.get(config.agent_type)
        if not creator:
            raise ValueError(f"未知的 Agent 类型: {config.agent_type}")
        
        return creator(config)
    
    def get_supported_agents(self) -> List[str]:
        """获取支持的 Agent 类型列表"""
        return list(self._adapters.keys())


# 创建全局工厂实例
_agent_factory = AgentAdapterFactory()


def register_agent_adapter(agent_type: str, creator: Callable[[AgentConfig], BaseAgentAdapter]):
    """注册 Agent 适配器（便捷函数）"""
    _agent_factory.register_adapter(agent_type, creator)


def create_agent_adapter(config: AgentConfig) -> BaseAgentAdapter:
    """创建 Agent 适配器（便捷函数）"""
    return _agent_factory.create_adapter(config)


def get_supported_agents() -> List[str]:
    """获取支持的 Agent 类型列表（便捷函数）"""
    return _agent_factory.get_supported_agents()


__all__ = [
    "AgentResponse",
    "AgentConfig",
    "BaseAgentAdapter",
    "AgentAdapterFactory",
    "register_agent_adapter",
    "create_agent_adapter",
    "get_supported_agents"
]