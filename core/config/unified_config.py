"""
统一配置管理 - 兼容层（Nanochat 风格）
===========================================

⚠️  已重构为 Nanochat 风格极简配置 ⚠️
==============================================

旧代码: from core.config.unified_config import UnifiedConfig
新代码: from core.config.nanochat_config import config

本文件作为兼容层，将旧 API 调用转发到新的 Nanochat 配置系统。
旧代码无需立即修改，但建议逐步迁移到新 API。

迁移指南:
    旧: config.get("endpoints.ollama.url")
    新: config.ollama.url
    
    旧: config.get_max_retries("default")
    新: config.retries.default
    
    旧: config.get_timeout("default")
    新: config.timeouts.default

作者: LivingTree AI Team
日期: 2026-04-25
"""

import warnings
from typing import Any, Optional, Dict
from functools import wraps

# 导入新的 Nanochat 配置
from .nanochat_config import NanochatConfig, config as _new_config

# 显示弃用警告
warnings.warn(
    "UnifiedConfig is deprecated. "
    "Use 'from core.config.nanochat_config import config' instead. "
    "This compatibility layer will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2,
)


def _deprecated(func):
    """弃用装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        warnings.warn(
            f"{func.__name__} is deprecated. Use NanochatConfig API instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return func(*args, **kwargs)
    return wrapper


class UnifiedConfig:
    """
    兼容层: UnifiedConfig → NanochatConfig
    
    旧代码继续工作，但使用新的配置系统。
    
    示例:
        # 旧代码（仍然工作）
        config = UnifiedConfig.get_instance()
        url = config.get("endpoints.ollama.url")
        
        # 新代码（推荐）
        from core.config.nanochat_config import config
        url = config.ollama.url
    """
    
    _instance = None
    _lock = None  # 不需要锁，新配置是线程安全的
    
    @classmethod
    def get_instance(cls) -> "UnifiedConfig":
        """获取单例实例（兼容旧 API）"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """初始化（实际上只是包装新配置）"""
        self._config = _new_config
    
    # ── 兼容旧 API: get/set ─────────────────────────────────────────────
    
    @_deprecated
    def get(self, key: str, default: Any = None) -> Any:
        """
        兼容旧 API: config.get("endpoints.ollama.url")
        
        新 API: config.ollama.url
        """
        keys = key.split('.')
        obj = self._config
        
        for k in keys:
            if hasattr(obj, k):
                obj = getattr(obj, k)
            elif isinstance(obj, dict) and k in obj:
                obj = obj[k]
            else:
                return default
        
        return obj
    
    @_deprecated
    def set(self, key: str, value: Any) -> None:
        """
        兼容旧 API: config.set("endpoints.ollama.url", "...")
        
        新 API: config.ollama.url = "..."
        """
        keys = key.split('.')
        obj = self._config
        
        for k in keys[:-1]:
            if hasattr(obj, k):
                obj = getattr(obj, k)
            elif isinstance(obj, dict) and k in obj:
                obj = obj[k]
        
        last_key = keys[-1]
        if hasattr(obj, last_key):
            setattr(obj, last_key, value)
        elif isinstance(obj, dict):
            obj[last_key] = value
    
    # ── 兼容旧 API: get_* 方法 ─────────────────────────────────────────
    
    @_deprecated
    def get_ollama_url(self) -> str:
        """新 API: config.ollama.url"""
        return self._config.ollama.url
    
    @_deprecated
    def get_ollama_timeout(self) -> int:
        """新 API: config.ollama.timeout"""
        return self._config.ollama.timeout
    
    @_deprecated
    def get_timeout(self, name: str = "default") -> int:
        """新 API: config.timeouts.<name>"""
        return getattr(self._config.timeouts, name, 30)
    
    @_deprecated
    def get_delay(self, name: str = "polling_medium") -> float:
        """新 API: config.delays.<name>"""
        return getattr(self._config.delays, name, 0.5)
    
    @_deprecated
    def get_max_retries(self, category: str = "default") -> int:
        """新 API: config.retries.<category> 或 config.retries.default"""
        return getattr(self._config.retries, category, self._config.retries.default)
    
    @_deprecated
    def get_retry_delay(self, category: str = "default") -> float:
        """新 API: 使用 config.retries.exponential_base（近似）"""
        return float(self._config.retries.exponential_base)
    
    @_deprecated
    def get_retry_config(self, category: str = "default") -> Dict[str, Any]:
        """新 API: 直接访问 config.retries"""
        return {
            "max_retries": self.get_max_retries(category),
            "delay": self.get_retry_delay(category),
            "backoff": "exponential",
        }
    
    @_deprecated
    def get_path(self, name: str = "data") -> str:
        """新 API: config.paths.<name>"""
        return getattr(self._config.paths, name, f"./{name}")
    
    @_deprecated
    def get_api_key(self, provider: str) -> Optional[str]:
        """新 API: config.api_keys.<provider>"""
        return getattr(self._config.api_keys, provider, None)
    
    # ── 新增: 直接访问新配置 ──────────────────────────────────────────
    
    @property
    def new_config(self) -> NanochatConfig:
        """直接访问新的 Nanochat 配置（推荐）"""
        return self._config


# ── 兼容旧 API: 全局函数 ───────────────────────────────────────────────

def get_unified_config() -> UnifiedConfig:
    """兼容旧 API: 获取全局配置实例"""
    warnings.warn(
        "get_unified_config() is deprecated. "
        "Use 'from core.config.nanochat_config import config' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return UnifiedConfig.get_instance()


def set_unified_config(config: UnifiedConfig):
    """兼容旧 API: 设置全局配置实例"""
    warnings.warn(
        "set_unified_config() is deprecated.",
        DeprecationWarning,
        stacklevel=2,
    )
    UnifiedConfig._instance = config


# ── 导出 ─────────────────────────────────────────────────────────────

__all__ = ['UnifiedConfig', 'get_unified_config', 'set_unified_config']
