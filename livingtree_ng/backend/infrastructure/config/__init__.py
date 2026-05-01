"""
LivingTree NG - 简化配置系统

设计哲学:
    - 配置即代码 (Configuration as Code)
    - 简单的 dataclass
    - 合理的默认值
    - 直接导入使用
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import os


@dataclass
class OllamaConfig:
    """Ollama 配置"""
    url: str = "http://www.mogoo.com.cn:8899/v1"
    timeout: int = 120
    max_retries: int = 3
    default_model: str = "qwen2.5:0.5b"


@dataclass
class LLMConfig:
    """LLM 默认参数"""
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    max_tokens: int = 2048


@dataclass
class PathsConfig:
    """路径配置"""
    data: str = "./data"
    logs: str = "./logs"
    cache: str = "./cache"
    models: str = "./models"


@dataclass
class Config:
    """
    主配置类
    
    使用示例:
        from backend.infrastructure.config import config
        
        # 读取配置
        url = config.ollama.url
        max_tokens = config.llm.max_tokens
        
        # 修改配置
        config.ollama.url = "http://new-host:11434"
    """
    
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        import dataclasses
        
        def convert(obj):
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                return {k.name: convert(getattr(obj, k.name)) for k in dataclasses.fields(obj)}
            return obj
        
        return convert(self)


# 全局配置实例
config = Config()

# 确保数据目录存在
os.makedirs(config.paths.data, exist_ok=True)
os.makedirs(config.paths.logs, exist_ok=True)
os.makedirs(config.paths.cache, exist_ok=True)
os.makedirs(config.paths.models, exist_ok=True)
