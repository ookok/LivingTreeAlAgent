"""
缓存配置模块
定义三级缓存系统的配置参数
"""

from dataclasses import dataclass
from typing import Dict, Any
import json
import os


@dataclass
class CacheConfig:
    """缓存配置基类"""
    enabled: bool = True
    ttl_seconds: int = 900
    max_size: int = 500


@dataclass
class MemoryCacheConfig(CacheConfig):
    """L1内存缓存配置"""
    max_items: int = 100
    ttl_seconds: int = 900
    heat_threshold: float = 3.0


@dataclass
class LocalCacheConfig(CacheConfig):
    """L2本地缓存配置"""
    db_path: str = "~/.hermes-desktop/cache/conversation.db"
    max_items: int = 10000
    ttl_seconds: int = 86400
    index_type: str = "hybrid"


@dataclass
class SemanticCacheConfig(CacheConfig):
    """L3语义缓存配置"""
    vector_dim: int = 384
    similarity_threshold: float = 0.85
    index_type: str = "faiss"
    persist_path: str = "~/.hermes-desktop/cache/semantic_index"
    batch_size: int = 100


class CacheConfigManager:
    """缓存配置管理器"""
    
    DEFAULT_CONFIG = {
        "memory_cache": {
            "enabled": True,
            "max_items": 100,
            "ttl_seconds": 900,
            "heat_threshold": 3.0
        },
        "local_cache": {
            "enabled": True,
            "db_path": "~/.hermes-desktop/cache/conversation.db",
            "max_items": 10000,
            "ttl_seconds": 86400,
            "index_type": "hybrid"
        },
        "semantic_cache": {
            "enabled": True,
            "vector_dim": 384,
            "similarity_threshold": 0.85,
            "index_type": "faiss",
            "persist_path": "~/.hermes-desktop/cache/semantic_index",
            "batch_size": 100
        }
    }
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or self._get_default_path()
        self.config = self._load_config()
        
    def _get_default_path(self) -> str:
        home = os.path.expanduser("~")
        return os.path.join(home, ".hermes-desktop", "cache_config.json")
    
    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return self.DEFAULT_CONFIG.copy()
    
    def save_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def get_memory_config(self) -> MemoryCacheConfig:
        cfg = self.config.get("memory_cache", self.DEFAULT_CONFIG["memory_cache"])
        return MemoryCacheConfig(**cfg)
    
    def get_local_config(self) -> LocalCacheConfig:
        cfg = self.config.get("local_cache", self.DEFAULT_CONFIG["local_cache"])
        cfg["db_path"] = os.path.expanduser(cfg["db_path"])
        return LocalCacheConfig(**cfg)
    
    def get_semantic_config(self) -> SemanticCacheConfig:
        cfg = self.config.get("semantic_cache", self.DEFAULT_CONFIG["semantic_cache"])
        cfg["persist_path"] = os.path.expanduser(cfg["persist_path"])
        return SemanticCacheConfig(**cfg)
    
    def update_config(self, layer: str, params: Dict[str, Any]):
        if layer in self.config:
            self.config[layer].update(params)
            self.save_config()
