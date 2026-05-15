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
from pydantic import BaseModel, Field, model_validator


class ModelConfig(BaseModel):
    """LLM model configuration — uses TreeLLM for multi-provider routing."""

    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_api_key: str = ""

    flash_model: str = "deepseek/deepseek-v4-flash"
    flash_temperature: float = 0.3
    flash_max_tokens: int = 4096

    pro_model: str = "deepseek/deepseek-v4-pro"
    pro_temperature: float = 0.7
    pro_max_tokens: int = 8192
    pro_thinking_enabled: bool = True

    # HiFloat8 — Ascend 950 cone-precision acceleration (2.60x@128K)
    hifloat8_enabled: bool = False
    hifloat8_min_context_for_boost: int = 4096  # context tokens threshold

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_flash_model: str = "qwen3.5:0.8b"
    ollama_small_model: str = "qwen2.5:1.5b"
    ollama_chat_model: str = "qwen3.5:4b"
    ollama_pro_model: str = "qwen3.5:9b"
    ollama_moe_model: str = "qwen3.6:35b-a3b"
    fallback_model: str = "qwen2.5:1.5b"  # Local fallback using Ollama

    # llama.cpp server (local optimized inference)
    llamacpp_base_url: str = "http://localhost:8080"
    llamacpp_chat_model: str = "qwen3.5-4b"
    llamacpp_temperature: float = 0.8
    llamacpp_top_p: float = 0.9
    llamacpp_top_k: int = 40
    llamacpp_repeat_penalty: float = 1.1
    llamacpp_max_tokens: int = 512

    # MOSS-TTS-Nano GGUF (local speech synthesis, ~200MB Q4_K_M)
    moss_tts_gguf_path: str = "models/moss-tts-nano-q4km.gguf"
    moss_tts_voice: str = "xiaoshu"  # 小树专用声线
    moss_tts_enabled: bool = True

    # VibeVoice (premium local speech AI: ASR + TTS + VAD)
    vibevoice_base_url: str = "http://localhost:8085"
    vibevoice_enabled: bool = True
    vibevoice_voice: str = "xiaoshu"  # 小树声线

    # FreeBuff — ad-supported free LLM via OpenRouter (fallback tier)
    freebuff_openrouter_key: str = ""
    freebuff_model: str = "deepseek/deepseek-v4-flash:free"
    freebuff_enabled: bool = True

    # OpenRouter — 300+ models unified API (key stored in secrets.enc)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_default_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    openrouter_enabled: bool = True

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

    sensetime_base_url: str = "https://api.sensetime.com/v1"
    sensetime_api_key: str = ""
    sensetime_flash_model: str = "SenseChat-Turbo"
    sensetime_flash_temperature: float = 0.3
    sensetime_flash_max_tokens: int = 4096
    sensetime_pro_model: str = "SenseChat-Pro"
    sensetime_pro_temperature: float = 0.5
    sensetime_pro_max_tokens: int = 8192

    hunyuan_base_url: str = "https://api.hunyuan.cloud.tencent.com/v1"
    hunyuan_api_key: str = ""
    hunyuan_flash_model: str = "hunyuan-lite"
    hunyuan_pro_model: str = "hunyuan-pro"

    baidu_base_url: str = "https://qianfan.baidubce.com/v2"
    baidu_api_key: str = ""
    baidu_flash_model: str = "ernie-speed"
    baidu_pro_model: str = "ernie-4.0"

    # Third-party service keys (stored in encrypted vault)
    tianditu_key: str = ""
    tencent_map_key: str = ""
    baidu_map_key: str = ""

    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    embedding_model: str = "all-MiniLM-L6-v2"

    @staticmethod
    def _all_providers() -> list[str]:
        return ['deepseek', 'longcat', 'xiaomi', 'aliyun', 'zhipu',
                'dmxapi', 'spark', 'siliconflow', 'mofang', 'nvidia',
                'modelscope', 'bailing', 'stepfun', 'internlm',
                'sensetime', 'openrouter', 'hunyuan', 'baidu']

    @model_validator(mode='after')
    def validate_provider_config(self) -> 'ModelConfig':
        remote_providers = self._all_providers()
        warnings = []
        has_configured = False

        for prefix in remote_providers:
            base_url = getattr(self, f'{prefix}_base_url', '')
            api_key = getattr(self, f'{prefix}_api_key', '')
            if base_url and not api_key:
                warnings.append(prefix)
            elif base_url and api_key:
                has_configured = True

        object.__setattr__(self, '_provider_warnings', warnings)
        object.__setattr__(self, '_has_configured', has_configured)

        if self.ollama_base_url:
            object.__setattr__(self, '_has_configured', True)
        if self.llamacpp_base_url:
            object.__setattr__(self, '_has_configured', True)

        if self.flash_model == self.pro_model:
            logger.warning(
                f"ModelConfig: flash_model and pro_model are both '{self.flash_model}' — "
                "consider using different models for flash vs pro"
            )
        return self

    def report_configured_providers(self) -> None:
        """Log a single summary line after vault keys are loaded.

        Re-checks actual api_key values (post vault-loading) rather than
        relying on pre-vault validation state.
        """
        all_p = self._all_providers()
        configured = [p for p in all_p if getattr(self, f'{p}_api_key', '')]
        missing = [p for p in all_p if p not in configured]

        if configured:
            logger.info(
                f"ModelConfig: {len(configured)}/{len(all_p)} "
                f"providers ready"
            )
        if missing:
            logger.debug(
                f"ModelConfig: {len(missing)} providers without keys "
                f"({', '.join(missing)})"
            )

        if not missing:  # All providers have keys → fully configured
            pass
        elif len(missing) == len(all_p):
            logger.warning(
                "ModelConfig: no provider is fully configured. "
                "System will have limited LLM functionality."
            )

        return self


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


