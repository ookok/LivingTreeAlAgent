"""
L0-L4 模型层配置与部署方案
统一管理本地和远程模型的下载、部署和启动
"""

import json
import subprocess
import httpx
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


# ── 枚举定义 ────────────────────────────────────────────────────────────────

class DeployMode(str, Enum):
    """部署模式"""
    LOCAL = "local"           # 本地部署
    REMOTE = "remote"         # 远程服务器


class ModelTier(str, Enum):
    """模型层级"""
    L0 = "L0"                 # 快速路由/意图分类
    L1 = "L1"                 # 轻量推理/搜索
    L2 = "L2"                 # 中等推理
    L3 = "L3"                 # 深度推理/意图理解
    L4 = "L4"                 # 深度生成/思考模式


class ServiceStatus(str, Enum):
    """服务状态"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    DOWNLOADING = "downloading"


# ── 模型定义 ────────────────────────────────────────────────────────────────

class ModelDefinition(BaseModel):
    """模型定义"""
    tier: ModelTier
    name: str                  # 显示名称
    ollama_name: str           # Ollama 模型名
    size_gb: float             # 模型大小(GB)
    min_memory_gb: float        # 最低内存需求
    recommended_memory_gb: float # 推荐内存
    description: str           # 描述
    purpose: str               # 用途
    gpu_layers_hint: int = 0   # GPU 层数提示
    quant: str = "Q4_K_M"      # 量化方式


# ── 预定义 L0-L4 模型 ────────────────────────────────────────────────────────

L0_L4_MODELS: List[ModelDefinition] = [
    # L0: 快速路由/意图分类
    ModelDefinition(
        tier=ModelTier.L0,
        name="SmolLM2 (推荐)",
        ollama_name="smollm2:latest",
        size_gb=0.14,
        min_memory_gb=0.5,
        recommended_memory_gb=1.0,
        description="极小体积，毫秒级响应，适合快速路由",
        purpose="意图分类、快速路由",
        gpu_layers_hint=0,
        quant="Q4_K_M"
    ),
    ModelDefinition(
        tier=ModelTier.L0,
        name="Qwen2.5-0.5B",
        ollama_name="qwen2.5:0.5b",
        size_gb=0.4,
        min_memory_gb=1.0,
        recommended_memory_gb=1.5,
        description="阿里通义千问轻量版",
        purpose="意图分类、快速路由",
        gpu_layers_hint=0,
        quant="Q4_K_M"
    ),
    ModelDefinition(
        tier=ModelTier.L0,
        name="Qwen2.5-1.5B",
        ollama_name="qwen2.5:1.5b",
        size_gb=1.1,
        min_memory_gb=2.0,
        recommended_memory_gb=2.5,
        description="阿里通义千问均衡版",
        purpose="意图分类、快速路由、搜索",
        gpu_layers_hint=0,
        quant="Q4_K_M"
    ),

    # L1: 轻量推理
    ModelDefinition(
        tier=ModelTier.L1,
        name="Qwen2.5-3B",
        ollama_name="qwen2.5:3b",
        size_gb=2.0,
        min_memory_gb=3.0,
        recommended_memory_gb=4.0,
        description="通义千问中等规模",
        purpose="轻量推理、搜索增强",
        gpu_layers_hint=0,
        quant="Q4_K_M"
    ),

    # L2: 中等推理
    ModelDefinition(
        tier=ModelTier.L2,
        name="Qwen2.5-7B",
        ollama_name="qwen2.5:7b",
        size_gb=4.7,
        min_memory_gb=6.0,
        recommended_memory_gb=8.0,
        description="通义千问标准版 (推荐日常使用)",
        purpose="通用对话、文档处理",
        gpu_layers_hint=32,
        quant="Q4_K_M"
    ),

    # L3: 深度推理
    ModelDefinition(
        tier=ModelTier.L3,
        name="Qwen3.5-4B (推荐)",
        ollama_name="qwen3.5:4b",
        size_gb=2.9,
        min_memory_gb=4.0,
        recommended_memory_gb=6.0,
        description="通义千问思考模型，推理能力强",
        purpose="意图理解、复杂推理",
        gpu_layers_hint=32,
        quant="Q4_K_M"
    ),
    ModelDefinition(
        tier=ModelTier.L3,
        name="Qwen3.5-2B",
        ollama_name="qwen3.5:2b",
        size_gb=1.5,
        min_memory_gb=2.5,
        recommended_memory_gb=4.0,
        description="通义千问思考模型轻量版",
        purpose="意图理解、复杂推理",
        gpu_layers_hint=16,
        quant="Q4_K_M"
    ),

    # L4: 深度生成
    ModelDefinition(
        tier=ModelTier.L4,
        name="Qwen3.5-9B (推荐)",
        ollama_name="qwen3.5:9b",
        size_gb=6.0,
        min_memory_gb=8.0,
        recommended_memory_gb=12.0,
        description="通义千问深度思考模型，复杂任务首选",
        purpose="深度生成、复杂分析、思考模式",
        gpu_layers_hint=48,
        quant="Q4_K_M"
    ),
    ModelDefinition(
        tier=ModelTier.L4,
        name="DeepSeek-R1-70B",
        ollama_name="deepseek-r1:70b",
        size_gb=43.0,
        min_memory_gb=48.0,
        recommended_memory_gb=64.0,
        description="深度求索推理模型，超大参数",
        purpose="深度分析、复杂推理",
        gpu_layers_hint=96,
        quant="Q4_K_M"
    ),
]


# ── 层配置 ──────────────────────────────────────────────────────────────────

class LayerConfig(BaseModel):
    """单层配置"""
    tier: ModelTier
    model: Optional[ModelDefinition] = None
    status: ServiceStatus = ServiceStatus.STOPPED
    local_endpoint: str = "http://localhost:11434"
    remote_endpoint: str = ""
    auto_start: bool = True
    keep_alive: str = "5m"


class LayerDeploymentConfig(BaseModel):
    """L0-L4 层部署配置"""
    mode: DeployMode = DeployMode.LOCAL
    layers: Dict[str, LayerConfig] = Field(default_factory=dict)
    
    # 远程服务器配置
    remote_api_key: str = ""
    remote_base_url: str = "http://139.199.124.242:8899/v1"
    
    # 自动部署设置
    auto_deploy_all: bool = True
    download_on_start: bool = True
    
    # Ollama 基础配置
    ollama_base_url: str = "http://localhost:11434"
    
    class Config:
        use_enum_values = True


# ── 便捷函数 ─────────────────────────────────────────────────────────────────

def get_models_by_tier(tier: ModelTier) -> List[ModelDefinition]:
    """获取指定层级的所有模型"""
    return [m for m in L0_L4_MODELS if m.tier == tier]


def get_default_model_for_tier(tier: ModelTier) -> Optional[ModelDefinition]:
    """获取指定层级的默认推荐模型"""
    tier_models = get_models_by_tier(tier)
    if not tier_models:
        return None
    # 返回标记为"推荐"的模型
    for m in tier_models:
        if "(推荐)" in m.name:
            return m
    # 否则返回第一个
    return tier_models[0]


def get_total_size_for_models(models: List[ModelDefinition]) -> float:
    """计算模型总大小"""
    return sum(m.size_gb for m in models)


def create_default_layer_config() -> LayerDeploymentConfig:
    """创建默认层配置"""
    config = LayerDeploymentConfig()
    
    # 为每个层级设置默认模型
    for tier in ModelTier:
        default_model = get_default_model_for_tier(tier)
        config.layers[tier.value] = LayerConfig(
            tier=tier,
            model=default_model,
            status=ServiceStatus.STOPPED,
            auto_start=True if default_model else False
        )
    
    return config


def save_layer_config(config: LayerDeploymentConfig, path: Optional[Path] = None) -> None:
    """保存层配置"""
    if path is None:
        path = Path(__file__).parent / ".layer_config.json"
    
    # 转换为可序列化格式
    data = config.model_dump()
    
    # 处理 LayerConfig 中的 model 字段
    for layer_key, layer in data.get("layers", {}).items():
        if layer.get("model"):
            # 保存模型完整信息
            model_data = layer["model"]
            layer["model_name"] = model_data.get("ollama_name", "")
            layer["model_size_gb"] = model_data.get("size_gb", 0)
            del layer["model"]
    
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_layer_config(path: Optional[Path] = None) -> LayerDeploymentConfig:
    """加载层配置"""
    if path is None:
        path = Path(__file__).parent / ".layer_config.json"
    
    if not path.exists():
        return create_default_layer_config()
    
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return LayerDeploymentConfig(**data)
    except Exception:
        return create_default_layer_config()


# ── 硬件检测 ─────────────────────────────────────────────────────────────────

def check_ollama_installed() -> bool:
    """检查 Ollama 是否已安装"""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_system_memory() -> Dict[str, float]:
    """获取系统内存信息"""
    try:
        import psutil
from core.logger import get_logger
logger = get_logger('model_layer_config')

        mem = psutil.virtual_memory()
        return {
            "total_gb": mem.total / (1024**3),
            "available_gb": mem.available / (1024**3),
            "used_gb": mem.used / (1024**3),
            "percent": mem.percent
        }
    except ImportError:
        return {"total_gb": 0, "available_gb": 0, "used_gb": 0, "percent": 0}


def get_recommended_models_for_hardware() -> List[ModelDefinition]:
    """根据硬件推荐合适的模型"""
    mem_info = check_system_memory()
    total_gb = mem_info.get("total_gb", 0)
    
    recommended = []
    for model in L0_L4_MODELS:
        if model.recommended_memory_gb <= total_gb * 0.5:
            recommended.append(model)
    
    return recommended


# ── 测试函数 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("L0-L4 模型层配置")
    logger.info("=" * 60)
    
    # 检查 Ollama
    logger.info(f"\n[系统检测]")
    logger.info(f"  Ollama 已安装: {check_ollama_installed()}")
    logger.info(f"  系统内存: {check_system_memory()}")
    
    # 显示模型列表
    logger.info(f"\n[预定义模型] ({len(L0_L4_MODELS)} 个)")
    for tier in ModelTier:
        models = get_models_by_tier(tier)
        logger.info(f"\n  {tier.value}:")
        for m in models:
            logger.info(f"    - {m.name} ({m.ollama_name}, {m.size_gb}GB)")
            logger.info(f"      用途: {m.purpose}")
    
    # 硬件推荐
    logger.info(f"\n[硬件推荐]")
    recommended = get_recommended_models_for_hardware()
    logger.info(f"  可运行模型: {len(recommended)} 个")
    for m in recommended[:5]:
        logger.info(f"    - {m.name} ({m.tier.value})")
    
    # 默认配置
    logger.info(f"\n[默认配置]")
    config = create_default_layer_config()
    logger.info(f"  部署模式: {config.mode}")
    logger.info(f"  自动部署: {config.auto_deploy_all}")
    
    logger.info("\n" + "=" * 60)
