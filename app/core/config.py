"""
企业级配置管理
支持环境变量覆盖和配置验证
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from functools import lru_cache
import yaml


@dataclass
class SourceConfig:
    """下载源配置"""
    mirror: str
    token: Optional[str] = None
    cache_dir: str = "./models"
    max_workers: int = 3
    timeout: int = 300


@dataclass
class InferenceConfig:
    """推理配置"""
    default_context_size: int = 4096
    default_n_threads: int = 4
    default_n_gpu_layers: int = 0
    batch_size: int = 512
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    top_k: int = 40


@dataclass
class HardwareConfig:
    """硬件配置"""
    auto_detect: bool = True
    gpu_memory_threshold: float = 0.8
    system_memory_threshold: float = 0.85
    low_memory_mode: bool = False


@dataclass
class MonitoringConfig:
    """监控配置"""
    enabled: bool = True
    metrics_port: int = 9090
    prometheus_endpoint: str = "/metrics"
    collect_interval: int = 5
    alert_rules: Dict[str, float] = field(default_factory=lambda: {
        "memory_usage_threshold": 85,
        "disk_usage_threshold": 90,
        "gpu_usage_threshold": 95
    })


@dataclass
class SecurityConfig:
    """安全配置"""
    enabled: bool = False
    api_key_header: str = "X-API-Key"
    rate_limit_per_minute: int = 60
    jwt_secret: Optional[str] = None
    jwt_expire_hours: int = 24


@dataclass
class AppConfig:
    """完整应用配置"""
    system_name: str = "Hermes Desktop"
    version: str = "2.0.0"
    debug: bool = False
    
    modelscope: SourceConfig = field(default_factory=lambda: SourceConfig(
        mirror="https://mirror.modelScope.cn"
    ))
    huggingface: SourceConfig = field(default_factory=lambda: SourceConfig(
        mirror="https://hf-mirror.com"
    ))
    
    inference: InferenceConfig = field(default_factory=InferenceConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    model_dir: Path = field(default_factory=lambda: Path("./models"))
    log_dir: Path = field(default_factory=lambda: Path("./logs"))


class ConfigManager:
    """配置管理器"""
    
    _instance: Optional['ConfigManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.config_path = Path(__file__).parent / "config.yaml"
        self._config: Dict[str, Any] = {}
        self._app_config: Optional[AppConfig] = None
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        if not self.config_path.exists():
            self._create_default_config()
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        # 环境变量替换
        self._config = self._resolve_env_vars(self._config)
        
        # 构建 AppConfig
        self._build_app_config()
    
    def _resolve_env_vars(self, config: Dict) -> Dict:
        """递归解析环境变量"""
        result = {}
        for key, value in config.items():
            if isinstance(value, dict):
                result[key] = self._resolve_env_vars(value)
            elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                result[key] = os.getenv(env_var, "")
            else:
                result[key] = value
        return result
    
    def _build_app_config(self):
        """构建 AppConfig 对象"""
        sys_cfg = self._config.get("system", {})
        ms_cfg = self._config.get("sources", {}).get("modelscope", {})
        hf_cfg = self._config.get("sources", {}).get("huggingface", {})
        inf_cfg = self._config.get("inference", {})
        hw_cfg = self._config.get("hardware", {})
        mon_cfg = self._config.get("monitoring", {})
        sec_cfg = self._config.get("security", {})
        
        self._app_config = AppConfig(
            system_name=sys_cfg.get("name", "Hermes Desktop"),
            version=sys_cfg.get("version", "2.0.0"),
            debug=sys_cfg.get("debug", False),
            modelscope=SourceConfig(**ms_cfg) if ms_cfg else SourceConfig(
                mirror="https://mirror.modelScope.cn"
            ),
            huggingface=SourceConfig(**hf_cfg) if hf_cfg else SourceConfig(
                mirror="https://hf-mirror.com"
            ),
            inference=InferenceConfig(**inf_cfg) if inf_cfg else InferenceConfig(),
            hardware=HardwareConfig(**hw_cfg) if hw_cfg else HardwareConfig(),
            monitoring=MonitoringConfig(**mon_cfg) if mon_cfg else MonitoringConfig(),
            security=SecurityConfig(**sec_cfg) if sec_cfg else SecurityConfig(),
            model_dir=Path(self._config.get("model_dir", "./models")),
            log_dir=Path(self._config.get("log_dir", "./logs"))
        )
    
    def _create_default_config(self):
        """创建默认配置文件"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        default_config = {
            "system": {
                "name": "Hermes Desktop",
                "version": "2.0.0",
                "debug": False
            },
            "sources": {
                "modelscope": {
                    "mirror": "https://mirror.modelScope.cn",
                    "cache_dir": "./models"
                },
                "huggingface": {
                    "mirror": "https://hf-mirror.com",
                    "cache_dir": "./models"
                }
            },
            "inference": {
                "default_context_size": 4096,
                "default_n_threads": 4,
                "temperature": 0.7
            },
            "hardware": {
                "auto_detect": True,
                "gpu_memory_threshold": 0.8,
                "system_memory_threshold": 0.85
            },
            "monitoring": {
                "enabled": True,
                "collect_interval": 5
            },
            "security": {
                "enabled": False
            },
            "model_dir": "./models",
            "log_dir": "./logs"
        }
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
    
    @property
    def app_config(self) -> AppConfig:
        """获取应用配置"""
        return self._app_config
    
    @property
    def raw_config(self) -> Dict[str, Any]:
        """获取原始配置"""
        return self._config.copy()
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def save(self):
        """保存配置到文件"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)
    
    def reload(self):
        """重新加载配置"""
        self._load_config()


@lru_cache(maxsize=1)
def get_config() -> ConfigManager:
    """获取配置管理器单例"""
    return ConfigManager()


def get_app_config() -> AppConfig:
    """获取应用配置"""
    return get_config().app_config
