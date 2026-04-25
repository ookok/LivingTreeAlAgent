"""
统一配置管理 - P0 核心配置
LivingTreeAI 配置中心
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass, field
import os
import yaml


@dataclass
class ServiceEndpoint:
    """服务端点配置"""
    host: str
    port: int
    protocol: str = "http"
    timeout: float = 30.0
    retry_count: int = 3
    
    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"


@dataclass
class UnifiedConfig:
    """
    统一配置类
    
    包含所有核心服务配置
    """
    # === P0: 核心服务配置 ===
    
    # 模型服务
    model_service: ServiceEndpoint = field(
        default_factory=lambda: ServiceEndpoint(
            host=os.getenv("MODEL_HOST", "localhost"),
            port=int(os.getenv("MODEL_PORT", "8000")),
            protocol="http",
            timeout=60.0,
        )
    )
    
    # 中继服务器
    relay_service: ServiceEndpoint = field(
        default_factory=lambda: ServiceEndpoint(
            host=os.getenv("RELAY_HOST", "localhost"),
            port=int(os.getenv("RELAY_PORT", "8001")),
            protocol="http",
            timeout=30.0,
        )
    )
    
    # 知识库服务
    knowledge_service: ServiceEndpoint = field(
        default_factory=lambda: ServiceEndpoint(
            host=os.getenv("KNOWLEDGE_HOST", "localhost"),
            port=int(os.getenv("KNOWLEDGE_PORT", "8002")),
            protocol="http",
            timeout=45.0,
        )
    )
    
    # === P0: 超时配置 ===
    default_timeout: float = 30.0
    long_running_timeout: float = 300.0  # 5分钟
    user_input_timeout: float = 60.0
    
    # === P0: 日志配置 ===
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None
    log_max_bytes: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 5
    
    # === P1: 重试配置 ===
    max_retry_count: int = 3
    retry_delay: float = 1.0
    exponential_backoff: bool = True
    
    # === P1: 代理配置 ===
    proxy_enabled: bool = False
    proxy_url: Optional[str] = None
    
    # === P1: 缓存配置 ===
    cache_enabled: bool = True
    cache_max_size: int = 1000
    cache_ttl: float = 3600.0  # 1小时
    
    @classmethod
    def load_from_file(cls, config_path: str) -> 'UnifiedConfig':
        """从YAML文件加载配置"""
        if not os.path.exists(config_path):
            return cls()
            
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        if not data:
            return cls()
            
        # 构建配置对象
        config = cls()
        
        # 解析服务端点
        if 'services' in data:
            services = data['services']
            for service_name in ['model_service', 'relay_service', 'knowledge_service']:
                if service_name in services:
                    svc_data = services[service_name]
                    setattr(config, service_name, ServiceEndpoint(
                        host=svc_data.get('host', 'localhost'),
                        port=svc_data.get('port', 8000),
                        protocol=svc_data.get('protocol', 'http'),
                        timeout=svc_data.get('timeout', 30.0),
                    ))
        
        # 解析超时配置
        if 'timeout' in data:
            config.default_timeout = data['timeout'].get('default', 30.0)
            config.long_running_timeout = data['timeout'].get('long_running', 300.0)
            
        # 解析日志配置
        if 'logging' in data:
            logging_data = data['logging']
            config.log_level = logging_data.get('level', 'INFO')
            config.log_file = logging_data.get('file')
            
        # 解析代理配置
        if 'proxy' in data:
            proxy_data = data['proxy']
            config.proxy_enabled = proxy_data.get('enabled', False)
            config.proxy_url = proxy_data.get('url')
            
        return config
    
    def save_to_file(self, config_path: str):
        """保存配置到YAML文件"""
        data = {
            'services': {
                'model_service': {
                    'host': self.model_service.host,
                    'port': self.model_service.port,
                    'protocol': self.model_service.protocol,
                    'timeout': self.model_service.timeout,
                },
                'relay_service': {
                    'host': self.relay_service.host,
                    'port': self.relay_service.port,
                    'protocol': self.relay_service.protocol,
                    'timeout': self.relay_service.timeout,
                },
                'knowledge_service': {
                    'host': self.knowledge_service.host,
                    'port': self.knowledge_service.port,
                    'protocol': self.knowledge_service.protocol,
                    'timeout': self.knowledge_service.timeout,
                },
            },
            'timeout': {
                'default': self.default_timeout,
                'long_running': self.long_running_timeout,
            },
            'logging': {
                'level': self.log_level,
                'file': self.log_file,
            },
            'proxy': {
                'enabled': self.proxy_enabled,
                'url': self.proxy_url,
            },
        }
        
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'services': {
                'model_service': self.model_service.url,
                'relay_service': self.relay_service.url,
                'knowledge_service': self.knowledge_service.url,
            },
            'timeout': {
                'default': self.default_timeout,
                'long_running': self.long_running_timeout,
                'user_input': self.user_input_timeout,
            },
            'logging': {
                'level': self.log_level,
                'file': self.log_file,
            },
            'retry': {
                'max_count': self.max_retry_count,
                'delay': self.retry_delay,
                'exponential_backoff': self.exponential_backoff,
            },
            'cache': {
                'enabled': self.cache_enabled,
                'max_size': self.cache_max_size,
                'ttl': self.cache_ttl,
            },
        }


# 全局配置实例
_global_config: Optional[UnifiedConfig] = None


def get_unified_config() -> UnifiedConfig:
    """获取全局配置实例（单例）"""
    global _global_config
    if _global_config is None:
        _global_config = UnifiedConfig()
    return _global_config


def set_unified_config(config: UnifiedConfig):
    """设置全局配置"""
    global _global_config
    _global_config = config


def init_unified_config(config_path: Optional[str] = None) -> UnifiedConfig:
    """初始化统一配置"""
    if config_path and os.path.exists(config_path):
        config = UnifiedConfig.load_from_file(config_path)
    else:
        config = UnifiedConfig()
        
    set_unified_config(config)
    return config
