"""
LivingTree 统一配置系统
=======================

合并 NanochatConfig + OptimalConfig + UnifiedConfig 的设计精华：
- dataclass 类型安全（NanochatConfig 风格）
- 计算最优配置（OptimalConfig 风格）
- YAML 文件加载（UnifiedConfig 兼容）
- 环境变量覆盖
- 单例全局实例
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from threading import Lock


# ── 路径工具 ─────────────────────────────────────────────────────────

def _get_project_root() -> str:
    return str(Path(__file__).parent.parent.parent)


# ── 子配置 dataclass ─────────────────────────────────────────────────

@dataclass
class EndpointConfig:
    url: str = ""
    timeout: int = 30
    max_retries: int = 3


@dataclass
class RetryConfig:
    default: int = 3
    api: int = 3
    message: int = 5
    download: int = 3
    exponential_base: int = 2


@dataclass
class TimeoutConfig:
    default: int = 30
    long: int = 60
    browser: int = 15
    download: int = 120
    quick: int = 5
    search: int = 15
    llm_generate: int = 120


@dataclass
class DelayConfig:
    polling_short: float = 0.1
    polling_medium: float = 0.5
    polling_long: float = 1.0
    polling_image: int = 2
    polling_video: int = 3
    periodic_check: int = 5
    heartbeat: int = 30
    long_task: int = 60
    wait_short: int = 1
    wait_medium: int = 2
    wait_long: int = 5
    wait_extreme: int = 10


@dataclass
class LLMConfig:
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    max_tokens: int = 4096
    max_context: int = 8192
    batch_size: int = 32
    width: int = 64
    heads: int = 4
    learning_rate: float = 0.0003
    num_ctx: int = 8192
    num_gpu: int = 0
    keep_alive: str = "5m"


@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    default_model: str = ""
    num_ctx: int = 8192
    num_gpu: int = 0
    keep_alive: str = "5m"


@dataclass
class ModelMarketConfig:
    sources: list = field(default_factory=lambda: ["modelscope", "huggingface"])
    default_source: str = "modelscope"
    modelscope_token: str = ""
    modelscope_cache_dir: str = ""
    hf_token: str = ""
    hf_cache_dir: str = ""
    max_concurrent_downloads: int = 2
    download_timeout: int = 3600


@dataclass
class SearchConfig:
    serper_key: str = ""
    brave_key: str = ""
    cache_ttl_minutes: int = 60
    cn_sites: list = field(default_factory=lambda: [
        "zhihu.com", "juejin.cn", "weixin.qq.com", "bilibili.com"
    ])


@dataclass
class AgentBehaviorConfig:
    max_iterations: int = 90
    max_tokens: int = 4096
    temperature: float = 0.7
    stream_output: bool = True


@dataclass
class EvolutionConfig:
    enable_self_reflection: bool = True
    enable_strategy_optimization: bool = True
    enable_auto_repair: bool = True
    reflection_batch_size: int = 10
    improvement_threshold: float = 0.3


@dataclass
class ObservabilityConfig:
    enable_tracing: bool = True
    enable_metrics: bool = True
    enable_structured_logging: bool = True
    log_level: str = "INFO"
    opik_project: str = "livingtree"
    metrics_port: int = 9090


@dataclass
class DeepSeekConfig:
    base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    default_model: str = "deepseek-chat"
    thinking_model: str = "deepseek-reasoner"
    temperature: float = 0.7
    max_tokens: int = 8192
    enable_thinking: bool = True


# ── 主配置 ──────────────────────────────────────────────────────────

@dataclass
class LTAIConfig:
    project_root: str = field(default_factory=_get_project_root)
    version: str = "1.0.0"

    # 端点
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    deepseek: DeepSeekConfig = field(default_factory=DeepSeekConfig)
    endpoints: Dict[str, EndpointConfig] = field(default_factory=dict)

    # 子配置
    retries: RetryConfig = field(default_factory=RetryConfig)
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    delays: DelayConfig = field(default_factory=DelayConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    # 业务配置
    agent: AgentBehaviorConfig = field(default_factory=AgentBehaviorConfig)
    model_market: ModelMarketConfig = field(default_factory=ModelMarketConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    evolution: EvolutionConfig = field(default_factory=EvolutionConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)

    # 路径
    models_dir: str = ""
    storage_dir: str = ""
    ollama_home: str = ""
    default_project_dir: str = ""

    # P2P
    enable_p2p: bool = True
    relay_servers: list = field(default_factory=lambda: ["139.199.124.242:8888"])

    # 扩展
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.models_dir:
            self.models_dir = os.path.join(self.project_root, "models")
        if not self.storage_dir:
            self.storage_dir = os.path.join(self.project_root, "storage")
        self._decrypt_sensitive()

    def _decrypt_sensitive(self):
        try:
            from .encrypted_config import decrypt_value
            if self.deepseek.api_key:
                self.deepseek.api_key = decrypt_value(self.deepseek.api_key)
        except Exception:
            pass

    # ── 从 YAML 加载 ──

    @classmethod
    def from_yaml(cls, path: str = None) -> "LTAIConfig":
        if path is None:
            root = _get_project_root()
            paths = [
                os.path.join(root, "config", "livingtree.yaml"),
                os.path.join(root, "config", "config.yaml"),
            ]
        else:
            paths = [path]

        config = cls()

        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                    config._apply_yaml(data)
                    config._decrypt_sensitive()
                except Exception as e:
                    print(f"[LTAIConfig] YAML 加载失败 ({p}): {e}")

        config._apply_env_overrides()
        return config

    def _apply_yaml(self, data: Dict[str, Any]):
        for key, value in data.items():
            if key in ("ollama", "deepseek", "agent", "model_market", "search",
                       "evolution", "observability", "retries", "timeouts",
                       "delays", "llm"):
                sub_config = getattr(self, key, None)
                if isinstance(sub_config, object) and not isinstance(value, dict):
                    continue
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if hasattr(sub_config, sub_key):
                            setattr(sub_config, sub_key, sub_value)
            elif key == "endpoints":
                for ep_name, ep_data in value.items():
                    if isinstance(ep_data, dict):
                        self.endpoints[ep_name] = EndpointConfig(**ep_data)
            elif hasattr(self, key):
                setattr(self, key, value)
            else:
                self.extra[key] = value

    def _apply_env_overrides(self):
        overrides = {
            "OLLAMA_BASE_URL": ("ollama", "base_url"),
            "OLLAMA_DEFAULT_MODEL": ("ollama", "default_model"),
            "OLLAMA_NUM_CTX": ("ollama", "num_ctx"),
            "DEEPSEEK_API_KEY": ("deepseek", "api_key"),
            "DEEPSEEK_BASE_URL": ("deepseek", "base_url"),
            "DEEPSEEK_MODEL": ("deepseek", "default_model"),
            "LTAI_MODELS_DIR": ("models_dir", None),
            "LTAI_STORAGE_DIR": ("storage_dir", None),
            "LTAI_LOG_LEVEL": ("observability", "log_level"),
            "LTAI_MAX_ITERATIONS": ("agent", "max_iterations"),
        }
        for env_key, (attr_path, sub_attr) in overrides.items():
            val = os.environ.get(env_key)
            if val is not None:
                if sub_attr is None:
                    setattr(self, attr_path, val)
                else:
                    obj = getattr(self, attr_path)
                    if hasattr(obj, sub_attr):
                        converted = self._convert_type(val, type(getattr(obj, sub_attr)))
                        setattr(obj, sub_attr, converted)

    @staticmethod
    def _convert_type(value: str, target_type):
        if target_type is int:
            return int(value)
        if target_type is float:
            return float(value)
        if target_type is bool:
            return value.lower() in ("true", "1", "yes")
        return value

    # ── 计算最优配置 ──

    def compute_optimal(self, depth: int) -> "OptimalParams":
        return OptimalParams.compute(self, depth)

    def get(self, key: str, default: Any = None) -> Any:
        parts = key.split(".")
        obj = self
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                return default
        return obj


# ── 最优参数 ────────────────────────────────────────────────────────

@dataclass
class OptimalParams:
    depth: int
    timeout: float
    long_timeout: float
    quick_timeout: float
    retry_delay: float
    max_retries: int
    exponential_base: float
    polling_short: float
    polling_medium: float
    polling_long: float
    wait_short: float
    wait_long: float
    max_tokens: int
    max_context: int
    max_workers: int
    batch_size: int
    llm_temperature: float
    llm_top_p: float

    @classmethod
    def compute(cls, config: "LTAIConfig", depth: int) -> "OptimalParams":
        depth = max(1, min(depth, 10))
        factor = 1.0 + math.log(depth) * 0.5
        return cls(
            depth=depth,
            timeout=config.timeouts.default * factor,
            long_timeout=config.timeouts.long * factor,
            quick_timeout=config.timeouts.quick * factor,
            retry_delay=1.0 * factor,
            max_retries=int(config.retries.default * factor),
            exponential_base=config.retries.exponential_base,
            polling_short=config.delays.polling_short * factor,
            polling_medium=config.delays.polling_medium * factor,
            polling_long=config.delays.polling_long * factor,
            wait_short=config.delays.wait_short * factor,
            wait_long=config.delays.wait_long * factor,
            max_tokens=int(config.llm.max_tokens * factor),
            max_context=int(config.llm.max_context * factor),
            max_workers=max(1, int(depth * 2)),
            batch_size=max(1, int(config.llm.batch_size / factor)),
            llm_temperature=min(1.0, config.llm.temperature * (1.0 + depth * 0.05)),
            llm_top_p=min(1.0, config.llm.top_p),
        )


# ── 全局单例 ────────────────────────────────────────────────────────

import math

_global_config: Optional[LTAIConfig] = None
_config_lock = Lock()


def get_config(reload: bool = False) -> LTAIConfig:
    global _global_config
    if _global_config is None or reload:
        with _config_lock:
            if _global_config is None or reload:
                _global_config = LTAIConfig.from_yaml()
    return _global_config


config = get_config()

__all__ = [
    "LTAIConfig",
    "OptimalParams",
    "get_config",
    "config",
    "EndpointConfig",
    "RetryConfig",
    "TimeoutConfig",
    "DelayConfig",
    "LLMConfig",
    "OllamaConfig",
    "ModelMarketConfig",
    "SearchConfig",
    "AgentBehaviorConfig",
    "EvolutionConfig",
    "ObservabilityConfig",
]
