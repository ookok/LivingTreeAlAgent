"""
核心配置管理
参考 hermes-agent 的 config.yaml 设计
"""

import os
import json
import yaml
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


# ── 配置模型 ─────────────────────────────────────────────────────────

class OllamaConfig(BaseModel):
    """Ollama 服务配置"""
    base_url: str = "http://localhost:11434"
    default_model: str = ""           # 默认模型名（如 qwen2.5:7b）
    num_ctx: int = 8192               # 上下文窗口大小（自动从 /api/show 获取）
    num_gpu: int = 0                  # GPU layers（0 = 全 CPU）
    keep_alive: str = "5m"            # 模型保持加载时间


class ModelPathConfig(BaseModel):
    """模型路径配置"""
    models_dir: str = ""              # 模型存储目录（默认为软件目录/models）
    ollama_home: str = ""              # Ollama 模型目录（~/.ollama）
    auto_import: bool = True          # 自动导入 GGUF 到 Ollama


class ModelMarketConfig(BaseModel):
    """模型市场配置"""
    sources: list[str] = Field(default_factory=lambda: ["modelscope", "huggingface"])
    default_source: str = "modelscope"
    # ModelScope
    modelscope_token: str = ""
    modelscope_cache_dir: str = ""
    # HuggingFace
    hf_token: str = ""
    hf_cache_dir: str = ""
    # 下载
    max_concurrent_downloads: int = 2
    download_timeout: int = 3600


class ModelStoreConfig(BaseModel):
    """模型商店配置 (P2P模型分发 + 中继链网络)"""
    enable_p2p: bool = True                  # 启用P2P模型发现
    relay_servers: list[str] = Field(default_factory=lambda: [
        "139.199.124.242:8888",  # 默认中继服务器
    ])
    enable_monitoring: bool = True           # 启用运行时监控
    storage_dir: str = ""                     # 模型存储目录
    max_concurrent_downloads: int = 3         # 最大并发下载数


class WritingConfig(BaseModel):
    """写作配置"""
    default_project_dir: str = ""
    auto_save_interval: int = 30      # 秒
    enable_file_watch: bool = True


class SearchConfig(BaseModel):
    """搜索配置"""
    serper_key: str = ""              # Serper API Key（可选）
    brave_key: str = ""                # Brave Search API Key（可选）
    cache_ttl_minutes: int = 60       # 缓存有效期（分钟）
    cn_sites: list[str] = Field(default_factory=lambda: [
        "zhihu.com", "juejin.cn", "weixin.qq.com", "bilibili.com"
    ])  # 中文优质站点


class AgentConfig(BaseModel):
    """Agent 行为配置"""
    max_iterations: int = 90
    max_tokens: int = 4096
    temperature: float = 0.7
    enabled_toolsets: list[str] = Field(default_factory=lambda: ["file", "writing", "project", "ollama"])
    streaming: bool = True
    show_reasoning: bool = False


class AppConfig(BaseModel):
    """完整应用配置"""
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    model_path: ModelPathConfig = Field(default_factory=ModelPathConfig)
    model_market: ModelMarketConfig = Field(default_factory=ModelMarketConfig)
    writing: WritingConfig = Field(default_factory=WritingConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)

    # 模型商店配置 (P2P模型分发)
    model_store: ModelStoreConfig = Field(default_factory=ModelStoreConfig)

    # 窗口状态
    window_width: int = 1400
    window_height: int = 900
    left_panel_width: int = 240
    right_panel_width: int = 300

    # 外观
    theme: str = "dark"


# ── 路径 & 加载 ──────────────────────────────────────────────────────

def _get_config_dir() -> Path:
    """配置目录（优先用户目录，兜底软件目录）"""
    user_cfg = Path.home() / ".hermes-desktop"
    if os.access(str(Path.home()), os.W_OK):
        user_cfg.mkdir(parents=True, exist_ok=True)
        return user_cfg
    # 兜底：软件目录
    sw_dir = Path(__file__).parent
    cfg_dir = sw_dir / ".config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir


def _get_config_path() -> Path:
    return _get_config_dir() / "config.json"


def _get_models_dir(cfg: AppConfig) -> Path:
    """获取模型存储目录"""
    if cfg.model_path.models_dir:
        p = Path(cfg.model_path.models_dir)
    else:
        p = Path(__file__).parent / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _get_projects_dir(cfg: AppConfig) -> Path:
    """获取项目文档目录"""
    if cfg.writing.default_project_dir:
        p = Path(cfg.writing.default_project_dir)
    else:
        p = Path.home() / "Documents" / "HermesProjects"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── 公开 API ────────────────────────────────────────────────────────

DEFAULT_CONFIG = AppConfig()


