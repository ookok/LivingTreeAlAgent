"""
DSPy 优化器配置

管理 DSPy 依赖、模型配置和优化器参数
"""

import os
import importlib.util
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


# ============ 依赖检查 ============

def is_dspy_available() -> bool:
    """检查 DSPy 是否可用"""
    return importlib.util.find_spec("dspy") is not None


# 延迟导入，避免影响无 DSPy 环境
_dspy = None
_dspy_teleprompt = None


def _import_dspy():
    """延迟导入 DSPy"""
    global _dspy, _dspy_teleprompt
    if _dspy is None:
        if not is_dspy_available():
            raise ImportError(
                "DSPy 未安装。请运行: pip install dspy-ai\n"
                "或者设置配置中的 enable_dspy_optimizer=False 以禁用此功能"
            )
        import dspy
        _dspy = dspy
        try:
            from dspy import teleprompt
            _dspy_teleprompt = teleprompt
        except ImportError:
            _dspy_teleprompt = None
    return _dspy


# ============ 配置类 ============

@dataclass
class DSPyModelConfig:
    """DSPy 模型配置"""
    
    # LLM 配置
    provider: str = "ollama"  # "ollama", "openai", "LiteLLM"
    model_name: str = "llama3.2"
    api_base: str = "http://localhost:11434"
    api_key: str = ""
    
    # 优化器专用模型（用于 instruction generation）
    optimizer_model_name: Optional[str] = None
    optimizer_provider: Optional[str] = None
    
    # 检索器配置
    retriever_enabled: bool = False
    retriever_url: Optional[str] = None
    
    # 其他参数
    max_tokens: int = 4096
    temperature: float = 0.0  # 优化器需要确定性输出


@dataclass
class DSPyOptimizerConfig:
    """DSPy 优化器配置"""
    
    # 全局开关
    enabled: bool = True
    
    # 优化器选择
    # "mipro" - MIPROv2 (贝叶斯优化, 大数据量)
    # "copro" - COPRO (指令优化, 中等数据量)
    # "bootstrap" - BootstrapFewShot (快速, 小数据量)
    # "gepa" - GEPA (反思优化, Agent 系统)
    # "auto" - 根据数据量自动选择
    default_optimizer: str = "auto"
    
    # 训练集要求
    min_train_examples: int = 5      # 最小训练样本数
    min_dev_examples: int = 3        # 最小验证样本数
    max_train_examples: int = 500    # 最大训练样本数
    max_dev_examples: int = 100      # 最大验证样本数
    
    # MIPROv2 参数
    mipro_trials: int = 10
    mipro_candidates: int = 10
    
    # COPRO 参数
    copro_breadth: int = 10
    copro_depth: int = 3
    
    # Bootstrap 参数
    bootstrap_max_demos: int = 4
    
    # GEPA 参数
    gepa_reflection_steps: int = 3
    
    # 优化触发条件
    optimize_on_failure_rate: float = 0.4       # 技能失败率超过此值时触发优化
    optimize_min_uses: int = 3                  # 最少使用次数
    optimize_cooldown_seconds: float = 3600.0   # 优化冷却时间（秒）
    
    # 签名优化
    optimize_signatures: bool = True
    optimize_few_shot: bool = True
    
    # 日志与调试
    verbose: bool = True
    log_optimization: bool = True


@dataclass
class DSPyIntegrationConfig:
    """DSPy 集成总配置"""
    
    model: DSPyModelConfig = field(default_factory=DSPyModelConfig)
    optimizer: DSPyOptimizerConfig = field(default_factory=DSPyOptimizerConfig)
    
    # 数据目录
    cache_dir: str = "~/.hermes-desktop/dspy_cache"
    trainset_dir: str = "~/.hermes-desktop/dspy_trainsets"
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        from dataclasses import asdict
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DSPyIntegrationConfig":
        """从字典反序列化"""
        model_data = data.get("model", {})
        optimizer_data = data.get("optimizer", {})
        return cls(
            model=DSPyModelConfig(**model_data),
            optimizer=DSPyOptimizerConfig(**optimizer_data),
            cache_dir=data.get("cache_dir", cls.__dataclass_fields__['cache_dir'].default),
            trainset_dir=data.get("trainset_dir", cls.__dataclass_fields__['trainset_dir'].default),
        )


# ============ 全局配置 ============

_default_config: Optional[DSPyIntegrationConfig] = None


def get_dspy_config() -> DSPyIntegrationConfig:
    """获取全局 DSPy 配置"""
    global _default_config
    if _default_config is None:
        _default_config = DSPyIntegrationConfig()
    return _default_config


def set_dspy_config(config: DSPyIntegrationConfig):
    """设置全局 DSPy 配置"""
    global _default_config
    _default_config = config


# ============ 初始化函数 ============

def init_dspy(config: Optional[DSPyIntegrationConfig] = None) -> bool:
    """
    初始化 DSPy 环境
    
    Returns:
        bool: 是否成功初始化
    """
    if not is_dspy_available():
        return False
    
    config = config or get_dspy_config()
    
    try:
        dspy = _import_dspy()
        
        # 配置 LM
        if config.model.provider == "ollama":
            lm = dspy.LM(
                f"ollama_chat/{config.model.model_name}",
                api_base=config.model.api_base,
                api_key="",
                max_tokens=config.model.max_tokens,
            )
        elif config.model.provider == "openai":
            lm = dspy.LM(
                f"openai/{config.model.model_name}",
                api_key=config.model.api_key or os.environ.get("OPENAI_API_KEY", ""),
                api_base=config.model.api_base,
                max_tokens=config.model.max_tokens,
            )
        else:
            # 默认使用 LiteLLM 格式
            lm = dspy.LM(
                f"{config.model.provider}/{config.model.model_name}",
                api_key=config.model.api_key,
                api_base=config.model.api_base,
                max_tokens=config.model.max_tokens,
            )
        
        dspy.configure(lm=lm)
        
        # 配置优化器专用 LM
        if config.model.optimizer_model_name:
            opt_provider = config.model.optimizer_provider or config.model.provider
            opt_lm = dspy.LM(
                f"{opt_provider}/{config.model.optimizer_model_name}",
                api_key=config.model.api_key,
                api_base=config.model.api_base,
                max_tokens=config.model.max_tokens,
            )
            dspy.configure(lm=lm, optimizer_lm=opt_lm)
        
        # 配置检索器
        if config.model.retriever_enabled and config.model.retriever_url:
            try:
                rm = dspy.ColBERTv2(url=config.model.retriever_url)
                dspy.configure(rm=rm)
            except Exception:
                pass
        
        # 创建缓存目录
        cache_path = os.path.expanduser(config.cache_dir)
        os.makedirs(cache_path, exist_ok=True)
        trainset_path = os.path.expanduser(config.trainset_dir)
        os.makedirs(trainset_path, exist_ok=True)
        
        return True
        
    except Exception as e:
        if config.optimizer.verbose:
            print(f"[Warning] DSPy 初始化失败: {e}")
        return False
