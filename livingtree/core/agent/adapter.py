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

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, AsyncIterator


@dataclass
class AgentResponse:
    content: str
    reasoning: Optional[List[str]] = None
    confidence: float = 1.0
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: str = "completed"


@dataclass
class AgentConfig:
    agent_type: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: str = "default"
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 60


class BaseAgentAdapter(ABC):

    def __init__(self, config: AgentConfig):
        self.config = config

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> AgentResponse:
        pass

    @abstractmethod
    async def async_generate(self, prompt: str, **kwargs) -> AgentResponse:
        pass

    @abstractmethod
    def stream_generate(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        pass

    @abstractmethod
    def get_supported_models(self) -> List[str]:
        pass


class AgentAdapterFactory:

    def __init__(self):
        self._adapters: Dict[str, Callable[[AgentConfig], BaseAgentAdapter]] = {}

    def register_adapter(self, agent_type: str,
                         creator: Callable[[AgentConfig], BaseAgentAdapter]):
        self._adapters[agent_type] = creator

    def create_adapter(self, config: AgentConfig) -> BaseAgentAdapter:
        creator = self._adapters.get(config.agent_type)
        if not creator:
            raise ValueError(f"未知的 Agent 类型: {config.agent_type}")
        return creator(config)

    def get_supported_agents(self) -> List[str]:
        return list(self._adapters.keys())


_agent_factory = AgentAdapterFactory()


def register_agent_adapter(agent_type: str,
                           creator: Callable[[AgentConfig], BaseAgentAdapter]):
    _agent_factory.register_adapter(agent_type, creator)


def create_agent_adapter(config: AgentConfig) -> BaseAgentAdapter:
    return _agent_factory.create_adapter(config)


def get_supported_agents() -> List[str]:
    return _agent_factory.get_supported_agents()


__all__ = [
    "AgentResponse",
    "AgentConfig",
    "BaseAgentAdapter",
    "AgentAdapterFactory",
    "register_agent_adapter",
    "create_agent_adapter",
    "get_supported_agents",
]