class UserConfig(BaseModel):
    """User preferences."""
    theme: str = "light"
    auto_update: bool = True
    auto_heal: bool = True


class MergeConfig(BaseModel):
    """Gray-release merge feature flags."""
    execution_pipeline: dict = Field(default_factory=lambda: {"enabled": False, "flow_pct": 0.0, "fallback_mode": True})
    network_mesh: dict = Field(default_factory=lambda: {"enabled": False, "flow_pct": 0.0, "fallback_mode": True})
    policy_guard: dict = Field(default_factory=lambda: {"enabled": True, "flow_pct": 1.0, "fallback_mode": False})
    skill_hub: dict = Field(default_factory=lambda: {"enabled": True, "flow_pct": 1.0, "fallback_mode": False})
    tts_unified: dict = Field(default_factory=lambda: {"enabled": True, "flow_pct": 1.0, "fallback_mode": False})


class EmailConfig(BaseModel):
    """Email notification configuration."""
    enabled: bool = False
    sender: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    recipients: list[str] = Field(default_factory=list)


class PathsConfig(BaseModel):
    """File system paths."""
    data: str = "./data"
    logs: str = "./logs"
    cache: str = "./cache"
    temp: str = "./tmp"
    output: str = "./output"


class EndpointsConfig(BaseModel):
    """External service endpoints."""
    relay_server: str = ""
    stun_server: str = "stun.l.google.com:19302"
    cloud_sync_url: str = ""
    market_tools_url: str = ""


