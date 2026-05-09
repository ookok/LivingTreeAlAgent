"""LTAIConfig — Unified configuration system for the LivingTree digital life form.

Loads from:
1. Default values (hardcoded)
2. YAML config files (config/ltaiconfig.yaml)
3. Environment variables (LT_ prefix)

Usage:
    from livingtree.config import config, get_config
    config.ollama.base_url
    config.compute_optimal(depth=5)
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Optional

import yaml
from loguru import logger
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """LLM model configuration — uses TreeLLM for multi-provider routing."""

    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_api_key: str = ""

    flash_model: str = "deepseek/deepseek-v4-flash"
    flash_temperature: float = 0.3
    flash_max_tokens: int = 4096

    pro_model: str = "deepseek/deepseek-v4-pro"
    pro_temperature: float = 0.7
    pro_max_tokens: int = 8192
    pro_thinking_enabled: bool = True

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_flash_model: str = "qwen3.5:0.8b"
    ollama_small_model: str = "qwen2.5:1.5b"
    ollama_chat_model: str = "qwen3.5:4b"
    ollama_pro_model: str = "qwen3.5:9b"
    ollama_moe_model: str = "qwen3.6:35b-a3b"
    fallback_model: str = "qwen2.5:1.5b"  # Local fallback using Ollama

    longcat_base_url: str = "https://api.longcat.chat/openai/v1"
    longcat_api_key: str = ""
    longcat_flash_model: str = "openai/LongCat-Flash-Lite"
    longcat_flash_temperature: float = 0.3
    longcat_flash_max_tokens: int = 4096
    longcat_models: str = "openai/LongCat-Flash-Lite,openai/LongCat-Flash-Chat"
    longcat_chat_model: str = "openai/LongCat-Flash-Chat"
    longcat_chat_temperature: float = 0.5
    longcat_chat_max_tokens: int = 4096

    xiaomi_base_url: str = "https://api.xiaomimimo.com/v1"
    xiaomi_api_key: str = ""
    xiaomi_flash_model: str = "mimo-v2-flash"
    xiaomi_pro_model: str = "mimo-v2.5"

    aliyun_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    aliyun_api_key: str = ""
    aliyun_flash_model: str = "qwen-turbo"
    aliyun_pro_model: str = "qwen-max"

    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_api_key: str = ""
    zhipu_flash_model: str = "glm-4-flash"
    zhipu_pro_model: str = "glm-4-plus"

    dmxapi_base_url: str = "https://www.dmxapi.cn/v1"
    dmxapi_api_key: str = ""
    dmxapi_default_model: str = "gpt-5-mini"

    spark_base_url: str = "https://maas-api.cn-huabei-1.xf-yun.com/v2"
    spark_api_key: str = ""
    spark_default_model: str = "xdeepseekv3"

    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_api_key: str = ""
    siliconflow_flash_model: str = "Qwen/Qwen2.5-7B-Instruct"
    siliconflow_default_model: str = "Qwen/Qwen2.5-7B-Instruct"
    siliconflow_pro_model: str = "deepseek-ai/DeepSeek-V3"
    siliconflow_reasoning_model: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
    siliconflow_small_model: str = "Qwen/Qwen2.5-1.5B-Instruct"

    mofang_base_url: str = "https://ai.gitee.com/v1"
    mofang_api_key: str = ""
    mofang_flash_model: str = "Qwen/Qwen2.5-7B-Instruct"
    mofang_default_model: str = "Qwen/Qwen2.5-7B-Instruct"
    mofang_pro_model: str = "deepseek-ai/DeepSeek-V3"
    mofang_reasoning_model: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
    mofang_small_model: str = "Qwen/Qwen2.5-1.5B-Instruct"

    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_api_key: str = ""
    nvidia_default_model: str = "deepseek-ai/deepseek-r1"

    modelscope_base_url: str = "https://api-inference.modelscope.cn/v1"
    modelscope_api_key: str = ""
    modelscope_flash_model: str = "Qwen/Qwen3-8B"
    modelscope_flash_temperature: float = 0.3
    modelscope_flash_max_tokens: int = 4096
    modelscope_chat_model: str = "Qwen/Qwen2.5-72B-Instruct"
    modelscope_chat_temperature: float = 0.5
    modelscope_chat_max_tokens: int = 4096
    modelscope_pro_model: str = "deepseek-ai/DeepSeek-V3"
    modelscope_reasoning_model: str = "deepseek-ai/DeepSeek-R1"
    modelscope_small_model: str = "Qwen/Qwen2.5-7B-Instruct"

    bailing_base_url: str = "https://api.baichuan-ai.com/v1"
    bailing_api_key: str = ""
    bailing_flash_model: str = "Baichuan4-Turbo"
    bailing_flash_temperature: float = 0.3
    bailing_flash_max_tokens: int = 4096
    bailing_chat_model: str = "Baichuan4"
    bailing_chat_temperature: float = 0.5
    bailing_chat_max_tokens: int = 4096
    bailing_pro_model: str = "Baichuan4"
    bailing_reasoning_model: str = "Baichuan4"
    bailing_small_model: str = "Baichuan4-Air"

    stepfun_base_url: str = "https://api.stepfun.com/v1"
    stepfun_api_key: str = ""
    stepfun_flash_model: str = "step-1-flash"
    stepfun_flash_temperature: float = 0.3
    stepfun_flash_max_tokens: int = 4096
    stepfun_chat_model: str = "step-1-8k"
    stepfun_chat_temperature: float = 0.5
    stepfun_chat_max_tokens: int = 4096
    stepfun_pro_model: str = "step-2-16k"
    stepfun_reasoning_model: str = "step-2-16k"
    stepfun_small_model: str = "step-1-flash"

    internlm_base_url: str = "https://api.intern-ai.org.cn/v1"
    internlm_api_key: str = ""
    internlm_flash_model: str = "internlm2.5-7b-chat"
    internlm_flash_temperature: float = 0.3
    internlm_flash_max_tokens: int = 4096
    internlm_chat_model: str = "internlm2.5-20b-chat"
    internlm_chat_temperature: float = 0.5
    internlm_chat_max_tokens: int = 4096
    internlm_pro_model: str = "internlm3-latest"
    internlm_reasoning_model: str = "internlm3-latest"
    internlm_small_model: str = "internlm2.5-7b-chat"

    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    embedding_model: str = "all-MiniLM-L6-v2"


class CellConfig(BaseModel):
    """Cell layer configuration."""
    enabled: bool = True
    default_base_model: str = "gpt2"
    lora_r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.1
    learning_rate: float = 2e-4
    max_cells: int = 50
    auto_evolution: bool = True
    distillation_enabled: bool = True
    mitosis_threshold: int = 5
    regeneration_check_interval: float = 300.0
    checkpoint_dir: str = "./data/cells/checkpoints"


class NetworkConfig(BaseModel):
    """P2P network configuration."""
    enabled: bool = True
    node_name: str = "livingtree-node"
    lan_port: int = 9999
    discovery_interval: float = 30.0
    heartbeat_interval: float = 10.0
    max_peers: int = 100
    reputation_decay: float = 10.0
    trust_threshold: float = 1.0
    shared_secret: str = ""
    nat_enabled: bool = True
    relay_server: str = ""
    stun_server: str = "stun.l.google.com:19302"


class KnowledgeConfig(BaseModel):
    """Knowledge management configuration."""
    db_path: str = "./data/knowledge/kb.db"
    vector_dim: int = 128
    max_documents: int = 100000
    embedding_backend: str = "local"
    graph_enabled: bool = True
    format_discovery_enabled: bool = True
    gap_detection_interval: float = 3600.0


class ObservabilityConfig(BaseModel):
    """Observability configuration."""
    log_level: str = "INFO"
    log_file: str = "./data/logs/livingtree.log"
    log_rotation: str = "100 MB"
    log_retention: str = "30 days"
    metrics_enabled: bool = True
    metrics_port: int = 9090
    tracing_enabled: bool = True
    trace_sample_rate: float = 0.1


class EvolutionConfig(BaseModel):
    """Self-evolution configuration."""
    enabled: bool = True
    auto_mutation: bool = True
    mutation_rate: float = 0.1
    reflection_depth: int = 3
    code_absorption_enabled: bool = True
    skill_auto_discovery: bool = True
    tool_auto_registration: bool = True
    max_evolution_generations: int = 1000


class SafetyConfig(BaseModel):
    """Safety and security configuration."""
    default_policy: str = "deny"
    audit_enabled: bool = True
    sandbox_timeout: int = 30
    sandbox_max_memory_mb: int = 512
    kill_switch_enabled: bool = True
    allowed_domains: list[str] = Field(default_factory=list)
    blocked_patterns: list[str] = Field(default_factory=lambda: [
        "delete_system", "modify_os", "execute_unsigned_code", "self_modify_core"
    ])


class ExecutionConfig(BaseModel):
    """Task execution configuration."""
    max_parallel_tasks: int = 10
    task_timeout: int = 3600
    max_retries: int = 3
    retry_delay: float = 1.0
    plan_depth: int = 10
    auto_heal_enabled: bool = True
    heal_check_interval: float = 60.0
    orchestrator_max_agents: int = 20


class DocEngineConfig(BaseModel):
    """Document engine configuration."""
    enabled: bool = True
    output_dir: str = "./data/output"
    template_dir: str = "./data/templates"
    default_format: str = "markdown"

    # Industrial report templates
    eia_template: list[str] = Field(default_factory=lambda: [
        "总论", "工程分析", "环境现状调查与评价", "环境影响预测与评价",
        "环境保护措施", "环境风险评价", "环境经济损益分析",
        "环境管理与监测计划", "结论与建议"
    ])
    emergency_plan_template: list[str] = Field(default_factory=lambda: [
        "总则", "基本情况", "环境风险识别", "应急组织体系",
        "应急响应", "后期处置", "应急保障", "附则"
    ])
    acceptance_template: list[str] = Field(default_factory=lambda: [
        "总论", "工程调查", "环境监测", "环境影响调查",
        "环境管理检查", "公众意见调查", "结论与建议"
    ])
    feasibility_template: list[str] = Field(default_factory=lambda: [
        "总论", "项目背景", "市场分析", "技术方案",
        "建设条件", "环境影响", "投资估算", "经济评价", "结论"
    ])


class APIConfig(BaseModel):
    """API server configuration."""
    host: str = "0.0.0.0"
    port: int = 8100
    workers: int = 1
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    ws_enabled: bool = True
    docs_enabled: bool = True


class LTAIConfig(BaseModel):
    """Top-level configuration for the LivingTree digital life form."""

    version: str = "2.0.0"
    model: ModelConfig = Field(default_factory=ModelConfig)
    cell: CellConfig = Field(default_factory=CellConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    evolution: EvolutionConfig = Field(default_factory=EvolutionConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    doc_engine: DocEngineConfig = Field(default_factory=DocEngineConfig)
    api: APIConfig = Field(default_factory=APIConfig)

    def compute_optimal(self, depth: int = 5) -> dict[str, Any]:
        """Compute optimal parameters based on task complexity."""
        return {
            "depth": min(depth, 20),
            "temperature": max(0.1, self.model.temperature - depth * 0.05),
            "max_tokens": min(self.model.max_tokens + depth * 256, 32768),
            "retries": min(self.execution.max_retries + depth, 10),
            "plan_depth": min(self.execution.plan_depth + depth, 30),
        }

    def to_yaml(self, path: Path | None = None) -> str:
        """Export configuration to YAML."""
        import yaml
        data = self.model_dump()
        yaml_str = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True)
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml_str, encoding="utf-8")
        return yaml_str

    @classmethod
    def from_yaml(cls, path: Path) -> "LTAIConfig":
        """Load configuration from YAML file."""
        if not path.exists():
            logger.warning(f"Config file not found: {path}, using defaults")
            return cls()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(**data)

    @classmethod
    def from_env(cls) -> "LTAIConfig":
        """Load configuration from environment variables (LT_ prefix)."""
        data = {}
        env_map: dict[str, tuple[str, type]] = {
            "LT_DEEPSEEK_API_KEY": ("model.deepseek_api_key", str),
            "LT_FLASH_MODEL": ("model.flash_model", str),
            "LT_PRO_MODEL": ("model.pro_model", str),
            "LT_FALLBACK_MODEL": ("model.fallback_model", str),
            "LT_NODE_NAME": ("network.node_name", str),
            "LT_LAN_PORT": ("network.lan_port", int),
            "LT_SHARED_SECRET": ("network.shared_secret", str),
            "LT_LOG_LEVEL": ("observability.log_level", str),
            "LT_API_HOST": ("api.host", str),
            "LT_API_PORT": ("api.port", int),
            "LT_MODELSCOPE_API_KEY": ("model.modelscope_api_key", str),
            "LT_MODELSCOPE_FLASH_MODEL": ("model.modelscope_flash_model", str),
            "LT_MODELSCOPE_CHAT_MODEL": ("model.modelscope_chat_model", str),
            "LT_MODELSCOPE_PRO_MODEL": ("model.modelscope_pro_model", str),
            "LT_MODELSCOPE_BASE_URL": ("model.modelscope_base_url", str),
            "LT_BAILING_API_KEY": ("model.bailing_api_key", str),
            "LT_BAILING_FLASH_MODEL": ("model.bailing_flash_model", str),
            "LT_BAILING_CHAT_MODEL": ("model.bailing_chat_model", str),
            "LT_BAILING_PRO_MODEL": ("model.bailing_pro_model", str),
            "LT_BAILING_BASE_URL": ("model.bailing_base_url", str),
            "LT_STEPFUN_API_KEY": ("model.stepfun_api_key", str),
            "LT_STEPFUN_FLASH_MODEL": ("model.stepfun_flash_model", str),
            "LT_STEPFUN_CHAT_MODEL": ("model.stepfun_chat_model", str),
            "LT_STEPFUN_PRO_MODEL": ("model.stepfun_pro_model", str),
            "LT_STEPFUN_BASE_URL": ("model.stepfun_base_url", str),
            "LT_INTERNLM_API_KEY": ("model.internlm_api_key", str),
            "LT_INTERNLM_FLASH_MODEL": ("model.internlm_flash_model", str),
            "LT_INTERNLM_CHAT_MODEL": ("model.internlm_chat_model", str),
            "LT_INTERNLM_PRO_MODEL": ("model.internlm_pro_model", str),
            "LT_INTERNLM_BASE_URL": ("model.internlm_base_url", str),
        }
        for env_key, (config_path, converter) in env_map.items():
            value = os.environ.get(env_key)
            if value is not None:
                keys = config_path.split(".")
                current = data
                for k in keys[:-1]:
                    current = current.setdefault(k, {})
                current[keys[-1]] = converter(value)
        return cls(**data)


_config_lock = threading.Lock()
_config_instance: Optional[LTAIConfig] = None
_config_paths: list[Path] = []


def _find_config_paths() -> list[Path]:
    """Find config file in standard locations."""
    paths = [
        Path("config/ltaiconfig.yaml"),
        Path("config/config.yaml"),
        Path.home() / ".livingtree" / "config.yaml",
    ]
    return [p for p in paths if p.exists()]


def _load_config() -> LTAIConfig:
    """Internal: load configuration from file + secrets vault + env overrides."""
    paths = _find_config_paths()
    if paths:
        config = LTAIConfig.from_yaml(paths[0])
        logger.info(f"Loaded config from {paths[0]}")
    else:
        config = LTAIConfig()
        logger.info("Using default configuration")

    # Load API keys from encrypted secret vault
    try:
        from .secrets import get_secret_vault
        vault = get_secret_vault()
        api_key = vault.get("deepseek_api_key", "")
        if api_key:
            config.model.deepseek_api_key = api_key
            logger.info("Loaded deepseek_api_key from encrypted vault")
        longcat_key = vault.get("longcat_api_key", "")
        if longcat_key:
            config.model.longcat_api_key = longcat_key
            logger.info("Loaded longcat_api_key from encrypted vault")
        xiaomi_key = vault.get("xiaomi_api_key", "")
        if xiaomi_key:
            config.model.xiaomi_api_key = xiaomi_key
            logger.info("Loaded xiaomi_api_key from encrypted vault")
        aliyun_key = vault.get("aliyun_api_key", "")
        if aliyun_key:
            config.model.aliyun_api_key = aliyun_key
            logger.info("Loaded aliyun_api_key from encrypted vault")
        zhipu_key = vault.get("zhipu_api_key", "")
        if zhipu_key:
            config.model.zhipu_api_key = zhipu_key
            logger.info("Loaded zhipu_api_key from encrypted vault")
        dmxapi_key = vault.get("dmxapi_api_key", "")
        if dmxapi_key:
            config.model.dmxapi_api_key = dmxapi_key
            logger.info("Loaded dmxapi_api_key from encrypted vault")
        spark_key = vault.get("spark_api_key", "")
        if spark_key:
            config.model.spark_api_key = spark_key
            logger.info("Loaded spark_api_key from encrypted vault")

        siliconflow_key = vault.get("siliconflow_api_key", "")
        if siliconflow_key:
            config.model.siliconflow_api_key = siliconflow_key
            logger.info("Loaded siliconflow_api_key from encrypted vault")

        mofang_key = vault.get("mofang_api_key", "")
        if mofang_key:
            config.model.mofang_api_key = mofang_key
            logger.info("Loaded mofang_api_key from encrypted vault")

        nvidia_key = vault.get("nvidia_api_key", "")
        if nvidia_key:
            config.model.nvidia_api_key = nvidia_key
            config.model.nvidia_base_url = vault.get("nvidia_base_url", "https://integrate.api.nvidia.com/v1")
            config.model.nvidia_default_model = vault.get("nvidia_default_model", "deepseek-ai/deepseek-r1")
            logger.info("Loaded nvidia_api_key from encrypted vault")

        modelscope_key = vault.get("modelscope_api_key", "")
        if modelscope_key:
            config.model.modelscope_api_key = modelscope_key
            logger.info("Loaded modelscope_api_key from encrypted vault")
        bailing_key = vault.get("bailing_api_key", "")
        if bailing_key:
            config.model.bailing_api_key = bailing_key
            logger.info("Loaded bailing_api_key from encrypted vault")
        stepfun_key = vault.get("stepfun_api_key", "")
        if stepfun_key:
            config.model.stepfun_api_key = stepfun_key
            logger.info("Loaded stepfun_api_key from encrypted vault")
        internlm_key = vault.get("internlm_api_key", "")
        if internlm_key:
            config.model.internlm_api_key = internlm_key
            logger.info("Loaded internlm_api_key from encrypted vault")
    except Exception as e:
        logger.debug(f"Secret vault load skipped: {e}")

    env_config = LTAIConfig.from_env()
    if env_config.model_dump(exclude_defaults=True):
        merged = config.model_dump()
        _deep_merge(merged, env_config.model_dump(exclude_defaults=True))
        config = LTAIConfig(**merged)
        logger.info("Applied environment variable overrides")

    return config


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override dict into base dict."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def get_config(reload: bool = False) -> LTAIConfig:
    """Get the global configuration instance (thread-safe).

    Args:
        reload: If True, force reload from disk + environment.
    """
    global _config_instance
    with _config_lock:
        if _config_instance is None or reload:
            _config_instance = _load_config()
        return _config_instance


def reload_config() -> LTAIConfig:
    """Force reload configuration from disk."""
    return get_config(reload=True)


config: LTAIConfig
try:
    config = get_config()
except Exception:
    config = LTAIConfig()
