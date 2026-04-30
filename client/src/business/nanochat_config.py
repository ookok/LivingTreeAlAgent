"""
LivingTree AI - Nanochat 风格极简配置系统
=============================================

设计哲学 (来自 nanochat):
    - 配置即代码 (Configuration as Code)
    - 简单的 dataclass，不用 YAML
    - 合理的默认值，大多数情况不需要改
    - 直接导入使用，不用单例模式
    - 不需要热重载，改配置就重启
    - 环境变量在 Python 中直接处理。
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import os


# ── 子配置 dataclass ─────────────────────────────────────────────────────────

@dataclass
class EndpointConfig:
    """端点配置"""
    url: str = ""
    timeout: int = 30
    max_retries: int = 3


@dataclass
class RetryConfig:
    """重试配置"""
    default: int = 3
    api: int = 3           # API 请求重试次数
    message: int = 5
    download: int = 3
    exponential_base: int = 2


@dataclass
class TimeoutConfig:
    """超时配置"""
    default: int = 30
    long: int = 60
    browser: int = 15
    download: int = 120
    quick: int = 5
    search: int = 15
    llm_generate: int = 120


@dataclass
class DelayConfig:
    """延迟配置（秒）"""
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
class AgentConfig:
    """Agent 配置"""
    init_timeout: int = 10
    task_poll_interval: float = 0.1


@dataclass
class LLMConfig:
    """LLM 默认参数"""
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    max_tokens: int = 2048


@dataclass
class ApiKeysConfig:
    """API Keys 配置（从环境变量加载）"""
    openai: Optional[str] = None
    anthropic: Optional[str] = None
    deepseek: Optional[str] = None
    moonshot: Optional[str] = None
    dashscope: Optional[str] = None
    modelscope: Optional[str] = None
    huggingface: Optional[str] = None
    
    def __post_init__(self):
        """自动从环境变量加载"""
        if self.openai is None:
            self.openai = os.getenv("OPENAI_API_KEY")
        if self.anthropic is None:
            self.anthropic = os.getenv("ANTHROPIC_API_KEY")
        if self.deepseek is None:
            self.deepseek = os.getenv("DEEPSEEK_API_KEY")
        if self.moonshot is None:
            self.moonshot = os.getenv("MOONSHOT_API_KEY")
        if self.dashscope is None:
            self.dashscope = os.getenv("DASHSCOPE_API_KEY")
        if self.modelscope is None:
            self.modelscope = os.getenv("MODELSCOPE_TOKEN")
        if self.huggingface is None:
            self.huggingface = os.getenv("HF_TOKEN")


@dataclass
class PathsConfig:
    """路径配置"""
    data: str = "./data"
    logs: str = "./logs"
    cache: str = "./cache"
    temp: str = "/tmp"
    distillation: str = "./data/distillation"
    templates: str = "./data/templates"
    vector_db: str = "./data/vector_db"
    regulations: str = "./data/regulations"


@dataclass
class LimitsConfig:
    """资源限制"""
    max_file_size: int = 52428800  # 50MB
    max_cache_size: int = 1073741824  # 1GB
    max_tokens: int = 2048
    max_context: int = 4096
    max_level: int = 4


@dataclass
class CognitiveConfig:
    """认知框架配置"""
    # 心理表征配置
    mental_model_enabled: bool = True
    embedding_dim: int = 384
    
    # 注意力控制配置
    attention_enabled: bool = True
    focus_stack_max_depth: int = 10
    default_priority: str = "medium"
    
    # 元认知监控配置
    meta_reasoning_enabled: bool = True
    confidence_threshold: float = 0.6
    fallback_on_low_confidence: bool = True
    
    # 经验档案配置
    experience_manager_enabled: bool = True
    similarity_threshold: float = 0.7
    max_cases_per_query: int = 10
    
    # 创意引擎配置
    idea_generator_enabled: bool = True
    default_num_ideas: int = 5
    diversity_weight: float = 0.3


@dataclass
class IndustryGovernanceConfig:
    """行业知识治理配置"""
    
    # 目标行业
    target_industry: str = "通用"
    
    # 来源白名单（仅索引这些来源）
    source_whitelist: List[str] = field(default_factory=lambda: [
        "国标", "行标", "技术手册", "专利", "权威论文", "内部项目文档"
    ])
    
    # 来源黑名单（排除这些来源）
    source_blacklist: List[str] = field(default_factory=lambda: [
        "通用百科", "新闻", "论坛帖子", "博客", "社交媒体"
    ])
    
    # 最小权威等级要求 (1-5)
    min_authority_level: int = 2
    
    # 是否允许过期文档
    allow_outdated_docs: bool = False
    
    # 相关性打分权重
    domain_weight: float = 0.35
    timeliness_weight: float = 0.25
    authority_weight: float = 0.25
    confidence_weight: float = 0.15
    
    # 相关性阈值
    pass_threshold: float = 0.6
    warning_threshold: float = 0.4
    
    # 是否向用户暴露来源
    source_visibility: bool = True
    
    # 层级权重配置
    tier_l1_weight: float = 0.55  # 核心层（企业私有）
    tier_l2_weight: float = 0.35  # 行业层（公开标准）
    tier_l3_weight: float = 0.10  # 通用层（百科）
    
    # 行业方言支持
    dialect_enabled: bool = True
    default_region: str = "南京"


# ── 主配置类 ───────────────────────────────────────────────────────────────────

@dataclass
class NanochatConfig:
    """
    Nanochat 风格极简配置（主类）
    
    设计原则:
        1. 所有配置都是 dataclass 字段
        2. 合理的默认值
        3. 直接访问（config.ollama.url）
        4. 不需要单例模式（直接导入 config）
        5. 不需要热重载（重启即可）
        6. 同时支持属性访问和字典式访问
    
    使用示例:
        from client.src.business.nanochat_config import config
        
        # 读取配置（推荐：属性访问，最快）
        url = config.ollama.url
        timeout = config.timeouts.default
        max_retries = config.retries.default
        
        # 读取配置（兼容：字典式访问）
        url = config["ollama.url"]
        
        # 修改配置（运行时）
        config.ollama.url = "http://new-host:11434"
        config["ollama.url"] = "http://new-host:11434"
        
        # 检查 API Key
        if config.api_keys.openai:
            print("OpenAI API Key 已配置")
        
        # 包含检查
        if "ollama.url" in config:
            print("ollama.url 已配置")
    """
    
    # 服务端点
    ollama: EndpointConfig = field(default_factory=lambda: EndpointConfig(
        url="http://www.mogoo.com.cn:8899/v1",
        timeout=120,
        max_retries=3,
    ))
    
    cloud_sync: EndpointConfig = field(default_factory=lambda: EndpointConfig(
        url="ws://localhost:8765/sync",
        timeout=30,
        max_retries=3,
    ))
    
    tracker: EndpointConfig = field(default_factory=lambda: EndpointConfig(
        url="http://localhost:8765",
    ))
    
    relay: EndpointConfig = field(default_factory=lambda: EndpointConfig(
        url="ws://139.199.124.242:8888",
        timeout=60,
        max_retries=5,
    ))
    
    # 超时配置
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    
    # 重试配置
    retries: RetryConfig = field(default_factory=RetryConfig)
    
    # 延迟配置
    delays: DelayConfig = field(default_factory=DelayConfig)
    
    # Agent 配置
    agent: AgentConfig = field(default_factory=AgentConfig)
    
    # LLM 默认参数
    llm: LLMConfig = field(default_factory=LLMConfig)
    
    # API Keys（自动从环境变量加载）
    api_keys: ApiKeysConfig = field(default_factory=ApiKeysConfig)
    
    # 路径配置
    paths: PathsConfig = field(default_factory=PathsConfig)
    
    # 资源限制
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    
    # 认知框架配置
    cognitive: CognitiveConfig = field(default_factory=CognitiveConfig)
    
    # 行业知识治理配置
    industry_governance: IndustryGovernanceConfig = field(default_factory=IndustryGovernanceConfig)
    
    # ── 常用快捷属性 ─────────────────────────────────────────────────────────
    
    @property
    def ollama_url(self) -> str:
        """获取 Ollama 服务地址（快捷属性）"""
        return self.ollama.url
    
    @property
    def ollama_timeout(self) -> int:
        """获取 Ollama 超时时间（快捷属性）"""
        return self.ollama.timeout
    
    @property
    def default_timeout(self) -> int:
        """获取默认超时时间（快捷属性）"""
        return self.timeouts.default
    
    @property
    def default_retries(self) -> int:
        """获取默认重试次数（快捷属性）"""
        return self.retries.default
    
    # ── 字典式访问（支持 config["ollama.url"]）────────────────────────────
    
    def __getitem__(self, key: str) -> Any:
        """
        支持字典式读取: config["ollama.url"]
        
        推荐使用: config.ollama.url（更快）
        此方法为了兼容从 UnifiedConfig 迁移过来的代码
        """
        keys = key.split('.')
        obj = self
        
        for k in keys:
            if isinstance(obj, dict):
                obj = obj.get(k)
            else:
                obj = getattr(obj, k, None)
            
            if obj is None:
                raise KeyError(key)
        
        return obj
    
    def __setitem__(self, key: str, value: Any) -> None:
        """
        支持字典式写入: config["ollama.url"] = "..."
        """
        keys = key.split('.')
        obj = self
        
        for k in keys[:-1]:
            if isinstance(obj, dict):
                obj = obj[k]
            else:
                obj = getattr(obj, k)
        
        last_key = keys[-1]
        if isinstance(obj, dict):
            obj[last_key] = value
        else:
            setattr(obj, last_key, value)
    
    def __contains__(self, key: str) -> bool:
        """支持 'ollama.url' in config"""
        try:
            self[key]
            return True
        except (KeyError, AttributeError):
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        ⚠️ 已废弃: 请使用 config.ollama.url 或 config["ollama.url"]
        
        兼容旧 API: config.get("endpoints.ollama.url")
        """
        import warnings
        warnings.warn(
            f"NanochatConfig.get() 已废弃，请使用 config.{key.replace('.', '.')}",
            DeprecationWarning,
            stacklevel=2
        )
        try:
            return self[key]
        except KeyError:
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        ⚠️ 已废弃: 请使用 config.ollama.url = "..." 或 config["ollama.url"] = "..."
        
        兼容旧 API: config.set("endpoints.ollama.url", "...")
        """
        import warnings
        warnings.warn(
            f"NanochatConfig.set() 已废弃，请使用直接赋值",
            DeprecationWarning,
            stacklevel=2
        )
        self[key] = value
    
    # ── 导出为字典（用于调试/序列化）─────────────────────────────────────
    
    def to_dict(self) -> Dict[str, Any]:
        """导出为字典（用于调试或序列化）"""
        import dataclasses
        
        def convert(obj):
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                return {k.name: convert(getattr(obj, k.name)) for k in dataclasses.fields(obj)}
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(item) for item in obj]
            else:
                return obj
        
        return convert(self)
    
    # ── 从环境变量覆盖（可选，用于部署）────────────────────────────────────
    
    def load_from_env(self, prefix: str = "LIVINGTREE_") -> None:
        """
        从环境变量覆盖配置
        
        环境变量命名规则:
            LIVINGTREE_OLLAMA_URL -> config.ollama.url
            LIVINGTREE_TIMEOUTS_DEFAULT -> config.timeouts.default
        
        使用场景:
            - Docker 容器部署
            - 云平台部署
            - 测试环境配置
        """
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            
            # 解析环境变量名
            config_key = key[len(prefix):].lower()
            parts = config_key.split('_')
            
            # 导航到目标对象
            obj = self
            for i, part in enumerate(parts[:-1]):
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    break
            else:
                # 设置值
                final_key = parts[-1]
                if hasattr(obj, final_key):
                    # 尝试类型转换
                    current_value = getattr(obj, final_key)
                    if isinstance(current_value, int):
                        setattr(obj, final_key, int(value))
                    elif isinstance(current_value, float):
                        setattr(obj, final_key, float(value))
                    elif isinstance(current_value, bool):
                        setattr(obj, final_key, value.lower() in ('true', '1', 'yes'))
                    else:
                        setattr(obj, final_key, value)
                    
                    print(f"[NanochatConfig] 从环境变量加载: {key} -> {config_key}")


# ── 全局配置实例 ─────────────────────────────────────────────────────────────

# 直接使用这个实例（不需要单例模式）
config = NanochatConfig()

# 可选：从环境变量加载覆盖（部署时使用）
# config.load_from_env()


# ── 兼容层：UnifiedConfig（已废弃，请直接使用 config）──────────────────

class UnifiedConfig:
    """
    ⚠️ 已废弃: 请直接使用 `from client.src.business.nanochat_config import config`
    
    兼容层: UnifiedConfig → NanochatConfig
    
    旧代码（仍然工作，但会显示弃用警告）:
        from client.src.business.config import UnifiedConfig
        config = UnifiedConfig.get_instance()
        url = config.get("endpoints.ollama.url")
    
    新代码（推荐）:
        from client.src.business.nanochat_config import config
        url = config.ollama.url
        # 或字典式访问
        url = config["ollama.url"]
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
        self._config = config
    
    def get(self, key: str, default: Any = None) -> Any:
        """⚠️ 已废弃: 请使用 config.ollama.url 或 config["ollama.url"]"""
        import warnings
        warnings.warn(
            f"UnifiedConfig.get() 已废弃，请使用 config.{key.replace('.', '.')}",
            DeprecationWarning,
            stacklevel=2
        )
        try:
            return self._config[key]
        except KeyError:
            return default
    
    def set(self, key: str, value: Any) -> None:
        """已废弃: 请使用 config.ollama.url = ... 或 config["ollama.url"] = ..."""
        import warnings
        warnings.warn(
            "UnifiedConfig.set() 已废弃，请使用直接赋值",
            DeprecationWarning,
            stacklevel=2
        )
        self._config[key] = value
    
    def __getattr__(self, name: str) -> Any:
        """代理属性访问到新配置"""
        return getattr(self._config, name)
    
    def __setattr__(self, name: str, value: Any) -> None:
        """代理属性设置到新配置"""
        if name == "_config":
            super().__setattr__(name, value)
        else:
            setattr(self._config, name, value)
    
    @property
    def new_config(self) -> NanochatConfig:
        """直接访问新的 Nanochat 配置（推荐）"""
        return self._config


def get_unified_config() -> UnifiedConfig:
    """兼容旧 API: 获取全局配置实例"""
    return UnifiedConfig.get_instance()


def set_unified_config(config: UnifiedConfig):
    """兼容旧 API: 设置全局配置实例"""
    UnifiedConfig._instance = config


# 导出
__all__ = ['config', 'NanochatConfig', 'EndpointConfig', 'RetryConfig', 
           'TimeoutConfig', 'DelayConfig', 'AgentConfig', 'LLMConfig', 
           'ApiKeysConfig', 'PathsConfig', 'LimitsConfig', 'CognitiveConfig',
           'IndustryGovernanceConfig',
           # 兼容层（已废弃）
           'UnifiedConfig', 'get_unified_config', 'set_unified_config']
