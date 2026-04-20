"""
统一配置管理系统

集中管理所有配置，包括 LLM API 密钥、系统配置等
"""

import os
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "openai"  # openai, anthropic, google, ollama
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 60


@dataclass
class EmbeddingConfig:
    """嵌入配置"""
    provider: str = "openai"  # openai, huggingface
    model: str = "text-embedding-ada-002"
    api_key: str = ""
    dimension: int = 1536


@dataclass
class BrowserPoolConfig:
    """浏览器会话池配置"""
    max_sessions: int = 5
    session_timeout: int = 300  # 5分钟
    use_cloud: bool = False


@dataclass
class SecurityConfig:
    """安全配置"""
    allowed_domains: List[str] = field(default_factory=lambda: ["*"])
    blocked_domains: List[str] = field(default_factory=list)
    enable_audit: bool = True


@dataclass
class DocumentQAConfig:
    """文档 QA 配置"""
    embedding_model: str = "text-embedding-ada-002"
    llm_model: str = "gpt-4o"
    temperature: float = 0.7
    top_k: int = 3
    chunk_size: int = 1000
    chunk_overlap: int = 200


@dataclass
class SystemConfig:
    """系统配置"""
    debug: bool = False
    log_level: str = "INFO"
    data_dir: str = "./data"
    cache_dir: str = "./cache"