def load_config() -> AppConfig:
    """从文件加载配置（不存在则返回默认）"""
    path = _get_config_path()
    if not path.exists():
        return DEFAULT_CONFIG
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig(**data)
    except Exception:
        return DEFAULT_CONFIG


def save_config(cfg: AppConfig) -> None:
    """保存配置到文件"""
    path = _get_config_path()
    path.write_text(json.dumps(cfg.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")


def get_hermes_home() -> Path:
    """获取 Hermes 主目录（用于存储 .env 等文件）"""
    return _get_config_dir()


def get_env_value(key: str, default: str = "") -> str:
    """
    从 .env 文件获取环境变量值
    
    Args:
        key: 环境变量名
        default: 默认值
    
    Returns:
        str: 环境变量值或默认值
    """
    # 先从当前环境变量获取
    value = os.environ.get(key)
    if value:
        return value
    
    # 从 .env 文件获取
    env_file = get_hermes_home() / ".env"
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        k, v = line.split('=', 1)
                        if k.strip() == key:
                            return v.strip()
        except Exception:
            pass
    
    return default


def get_models_dir() -> Path:
    return _get_models_dir(load_config())


def get_projects_dir() -> Path:
    return _get_projects_dir(load_config())


def get_config_dir() -> Path:
    return _get_config_dir()


# ── UnifiedConfig 兼容层 ─────────────────────────────────────────────
# 为了兼容从 core.config 迁移过来的代码

import warnings
from typing import Any, Optional, Dict

# 导入 NanochatConfig
from .nanochat_config import NanochatConfig as _NanochatConfig, config as _nanochat_config


class UnifiedConfig:
    """
    兼容层: UnifiedConfig → NanochatConfig
    
    旧代码继续工作，但使用新的配置系统。
    
    示例:
        # 旧代码（仍然工作）
        from client.src.business.config import UnifiedConfig
        config = UnifiedConfig.get_instance()
        url = config.get("endpoints.ollama.url")
        
        # 新代码（推荐）
        from client.src.business.nanochat_config import config
        url = config.ollama.url
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> "UnifiedConfig":
        """获取单例实例（兼容旧 API）"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """初始化（实际上只是包装新配置）"""
        self._config = _nanochat_config
    
    # ── 兼容旧 API: get/set ─────────────────────────────────────────────
    
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
    
    def get_ollama_url(self) -> str:
        """新 API: config.ollama.url"""
        return self._config.ollama.url
    
    def get_ollama_timeout(self) -> int:
        """新 API: config.ollama.timeout"""
        return self._config.ollama.timeout
    
    def get_timeout(self, name: str = "default") -> int:
        """新 API: config.timeouts.<name>"""
        return getattr(self._config.timeouts, name, 30)
    
    def get_delay(self, name: str = "polling_medium") -> float:
        """新 API: config.delays.<name>"""
        return getattr(self._config.delays, name, 0.5)
    
    def get_max_retries(self, category: str = "default") -> int:
        """新 API: config.retries.<category> 或 config.retries.default"""
        return getattr(self._config.retries, category, self._config.retries.default)
    
    def get_retry_delay(self, category: str = "default") -> float:
        """新 API: 使用 config.retries.exponential_base（近似）"""
        return float(self._config.retries.exponential_base)
    
    def get_retry_config(self, category: str = "default") -> Dict[str, Any]:
        """新 API: 直接访问 config.retries"""
        return {
            "max_retries": self.get_max_retries(category),
            "delay": self.get_retry_delay(category),
            "backoff": "exponential",
        }
    
    def get_path(self, name: str = "data") -> str:
        """新 API: config.paths.<name>"""
        return getattr(self._config.paths, name, f"./{name}")
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """新 API: config.api_keys.<provider>"""
        return getattr(self._config.api_keys, provider, None)
    
    # ── 新增: 直接访问新配置 ──────────────────────────────────────────
    
    @property
    def new_config(self) -> _NanochatConfig:
        """直接访问新的 Nanochat 配置（推荐）"""
        return self._config


def get_unified_config() -> UnifiedConfig:
    """兼容旧 API: 获取全局配置实例"""
    return UnifiedConfig.get_instance()


def set_unified_config(config: UnifiedConfig):
    """兼容旧 API: 设置全局配置实例"""
    UnifiedConfig._instance = config


# 更新 __all__ 导出
__all__ = [
    'AppConfig', 'OllamaConfig', 'ModelPathConfig', 'ModelMarketConfig',
    'ModelStoreConfig', 'WritingConfig', 'SearchConfig', 'AgentConfig',
    'load_config', 'save_config', 'get_hermes_home', 'get_env_value',
    'get_models_dir', 'get_projects_dir', 'get_config_dir',
    # 新增：UnifiedConfig 兼容层
    'UnifiedConfig', 'get_unified_config', 'set_unified_config',
]

