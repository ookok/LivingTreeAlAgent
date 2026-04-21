"""
统一模型客户端
支持本地 GGUF 模型 (llama-cpp-python) 和远程 API (OpenAI 兼容)
"""
import json
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any, Callable, Generator, Iterator
from pathlib import Path

from .llama_cpp_client import LlamaCppClient, LlamaCppConfig
from .ollama_client import OllamaClient, OllamaConfig

logger = __import__("logging").getLogger(__name__)


class ModelSource(Enum):
    """模型来源"""
    LOCAL_GGUF = "local_gguf"      # 本地 GGUF 文件 (llama-cpp-python)
    LOCAL_OLLAMA = "local_ollama"  # 本地 Ollama 服务
    REMOTE_API = "remote_api"     # 远程 API


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    source: ModelSource
    path: str = ""                          # 本地路径或 API 地址
    size: int = 0                           # 模型大小 (bytes)
    loaded: bool = False                    # 是否已加载
    context_length: int = 2048              # 上下文长度
    gpu_layers: int = -1                    # GPU 层数 (-1 = 自动)
    n_threads: int = 4                      # CPU 线程数
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationConfig:
    """生成配置"""
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    max_tokens: int = 2048
    stop: List[str] = field(default_factory=list)
    stream: bool = True


@dataclass
class Message:
    """对话消息"""
    role: str                               # "user", "assistant", "system"
    content: str


class UnifiedModelClient(ABC):
    """统一模型客户端基类"""
    
    @abstractmethod
    def generate(self, prompt: str, config: Optional[GenerationConfig] = None) -> str:
        """生成文本（同步）"""
        pass
    
    @abstractmethod
    def generate_stream(self, prompt: str, config: Optional[GenerationConfig] = None) -> Iterator[str]:
        """生成文本（流式）"""
        pass
    
    @abstractmethod
    def chat(self, messages: List[Message], config: Optional[GenerationConfig] = None) -> str:
        """对话（同步）"""
        pass
    
    @abstractmethod
    def chat_stream(self, messages: List[Message], config: Optional[GenerationConfig] = None) -> Iterator[str]:
        """对话（流式）"""
        pass
    
    @abstractmethod
    def is_ready(self) -> bool:
        """检查是否就绪"""
        pass
    
    @abstractmethod
    def unload(self):
        """卸载模型"""
        pass


class LlamaCppAdapter(UnifiedModelClient):
    """
    llama-cpp-python 适配器
    直接加载 GGUF 模型，无中间服务
    """
    
    def __init__(self, model_path: str, config: Optional[LlamaCppConfig] = None):
        self.model_path = Path(model_path)
        self.config = config or LlamaCppConfig()
        self._llama = None
        self._lock = threading.Lock()
        
        # 加载模型
        self._load_model()
    
    def _load_model(self):
        """加载模型"""
        try:
            from llama_cpp import Llama
            
            logger.info(f"Loading GGUF model: {self.model_path}")
            
            self._llama = Llama(
                model_path=str(self.model_path),
                n_ctx=self.config.n_ctx,
                n_threads=self.config.n_threads,
                n_gpu_layers=self.config.n_gpu_layers,
                use_mlock=self.config.use_mlock,
                use_mmap=self.config.use_mmap,
                verbose=self.config.verbose,
            )
            
            logger.info(f"Model loaded successfully: {self.model_path.name}")
            
        except ImportError:
            logger.warning("llama-cpp-python not installed. Run: pip install llama-cpp-python")
            raise
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def _build_prompt(self, messages: List[Message]) -> str:
        """构建提示词"""
        prompt_parts = []
        
        for msg in messages:
            if msg.role == "system":
                prompt_parts.append(f"### System:\n{msg.content}\n\n")
            elif msg.role == "user":
                prompt_parts.append(f"### User:\n{msg.content}\n\n")
            elif msg.role == "assistant":
                prompt_parts.append(f"### Assistant:\n{msg.content}\n\n")
        
        prompt_parts.append("### Assistant:\n")
        return "".join(prompt_parts)
    
    def generate(self, prompt: str, config: Optional[GenerationConfig] = None) -> str:
        """生成文本（同步）"""
        config = config or GenerationConfig()
        
        with self._lock:
            output = self._llama(
                prompt,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                top_k=config.top_k,
                repeat_penalty=config.repeat_penalty,
                stop=config.stop,
                echo=False,
                stream=False,
            )
        
        return output["choices"][0]["text"]
    
    def generate_stream(self, prompt: str, config: Optional[GenerationConfig] = None) -> Iterator[str]:
        """生成文本（流式）"""
        config = config or GenerationConfig()
        
        with self._lock:
            stream = self._llama(
                prompt,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                top_k=config.top_k,
                repeat_penalty=config.repeat_penalty,
                stop=config.stop,
                echo=False,
                stream=True,
            )
            
            for output in stream:
                if content := output.get("choices", [{}])[0].get("delta", {}).get("content", ""):
                    yield content
    
    def chat(self, messages: List[Message], config: Optional[GenerationConfig] = None) -> str:
        """对话（同步）"""
        prompt = self._build_prompt(messages)
        return self.generate(prompt, config)
    
    def chat_stream(self, messages: List[Message], config: Optional[GenerationConfig] = None) -> Iterator[str]:
        """对话（流式）"""
        prompt = self._build_prompt(messages)
        return self.generate_stream(prompt, config)
    
    def is_ready(self) -> bool:
        """检查是否就绪"""
        return self._llama is not None
    
    def unload(self):
        """卸载模型"""
        with self._lock:
            if self._llama:
                del self._llama
                self._llama = None
                logger.info(f"Model unloaded: {self.model_path.name}")