class LTAIConfig(BaseModel):
    """Top-level configuration for the LivingTree digital life form.

    All config (except API keys in secrets.enc) lives in config/livingtree.yaml.
    Modify via CLI: livingtree config set <key> <value>"""

    model_config = {"extra": "allow"}

    version: str = "2.4.0"
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
    user: UserConfig = Field(default_factory=UserConfig)
    merges: MergeConfig = Field(default_factory=MergeConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    endpoints: EndpointsConfig = Field(default_factory=EndpointsConfig)

    def compute_optimal(self, depth: int = 5) -> dict[str, Any]:
        """Compute optimal parameters based on task complexity."""
        return {
            "depth": min(depth, 20),
            "temperature": max(0.1, self.model.flash_temperature - depth * 0.05),
            "max_tokens": min(self.model.flash_max_tokens + depth * 256, 32768),
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
            "LT_LONGCAT_API_KEY": ("model.longcat_api_key", str),
            "LT_XIAOMI_API_KEY": ("model.xiaomi_api_key", str),
            "LT_ALIYUN_API_KEY": ("model.aliyun_api_key", str),
            "LT_ZHIPU_API_KEY": ("model.zhipu_api_key", str),
            "LT_DMXAPI_API_KEY": ("model.dmxapi_api_key", str),
            "LT_SPARK_API_KEY": ("model.spark_api_key", str),
            "LT_SILICONFLOW_API_KEY": ("model.siliconflow_api_key", str),
            "LT_MOFANG_API_KEY": ("model.mofang_api_key", str),
            "LT_NVIDIA_API_KEY": ("model.nvidia_api_key", str),
            "LT_MODELSCOPE_API_KEY": ("model.modelscope_api_key", str),
            "LT_BAILING_API_KEY": ("model.bailing_api_key", str),
            "LT_STEPFUN_API_KEY": ("model.stepfun_api_key", str),
            "LT_INTERNLM_API_KEY": ("model.internlm_api_key", str),
            "LT_SENSETIME_API_KEY": ("model.sensetime_api_key", str),
            "LT_OPENROUTER_API_KEY": ("model.openrouter_api_key", str),
            "LT_HUNYUAN_API_KEY": ("model.hunyuan_api_key", str),
            "LT_BAIDU_API_KEY": ("model.baidu_api_key", str),
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
    """Find config file in standard locations (unified config)."""
    paths = [
        Path("config/livingtree.yaml"),
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

    # Load API keys from encrypted secret vault (unified loop over _all_providers)
    try:
        from .secrets import get_secret_vault
        vault = get_secret_vault()
        for prefix in ModelConfig._all_providers():
            key = vault.get(f"{prefix}_api_key", "")
            if key:
                setattr(config.model, f"{prefix}_api_key", key)
                logger.info(f"Loaded {prefix}_api_key from encrypted vault")
        # Extra per-provider settings (base_url / model overrides)
        nvidia_base = vault.get("nvidia_base_url", "")
        if nvidia_base:
            config.model.nvidia_base_url = nvidia_base
        nvidia_model = vault.get("nvidia_default_model", "")
        if nvidia_model:
            config.model.nvidia_default_model = nvidia_model
        spark_base = vault.get("spark_base_url", "")
        if spark_base:
            config.model.spark_base_url = spark_base

        # ── Non-provider secrets ──
        tdt_key = vault.get("tianditu_key", "")
        if tdt_key:
            config.model.tianditu_key = tdt_key
            logger.info("Loaded tianditu_key from encrypted vault")
        tx_key = vault.get("tencent_map_key", "")
        if tx_key:
            config.model.tencent_map_key = tx_key
            logger.info("Loaded tencent_map_key from encrypted vault")
        bd_key = vault.get("baidu_map_key", "")
        if bd_key:
            config.model.baidu_map_key = bd_key
            logger.info("Loaded baidu_map_key from encrypted vault")
        jwt_key = vault.get("jwt_secret", "")
        if jwt_key:
            config.model.jwt_secret = jwt_key
            logger.info("Loaded jwt_secret from encrypted vault")
        smtp_pw = vault.get("smtp_password", "")
        if smtp_pw and hasattr(config, 'email'):
            config.email.smtp_password = smtp_pw
            logger.info("Loaded smtp_password from encrypted vault")
    except Exception:
        pass

    # ── Seed built-in default keys on first run (encrypted) ──
    try:
        vault.seed_defaults()
    except Exception:
        pass

    # ── Load additional providers from YAML ──
    _load_providers_yaml(config)

    # ── Summary report (silent — no per-provider warnings) ──
    config.model.report_configured_providers()

    return config


def _load_providers_yaml(config: LTAIConfig) -> None:
    """Load additional providers from config/providers.yaml.

    Allows users to add new LLM providers without modifying settings.py.
    Format:
      providers:
        - name: my-provider
          base_url: https://api.example.com/v1
          api_key: sk-xxx  # or ${MY_PROVIDER_KEY} for env var
          flash_model: my-model-flash
          pro_model: my-model-pro
    """
    providers_yaml = Path("config/providers.yaml")
    if not providers_yaml.exists():
        return

    try:
        import yaml
        data = yaml.safe_load(providers_yaml.read_text(encoding="utf-8"))
        providers = data.get("providers", [])
        if not providers:
            return

        loaded = 0
        for p in providers:
            name = p.get("name", "")
            if not name:
                continue

            # Resolve env vars in api_key
            api_key = p.get("api_key", "")
            if api_key.startswith("${") and api_key.endswith("}"):
                env_var = api_key[2:-1]
                api_key = os.environ.get(env_var, "")

            base_url = p.get("base_url", "")
            if base_url:
                setattr(config.model, f"{name}_base_url", base_url)
            if api_key:
                setattr(config.model, f"{name}_api_key", api_key)

            flash = p.get("flash_model", "")
            pro = p.get("pro_model", "")
            if flash:
                setattr(config.model, f"{name}_flash_model", flash)
            if pro:
                setattr(config.model, f"{name}_pro_model", pro)

            loaded += 1
            logger.info(f"Loaded provider '{name}' from config/providers.yaml")

        if loaded:
            logger.info(f"Loaded {loaded} additional providers from config/providers.yaml")
    except Exception as e:
        logger.warning(f"Failed to load config/providers.yaml: {e}")


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


# ═══ Config Hot-Reload File Watcher ═══

import asyncio
import os
from pathlib import Path


class ConfigWatcher:
    """Polling-based config file watcher for hot-reload.

    Monitors config files for changes and auto-reloads configuration
    when any watched file is modified. Uses polling (low overhead) —
    suitable even without watchdog installed.

    Usage:
        watcher = ConfigWatcher(interval_sec=5)
        await watcher.start()
        ...
        await watcher.stop()
    """

    def __init__(self, interval_sec: float = 10.0):
        self._interval = interval_sec
        self._task: asyncio.Task | None = None
        self._mtimes: dict[str, float] = {}
        self._watch_paths: list[str] = []

    def add(self, path: str | Path) -> None:
        """Add a config file to watch."""
        p = str(path)
        if p not in self._watch_paths and os.path.isfile(p):
            self._watch_paths.append(p)
            self._mtimes[p] = os.path.getmtime(p)

    def add_defaults(self) -> None:
        """Watch the unified config files."""
        config_dir = Path(__file__).resolve().parent.parent.parent / "config"
        candidates = [
            "livingtree.yaml",
            "secrets.enc",
        ]
        for name in candidates:
            fpath = config_dir / name
            if fpath.is_file():
                self.add(fpath)

    async def start(self) -> None:
        """Start polling loop in background."""
        if self._task is not None:
            return
        from loguru import logger as _log
        self._task = asyncio.create_task(self._poll_loop())
        _log.info(f"ConfigWatcher: monitoring {len(self._watch_paths)} files (interval={self._interval}s)")

    async def stop(self) -> None:
        """Stop polling loop."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _poll_loop(self) -> None:
        from loguru import logger as _log
        while True:
            try:
                await asyncio.sleep(self._interval)
                changed = self._check_changes()
                if changed:
                    _log.info(f"ConfigWatcher: {len(changed)} file(s) changed, reloading...")
                    reload_config()
                    self._update_mtimes(changed)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                _log.debug(f"ConfigWatcher poll: {e}")

    def _check_changes(self) -> list[str]:
        changed = []
        for path in self._watch_paths:
            try:
                current = os.path.getmtime(path)
                if current != self._mtimes.get(path, current):
                    changed.append(path)
            except OSError:
                continue
        return changed

    def _update_mtimes(self, paths: list[str]) -> None:
        for path in paths:
            try:
                self._mtimes[path] = os.path.getmtime(path)
            except OSError:
                pass

    @property
    def watching(self) -> bool:
        return self._task is not None and not self._task.done()


_config_watcher: ConfigWatcher | None = None


def get_config_watcher(interval_sec: float = 10.0) -> ConfigWatcher:
    global _config_watcher
    if _config_watcher is None:
        _config_watcher = ConfigWatcher(interval_sec=interval_sec)
        _config_watcher.add_defaults()
    return _config_watcher


async def start_config_watcher(interval_sec: float = 10.0) -> ConfigWatcher:
    watcher = get_config_watcher(interval_sec=interval_sec)
    await watcher.start()
    return watcher