class ConfigManager:
    """配置管理器"""
    
    _instance = None
    _config_file = "config.json"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # LLM 配置
        self.llm = LLMConfig()
        
        # 嵌入配置
        self.embedding = EmbeddingConfig()
        
        # 浏览器会话池配置
        self.browser_pool = BrowserPoolConfig()
        
        # 安全配置
        self.security = SecurityConfig()
        
        # 文档 QA 配置
        self.document_qa = DocumentQAConfig()
        
        # 系统配置
        self.system = SystemConfig()
        
        # 加载配置
        self._load_config()
    
    def _load_config(self):
        """从文件加载配置"""
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 更新各配置
                if 'llm' in data:
                    for key, value in data['llm'].items():
                        if hasattr(self.llm, key):
                            setattr(self.llm, key, value)
                
                if 'embedding' in data:
                    for key, value in data['embedding'].items():
                        if hasattr(self.embedding, key):
                            setattr(self.embedding, key, value)
                
                if 'browser_pool' in data:
                    for key, value in data['browser_pool'].items():
                        if hasattr(self.browser_pool, key):
                            setattr(self.browser_pool, key, value)
                
                if 'security' in data:
                    for key, value in data['security'].items():
                        if hasattr(self.security, key):
                            setattr(self.security, key, value)
                
                if 'document_qa' in data:
                    for key, value in data['document_qa'].items():
                        if hasattr(self.document_qa, key):
                            setattr(self.document_qa, key, value)
                
                if 'system' in data:
                    for key, value in data['system'].items():
                        if hasattr(self.system, key):
                            setattr(self.system, key, value)
                
                print(f"[ConfigManager] 从 {self._config_file} 加载配置成功")
                
            except Exception as e:
                print(f"[ConfigManager] 加载配置失败: {e}")
    
    def _save_config(self):
        """保存配置到文件"""
        try:
            data = {
                'llm': {
                    'provider': self.llm.provider,
                    'model': self.llm.model,
                    'api_key': self.llm.api_key,
                    'base_url': self.llm.base_url,
                    'temperature': self.llm.temperature,
                    'max_tokens': self.llm.max_tokens,
                    'timeout': self.llm.timeout
                },
                'embedding': {
                    'provider': self.embedding.provider,
                    'model': self.embedding.model,
                    'api_key': self.embedding.api_key,
                    'dimension': self.embedding.dimension
                },
                'browser_pool': {
                    'max_sessions': self.browser_pool.max_sessions,
                    'session_timeout': self.browser_pool.session_timeout,
                    'use_cloud': self.browser_pool.use_cloud
                },
                'security': {
                    'allowed_domains': self.security.allowed_domains,
                    'blocked_domains': self.security.blocked_domains,
                    'enable_audit': self.security.enable_audit
                },
                'document_qa': {
                    'embedding_model': self.document_qa.embedding_model,
                    'llm_model': self.document_qa.llm_model,
                    'temperature': self.document_qa.temperature,
                    'top_k': self.document_qa.top_k,
                    'chunk_size': self.document_qa.chunk_size,
                    'chunk_overlap': self.document_qa.chunk_overlap
                },
                'system': {
                    'debug': self.system.debug,
                    'log_level': self.system.log_level,
                    'data_dir': self.system.data_dir,
                    'cache_dir': self.system.cache_dir
                }
            }
            
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            print(f"[ConfigManager] 配置已保存到 {self._config_file}")
            
        except Exception as e:
            print(f"[ConfigManager] 保存配置失败: {e}")
    
    def update_llm_config(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None
    ):
        """更新 LLM 配置"""
        if provider is not None:
            self.llm.provider = provider
        if model is not None:
            self.llm.model = model
        if api_key is not None:
            self.llm.api_key = api_key
        if base_url is not None:
            self.llm.base_url = base_url
        if temperature is not None:
            self.llm.temperature = temperature
        if max_tokens is not None:
            self.llm.max_tokens = max_tokens
        if timeout is not None:
            self.llm.timeout = timeout
        
        self._save_config()
    
    def update_embedding_config(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        dimension: Optional[int] = None
    ):
        """更新嵌入配置"""
        if provider is not None:
            self.embedding.provider = provider
        if model is not None:
            self.embedding.model = model
        if api_key is not None:
            self.embedding.api_key = api_key
        if dimension is not None:
            self.embedding.dimension = dimension
        
        self._save_config()
    
    def update_browser_pool_config(
        self,
        max_sessions: Optional[int] = None,
        session_timeout: Optional[int] = None,
        use_cloud: Optional[bool] = None
    ):
        """更新浏览器会话池配置"""
        if max_sessions is not None:
            self.browser_pool.max_sessions = max_sessions
        if session_timeout is not None:
            self.browser_pool.session_timeout = session_timeout
        if use_cloud is not None:
            self.browser_pool.use_cloud = use_cloud
        
        self._save_config()
    
    def update_security_config(
        self,
        allowed_domains: Optional[List[str]] = None,
        blocked_domains: Optional[List[str]] = None,
        enable_audit: Optional[bool] = None
    ):
        """更新安全配置"""
        if allowed_domains is not None:
            self.security.allowed_domains = allowed_domains
        if blocked_domains is not None:
            self.security.blocked_domains = blocked_domains
        if enable_audit is not None:
            self.security.enable_audit = enable_audit
        
        self._save_config()
    
    def update_document_qa_config(
        self,
        embedding_model: Optional[str] = None,
        llm_model: Optional[str] = None,
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ):
        """更新文档 QA 配置"""
        if embedding_model is not None:
            self.document_qa.embedding_model = embedding_model
        if llm_model is not None:
            self.document_qa.llm_model = llm_model
        if temperature is not None:
            self.document_qa.temperature = temperature
        if top_k is not None:
            self.document_qa.top_k = top_k
        if chunk_size is not None:
            self.document_qa.chunk_size = chunk_size
        if chunk_overlap is not None:
            self.document_qa.chunk_overlap = chunk_overlap
        
        self._save_config()
    
    def update_system_config(
        self,
        debug: Optional[bool] = None,
        log_level: Optional[str] = None,
        data_dir: Optional[str] = None,
        cache_dir: Optional[str] = None
    ):
        """更新系统配置"""
        if debug is not None:
            self.system.debug = debug
        if log_level is not None:
            self.system.log_level = log_level
        if data_dir is not None:
            self.system.data_dir = data_dir
        if cache_dir is not None:
            self.system.cache_dir = cache_dir
        
        self._save_config()
    
    def get_llm_api_key(self) -> str:
        """
        获取 LLM API 密钥
        
        优先使用配置中的密钥，其次使用环境变量
        """
        if self.llm.api_key:
            return self.llm.api_key
        
        # 回退到环境变量
        if self.llm.provider == "openai":
            return os.getenv("OPENAI_API_KEY", "")
        elif self.llm.provider == "anthropic":
            return os.getenv("ANTHROPIC_API_KEY", "")
        elif self.llm.provider == "google":
            return os.getenv("GOOGLE_API_KEY", "")
        
        return ""
    
    def get_embedding_api_key(self) -> str:
        """
        获取嵌入 API 密钥
        
        优先使用配置中的密钥，其次使用环境变量
        """
        if self.embedding.api_key:
            return self.embedding.api_key
        
        # 回退到环境变量
        if self.embedding.provider == "openai":
            return os.getenv("OPENAI_API_KEY", "")
        
        return ""
    
    def to_dict(self) -> Dict[str, Any]:
        """导出配置为字典"""
        return {
            'llm': {
                'provider': self.llm.provider,
                'model': self.llm.model,
                'api_key': '***' if self.llm.api_key else '',
                'base_url': self.llm.base_url,
                'temperature': self.llm.temperature,
                'max_tokens': self.llm.max_tokens,
                'timeout': self.llm.timeout
            },
            'embedding': {
                'provider': self.embedding.provider,
                'model': self.embedding.model,
                'api_key': '***' if self.embedding.api_key else '',
                'dimension': self.embedding.dimension
            },
            'browser_pool': {
                'max_sessions': self.browser_pool.max_sessions,
                'session_timeout': self.browser_pool.session_timeout,
                'use_cloud': self.browser_pool.use_cloud
            },
            'security': {
                'allowed_domains': self.security.allowed_domains,
                'blocked_domains': self.security.blocked_domains,
                'enable_audit': self.security.enable_audit
            },
            'document_qa': {
                'embedding_model': self.document_qa.embedding_model,
                'llm_model': self.document_qa.llm_model,
                'temperature': self.document_qa.temperature,
                'top_k': self.document_qa.top_k,
                'chunk_size': self.document_qa.chunk_size,
                'chunk_overlap': self.document_qa.chunk_overlap
            },
            'system': {
                'debug': self.system.debug,
                'log_level': self.system.log_level,
                'data_dir': self.system.data_dir,
                'cache_dir': self.system.cache_dir
            }
        }


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """
    获取配置管理器实例
    
    Returns:
        ConfigManager: 配置管理器实例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def create_config_manager(config_file: str = "config.json") -> ConfigManager:
    """
    创建配置管理器
    
    Args:
        config_file: 配置文件路径
        
    Returns:
        ConfigManager: 配置管理器实例
    """
    ConfigManager._config_file = config_file
    return get_config_manager()