class OllamaAdapter(UnifiedModelClient):
    """
    Ollama 适配器
    通过 Ollama 服务调用模型
    """
    
    def __init__(self, model_name: str, config: Optional[OllamaConfig] = None):
        self.model_name = model_name
        self.config = config or OllamaConfig()
        self._client = OllamaClient(self.config)
    
    def generate(self, prompt: str, config: Optional[GenerationConfig] = None) -> str:
        """生成文本（同步）"""
        import asyncio
        return asyncio.run(self._client.generate(self.model_name, prompt, config))
    
    def generate_stream(self, prompt: str, config: Optional[GenerationConfig] = None) -> Iterator[str]:
        """生成文本（流式）"""
        for chunk in self._client.stream_generate(self.model_name, prompt, config):
            yield chunk
    
    def chat(self, messages: List[Message], config: Optional[GenerationConfig] = None) -> str:
        """对话（同步）"""
        return self._client.chat(self.model_name, messages, config)
    
    def chat_stream(self, messages: List[Message], config: Optional[GenerationConfig] = None) -> Iterator[str]:
        """对话（流式）"""
        for chunk in self._client.stream_chat(self.model_name, messages, config):
            yield chunk
    
    def is_ready(self) -> bool:
        """检查是否就绪"""
        return self._client.ping()
    
    def unload(self):
        """Ollama 不需要手动卸载"""
        logger.info("Ollama model unload - handled by Ollama server")


class UnifiedModelManager:
    """
    统一模型管理器
    管理多个模型客户端，支持热切换
    """
    
    def __init__(self):
        self._clients: Dict[str, UnifiedModelClient] = {}
        self._current: Optional[str] = None
        self._lock = threading.RLock()
        self._callbacks: List[Callable[[str, Optional[str]], None]] = []  # (old_model, new_model)
    
    def register_client(self, name: str, client: UnifiedModelClient):
        """注册模型客户端"""
        with self._lock:
            self._clients[name] = client
            logger.info(f"Registered model client: {name}")
    
    def unregister_client(self, name: str):
        """注销模型客户端"""
        with self._lock:
            if name in self._clients:
                self._clients[name].unload()
                del self._clients[name]
                if self._current == name:
                    self._current = None
                logger.info(f"Unregistered model client: {name}")
    
    def switch_model(self, name: str) -> bool:
        """切换当前模型"""
        with self._lock:
            if name not in self._clients:
                logger.warning(f"Model not found: {name}")
                return False
            
            old = self._current
            self._current = name
            
            # 通知回调
            for cb in self._callbacks:
                try:
                    cb(old, name)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
            
            logger.info(f"Switched to model: {name}")
            return True
    
    def get_current(self) -> Optional[UnifiedModelClient]:
        """获取当前模型客户端"""
        with self._lock:
            if self._current and self._current in self._clients:
                return self._clients[self._current]
            return None
    
    def list_models(self) -> List[str]:
        """列出所有模型"""
        with self._lock:
            return list(self._clients.keys())
    
    def generate(self, prompt: str, config: Optional[GenerationConfig] = None) -> str:
        """生成文本（使用当前模型）"""
        client = self.get_current()
        if not client:
            raise RuntimeError("No model selected")
        return client.generate(prompt, config)
    
    def generate_stream(self, prompt: str, config: Optional[GenerationConfig] = None) -> Iterator[str]:
        """生成文本流（使用当前模型）"""
        client = self.get_current()
        if not client:
            raise RuntimeError("No model selected")
        return client.generate_stream(prompt, config)
    
    def chat(self, messages: List[Message], config: Optional[GenerationConfig] = None) -> str:
        """对话（使用当前模型）"""
        client = self.get_current()
        if not client:
            raise RuntimeError("No model selected")
        return client.chat(messages, config)
    
    def chat_stream(self, messages: List[Message], config: Optional[GenerationConfig] = None) -> Iterator[str]:
        """对话流（使用当前模型）"""
        client = self.get_current()
        if not client:
            raise RuntimeError("No model selected")
        return client.chat_stream(messages, config)
    
    def on_model_switch(self, callback: Callable[[str, Optional[str]], None]):
        """注册模型切换回调"""
        self._callbacks.append(callback)


# ============= 工厂函数 =============

LLAMA_CPP_AVAILABLE = False
try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    pass


def create_local_client(
    model_path: str,
    backend: str = "llama-cpp",
    n_ctx: int = 4096,
    n_gpu_layers: int = -1,
    n_threads: int = 4,
) -> UnifiedModelClient:
    """
    创建本地模型客户端
    
    Args:
        model_path: GGUF 模型文件路径
        backend: 后端类型 ("llama-cpp" 或 "ollama")
        n_ctx: 上下文长度
        n_gpu_layers: GPU 层数 (-1 = 自动)
        n_threads: CPU 线程数
    
    Returns:
        UnifiedModelClient 实例
    """
    if backend == "llama-cpp":
        if not LLAMA_CPP_AVAILABLE:
            raise ImportError(
                "llama-cpp-python not installed.\n"
                "Install with: pip install llama-cpp-python\n"
                "For GPU support: pip install llama-cpp-python --force-reinstall --no-cache-dir"
            )
        
        config = LlamaCppConfig(
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_threads=n_threads,
        )
        return LlamaCppAdapter(model_path, config)
    
    elif backend == "ollama":
        # 从路径提取模型名
        model_name = Path(model_path).stem
        return OllamaAdapter(model_name)
    
    else:
        raise ValueError(f"Unknown backend: {backend}")


def create_remote_client(
    api_url: str,
    api_key: Optional[str] = None,
    model_name: str = "gpt-4",
    timeout: float = 60.0,
) -> UnifiedModelClient:
    """
    创建远程 API 客户端
    支持 OpenAI 兼容 API

    Args:
        api_url: API 地址 (如 https://api.openai.com/v1)
        api_key: API 密钥
        model_name: 模型名称
        timeout: 请求超时时间 (秒)

    Returns:
        UnifiedModelClient 实例
    """
    from .remote_api_client import RemoteApiClient
    return RemoteApiClient(
        api_url=api_url,
        api_key=api_key,
        model_name=model_name,
        timeout=timeout,
    )


def create_writing_assistant(
    use_local: bool = True,
    local_model_path: Optional[str] = None,
    remote_api_url: Optional[str] = None,
    remote_api_key: Optional[str] = None,
    remote_model: str = "gpt-4",
) -> "WritingAssistant":
    """
    创建写作助手

    Args:
        use_local: True=使用本地模型，False=使用远程API
        local_model_path: 本地 GGUF 模型路径
        remote_api_url: 远程 API 地址
        remote_api_key: 远程 API 密钥
        remote_model: 远程模型名称

    Returns:
        WritingAssistant 实例
    """
    from .writing_assistant import WritingAssistant
    return WritingAssistant(
        use_local=use_local,
        local_model_path=local_model_path,
        remote_api_url=remote_api_url,
        remote_api_key=remote_api_key,
        remote_model=remote_model,
    )
